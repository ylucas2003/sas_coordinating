"""Tools estatísticas — agregados de ciclo, trajetória de aluno, distribuição.

Reaproveitam `stats.ciclo_estatisticas.calcular` e a tabela `metrica_simulado`.
A diferença pras rotas do front é que devolvemos um payload mais conciso —
LLM lida mal com payloads de 100k tokens, então simplificamos antes de enviar.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from ...stats import ciclo_estatisticas
from ...stats.utils import como_float, nota_real


# ─── estatisticas_ciclo ───────────────────────────────────────────────────

def estatisticas_ciclo(
    cliente: Client,
    *,
    ciclo_id: str,
    incluir_por_materia: bool = True,
) -> dict:
    """Resumo estatístico de um ciclo (conjunta + por matéria, comparação com anterior)."""
    payload = ciclo_estatisticas.calcular(cliente, ciclo_id=ciclo_id)
    if payload is None:
        return {"erro": f"ciclo {ciclo_id} não encontrado"}
    return _compactar_para_llm(payload, incluir_por_materia=incluir_por_materia)


def _compactar_para_llm(payload: dict, *, incluir_por_materia: bool) -> dict:
    """Reduz o payload bruto a um dict compacto e legível pelo LLM.

    O payload original tem ~30k tokens — perde foco e custa caro. Aqui ficamos
    com o essencial: métricas + contagens, e DESCARTAMOS o histograma bruto
    (ele só faz sentido pro front renderizar; o LLM se confunde com array de bins).
    """
    out: dict = {
        "ciclo": payload.get("ciclo"),
        "cicloAnterior": (payload.get("cicloAnterior") or {}).get("nome") if payload.get("cicloAnterior") else None,
        "conjunta": _stats_min(payload.get("conjunta")),
    }
    if incluir_por_materia:
        out["porMateria"] = [
            _materia_min(m) for m in (payload.get("porMateria") or [])
        ]
    return out


_KEYS_STATS_LLM = (
    "n", "media", "mediana", "desvioPadrao", "p10", "p90",
    "pctAprovados", "pctZonaCritica", "pctExcelencia",
    "skewness", "curtose", "bimodal",
)


def _stats_min(bloco: dict | None) -> dict:
    """Extrai só o essencial de um bloco {stats, anterior, delta, corte}."""
    if not bloco:
        return {}
    stats = bloco.get("stats") or {}
    anterior = (bloco.get("anterior") or {}).get("stats") if bloco.get("anterior") else None
    delta = bloco.get("delta") or {}
    out = {k: stats.get(k) for k in _KEYS_STATS_LLM if stats.get(k) is not None}
    if bloco.get("corte") is not None:
        out["corte"] = bloco["corte"]
    if anterior:
        out["anterior"] = {k: anterior.get(k) for k in _KEYS_STATS_LLM if anterior.get(k) is not None}
    if delta:
        # Apenas deltas das métricas que importam.
        out["delta"] = {k: v for k, v in delta.items() if v is not None and k in _KEYS_STATS_LLM}
    return out


def _materia_min(m: dict) -> dict:
    return {
        "materia": m.get("materia"),
        "eliminatoriaF1": m.get("eliminatoriaF1", False),
        "fase1": _stats_min(m.get("fase1")),
        "fase2": _stats_min(m.get("fase2")),
        "deltaF1F2": m.get("deltaF1F2"),
    }


_SCHEMA_EST_CICLO = {
    "name": "estatisticas_ciclo",
    "description": (
        "Resumo estatístico de um ciclo: média, mediana, desvio, taxa de aprovados, "
        "histograma da análise conjunta (F1+F2 agregados por aluno), e quando disponível "
        "a comparação com o ciclo anterior. Por padrão inclui também o recorte por matéria "
        "(F1 e F2 separados, com corte aplicado)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ciclo_id": {"type": "string", "description": "UUID do ciclo."},
            "incluir_por_materia": {
                "type": "boolean",
                "default": True,
                "description": "Se false, retorna só conjunta (mais compacto).",
            },
        },
        "required": ["ciclo_id"],
    },
}


# ─── trajetoria_aluno ─────────────────────────────────────────────────────

def trajetoria_aluno(cliente: Client, *, aluno_id: str, limite: int = 40) -> dict:
    """Histórico cronológico de notas do aluno (escala 0–10)."""
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, anulado, e_agregado, "
            "materia_id, nota_maxima, tipo, fase, ciclo_id)"
        )
        .eq("aluno_id", aluno_id)
        .execute()
    )

    materias_resp = cliente.table("materia").select("id, codigo, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (materias_resp.data or [])}

    linhas: list[dict] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        if not linha.get("presente"):
            continue
        nota = nota_real(
            como_float(linha.get("pontuacao")),
            como_float(sim.get("nota_maxima")),
        )
        if nota is None:
            continue
        linhas.append(
            {
                "simuladoId": sim.get("id"),
                "simulado": sim.get("nome"),
                "rotuloCurto": sim.get("rotulo_curto"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "materia": nome_mat.get(sim.get("materia_id")) if sim.get("materia_id") else None,
                "tipo": sim.get("tipo"),
                "fase": sim.get("fase"),
                "cicloId": sim.get("ciclo_id"),
                "nota": round(nota, 2),
            }
        )
    linhas.sort(key=lambda r: r["dataAplicacao"] or "")

    # Aplica limite ao final, mantendo as mais recentes
    if len(linhas) > limite:
        linhas = linhas[-limite:]

    return {"total": len(linhas), "trajetoria": linhas}


_SCHEMA_TRAJETORIA = {
    "name": "trajetoria_aluno",
    "description": (
        "Histórico cronológico de notas do aluno em escala 0–10. "
        "Use pra responder 'qual a evolução do aluno X', 'em que matérias ele caiu', etc."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "aluno_id": {"type": "string", "description": "UUID do aluno."},
            "limite": {"type": "integer", "default": 40, "description": "Máx. notas retornadas (mais recentes)."},
        },
        "required": ["aluno_id"],
    },
}


# ─── histograma_simulado ──────────────────────────────────────────────────

def histograma_simulado(cliente: Client, *, simulado_id: str) -> dict:
    """Distribuição de notas em bins de 0,5 ponto (cache em metrica_simulado)."""
    resp = (
        cliente.table("metrica_simulado")
        .select(
            "media, mediana, desvio_padrao, quartil_1, quartil_3, n_presentes, n_ausentes, histograma"
        )
        .eq("simulado_id", simulado_id)
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .limit(1)
        .execute()
    )
    if not resp.data:
        return {"erro": f"métrica de {simulado_id} ainda não calculada"}
    m = resp.data[0]
    return {
        "simuladoId": simulado_id,
        "histograma": m.get("histograma"),
        "media": _f(m.get("media")),
        "mediana": _f(m.get("mediana")),
        "desvioPadrao": _f(m.get("desvio_padrao")),
        "quartil1": _f(m.get("quartil_1")),
        "quartil3": _f(m.get("quartil_3")),
        "nPresentes": m.get("n_presentes"),
        "nAusentes": m.get("n_ausentes"),
    }


_SCHEMA_HIST_SIMULADO = {
    "name": "histograma_simulado",
    "description": (
        "Distribuição de notas (histograma com bins de 0,5) + estatísticas básicas de um simulado."
    ),
    "parameters": {
        "type": "object",
        "properties": {"simulado_id": {"type": "string", "description": "UUID do simulado."}},
        "required": ["simulado_id"],
    },
}


# ─── notas_simulado ───────────────────────────────────────────────────────

def notas_simulado(cliente: Client, *, simulado_id: str, limite: int = 50) -> dict:
    """Tabela completa de notas de um simulado (aluno × nota normalizada).

    Para listas grandes, prefira `ranking_simulado` ou `exportar_csv`.
    """
    base = (
        cliente.table("simulado")
        .select("nota_maxima")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not base.data:
        return {"erro": f"simulado {simulado_id} não encontrado"}
    nota_max = como_float(base.data[0].get("nota_maxima"))

    resp = (
        cliente.table("nota")
        .select("pontuacao, presente, aluno(id, nome)")
        .eq("simulado_id", simulado_id)
        .execute()
    )
    saida: list[dict] = []
    for linha in resp.data or []:
        aluno = linha.get("aluno") or {}
        bruta = como_float(linha.get("pontuacao"))
        nota = nota_real(bruta, nota_max)
        saida.append(
            {
                "alunoId": aluno.get("id"),
                "nome": aluno.get("nome", ""),
                "nota": round(nota, 2) if nota is not None else None,
                "presente": bool(linha.get("presente")),
            }
        )
    saida.sort(key=lambda r: (not r["presente"], -(r["nota"] or 0)))
    truncado = len(saida) > limite
    return {"total": len(saida), "truncado": truncado, "notas": saida[:limite]}


_SCHEMA_NOTAS_SIMULADO = {
    "name": "notas_simulado",
    "description": (
        "Notas de todos os alunos em um simulado, ordenadas (presentes primeiro, nota desc). "
        "Limita a 50 por default — para listas maiores use exportar_csv."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "simulado_id": {"type": "string", "description": "UUID do simulado."},
            "limite": {"type": "integer", "default": 50},
        },
        "required": ["simulado_id"],
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────────

def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, callable]] = [
    (_SCHEMA_EST_CICLO, estatisticas_ciclo),
    (_SCHEMA_TRAJETORIA, trajetoria_aluno),
    (_SCHEMA_HIST_SIMULADO, histograma_simulado),
    (_SCHEMA_NOTAS_SIMULADO, notas_simulado),
]
