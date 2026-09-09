"""Um aluno come UMA vez por refeição por dia, com duas cantinas no ar
(docs/40 §12.12).

⚠️ Estes testes existem por causa de uma premissa que era verdadeira e deixou
de ser. Enquanto havia uma cantina cadastrada, "o almoço de terça" e "o cardápio
de almoço de terça" eram a mesma coisa, e `UNIQUE (cardapio_id, aluno_id)`
bastava. Com a segunda cantina — "Food", que a planilha da coordenação
registrava como se fosse um LOCAL —, a trava antiga passa a permitir o aluno
pedir nas duas, e as duas cozinham para ele.

Nada disso dava erro antes. É o mesmo padrão que o docs/38 §1.1 registrou no
`foto_perfil.py`: o dia em que a premissa cai não vem com aviso.
"""

import asyncio
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.routes import cantina as rotas

from .fake_postgrest import FakeCliente

ALUNO = {"aluno_id": "A1"}
HOJE = date.today().isoformat()
AMANHA = (date.today() + timedelta(days=1)).isoformat()


def _banco() -> dict:
    """Duas cantinas publicando o MESMO almoço de hoje — o cenário da §12.12."""
    prazo = f"{AMANHA}T23:59:00+00:00"
    cardapio = {
        "data": HOJE,
        "refeicao": "almoco",
        "pedidos_ate": prazo,
        "publicado_em": "2026-09-01T10:00:00+00:00",
        "sem_refeicao": False,
        "aceita_pedido": True,
        "aceita_presencial": True,
    }
    return {
        "cantina": {
            "ari": {"id": "ari", "nome": "Cantina do Ari", "ativo": True,
                    "valor_almoco": 18.0, "valor_janta": None},
            "food": {"id": "food", "nome": "Food", "ativo": True,
                     "valor_almoco": 21.5, "valor_janta": None},
        },
        "cardapio": {
            "c-ari": {"id": "c-ari", "cantina_id": "ari", **cardapio},
            "c-food": {"id": "c-food", "cantina_id": "food", **cardapio},
        },
        "cardapio_bloco": {
            "b1": {"id": "b1", "cardapio_id": "c-ari", "nome": "Proteína", "ordem": 1,
                   "escolhas_minimas": 0, "escolhas_maximas": 1},
            "b2": {"id": "b2", "cardapio_id": "c-food", "nome": "Proteína", "ordem": 1,
                   "escolhas_minimas": 0, "escolhas_maximas": 1},
        },
        "cardapio_opcao": {
            "o1": {"id": "o1", "bloco_id": "b1", "nome": "Frango", "ordem": 1, "disponivel": True},
            "o2": {"id": "o2", "bloco_id": "b2", "nome": "Peixe", "ordem": 1, "disponivel": True},
        },
        "direito_refeicao_aluno": {
            "d1": {"id": "d1", "aluno_id": "A1", "refeicao": "almoco"},
        },
        "pedido_refeicao": {},
        "pedido_refeicao_item": {},
    }


def _com(monkeypatch, db) -> None:
    monkeypatch.setattr(rotas, "get_supabase", lambda: FakeCliente(db))


def _pedir(cardapio_id: str) -> dict:
    """Pedido SEM itens, e é de propósito.

    O que se testa aqui é a linha de `pedido_refeicao` — a trava do dia, as
    cópias de `data`/`refeicao` e o preço carimbado —, não a escolha de prato.
    Os blocos deste banco têm `escolhas_minimas = 0`, então pedido vazio é
    válido, e assim o teste não depende do fake resolver relação aninhada
    (`cardapio_opcao(*)`), que ele não resolve.
    """
    corpo = rotas.PedidoBody(opcao_ids=[])
    return asyncio.run(rotas.salvar_pedido(cardapio_id, corpo, ALUNO))


# ─── A trava ──────────────────────────────────────────────────────────────


def test_pedir_nas_duas_cantinas_no_mesmo_almoco_e_recusado(monkeypatch):
    """O defeito que a 0055 fecha, e que hoje passaria.

    Sem ela: duas linhas, duas cozinhas, e a contagem de cada cantina certa
    isoladamente — ninguém tem como perceber somando.
    """
    db = _banco()
    _com(monkeypatch, db)

    _pedir("c-ari")

    with pytest.raises(HTTPException) as erro:
        _pedir("c-food")

    assert erro.value.status_code == 409
    assert "já tem uma refeição marcada" in erro.value.detail
    assert len(db["pedido_refeicao"]) == 1, "a segunda linha não pode existir"


def test_a_recusa_vale_tambem_entre_modos(monkeypatch):
    """Pedir numa e declarar presença na outra é a mesma refeição.

    São linhas da mesma tabela, e o índice não distingue modo — o que é o
    comportamento certo: quem vai comer, vai comer uma vez.
    """
    db = _banco()
    _com(monkeypatch, db)

    _pedir("c-ari")

    with pytest.raises(HTTPException) as erro:
        asyncio.run(rotas.gerar_retirada("c-food", ALUNO))

    assert erro.value.status_code == 409


def test_dias_diferentes_continuam_livres(monkeypatch):
    """A trava é do DIA, não do aluno: amanhã ele escolhe de novo, onde quiser."""
    db = _banco()
    db["cardapio"]["c-amanha"] = {
        **db["cardapio"]["c-food"], "id": "c-amanha", "data": AMANHA,
    }
    db["cardapio_bloco"]["b3"] = {
        "id": "b3", "cardapio_id": "c-amanha", "nome": "Proteína", "ordem": 1,
        "escolhas_minimas": 0, "escolhas_maximas": 1,
    }
    db["cardapio_opcao"]["o3"] = {
        "id": "o3", "bloco_id": "b3", "nome": "Carne", "ordem": 1, "disponivel": True,
    }
    _com(monkeypatch, db)

    _pedir("c-ari")
    _pedir("c-amanha")

    assert len(db["pedido_refeicao"]) == 2


# ─── O que a linha guarda ─────────────────────────────────────────────────


def test_a_linha_carrega_dia_refeicao_e_o_preco_da_cantina_certa(monkeypatch):
    """As três cópias da 0054 e da 0055, escritas no mesmo INSERT.

    ⚠️ O preço é o da cantina DAQUELE cardápio. Com duas cantinas cobrando
    valores diferentes pelo almoço, ler "o" valor da cantina deixou de fazer
    sentido — e o erro seria invisível: o relatório fecharia, com o número
    errado.
    """
    db = _banco()
    _com(monkeypatch, db)

    _pedir("c-food")

    linha = next(iter(db["pedido_refeicao"].values()))
    assert linha["data"] == HOJE
    assert linha["refeicao"] == "almoco"
    assert linha["valor_cobrado"] == 21.5, "o preço da Food, não o da Cantina do Ari"


def test_o_aluno_ve_de_quem_e_cada_cardapio(monkeypatch):
    """Dois almoços do mesmo dia precisam ser distinguíveis na tela.

    Sem o nome, o aluno escolhe entre dois cartões idênticos — que é escolher
    no escuro (docs/40 §12.12.3).
    """
    db = _banco()
    _com(monkeypatch, db)

    saida = asyncio.run(rotas.cantina_do_aluno(ALUNO))

    nomes = sorted(dia["cantina"] for dia in saida["dias"])
    assert nomes == ["Cantina do Ari", "Food"]
