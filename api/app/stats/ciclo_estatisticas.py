"""Agregação estatística por ciclo — versão "tudo numa página".

Diferente da versão anterior (uma chamada por fase), esta retorna **todo o
ciclo de uma vez**: F1, F2 e a análise conjunta (média ponderada do aluno
no ciclo inteiro). O front consome um único payload e renderiza a página
sem filtros de fase.

Estrutura do payload:
    {
      "ciclo": {...},
      "cicloAnterior": {...} | None,
      "resumo": { stats principais do ciclo todo, conjunta },
      "evolucaoTemporal": [{simuladoId, data, materia, media, fase, ...}],
      "conjunta": { stats + histograma do ciclo todo, F1+F2 agregados },
      "porMateria": [
        {
          "materia": {codigo, nome},
          "eliminatoria": false,
          "corte": 4.0,
          "fase1": { stats, histograma } | None,
          "fase2": { stats, histograma } | None,
          "deltaF1F2": { media, mediana, pctAprovados } | None
        },
        ...
      ]
    }

A comparação com o ciclo anterior fica no campo `anterior` dentro de cada
bloco de stats (conjunta + fase1/fase2 por matéria).

Sem cache em DB no MVP — recalcula a cada request. Os recortes do ciclo
têm poucos simulados × centenas de alunos, é barato.
"""

from __future__ import annotations

import logging
import statistics as st
from collections import defaultdict
from typing import Any

from supabase import Client

from .thresholds import NOTA_CORTE_FASE_2
from .utils import (
    como_float,
    detectar_bimodalidade,
    histograma_bins,
    kurtosis,
    moda_histograma,
    nota_real,
    percentil,
    skewness,
    taxas_por_corte,
)

log = logging.getLogger("sas.stats.ciclo_estatisticas")

LARGURA_BIN = 0.5
NOTA_MAXIMA_NORMALIZADA = 10.0
CORTE_INGLES_ITA_F1 = 5.0
NOTA_EXCELENCIA = 7.0


def calcular(
    cliente: Client,
    *,
    ciclo_id: str,
) -> dict[str, Any] | None:
    """Devolve o payload completo do ciclo (F1 + F2 + conjunta + por matéria).

    Retorna None se o ciclo não existir.
    """
    ciclo = _carregar_ciclo(cliente, ciclo_id)
    if ciclo is None:
        return None

    ciclo_anterior = _carregar_ciclo_anterior(cliente, ciclo)
    materias = _mapa_materias(cliente)

    # Carrega simulados e notas do ciclo atual + anterior.
    simulados_atual = _carregar_simulados(cliente, ciclo_id=ciclo_id)
    notas_atual = _carregar_notas(cliente, simulados=simulados_atual)

    if ciclo_anterior:
        simulados_ant = _carregar_simulados(cliente, ciclo_id=ciclo_anterior["id"])
        notas_ant = _carregar_notas(cliente, simulados=simulados_ant)
    else:
        simulados_ant, notas_ant = [], {}

    is_ita = ciclo.get("vestibular_alvo") == "ITA"

    # ── Análise conjunta (ciclo todo, F1+F2 agregados por aluno) ──
    conjunta_atual = _agregado_por_aluno(simulados_atual, notas_atual)
    conjunta_ant = _agregado_por_aluno(simulados_ant, notas_ant)
    bloco_conjunta = _resumir(
        valores=conjunta_atual,
        corte=NOTA_CORTE_FASE_2,
        anterior=conjunta_ant or None,
    )

    # ── Por matéria, com F1 e F2 separados (e delta entre eles) ──
    por_materia = _por_materia_dual_fase(
        simulados=simulados_atual,
        notas=notas_atual,
        simulados_ant=simulados_ant,
        notas_ant=notas_ant,
        materias=materias,
        is_ita=is_ita,
    )

    # ── Evolução temporal: tudo cronologicamente, com fase no payload ──
    evolucao = _evolucao_temporal(
        simulados=simulados_atual,
        notas_por_simulado=notas_atual,
        materias=materias,
    )

    # ── Resumo de topo (KPIs principais pro hero) ──
    stats_conj = bloco_conjunta["stats"]
    resumo = {
        "nAlunos": stats_conj.get("n", 0),
        "media": stats_conj.get("media"),
        "mediana": stats_conj.get("mediana"),
        "pctAprovados": stats_conj.get("pctAprovados"),
        "pctZonaCritica": stats_conj.get("pctZonaCritica"),
        "pctExcelencia": stats_conj.get("pctExcelencia"),
        "delta": bloco_conjunta.get("delta") or {},
    }

    return {
        "ciclo": {
            "id": ciclo["id"],
            "nome": ciclo["nome"],
            "vestibularAlvo": ciclo.get("vestibular_alvo"),
            "ordem": ciclo.get("ordem"),
        },
        "cicloAnterior": (
            {"id": ciclo_anterior["id"], "nome": ciclo_anterior["nome"]}
            if ciclo_anterior
            else None
        ),
        "resumo": resumo,
        "evolucaoTemporal": evolucao,
        "conjunta": bloco_conjunta,
        "porMateria": por_materia,
    }


# ─── Loaders ──────────────────────────────────────────────────────────────


def _carregar_ciclo(cliente: Client, ciclo_id: str) -> dict | None:
    resp = (
        cliente.table("ciclo")
        .select("id, nome, ordem, vestibular_alvo, ano_letivo_id")
        .eq("id", ciclo_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _carregar_ciclo_anterior(cliente: Client, ciclo_atual: dict) -> dict | None:
    ordem = ciclo_atual.get("ordem")
    if ordem is None or ordem <= 1:
        return None
    resp = (
        cliente.table("ciclo")
        .select("id, nome, ordem, vestibular_alvo, ano_letivo_id")
        .eq("vestibular_alvo", ciclo_atual["vestibular_alvo"])
        .eq("ano_letivo_id", ciclo_atual["ano_letivo_id"])
        .eq("ordem", ordem - 1)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _carregar_simulados(cliente: Client, *, ciclo_id: str) -> list[dict]:
    """Todos os simulados não-anulados/não-agregados do ciclo (F1 + F2)."""
    resp = (
        cliente.table("simulado")
        .select("id, nome, rotulo_curto, tipo, data_aplicacao, materia_id, nota_maxima")
        .eq("ciclo_id", ciclo_id)
        .eq("anulado", False)
        .eq("e_agregado", False)
        .order("data_aplicacao")
        .execute()
    )
    return resp.data or []


def _mapa_materias(cliente: Client) -> dict[str, dict]:
    resp = cliente.table("materia").select("id, codigo, nome").execute()
    return {m["id"]: m for m in (resp.data or [])}


def _carregar_notas(cliente: Client, *, simulados: list[dict]) -> dict[str, list[dict]]:
    """{simulado_id: [{aluno_id, nota}]} em escala 0–10."""
    if not simulados:
        return {}
    ids = [s["id"] for s in simulados]
    nota_max_por_sim = {s["id"]: como_float(s.get("nota_maxima")) or 10.0 for s in simulados}

    resp = (
        cliente.table("nota")
        .select("aluno_id, simulado_id, pontuacao, presente")
        .in_("simulado_id", ids)
        .eq("presente", True)
        .execute()
    )
    saida: dict[str, list[dict]] = defaultdict(list)
    for linha in resp.data or []:
        sim_id = linha["simulado_id"]
        nota = nota_real(como_float(linha.get("pontuacao")), nota_max_por_sim[sim_id])
        if nota is None:
            continue
        saida[sim_id].append({"aluno_id": linha["aluno_id"], "nota": nota})
    return saida


# ─── Agregadores ──────────────────────────────────────────────────────────


def _agregado_por_aluno(
    simulados: list[dict],
    notas_por_simulado: dict[str, list[dict]],
) -> list[float]:
    """Uma nota por aluno = média das notas dele entre os simulados do recorte."""
    por_aluno: dict[str, list[float]] = defaultdict(list)
    for sim in simulados:
        for n in notas_por_simulado.get(sim["id"], []):
            por_aluno[n["aluno_id"]].append(n["nota"])
    return [sum(notas) / len(notas) for notas in por_aluno.values() if notas]


def _por_materia_dual_fase(
    *,
    simulados: list[dict],
    notas: dict[str, list[dict]],
    simulados_ant: list[dict],
    notas_ant: dict[str, list[dict]],
    materias: dict[str, dict],
    is_ita: bool,
) -> list[dict]:
    """Para cada matéria, produz {fase1, fase2, deltaF1F2}.

    Cada `fase{N}` é um bloco completo (stats + histograma + comparação com
    ciclo anterior). `deltaF1F2` compara a fase 2 com a fase 1 do mesmo ciclo
    — diferente de `delta`, que compara com o ciclo anterior.
    """
    sim_por_mat_fase: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for s in simulados:
        if s.get("materia_id") and s.get("tipo"):
            sim_por_mat_fase[(s["materia_id"], s["tipo"])].append(s)

    sim_ant_por_mat_fase: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for s in simulados_ant:
        if s.get("materia_id") and s.get("tipo"):
            sim_ant_por_mat_fase[(s["materia_id"], s["tipo"])].append(s)

    # Quais matérias existem no ciclo atual.
    materia_ids = {s["materia_id"] for s in simulados if s.get("materia_id")}

    saida: list[dict] = []
    for materia_id in materia_ids:
        materia = materias.get(materia_id)
        if not materia:
            continue
        codigo = materia["codigo"]
        eliminatoria_f1 = is_ita and codigo == "ingles"
        corte_f1 = CORTE_INGLES_ITA_F1 if eliminatoria_f1 else NOTA_CORTE_FASE_2
        corte_f2 = NOTA_CORTE_FASE_2

        # Fase 1
        f1_atual = _agregado_por_aluno(sim_por_mat_fase.get((materia_id, "fase_1"), []), notas)
        f1_ant = _agregado_por_aluno(sim_ant_por_mat_fase.get((materia_id, "fase_1"), []), notas_ant)
        bloco_f1 = (
            _resumir(valores=f1_atual, corte=corte_f1, anterior=f1_ant or None)
            if f1_atual else None
        )

        # Fase 2
        f2_atual = _agregado_por_aluno(sim_por_mat_fase.get((materia_id, "fase_2"), []), notas)
        f2_ant = _agregado_por_aluno(sim_ant_por_mat_fase.get((materia_id, "fase_2"), []), notas_ant)
        bloco_f2 = (
            _resumir(valores=f2_atual, corte=corte_f2, anterior=f2_ant or None)
            if f2_atual else None
        )

        # Delta F1 → F2 (mesmo ciclo, evolução intra-ciclo).
        delta_f1_f2 = None
        if bloco_f1 and bloco_f2:
            delta_f1_f2 = _calcular_delta(bloco_f2["stats"], bloco_f1["stats"])

        saida.append({
            "materia": {"codigo": codigo, "nome": materia["nome"]},
            "eliminatoriaF1": eliminatoria_f1,
            "fase1": bloco_f1,
            "fase2": bloco_f2,
            "deltaF1F2": delta_f1_f2,
        })

    saida.sort(key=lambda r: r["materia"]["codigo"])
    return saida


def _evolucao_temporal(
    *,
    simulados: list[dict],
    notas_por_simulado: dict[str, list[dict]],
    materias: dict[str, dict],
) -> list[dict]:
    """Lista cronológica de simulados (F1 + F2 misturados, ordenados por data)."""
    saida: list[dict] = []
    for s in simulados:
        notas = [n["nota"] for n in notas_por_simulado.get(s["id"], [])]
        if not notas:
            continue
        media = sum(notas) / len(notas)
        materia_obj = None
        materia_id = s.get("materia_id")
        if materia_id and materia_id in materias:
            m = materias[materia_id]
            materia_obj = {"codigo": m["codigo"], "nome": m["nome"]}
        saida.append({
            "simuladoId": s["id"],
            "nome": s["nome"],
            "rotuloCurto": s.get("rotulo_curto"),
            "data": s["data_aplicacao"],
            "materia": materia_obj,
            "fase": s.get("tipo"),
            "media": round(media, 2),
            "nPresentes": len(notas),
        })
    saida.sort(key=lambda p: p["data"] or "")
    return saida


# ─── Cálculo de stats de um recorte ───────────────────────────────────────


def _resumir(
    *,
    valores: list[float],
    corte: float,
    anterior: list[float] | None,
) -> dict[str, Any]:
    bloco = _stats_payload(valores, corte=corte)
    bloco["corte"] = corte
    if anterior:
        ant = _stats_payload(anterior, corte=corte)
        bloco["anterior"] = ant
        bloco["delta"] = _calcular_delta(bloco["stats"], ant["stats"])
    else:
        bloco["anterior"] = None
        bloco["delta"] = None
    return bloco


def _stats_payload(valores: list[float], *, corte: float) -> dict[str, Any]:
    if not valores:
        return {"stats": _stats_vazio(), "histograma": None}

    n = len(valores)
    media = sum(valores) / n
    mediana = st.median(valores)
    desvio = st.stdev(valores) if n > 1 else 0.0
    variancia = st.variance(valores) if n > 1 else 0.0

    hist = histograma_bins(
        valores,
        largura_bin=LARGURA_BIN,
        maximo=NOTA_MAXIMA_NORMALIZADA,
    )
    pct_apr, pct_crit, pct_exc = taxas_por_corte(
        valores, corte=corte, excelencia=NOTA_EXCELENCIA
    )

    stats = {
        "n": n,
        "media": round(media, 2),
        "mediana": round(mediana, 2),
        "moda": _arr(moda_histograma(hist["contagens"], LARGURA_BIN)),
        "desvioPadrao": round(desvio, 2),
        "variancia": round(variancia, 3),
        "minimo": round(min(valores), 2),
        "maximo": round(max(valores), 2),
        "amplitude": round(max(valores) - min(valores), 2),
        "iqr": _calc_iqr(valores),
        "p10": _arr(percentil(valores, 10)),
        "p25": _arr(percentil(valores, 25)),
        "p50": _arr(percentil(valores, 50)),
        "p75": _arr(percentil(valores, 75)),
        "p90": _arr(percentil(valores, 90)),
        "skewness": _arr3(skewness(valores)),
        "curtose": _arr3(kurtosis(valores)),
        "bimodal": detectar_bimodalidade(hist["contagens"]),
        "pctAprovados": pct_apr,
        "pctZonaCritica": pct_crit,
        "pctExcelencia": pct_exc,
    }
    return {"stats": stats, "histograma": hist}


def _stats_vazio() -> dict[str, Any]:
    return {
        "n": 0,
        "media": None, "mediana": None, "moda": None,
        "desvioPadrao": None, "variancia": None,
        "minimo": None, "maximo": None, "amplitude": None, "iqr": None,
        "p10": None, "p25": None, "p50": None, "p75": None, "p90": None,
        "skewness": None, "curtose": None, "bimodal": False,
        "pctAprovados": None, "pctZonaCritica": None, "pctExcelencia": None,
    }


def _calcular_delta(atual: dict, anterior: dict) -> dict[str, float | None]:
    campos = ("media", "mediana", "desvioPadrao", "pctAprovados", "pctExcelencia")
    saida: dict[str, float | None] = {}
    for k in campos:
        a, b = atual.get(k), anterior.get(k)
        if a is None or b is None:
            saida[k] = None
        else:
            saida[k] = round(a - b, 2)
    return saida


def _calc_iqr(valores: list[float]) -> float | None:
    q1 = percentil(valores, 25)
    q3 = percentil(valores, 75)
    if q1 is None or q3 is None:
        return None
    return round(q3 - q1, 2)


def _arr(v: float | None) -> float | None:
    return round(v, 2) if v is not None else None


def _arr3(v: float | None) -> float | None:
    return round(v, 3) if v is not None else None
