"""Insight de IA individual do aluno por ciclo (card do painel do aluno).

Espelha o padrão de insights.py (insight de ciclo da coordenação): cache em
`insight_aluno_ciclo` chaveado por (aluno_id, ciclo_id, hash_payload) — os
números mudam → hash muda → regenera. Falha graciosamente para [] sem
OPENAI_API_KEY ou sem o SDK.

Modelo: gpt-4o-mini (settings.openai_modelo_insights), Structured Outputs strict.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from supabase import Client

from ..config import get_settings
from .insights import MAX_TOKENS, N_BULLETS_MAX, SCHEMA_SAIDA, _disponivel
from .utils import hash_payload_estavel

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # _disponivel() já cobre a ausência do SDK

log = logging.getLogger("sas.stats.insight_aluno")


PROMPT_ALUNO = """Você é um mentor de estudos do Colégio Ari de Sá falando DIRETAMENTE COM O ALUNO sobre o desempenho dele no ciclo de simulados ITA/IME.

# Estilo OBRIGATÓRIO

- Gere de 3 a 5 bullets, cada um com no máximo 22 palavras.
- Fale em 2ª pessoa ("você subiu", "priorize"), tom encorajador e concreto — sem falsa positividade.
- TRADUZA números em ação:
  · SIM: "Matemática subiu 0,7 desde o ciclo passado — continue no ritmo."
  · SIM: "Inglês está 0,8 abaixo do corte eliminatório de 5,0 — priorize esta semana."
  · NÃO: jargão estatístico de qualquer tipo.
- Compare apenas com AGREGADOS da turma (média da turma) — NUNCA cite ou estime colegas.
- Se houver dados do ciclo anterior, faça pelo menos um bullet comparativo.
- Sempre feche com um bullet de próximo passo prático.

# Contexto do domínio

Notas 0–10. Cortes: 4,0 por matéria; 5,0 só para Inglês na Fase 1 do ITA (única eliminatória).
Streak = ciclos consecutivos com a média do aluno acima da média da turma.

Devolva exclusivamente JSON no schema."""


def gerar_para_aluno_ciclo(
    cliente_db: Client,
    *,
    aluno_id: str,
    ciclo_id: str,
    stats_payload: dict[str, Any],
    contexto: dict[str, Any],
) -> list[str]:
    """Devolve bullets do insight individual (aluno × ciclo), com cache."""
    hash_p = hash_payload_estavel({"stats": stats_payload, "ctx": contexto})

    cache = _consultar_cache(cliente_db, aluno_id, ciclo_id, hash_p)
    if cache is not None:
        return cache

    settings = get_settings()
    if not _disponivel(settings.openai_api_key):
        log.info("openai indisponível — pulando insight do aluno")
        return []

    try:
        bullets = _chamar_llm(
            api_key=settings.openai_api_key,
            modelo=settings.openai_modelo_insights,
            stats_payload=stats_payload,
            contexto=contexto,
        )
    except Exception:
        log.exception("erro gerando insight aluno=%s ciclo=%s", aluno_id, ciclo_id)
        return []

    _salvar_cache(
        cliente_db,
        aluno_id=aluno_id,
        ciclo_id=ciclo_id,
        hash_payload=hash_p,
        bullets=bullets,
        modelo=settings.openai_modelo_insights,
    )
    return bullets


def _chamar_llm(
    *,
    api_key: str,
    modelo: str,
    stats_payload: dict,
    contexto: dict,
) -> list[str]:
    client = OpenAI(api_key=api_key)
    user_payload = json.dumps(
        {"contexto": contexto, "estatisticas": stats_payload},
        ensure_ascii=False,
        indent=2,
    )
    response = client.chat.completions.create(
        model=modelo,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": PROMPT_ALUNO},
            {
                "role": "user",
                "content": (
                    "Gere os bullets para o aluno abaixo. Compare com o ciclo "
                    "anterior quando houver dados.\n\n"
                    f"{user_payload}"
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "InsightAlunoCiclo",
                "strict": True,
                "schema": SCHEMA_SAIDA,
            },
        },
    )

    texto = response.choices[0].message.content
    if not texto:
        return []
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        log.warning("LLM devolveu JSON inválido (insight aluno): %s", texto[:200])
        return []

    bullets = [b for b in dados.get("bullets") or [] if isinstance(b, str) and b.strip()]
    return bullets[:N_BULLETS_MAX]


def _consultar_cache(
    cliente: Client, aluno_id: str, ciclo_id: str, hash_payload: str
) -> list[str] | None:
    resp = (
        cliente.table("insight_aluno_ciclo")
        .select("bullets")
        .eq("aluno_id", aluno_id)
        .eq("ciclo_id", ciclo_id)
        .eq("hash_payload", hash_payload)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    bullets = resp.data[0].get("bullets")
    return bullets if isinstance(bullets, list) else []


def _salvar_cache(
    cliente: Client,
    *,
    aluno_id: str,
    ciclo_id: str,
    hash_payload: str,
    bullets: list[str],
    modelo: str,
) -> None:
    if not bullets:
        return
    cliente.table("insight_aluno_ciclo").upsert(
        {
            "aluno_id": aluno_id,
            "ciclo_id": ciclo_id,
            "hash_payload": hash_payload,
            "bullets": bullets,
            "modelo": modelo,
        },
        on_conflict="aluno_id,ciclo_id,hash_payload",
    ).execute()
