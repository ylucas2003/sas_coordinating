"""Orquestra a geração da rubrica em 2 passos: gerar e criticar/reescrever.

`rubrica_final.criterios` (formato canônico, sem os campos de bookkeeping da
crítica) é o que segue para `avaliador.py` e `pontuacao.py`. O pacote
devolvido inclui `uso` (tokens por etapa) para rastreio de custo.
"""

from __future__ import annotations

import json

from . import config, prompts, schemas
from .cliente_llm import RespostaLLM, chamar_llm_json
from .dados import Questao
from .imagem import montar_bloco_imagem

_CAMPOS_CANONICOS_CRITERIO = (
    "id",
    "pontuacao",
    "objetivo_pedagogico",
    "evidencias_esperadas",
    "resultados_esperados",
    "metodos_alternativos_aceitos",
    "erros_comuns",
)


def _uso_da_resposta(resposta: RespostaLLM) -> dict:
    return {
        "modelo": resposta.modelo,
        "tokens_entrada": resposta.tokens_entrada,
        "tokens_saida": resposta.tokens_saida,
    }


def gerar_rubrica_inicial(
    *, api_key: str, modelo: str, questao: Questao, figura_data_url: str | None
) -> RespostaLLM:
    texto_usuario = (
        f"## Enunciado\n{questao.enunciado_texto}\n\n"
        f"## Solução oficial (gabarito)\n{questao.gabarito_texto}"
    )
    conteudo: list[dict] = [{"type": "text", "text": texto_usuario}]
    if figura_data_url is not None:
        conteudo.append(montar_bloco_imagem(figura_data_url))
    mensagens = [
        {"role": "system", "content": prompts.PROMPT_GERAR_RUBRICA},
        {"role": "user", "content": conteudo},
    ]
    return chamar_llm_json(
        api_key=api_key,
        modelo=modelo,
        mensagens=mensagens,
        nome_schema="RubricaInicial",
        schema=schemas.SCHEMA_RUBRICA,
        max_tokens=config.MAX_TOKENS_RUBRICA,
        temperatura=config.TEMPERATURA,
    )


def criticar_e_reescrever_rubrica(
    *,
    api_key: str,
    modelo: str,
    questao: Questao,
    figura_data_url: str | None,
    rubrica_inicial: dict,
) -> RespostaLLM:
    texto_usuario = (
        f"## Enunciado\n{questao.enunciado_texto}\n\n"
        f"## Solução oficial (gabarito)\n{questao.gabarito_texto}\n\n"
        f"## Rubrica gerada (a revisar)\n"
        f"{json.dumps(rubrica_inicial, ensure_ascii=False, indent=2)}"
    )
    conteudo: list[dict] = [{"type": "text", "text": texto_usuario}]
    if figura_data_url is not None:
        conteudo.append(montar_bloco_imagem(figura_data_url))
    mensagens = [
        {"role": "system", "content": prompts.PROMPT_CRITICAR_RUBRICA},
        {"role": "user", "content": conteudo},
    ]
    return chamar_llm_json(
        api_key=api_key,
        modelo=modelo,
        mensagens=mensagens,
        nome_schema="RubricaCriticada",
        schema=schemas.SCHEMA_RUBRICA_CRITICADA,
        max_tokens=config.MAX_TOKENS_CRITICA,
        temperatura=config.TEMPERATURA,
    )


def _limpar_criterios_para_avaliacao(criterios_criticados: list[dict]) -> list[dict]:
    """Remove os campos de bookkeeping da crítica (foi_reescrito/motivo_alteracao),
    deixando só o formato canônico usado pelo avaliador e pelo motor de nota."""
    return [
        {campo: c[campo] for campo in _CAMPOS_CANONICOS_CRITERIO}
        for c in criterios_criticados
    ]


def gerar_rubrica_final(
    *, api_key: str, modelo: str, questao: Questao, figura_data_url: str | None
) -> dict:
    """Roda os 2 passos e devolve o pacote completo: rubrica inicial, final,
    o que mudou e o uso de tokens por etapa."""
    resposta_inicial = gerar_rubrica_inicial(
        api_key=api_key, modelo=modelo, questao=questao, figura_data_url=figura_data_url
    )
    rubrica_inicial = resposta_inicial.dados

    resposta_critica = criticar_e_reescrever_rubrica(
        api_key=api_key,
        modelo=modelo,
        questao=questao,
        figura_data_url=figura_data_url,
        rubrica_inicial=rubrica_inicial,
    )
    rubrica_criticada = resposta_critica.dados

    criterios_finais = _limpar_criterios_para_avaliacao(rubrica_criticada["criterios"])

    return {
        "rubrica_inicial": rubrica_inicial,
        "rubrica_final": {"criterios": criterios_finais},
        "alteracoes": {
            "resumo_geral": rubrica_criticada["resumo_geral"],
            "por_criterio": [
                {
                    "id": c["id"],
                    "foi_reescrito": c["foi_reescrito"],
                    "motivo_alteracao": c["motivo_alteracao"],
                }
                for c in rubrica_criticada["criterios"]
            ],
        },
        "uso": {
            "gerar_rubrica": _uso_da_resposta(resposta_inicial),
            "criticar_rubrica": _uso_da_resposta(resposta_critica),
        },
    }
