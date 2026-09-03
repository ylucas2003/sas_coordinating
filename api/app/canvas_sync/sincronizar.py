"""Orquestração da sincronização Canvas → banco do SAS.

Duas rotinas sobre o mesmo núcleo (`_sincronizar_curso_simulados`):

  sincronizar_ano_atual()          — incremental, roda a cada 5 min via
                                     POST /canvas-sync/run. Só o curso
                                     "{ano} 3o ITA/IME Simulados" do ano
                                     vigente, só notas corrigidas na janela
                                     recente (graded_since).
  sincronizar_historico_completo() — backfill único, roda via
                                     scripts/canvas_backfill.py. Todos os
                                     anos + e-mail dos alunos.

Reaproveita os upserts genéricos de ingest/upsert.py — o Canvas é só uma
fonte nova para os mesmos dicts que a planilha produzia (com colunas extras).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from supabase import Client

from ..ingest.header import (
    ColunaSimulado,
    inferir_fase_simulados,
    parsear_section,
)
from ..ingest.upsert import (
    atualizar_periodo_ciclo,
    buscar_materia_por_codigo,
    upsert_alunos_em_lote,
    upsert_ano_letivo,
    upsert_ciclo,
    upsert_matriculas_em_lote,
    upsert_notas_em_lote,
    upsert_sede,
    upsert_simulados_em_lote,
    upsert_turma,
)
from ..stats import computavel
from . import mapeador
from .arquivos import sincronizar_arquivos_do_curso
from .cliente import ClienteCanvas
from .questoes import sincronizar_questoes_do_quiz


@dataclass
class ResumoSincronizacao:
    cursos_processados: int = 0
    alunos_processados: int = 0
    turmas_processadas: int = 0
    ciclos_processados: int = 0
    simulados_processados: int = 0
    notas_gravadas: int = 0
    emails_preenchidos: int = 0
    quizzes_sincronizados: int = 0
    respostas_questao_gravadas: int = 0
    arquivos_sincronizados: int = 0
    avisos: list[str] = field(default_factory=list)
    # Controle interno do recompute-alvo (NÃO vão pro audit jsonb — ver como_dict).
    simulados_tocados: set[str] = field(default_factory=set)
    alunos_tocados: set[str] = field(default_factory=set)

    def como_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # set não serializa em JSON, e são estado de controle, não auditoria.
        d.pop("simulados_tocados", None)
        d.pop("alunos_tocados", None)
        return d


# ─── Descoberta de cursos e ano vigente ───────────────────────────────────


async def _descobrir_cursos_simulados(
    canvas: ClienteCanvas, account_id: str
) -> list[tuple[int, dict[str, Any]]]:
    """[(ano, curso)] ordenado por ano, só cursos '{ano} 3o ITA/IME Simulados'."""
    cursos = await canvas.listar_cursos_da_conta(account_id, search_term="Simulados")
    encontrados: list[tuple[int, dict[str, Any]]] = []
    for curso in cursos:
        ano = mapeador.parsear_ano_curso_simulados(curso.get("name", ""))
        if ano is not None:
            encontrados.append((ano, curso))
    return sorted(encontrados, key=lambda par: par[0])


async def _curso_do_ano_vigente(
    canvas: ClienteCanvas, *, account_id: str, override_ano: str | None
) -> tuple[int, dict[str, Any]]:
    cursos = await _descobrir_cursos_simulados(canvas, account_id)
    if not cursos:
        raise RuntimeError("Nenhum curso '{ano} 3o ITA/IME Simulados' encontrado na conta.")
    if override_ano:
        alvo = int(override_ano)
        for ano, curso in cursos:
            if ano == alvo:
                return ano, curso
        raise RuntimeError(
            f"CANVAS_ANO_VIGENTE={alvo} configurado, mas nenhum curso desse ano existe."
        )
    return cursos[-1]  # maior ano encontrado — autodetecção


# ─── Núcleo: um curso "Simulados" inteiro ─────────────────────────────────


async def _sincronizar_curso_simulados(
    *,
    cliente: Client,
    canvas: ClienteCanvas,
    curso: dict[str, Any],
    ano: int,
    graded_since: str | None,
    resumo: ResumoSincronizacao,
) -> dict[str, str]:
    """Sincroniza turma/aluno/matrícula/ciclo/simulado/nota de um curso.

    Devolve {canvas_user_id: aluno_id} — o backfill usa pra buscar e-mails.
    """
    course_id = str(curso["id"])
    # canvas_course_id: é aqui que o agendamento (P1) descobre em que curso
    # criar Assignments — o sync é quem mantém o vínculo atualizado.
    ano_letivo_id = upsert_ano_letivo(cliente, ano=ano, canvas_course_id=course_id)

    # ── (1) Sections → sede/turma ──
    sections = await canvas.listar_sections(course_id)
    turma_por_section_id: dict[str, str] = {}
    for section in sections:
        nome_section = (section.get("name") or "").strip()
        parsed = parsear_section(nome_section)
        if parsed.serie is None and parsed.sede_codigo != "ONLINE":
            # Sections fora do padrão ("2022", "AFA", nome de curso colado...)
            # não geram turma — matrículas nelas ficam sem matricula_turma.
            resumo.avisos.append(f"Section '{nome_section}' fora do padrão — turma não criada.")
            continue
        sede_id = upsert_sede(cliente, codigo=parsed.sede_codigo, modalidade=parsed.modalidade)
        turma_id = upsert_turma(
            cliente,
            sede_id=sede_id,
            ano_letivo_id=ano_letivo_id,
            serie=parsed.serie or 0,
            trilha=parsed.trilha or "ONLINE",
            section_original=nome_section,
        )
        turma_por_section_id[str(section["id"])] = turma_id
    resumo.turmas_processadas += len(turma_por_section_id)

    # ── (2) Enrollments → aluno + matricula_turma ──
    enrollments = await canvas.listar_matriculas_de_alunos(course_id)

    # Um aluno aparece uma vez POR SECTION — dedup por matrícula, senão o
    # upsert em lote falha ("ON CONFLICT cannot affect row a second time").
    # Só entram alunos de sections reconhecidas: as sections-lixo ("2022",
    # "AFA", nomes de curso) carregam alunos arquivados de anos anteriores.
    aluno_por_matricula: dict[str, dict[str, Any]] = {}
    matricula_por_canvas_user: dict[str, str] = {}
    for enrollment in enrollments:
        if str(enrollment.get("course_section_id")) not in turma_por_section_id:
            continue
        aluno = mapeador.mapear_aluno(enrollment.get("user") or {})
        if aluno is None:
            continue
        aluno_por_matricula[aluno["matricula"]] = aluno
        matricula_por_canvas_user[aluno["canvas_user_id"]] = aluno["matricula"]

    matricula_para_id = upsert_alunos_em_lote(
        cliente, alunos=list(aluno_por_matricula.values())
    )
    resumo.alunos_processados += len(matricula_para_id)

    aluno_por_canvas_user: dict[str, str] = {
        canvas_user: matricula_para_id[matricula]
        for canvas_user, matricula in matricula_por_canvas_user.items()
        if matricula in matricula_para_id
    }

    # Dedup pela chave de conflito (aluno, turma, ativo_desde) — dois
    # enrollments do mesmo aluno na mesma section (active + completed) colidem.
    matricula_por_chave: dict[tuple[str, str, str], dict[str, Any]] = {}
    for enrollment in enrollments:
        canvas_user = str((enrollment.get("user") or {}).get("id", ""))
        aluno_id = aluno_por_canvas_user.get(canvas_user)
        turma_id = turma_por_section_id.get(str(enrollment.get("course_section_id")))
        if aluno_id and turma_id:
            payload = mapeador.mapear_matricula(enrollment, aluno_id=aluno_id, turma_id=turma_id)
            matricula_por_chave[(aluno_id, turma_id, payload["ativo_desde"])] = payload
    upsert_matriculas_em_lote(cliente, matriculas=list(matricula_por_chave.values()))

    # ── (3) Assignment Groups → ciclo (só ITA/IME) ──
    grupos = await canvas.listar_grupos_de_avaliacao(course_id)
    ciclo_por_group_id: dict[str, str] = {}
    ordem_por_group_id: dict[str, int] = {}
    for grupo in grupos:
        parsed_grupo = mapeador.parsear_grupo_ciclo(grupo.get("name") or "")
        if parsed_grupo is None:
            continue  # SAS/ENEM/Imported Assignments — descartado por definição
        ordem, vestibular = parsed_grupo
        ciclo_id = upsert_ciclo(
            cliente,
            ano_letivo_id=ano_letivo_id,
            ordem=ordem,
            nome=f"Ciclo {ordem} · {vestibular} · {ano}",
            vestibular_alvo=vestibular,
            canvas_assignment_group_id=str(grupo["id"]),
        )
        group_id = str(grupo["id"])
        ciclo_por_group_id[group_id] = ciclo_id
        ordem_por_group_id[group_id] = ordem
    resumo.ciclos_processados += len(ciclo_por_group_id)

    # ── (4) Assignments → simulado (fase inferida por agrupamento Pn) ──
    assignments = await canvas.listar_assignments(course_id)

    # Regra P1: campo originado no SAS nunca é sobrescrito pelo sync.
    # Simulados origem='sas' são casados por external_id ANTES da gramática
    # de nome (renomear à mão no Canvas não os derruba do SAS) e seguem por
    # um lote reduzido — só os campos que continuam sendo do Canvas.
    ids_do_curso = [str(a["id"]) for a in assignments]
    external_ids_sas: set[str] = set()
    datas_sas: dict[str, list[date]] = {}   # ciclo_id → datas (p/ período)
    hoje = date.today()
    for inicio in range(0, len(ids_do_curso), 100):
        resp_sas = (
            cliente.table("simulado")
            .select("external_id, ciclo_id, data_aplicacao")
            .eq("origem", "sas")
            .in_("external_id", ids_do_curso[inicio : inicio + 100])
            .execute()
        )
        for linha in resp_sas.data or []:
            external_ids_sas.add(str(linha["external_id"]))
            # A data do simulado SAS conta pro período do ciclo — mas só
            # depois de aplicada (agendamento futuro não estica periodo_fim).
            d = date.fromisoformat(str(linha["data_aplicacao"]))
            if d <= hoje:
                datas_sas.setdefault(linha["ciclo_id"], []).append(d)

    cache_materia: dict[str, str | None] = {}
    colunas_fase: list[ColunaSimulado] = []
    contexto_por_external_id: dict[str, dict[str, Any]] = {}
    simulados_payload_sas: list[dict[str, Any]] = []

    for assignment in assignments:
        if str(assignment["id"]) in external_ids_sas:
            # Lote reduzido: quiz_id/unlock/lock são produzidos pelo Canvas;
            # identidade (nome, rótulo, data, escala, tipo, ciclo, matéria)
            # é do SAS e fica intocada.
            simulados_payload_sas.append(
                {
                    "external_id": str(assignment["id"]),
                    "quiz_id": (
                        str(assignment["quiz_id"]) if assignment.get("quiz_id") else None
                    ),
                    "unlock_at": assignment.get("unlock_at"),
                    "lock_at": assignment.get("lock_at"),
                }
            )
            continue
        group_id = str(assignment.get("assignment_group_id"))
        ciclo_id = ciclo_por_group_id.get(group_id)
        if ciclo_id is None or not assignment.get("published"):
            continue
        info = mapeador.parsear_nome_assignment(assignment.get("name") or "")
        if info is None or info["data_aplicacao"] is None:
            resumo.avisos.append(
                f"Assignment '{assignment.get('name')}' fora da gramática — ignorado."
            )
            continue

        codigo = info["materia_codigo"]
        if codigo and codigo not in cache_materia:
            cache_materia[codigo] = buscar_materia_por_codigo(cliente, codigo)
        materia_id = cache_materia.get(codigo) if codigo else None

        external_id = str(assignment["id"])
        # ColunaSimulado é reaproveitada só pelo agrupamento de fase; a ordem do
        # ciclo vem do Assignment Group (fonte da verdade), não do nome.
        colunas_fase.append(
            ColunaSimulado(
                indice=0,
                nome_original=assignment["name"],
                rotulo_curto=info["rotulo_curto"],
                materia_codigo=codigo,
                data_aplicacao=info["data_aplicacao"],
                external_id=external_id,
                ciclo_ordem=ordem_por_group_id[group_id],
            )
        )
        contexto_por_external_id[external_id] = {
            "assignment": assignment,
            "ciclo_id": ciclo_id,
            "materia_id": materia_id,
            "data_aplicacao": info["data_aplicacao"],
        }

    inferir_fase_simulados(colunas_fase)

    simulados_payload: list[dict[str, Any]] = []
    datas_por_ciclo: dict[str, list[date]] = {}
    for col in colunas_fase:
        ctx = contexto_por_external_id[col.external_id]
        simulados_payload.append(
            mapeador.mapear_simulado(
                ctx["assignment"],
                ciclo_id=ctx["ciclo_id"],
                materia_id=ctx["materia_id"],
                rotulo_curto=col.rotulo_curto,
                data_aplicacao=ctx["data_aplicacao"],
                tipo=col.fase,
            )
        )
        datas_por_ciclo.setdefault(ctx["ciclo_id"], []).append(ctx["data_aplicacao"])

    external_para_simulado_id = upsert_simulados_em_lote(cliente, simulados=simulados_payload)

    # Lote reduzido dos origem='sas' — chamada SEPARADA de propósito: o upsert
    # em massa do PostgREST usa a união das chaves de todas as linhas do
    # array, e misturar payload completo com reduzido zeraria os campos
    # ausentes das linhas reduzidas (nome, nota_maxima, ...).
    external_para_simulado_id.update(
        upsert_simulados_em_lote(cliente, simulados=simulados_payload_sas)
    )
    resumo.simulados_processados += len(external_para_simulado_id)

    for ciclo_id, datas in datas_sas.items():
        datas_por_ciclo.setdefault(ciclo_id, []).extend(datas)
    for ciclo_id, datas in datas_por_ciclo.items():
        atualizar_periodo_ciclo(
            cliente, ciclo_id=ciclo_id, periodo_inicio=min(datas), periodo_fim=max(datas)
        )

    # ── (5) Submissions → nota (dedup pela PK aluno+simulado) ──
    submissions = await canvas.listar_submissions(course_id, graded_since=graded_since)
    nota_por_chave: dict[tuple[str, str], dict[str, Any]] = {}
    for submission in submissions:
        simulado_id = external_para_simulado_id.get(str(submission.get("assignment_id")))
        aluno_id = aluno_por_canvas_user.get(str(submission.get("user_id")))
        if simulado_id and aluno_id:
            nota_por_chave[(aluno_id, simulado_id)] = mapeador.mapear_nota(
                submission, aluno_id=aluno_id, simulado_id=simulado_id
            )
    resumo.notas_gravadas += upsert_notas_em_lote(cliente, notas=list(nota_por_chave.values()))

    # Simulados/alunos tocados nesta rodada → recompute-alvo em sincronizar_ano_atual.
    resumo.simulados_tocados.update(simulado_id for (_, simulado_id) in nota_por_chave)
    resumo.alunos_tocados.update(aluno_id for (aluno_id, _) in nota_por_chave)

    # ── (6) Questões dos quizzes (gated — Quiz Statistics é 1 chamada/quiz) ──
    simulado_ids_com_notas_novas = {simulado_id for (_, simulado_id) in nota_por_chave}
    await _sincronizar_questoes_gated(
        cliente=cliente,
        canvas=canvas,
        course_id=course_id,
        simulado_ids_do_curso=set(external_para_simulado_id.values()),
        simulado_ids_com_notas_novas=simulado_ids_com_notas_novas,
        aluno_por_canvas_user=aluno_por_canvas_user,
        resumo=resumo,
    )

    # ── (7) Arquivo (PDF) da prova — gated, casado por nome contra Course Files ──
    await _sincronizar_arquivos_gated(
        cliente=cliente,
        canvas=canvas,
        course_id=course_id,
        simulado_ids_do_curso=set(external_para_simulado_id.values()),
        resumo=resumo,
    )

    resumo.cursos_processados += 1
    return aluno_por_canvas_user


# ─── Questões dos quizzes (Fase 2) ────────────────────────────────────────

# Além dos quizzes com notas novas na rodada, o incremental vai puxando o
# backlog de quizzes nunca sincronizados — poucos por rodada para caber no
# ciclo de 5 min.
MAX_QUIZZES_PENDENTES_POR_RODADA = 3


async def _sincronizar_questoes_gated(
    *,
    cliente: Client,
    canvas: ClienteCanvas,
    course_id: str,
    simulado_ids_do_curso: set[str],
    simulado_ids_com_notas_novas: set[str],
    aluno_por_canvas_user: dict[str, str],
    resumo: ResumoSincronizacao,
) -> None:
    """Sincroniza questões só de quem precisa: (a) quizzes cujas notas mudaram
    nesta rodada; (b) até MAX_QUIZZES_PENDENTES_POR_RODADA quizzes já aplicados
    e nunca sincronizados (backlog)."""
    if not simulado_ids_do_curso:
        return

    ids = list(simulado_ids_do_curso)
    com_quiz: list[dict[str, Any]] = []
    for inicio in range(0, len(ids), 100):
        resp = (
            cliente.table("simulado")
            .select("id, quiz_id, data_aplicacao, questoes_sincronizadas_em")
            .in_("id", ids[inicio : inicio + 100])
            .not_.is_("quiz_id", "null")
            .execute()
        )
        com_quiz.extend(resp.data or [])

    hoje = date.today().isoformat()
    # Backlog do mais recente para o mais antigo: se um quiz antigo falhar
    # permanentemente (statistics indisponível), ele afunda para o fim da
    # fila em vez de ocupar um slot toda rodada — o resgate é o script
    # canvas_backfill_questoes.py.
    com_quiz.sort(key=lambda s: s.get("data_aplicacao") or "", reverse=True)
    alvo: list[dict[str, Any]] = []
    pendentes_usados = 0
    for sim in com_quiz:
        if sim["id"] in simulado_ids_com_notas_novas:
            alvo.append(sim)
        elif (
            sim.get("questoes_sincronizadas_em") is None
            and sim.get("data_aplicacao") is not None
            and sim["data_aplicacao"] <= hoje
            and pendentes_usados < MAX_QUIZZES_PENDENTES_POR_RODADA
        ):
            alvo.append(sim)
            pendentes_usados += 1

    for sim in alvo:
        try:
            resultado = await sincronizar_questoes_do_quiz(
                cliente,
                canvas,
                course_id=course_id,
                simulado_id=sim["id"],
                quiz_id=str(sim["quiz_id"]),
                aluno_por_canvas_user=aluno_por_canvas_user,
            )
        except Exception as exc:
            resumo.avisos.append(f"Questões do quiz {sim['quiz_id']} falharam: {exc}")
            continue
        resumo.quizzes_sincronizados += 1
        resumo.respostas_questao_gravadas += resultado["respostas"]
        if resultado["questoes"] and not resultado["tem_user_ids"]:
            resumo.avisos.append(
                f"Quiz {sim['quiz_id']}: statistics sem user_ids por alternativa — "
                "respostas por aluno não sincronizadas (avaliar plano B: Quiz Submissions)."
            )


# ─── Arquivo (PDF) da prova (Fase 3) ──────────────────────────────────────

# PDFs são bem maiores que Quiz Statistics (download + upload pro Storage) —
# poucos por rodada pra caber no ciclo de 5 min. O backfill dedicado
# (scripts/canvas_backfill_arquivos.py) zera o backlog sem esse limite.
MAX_ARQUIVOS_PENDENTES_POR_RODADA = 5


async def _sincronizar_arquivos_gated(
    *,
    cliente: Client,
    canvas: ClienteCanvas,
    course_id: str,
    simulado_ids_do_curso: set[str],
    resumo: ResumoSincronizacao,
) -> None:
    """Sincroniza o arquivo (PDF) só de simulados já aplicados e sem arquivo
    ainda, até MAX_ARQUIVOS_PENDENTES_POR_RODADA arquivos por rodada."""
    if not simulado_ids_do_curso:
        return

    hoje = date.today().isoformat()
    ids = list(simulado_ids_do_curso)
    pendentes: list[dict[str, Any]] = []
    for inicio in range(0, len(ids), 100):
        resp = (
            cliente.table("simulado")
            .select("id, rotulo_curto, data_aplicacao, ciclo(ordem), materia(codigo)")
            .in_("id", ids[inicio : inicio + 100])
            .is_("arquivo_storage_path", "null")
            .not_.is_("rotulo_curto", "null")
            .not_.is_("materia_id", "null")
            .lte("data_aplicacao", hoje)
            .execute()
        )
        pendentes.extend(resp.data or [])
    if not pendentes:
        return

    simulados_pendentes = [
        {
            "id": p["id"],
            "ciclo_ordem": (p.get("ciclo") or {}).get("ordem"),
            "rotulo_curto": p["rotulo_curto"],
            "materia_codigo": (p.get("materia") or {}).get("codigo"),
        }
        for p in pendentes
    ]
    simulados_pendentes = [
        p for p in simulados_pendentes if p["ciclo_ordem"] is not None and p["materia_codigo"]
    ]
    if not simulados_pendentes:
        return

    resultado = await sincronizar_arquivos_do_curso(
        cliente,
        canvas,
        course_id=course_id,
        simulados_pendentes=simulados_pendentes,
        limite_arquivos=MAX_ARQUIVOS_PENDENTES_POR_RODADA,
    )
    resumo.arquivos_sincronizados += resultado["arquivos_baixados"]
    resumo.avisos.extend(resultado["avisos"])


# ─── E-mail dos alunos no sync incremental ────────────────────────────────

# Fallback por Communication Channels é 1 chamada POR aluno — limitado por
# rodada para não estourar o ciclo de 5 min. Alunos já tentados são marcados
# em aluno.email_verificado_em e não são re-tentados.
MAX_CANAIS_POR_RODADA = 15


async def _preencher_emails_incremental(
    *,
    cliente: Client,
    canvas: ClienteCanvas,
    course_id: str,
    resumo: ResumoSincronizacao,
) -> None:
    """Preenche aluno.email onde estiver NULL (validação do primeiro acesso).

    Passo 1: /courses/{id}/users?include[]=email — uma chamada paginada cobre
    todos os alunos do curso. Passo 2 (fallback): Communication Channels para
    quem continuar sem e-mail, até MAX_CANAIS_POR_RODADA por rodada.
    Nunca sobrescreve e-mail já preenchido.
    """
    resp = (
        cliente.table("aluno")
        .select("id, canvas_user_id, email_verificado_em")
        .is_("email", "null")
        .eq("ativo", True)
        .not_.is_("canvas_user_id", "null")
        .execute()
    )
    pendentes = resp.data or []
    if not pendentes:
        return

    try:
        usuarios = await canvas.listar_usuarios_do_curso(course_id)
    except Exception as exc:
        resumo.avisos.append(f"Falha ao listar usuários do curso p/ e-mail: {exc}")
        usuarios = []
    email_por_canvas_user = {
        str(u["id"]): u.get("email") for u in usuarios if u.get("email")
    }

    ainda_sem_email: list[dict[str, Any]] = []
    for aluno in pendentes:
        email = email_por_canvas_user.get(str(aluno["canvas_user_id"]))
        if email:
            cliente.table("aluno").update({"email": email}).eq("id", aluno["id"]).execute()
            resumo.emails_preenchidos += 1
        else:
            ainda_sem_email.append(aluno)

    nao_tentados = [a for a in ainda_sem_email if not a.get("email_verificado_em")]
    for aluno in nao_tentados[:MAX_CANAIS_POR_RODADA]:
        patch: dict[str, Any] = {
            "email_verificado_em": datetime.now(timezone.utc).isoformat()
        }
        try:
            canais = await canvas.listar_canais_de_comunicacao(str(aluno["canvas_user_id"]))
            email = mapeador.extrair_email(canais)
            if email:
                patch["email"] = email
                resumo.emails_preenchidos += 1
        except Exception:
            pass  # marca a tentativa mesmo assim — sem loop infinito de retry
        cliente.table("aluno").update(patch).eq("id", aluno["id"]).execute()


# ─── Recalcular métricas/classificação/alertas (mesma sequência do pipeline) ──


def _recalcular_stats(cliente: Client) -> None:
    from ..stats import alertas as _alertas, classificacao as _classif, metricas as _metricas

    _metricas.recalcular_tudo(cliente)
    _classif.recalcular_tudo(cliente)
    _alertas.avaliar_tudo(cliente)


# ─── Rotinas públicas ─────────────────────────────────────────────────────


async def sincronizar_ano_atual(
    *,
    cliente: Client,
    canvas: ClienteCanvas,
    account_id: str,
    override_ano: str | None,
    lookback_minutos: int,
) -> ResumoSincronizacao:
    """Sync incremental (POST /canvas-sync/run, a cada 5 min)."""
    resumo = ResumoSincronizacao()
    ano, curso = await _curso_do_ano_vigente(
        canvas, account_id=account_id, override_ano=override_ano
    )
    graded_since = (
        datetime.now(timezone.utc) - timedelta(minutes=lookback_minutos)
    ).isoformat()

    # Simulados agendados no SAS que ainda não existem no Canvas (POST falhou
    # na hora do agendamento) — tenta de novo ANTES do sync de leitura, assim
    # um que sincronize agora já entra no casamento por external_id da rodada.
    from .agendamento import reprocessar_canvas_pendentes

    pendencias = await reprocessar_canvas_pendentes(cliente, canvas)
    if pendencias["sincronizados"] or pendencias["falharam"]:
        resumo.avisos.append(
            f"agendamentos reprocessados: {pendencias['sincronizados']} sincronizados, "
            f"{pendencias['falharam']} ainda em falha"
        )

    await _sincronizar_curso_simulados(
        cliente=cliente, canvas=canvas, curso=curso, ano=ano,
        graded_since=graded_since, resumo=resumo,
    )
    await _preencher_emails_incremental(
        cliente=cliente, canvas=canvas, course_id=str(curso["id"]), resumo=resumo,
    )
    # Recompute-ALVO: recalcula só os simulados/alunos tocados nesta rodada,
    # em vez do cache multi-ano inteiro (que era ~3300 round-trips → 60-100 min
    # na instância free do Render). Sem notas novas, ambos os conjuntos são
    # vazios e nada roda. Alertas NÃO rodam aqui — o job horário
    # POST /alertas/verificar os avalia, e o reconcile diário
    # POST /canvas-sync/reconciliar recomputa tudo pra curar drift de turma.
    from ..stats import classificacao as _classif, metricas as _metricas

    # ⚠️ **A ORDEM AQUI É O PONTO**, duas vezes.
    #
    # 1. Depois das QUESTÕES: a evidência mora em `questao_resposta_aluno`, que
    #    a etapa (6) de cada curso acabou de popular. Avaliar antes dela
    #    classificaria todo mundo como computável e sumiria com o efeito **sem
    #    erro nenhum** — nenhuma exceção, nenhum log, só a estatística de volta
    #    ao que era. É a falha silenciosa mais provável do sprint.
    # 2. Antes do RECOMPUTE: métrica e classificação leem `computavel`. Rodar
    #    depois delas deixaria o cache um ciclo atrás da conclusão, e a tela
    #    contradiria a régua — foi o que aconteceu com a 0037 (docs/31).
    if resumo.simulados_tocados:
        computavel.avaliar_computavel(cliente, simulado_ids=sorted(resumo.simulados_tocados))
        _metricas.recalcular_simulados(cliente, resumo.simulados_tocados)
    if resumo.alunos_tocados:
        _classif.recalcular_alunos(cliente, resumo.alunos_tocados)
    return resumo


async def sincronizar_historico_completo(
    *,
    cliente: Client,
    canvas: ClienteCanvas,
    account_id: str,
) -> ResumoSincronizacao:
    """Backfill único: todos os anos encontrados + e-mail dos alunos."""
    resumo = ResumoSincronizacao()
    cursos = await _descobrir_cursos_simulados(canvas, account_id)
    if not cursos:
        raise RuntimeError("Nenhum curso '{ano} 3o ITA/IME Simulados' encontrado na conta.")

    aluno_por_canvas_user: dict[str, str] = {}
    for ano, curso in cursos:
        mapa = await _sincronizar_curso_simulados(
            cliente=cliente, canvas=canvas, curso=curso, ano=ano,
            graded_since=None, resumo=resumo,
        )
        aluno_por_canvas_user.update(mapa)

    # E-mail: uma chamada por aluno (Communication Channels) — só no backfill.
    for canvas_user_id, aluno_id in aluno_por_canvas_user.items():
        try:
            canais = await canvas.listar_canais_de_comunicacao(canvas_user_id)
        except Exception:
            continue  # aluno sem canais acessíveis não bloqueia o backfill
        email = mapeador.extrair_email(canais)
        if email:
            cliente.table("aluno").update({"email": email}).eq("id", aluno_id).execute()
            resumo.emails_preenchidos += 1

    _recalcular_stats(cliente)
    return resumo
