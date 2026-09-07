"""Retirada presencial — o código do QR e a máquina de estados (docs/40).

Duas metades, e a ordem delas é a do plano (docs/40 §9): o token primeiro,
sozinho, e só depois as rotas.

**O código do QR.** Ele é assinado com a MESMA chave das sessões, então o que o
separa de uma credencial é um claim de propósito. Se `uso` deixar de ser
conferido, um token de sessão passa no balcão e um código de QR passa como
Bearer — a forma exata da vulnerabilidade do token de download (PR #7,
`test_auth_chat.py`). Os testes daqui são irmãos daqueles.

**A máquina de estados.** `pedido` é porta sem volta, `presencial` é reversível
até o QR ser lido, e `retirado_em` é final dos dois lados (docs/40 §2). Nada
disso é `CHECK` no banco — o backend nunca escreve SQL —, então é regra que só
existe se tiver teste.

Convenção do arquivo (como `test_foto_perfil.py`): chama os handlers `async def`
direto com `asyncio.run`, com o `FakeCliente` no lugar do PostgREST. Sem
TestClient e sem banco de verdade.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_cantina_retirada.py -q
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from jose import jwt

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    """Chave de assinatura conhecida, para os testes forjarem tokens.

    O `cache_clear` nas duas pontas é obrigatório: `get_settings` é cacheado, e
    sem limpar depois a chave de teste vazaria para os outros arquivos.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    yield
    get_settings.cache_clear()


# ─── O código do QR ──────────────────────────────────────────────────────


def test_codigo_valido_volta_com_os_tres_campos():
    from app.cantina_token import assinar_retirada, ler_retirada

    codigo, expira_em = assinar_retirada(
        pedido_id="ped-1", cardapio_id="card-1", aluno_id="alu-1"
    )
    assert ler_retirada(codigo) == {
        "pedido_id": "ped-1",
        "cardapio_id": "card-1",
        "aluno_id": "alu-1",
    }
    # A validade volta junto para a tela do aluno renovar ANTES de vencer, sem
    # repetir a constante em TypeScript.
    assert 0 < (expira_em - datetime.now(UTC)).total_seconds() <= 120


def test_codigo_vencido_e_recusado():
    """O QR é fotografável. Se o vencimento não fosse conferido, um print no
    grupo da turma viraria crachá."""
    from app.cantina_token import RetiradaIlegivel, ler_retirada

    codigo, _ = _forjar(exp=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(RetiradaIlegivel):
        ler_retirada(codigo)


def test_codigo_assinado_com_outra_chave_e_recusado():
    """Quem monta o próprio QR não sabe a chave — e é só isso que o impede de
    escrever `aluno_id` de outra pessoa."""
    from app.cantina_token import RetiradaIlegivel, ler_retirada

    codigo = jwt.encode(
        {
            "uso": "retirada",
            "pedido_id": "ped-1",
            "cardapio_id": "card-1",
            "aluno_id": "alu-1",
            "exp": datetime.now(UTC) + timedelta(minutes=2),
        },
        "outra-chave-com-mais-de-32-caracteres-aqui",
        algorithm="HS256",
    )
    with pytest.raises(RetiradaIlegivel):
        ler_retirada(codigo)


@pytest.mark.parametrize("ausente", ["pedido_id", "cardapio_id", "aluno_id"])
def test_codigo_sem_campo_obrigatorio_e_recusado(ausente):
    """Sem `pedido_id` não há linha para marcar; sem `cardapio_id` não há como
    conferir de que cantina é; sem `aluno_id` o evento de tempo real não acha
    dono. Nenhum dos três tem substituto."""
    from app.cantina_token import RetiradaIlegivel, ler_retirada

    codigo, _ = _forjar(remover=ausente)
    with pytest.raises(RetiradaIlegivel):
        ler_retirada(codigo)


def test_codigo_sem_validade_e_recusado():
    """⚠️ O caso que o `jwt.decode` NÃO pega sozinho: ele confere `exp` se `exp`
    existir. Um token sem validade tem assinatura boa e vale para sempre."""
    from app.cantina_token import RetiradaIlegivel, ler_retirada

    codigo, _ = _forjar(remover="exp")
    with pytest.raises(RetiradaIlegivel):
        ler_retirada(codigo)


def test_token_de_sessao_nao_passa_como_codigo_de_qr():
    """⚠️ Metade do furo do PR #7, no sentido de ida.

    A chave é a mesma, então um token de sessão de aluno tem assinatura válida
    aqui. O que o recusa é o claim de propósito: sem `uso: "retirada"`, ele não
    é um código de QR — é uma credencial que alguém tentou reapresentar.
    """
    from app.auth import criar_token
    from app.cantina_token import RetiradaIlegivel, ler_retirada

    sessao = criar_token({"tipo": "aluno", "sub": "alu-1", "aluno_id": "alu-1"})
    with pytest.raises(RetiradaIlegivel):
        ler_retirada(sessao)


def test_codigo_de_qr_nao_abre_sessao():
    """⚠️ A outra metade, no sentido de volta.

    Apresentado como Bearer, o código do QR tem assinatura válida — e é
    `get_current_user` que o barra, porque ele não tem `tipo` em
    `TIPOS_DE_SESSAO`. Este teste é o irmão direto de
    `test_auth_chat.test_token_de_download_nao_abre_sessao_no_chat`.
    """
    from app.auth import get_current_user
    from app.cantina_token import assinar_retirada

    codigo, _ = assinar_retirada(pedido_id="p", cardapio_id="c", aluno_id="a")

    class _Credencial:
        credentials = codigo

    with pytest.raises(HTTPException) as erro:
        asyncio.run(get_current_user(_Credencial()))
    assert erro.value.status_code == 401


def _forjar(*, exp: datetime | None = None, remover: str | None = None) -> tuple[str, dict]:
    """Um código montado à mão, para simular o que um cliente adulterado manda."""
    conteudo = {
        "uso": "retirada",
        "pedido_id": "ped-1",
        "cardapio_id": "card-1",
        "aluno_id": "alu-1",
        "exp": exp or datetime.now(UTC) + timedelta(minutes=2),
    }
    if remover:
        conteudo.pop(remover)
    return jwt.encode(conteudo, SEGREDO, algorithm="HS256"), conteudo


# ─── A máquina de estados ────────────────────────────────────────────────
#
# O cenário é sempre o mesmo: uma cantina, o almoço de HOJE publicado aceitando
# os dois modos, e a Ana com direito a almoço. "Hoje" é calculado no fuso da
# escola, como o servidor calcula — data fixa no teste quebraria sozinha amanhã.

ALUNO = {"tipo": "aluno", "sub": "alu-1", "aluno_id": "alu-1"}
CANTINA = {"tipo": "cantina", "sub": "conta-1", "cantina_id": "cant-1"}
OUTRA_CANTINA = {"tipo": "cantina", "sub": "conta-9", "cantina_id": "cant-9"}


class _Requisicao:
    """Só o que os handlers leem de `Request`: `client.host`."""

    client = type("C", (), {"host": "203.0.113.7"})()


def _hoje():
    from app.banco.missao import FUSO_DA_ESCOLA

    return datetime.now(UTC).astimezone(FUSO_DA_ESCOLA).date()


def _banco(*, aceita_presencial: bool = True, aceita_pedido: bool = True, dia=None) -> dict:
    hoje = _hoje()
    return {
        "cantina": {
            "cant-1": {"id": "cant-1", "nome": "Copa", "ativo": True},
            "cant-9": {"id": "cant-9", "nome": "Outra", "ativo": True},
        },
        "cardapio": {
            "card-1": {
                "id": "card-1",
                "cantina_id": "cant-1",
                "data": (dia or hoje).isoformat(),
                "refeicao": "almoco",
                # Prazo no futuro: o pedido continua aberto, para os testes que
                # exercitam a troca de modo. A retirada presencial não olha isto.
                "pedidos_ate": (datetime.now(UTC) + timedelta(hours=6)).isoformat(),
                "publicado_em": "2026-09-01T10:00:00+00:00",
                "sem_refeicao": False,
                "aceita_pedido": aceita_pedido,
                "aceita_presencial": aceita_presencial,
            },
            # O mesmo dia, na cantina do outro prédio: é o cardápio que o balcão
            # errado não pode confirmar.
            "card-9": {
                "id": "card-9",
                "cantina_id": "cant-9",
                "data": (dia or hoje).isoformat(),
                "refeicao": "almoco",
                "pedidos_ate": (datetime.now(UTC) + timedelta(hours=6)).isoformat(),
                "publicado_em": "2026-09-01T10:00:00+00:00",
                "sem_refeicao": False,
                "aceita_pedido": True,
                "aceita_presencial": True,
            },
        },
        "direito_refeicao_aluno": {
            "d1": {"aluno_id": "alu-1", "refeicao": "almoco"},
        },
        "aluno": {
            "alu-1": {"id": "alu-1", "nome": "Ana Lima", "restricao_alimentar": "sem lactose"},
        },
        "pedido_refeicao": {},
        "pedido_refeicao_item": {},
        "cardapio_bloco": {},
        "matricula_turma": {},
        "evento_auditoria": {},
    }


def _com_banco(monkeypatch, db):
    from app.routes import cantina as rotas
    from tests.fake_postgrest import FakeCliente

    monkeypatch.setattr(rotas, "get_supabase", lambda: FakeCliente(db))
    return rotas


def _gerar(rotas, db, cardapio_id: str = "card-1", aluno=None) -> dict:
    return asyncio.run(rotas.gerar_retirada(cardapio_id, aluno or ALUNO))


def _confirmar(rotas, token: str, usuario=None) -> dict:
    corpo = rotas.ConfirmarRetiradaBody(token=token)
    return asyncio.run(rotas.confirmar_retirada(corpo, _Requisicao(), usuario or CANTINA))


def _linhas(db) -> list[dict]:
    return list(db["pedido_refeicao"].values())


# ─── Gerar o QR ──────────────────────────────────────────────────────────


def test_gerar_cria_a_linha_presencial(monkeypatch):
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    saida = _gerar(rotas, db)

    assert saida["token"] and saida["expiraEm"]
    assert len(_linhas(db)) == 1
    assert _linhas(db)[0]["modo"] == "presencial"
    assert _linhas(db)[0].get("retirado_em") is None


def test_gerar_de_novo_renova_o_codigo_sem_criar_outra_linha(monkeypatch):
    """A tela do aluno chama isto a cada dois minutos enquanto o QR está
    visível. Se cada renovação criasse linha, o `UNIQUE(cardapio_id, aluno_id)`
    explodiria — e antes disso a contagem da cantina teria contado a mesma
    pessoa duas vezes."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    primeiro = _gerar(rotas, db)["token"]
    segundo = _gerar(rotas, db)["token"]

    assert len(_linhas(db)) == 1
    # Códigos diferentes (o `exp` andou), mas apontando para a MESMA linha.
    from app.cantina_token import ler_retirada

    assert ler_retirada(primeiro)["pedido_id"] == ler_retirada(segundo)["pedido_id"]


def test_quem_ja_pediu_nao_vira_presencial(monkeypatch):
    """⚠️ A transição proibida do §2: `pedido` é porta sem volta. Quem pediu
    comprometeu a cozinha com um prato, e virar presencial deixaria esse prato
    feito para ninguém."""
    db = _banco()
    db["pedido_refeicao"]["p1"] = {
        "id": "p1", "cardapio_id": "card-1", "aluno_id": "alu-1", "modo": "pedido",
    }
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        _gerar(rotas, db)
    assert erro.value.status_code == 409


def test_aluno_sem_direito_nao_gera(monkeypatch):
    """Mesma recusa do pedido: quem não tem direito à refeição não entra pela
    porta nova (docs/38 §3.2)."""
    db = _banco()
    db["direito_refeicao_aluno"] = {}
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        _gerar(rotas, db)
    assert erro.value.status_code == 403


def test_cardapio_que_nao_aceita_presencial_recusa(monkeypatch):
    """O modo é do DIA, e a recusa é do servidor: a tela do aluno pode estar
    aberta desde antes de a cantina desligar o presencial."""
    db = _banco(aceita_presencial=False)
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        _gerar(rotas, db)
    assert erro.value.status_code == 422


def test_cardapio_de_outro_dia_recusa(monkeypatch):
    """docs/40 §11.1: o QR é para ser lido na hora. Um código para daqui a três
    dias não avisa a cozinha de nada real e enche a lista de pendentes."""
    db = _banco(dia=_hoje() - timedelta(days=1))
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        _gerar(rotas, db)
    assert erro.value.status_code == 422


def test_cardapio_em_rascunho_nao_existe_para_o_aluno(monkeypatch):
    db = _banco()
    db["cardapio"]["card-1"]["publicado_em"] = None
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        _gerar(rotas, db)
    assert erro.value.status_code == 404


def test_presencial_ignora_o_prazo_do_pedido(monkeypatch):
    """A diferença que define a feature: `pedidos_ate` vencido fecha o pedido e
    NÃO fecha a retirada presencial (docs/40 §3)."""
    db = _banco()
    db["cardapio"]["card-1"]["pedidos_ate"] = (
        datetime.now(UTC) - timedelta(hours=1)
    ).isoformat()
    rotas = _com_banco(monkeypatch, db)

    assert _gerar(rotas, db)["token"]


# ─── Desistir ────────────────────────────────────────────────────────────


def test_desistir_apaga_a_linha_nao_lida(monkeypatch):
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    _gerar(rotas, db)

    assert asyncio.run(rotas.desistir_da_retirada("card-1", ALUNO)) == {"ok": True}
    assert _linhas(db) == []


def test_desistir_sem_ter_gerado_e_no_op(monkeypatch):
    """Idempotente: desistir do que não existe já é o estado que o aluno quer,
    e um erro aqui só apareceria em toque duplo."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    assert asyncio.run(rotas.desistir_da_retirada("card-1", ALUNO)) == {"ok": True}


def test_desistir_depois_de_retirada_e_recusado(monkeypatch):
    """⚠️ `retirado_em` é final dos dois lados: o aluno já comeu. Apagar a linha
    aqui apagaria a única prova de que a refeição saiu."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    _confirmar(rotas, _gerar(rotas, db)["token"])

    with pytest.raises(HTTPException) as erro:
        asyncio.run(rotas.desistir_da_retirada("card-1", ALUNO))
    assert erro.value.status_code == 409
    assert len(_linhas(db)) == 1


# ─── Trocar de presencial para pedido ────────────────────────────────────


def test_pedido_sobrescreve_presencial_ainda_nao_lido(monkeypatch):
    """A transição PERMITIDA do §2, e o cenário da conversa: gerou o QR às 7h,
    ninguém leu, e às 11h ele muda de ideia e pede."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    _gerar(rotas, db)

    asyncio.run(rotas.salvar_pedido("card-1", rotas.PedidoBody(opcao_ids=[]), ALUNO))

    assert len(_linhas(db)) == 1
    assert _linhas(db)[0]["modo"] == "pedido"


def test_pedido_depois_de_retirada_e_recusado(monkeypatch):
    """A recusa nova no `PUT` (docs/40 §2): mudar o pedido de uma refeição já
    servida mexeria na contagem de um prato que saiu do balcão."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    _confirmar(rotas, _gerar(rotas, db)["token"])

    with pytest.raises(HTTPException) as erro:
        asyncio.run(rotas.salvar_pedido("card-1", rotas.PedidoBody(opcao_ids=[]), ALUNO))
    assert erro.value.status_code == 409


def test_dia_so_de_presencial_nao_aceita_pedido(monkeypatch):
    """`aceita_pedido` também é regra de servidor, não enfeite de tela."""
    db = _banco(aceita_pedido=False)
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        asyncio.run(rotas.salvar_pedido("card-1", rotas.PedidoBody(opcao_ids=[]), ALUNO))
    assert erro.value.status_code == 422


# ─── A leitura no balcão ─────────────────────────────────────────────────


def test_confirmar_marca_a_retirada_e_devolve_a_ficha(monkeypatch):
    """A resposta é a régua de dado do docs/38 §8.1.2: nome, turma, refeição e
    restrição alimentar. Nada de nota, ficha ou histórico."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    saida = _confirmar(rotas, _gerar(rotas, db)["token"])

    assert saida["alunoId"] == "alu-1"
    assert saida["nome"] == "Ana Lima"
    assert saida["restricaoAlimentar"] == "sem lactose"
    assert saida["refeicao"] == "almoco"
    assert saida["retiradoEm"]
    assert set(saida) == {
        "alunoId", "nome", "turma", "refeicao", "data", "restricaoAlimentar", "retiradoEm",
    }
    assert _linhas(db)[0]["retirado_em"]


def test_segunda_leitura_do_mesmo_codigo_da_409(monkeypatch):
    """⚠️ O teste central do §4.

    É o que prova que a trava é o `WHERE` do UPDATE, e não um "buscar, conferir,
    gravar" — entre a leitura e a escrita caberia a segunda câmera do mesmo
    balcão, e as duas serviriam o mesmo aluno. Aqui o mesmo código é lido duas
    vezes e a segunda não acha linha com `retirado_em IS NULL`.
    """
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    token = _gerar(rotas, db)["token"]

    _confirmar(rotas, token)
    with pytest.raises(HTTPException) as erro:
        _confirmar(rotas, token)

    assert erro.value.status_code == 409
    # A hora da retirada original entra na frase: na maioria das vezes isto é
    # segunda passagem por engano, não fraude.
    assert "já foi retirada" in erro.value.detail


def test_confirmar_codigo_de_cardapio_de_outra_cantina(monkeypatch):
    """O recorte vem do TOKEN DE SESSÃO. Um código válido do outro prédio é 403
    — o recurso existe, e quem está no balcão precisa entender isso."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    token = _gerar(rotas, db, "card-9")["token"]

    with pytest.raises(HTTPException) as erro:
        _confirmar(rotas, token, CANTINA)
    assert erro.value.status_code == 403
    # E a linha não foi tocada: recusar sem escrever é o ponto.
    assert all(linha.get("retirado_em") is None for linha in _linhas(db))


def test_confirmar_com_codigo_ilegivel(monkeypatch):
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        _confirmar(rotas, "isto-não-é-um-jwt")
    assert erro.value.status_code == 422


def test_confirmar_com_codigo_vencido(monkeypatch):
    """Dois minutos de validade: o print mandado no grupo não serve para nada."""
    db = _banco()
    db["pedido_refeicao"]["ped-1"] = {
        "id": "ped-1", "cardapio_id": "card-1", "aluno_id": "alu-1", "modo": "presencial",
    }
    rotas = _com_banco(monkeypatch, db)
    vencido, _ = _forjar(exp=datetime.now(UTC) - timedelta(seconds=1))

    with pytest.raises(HTTPException) as erro:
        _confirmar(rotas, vencido)
    assert erro.value.status_code == 422
    assert db["pedido_refeicao"]["ped-1"].get("retirado_em") is None


def test_confirmar_depois_de_o_aluno_ter_virado_pedido(monkeypatch):
    """De graça, pela mesma condição do UPDATE: `modo = "presencial"` deixou de
    bater. O aluno gerou o QR, desistiu e pediu — o código velho não serve."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    token = _gerar(rotas, db)["token"]
    asyncio.run(rotas.salvar_pedido("card-1", rotas.PedidoBody(opcao_ids=[]), ALUNO))

    with pytest.raises(HTTPException) as erro:
        _confirmar(rotas, token)
    assert erro.value.status_code == 409


def test_confirmar_publica_evento_de_retirada(monkeypatch):
    """O stream avisa; quem decide o texto é `GET /me/cantina` (docs/40 §5)."""
    from app.cantina_eventos import Evento, para_a_cantina, para_o_aluno

    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    recebidos: list[Evento] = []
    monkeypatch.setattr(rotas.barramento, "publicar", recebidos.append)

    _confirmar(rotas, _gerar(rotas, db)["token"])

    retiradas = [e for e in recebidos if e.tipo == "retirada"]
    assert len(retiradas) == 1
    # Os dois recortes que já existiam cobrem o tipo novo sem alteração.
    assert para_o_aluno("alu-1")(retiradas[0])
    assert para_a_cantina("cant-1")(retiradas[0])
    assert not para_o_aluno("outro")(retiradas[0])


# ─── O que as telas leem ─────────────────────────────────────────────────


def test_contagem_separa_pendentes_de_retirados(monkeypatch):
    """Linha à parte, e não somada às opções: presencial não escolhe prato
    (docs/40 §10.1), então entrar na contagem por opção inventaria comida."""
    db = _banco()
    db["direito_refeicao_aluno"]["d2"] = {"aluno_id": "alu-2", "refeicao": "almoco"}
    rotas = _com_banco(monkeypatch, db)
    _gerar(rotas, db)
    _confirmar(rotas, _gerar(rotas, db, aluno={"tipo": "aluno", "aluno_id": "alu-2"})["token"])

    saida = asyncio.run(rotas.contagem_do_cardapio("card-1", CANTINA))

    assert saida["presencial"] == {"pendentes": 1, "retirados": 1}
    assert saida["opcoes"] == []


def test_lista_do_balcao_marca_o_modo(monkeypatch):
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    _gerar(rotas, db)

    linha = asyncio.run(rotas.pedidos_do_cardapio("card-1", CANTINA))[0]

    assert linha["modo"] == "presencial"
    assert linha["retiradoEm"] is None
    assert linha["escolhas"] == []


# ─── A coordenação: a mesma leitura, sem poder mexer ─────────────────────
#
# A coordenação não tem a rota `/contagem` da cantina: ela lê o dia inteiro em
# `GET /administracao/cantina/cardapios/{id}`. Enquanto essa rota montava só
# `contagem`, a tela ficava sem o presencial — e como a contagem por opção o
# ignora de propósito (docs/40 §10.1), ela dizia "nenhum pedido ainda" ao lado
# de uma lista de nomes.


def _misto(monkeypatch):
    """Um pedido, um presencial pendente e um presencial já retirado.

    É o cenário que separa os três números: `contagem` some com dois deles,
    `presencial` explica os dois, e `pedidos` tem os três.
    """
    db = _banco()
    for i in (2, 3):
        db["direito_refeicao_aluno"][f"d{i}"] = {"aluno_id": f"alu-{i}", "refeicao": "almoco"}
        db["aluno"][f"alu-{i}"] = {"id": f"alu-{i}", "nome": f"Beto {i}"}
    rotas = _com_banco(monkeypatch, db)
    asyncio.run(rotas.salvar_pedido("card-1", rotas.PedidoBody(opcao_ids=[]), ALUNO))
    _gerar(rotas, db, aluno={"tipo": "aluno", "aluno_id": "alu-2"})
    _confirmar(rotas, _gerar(rotas, db, aluno={"tipo": "aluno", "aluno_id": "alu-3"})["token"])
    return rotas, db


def test_coordenacao_le_o_presencial_com_a_mesma_forma_da_cantina(monkeypatch):
    """⚠️ Os MESMOS nomes, vindos da MESMA função.

    A asserção que importa não é o par de números — é a igualdade com o que a
    rota da cantina devolve. Duas contagens escritas separadamente para o mesmo
    dia divergem no primeiro ajuste que só uma delas receber, e aí a cantina e a
    coordenação passam a discordar sobre quantas pessoas vão comer.
    """
    rotas, _ = _misto(monkeypatch)

    da_coordenacao = asyncio.run(rotas.cardapio_para_a_coordenacao("card-1"))
    da_cantina = asyncio.run(rotas.contagem_do_cardapio("card-1", CANTINA))

    assert da_coordenacao["presencial"] == {"pendentes": 1, "retirados": 1}
    assert da_coordenacao["presencial"] == da_cantina["presencial"]
    # A contagem por opção continua sendo a de PRATO, e por isso não fecha com
    # os três da lista: é justamente essa distância que o bloco explica.
    assert da_coordenacao["contagem"] == da_cantina["opcoes"]
    assert len(da_coordenacao["pedidos"]) == 3


def test_coordenacao_sem_presencial_nenhum_recebe_zeros(monkeypatch):
    """Zero é resposta; chave ausente é a tela adivinhando.

    Sem o bloco, a coordenação teria de tratar "não veio" como "não houve" — e
    no dia em que a rota falhasse de outro jeito ela mostraria o mesmo nada.
    """
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    asyncio.run(rotas.salvar_pedido("card-1", rotas.PedidoBody(opcao_ids=[]), ALUNO))

    saida = asyncio.run(rotas.cardapio_para_a_coordenacao("card-1"))

    assert saida["presencial"] == {"pendentes": 0, "retirados": 0}


def test_lista_da_coordenacao_marca_o_modo_como_a_do_balcao(monkeypatch):
    """A marca por aluno do docs/40 §8 sai da mesma `_pedidos_do_cardapio`.

    Sem `modo` e `retiradoEm` no caminho da coordenação, a tela renderiza a
    tarja vazia — e as duas listas só continuam iguais enquanto ninguém montar
    uma projeção própria aqui.
    """
    rotas, _ = _misto(monkeypatch)

    da_coordenacao = asyncio.run(rotas.cardapio_para_a_coordenacao("card-1"))["pedidos"]

    assert da_coordenacao == asyncio.run(rotas.pedidos_do_cardapio("card-1", CANTINA))
    por_aluno = {linha["alunoId"]: linha for linha in da_coordenacao}
    assert por_aluno["alu-1"]["modo"] == "pedido"
    assert por_aluno["alu-2"]["modo"] == "presencial"
    assert por_aluno["alu-2"]["retiradoEm"] is None
    assert por_aluno["alu-3"]["retiradoEm"]


def test_tela_do_aluno_conta_a_historia_do_presencial(monkeypatch):
    """`meuPedido` continua sendo O PEDIDO — nulo no presencial, porque uma
    lista vazia diria "você pediu nada" onde a verdade é "você vai buscar"."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    _gerar(rotas, db)

    dia = asyncio.run(rotas.cantina_do_aluno(ALUNO))["dias"][0]

    assert dia["modo"] == "presencial"
    assert dia["meuPedido"] is None
    assert dia["retiradoEm"] is None
    assert dia["aceitaPedido"] is True
    assert dia["aceitaPresencial"] is True

    _confirmar(rotas, _gerar(rotas, db)["token"])
    assert asyncio.run(rotas.cantina_do_aluno(ALUNO))["dias"][0]["retiradoEm"]


def test_dia_sem_linha_nenhuma_nao_tem_modo(monkeypatch):
    """Nenhum dos dois caminhos escolhido ainda: é o estado em que a tela mostra
    as duas ações lado a lado (docs/40 §6)."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    dia = asyncio.run(rotas.cantina_do_aluno(ALUNO))["dias"][0]

    assert dia["modo"] is None
    assert dia["meuPedido"] is None


# ─── O calendário: os três números do dia ────────────────────────────────
#
# A view `v_pedidos_por_cardapio` não existe no `FakeCliente` — ele é um dict de
# tabelas, não um Postgres. `_com_a_view` a reconstrói em Python com a MESMA
# agregação da 0052, a partir das linhas que os handlers gravaram: assim
# `quantos == com_pedido + presenciais` sai dos dados, e não de um número
# escrito à mão que passaria mesmo se a rota lesse a coluna errada.
#
# ⚠️ Isto prova o CONTRATO da rota, não a view. Que o Postgres devolve as três
# colunas foi verificado com curl em `v_pedidos_por_cardapio` depois do
# `restart postgrest` — sem o restart elas voltam 404 (CLAUDE.md, armadilha 1).


def _com_a_view(db: dict) -> dict:
    """Materializa a view da 0052 no fake, como o Postgres a calcularia."""
    view = {}
    for cardapio_id in db["cardapio"]:
        linhas = [p for p in db["pedido_refeicao"].values() if p["cardapio_id"] == cardapio_id]
        # `modo` ausente é `pedido`, como no banco: quem grava o pedido não
        # manda a coluna, e quem responde é o `DEFAULT 'pedido'` da 0051 — que o
        # fake não tem. É a mesma leitura que `_pedidos_do_cardapio` faz.
        modos = [p.get("modo") or "pedido" for p in linhas]
        view[cardapio_id] = {
            "cardapio_id": cardapio_id,
            # O LEFT JOIN da 0052: o cardápio sem pedido nenhum vem com 0, não
            # some da lista.
            "quantos": len(modos),
            "com_pedido": modos.count("pedido"),
            "presenciais": modos.count("presencial"),
        }
    db["v_pedidos_por_cardapio"] = view
    return db


def test_calendario_quebra_o_total_entre_as_duas_portas(monkeypatch):
    """O caso que virava chamado de bug: o dia mostra 3, e a contagem por opção
    soma 1, porque presencial não escolhe prato (docs/40 §10.1).

    `pedidos` continua sendo o total — "quantos vão comer" —, e é a quebra em
    `comPedido`/`presenciais` que permite ao número se explicar sozinho.
    """
    db = _banco()
    for i in (2, 3):
        db["direito_refeicao_aluno"][f"d{i}"] = {"aluno_id": f"alu-{i}", "refeicao": "almoco"}
    rotas = _com_banco(monkeypatch, db)
    asyncio.run(rotas.salvar_pedido("card-1", rotas.PedidoBody(opcao_ids=[]), ALUNO))
    _gerar(rotas, db, aluno={"tipo": "aluno", "aluno_id": "alu-2"})
    # Já retirado conta junto: quem passou pelo balcão comeu, e o calendário
    # responde "quantos vão comer", não "quantos ainda vão aparecer".
    _confirmar(rotas, _gerar(rotas, db, aluno={"tipo": "aluno", "aluno_id": "alu-3"})["token"])
    _com_a_view(db)

    dia = asyncio.run(rotas.calendario_da_cantina(_hoje(), _hoje(), CANTINA))[0]

    assert dia["pedidos"] == 3
    assert dia["comPedido"] == 1
    assert dia["presenciais"] == 2
    assert dia["pedidos"] == dia["comPedido"] + dia["presenciais"]


def test_calendario_da_coordenacao_sai_igual_ao_da_cantina(monkeypatch):
    """As duas rotas delegam à mesma `_calendario`, e é isso que garante o
    contrato único. Um dia divergir aqui significa alguém ter duplicado a
    montagem — que é como os dois números começaram a discordar."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    _gerar(rotas, db)
    _com_a_view(db)

    da_cantina = asyncio.run(rotas.calendario_da_cantina(_hoje(), _hoje(), CANTINA))
    da_coordenacao = asyncio.run(rotas.calendario_da_coordenacao(_hoje(), _hoje(), "cant-1"))

    assert da_cantina == da_coordenacao
    assert da_cantina[0]["presenciais"] == 1
    assert da_cantina[0]["comPedido"] == 0


def test_dia_sem_pedido_nenhum_vem_com_os_tres_zeros(monkeypatch):
    """O cardápio ausente da view (nunca acontece com o LEFT JOIN, mas a rota
    não depende disso) não pode virar dia sem número: `None` no lugar de `0`
    apagaria a contagem da tela em vez de mostrar que ninguém pediu."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    db["v_pedidos_por_cardapio"] = {}

    dia = asyncio.run(rotas.calendario_da_cantina(_hoje(), _hoje(), CANTINA))[0]

    assert (dia["pedidos"], dia["comPedido"], dia["presenciais"]) == (0, 0, 0)


# ─── Publicar e a regra da casa ──────────────────────────────────────────


def test_publicar_com_os_dois_modos_desligados_e_recusado(monkeypatch):
    """Um cardápio que não aceita nada não é "publicado": é `sem_refeicao`
    disfarçado, e o aluno veria comida sem nenhum botão (docs/40 §1)."""
    db = _banco(aceita_pedido=False, aceita_presencial=False)
    db["cardapio"]["card-1"]["publicado_em"] = None
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        asyncio.run(rotas.publicar_cardapio("card-1", _Requisicao(), CANTINA))
    assert erro.value.status_code == 422
    assert db["cardapio"]["card-1"]["publicado_em"] is None


def test_publicar_so_presencial_nao_exige_prazo(monkeypatch):
    """⚠️ Sem isto a feature nasceria morta no caso que ela existe para
    resolver: o almoço de HOJE. A regra padrão da casa é "véspera às 20h", então
    um cardápio criado hoje já nasce com prazo vencido — e a recusa de prazo,
    que é certa para quem aceita pedido, impediria de publicar o dia inteiro.
    """
    db = _banco(aceita_pedido=False, aceita_presencial=True)
    db["cardapio"]["card-1"]["pedidos_ate"] = (
        datetime.now(UTC) - timedelta(hours=20)
    ).isoformat()
    db["cardapio"]["card-1"]["publicado_em"] = None
    db["cardapio_bloco"]["b1"] = {"id": "b1", "cardapio_id": "card-1", "nome": "Prato", "ordem": 0}
    rotas = _com_banco(monkeypatch, db)

    # Chega até a recusa de "sem opção", que é a próxima da fila — ou seja,
    # passou pelas duas de prazo.
    with pytest.raises(HTTPException) as erro:
        asyncio.run(rotas.publicar_cardapio("card-1", _Requisicao(), CANTINA))
    assert "pelo menos uma opção" in erro.value.detail


def test_publicar_com_os_dois_modos_ignora_prazo_vencido(monkeypatch):
    """Prazo vencido só é motivo de recusa quando o pedido é o ÚNICO jeito de
    comer. Com a retirada presencial ligada o cardápio não fica invisível: a
    encomenda fecha e o balcão segue — que é o dia em que a feature serve.

    ⚠️ Este teste existe porque as duas metades discordavam: o editor liberava o
    botão (`invisivel` em `CardapioDoDia.tsx` exige `!aceitaPresencial`) e o
    servidor recusava, então a cantina só descobria pelo erro depois do clique.
    As duas barreiras do docs/38 §3.3.1 continuam de pé — agora com a mesma
    régua nos dois lados.
    """
    db = _banco(aceita_pedido=True, aceita_presencial=True)
    db["cardapio"]["card-1"]["pedidos_ate"] = (
        datetime.now(UTC) - timedelta(hours=20)
    ).isoformat()
    db["cardapio"]["card-1"]["publicado_em"] = None
    db["cardapio_bloco"]["b1"] = {"id": "b1", "cardapio_id": "card-1", "nome": "Prato", "ordem": 0}
    rotas = _com_banco(monkeypatch, db)

    # Mesma leitura do teste acima: chegar em "sem opção" prova que as duas
    # recusas de prazo ficaram para trás.
    with pytest.raises(HTTPException) as erro:
        asyncio.run(rotas.publicar_cardapio("card-1", _Requisicao(), CANTINA))
    assert "pelo menos uma opção" in erro.value.detail


ADMIN = {"tipo": "coordenador", "sub": "coord-1", "papel": "administrador"}


def test_criar_cantina_com_os_quatro_modos(monkeypatch):
    """A regra da casa entra no cadastro, senão ela nasce sempre no default e a
    cantina teria de ligar o presencial dia a dia, no editor (docs/40 §1)."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    corpo = rotas.NovaCantinaBody(
        nome="Copa Nova",
        aceita_pedido_almoco=True,
        aceita_pedido_janta=False,
        aceita_presencial_almoco=True,
        aceita_presencial_janta=True,
    )

    saida = asyncio.run(rotas.criar_cantina(corpo, _Requisicao(), ADMIN))

    assert saida["aceita_pedido_janta"] is False
    assert saida["aceita_presencial_almoco"] is True
    assert saida["aceita_presencial_janta"] is True


def test_criar_cantina_sem_falar_de_modo_deixa_o_default_do_banco(monkeypatch):
    """⚠️ As quatro colunas são NOT NULL: mandar `None` seria erro do banco. O
    certo para "não disse" é a chave não entrar no insert."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    saida = asyncio.run(
        rotas.criar_cantina(rotas.NovaCantinaBody(nome="Copa Nova"), _Requisicao(), ADMIN)
    )

    # A asserção é sobre o que foi ESCRITO, não sobre o que voltou: no fake a
    # linha guardada é o próprio payload, e no Postgres de verdade a resposta
    # viria com os DEFAULT já preenchidos. O que precisa valer nos dois é que
    # nenhum `None` foi enviado para uma coluna NOT NULL.
    escrita = db["cantina"][saida["id"]]
    for campo in rotas.CAMPOS_DE_MODO_DA_CASA:
        assert campo not in escrita


def test_patch_muda_um_modo_sem_zerar_os_outros(monkeypatch):
    """A razão de `None` ser "não mexi": ligar o presencial do almoço não pode
    desligar o da janta só porque o corpo não falou dela."""
    db = _banco()
    db["cantina"]["cant-1"].update(
        {
            "aceita_pedido_almoco": True,
            "aceita_pedido_janta": False,
            "aceita_presencial_almoco": False,
            "aceita_presencial_janta": True,
        }
    )
    rotas = _com_banco(monkeypatch, db)

    saida = asyncio.run(
        rotas.editar_cantina(
            "cant-1",
            rotas.EditarCantinaBody(aceita_presencial_almoco=True),
            _Requisicao(),
            ADMIN,
        )
    )

    assert saida["aceita_presencial_almoco"] is True
    assert saida["aceita_pedido_almoco"] is True
    assert saida["aceita_pedido_janta"] is False
    assert saida["aceita_presencial_janta"] is True


def test_patch_de_outro_campo_nao_toca_nos_modos(monkeypatch):
    """`None` nunca desliga: um PATCH de nome não pode apagar a regra de modos —
    seria a perda silenciosa que os `valor_*` já evitam."""
    db = _banco()
    db["cantina"]["cant-1"]["aceita_presencial_almoco"] = True
    rotas = _com_banco(monkeypatch, db)

    saida = asyncio.run(
        rotas.editar_cantina(
            "cant-1", rotas.EditarCantinaBody(nome="Copa do Bloco B"), _Requisicao(), ADMIN
        )
    )

    assert saida["nome"] == "Copa do Bloco B"
    assert saida["aceita_presencial_almoco"] is True


def test_patch_vazio_continua_recusado(monkeypatch):
    """A recusa antiga não pode ter virado "salvei nada": os campos novos são
    todos opcionais, e sem esta guarda um corpo vazio passaria a ser um UPDATE
    sem patch."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    with pytest.raises(HTTPException) as erro:
        asyncio.run(
            rotas.editar_cantina("cant-1", rotas.EditarCantinaBody(), _Requisicao(), ADMIN)
        )
    assert erro.value.status_code == 422


def test_edicao_de_modo_vai_para_a_auditoria(monkeypatch):
    """Mudar a regra da casa muda quem come sem pedir. `cantina_editada` já leva
    o patch inteiro no detalhe — este teste tranca isso para os campos novos."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)

    asyncio.run(
        rotas.editar_cantina(
            "cant-1",
            rotas.EditarCantinaBody(aceita_presencial_janta=True),
            _Requisicao(),
            ADMIN,
        )
    )

    trilha = [
        e for e in db["evento_auditoria"].values() if e.get("acao") == "cantina_editada"
    ]
    assert trilha[0]["detalhe"]["aceita_presencial_janta"] is True


def test_as_duas_leituras_devolvem_a_regra_da_casa(monkeypatch):
    """Sem isto a tela não tem como mostrar o estado atual.

    As duas rotas já liam a linha inteira (`select("*")`), então os campos novos
    vieram de graça. O que este teste tranca é o outro lado: que nenhuma das
    duas passe a montar a resposta campo a campo — como
    `editar_conta_de_cantina` faz — e deixe a regra da casa de fora.
    """
    db = _banco()
    db["cantina"]["cant-1"].update(
        {
            "aceita_pedido_almoco": True,
            "aceita_pedido_janta": True,
            "aceita_presencial_almoco": True,
            "aceita_presencial_janta": False,
        }
    )
    rotas = _com_banco(monkeypatch, db)

    da_sessao = asyncio.run(rotas.cantina_da_sessao(CANTINA))
    da_coordenacao = next(
        c for c in asyncio.run(rotas.listar_cantinas()) if c["id"] == "cant-1"
    )

    for campo in rotas.CAMPOS_DE_MODO_DA_CASA:
        assert campo in da_sessao
        assert campo in da_coordenacao
    assert da_sessao["aceita_presencial_almoco"] is True
    assert da_coordenacao["aceita_presencial_janta"] is False


def test_regra_da_casa_chega_no_cardapio_novo(monkeypatch):
    """A ponta a ponta da regra: o que a coordenação liga na cantina é o que o
    cardápio criado depois já nasce aceitando."""
    db = _banco()
    rotas = _com_banco(monkeypatch, db)
    asyncio.run(
        rotas.editar_cantina(
            "cant-1",
            rotas.EditarCantinaBody(aceita_presencial_janta=True),
            _Requisicao(),
            ADMIN,
        )
    )

    # Janta porque o almoço de hoje já existe no cenário — e é justamente a
    # refeição em que a regra foi ligada.
    novo = asyncio.run(
        rotas.criar_cardapio(
            rotas.NovoCardapioBody(data=_hoje(), refeicao="janta"), _Requisicao(), CANTINA
        )
    )

    assert novo["aceitaPresencial"] is True
    assert novo["aceitaPedido"] is True


def test_modos_pela_regra_da_casa():
    """Pré-preenchimento do cardápio novo, e os fallbacks são os DEFAULT da
    0051 — senão o modo passaria a depender da origem da linha."""
    from app.routes.cantina import _modos_pela_regra

    casa = {
        "aceita_pedido_almoco": True, "aceita_presencial_almoco": True,
        "aceita_pedido_janta": False, "aceita_presencial_janta": True,
    }
    assert _modos_pela_regra(casa, "almoco") == (True, True)
    assert _modos_pela_regra(casa, "janta") == (False, True)
    # Linha sem os campos (base anterior à 0051) vale o que o banco valeria.
    assert _modos_pela_regra({}, "almoco") == (True, False)
