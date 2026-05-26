"""Métricas agregadas por simulado.

Para cada simulado válido (não-anulado, não-agregado), calculamos
estatísticas em três recortes:
  - geral  : todas as notas do simulado
  - turma  : uma linha por turma
  - sede   : uma linha por sede

Persistido em `metrica_simulado (simulado_id, recorte_tipo, recorte_id)`.
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

# Inglês ITA Fase 1 é eliminatória com corte 5,0 (escala 0–10) — todos os
# demais recortes usam o corte padrão de Fase 2 (4,0 por matéria), aplicado
# também na Fase 1 por consistência visual.
CORTE_INGLES_ITA_F1 = 5.0
NOTA_EXCELENCIA = 7.0

log = logging.getLogger("sas.stats.metricas")

# Largura do bin do histograma — notas sempre em escala 0–10 → 20 bins de 0,5.
LARGURA_BIN = 0.5
NOTA_MAXIMA_NORMALIZADA = 10.0


def recalcular_tudo(cliente: Client) -> int:
    """Recalcula métricas de todos os simulados válidos.

    Retorna a quantidade de simulados processados. Chamado pelo pipeline
    após o upload acabar.
    """
    resp = (
        cliente.table("simulado")
        .select(
            "id, nota_maxima, anulado, e_agregado, tipo, materia_id, "
            "ciclo:ciclo_id(vestibular_alvo), materia:materia_id(codigo)"
        )
        .eq("anulado", False)
        .eq("e_agregado", False)
        .execute()
    )
    simulados = resp.data or []
    log.info("recalculando métricas de %d simulados", len(simulados))

    for simulado in simulados:
        recalcular_simulado(
            cliente,
            simulado_id=simulado["id"],
            nota_maxima=como_float(simulado.get("nota_maxima")) or 10.0,
            corte=_corte_aplicavel(simulado),
        )
    return len(simulados)


def _corte_aplicavel(simulado: dict) -> float:
    """Decide o corte (escala 0–10) que define "aprovado" pra esse simulado.

    Regra: corte padrão 4,0 (Fase 2 por matéria, aplicado também em Fase 1
    por consistência visual). Exceção única: Inglês na Fase 1 do ITA —
    eliminatória com corte 5,0.
    """
    materia = (simulado.get("materia") or {}).get("codigo") if simulado.get("materia") else None
    ciclo = simulado.get("ciclo") or {}
    vest = ciclo.get("vestibular_alvo")
    tipo = simulado.get("tipo")
    if vest == "ITA" and tipo == "fase_1" and materia == "ingles":
        return CORTE_INGLES_ITA_F1
    return NOTA_CORTE_FASE_2


def recalcular_simulado(
    cliente: Client,
    *,
    simulado_id: str,
    nota_maxima: float,
    corte: float = NOTA_CORTE_FASE_2,
) -> None:
    """Recalcula as 3 visões de métrica de um simulado.

    Todas as estatísticas (média, mediana, desvio, histograma) ficam em
    escala 0–10, não na escala do simulado original. Razão: a coluna
    `Points Possible` do Canvas representa o número de questões, e a "nota"
    sempre é interpretada como (acertos / total) * 10.
    """
    notas_presentes, n_ausentes = _carregar_notas(cliente, simulado_id, nota_maxima=nota_maxima)

    # Geral.
    _salvar(
        cliente,
        simulado_id=simulado_id,
        recorte_tipo="geral",
        recorte_id=None,
        valores=[n["pontuacao"] for n in notas_presentes],
        n_ausentes=n_ausentes,
        corte=corte,
    )

    # Por turma.
    por_turma: dict[str, list[float]] = defaultdict(list)
    for n in notas_presentes:
        if n.get("turma_id"):
            por_turma[n["turma_id"]].append(n["pontuacao"])
    for turma_id, valores in por_turma.items():
        _salvar(
            cliente,
            simulado_id=simulado_id,
            recorte_tipo="turma",
            recorte_id=turma_id,
            valores=valores,
            n_ausentes=0,
            corte=corte,
        )

    # Por sede.
    por_sede: dict[str, list[float]] = defaultdict(list)
    for n in notas_presentes:
        if n.get("sede_id"):
            por_sede[n["sede_id"]].append(n["pontuacao"])
    for sede_id, valores in por_sede.items():
        _salvar(
            cliente,
            simulado_id=simulado_id,
            recorte_tipo="sede",
            recorte_id=sede_id,
            valores=valores,
            n_ausentes=0,
            corte=corte,
        )


# ─── Internals ────────────────────────────────────────────────────────────


def _carregar_notas(
    cliente: Client,
    simulado_id: str,
    *,
    nota_maxima: float,
) -> tuple[list[dict], int]:
    """Carrega notas do simulado via view `v_nota_dimensoes`, já normalizadas
    para escala 0–10.

    A pontuação no banco é "acertos brutos"; aqui aplicamos
    `(pontuacao / nota_maxima) * 10` para que todos os cálculos (média,
    mediana, desvio, histograma) fiquem na mesma escala — comparável entre
    simulados de matérias diferentes.

    Retorna (presentes_com_dimensoes, n_ausentes).
    """
    resp_pres = (
        cliente.table("v_nota_dimensoes")
        .select("aluno_id, pontuacao, turma_id, sede_id")
        .eq("simulado_id", simulado_id)
        .eq("presente", True)
        .execute()
    )
    presentes: list[dict] = []
    for linha in resp_pres.data or []:
        nota = nota_real(como_float(linha.get("pontuacao")), nota_maxima)
        if nota is None:
            continue
        presentes.append(
            {
                "pontuacao": nota,                          # 0–10
                "turma_id": linha.get("turma_id"),
                "sede_id": linha.get("sede_id"),
            }
        )

    resp_aus = (
        cliente.table("nota")
        .select("aluno_id", count="exact")
        .eq("simulado_id", simulado_id)
        .eq("presente", False)
        .execute()
    )
    n_ausentes = resp_aus.count or 0
    return presentes, n_ausentes


def _salvar(
    cliente: Client,
    *,
    simulado_id: str,
    recorte_tipo: str,
    recorte_id: str | None,
    valores: list[float],
    n_ausentes: int,
    corte: float,
) -> None:
    """Upserta uma linha em `metrica_simulado`. Os valores estão sempre
    em escala 0–10 (normalizados em `_carregar_notas`)."""
    if not valores:
        payload: dict[str, Any] = {
            "simulado_id": simulado_id,
            "recorte_tipo": recorte_tipo,
            "recorte_id": recorte_id,
            "media": None,
            "mediana": None,
            "desvio_padrao": None,
            "variancia": None,
            "minimo": None,
            "maximo": None,
            "quartil_1": None,
            "quartil_3": None,
            "n_presentes": 0,
            "n_ausentes": n_ausentes,
            "histograma": None,
            "skewness": None,
            "curtose": None,
            "p10": None,
            "p90": None,
            "moda": None,
            "pct_aprovados": None,
            "pct_zona_critica": None,
            "pct_excelencia": None,
            "bimodal_flag": False,
        }
    else:
        media = st.mean(valores)
        mediana = st.median(valores)
        desvio = st.stdev(valores) if len(valores) > 1 else 0.0
        variancia = st.variance(valores) if len(valores) > 1 else 0.0
        hist = histograma_bins(
            valores,
            largura_bin=LARGURA_BIN,
            maximo=NOTA_MAXIMA_NORMALIZADA,
        )
        pct_apr, pct_crit, pct_exc = taxas_por_corte(
            valores, corte=corte, excelencia=NOTA_EXCELENCIA
        )
        payload = {
            "simulado_id": simulado_id,
            "recorte_tipo": recorte_tipo,
            "recorte_id": recorte_id,
            "media": round(media, 2),
            "mediana": round(mediana, 2),
            "desvio_padrao": round(desvio, 2),
            "variancia": round(variancia, 3),
            "minimo": round(min(valores), 2),
            "maximo": round(max(valores), 2),
            "quartil_1": _arredonda(percentil(valores, 25)),
            "quartil_3": _arredonda(percentil(valores, 75)),
            "n_presentes": len(valores),
            "n_ausentes": n_ausentes,
            "histograma": hist,
            "skewness": _arredonda3(skewness(valores)),
            "curtose": _arredonda3(kurtosis(valores)),
            "p10": _arredonda(percentil(valores, 10)),
            "p90": _arredonda(percentil(valores, 90)),
            "moda": _arredonda(moda_histograma(hist["contagens"], LARGURA_BIN)),
            "pct_aprovados": pct_apr,
            "pct_zona_critica": pct_crit,
            "pct_excelencia": pct_exc,
            "bimodal_flag": detectar_bimodalidade(hist["contagens"]),
        }

    cliente.table("metrica_simulado").upsert(
        payload,
        on_conflict="simulado_id,recorte_tipo,recorte_id",
    ).execute()


def _arredonda(v: float | None) -> float | None:
    return round(v, 2) if v is not None else None


def _arredonda3(v: float | None) -> float | None:
    return round(v, 3) if v is not None else None


# ─── Consultas auxiliares pra outros módulos ──────────────────────────────


_CAMPOS_METRICA = (
    "media, mediana, desvio_padrao, variancia, minimo, maximo, "
    "quartil_1, quartil_3, n_presentes, n_ausentes, histograma, "
    "skewness, curtose, p10, p90, moda, "
    "pct_aprovados, pct_zona_critica, pct_excelencia, bimodal_flag"
)


def carregar_metrica_geral(cliente: Client, simulado_id: str) -> dict | None:
    """Devolve a linha geral da `metrica_simulado` ou None."""
    resp = (
        cliente.table("metrica_simulado")
        .select(_CAMPOS_METRICA)
        .eq("simulado_id", simulado_id)
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def mapa_metrica_geral_por_simulado(cliente: Client) -> dict[str, dict]:
    """{simulado_id: {media, mediana, desvio_padrao, n_presentes, ...}} para todos os simulados."""
    resp = (
        cliente.table("metrica_simulado")
        .select("simulado_id, media, mediana, desvio_padrao, n_presentes, n_ausentes")
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .execute()
    )
    return {linha["simulado_id"]: linha for linha in (resp.data or [])}
