"""Insight de IA individual do aluno por ciclo (card do painel do aluno).

Espelha o padrão de insights.py (insight de ciclo da coordenação): cache em
`insight_aluno_ciclo` chaveado por (aluno_id, ciclo_id, hash_payload) — os
números mudam → hash muda → regenera. Falha graciosamente para [] sem
OPENAI_API_KEY ou sem o SDK.

⚠️ O TEXTO que vai ao modelo também entra no hash (`_chave_do_cache`), e não só
os números. Até 25/10 a chave era `{stats, ctx}`: o prompt foi corrigido — sem
corte cravado, sem a "streak" de ciclos acima da média — e os bullets velhos
continuavam saindo do cache enquanto os números do ciclo não mudassem, o que,
num ciclo fechado, é para sempre.

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
  · SIM: "Química ficou 0,8 abaixo da média da turma neste ciclo — priorize esta semana."
  · NÃO: jargão estatístico de qualquer tipo.
- Compare apenas com AGREGADOS da turma (média da turma) — NUNCA cite ou estime colegas.
- Se houver dados do ciclo anterior, faça pelo menos um bullet comparativo.
- Sempre feche com um bullet de próximo passo prático.

# Contexto do domínio

Notas 0–10.
Cortes: NÃO estão nestas estatísticas e mudam com a régua do aluno (o vestibular-alvo). Não cite número de corte nem diga que alguma matéria está acima ou abaixo do corte, nem que é eliminatória.
Sequência = quantos simulados SEGUIDOS o aluno fez sem faltar — é presença, não nota. Ela não está nestas estatísticas: não fale de sequência.
`ciclosAcimaDaMediaDaTurma` NÃO é a sequência: é quantos ciclos seguidos a média do aluno ficou acima da média da turma. Se usar, diga exatamente isso.
`mediaTurma` null = a turma era pequena demais para comparar sem expor colegas. Não compare essa matéria com a turma nem estime a média dela.

Devolva exclusivamente JSON no schema."""

#: O pedido da mensagem do usuário, antes do JSON. Constante, e não literal
#: dentro de `_chamar_llm`, para entrar na chave do cache junto do prompt.
PEDIDO_AO_MODELO = (
    "Gere os bullets para o aluno abaixo. Compare com o ciclo anterior quando houver dados."
)


def _chave_do_cache(stats_payload: dict[str, Any], contexto: dict[str, Any]) -> str:
    """O hash de tudo que decide o texto: os números, o contexto e as instruções.

    O prompt vai INTEIRO no hash, e não um número de versão: versão à mão é a
    que alguém esquece de subir, e o defeito voltaria calado. O custo de mexer
    numa vírgula do prompt é regenerar os bullets de quem abrir a tela — uma
    chamada do gpt-4o-mini por aluno × ciclo.
    """
    return hash_payload_estavel(
        {
            "prompt": {"sistema": PROMPT_ALUNO, "pedido": PEDIDO_AO_MODELO},
            "stats": stats_payload,
            "ctx": contexto,
        }
    )


def gerar_para_aluno_ciclo(
    cliente_db: Client,
    *,
    aluno_id: str,
    ciclo_id: str,
    stats_payload: dict[str, Any],
    contexto: dict[str, Any],
) -> list[str]:
    """Devolve bullets do insight individual (aluno × ciclo), com cache."""
    hash_p = _chave_do_cache(stats_payload, contexto)

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
            {"role": "user", "content": f"{PEDIDO_AO_MODELO}\n\n{user_payload}"},
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
