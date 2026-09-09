"""Quantas vezes a cantina vai ao banco por requisição (docs/40 §12.1.3).

Estes testes contam **idas ao PostgREST**, não tempo. O motivo é que o cliente
é síncrono e o processo tem um event loop só (`UVICORN_WORKERS=1`): cada ida é
um pedaço de API parada para todo mundo, e um laço que consulta por item
degrada com o tamanho do mês sem nunca dar erro.

⚠️ Se algum destes quebrar por um número **maior**, a pergunta não é "posso
subir o limite?" — é "que consulta voltou para dentro de um `for`?".
"""

import asyncio
from collections import Counter
from datetime import date, timedelta

import pytest

from app.routes import cantina as rotas

from .fake_postgrest import FakeCliente

ALUNO = {"aluno_id": "A1"}


class ClienteQueConta(FakeCliente):
    """`FakeCliente` que registra quantas vezes cada tabela foi consultada."""

    def __init__(self, db):
        super().__init__(db)
        self.idas: Counter = Counter()

    def table(self, nome):
        self.idas[nome] += 1
        return super().table(nome)


def _cardapios_da_semana(quantos_dias: int) -> dict:
    """Uma semana lançada, almoço e janta em cada dia — o caso normal."""
    hoje = date.today()
    cardapios, blocos, opcoes = {}, {}, {}
    for dia in range(quantos_dias):
        data = (hoje + timedelta(days=dia)).isoformat()
        for refeicao in ("almoco", "janta"):
            cid = f"card-{dia}-{refeicao}"
            cardapios[cid] = {
                "id": cid,
                "cantina_id": "cant-1",
                "data": data,
                "refeicao": refeicao,
                "pedidos_ate": f"{data}T23:59:00+00:00",
                "publicado_em": "2026-09-01T10:00:00+00:00",
                "sem_refeicao": False,
                "aceita_pedido": True,
                "aceita_presencial": False,
            }
            bid = f"bloco-{cid}"
            blocos[bid] = {
                "id": bid,
                "cardapio_id": cid,
                "nome": "Proteína",
                "ordem": 1,
                "escolhas_minimas": 0,
                "escolhas_maximas": 1,
            }
            oid = f"opcao-{cid}"
            opcoes[oid] = {
                "id": oid,
                "bloco_id": bid,
                "nome": "Frango",
                "ordem": 1,
                "disponivel": True,
            }
    return {
        "cardapio": cardapios,
        "cardapio_bloco": blocos,
        "cardapio_opcao": opcoes,
        "direito_refeicao_aluno": {
            "d1": {"id": "d1", "aluno_id": "A1", "refeicao": "almoco"},
            "d2": {"id": "d2", "aluno_id": "A1", "refeicao": "janta"},
        },
        "pedido_refeicao": {},
        "pedido_refeicao_item": {},
    }


@pytest.mark.parametrize("dias", [1, 5, 15])
def test_a_leitura_do_aluno_nao_cresce_com_o_tamanho_do_mes(monkeypatch, dias):
    """O teste que FALHAVA antes do lote (docs/40, passo 4).

    Antes, `cardapio_bloco` era consultado uma vez POR CARDÁPIO: com a semana
    lançada em duas refeições, 10 idas em série; com o mês, 60. E esta rota tem
    `refetchInterval` de 60 s por aluno com direito, então o custo se
    multiplicava por gente na fila, não por tela aberta.
    """
    cliente = ClienteQueConta(_cardapios_da_semana(dias))
    monkeypatch.setattr(rotas, "get_supabase", lambda: cliente)

    saida = asyncio.run(rotas.cantina_do_aluno(ALUNO))

    assert len(saida["dias"]) == dias * 2, "todos os cardápios publicados têm de vir"
    assert cliente.idas["cardapio_bloco"] == 1, (
        f"{cliente.idas['cardapio_bloco']} idas a cardapio_bloco para {dias * 2} "
        "cardápios — a consulta voltou para dentro do laço"
    )
    # O total também não pode crescer: são as quatro leituras fixas
    # (direitos, cardápios, blocos, meus pedidos).
    assert sum(cliente.idas.values()) <= 5, dict(cliente.idas)


def test_a_ficha_da_coordenacao_conta_as_opcoes_uma_vez_so(monkeypatch):
    """`_contagem` rodava duas vezes na mesma requisição.

    Uma para a tela, outra escondida dentro de `_pedidos_do_cardapio`, que só
    queria o NOME de cada opção. A view agregada não é barata — ela varre
    `pedido_refeicao_item`, a tabela que cresce por dia × aluno × item
    (CLAUDE.md, armadilha 2).
    """
    db = _cardapios_da_semana(1)
    db["v_contagem_pedidos_por_opcao"] = {}
    db["v_pedidos_presenciais"] = {}
    db["matricula_turma"] = {}
    cliente = ClienteQueConta(db)
    monkeypatch.setattr(rotas, "get_supabase", lambda: cliente)

    asyncio.run(rotas.cardapio_para_a_coordenacao("card-0-almoco"))

    assert cliente.idas["v_contagem_pedidos_por_opcao"] == 1, (
        f"{cliente.idas['v_contagem_pedidos_por_opcao']} idas à view de contagem "
        "— alguém voltou a calcular a mesma agregação duas vezes"
    )
