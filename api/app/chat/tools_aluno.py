"""Tools do chat do aluno — restritas aos dados do próprio aluno.

Espelham os endpoints /me: cada handler recebe o `aluno_id` injetado pelo
dispatcher a partir do JWT. NENHUM schema declara `aluno_id` — mesmo que o
LLM alucine um nos argumentos, o dispatcher o descarta e injeta o do token.

Mesmas convenções do registry do coordenador (tools/__init__.py):
read-only, retornos JSON-serializáveis, erros como {"erro": "..."}.
"""

from __future__ import annotations

from typing import Any, Callable

from supabase import Client

from ..stats.aluno_dados import (
    detalhe_simulado_do_aluno,
    evolucao_do_aluno,
    payload_insight_ciclo,
    questoes_do_aluno_no_simulado,
    simulados_do_aluno,
    streak_do_aluno,
)
from ..stats.insight_aluno import gerar_para_aluno_ciclo


# ─── minhas_notas ─────────────────────────────────────────────────────────

def minhas_notas(cliente: Client, *, aluno_id: str) -> dict:
    """Todos os simulados do aluno com nota, delta e média da turma."""
    simulados = simulados_do_aluno(cliente, aluno_id)
    return {"total": len(simulados), "simulados": simulados}


_SCHEMA_MINHAS_NOTAS = {
    "name": "minhas_notas",
    "description": (
        "Lista todos os simulados do aluno com nota (0-10), delta vs o próprio "
        "padrão, média da turma, matéria, ciclo e vestibular. Use PRIMEIRO para "
        "descobrir os ids dos simulados antes das tools de detalhe."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── meu_desempenho_em_simulado ───────────────────────────────────────────

def meu_desempenho_em_simulado(cliente: Client, *, aluno_id: str, simulado_id: str) -> dict:
    """Nota, posição, percentil e comparação com grupos num simulado."""
    return detalhe_simulado_do_aluno(cliente, aluno_id, simulado_id)


_SCHEMA_MEU_DESEMPENHO = {
    "name": "meu_desempenho_em_simulado",
    "description": (
        "Detalhe do aluno em UM simulado: nota, posição no ranking, percentil e "
        "comparação com a média geral, top 15% e inferior 15% da turma. "
        "Requer o simulado_id (descubra com minhas_notas)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "simulado_id": {"type": "string", "description": "id (UUID) do simulado."},
        },
        "required": ["simulado_id"],
    },
}


# ─── minha_evolucao ───────────────────────────────────────────────────────

def minha_evolucao(cliente: Client, *, aluno_id: str) -> dict:
    """Séries por matéria ao longo dos ciclos (aluno × média da turma)."""
    evolucao = evolucao_do_aluno(cliente, aluno_id)
    evolucao["materias_disponiveis"] = sorted((evolucao.get("materias") or {}).keys())
    return evolucao


_SCHEMA_MINHA_EVOLUCAO = {
    "name": "minha_evolucao",
    "description": (
        "Evolução do aluno por matéria ao longo dos ciclos, comparada à média da "
        "turma. Use para perguntas de tendência ('estou melhorando em física?')."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── meu_streak ───────────────────────────────────────────────────────────

def meu_streak(cliente: Client, *, aluno_id: str) -> dict:
    """Ciclos consecutivos acima da média da turma."""
    return streak_do_aluno(cliente, aluno_id)


_SCHEMA_MEU_STREAK = {
    "name": "meu_streak",
    "description": "Quantos ciclos consecutivos o aluno fechou acima da média da turma.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── minhas_questoes_erradas ──────────────────────────────────────────────

def minhas_questoes_erradas(cliente: Client, *, aluno_id: str, simulado_id: str) -> dict:
    """Questões erradas/em branco reais do aluno num simulado (dados do Canvas)."""
    resultado = questoes_do_aluno_no_simulado(cliente, aluno_id, simulado_id)
    if "erro" in resultado:
        return resultado
    if not resultado.get("temGabarito"):
        return {"erro": "Este simulado não tem detalhe por questão (não é um quiz sincronizado)."}
    if not resultado.get("temMinhasRespostas"):
        return {"erro": "As respostas do aluno neste simulado ainda não foram sincronizadas."}

    para_revisar = [
        {
            "posicao": q["posicao"],
            "resultado": q["resultado"],
            "assunto": q["assunto"],
            "enunciadoResumo": q["textoResumo"],
            "alternativaMarcada": q["alternativaMarcada"],
            "alternativaCorreta": q["alternativaCorreta"],
        }
        for q in resultado["questoes"]
        if q["resultado"] in ("errada", "em_branco")
    ]
    return {
        "totalQuestoes": resultado["totalQuestoes"],
        "acertos": resultado["acertos"],
        "erros": resultado["erros"],
        "emBranco": resultado["emBranco"],
        "paraRevisar": para_revisar,
    }


_SCHEMA_MINHAS_QUESTOES = {
    "name": "minhas_questoes_erradas",
    "description": (
        "Questões que o aluno errou ou deixou em branco num simulado, com o resumo "
        "do enunciado, a alternativa marcada e a correta. Use para 'o que devo "
        "revisar?'. Requer o simulado_id (descubra com minhas_notas)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "simulado_id": {"type": "string", "description": "id (UUID) do simulado."},
        },
        "required": ["simulado_id"],
    },
}


# ─── meu_insight_do_ciclo ─────────────────────────────────────────────────

def meu_insight_do_ciclo(cliente: Client, *, aluno_id: str) -> dict:
    """Bullets de insight do ciclo mais recente (cacheados em insight_aluno_ciclo)."""
    resultado = payload_insight_ciclo(cliente, aluno_id)
    if resultado is None:
        return {"erro": "O aluno ainda não tem notas em nenhum ciclo."}
    ciclo, stats_payload = resultado

    nome_resp = cliente.table("aluno").select("nome").eq("id", aluno_id).limit(1).execute()
    nome = (nome_resp.data or [{}])[0].get("nome") or ""

    bullets = gerar_para_aluno_ciclo(
        cliente,
        aluno_id=aluno_id,
        ciclo_id=ciclo["id"],
        stats_payload=stats_payload,
        contexto={"nomeAluno": nome},
    )
    return {"ciclo": ciclo["nome"], "bullets": bullets, "estatisticas": stats_payload}


_SCHEMA_MEU_INSIGHT = {
    "name": "meu_insight_do_ciclo",
    "description": (
        "Resumo de IA do ciclo mais recente do aluno (bullets) + as estatísticas "
        "individuais do ciclo (média própria vs turma, por matéria, streak)."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_MINHAS_NOTAS, minhas_notas),
    (_SCHEMA_MEU_DESEMPENHO, meu_desempenho_em_simulado),
    (_SCHEMA_MINHA_EVOLUCAO, minha_evolucao),
    (_SCHEMA_MEU_STREAK, meu_streak),
    (_SCHEMA_MINHAS_QUESTOES, minhas_questoes_erradas),
    (_SCHEMA_MEU_INSIGHT, meu_insight_do_ciclo),
]

SCHEMAS_ALUNO: list[dict[str, Any]] = [
    {"type": "function", "function": schema} for schema, _ in TOOLS
]

_HANDLERS: dict[str, Callable] = {schema["name"]: handler for schema, handler in TOOLS}


def executar_para_aluno(nome: str, cliente, args: dict, *, aluno_id: str) -> dict:
    """Despacha uma tool do aluno injetando o aluno_id do JWT.

    Qualquer `aluno_id` vindo do LLM é descartado — o aluno nunca consegue
    consultar dados de outra pessoa por aqui.
    """
    fn = _HANDLERS.get(nome)
    if fn is None:
        return {"erro": f"tool '{nome}' não existe"}
    args = dict(args or {})
    args.pop("aluno_id", None)
    try:
        return fn(cliente, aluno_id=aluno_id, **args)
    except TypeError as e:
        return {"erro": f"argumentos inválidos para '{nome}': {e}"}
    except Exception as e:  # noqa: BLE001
        return {"erro": f"erro ao executar '{nome}': {type(e).__name__}: {e}"}
