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
  - **Não decide sozinho quais provas são exceção.** A lista de
    `simulado.zero_e_ausencia` é ligada à mão (migration 0046). Não há
    detector: o critério que achou as oito de 2023 — pico em zero com vale ao
    lado, prova irmã do mesmo dia com contagem incompatível — é forte para um
    humano ler e fraco para uma máquina aplicar.

─── As DUAS evidências, e por que a segunda existe ──────────────────────

  A) **Por aluno** (`todas_em_branco`): ele abriu o quiz e não marcou nada.
     Direta, verificável, 122 células em produção.
  B) **Por prova** (`zero_por_falta_lancada`): naquela prova o professor
     lançou 0 para quem faltou. São oito provas de 2023 — 71% de todos os
     zeros do sistema —, nenhuma delas quiz, e por isso invisíveis para a
     evidência (A). O que as autoriza é a contagem da prova irmã do mesmo dia:
     em seis das oito, o número de alunos acima de zero bate com quantos
     alunos a irmã avaliou, dentro de 1% a 7% (docs/32 §1.4).

  A (A) é mais específica e ganha quando as duas se aplicam. Na prática elas
  não colidem: as oito provas de (B) não têm dado de questão nenhum.

  ⚠️ (B) marca a NOTA, não a prova. A prova continua entrando na média — com
  a média de quem de fato a fez. Isso é diferente de `simulado.nota_confiavel`,
  que tira a prova inteira do agregado e existe para o caso, ainda não
  observado, de uma prova de fato inutilizável.

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

#: Os dois motivos. A coluna é texto para a próxima regra não precisar de
#: migration — não para virar campo livre.
#:
#: `TODAS_EM_BRANCO` é evidência POR ALUNO: ele abriu o quiz e não marcou nada.
#: `ZERO_POR_FALTA_LANCADA` é evidência POR PROVA: naquela prova o professor
#: lançou 0 para quem faltou, e a contagem da prova irmã do mesmo dia confirma
#: (docs/32 §1.4). A segunda não sabe QUEM faltou — sabe que, ali, zero não é
#: desempenho.
TODAS_EM_BRANCO = "todas_em_branco"
ZERO_POR_FALTA_LANCADA = "zero_por_falta_lancada"

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

    # A segunda evidência é da PROVA, e vale mesmo onde não há quiz — é
    # justamente o caso das oito de 2023, todas com nota lançada à mão.
    provas_zero_e_falta = _provas_com_zero_e_ausencia(cliente, simulado_ids)

    questao_para_simulado = _mapear_questoes(cliente, simulado_ids)
    if not questao_para_simulado:
        # Nenhum dos simulados é quiz: não há evidência POR ALUNO para
        # ninguém. A da prova continua valendo, e quem não se encaixa em
        # nenhuma das duas volta a ser computável.
        return _aplicar(cliente, simulado_ids, {}, provas_zero_e_falta)

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
    return _aplicar(cliente, simulado_ids, veredictos, provas_zero_e_falta)


def _provas_com_zero_e_ausencia(cliente: Client, simulado_ids: list[str]) -> set[str]:
    """Quais destas provas estão marcadas como "aqui, zero quer dizer falta".

    Ligada à mão, com lista na mão (`simulado.zero_e_ausencia`, migration
    0046). Não há detector automático de propósito: o critério que achou as
    oito de 2023 é forte para um humano ler e fraco para uma máquina aplicar —
    em Redação um pico em zero é legítimo, e automatizar repetiria o erro da
    regra dos "2+ zeros no mesmo dia", que apagava nota de quem respondeu.
    """
    marcadas: set[str] = set()
    for lote in _em_lotes(simulado_ids):
        resp = (
            cliente.table("simulado")
            .select("id, zero_e_ausencia")
            .in_("id", lote)
            .execute()
        )
        for linha in resp.data or []:
            if linha.get("zero_e_ausencia"):
                marcadas.add(linha["id"])
    return marcadas


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
    provas_zero_e_falta: set[str] | None = None,
) -> int:
    """Escreve só o que mudou de estado."""
    marcadas = provas_zero_e_falta or set()
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

            # A evidência da PROVA entra aqui, e não em `decidir`, porque só
            # neste ponto se sabe se a nota é zero. Ela é o fallback: a
            # evidência por aluno é mais específica e ganha quando existe.
            if computavel and linha["simulado_id"] in marcadas:
                computavel, motivo = False, ZERO_POR_FALTA_LANCADA

            # Nenhuma das duas regras fala de outra coisa que não ZERO com
            # presença afirmada. Nota positiva e ausência declarada não são
            # assunto delas — e "todas em branco" com nota acima de zero seria
            # contradição do Canvas, não nossa.
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
