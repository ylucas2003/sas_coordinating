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
from . import mapeador
from .cliente import ClienteCanvas


@dataclass
class ResumoSincronizacao:
    cursos_processados: int = 0
    alunos_processados: int = 0
    turmas_processadas: int = 0
    ciclos_processados: int = 0
    simulados_processados: int = 0
    notas_gravadas: int = 0
    emails_preenchidos: int = 0
    avisos: list[str] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    ano_letivo_id = upsert_ano_letivo(cliente, ano=ano)

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
    aluno_por_matricula: dict[str, dict[str, Any]] = {}
    matricula_por_canvas_user: dict[str, str] = {}
    for enrollment in enrollments:
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
        )
        group_id = str(grupo["id"])
        ciclo_por_group_id[group_id] = ciclo_id
        ordem_por_group_id[group_id] = ordem
    resumo.ciclos_processados += len(ciclo_por_group_id)

    # ── (4) Assignments → simulado (fase inferida por agrupamento Pn) ──
    assignments = await canvas.listar_assignments(course_id)
    cache_materia: dict[str, str | None] = {}
    colunas_fase: list[ColunaSimulado] = []
    contexto_por_external_id: dict[str, dict[str, Any]] = {}

    for assignment in assignments:
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
    resumo.simulados_processados += len(external_para_simulado_id)

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

    resumo.cursos_processados += 1
    return aluno_por_canvas_user


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
    await _sincronizar_curso_simulados(
        cliente=cliente, canvas=canvas, curso=curso, ano=ano,
        graded_since=graded_since, resumo=resumo,
    )
    _recalcular_stats(cliente)
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
