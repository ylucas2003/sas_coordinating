"""Tools de comparação — entre ciclos e entre alunos.

Reaproveita o cálculo de kNN da rota /alunos/{id}/similares (mesma lógica).
"""

from __future__ import annotations

import math
import statistics as st
from collections import defaultdict
from typing import Any

from supabase import Client

from ...stats import classificacao as _classif
from ...stats.utils import como_float, nota_real


# ─── comparar_ciclos ──────────────────────────────────────────────────────

def comparar_ciclos(
    cliente: Client,
    *,
    ciclo_id_a: str,
    ciclo_id_b: str,
) -> dict:
    """Compara duas ciclos no nível conjunto (média, mediana, taxas).

    Carrega métricas dos dois ciclos rodando o stats engine, mas só devolve
    o resumo conjunto (não o por matéria) — pra ficar compacto.
    """
    from ...stats import ciclo_estatisticas

    pa = ciclo_estatisticas.calcular(cliente, ciclo_id=ciclo_id_a)
    pb = ciclo_estatisticas.calcular(cliente, ciclo_id=ciclo_id_b)
    if pa is None:
        return {"erro": f"ciclo {ciclo_id_a} não encontrado"}
    if pb is None:
        return {"erro": f"ciclo {ciclo_id_b} não encontrado"}

    sa = (pa.get("conjunta") or {}).get("stats") or {}
    sb = (pb.get("conjunta") or {}).get("stats") or {}
    delta = {}
    for k in ("media", "mediana", "desvioPadrao", "pctAprovados", "pctZonaCritica", "pctExcelencia"):
        va, vb = sa.get(k), sb.get(k)
        if va is not None and vb is not None:
            delta[k] = round(va - vb, 3)
    return {
        "cicloA": {"ciclo": pa.get("ciclo"), "stats": _filtrar(sa)},
        "cicloB": {"ciclo": pb.get("ciclo"), "stats": _filtrar(sb)},
        "delta_AmenosB": delta,
    }


_SCHEMA_COMPARAR_CICLOS = {
    "name": "comparar_ciclos",
    "description": (
        "Compara dois ciclos na análise conjunta (média, mediana, taxa de aprovados, etc.). "
        "Retorna delta = A − B. Útil pra '2026/1 vs 2025/4'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ciclo_id_a": {"type": "string", "description": "UUID do ciclo A."},
            "ciclo_id_b": {"type": "string", "description": "UUID do ciclo B (para o delta)."},
        },
        "required": ["ciclo_id_a", "ciclo_id_b"],
    },
}


# ─── alunos_similares ─────────────────────────────────────────────────────

def alunos_similares(cliente: Client, *, aluno_id: str, k: int = 5) -> dict:
    """kNN: alunos mais próximos por vetor (médias por matéria + desvio + slope)."""
    vetores = _vetores_features(cliente)
    if aluno_id not in vetores:
        return {"erro": f"aluno {aluno_id} sem notas suficientes para vetor de features"}

    alvo = vetores[aluno_id]
    distancias: list[tuple[str, float]] = []
    for outro_id, vec in vetores.items():
        if outro_id == aluno_id:
            continue
        d = _distancia(alvo, vec)
        if d is None:
            continue
        distancias.append((outro_id, d))
    distancias.sort(key=lambda x: x[1])
    top = distancias[:k]

    nomes_resp = cliente.table("aluno").select("id, nome").execute()
    nomes = {a["id"]: a["nome"] for a in (nomes_resp.data or [])}
    classif = _classif.mapa_classificacao(cliente)

    saida = []
    for outro_id, d in top:
        c = classif.get(outro_id) or {}
        saida.append({
            "alunoId": outro_id,
            "nome": nomes.get(outro_id, outro_id),
            "distancia": round(d, 3),
            "perfil": c.get("perfil"),
            "tendencia": c.get("tendencia"),
            "zona": c.get("zona"),
            "media": como_float(c.get("media_recente")),
        })
    return {"alunoId": aluno_id, "k": k, "similares": saida}


_SCHEMA_ALUNOS_SIMILARES = {
    "name": "alunos_similares",
    "description": (
        "kNN: alunos mais parecidos com o alvo, por vetor de features "
        "(médias por matéria + desvio geral + coeficiente de tendência). "
        "Distância euclidiana normalizada. Útil pra 'quem mais se parece com o aluno X'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "aluno_id": {"type": "string", "description": "UUID do aluno alvo."},
            "k": {"type": "integer", "default": 5, "description": "Quantos vizinhos."},
        },
        "required": ["aluno_id"],
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────────

def _filtrar(stats: dict) -> dict:
    """Stats mínimo pra LLM (sem histograma, sem outliers de campo)."""
    keys = ("n", "media", "mediana", "desvioPadrao", "p10", "p90",
            "pctAprovados", "pctZonaCritica", "pctExcelencia", "skewness", "curtose", "bimodal")
    return {k: stats.get(k) for k in keys if stats.get(k) is not None}


def _vetores_features(cliente: Client) -> dict[str, list[float | None]]:
    """{aluno_id: vetor}. Cópia simplificada da lógica em routes/alunos.py."""
    materias_resp = cliente.table("materia").select("id, nome").execute()
    materias = sorted(materias_resp.data or [], key=lambda m: m["nome"])
    materia_ids = [m["id"] for m in materias]

    resp = (
        cliente.table("nota")
        .select("aluno_id, pontuacao, simulado("
                "materia_id, data_aplicacao, anulado, e_agregado, nota_maxima)")
        .eq("presente", True)
        .execute()
    )

    por_aluno: dict[str, list[dict]] = defaultdict(list)
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        mid = sim.get("materia_id")
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None or not mid:
            continue
        por_aluno[linha["aluno_id"]].append({"materia_id": mid, "nota": nota})

    classif = _classif.mapa_classificacao(cliente)
    vetores: dict[str, list[float | None]] = {}
    for aluno_id, notas in por_aluno.items():
        por_mat: dict[str, list[float]] = defaultdict(list)
        for n in notas:
            por_mat[n["materia_id"]].append(n["nota"])
        v: list[float | None] = []
        for mid in materia_ids:
            vals = por_mat.get(mid, [])
            v.append(st.mean(vals) if vals else None)
        todas = [n["nota"] for n in notas]
        v.append(st.stdev(todas) if len(todas) > 1 else None)
        v.append(como_float((classif.get(aluno_id) or {}).get("coef_tendencia")))
        vetores[aluno_id] = v
    return vetores


def _distancia(a: list[float | None], b: list[float | None]) -> float | None:
    if len(a) != len(b):
        return None
    soma = 0.0
    dims = 0
    for x, y in zip(a, b):
        if x is None or y is None:
            continue
        soma += (x - y) ** 2
        dims += 1
    if dims == 0:
        return None
    return math.sqrt(soma / dims)


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, callable]] = [
    (_SCHEMA_COMPARAR_CICLOS, comparar_ciclos),
    (_SCHEMA_ALUNOS_SIMILARES, alunos_similares),
]
