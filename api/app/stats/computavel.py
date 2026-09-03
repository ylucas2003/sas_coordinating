"""Quais notas entram na conta — e por que algumas não entram.

A medição contra produção (docs/32 §1.1) achou 2.756 notas com `pontuacao = 0`
e `presente = true`. Entre as 284 em que dá para olhar por dentro — as de prova
que era quiz, com as respostas gravadas —, **122 não têm nenhuma alternativa
marcada**. O aluno abriu a prova e não respondeu: é ausência escrita como nota.

A fração média de questões em branco é **0,0033** entre as notas maiores que
zero e **0,4959** entre os zeros. Cento e cinquenta vezes. O sinal é forte, mas
a regra aqui é deliberadamente ESTREITA: só marca quem não respondeu NADA.
Quem respondeu tudo e errou tudo tirou zero, e o zero conta.

⚠️ O que este módulo NÃO faz, e é o principal:

  - **Não apaga nada.** A regra anterior (`limpar_zeros_provaveis_ausencias`)
    inferia ausência de "2+ zeros no mesmo dia" e escrevia `presente = false,
    pontuacao = null` por cima do fato do Canvas. Em produção ela pega 414
    células; onde dá para conferir, **73 confirmam e 12 contradizem — 14% de
    erro** —, e em 329 delas não há como conferir. Um proxy que erra 14% no
    verificável e opera às cegas em 79% dos casos não é regra, é dano.
  - **Não julga prova sem dado de questão.** Fase 2, Redação e discursiva não
    têm evidência por aluno; ali o zero conta e a tela diz que não há como
    distinguir. Um zero em Redação é nota de verdade com muito mais frequência
    que um zero em Matemática objetiva.
  - **Não infere por prova.** Aquilo é o Problema B, e a decisão é sobre a
    prova inteira (`simulado.nota_confiavel`), tomada à mão.

⚠️ **ORDEM.** A evidência mora em `questao_resposta_aluno`, que o sync popula
DEPOIS da nota. Chamar isto antes das respostas chegarem classifica todo mundo
como computável e some com o efeito **sem erro nenhum** — falha silenciosa, a
mais provável do sprint. Tem teste próprio.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from supabase import Client

log = logging.getLogger("sas.stats.computavel")

#: O motivo, hoje único. A coluna é texto para a próxima regra não precisar de
#: migration — não para virar campo livre.
TODAS_EM_BRANCO = "todas_em_branco"

#: Balde sintético do Quiz Statistics que significa "deixou em branco".
#: `other` (marcou fora das alternativas) NÃO conta como branco: é resposta,
#: só que numa alternativa que não existe mais.
BALDE_EM_BRANCO = "none"

#: Teto por consulta ao PostgREST. Não há paginação em lugar nenhum do projeto
#: (armadilha 2 do CLAUDE.md) e `questao_resposta_aluno` é a maior tabela do
#: banco — um `in_` com milhares de ids vira URL que o servidor recusa.
LOTE = 200


def _em_lotes(itens: list[str], tamanho: int = LOTE) -> Iterable[list[str]]:
    for i in range(0, len(itens), tamanho):
        yield itens[i : i + tamanho]


def decidir(respostas: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """A regra, pura: esta nota entra na conta?

    `respostas` são as linhas de `questao_resposta_aluno` daquele aluno naquele
    simulado. Devolve `(computavel, motivo)`.
    """
    # Sem evidência não se conclui nada. Prova que não era quiz cai aqui, e é
    # o caso da maioria — 89,7% dos zeros não têm dado de questão.
    if not respostas:
        return True, None

    for r in respostas:
        if r.get("alternativa_id") is not None:
            return True, None
        # Alternativa nula por `other` é resposta, não branco. Linha antiga,
        # gravada antes da 0043, tem o balde nulo: aí o legado é tratado como
        # branco, que é o que ele significava quando foi escrito.
        balde = r.get("balde_sem_alternativa")
        if balde is not None and balde != BALDE_EM_BRANCO:
            return True, None

    return False, TODAS_EM_BRANCO


def avaliar_computavel(cliente: Client, *, simulado_ids: list[str]) -> int:
    """Reavalia `nota.computavel` dos simulados dados. Devolve quantas mudaram.

    Idempotente e nos DOIS sentidos: uma nota que deixou de se encaixar na
    regra volta a ser computável sozinha. Sem isso, corrigir a evidência não
    corrigiria a conclusão, e o banco acumularia veredictos de uma regra que
    não vale mais.
    """
    if not simulado_ids:
        return 0

    questao_para_simulado = _mapear_questoes(cliente, simulado_ids)
    if not questao_para_simulado:
        # Nenhum dos simulados é quiz: não há evidência para ninguém, e a
        # única coisa a fazer é desmarcar quem porventura estivesse marcado.
        return _aplicar(cliente, simulado_ids, {})

    respostas = _carregar_respostas(cliente, list(questao_para_simulado))

    # (aluno, simulado) → as respostas daquele aluno naquela prova.
    por_aluno_simulado: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in respostas:
        simulado_id = questao_para_simulado.get(r["questao_id"])
        if simulado_id is None:
            continue
        por_aluno_simulado[(r["aluno_id"], simulado_id)].append(r)

    veredictos = {
        chave: decidir(linhas) for chave, linhas in por_aluno_simulado.items()
    }
    return _aplicar(cliente, simulado_ids, veredictos)


def _mapear_questoes(cliente: Client, simulado_ids: list[str]) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for lote in _em_lotes(simulado_ids):
        resp = (
            cliente.table("questao")
            .select("id, simulado_id")
            .in_("simulado_id", lote)
            .execute()
        )
        for linha in resp.data or []:
            mapa[linha["id"]] = linha["simulado_id"]
    return mapa


def _carregar_respostas(cliente: Client, questao_ids: list[str]) -> list[dict]:
    linhas: list[dict] = []
    for lote in _em_lotes(questao_ids):
        resp = (
            cliente.table("questao_resposta_aluno")
            .select("aluno_id, questao_id, alternativa_id, balde_sem_alternativa")
            .in_("questao_id", lote)
            .execute()
        )
        linhas.extend(resp.data or [])
    return linhas


def _aplicar(
    cliente: Client,
    simulado_ids: list[str],
    veredictos: dict[tuple[str, str], tuple[bool, str | None]],
) -> int:
    """Escreve só o que mudou de estado."""
    mudancas = 0
    for lote in _em_lotes(simulado_ids):
        resp = (
            cliente.table("nota")
            .select("aluno_id, simulado_id, pontuacao, presente, computavel")
            .in_("simulado_id", lote)
            .execute()
        )
        for linha in resp.data or []:
            chave = (linha["aluno_id"], linha["simulado_id"])
            computavel, motivo = veredictos.get(chave, (True, None))

            # A regra só fala de ZERO com presença afirmada. Nota positiva e
            # ausência declarada não são assunto dela — e "todas em branco"
            # com nota acima de zero seria contradição do Canvas, não nossa.
            if computavel is False and not _e_zero_presente(linha):
                computavel, motivo = True, None

            if bool(linha.get("computavel", True)) == computavel:
                continue

            (
                cliente.table("nota")
                .update({"computavel": computavel, "motivo_nao_computavel": motivo})
                .eq("aluno_id", linha["aluno_id"])
                .eq("simulado_id", linha["simulado_id"])
                .execute()
            )
            mudancas += 1

    if mudancas:
        log.info("computavel: %d nota(s) mudaram de estado", mudancas)
    return mudancas


def _e_zero_presente(linha: dict) -> bool:
    if not linha.get("presente"):
        return False
    try:
        return float(linha.get("pontuacao") or 0) == 0.0
    except (TypeError, ValueError):
        return False
