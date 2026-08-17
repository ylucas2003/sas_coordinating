"""Orquestra a avaliação da resposta do aluno.

Desenho para funcionar com modelo barato:
1. A LLM responde só PERGUNTAS FACTUAIS por critério (evidências, método,
   resultado declarado, comparação com o esperado) — nunca escolhe veredito.
2. O veredito é derivado em código (pontuacao.derivar_veredito) — a política
   de correção fica determinística.
3. MICRO-ESCALONAMENTO assimétrico: o modelo barato pode conceder crédito
   integral sozinho, mas qualquer desconto ou sinal suspeito re-avalia SÓ
   aquele critério no modelo forte. Nota de aluno não desce sem confirmação
   do modelo forte.

O avaliador NUNCA recebe o gabarito (nem aceita o parâmetro) — a âncora
numérica vem dos `resultados_esperados` da rubrica.
"""

from __future__ import annotations

import json
import logging
import re

from . import config, pontuacao, prompts, schemas
from .cliente_llm import chamar_llm_json
from .dados import Questao
from .imagem import montar_bloco_imagem

log = logging.getLogger(__name__)


def _uso(resposta) -> dict:
    return {
        "modelo": resposta.modelo,
        "tokens_entrada": resposta.tokens_entrada,
        "tokens_saida": resposta.tokens_saida,
    }


def _montar_conteudo_usuario(
    questao: Questao,
    figura_data_url: str | None,
    criterios: list[dict],
    paginas_data_urls: list[str],
    resposta_texto: str | None,
) -> list[dict]:
    conteudo: list[dict] = [
        {"type": "text", "text": f"## Enunciado\n{questao.enunciado_texto}"},
    ]
    if figura_data_url is not None:
        conteudo.append(montar_bloco_imagem(figura_data_url))
    conteudo.append(
        {
            "type": "text",
            "text": (
                "## Rubrica de correção — avalie exatamente estes critérios por id\n"
                f"{json.dumps(criterios, ensure_ascii=False, separators=(',', ':'))}"
            ),
        }
    )
    if resposta_texto is not None:
        conteudo.append(
            {
                "type": "text",
                "text": f"## Resposta do aluno (transcrita)\n{resposta_texto}",
            }
        )
    if paginas_data_urls:
        conteudo.append(
            {"type": "text", "text": "## Resposta do aluno (fotos, na ordem das páginas)"}
        )
        for data_url in paginas_data_urls:
            conteudo.append(montar_bloco_imagem(data_url))
    conteudo.append(
        {
            "type": "text",
            "text": (
                "Emita um item de avaliação para CADA critério da rubrica, sem "
                "omitir nem repetir nenhum id. Responda apenas no schema pedido."
            ),
        }
    )
    return conteudo


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", "", (texto or "").lower())


def _confere_verificavel_textualmente(
    declarado: str, resultados_esperados: list[str]
) -> bool:
    """Um 'confere' do modelo barato só dispensa confirmação se o valor
    declarado pelo aluno bate TEXTUALMENTE com alguma forma esperada
    (substring em qualquer direção, normalizado). Formas diferentes do mesmo
    valor existem — mas aí o correto era 'equivalente_em_outra_forma', que
    escala por conta própria. 'confere' não-verificável é o esconderijo
    clássico da leniência do modelo barato (ex: declarou 2±√6i, esperado
    1±2i, e ele disse 'confere')."""
    declarado_norm = _normalizar(declarado)
    if not declarado_norm:
        return False
    for esperado in resultados_esperados:
        esperado_norm = _normalizar(esperado)
        if declarado_norm in esperado_norm or esperado_norm in declarado_norm:
            return True
    return False


def _gatilhos_de_escalonamento(item: dict, criterio: dict) -> list[str]:
    """Sinais determinísticos de que o veredito do modelo barato precisa de
    confirmação do modelo forte para valer."""
    gatilhos = []

    if item["veredito"] != "atendido":
        # Assimetria deliberada: desconto de nota exige confirmação.
        gatilhos.append(f"veredito_{item['veredito']}")

    if item.get("comparacao_resultado") == "equivalente_em_outra_forma":
        # Equivalência algébrica é onde modelos baratos mais se enganam
        # (nas duas direções) — confirma antes de aceitar.
        gatilhos.append("equivalencia_alegada")

    esperadas = set(criterio.get("evidencias_esperadas", []))
    if any(ev in esperadas for ev in item.get("evidencias_encontradas", [])):
        gatilhos.append("evidencia_copiada_da_rubrica")

    resultados_esperados = criterio.get("resultados_esperados", [])
    comparacao = item.get("comparacao_resultado")

    if (
        comparacao == "confere"
        and resultados_esperados
        and not _confere_verificavel_textualmente(
            item.get("resultado_declarado_pelo_aluno", ""), resultados_esperados
        )
    ):
        gatilhos.append("confere_nao_verificavel_textualmente")

    if resultados_esperados and comparacao == "sem_resultado_esperado":
        # O critério TEM resultado esperado mas o avaliador barato disse que
        # não há — contradição objetiva (extração preguiçosa); confirma.
        gatilhos.append("comparacao_contradiz_rubrica")

    return gatilhos


def _derivar_vereditos(avaliacao: dict) -> dict:
    for item in avaliacao.get("avaliacoes_por_criterio", []):
        item["veredito"] = pontuacao.derivar_veredito(item)
    return avaliacao


def avaliar_resposta(
    *,
    api_key: str,
    modelo: str,
    questao: Questao,
    figura_data_url: str | None,
    rubrica_final: dict,
    paginas_data_urls: list[str] = (),
    resposta_texto: str | None = None,
) -> tuple[dict, dict]:
    """Avaliação de todos os critérios em UMA chamada (um modelo).

    Devolve `(avaliacao, uso)`. Cada item da avaliação sai com `veredito`
    derivado em código a partir das respostas factuais da LLM.
    """
    if not paginas_data_urls and not resposta_texto:
        raise ValueError(
            "avaliar_resposta precisa de paginas_data_urls ou resposta_texto."
        )

    criterios = rubrica_final["criterios"]
    conteudo = _montar_conteudo_usuario(
        questao, figura_data_url, criterios, paginas_data_urls, resposta_texto
    )
    mensagens = [
        {"role": "system", "content": prompts.PROMPT_AVALIAR_RESPOSTA},
        {"role": "user", "content": conteudo},
    ]
    resposta = chamar_llm_json(
        api_key=api_key,
        modelo=modelo,
        mensagens=mensagens,
        nome_schema="AvaliacaoRespostaAluno",
        schema=schemas.schema_avaliacao_para([c["id"] for c in criterios]),
        max_tokens=config.MAX_TOKENS_AVALIACAO,
        temperatura=config.TEMPERATURA,
    )
    return _derivar_vereditos(resposta.dados), _uso(resposta)


def _reavaliar_criterio(
    *,
    api_key: str,
    modelo: str,
    questao: Questao,
    figura_data_url: str | None,
    criterio: dict,
    paginas_data_urls: list[str],
    resposta_texto: str | None,
) -> tuple[dict, dict]:
    """Re-avalia UM critério no modelo forte (micro-escalonamento)."""
    conteudo = _montar_conteudo_usuario(
        questao, figura_data_url, [criterio], paginas_data_urls, resposta_texto
    )
    mensagens = [
        {"role": "system", "content": prompts.PROMPT_AVALIAR_UM_CRITERIO},
        {"role": "user", "content": conteudo},
    ]
    resposta = chamar_llm_json(
        api_key=api_key,
        modelo=modelo,
        mensagens=mensagens,
        nome_schema="AvaliacaoUmCriterio",
        schema=schemas.schema_avaliacao_para([criterio["id"]]),
        max_tokens=config.MAX_TOKENS_AVALIACAO,
        temperatura=config.TEMPERATURA,
    )
    avaliacao = _derivar_vereditos(resposta.dados)
    itens = avaliacao.get("avaliacoes_por_criterio", [])
    if not itens:
        raise ValueError(f"Escalonamento do critério {criterio['id']} voltou vazio.")
    return itens[0], _uso(resposta)


def avaliar_com_escalonamento(
    *,
    api_key: str,
    modelo_barato: str,
    modelo_forte: str | None,
    questao: Questao,
    figura_data_url: str | None,
    rubrica_final: dict,
    paginas_data_urls: list[str] = (),
    resposta_texto: str | None = None,
) -> tuple[dict, dict, list[dict]]:
    """Fluxo de dois níveis: avalia tudo no modelo barato; critérios com
    gatilho (qualquer desconto, equivalência alegada, evidência copiada,
    'confere' suspeito) são re-avaliados individualmente no modelo forte,
    cujo item substitui o do barato.

    Devolve `(avaliacao, uso, escalonamentos)` — `escalonamentos` lista
    {criterio_id, gatilhos, veredito_barato, veredito_final}.
    """
    avaliacao, uso_base = avaliar_resposta(
        api_key=api_key,
        modelo=modelo_barato,
        questao=questao,
        figura_data_url=figura_data_url,
        rubrica_final=rubrica_final,
        paginas_data_urls=paginas_data_urls,
        resposta_texto=resposta_texto,
    )
    uso = {"avaliacao_barata": uso_base}

    if not modelo_forte or modelo_forte == modelo_barato:
        return avaliacao, uso, []

    criterios_por_id = {c["id"]: c for c in rubrica_final["criterios"]}
    escalonamentos: list[dict] = []

    for indice, item in enumerate(avaliacao.get("avaliacoes_por_criterio", [])):
        criterio = criterios_por_id.get(item["criterio_id"])
        if criterio is None:
            continue
        gatilhos = _gatilhos_de_escalonamento(item, criterio)
        if not gatilhos:
            continue

        log.info(
            "escalonando criterio %s (%s) para %s",
            item["criterio_id"], ",".join(gatilhos), modelo_forte,
        )
        item_forte, uso_criterio = _reavaliar_criterio(
            api_key=api_key,
            modelo=modelo_forte,
            questao=questao,
            figura_data_url=figura_data_url,
            criterio=criterio,
            paginas_data_urls=paginas_data_urls,
            resposta_texto=resposta_texto,
        )
        uso[f"escalonamento_{item['criterio_id']}"] = uso_criterio
        escalonamentos.append(
            {
                "criterio_id": item["criterio_id"],
                "gatilhos": gatilhos,
                "veredito_barato": item["veredito"],
                "veredito_final": item_forte["veredito"],
            }
        )
        avaliacao["avaliacoes_por_criterio"][indice] = item_forte

    return avaliacao, uso, escalonamentos
