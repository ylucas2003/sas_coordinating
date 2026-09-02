"""Listas de questões (com dono) e estado de estudo do aluno — docs/22 §P5 e §P6.

Tabelas: `lista_questoes`, `lista_questoes_item` e `questao_estudo_aluno`
(migration 0029). A lista mora no servidor e não no `localStorage` do site de
origem porque o aluno entra no celular e no computador, e uma lista que existe
só num aparelho é uma lista que ele perde sem saber por quê (docs/22 §5.1).

**Este módulo nunca lê token.** Quem resolve o dono da sessão é `routes/banco.py`;
aqui o par `(dono_tipo, dono_id)` chega pronto e entra em TODA consulta. É o
ponto da parte: um aluno não enxerga lista de outro, e isso é teste, não
comentário (docs/22 §5.2).

Duas formas de dizer "não deu", e a distinção importa para a rota traduzir:

  - `None` (ou `False`, em `remover`) → a lista não existe **ou não é do dono**.
    A rota devolve **404**, nunca 403 — ver `_linha_da_lista`.
  - `ValueError` → o chamador citou uma `questao_id` que não existe no banco.
    É engano de entrada, não de permissão; a mensagem nomeia os ids.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from supabase import Client

from ..schemas.banco import (
    DonoLista,
    EstudoQuestao,
    Lista,
    ListaResumo,
    QuestaoVestibular,
)

# `_COLUNAS_QUESTAO` é privado do módulo, não do pacote: `montar_questoes` só
# aceita linhas cruas, e repetir a lista de colunas aqui a deixaria envelhecer
# em dois lugares. O sublinhado continua dizendo "ninguém de fora de `banco/`".
from .consultas import _COLUNAS_QUESTAO, montar_questoes, obter_questao

# `in_` vira query string, e URL tem teto — o mesmo lote de 100 que
# `canvas_sync/sincronizar.py` já usa nas leituras por lista de id.
_LOTE_IN = 100


# ─── Infraestrutura miúda ────────────────────────────────────────────────


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _em_lotes(ids: list[str]) -> Iterator[list[str]]:
    for inicio in range(0, len(ids), _LOTE_IN):
        yield ids[inicio : inicio + _LOTE_IN]


def _sem_repetidos(ids: list[str]) -> list[str]:
    """Mesma ordem, primeira ocorrência vence.

    A PK de `lista_questoes_item` é (lista_id, questao_id): id repetido no corpo
    derrubaria o insert em lote inteiro com erro de chave duplicada. Repetir é
    engano de quem chamou, não pedido de duplicar a questão na lista.
    """
    vistos: set[str] = set()
    unicos: list[str] = []
    for questao_id in ids:
        if questao_id not in vistos:
            vistos.add(questao_id)
            unicos.append(questao_id)
    return unicos


def _uuid_valido(valor: str) -> bool:
    """`lista_questoes.id` é uuid; texto solto faria o PostgREST devolver 400.

    Um 400 vazado daqui viraria 500 na rota. Id malformado é id que não existe —
    tratar como "não achei" mantém a resposta 404 e não conta nada a ninguém.
    """
    try:
        UUID(str(valor))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


# ─── Leitura das linhas cruas ────────────────────────────────────────────

_COLUNAS_LISTA = "id, titulo, dono_tipo, criada_em, atualizada_em"


def _linha_da_lista(
    cliente: Client, lista_id: str, dono_tipo: DonoLista, dono_id: str
) -> dict[str, Any] | None:
    """A linha da lista **se, e só se**, for do dono da sessão.

    Todo caminho de escrita e de leitura passa por aqui — é o único lugar onde o
    filtro de dono precisa estar certo.

    Devolve `None` tanto para "não existe" quanto para "é de outra pessoa", e a
    rota transforma os dois no mesmo **404**. Um 403 seria mais informativo do
    que se quer ser: distinguir os dois casos confirmaria a existência da lista
    alheia para quem estivesse varrendo uuids (docs/22 §5.2 — "um aluno nunca
    enxerga lista de outro").
    """
    if not _uuid_valido(lista_id):
        return None
    linhas = (
        cliente.table("lista_questoes")
        .select(_COLUNAS_LISTA)
        .eq("id", lista_id)
        .eq("dono_tipo", dono_tipo)
        .eq("dono_id", dono_id)
        .limit(1)
        .execute()
    ).data or []
    return linhas[0] if linhas else None


def _ordem_dos_itens(cliente: Client, lista_id: str) -> list[str]:
    """Os `questao_id` da lista, na ordem escolhida por quem montou."""
    itens = (
        cliente.table("lista_questoes_item")
        .select("questao_id, posicao")
        .eq("lista_id", lista_id)
        .order("posicao")
        .execute()
    ).data or []
    return [item["questao_id"] for item in itens]


# ─── Questões em lote ────────────────────────────────────────────────────


def _questoes_por_id(cliente: Client, ids: list[str]) -> dict[str, QuestaoVestibular]:
    """As questões pedidas, indexadas por id. Ids inexistentes simplesmente faltam.

    Lê em lote em vez de chamar `obter_questao` numa laçada: uma lista de 50
    viraria 50 idas ao PostgREST. A junção com a taxonomia fica com
    `consultas.montar_questoes` — a lista tem ordem própria, mas não tem
    tradução própria.

    `resolvida` e `anotacao` saem None de propósito, como em todo o resto de
    `consultas`: são estado de UM aluno, e a lista serve os dois perfis. Quem
    quer o estado pede `GET /banco/estudo`.
    """
    if not ids:
        return {}

    linhas: list[dict[str, Any]] = []
    for lote in _em_lotes(ids):
        linhas += (
            cliente.table("questao_vestibular")
            .select(_COLUNAS_QUESTAO)
            .in_("id", lote)
            .execute()
        ).data or []

    return {questao.id: questao for questao in montar_questoes(cliente, linhas)}


# ─── Montagem da resposta ────────────────────────────────────────────────


def _montar_lista(linha: dict[str, Any], questoes: list[QuestaoVestibular]) -> Lista:
    return Lista(
        id=str(linha["id"]),
        titulo=linha["titulo"],
        donoTipo=linha["dono_tipo"],
        totalQuestoes=len(questoes),
        criadaEm=str(linha["criada_em"]),
        atualizadaEm=str(linha["atualizada_em"]),
        questoes=questoes,
    )


def _lista_com_ordem(
    cliente: Client, linha: dict[str, Any], ordem: list[str]
) -> Lista:
    questoes = _questoes_por_id(cliente, ordem)
    # `if q in questoes` e não KeyError: se um id sumir do banco entre a leitura
    # dos itens e a das questões, a lista sai menor — não sai quebrada.
    return _montar_lista(linha, [questoes[q] for q in ordem if q in questoes])


def _lista_completa(cliente: Client, linha: dict[str, Any]) -> Lista:
    return _lista_com_ordem(cliente, linha, _ordem_dos_itens(cliente, str(linha["id"])))


def _tocar(
    cliente: Client, lista_id: str, dono_tipo: DonoLista, dono_id: str
) -> dict[str, Any]:
    """Atualiza `atualizada_em` e devolve a linha nova.

    O filtro de dono se repete no UPDATE de propósito: mesmo depois de
    `_linha_da_lista` ter confirmado a posse, uma escrita sem `dono_*` seria uma
    escrita por id puro — a única linha do módulo que um erro de refatoração
    conseguiria apontar para a lista de outra pessoa.
    """
    return (
        cliente.table("lista_questoes")
        .update({"atualizada_em": _agora()}, returning="representation")
        .eq("id", lista_id)
        .eq("dono_tipo", dono_tipo)
        .eq("dono_id", dono_id)
        .execute()
    ).data[0]


def _exigir_questoes(cliente: Client, ids: list[str]) -> dict[str, QuestaoVestibular]:
    """Carrega as questões e falha alto se alguma não existir.

    Sem isso o erro apareceria como violação de chave estrangeira do PostgREST —
    500 com mensagem em inglês sobre `lista_questoes_item_questao_id_fkey`, sem
    dizer qual id. E, em `atualizar`, apareceria **depois** do DELETE.
    """
    questoes = _questoes_por_id(cliente, ids)
    faltando = [q for q in ids if q not in questoes]
    if faltando:
        raise ValueError(f"Questão inexistente no banco: {', '.join(faltando)}")
    return questoes


# ─── Listas ──────────────────────────────────────────────────────────────


def listar(cliente: Client, dono_tipo: DonoLista, dono_id: str) -> list[ListaResumo]:
    """Os resumos das listas do dono, da mexida mais recente para a mais antiga."""
    linhas = (
        cliente.table("lista_questoes")
        .select(_COLUNAS_LISTA)
        .eq("dono_tipo", dono_tipo)
        .eq("dono_id", dono_id)
        .order("atualizada_em", desc=True)
        .execute()
    ).data or []
    if not linhas:
        return []

    # Uma contagem em lote em vez de uma consulta por lista: o resumo não carrega
    # as questões, mas mostrar "0 questões" numa lista cheia seria pior que lento.
    total_por_lista: Counter[str] = Counter()
    ids = [str(linha["id"]) for linha in linhas]
    for lote in _em_lotes(ids):
        itens = (
            cliente.table("lista_questoes_item")
            .select("lista_id")
            .in_("lista_id", lote)
            .execute()
        ).data or []
        total_por_lista.update(str(item["lista_id"]) for item in itens)

    return [
        ListaResumo(
            id=str(linha["id"]),
            titulo=linha["titulo"],
            donoTipo=linha["dono_tipo"],
            totalQuestoes=total_por_lista[str(linha["id"])],
            criadaEm=str(linha["criada_em"]),
            atualizadaEm=str(linha["atualizada_em"]),
        )
        for linha in linhas
    ]


def criar(cliente: Client, dono_tipo: DonoLista, dono_id: str, titulo: str) -> Lista:
    """Cria uma lista vazia para o dono da sessão."""
    linha = (
        cliente.table("lista_questoes")
        .insert(
            {"titulo": titulo.strip(), "dono_tipo": dono_tipo, "dono_id": dono_id},
            returning="representation",
        )
        .execute()
    ).data[0]
    return _montar_lista(linha, [])


def obter(
    cliente: Client, lista_id: str, dono_tipo: DonoLista, dono_id: str
) -> Lista | None:
    """A lista com as questões na ordem gravada, ou `None` se não for do dono."""
    linha = _linha_da_lista(cliente, lista_id, dono_tipo, dono_id)
    if linha is None:
        return None
    return _lista_completa(cliente, linha)


def atualizar(
    cliente: Client,
    lista_id: str,
    dono_tipo: DonoLista,
    dono_id: str,
    titulo: str | None = None,
    questao_ids: list[str] | None = None,
) -> Lista | None:
    """Renomeia e/ou **substitui a ordem inteira** da lista.

    `questao_ids` não é um patch: é a lista completa, do jeito que ela deve
    ficar. Os itens são apagados e reinseridos com `posicao` 0..n-1. É assim
    porque reordenar mandando a lista toda evita que "mover para cima" vire N
    requisições que chegam fora de ordem e deixam a lista embaralhada
    (docs/22 §P5). `questao_ids=[]` esvazia; `questao_ids=None` não mexe.
    """
    linha = _linha_da_lista(cliente, lista_id, dono_tipo, dono_id)
    if linha is None:
        return None

    ordem: list[str] | None = None
    questoes: dict[str, QuestaoVestibular] = {}
    if questao_ids is not None:
        ordem = _sem_repetidos(questao_ids)
        # Antes do DELETE: PostgREST não dá transação entre requisições, então um
        # id inválido descoberto no INSERT deixaria a lista vazia (docs/22 §P5).
        questoes = _exigir_questoes(cliente, ordem)

        cliente.table("lista_questoes_item").delete().eq("lista_id", lista_id).execute()
        if ordem:
            cliente.table("lista_questoes_item").insert(
                [
                    {"lista_id": lista_id, "questao_id": questao_id, "posicao": posicao}
                    for posicao, questao_id in enumerate(ordem)
                ],
                returning="minimal",
            ).execute()

    patch: dict[str, Any] = {"atualizada_em": _agora()}
    if titulo is not None:
        patch["titulo"] = titulo.strip()
    linha = (
        cliente.table("lista_questoes")
        .update(patch, returning="representation")
        .eq("id", lista_id)
        .eq("dono_tipo", dono_tipo)
        .eq("dono_id", dono_id)
        .execute()
    ).data[0]

    if ordem is None:
        return _lista_completa(cliente, linha)
    return _montar_lista(linha, [questoes[q] for q in ordem])


def remover(cliente: Client, lista_id: str, dono_tipo: DonoLista, dono_id: str) -> bool:
    """Apaga a lista do dono. `False` = não existe ou não é dele (a rota dá 404).

    Os itens vão junto pelo `ON DELETE CASCADE` da 0029 — não há órfão a limpar.
    """
    if not _uuid_valido(lista_id):
        return False
    apagadas = (
        cliente.table("lista_questoes")
        .delete()
        .eq("id", lista_id)
        .eq("dono_tipo", dono_tipo)
        .eq("dono_id", dono_id)
        .execute()
    ).data or []
    return bool(apagadas)


def adicionar_questao(
    cliente: Client,
    lista_id: str,
    dono_tipo: DonoLista,
    dono_id: str,
    questao_id: str,
) -> Lista | None:
    """Põe a questão no fim da lista. Adicionar de novo é no-op, não erro.

    Clicar duas vezes em "adicionar" é clique repetido, não pedido de duplicar —
    e a PK (lista_id, questao_id) nem permitiria a segunda linha.
    """
    linha = _linha_da_lista(cliente, lista_id, dono_tipo, dono_id)
    if linha is None:
        return None
    if obter_questao(cliente, questao_id) is None:
        raise ValueError(f"Questão inexistente no banco: {questao_id}")

    itens = (
        cliente.table("lista_questoes_item")
        .select("questao_id, posicao")
        .eq("lista_id", lista_id)
        .order("posicao")
        .execute()
    ).data or []
    ordem = [item["questao_id"] for item in itens]
    if questao_id in ordem:
        # Nada mudou: não escreve e não toca `atualizada_em`. Bumpar a lista para
        # o topo de `listar` por causa de um clique repetido seria mentira.
        return _lista_com_ordem(cliente, linha, ordem)

    # max+1 e não len(itens): remover do meio deixa buraco na numeração, e o que
    # importa é a ordem relativa, não a densidade.
    proxima = max((item["posicao"] for item in itens), default=-1) + 1
    cliente.table("lista_questoes_item").insert(
        {"lista_id": lista_id, "questao_id": questao_id, "posicao": proxima},
        returning="minimal",
    ).execute()

    return _lista_com_ordem(
        cliente, _tocar(cliente, lista_id, dono_tipo, dono_id), [*ordem, questao_id]
    )


def remover_questao(
    cliente: Client,
    lista_id: str,
    dono_tipo: DonoLista,
    dono_id: str,
    questao_id: str,
) -> Lista | None:
    """Tira a questão da lista. Tirar o que já não está é no-op, não erro.

    As posições restantes ficam com buraco (0, 1, 3) — inofensivo: a leitura é
    `order("posicao")`, e recompactar custaria N escritas para nada.
    """
    linha = _linha_da_lista(cliente, lista_id, dono_tipo, dono_id)
    if linha is None:
        return None

    apagados = (
        cliente.table("lista_questoes_item")
        .delete()
        .eq("lista_id", lista_id)
        .eq("questao_id", questao_id)
        .execute()
    ).data or []
    if apagados:
        linha = _tocar(cliente, lista_id, dono_tipo, dono_id)
    return _lista_completa(cliente, linha)


# ─── Estudo do aluno (docs/22 §P6) ───────────────────────────────────────


def _para_estudo(linha: Mapping[str, Any]) -> EstudoQuestao:
    """Linha crua → o tipo da fronteira. Uma função só, usada pela leitura e
    pela escrita: duas conversões divergiriam no dia em que uma coluna nova
    entrasse só de um lado."""
    return EstudoQuestao(
        questaoId=linha["questao_id"],
        resolvida=bool(linha["resolvida"]),
        anotacao=linha.get("anotacao"),
        alternativaEscolhida=linha.get("alternativa_escolhida"),
        acertou=linha.get("acertou"),
    )


def listar_estudo(cliente: Client, aluno_id: str) -> list[EstudoQuestao]:
    """O que este aluno marcou, anotou ou respondeu. Questão sem linha = não
    tocada — que é a maioria delas, e é a informação principal da tela de
    progresso."""
    linhas = (
        cliente.table("questao_estudo_aluno")
        .select("questao_id, resolvida, anotacao, alternativa_escolhida, acertou")
        .eq("aluno_id", aluno_id)
        .order("atualizado_em", desc=True)
        .execute()
    ).data or []
    return [_para_estudo(linha) for linha in linhas]


def atualizar_estudo(
    cliente: Client,
    aluno_id: str,
    questao_id: str,
    resolvida: bool | None = None,
    anotacao: str | None = None,
    alternativa_escolhida: str | None = None,
) -> EstudoQuestao:
    """Upsert por (aluno_id, questao_id). `None` num campo = não mexer nele.

    Ler antes de escrever, em vez de mandar um upsert só com o campo enviado:
    o PostgREST monta o `ON CONFLICT DO UPDATE` a partir das chaves do corpo, e
    depender disso deixaria "salvar uma anotação apaga o `resolvida`" a uma
    mudança de biblioteca de distância. O campo ausente é preservado aqui,
    explicitamente.

    Para **limpar** a anotação ou a resposta, mande `""` — string vazia vira
    NULL, para que "sem anotação" e "não respondeu" tenham uma representação só
    no banco.

    ⚠️ `acertou` é CALCULADO aqui, contra o gabarito que já está no banco, e
    nunca aceito de quem chamou (0042). É dele que sai a leitura de em que
    assunto o aluno erra; deixá-lo entrar pelo corpo poria essa leitura a um
    `curl` de distância de discordar da prova.

    ⚠️ E `acertou` NÃO mexe em `resolvida`. Responder no treino não marca a
    questão como feita: a marca é auto-declarada e o aluno é quem a dá, no pé
    do cartão. As duas colunas dizem coisas diferentes e a tela as separa.
    """
    questao = obter_questao(cliente, questao_id)
    if questao is None:
        raise ValueError(f"Questão inexistente no banco: {questao_id}")

    atuais = (
        cliente.table("questao_estudo_aluno")
        .select("resolvida, anotacao, alternativa_escolhida, acertou")
        .eq("aluno_id", aluno_id)
        .eq("questao_id", questao_id)
        .limit(1)
        .execute()
    ).data or []
    atual = atuais[0] if atuais else {}

    resolvida_final = bool(atual.get("resolvida", False) if resolvida is None else resolvida)
    if anotacao is None:
        anotacao_final = atual.get("anotacao")
    else:
        anotacao_final = anotacao.strip() or None

    if alternativa_escolhida is None:
        letra_final = atual.get("alternativa_escolhida")
        acertou_final = atual.get("acertou")
    else:
        letra_final = alternativa_escolhida.strip().upper() or None
        acertou_final = _conferir(letra_final, questao.gabarito)

    linha = (
        cliente.table("questao_estudo_aluno")
        .upsert(
            {
                "aluno_id": aluno_id,
                "questao_id": questao_id,
                "resolvida": resolvida_final,
                "anotacao": anotacao_final,
                "alternativa_escolhida": letra_final,
                "acertou": acertou_final,
                "atualizado_em": _agora(),
            },
            on_conflict="aluno_id,questao_id",
            returning="representation",
        )
        .execute()
    ).data[0]

    return _para_estudo(linha)


def _conferir(letra: str | None, gabarito: str | None) -> bool | None:
    """A letra marcada contra a letra da banca. `None` = não dá para dizer.

    Três nulos diferentes chegam aqui e todos viram o mesmo `None`, porque a
    tela não pode distingui-los como acerto ou erro:

      * o aluno pulou a questão (`letra` vazia);
      * a questão é dissertativa — 420 e 469 das 934 originais não têm letra, e
        isso é o esperado, não dado faltando (docs/22 §8, risco 4);
      * a objetiva não teve o gabarito importado.

    ⚠️ `None` NUNCA pode virar `False` na tela. "Errou" e "não sabemos" são
    conselhos de estudo opostos.
    """
    if not letra or not gabarito:
        return None
    return letra == gabarito.strip().upper()
