"""Tools estatísticas — agregados de ciclo, trajetória de aluno, distribuição.

Reaproveitam `stats.ciclo_estatisticas.calcular` e a tabela `metrica_simulado`.
A diferença pras rotas do front é que devolvemos um payload mais conciso —
LLM lida mal com payloads de 100k tokens, então simplificamos antes de enviar.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from ...stats import aluno_dados, ciclo_estatisticas, criterios, criterios_repo
from ...stats.utils import como_float, nota_real

#: Tetos da saída. O despacho não confere `maximum` (ferramentas.py), e as
#: duas listas são dado de aluno: quem limita é o handler (LGPD art. 6º, III).
TETO_DA_TRAJETORIA = 100
TETO_DE_NOTAS = 100

# ─── estatisticas_ciclo ───────────────────────────────────────────────────

def estatisticas_ciclo(
    cliente: Client,
    *,
    ciclo_id: str,
    incluir_por_materia: bool = True,
    criterio: str | None = None,
) -> dict:
    """Resumo estatístico de um ciclo (conjunta + por matéria, comparação com anterior).

    `criterio` decide TODO corte do payload, e existe porque o coordenador
    escolhe a régua na tela. Sem ele, a tool respondia sempre pela régua da
    casa enquanto o preâmbulo de contexto anunciava "régua de corte 'ita-f1'" —
    e o assistente dizia 70,98% de aprovados em Física ao lado de um gráfico
    marcando 60,14% (docs/31 §P3).
    """
    try:
        regua = criterios_repo.resolver(cliente, criterio or criterios.CRITERIO_DA_CASA)
    except KeyError as exc:
        return {"erro": str(exc)}

    payload = ciclo_estatisticas.calcular(cliente, ciclo_id=ciclo_id, criterio=regua)
    if payload is None:
        return {"erro": f"ciclo {ciclo_id} não encontrado"}
    compacto = _compactar_para_llm(payload, incluir_por_materia=incluir_por_materia)
    # O rótulo é obrigatório: um `corte` sem dizer de que régua ele saiu é o
    # que faz o modelo misturar dois números certos numa resposta errada.
    compacto["criterio"] = regua.nome
    return compacto


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
        "eliminatoria": m.get("eliminatoria", False),
        "corte": m.get("corte"),
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
        "(F1 e F2 separados, com corte aplicado). Todo corte e toda taxa saem da RÉGUA: "
        "se o contexto disser qual régua está na tela, passe o slug dela em `criterio`, "
        "senão os números não vão bater com o que a pessoa está vendo. O campo `criterio` "
        "da resposta diz qual régua respondeu — cite-a ao dar percentuais."
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
            "criterio": {
                "type": "string",
                "description": (
                    "Slug da régua: tio-leo | ita-f1 | ita-f2 | ime-f1 | ime-f2, ou uma "
                    "criada pela coordenação. Omitir usa a régua da casa (tio-leo)."
                ),
            },
        },
        "required": ["ciclo_id"],
    },
}


# ─── trajetoria_aluno ─────────────────────────────────────────────────────

def trajetoria_aluno(cliente: Client, *, aluno_id: str, limite: int = 40) -> dict:
    """Histórico cronológico de notas do aluno (escala 0–10).

    Quem entra na série é `aluno_dados.trajetoria_do_aluno`, a mesma leitura de
    `/alunos/{id}/trajetoria`; aqui só se escolhem os campos. `total` conta o
    que volta, depois do corte nas `limite` mais recentes.

    O piso é daqui porque o domínio avisa: com zero ou negativo o corte dele
    não faz o que o nome promete, e o despacho não confere `minimum`.
    """
    limite = min(max(1, limite), TETO_DA_TRAJETORIA)
    linhas = [
        {
            "simuladoId": p["simuladoId"],
            "simulado": p["simulado"],
            "rotuloCurto": p["rotuloCurto"],
            "dataAplicacao": p["dataAplicacao"],
            "materia": p["materia"],
            "tipo": p["tipo"],
            "cicloId": p["cicloId"],
            "nota": p["nota"],
        }
        for p in aluno_dados.trajetoria_do_aluno(cliente, aluno_id, limite)
    ]
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
            "limite": {
                "type": "integer",
                "default": 40,
                "description": f"Máx. notas retornadas (as mais recentes), até {TETO_DA_TRAJETORIA}.",
            },
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

    Para listas grandes, prefira `exportar_csv`. O teto é minimização (LGPD
    art. 6º, III; mapa de LGPD de 24/10): é a nota da turma inteira, e o
    despacho não confere `maximum`. `total` continua contando todos.
    """
    limite = min(max(1, limite), TETO_DE_NOTAS)
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
            "limite": {"type": "integer", "default": 50, "description": f"Quantas notas listar, até {TETO_DE_NOTAS}."},
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

#: Todas ao MCP (docs/43 §5.4, mapa de LGPD de 24/10). As de ciclo e de
#: simulado são agregado sem pessoa; trajetória e notas são dado de aluno com
#: o id no mesmo dict, e o MCP troca o nome por "Aluno <matrícula>".
METADADOS: dict[str, dict] = {
    "estatisticas_ciclo": {"expor_no_mcp": True},
    "trajetoria_aluno": {"expor_no_mcp": True},
    "histograma_simulado": {"expor_no_mcp": True},
    "notas_simulado": {"expor_no_mcp": True},
}
