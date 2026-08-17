"""Fluxo comum aos CLIs: carregar questão → encodar imagens → obter rubrica
(persistida ou gerada) → avaliar → nota.

Rubrica persistida (`rubrica.json` na pasta da questão): garante que todos
os alunos da mesma questão sejam corrigidos pela MESMA rubrica (justiça) e
evita pagar as 2 chamadas de geração por aluno. O arquivo é editável à mão
— quem revisar seta `"revisada_por_humano": true`. Se o gabarito mudar
depois da geração, o hash diverge e o pipeline avisa.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from . import config, dados, pontuacao, prompts
from .avaliador import avaliar_com_escalonamento
from .dados import Questao
from .imagem import carregar_imagem_base64
from .rubrica import gerar_rubrica_final

log = logging.getLogger(__name__)

ARQUIVO_RUBRICA = "rubrica.json"


def _hash_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def hash_prompts() -> str:
    """Identifica a versão dos prompts usada — muda quando qualquer prompt muda."""
    return _hash_texto(
        prompts.PROMPT_GERAR_RUBRICA
        + prompts.PROMPT_CRITICAR_RUBRICA
        + prompts.PROMPT_AVALIAR_RESPOSTA
    )


def metadados_execucao(modelo: str) -> dict:
    return {
        "modelo": modelo,
        "temperatura": config.TEMPERATURA,
        "hash_prompts": hash_prompts(),
        "executado_em": datetime.now().isoformat(timespec="seconds"),
    }


def preparar_questao(pasta_questao: Path) -> tuple[Questao, str | None]:
    """Carrega a questão e encoda a figura do enunciado (se houver)."""
    questao = dados.carregar_questao(pasta_questao)
    figura_data_url = (
        carregar_imagem_base64(questao.caminho_figura)
        if questao.caminho_figura is not None
        else None
    )
    return questao, figura_data_url


def obter_rubrica(
    pasta_questao: Path,
    questao: Questao,
    figura_data_url: str | None,
    *,
    api_key: str,
    modelo: str,
    regerar: bool = False,
) -> dict:
    """Carrega `rubrica.json` da pasta da questão se existir; senão gera
    (2 chamadas LLM) e SALVA — o próximo aluno da mesma questão reusa.

    Devolve {"rubrica_final", "origem" ('persistida'|'gerada'),
    "revisada_por_humano", "modelo_gerador", "uso"} (+ "rubrica_inicial" e
    "alteracoes" quando gerada nesta chamada).
    """
    caminho = pasta_questao / ARQUIVO_RUBRICA
    hash_gabarito = _hash_texto(questao.gabarito_texto)

    if caminho.is_file() and not regerar:
        salvo = json.loads(caminho.read_text(encoding="utf-8"))
        if salvo.get("hash_gabarito") != hash_gabarito:
            log.warning(
                "rubrica.json de %s foi gerada para OUTRA versão do gabarito "
                "(hash divergente) — considere regenerar com --regerar-rubrica.",
                pasta_questao.name,
            )
        return {
            "rubrica_final": {"criterios": salvo["criterios"]},
            "origem": "persistida",
            "revisada_por_humano": bool(salvo.get("revisada_por_humano", False)),
            "modelo_gerador": salvo.get("modelo"),
            "uso": {},
        }

    pacote = gerar_rubrica_final(
        api_key=api_key, modelo=modelo, questao=questao, figura_data_url=figura_data_url
    )
    persistido = {
        "criterios": pacote["rubrica_final"]["criterios"],
        "modelo": modelo,
        "gerada_em": datetime.now().isoformat(timespec="seconds"),
        "hash_gabarito": hash_gabarito,
        "hash_prompts": hash_prompts(),
        "revisada_por_humano": False,
        # Trilha de auditoria da geração — o que a crítica mudou e a versão pré-crítica.
        "alteracoes": pacote["alteracoes"],
        "rubrica_inicial": pacote["rubrica_inicial"],
    }
    caminho.write_text(
        json.dumps(persistido, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("rubrica.json salva em %s (edite à mão para revisar).", caminho)

    return {
        "rubrica_final": pacote["rubrica_final"],
        "rubrica_inicial": pacote["rubrica_inicial"],
        "alteracoes": pacote["alteracoes"],
        "origem": "gerada",
        "revisada_por_humano": False,
        "modelo_gerador": modelo,
        "uso": pacote["uso"],
    }


def corrigir_questao(
    pasta_questao: Path,
    aluno_id: str,
    *,
    api_key: str,
    modelo_avaliador: str,
    modelo_escalonamento: str | None = None,
    modelo_rubrica: str = config.MODELO_RUBRICA,
    regerar_rubrica: bool = False,
) -> dict:
    """Pipeline completo de UMA questão para UM aluno: rubrica (persistida ou
    gerada) → avaliação com escalonamento → nota. Devolve o resultado rico
    usado nos relatórios."""
    questao, figura_data_url = preparar_questao(pasta_questao)
    resposta_aluno = dados.carregar_resposta_aluno(pasta_questao, aluno_id)
    paginas_data_urls = [
        carregar_imagem_base64(p) for p in resposta_aluno.caminhos_paginas
    ]

    rubrica = obter_rubrica(
        pasta_questao,
        questao,
        figura_data_url,
        api_key=api_key,
        modelo=modelo_rubrica,
        regerar=regerar_rubrica,
    )

    avaliacao, uso_avaliacao, escalonamentos = avaliar_com_escalonamento(
        api_key=api_key,
        modelo_barato=modelo_avaliador,
        modelo_forte=modelo_escalonamento,
        questao=questao,
        figura_data_url=figura_data_url,
        rubrica_final=rubrica["rubrica_final"],
        paginas_data_urls=paginas_data_urls,
        resposta_texto=resposta_aluno.resposta_texto,
    )
    nota = pontuacao.calcular_nota(rubrica["rubrica_final"], avaliacao)

    resultado = {
        "rubrica_final": rubrica["rubrica_final"],
        "rubrica_origem": rubrica["origem"],
        "rubrica_revisada_por_humano": rubrica["revisada_por_humano"],
        "avaliacao": avaliacao,
        "escalonamentos": escalonamentos,
        "nota": nota,
        "uso": {**rubrica["uso"], **uso_avaliacao},
    }
    if "alteracoes" in rubrica:
        resultado["alteracoes"] = rubrica["alteracoes"]
        resultado["rubrica_inicial"] = rubrica["rubrica_inicial"]
    if resposta_aluno.nota_humana is not None:
        resultado["nota_humana"] = resposta_aluno.nota_humana
        resultado["comparacao"] = pontuacao.comparar_com_nota_humana(
            nota["nota_final"], resposta_aluno.nota_humana
        )
    return resultado
