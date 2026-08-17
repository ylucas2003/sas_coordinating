"""Única função que fala com a API da OpenAI — usada pelos 3 passos de LLM
do pipeline (gerar rubrica, criticar rubrica, avaliar resposta). Mesmo
padrão de `api/app/stats/insights.py`: cliente síncrono instanciado por
chamada, saída forçada por JSON schema estrito.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

try:
    from openai import OpenAI

    _SDK_DISPONIVEL = True
except ImportError:
    _SDK_DISPONIVEL = False


class ErroLLM(Exception):
    """Levantado quando a chamada à LLM falha ou a resposta não pode ser lida."""


@dataclass
class RespostaLLM:
    dados: dict
    tokens_entrada: int
    tokens_saida: int
    modelo: str


def chamar_llm_json(
    *,
    api_key: str,
    modelo: str,
    mensagens: list[dict],
    nome_schema: str,
    schema: dict,
    max_tokens: int,
    temperatura: float = 0.0,
) -> RespostaLLM:
    """Chama a Chat Completions API pedindo saída em JSON schema estrito."""
    if not _SDK_DISPONIVEL:
        raise ErroLLM(
            "Pacote openai não instalado — rode "
            "`pip install -r grading_prototype/requirements.txt`."
        )
    if not api_key:
        raise ErroLLM("OPENAI_API_KEY não configurada (.env).")

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=modelo,
            max_tokens=max_tokens,
            temperature=temperatura,
            messages=mensagens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": nome_schema,
                    "strict": True,
                    "schema": schema,
                },
            },
        )
    except Exception as exc:
        log.exception("erro chamando LLM modelo=%s schema=%s", modelo, nome_schema)
        raise ErroLLM(f"Falha na chamada a {modelo} ({nome_schema}): {exc}") from exc

    escolha = response.choices[0]
    if escolha.finish_reason == "length":
        raise ErroLLM(
            f"Resposta de {modelo} para {nome_schema} foi TRUNCADA por "
            f"max_tokens ({max_tokens}) — aumente o limite em config.py. "
            f"JSON parcial descartado."
        )

    texto = escolha.message.content
    if not texto:
        raise ErroLLM(f"Resposta vazia de {modelo} para {nome_schema}.")

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErroLLM(f"JSON inválido de {modelo} para {nome_schema}: {exc}") from exc

    uso = response.usage
    return RespostaLLM(
        dados=dados,
        tokens_entrada=uso.prompt_tokens if uso else 0,
        tokens_saida=uso.completion_tokens if uso else 0,
        modelo=modelo,
    )
