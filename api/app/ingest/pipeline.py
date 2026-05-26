"""Orquestra o pipeline completo de ingestão de uma planilha.

Fluxo:
  1. Parseia o arquivo bruto (CSV ou XLSX) → PlanilhaCrua.
  2. Interpreta o cabeçalho → lista de Coluna (identificação / simulado / ignorada).
  3. Garante existência de ano_letivo e materias.
  4. Para cada coluna de simulado: garante ciclo + simulado.
  5. Para cada linha de aluno: garante sede + turma + aluno + matricula_turma.
  6. Faz upsert de todas as notas em lote.
  7. Atualiza periodo_inicio/fim dos ciclos afetados.
  8. Registra resumo e finaliza o upload com status='sucesso'.

Idempotência: rodar a função duas vezes sobre o mesmo arquivo deve produzir
o mesmo estado final no banco (sem duplicação, sem alertas falsos).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from supabase import Client

log = logging.getLogger("sas.ingest")
log.setLevel(logging.INFO)
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(name)s · %(message)s", "%H:%M:%S"))
    log.addHandler(_h)


def _etapa(t0: float, mensagem: str) -> None:
    """Print uniformizado de etapa do pipeline com tempo decorrido."""
    log.info(f"[+{time.time() - t0:5.2f}s] {mensagem}")


# Etapas declaradas. O frontend consome estes prefixos pra avançar a barra.
# 1-7: ingestão; 8-10: stats engine (métricas, classificação, alertas).
TOTAL_ETAPAS = 10


def _emitir_etapa(
    cliente: Client,
    *,
    upload_id: str,
    numero: int,
    descricao: str,
    t0: float,
) -> None:
    """Grava um evento ETAPA no banco — o frontend usa pra avançar a barra."""
    mensagem = f"ETAPA {numero}/{TOTAL_ETAPAS}: {descricao}"
    _etapa(t0, mensagem)
    registrar_evento(cliente, upload_id=upload_id, nivel="info", mensagem=mensagem)

from .header import (
    Coluna,
    ColunaIdentificacao,
    ColunaSimulado,
    detectar_vestibulares_por_ciclo,
    inferir_fase_simulados,
    parsear_coluna,
    parsear_section,
)
from .reader import PlanilhaCrua, ler_csv, ler_xlsx, parsear_decimal_br
from .upsert import (
    atualizar_periodo_ciclo,
    buscar_materia_por_codigo,
    criar_upload,
    finalizar_upload,
    registrar_evento,
    upsert_alunos_em_lote,
    upsert_ano_letivo,
    upsert_ciclo,
    upsert_matriculas_em_lote,
    upsert_notas_em_lote,
    upsert_sede,
    upsert_simulados_em_lote,
    upsert_turma,
)


# ─── Tipos de retorno ─────────────────────────────────────────────────────


@dataclass
class ResumoIngestao:
    """Contagens reportadas no final do upload — alimenta o frontend e o `upload.resumo`."""
    alunos_processados: int = 0
    sedes_processadas: int = 0
    turmas_processadas: int = 0
    ciclos_processados: int = 0
    simulados_processados: int = 0
    notas_gravadas: int = 0
    notas_reclassificadas_como_ausencia: int = 0
    colunas_ignoradas: int = 0
    avisos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alunos_processados": self.alunos_processados,
            "sedes_processadas": self.sedes_processadas,
            "turmas_processadas": self.turmas_processadas,
            "ciclos_processados": self.ciclos_processados,
            "simulados_processados": self.simulados_processados,
            "notas_gravadas": self.notas_gravadas,
            "notas_reclassificadas_como_ausencia": self.notas_reclassificadas_como_ausencia,
            "colunas_ignoradas": self.colunas_ignoradas,
            "avisos": self.avisos,
        }


# ─── Função pública ───────────────────────────────────────────────────────


def processar_planilha(
    *,
    cliente: Client,
    arquivo_origem: str,
    conteudo: bytes,
    caminho_storage: str | None,
    autor: str | None = None,
    upload_id_existente: str | None = None,
) -> tuple[str, ResumoIngestao]:
    """Processa uma planilha de ponta a ponta.

    Retorna o `upload_id` e o resumo. Em caso de erro fatal, levanta exceção
    depois de registrar o estado de erro no banco.

    Se `upload_id_existente` for passado, reusa essa linha em vez de criar
    uma nova — usado pela rota /uploads que cria o registro antes de
    delegar pro BackgroundTask, pra poder devolver o ID na mesma resposta.
    """
    t0 = time.time()
    log.info("=" * 72)
    log.info(f"Iniciando ingestão de '{arquivo_origem}' ({len(conteudo) / 1024:.1f} KB)")
    if upload_id_existente:
        upload_id = upload_id_existente
    else:
        upload_id = criar_upload(
            cliente,
            arquivo_origem=arquivo_origem,
            caminho_storage=caminho_storage,
            autor=autor,
        )
    _etapa(t0, f"upload registrado: {upload_id}")

    try:
        _emitir_etapa(cliente, upload_id=upload_id, numero=1, descricao="lendo arquivo", t0=t0)
        planilha = _ler_arquivo(arquivo_origem, conteudo)
        _etapa(t0, f"parsing concluído: {len(planilha.linhas)} linhas de aluno, {len(planilha.cabecalho)} colunas")
        resumo = _processar(cliente, upload_id, planilha, t0)
        finalizar_upload(
            cliente,
            upload_id=upload_id,
            status="sucesso",
            resumo=resumo.to_dict(),
            linhas_total=len(planilha.linhas),
            linhas_aceitas=resumo.alunos_processados,
            linhas_rejeitadas=len(planilha.linhas) - resumo.alunos_processados,
        )
        _etapa(t0, f"FINALIZADO ok · {resumo.alunos_processados} alunos, {resumo.simulados_processados} simulados, {resumo.notas_gravadas} notas")
        return upload_id, resumo

    except Exception as exc:
        _etapa(t0, f"FALHOU: {exc}")
        finalizar_upload(
            cliente,
            upload_id=upload_id,
            status="erro",
            erro_mensagem=str(exc),
        )
        registrar_evento(
            cliente,
            upload_id=upload_id,
            nivel="erro",
            mensagem=f"Falha na ingestão: {exc}",
        )
        raise


# ─── Helpers internos ─────────────────────────────────────────────────────


def _ler_arquivo(arquivo_origem: str, conteudo: bytes) -> PlanilhaCrua:
    nome_minusculo = arquivo_origem.lower()
    if nome_minusculo.endswith(".csv"):
        return ler_csv(conteudo)
    if nome_minusculo.endswith(".xlsx") or nome_minusculo.endswith(".xlsm"):
        return ler_xlsx(conteudo)
    raise ValueError(f"Extensão não suportada para '{arquivo_origem}'. Use .csv ou .xlsx.")


def _processar(
    cliente: Client,
    upload_id: str,
    planilha: PlanilhaCrua,
    t0: float,
) -> ResumoIngestao:
    resumo = ResumoIngestao()

    # ── (1a) Detecta vestibular-alvo de cada ciclo numérico ──
    vestibulares_por_ciclo = detectar_vestibulares_por_ciclo(planilha.cabecalho)
    _etapa(
        t0,
        f"vestibulares detectados: " +
        (", ".join(f"ciclo {k}={v}" for k, v in sorted(vestibulares_por_ciclo.items())) or "nenhum"),
    )

    # ── (1b) Interpreta colunas individuais ──
    ano_fallback = _deduzir_ano_letivo(planilha)
    colunas = [
        parsear_coluna(i, nome, ano_fallback=ano_fallback)
        for i, nome in enumerate(planilha.cabecalho)
    ]

    # ── (1c) Infere fase_1/fase_2 agrupando por (ciclo, Pn) ──
    inferir_fase_simulados(colunas)

    indices_identificacao = _mapear_identificacao(colunas)
    colunas_simulado = [c for c in colunas if isinstance(c, ColunaSimulado)]
    resumo.colunas_ignoradas = sum(1 for c in colunas if c.tipo == "ignorada")

    if "sis_user_id" not in indices_identificacao:
        raise ValueError("Planilha sem coluna 'SIS User ID'. Não é possível identificar alunos.")
    if "section" not in indices_identificacao:
        raise ValueError("Planilha sem coluna 'Section'. Não é possível identificar turmas.")

    # ── (1d) Pré-validação: descarta simulados sem nenhum presente e alunos sem nota ──
    # Regras confirmadas pelo usuário em 2026-05-25:
    #   - simulado em que NENHUM aluno tem pontuação > 0 não é persistido
    #   - aluno cujas pontuações são todas NULL/0 não é persistido
    # Aplicado ANTES dos upserts pra evitar gravar lixo no banco.
    pontos_possiveis = planilha.pontos_possiveis
    indice_sis = indices_identificacao["sis_user_id"]
    indice_section = indices_identificacao["section"]

    # Filtro extra: descarta colunas com Points Possible = 0 (provas de treino).
    colunas_com_nota_maxima_zero: list[ColunaSimulado] = []
    colunas_simulado_filtradas: list[ColunaSimulado] = []
    for col in colunas_simulado:
        nota_maxima = parsear_decimal_br(pontos_possiveis[col.indice]) or 0.0
        if nota_maxima == 0:
            colunas_com_nota_maxima_zero.append(col)
        else:
            colunas_simulado_filtradas.append(col)

    # Conta presenças por coluna usando só linhas com identificação válida.
    linhas_com_identificacao = [
        linha
        for linha in planilha.linhas
        if (linha[indice_sis] or "").strip()
        and (linha[indice_section] or "").strip()
    ]
    colunas_simulado_validas: list[ColunaSimulado] = []
    colunas_sem_presenca: list[ColunaSimulado] = []
    for col in colunas_simulado_filtradas:
        tem_presenca = any(
            (p := parsear_decimal_br(linha[col.indice])) is not None and p > 0
            for linha in linhas_com_identificacao
        )
        (colunas_simulado_validas if tem_presenca else colunas_sem_presenca).append(col)

    for col in colunas_com_nota_maxima_zero:
        registrar_evento(
            cliente,
            upload_id=upload_id,
            nivel="info",
            mensagem=f"Coluna '{col.nome_original}' descartada (Points Possible = 0 — prova de treino).",
            coluna_planilha=col.nome_original,
        )
    for col in colunas_sem_presenca:
        registrar_evento(
            cliente,
            upload_id=upload_id,
            nivel="info",
            mensagem=f"Coluna '{col.nome_original}' descartada (nenhum aluno com nota — simulado não aplicado).",
            coluna_planilha=col.nome_original,
        )
    resumo.colunas_ignoradas += len(colunas_com_nota_maxima_zero) + len(colunas_sem_presenca)

    # Reduz `colunas_simulado` ao conjunto válido daqui pra frente.
    colunas_simulado = colunas_simulado_validas

    _emitir_etapa(
        cliente,
        upload_id=upload_id,
        numero=2,
        descricao=(
            f"cabeçalho interpretado: {len(colunas_simulado)} simulados válidos "
            f"({len(colunas_sem_presenca)} sem presença, "
            f"{len(colunas_com_nota_maxima_zero)} c/ Points Possible=0, "
            f"{resumo.colunas_ignoradas - len(colunas_sem_presenca) - len(colunas_com_nota_maxima_zero)} ENEM/SAS/agregados)"
        ),
        t0=t0,
    )

    # ── (2) Garante ano letivo (deduzido das datas das colunas) ──
    if ano_fallback is None:
        raise ValueError("Não foi possível deduzir o ano letivo a partir das datas das colunas.")
    ano_letivo_id = upsert_ano_letivo(cliente, ano=ano_fallback)
    _etapa(t0, f"ano letivo: {ano_fallback}")

    # ── (3) Resolve matéria → materia_id (cache em memória) ──
    cache_materia: dict[str, str | None] = {}

    def resolver_materia(codigo: str | None) -> str | None:
        if codigo is None:
            return None
        if codigo not in cache_materia:
            cache_materia[codigo] = buscar_materia_por_codigo(cliente, codigo)
        return cache_materia[codigo]

    _emitir_etapa(cliente, upload_id=upload_id, numero=3, descricao="criando ciclos e simulados", t0=t0)

    # ── (4) Ciclos + simulados — upserts em lote ──
    # 1. Resolve ciclos únicos (poucos: ~12). Cada um vira uma chamada porque
    #    ciclo precisa de UNIQUE(ano_letivo, ordem) e queremos o id de volta.
    # 2. Resolve materias (cache em memória).
    # 3. Batcheia o upsert dos simulados (UMA chamada em vez de N).
    ciclos_por_ordem: dict[int, str] = {}
    simulados_por_coluna: dict[int, dict[str, Any]] = {}
    datas_por_ciclo: dict[str, list[date]] = defaultdict(list)
    descartados_por_ciclo: dict[int | None, int] = defaultdict(int)

    # Constrói payload de simulados (após filtrar e resolver ciclo+materia).
    simulados_payload: list[dict[str, Any]] = []
    info_por_external_id: dict[str, dict[str, Any]] = {}

    for col in colunas_simulado:
        if col.data_aplicacao is None:
            registrar_evento(
                cliente,
                upload_id=upload_id,
                nivel="aviso",
                mensagem=f"Coluna '{col.nome_original}' sem data válida — simulado ignorado.",
                coluna_planilha=col.nome_original,
            )
            continue

        # Resolve ciclo efetivo + vestibular_alvo (todo simulado agora tem ciclo numérico).
        vestibular_efetivo = vestibulares_por_ciclo.get(col.ciclo_ordem)
        if not vestibular_efetivo:
            descartados_por_ciclo[col.ciclo_ordem] += 1
            continue
        ciclo_ordem_efetiva = col.ciclo_ordem
        nome_ciclo = f"Ciclo {ciclo_ordem_efetiva} · {vestibular_efetivo} · {ano_fallback}"

        if ciclo_ordem_efetiva not in ciclos_por_ordem:
            ciclo_id = upsert_ciclo(
                cliente,
                ano_letivo_id=ano_letivo_id,
                ordem=ciclo_ordem_efetiva,
                nome=nome_ciclo,
                vestibular_alvo=vestibular_efetivo,
            )
            ciclos_por_ordem[ciclo_ordem_efetiva] = ciclo_id
            resumo.ciclos_processados += 1

        ciclo_id = ciclos_por_ordem[ciclo_ordem_efetiva]
        materia_id = resolver_materia(col.materia_codigo)

        # nota_maxima já foi filtrada (= 0 descartado na pré-validação).
        nota_maxima = parsear_decimal_br(pontos_possiveis[col.indice]) or 0.0

        simulados_payload.append({
            "external_id": col.external_id,
            "ciclo_id": ciclo_id,
            "materia_id": materia_id,
            "nome": col.nome_original,
            "rotulo_curto": col.rotulo_curto,
            "data_aplicacao": col.data_aplicacao.isoformat(),
            "nota_maxima": nota_maxima,
            "e_agregado": False,
            "tipo": col.fase,
        })
        info_por_external_id[col.external_id] = {
            "indice_coluna": col.indice,
            "ciclo_id": ciclo_id,
            "data_aplicacao": col.data_aplicacao,
            "nota_maxima": nota_maxima,
        }

    # Manda todos os simulados num lote (200 por vez).
    external_para_simulado_id = upsert_simulados_em_lote(cliente, simulados=simulados_payload)

    # Hidrata os mapas que o restante do pipeline usa.
    for external_id, simulado_id in external_para_simulado_id.items():
        info = info_por_external_id[external_id]
        simulados_por_coluna[info["indice_coluna"]] = {
            "simulado_id": simulado_id,
            "nota_maxima": info["nota_maxima"],
            "data_aplicacao": info["data_aplicacao"],
        }
        datas_por_ciclo[info["ciclo_id"]].append(info["data_aplicacao"])
    resumo.simulados_processados = len(external_para_simulado_id)

    # Log de ciclos descartados, se houver
    for ordem, qtd in sorted(descartados_por_ciclo.items()):
        registrar_evento(
            cliente,
            upload_id=upload_id,
            nivel="info",
            mensagem=(
                f"Ciclo {ordem} sem vestibular ITA/IME identificado — "
                f"{qtd} coluna(s) de simulado descartada(s)."
            ),
        )

    _emitir_etapa(
        cliente,
        upload_id=upload_id,
        numero=4,
        descricao=f"criando turmas e {len(planilha.linhas)} alunos",
        t0=t0,
    )

    # ── (5) Sedes/turmas (deduplicadas) + alunos/matrículas (em lote) ──
    #
    # Antes era 4 upserts por aluno × 818 alunos ≈ 3.300 round-trips HTTP.
    # Agora:
    #   - sedes: 1 upsert por sede única (~3)
    #   - turmas: 1 upsert por turma única (~12)
    #   - alunos: 1 lote (≤500 alunos por requisição) com matricula→id de volta
    #   - matriculas: 1 lote
    primeira_data_aplicacao = min(
        (col.data_aplicacao for col in colunas_simulado if col.data_aplicacao),
        default=date.today(),
    )

    # 5a — sections únicas → cache (sede_id, turma_id)
    sections_brutas: set[str] = {
        (linha[indices_identificacao["section"]] or "").strip()
        for linha in planilha.linhas
        if (linha[indices_identificacao["section"]] or "").strip()
    }
    sections_para_ids: dict[str, tuple[str, str]] = {}
    sedes_vistas: set[str] = set()
    turmas_vistas: set[str] = set()

    for section in sections_brutas:
        section_parsed = parsear_section(section)
        sede_id = upsert_sede(
            cliente,
            codigo=section_parsed.sede_codigo,
            modalidade=section_parsed.modalidade,
        )
        if sede_id not in sedes_vistas:
            resumo.sedes_processadas += 1
            sedes_vistas.add(sede_id)

        serie = section_parsed.serie or 0
        trilha = section_parsed.trilha or "INDEFINIDA"
        turma_id = upsert_turma(
            cliente,
            sede_id=sede_id,
            ano_letivo_id=ano_letivo_id,
            serie=serie,
            trilha=trilha,
            section_original=section,
        )
        if turma_id not in turmas_vistas:
            resumo.turmas_processadas += 1
            turmas_vistas.add(turma_id)
        sections_para_ids[section] = (sede_id, turma_id)

    _etapa(
        t0,
        f"sedes/turmas resolvidas: {len(sedes_vistas)} sedes, {len(turmas_vistas)} turmas",
    )

    # 5b — payload de alunos válidos
    # Filtro adicional (2026-05-25): aluno com TODAS as notas vazias ou 0
    # nas colunas válidas não é persistido.
    indices_simulado_validos = [c.indice for c in colunas_simulado]

    def aluno_tem_alguma_nota(linha: list[str | None]) -> bool:
        for i in indices_simulado_validos:
            p = parsear_decimal_br(linha[i])
            if p is not None and p > 0:
                return True
        return False

    alunos_payload: list[dict[str, Any]] = []
    linhas_validas: list[tuple[str, str, list[str | None]]] = []  # (matricula, turma_id, linha)
    alunos_descartados_sem_nota = 0

    for indice_linha, linha in enumerate(planilha.linhas):
        nome_aluno = (linha[indices_identificacao["nome"]] or "").strip()
        matricula = (linha[indices_identificacao["sis_user_id"]] or "").strip()
        section = (linha[indices_identificacao["section"]] or "").strip()

        if not matricula:
            registrar_evento(
                cliente,
                upload_id=upload_id,
                nivel="aviso",
                mensagem="Linha sem SIS User ID — descartada.",
                linha_planilha=indice_linha + 3,
            )
            continue
        if not section or section not in sections_para_ids:
            registrar_evento(
                cliente,
                upload_id=upload_id,
                nivel="aviso",
                mensagem=f"Aluno {matricula} sem Section válida — descartado.",
                linha_planilha=indice_linha + 3,
            )
            continue
        if not aluno_tem_alguma_nota(linha):
            alunos_descartados_sem_nota += 1
            continue

        _, turma_id = sections_para_ids[section]
        alunos_payload.append({
            "matricula": matricula,
            "nome": nome_aluno or matricula,
            "ativo": True,
        })
        linhas_validas.append((matricula, turma_id, linha))

    if alunos_descartados_sem_nota:
        registrar_evento(
            cliente,
            upload_id=upload_id,
            nivel="info",
            mensagem=f"{alunos_descartados_sem_nota} aluno(s) descartado(s) por não ter nenhuma nota válida.",
        )

    # 5c — upsert em lote dos alunos + recupera ids
    _etapa(t0, f"upsert em lote de {len(alunos_payload)} alunos…")
    matricula_para_id = upsert_alunos_em_lote(cliente, alunos=alunos_payload)
    resumo.alunos_processados = len(matricula_para_id)
    _etapa(t0, f"alunos persistidos: {resumo.alunos_processados}")

    # 5d — matrícula_turma em lote
    matriculas_payload: list[dict[str, Any]] = []
    for matricula, turma_id, _ in linhas_validas:
        aluno_id = matricula_para_id.get(matricula)
        if not aluno_id:
            continue
        matriculas_payload.append({
            "aluno_id": aluno_id,
            "turma_id": turma_id,
            "ativo_desde": primeira_data_aplicacao.isoformat(),
        })
    upsert_matriculas_em_lote(cliente, matriculas=matriculas_payload)
    _etapa(t0, f"matrículas-turma persistidas: {len(matriculas_payload)}")

    # 5e — coleta notas pra upsert em lote (próxima etapa).
    #
    # Regra "zero = provável abandono" (ver project_zeros_provaveis_ausencias):
    # zero numa prova isolada pode ser nota real (aluno desistiu daquela matéria),
    # mas se um aluno tirou 0 em 2+ provas do MESMO DIA, é muito mais provável
    # que ele faltou aquele dia inteiro — reclassificamos essas células como
    # `presente=false, pontuacao=null` pra não contaminar média/distribuição.
    notas_para_gravar: list[dict[str, Any]] = []
    n_reclassificadas = 0
    for matricula, _, linha in linhas_validas:
        aluno_id = matricula_para_id.get(matricula)
        if not aluno_id:
            continue

        # Passo 1: parseia células e agrupa zeros por data.
        notas_aluno: list[dict[str, Any]] = []
        zeros_por_data: dict[date, list[int]] = defaultdict(list)
        for indice_coluna, info in simulados_por_coluna.items():
            pontuacao = parsear_decimal_br(linha[indice_coluna])
            presente = pontuacao is not None
            idx_no_array = len(notas_aluno)
            notas_aluno.append({
                "aluno_id": aluno_id,
                "simulado_id": info["simulado_id"],
                "pontuacao": pontuacao,
                "presente": presente,
                "_data": info["data_aplicacao"],  # campo temporário, removido antes do upsert
            })
            if presente and pontuacao == 0:
                zeros_por_data[info["data_aplicacao"]].append(idx_no_array)

        # Passo 2: reclassifica zeros em dias com 2+ zeros.
        for data_aplicacao, indices in zeros_por_data.items():
            if len(indices) < 2:
                continue
            for idx in indices:
                notas_aluno[idx]["pontuacao"] = None
                notas_aluno[idx]["presente"] = False
                n_reclassificadas += 1

        # Passo 3: remove campo temporário e adiciona ao lote.
        for nota in notas_aluno:
            nota.pop("_data", None)
        notas_para_gravar.extend(notas_aluno)

    resumo.notas_reclassificadas_como_ausencia = n_reclassificadas
    if n_reclassificadas > 0:
        _etapa(t0, f"reclassificadas como ausência: {n_reclassificadas} notas zero (2+ no mesmo dia)")

    _emitir_etapa(
        cliente,
        upload_id=upload_id,
        numero=5,
        descricao=f"gravando {len(notas_para_gravar)} notas em lote",
        t0=t0,
    )

    # ── (6) Grava notas em lote ──
    resumo.notas_gravadas = upsert_notas_em_lote(cliente, notas=notas_para_gravar)

    _emitir_etapa(cliente, upload_id=upload_id, numero=6, descricao="atualizando períodos dos ciclos", t0=t0)

    # ── (7) Atualiza períodos dos ciclos ──
    for ciclo_id, datas in datas_por_ciclo.items():
        if datas:
            atualizar_periodo_ciclo(
                cliente,
                ciclo_id=ciclo_id,
                periodo_inicio=min(datas),
                periodo_fim=max(datas),
            )

    _emitir_etapa(cliente, upload_id=upload_id, numero=7, descricao="ingestão concluída", t0=t0)

    # ── (8-10) Stats engine: tudo é calculado e persistido em tabelas de cache,
    # pra que as telas só precisem fazer SELECT depois. Import lazy pra evitar
    # ciclos quando alguém importa o pipeline em outro contexto.
    from ..stats import alertas as _alertas, classificacao as _classif, metricas as _metricas

    _emitir_etapa(cliente, upload_id=upload_id, numero=8, descricao="recalculando métricas dos simulados", t0=t0)
    n_metricas = _metricas.recalcular_tudo(cliente)
    _etapa(t0, f"métricas: {n_metricas} simulados processados")

    _emitir_etapa(cliente, upload_id=upload_id, numero=9, descricao="classificando alunos", t0=t0)
    n_classif = _classif.recalcular_tudo(cliente)
    _etapa(t0, f"classificação: {n_classif} alunos classificados")

    _emitir_etapa(cliente, upload_id=upload_id, numero=10, descricao="avaliando alertas", t0=t0)
    n_alertas = _alertas.avaliar_tudo(cliente)
    _etapa(t0, f"alertas: {n_alertas} avaliados (dedup por hash)")

    return resumo


def _mapear_identificacao(colunas: list[Coluna]) -> dict[str, int]:
    """Indexa colunas de identificação pelo nome do campo (nome, sis_user_id, section, ...)."""
    mapa: dict[str, int] = {}
    for col in colunas:
        if isinstance(col, ColunaIdentificacao):
            mapa[col.campo] = col.indice
    return mapa


def _deduzir_ano_letivo(planilha: PlanilhaCrua) -> int | None:
    """Procura uma data dd/mm/aaaa em qualquer cabeçalho e usa o ano dela."""
    import re

    padrao = re.compile(r"(\d{2}/\d{2}/(\d{4}))")
    for nome in planilha.cabecalho:
        m = padrao.search(nome)
        if m:
            return int(m.group(2))
    return None
