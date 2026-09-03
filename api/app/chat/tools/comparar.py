"""Tools de comparação — entre ciclos, entre alunos e entre simulados.

"Comparar" é função declarada em docs/04-screens e existia só para ciclos: dava
para perguntar "2026/1 contra 2025/4" e não "a Ana contra o Pedro" nem "o P22
foi mais difícil que o P21?" (docs/10 §1.6.3, docs/31 §P3).

`alunos_similares` reaproveita o cálculo de kNN da rota /alunos/{id}/similares.
"""

from __future__ import annotations

import math
import statistics as st
from collections import defaultdict
from typing import Any

from supabase import Client

from ...stats import classificacao as _classif
from ...stats.utils import como_float, nota_real, simulado_entra_no_agregado


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


# ─── comparar_alunos ──────────────────────────────────────────────────────

def comparar_alunos(cliente: Client, *, aluno_ids: list[str]) -> dict:
    """Lado a lado de 2 a 5 alunos: média por matéria, zona, perfil, tendência.

    "Comparar" é função declarada em docs/04-screens, e até aqui só existia
    para ciclos — dava para perguntar "2026/1 contra 2025/4" e não "a Ana
    contra o Pedro" (docs/10 §1.6.3).
    """
    ids = list(dict.fromkeys(aluno_ids or []))
    if not 2 <= len(ids) <= 5:
        return {"erro": "compare de 2 a 5 alunos por vez."}

    nomes_resp = cliente.table("aluno").select("id, nome").in_("id", ids).execute()
    nomes = {a["id"]: a["nome"] for a in (nomes_resp.data or [])}
    faltando = [i for i in ids if i not in nomes]
    if faltando:
        return {"erro": f"aluno(s) não encontrado(s): {', '.join(faltando)}"}

    materias_resp = cliente.table("materia").select("id, codigo, nome").execute()
    materias = {m["id"]: m for m in (materias_resp.data or [])}

    resp = (
        cliente.table("nota")
        .select(
            "aluno_id, pontuacao, "
            "simulado(materia_id, anulado, e_agregado, nota_confiavel, nota_maxima)"
        )
        .eq("presente", True)
        .eq("computavel", True)
        .in_("aluno_id", ids)
        .execute()
    )
    por_aluno_materia: dict[tuple[str, str], list[float]] = defaultdict(list)
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if not simulado_entra_no_agregado(sim):
            continue
        mid = sim.get("materia_id")
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None or not mid:
            continue
        por_aluno_materia[(linha["aluno_id"], mid)].append(nota)

    classif = _classif.mapa_classificacao(cliente)
    codigos = sorted({m["codigo"] for m in materias.values()})

    alunos = []
    for aluno_id in ids:
        c = classif.get(aluno_id) or {}
        por_materia = {}
        for mid, m in materias.items():
            vals = por_aluno_materia.get((aluno_id, mid), [])
            if vals:
                por_materia[m["codigo"]] = round(st.mean(vals), 2)
        alunos.append({
            "alunoId": aluno_id,
            "nome": nomes[aluno_id],
            "zona": c.get("zona"),
            "perfil": c.get("perfil"),
            "tendencia": c.get("tendencia"),
            "media": como_float(c.get("media_recente")),
            "porMateria": por_materia,
        })

    # Onde eles mais divergem: é a pergunta que motiva a comparação, e deixá-la
    # para o modelo calcular a partir da matriz é convite a erro de conta.
    maiores_diferencas = []
    for codigo in codigos:
        valores = [(a["nome"], a["porMateria"].get(codigo)) for a in alunos]
        presentes = [(n, v) for n, v in valores if v is not None]
        if len(presentes) < 2:
            continue
        melhor = max(presentes, key=lambda x: x[1])
        pior = min(presentes, key=lambda x: x[1])
        maiores_diferencas.append({
            "materia": codigo,
            "diferenca": round(melhor[1] - pior[1], 2),
            "maior": {"nome": melhor[0], "media": melhor[1]},
            "menor": {"nome": pior[0], "media": pior[1]},
        })
    maiores_diferencas.sort(key=lambda d: -d["diferenca"])

    return {"alunos": alunos, "maioresDiferencas": maiores_diferencas[:5]}


_SCHEMA_COMPARAR_ALUNOS = {
    "name": "comparar_alunos",
    "description": (
        "Compara de 2 a 5 alunos lado a lado: média por matéria, zona, perfil e "
        "tendência, mais as matérias em que eles mais divergem. Use para 'compare a "
        "Ana com o Pedro'. Descubra os UUIDs com buscar_aluno_por_nome."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "aluno_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "UUIDs dos alunos, de 2 a 5.",
            },
        },
        "required": ["aluno_ids"],
    },
}


# ─── comparar_simulados ───────────────────────────────────────────────────

def comparar_simulados(cliente: Client, *, simulado_ids: list[str]) -> dict:
    """Lado a lado de 2 a 5 simulados, pela métrica geral já calculada.

    Lê `metrica_simulado` no recorte 'geral' em vez de recalcular: essa tabela
    é escrita no ingest e no sync, e é a mesma fonte que a ficha do simulado
    mostra — recalcular aqui poderia divergir da tela.
    """
    ids = list(dict.fromkeys(simulado_ids or []))
    if not 2 <= len(ids) <= 5:
        return {"erro": "compare de 2 a 5 simulados por vez."}

    sims_resp = (
        cliente.table("simulado")
        .select("id, nome, data_aplicacao, tipo, materia_id, nota_maxima, anulado")
        .in_("id", ids)
        .execute()
    )
    sims = {s["id"]: s for s in (sims_resp.data or [])}
    faltando = [i for i in ids if i not in sims]
    if faltando:
        return {"erro": f"simulado(s) não encontrado(s): {', '.join(faltando)}"}

    materias_resp = cliente.table("materia").select("id, codigo, nome").execute()
    materias = {m["id"]: m for m in (materias_resp.data or [])}

    metricas_resp = (
        cliente.table("metrica_simulado")
        .select("simulado_id, media, mediana, desvio_padrao, n_presentes, n_ausentes, "
                "pct_aprovados, pct_zona_critica, pct_excelencia")
        .in_("simulado_id", ids)
        .eq("recorte_tipo", "geral")
        .execute()
    )
    metricas = {m["simulado_id"]: m for m in (metricas_resp.data or [])}

    saida = []
    for sid in ids:
        s = sims[sid]
        m = metricas.get(sid) or {}
        materia = materias.get(s.get("materia_id")) or {}
        saida.append({
            "simuladoId": sid,
            "nome": s.get("nome"),
            "data": s.get("data_aplicacao"),
            "fase": s.get("tipo"),
            "materia": materia.get("codigo"),
            "anulado": s.get("anulado"),
            "media": como_float(m.get("media")),
            "mediana": como_float(m.get("mediana")),
            "desvioPadrao": como_float(m.get("desvio_padrao")),
            "nPresentes": m.get("n_presentes"),
            "nAusentes": m.get("n_ausentes"),
            "pctAprovados": como_float(m.get("pct_aprovados")),
        })

    com_media = [s for s in saida if s["media"] is not None]
    resumo = None
    if len(com_media) >= 2:
        mais_facil = max(com_media, key=lambda s: s["media"])
        mais_dificil = min(com_media, key=lambda s: s["media"])
        resumo = {
            "maiorMedia": {"nome": mais_facil["nome"], "media": mais_facil["media"]},
            "menorMedia": {"nome": mais_dificil["nome"], "media": mais_dificil["media"]},
            "amplitude": round(mais_facil["media"] - mais_dificil["media"], 2),
        }

    return {"simulados": saida, "resumo": resumo}


_SCHEMA_COMPARAR_SIMULADOS = {
    "name": "comparar_simulados",
    "description": (
        "Compara de 2 a 5 simulados lado a lado: média, mediana, desvio, presentes, "
        "ausentes e taxa de aprovados, mais qual foi o mais fácil e o mais difícil. "
        "Use para 'o P22 foi mais difícil que o P21?'. Descubra os UUIDs com listar_simulados."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "simulado_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "UUIDs dos simulados, de 2 a 5.",
            },
        },
        "required": ["simulado_ids"],
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
                "materia_id, data_aplicacao, anulado, e_agregado, nota_confiavel, "
                "nota_maxima)")
        .eq("presente", True)
        .eq("computavel", True)
        .execute()
    )

    por_aluno: dict[str, list[dict]] = defaultdict(list)
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if not simulado_entra_no_agregado(sim):
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
    (_SCHEMA_COMPARAR_ALUNOS, comparar_alunos),
    (_SCHEMA_COMPARAR_SIMULADOS, comparar_simulados),
    (_SCHEMA_ALUNOS_SIMILARES, alunos_similares),
]
