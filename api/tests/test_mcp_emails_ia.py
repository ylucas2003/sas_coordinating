"""Os e-mails das contas de IA (decisão do dono de 26/10): o domínio puro e as rotas do card.

`app/mcp/emails_ia.py` é a forma do e-mail, o código de 6 dígitos, os HMAC e a
mensagem — sem I/O. `routes/mcp_emails_ia.py` é o card "Conexões de IA": cada
coordenador cadastra, lista e remove os e-mails da(s) conta(s) de IA dele. O
uso dos dois — o código que aprova a conexão OAuth — está em
tests/test_oauth_mcp.py.

Os handlers são `def` e são chamados direto, com o FakeCliente no lugar do
PostgREST (o padrão de test_mcp_rotas.py); por HTTP ficam só os guards.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_mcp_emails_ia.py -q
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.testclient import TestClient

from app import auth
from app.mcp import emails_ia, tokens
from app.routes import mcp_emails_ia
from tests.test_mcp_tokens import FakeClienteDoMcp
from tests.test_oauth_mcp import RemetenteFalso

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"

ADMIN_ID = "ad000000-0000-4000-8000-000000000001"
COORD_ID = "c0000000-0000-4000-8000-000000000002"
ADMINISTRADOR = {"sub": ADMIN_ID, "tipo": "coordenador", "papel": "administrador", "nome": "Admin"}
COORDENADOR = {"sub": COORD_ID, "tipo": "coordenador", "papel": "coordenador", "nome": "Coord"}


# ─── O domínio puro (app/mcp/emails_ia.py) ───────────────────────────────


@pytest.mark.parametrize("digitado", [
    "ana@gmail.com", "  Ana@Gmail.COM ", "ana.souza+ia@exemplo.com.br", "a@b.co", "x_y-z@sub.dominio.org",
])
def test_email_valido_depois_de_normalizar(digitado):
    email = emails_ia.normalizar_email(digitado)
    assert email == email.strip().lower() and emails_ia.email_valido(email)


@pytest.mark.parametrize("digitado", [
    "", "ana", "ana@", "@gmail.com", "ana@gmail",          # sem ponto no domínio: o SES não entrega
    "ana souza@gmail.com", "ana@@gmail.com", "ana@gmail..com", "ana@-gmail.com", "ana@gmail-.com",
    "ána@gmail.com", "ana@gmаil.com",                       # acento e o "а" cirílico
    "a" * 65 + "@gmail.com", "ana@" + "b" * 250 + ".com",
])
def test_email_invalido(digitado):
    assert not emails_ia.email_valido(emails_ia.normalizar_email(digitado))


def test_mascara_guarda_so_a_primeira_letra_e_o_dominio():
    assert emails_ia.mascarar_email("ana.lucia@exemplo.com.br") == "a***@exemplo.com.br"
    assert emails_ia.mascarar_email("sem-arroba") == "***"
    assert emails_ia.mascarar_email("@x.com") == "***"


def test_codigo_tem_seis_digitos_com_zero_a_esquerda(monkeypatch):
    codigos = {emails_ia.gerar_codigo() for _ in range(200)}
    assert all(re.fullmatch(r"\d{6}", c) for c in codigos) and len(codigos) > 190
    monkeypatch.setattr(emails_ia.secrets, "randbelow", lambda _n: 42)
    assert emails_ia.gerar_codigo() == "000042"


@pytest.mark.parametrize(("digitado", "esperado"), [
    ("123456", "123456"), (" 123 456 ", "123456"), ("123-456", "123456"), ("123.456", "123456"),
    ("12345", None), ("1234567", None), ("12a456", None), ("１２３４５６", None), ("", None),
])
def test_codigo_digitado_sem_os_separadores(digitado, esperado):
    assert emails_ia.codigo_no_formato(digitado) == esperado


def test_o_hash_do_codigo_e_preso_ao_pedido_ao_email_e_a_chave():
    chave = emails_ia.chave_dos_hashes(SEGREDO)
    email = emails_ia.hash_do_email(chave, "ana@gmail.com")
    base = emails_ia.hash_do_codigo(chave, "pedido-1", email, "123456")
    assert re.fullmatch(r"[0-9a-f]{64}", base) and re.fullmatch(r"[0-9a-f]{64}", email)
    outros = {
        emails_ia.hash_do_codigo(chave, "pedido-2", email, "123456"),
        emails_ia.hash_do_codigo(chave, "pedido-1", emails_ia.hash_do_email(chave, "bia@gmail.com"), "123456"),
        emails_ia.hash_do_codigo(chave, "pedido-1", email, "123457"),
        emails_ia.hash_do_codigo(emails_ia.chave_dos_hashes("outro-segredo"), "pedido-1", email, "123456"),
    }
    assert base not in outros and len(outros) == 4
    # Com a chave, e não sha256 puro: sem ela, o hash não diz nada a quem lê o banco.
    import hashlib

    assert email != hashlib.sha256(b"ana@gmail.com").hexdigest()
    assert emails_ia.chave_dos_hashes(SEGREDO) != emails_ia.chave_dos_hashes("outro-segredo")


def test_email_com_mais_chega_inteiro_ao_filtro_do_postgrest():
    """`ana+ia@gmail.com` é o alias mais comum de conta de IA, e o `+` já virou
    espaço numa query string deste projeto (lembretes/despachante.filtro_ts).
    O cliente de verdade, com um transporte falso, mostra a URL que sai: se uma
    atualização do postgrest-py deixar de encodar o `+`, o /codigo pararia de
    achar o cadastro calado — e este teste avisa."""
    import httpx
    from postgrest import SyncPostgrestClient

    urls: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        urls.append(str(pedido.url))
        return httpx.Response(200, json=[])

    cliente = SyncPostgrestClient("http://postgrest.invalid", schema="public")
    cliente.session = httpx.Client(base_url="http://postgrest.invalid", transport=httpx.MockTransport(responder))
    cliente.from_("email_conta_ia_mcp").select("id").eq("email", "ana+ia@gmail.com").execute()
    (url,) = urls
    assert "email=eq.ana%2Bia%40gmail.com" in url


def test_a_mensagem_leva_o_codigo_no_corpo_e_o_host_sem_o_nome_declarado():
    assunto, corpo = emails_ia.mensagem_do_codigo("004217", "claude.ai")
    assert "004217" not in assunto           # o assunto aparece na tela bloqueada
    assert re.search(r"^\s+004217\s*$", corpo, flags=re.M)
    assert "claude.ai" in corpo and "10 minutos" in corpo and "ignore este e-mail" in corpo


def test_a_mensagem_do_codigo_avisa_para_nao_compartilhar():
    """Padrão de OTP (revisão de segurança de 26/10): como aprovar não pede
    sessão e quem chama o /aprovar recebe o código do RFC, o único obstáculo
    entre um phishing e os dados dos alunos é a pessoa não entregar os seis
    dígitos — e o corpo manda nunca compartilhar nem repassar o código."""
    _, corpo = emails_ia.mensagem_do_codigo("004217", "claude.ai")
    baixo = corpo.lower()
    assert "compartilh" in baixo and "repass" in baixo


def test_o_hash_da_confirmacao_e_preso_ao_cadastro_e_separado_do_de_aprovar():
    """O código que confirma um cadastro não confirma outro — nem o mesmo
    endereço cadastrado de novo — e não se confunde com o de aprovar, que usa
    a mesma chave."""
    chave = emails_ia.chave_dos_hashes(SEGREDO)
    base = emails_ia.hash_da_confirmacao(chave, "id-1", "ana@gmail.com", "123456")
    assert re.fullmatch(r"[0-9a-f]{64}", base)
    outros = {
        emails_ia.hash_da_confirmacao(chave, "id-2", "ana@gmail.com", "123456"),
        emails_ia.hash_da_confirmacao(chave, "id-1", "bia@gmail.com", "123456"),
        emails_ia.hash_da_confirmacao(chave, "id-1", "ana@gmail.com", "123457"),
        emails_ia.hash_da_confirmacao(emails_ia.chave_dos_hashes("outro-segredo"), "id-1", "ana@gmail.com", "123456"),
        emails_ia.hash_do_codigo(chave, "id-1", "ana@gmail.com", "123456"),
    }
    assert base not in outros and len(outros) == 5


def test_a_mensagem_de_confirmacao_diz_o_que_confirmar_significa():
    """Quem recebeu o código por engano (o e-mail digitado errado) precisa ler
    que confirmar dá acesso aos dados do SAS — é o que o faz não repassar."""
    assunto, corpo = emails_ia.mensagem_de_confirmacao("004217")
    assert "004217" not in assunto and "confirmar" in assunto.lower()
    assert re.search(r"^\s+004217\s*$", corpo, flags=re.M)
    assert "10 minutos" in corpo and "Conexões de IA" in corpo
    assert "quem lê esta caixa conecta uma IA aos dados do SAS" in corpo
    assert "não digite nem repasse o código" in corpo


# ─── As rotas do card ────────────────────────────────────────────────────


def _contas() -> dict:
    return {
        "usuario_coordenacao": {
            ADMIN_ID: {"id": ADMIN_ID, "nome": "Admin da Casa", "papel": "administrador", "ativo": True},
            COORD_ID: {"id": COORD_ID, "nome": "Coordenadora", "papel": "coordenador", "ativo": True},
        },
        "email_conta_ia_mcp": {},
        "evento_auditoria": {},
    }


@pytest.fixture
def banco(monkeypatch) -> dict:
    db = _contas()
    monkeypatch.setattr(mcp_emails_ia, "get_supabase", lambda: FakeClienteDoMcp(db))
    monkeypatch.setattr(auth, "get_supabase", lambda: FakeClienteDoMcp(db))
    return db


@pytest.fixture(autouse=True)
def remetente(monkeypatch) -> RemetenteFalso:
    """O SES de mentira: o código de confirmação fica aqui em vez de sair, e é
    daqui que os testes o leem, como a pessoa o leria na caixa de entrada."""
    falso = RemetenteFalso()
    monkeypatch.setattr(mcp_emails_ia, "email_ses", falso)
    return falso


@pytest.fixture(autouse=True)
def _tetos_zerados():
    """Os tetos do código de confirmação são do processo: um teste não pode
    gastar a cota do outro."""
    tetos = (mcp_emails_ia.TETO_DE_CODIGOS_POR_CONTA, mcp_emails_ia.TETO_DE_CODIGOS_POR_EMAIL)
    for teto in tetos:
        teto.limpar()
    yield
    for teto in tetos:
        teto.limpar()


class _Pedido:
    def __init__(self, ip: str | None = "203.0.113.7"):
        self.client = type("C", (), {"host": ip})()


def _cadastrar(email: str, sessao: dict = COORDENADOR) -> mcp_emails_ia.EmailDaIa:
    return mcp_emails_ia.cadastrar_email(mcp_emails_ia.CadastrarEmailBody(email=email), _Pedido(), sessao)


def _remover(email_id: str, sessao: dict = COORDENADOR) -> mcp_emails_ia.EmailDaIaRemovido:
    return mcp_emails_ia.remover_email(email_id, _Pedido(), sessao)


def _confirmar_com(email_id: str, codigo: str, sessao: dict = COORDENADOR) -> mcp_emails_ia.EmailDaIa:
    return mcp_emails_ia.confirmar_email(email_id, mcp_emails_ia.ConfirmarEmailBody(codigo=codigo), _Pedido(), sessao)


def _confirmar(remetente: RemetenteFalso, criado: mcp_emails_ia.EmailDaIa, sessao: dict = COORDENADOR):
    """O passo do card: o código que chegou ao e-mail, digitado por quem o cadastrou."""
    return _confirmar_com(criado.id, remetente.ultimo_codigo(criado.email), sessao)


def _reenviar(email_id: str, sessao: dict = COORDENADOR) -> mcp_emails_ia.CodigoDeConfirmacao:
    return mcp_emails_ia.reenviar_codigo(email_id, _Pedido(), sessao)


def _codigo_errado(certo: str) -> str:
    return f"{(int(certo) + 1) % 10**6:06d}"


def _status(chamada) -> int:
    with pytest.raises(HTTPException) as erro:
        chamada()
    return erro.value.status_code


def test_cadastrar_normaliza_e_responde_no_formato_do_contrato(banco):
    criado = _cadastrar("  Coord.IA@Gmail.com ")
    assert set(criado.model_dump()) == {"id", "email", "criadoEm", "confirmadoEm", "ultimoUsoEm"}
    assert criado.email == "coord.ia@gmail.com" and criado.ultimoUsoEm is None
    (linha,) = banco["email_conta_ia_mcp"].values()
    assert linha["usuario_coordenacao_id"] == COORD_ID and linha["email"] == "coord.ia@gmail.com"
    assert linha["criado_em"].endswith("Z") and linha.get("removido_em") is None


def test_cadastrar_nasce_aguardando_e_manda_o_codigo_so_ao_email(banco, remetente):
    """A prova de posse (revisão de segurança de 26/10): o cadastro não vale
    nada até o código que chegou a ele voltar pelo card. O código só existe na
    caixa: o banco guarda o HMAC, preso a este cadastro, com prazo de 10 min."""
    criado = _cadastrar("coord.ia@gmail.com")
    assert criado.confirmadoEm is None
    (enviado,) = remetente.enviados
    assert enviado["destinatario"] == "coord.ia@gmail.com" and "confirmar" in enviado["assunto"].lower()
    codigo = remetente.ultimo_codigo("coord.ia@gmail.com")
    linha = banco["email_conta_ia_mcp"][criado.id]
    assert re.fullmatch(r"[0-9a-f]{64}", linha["hash_codigo_de_confirmacao"])
    assert linha["hash_codigo_de_confirmacao"] == emails_ia.hash_da_confirmacao(
        emails_ia.chave_dos_hashes(mcp_emails_ia.get_settings().jwt_secret_key), criado.id, "coord.ia@gmail.com", codigo
    )
    assert linha["confirmacao_expira_em"].endswith("Z") and linha["tentativas_de_confirmacao"] == 0
    assert codigo not in json.dumps(banco, default=str)
    # O que vai ao card não leva nada do código.
    assert "hash" not in json.dumps(criado.model_dump()) and codigo not in json.dumps(criado.model_dump())


def test_confirmar_com_o_codigo_certo_tira_o_hash_e_audita(banco, remetente):
    criado = _cadastrar("coord.ia@gmail.com")
    confirmado = _confirmar(remetente, criado)
    assert confirmado.id == criado.id and confirmado.confirmadoEm is not None
    linha = banco["email_conta_ia_mcp"][criado.id]
    assert linha["confirmado_em"] == confirmado.confirmadoEm and linha["confirmado_em"].endswith("Z")
    assert linha["hash_codigo_de_confirmacao"] is None and linha["confirmacao_expira_em"] is None
    eventos = [e for e in banco["evento_auditoria"].values() if e["acao"] == mcp_emails_ia.ACAO_EMAIL_CONFIRMADO]
    assert len(eventos) == 1 and eventos[0]["detalhe"] == {"email": "c***@gmail.com"}
    assert eventos[0]["ator_id"] == COORD_ID and eventos[0]["recurso"] == f"email_conta_ia/{criado.id}"
    # De novo: o mesmo item, sem segundo evento — o código já nem existe.
    assert _confirmar_com(criado.id, "000000").confirmadoEm == confirmado.confirmadoEm
    assert sum(e["acao"] == mcp_emails_ia.ACAO_EMAIL_CONFIRMADO for e in banco["evento_auditoria"].values()) == 1
    assert [e.confirmadoEm for e in mcp_emails_ia.listar_emails(COORDENADOR)] == [confirmado.confirmadoEm]


def test_codigo_errado_vencido_ou_sem_tentativas_nao_confirma(banco, remetente):
    criado = _cadastrar("coord.ia@gmail.com")
    certo = remetente.ultimo_codigo("coord.ia@gmail.com")
    linha = banco["email_conta_ia_mcp"][criado.id]
    # Fora do formato não gasta tentativa: não chega a comparar.
    assert _status(lambda: _confirmar_com(criado.id, "12345")) == 400
    assert linha["tentativas_de_confirmacao"] == 0
    for _ in range(emails_ia.TENTATIVAS_POR_CODIGO):
        assert _status(lambda: _confirmar_com(criado.id, _codigo_errado(certo))) == 400
    assert linha["tentativas_de_confirmacao"] == emails_ia.TENTATIVAS_POR_CODIGO == 5
    # Esgotadas, nem o certo confirma.
    assert _status(lambda: _confirmar_com(criado.id, certo)) == 400
    assert linha.get("confirmado_em") is None

    # Vencido também não, mesmo o certo e com tentativas sobrando.
    outro = _cadastrar("coord.chatgpt@gmail.com")
    certo = remetente.ultimo_codigo("coord.chatgpt@gmail.com")
    banco["email_conta_ia_mcp"][outro.id]["confirmacao_expira_em"] = "2026-01-01T00:00:00.000000Z"
    assert _status(lambda: _confirmar_com(outro.id, certo)) == 400
    assert banco["email_conta_ia_mcp"][outro.id].get("confirmado_em") is None
    assert not any(e["acao"] == mcp_emails_ia.ACAO_EMAIL_CONFIRMADO for e in banco["evento_auditoria"].values())


class _AntesDeGastar(FakeClienteDoMcp):
    """O cliente em que alguma coisa acontece entre ler o cadastro e gastar a
    tentativa — o outro chute, a outra aba (o `_ComCorrida` de test_oauth_mcp)."""

    def __init__(self, db: dict, antes):
        super().__init__(db)
        self._antes = antes

    def table(self, nome):
        tabela = super().table(nome)
        original = tabela.update

        def update(dados, **kw):
            if "tentativas_de_confirmacao" in dados and self._antes:
                antes, self._antes = self._antes, None
                antes()
            return original(dados, **kw)

        tabela.update = update
        return tabela


def test_a_tentativa_e_gasta_antes_de_comparar_na_confirmacao(banco, remetente, monkeypatch):
    """Dez chutes ao mesmo tempo não viram dez comparações: quem perde a vez de
    gastar a tentativa não compara — nem com o código certo."""
    criado = _cadastrar("coord.ia@gmail.com")
    certo = remetente.ultimo_codigo("coord.ia@gmail.com")
    linha = banco["email_conta_ia_mcp"][criado.id]

    def outro_chute_gastou_a_vez():
        linha["tentativas_de_confirmacao"] += 1

    corrida = _AntesDeGastar(banco, outro_chute_gastou_a_vez)
    monkeypatch.setattr(mcp_emails_ia, "get_supabase", lambda: corrida)
    assert _status(lambda: _confirmar_com(criado.id, certo)) == 400
    assert linha.get("confirmado_em") is None
    monkeypatch.setattr(mcp_emails_ia, "get_supabase", lambda: FakeClienteDoMcp(banco))
    assert _confirmar_com(criado.id, certo).confirmadoEm is not None
    assert linha["tentativas_de_confirmacao"] == 2


def test_outra_aba_que_confirmou_antes_devolve_o_item_sem_segundo_evento(banco, remetente, monkeypatch):
    """Duas abas da MESMA conta confirmando juntas: a segunda recebe o item
    confirmado, e não um 409 de "outro dono" nem um 400."""
    criado = _cadastrar("coord.ia@gmail.com")
    certo = remetente.ultimo_codigo("coord.ia@gmail.com")

    def a_outra_aba_confirmou():
        # Pelo MESMO cliente, já desarmado: a outra aba não tem corrida nenhuma.
        _confirmar_com(criado.id, certo)

    corrida = _AntesDeGastar(banco, a_outra_aba_confirmou)
    monkeypatch.setattr(mcp_emails_ia, "get_supabase", lambda: corrida)
    devolvido = _confirmar_com(criado.id, certo)
    assert devolvido.confirmadoEm == banco["email_conta_ia_mcp"][criado.id]["confirmado_em"]
    assert sum(e["acao"] == mcp_emails_ia.ACAO_EMAIL_CONFIRMADO for e in banco["evento_auditoria"].values()) == 1


def test_quem_digita_o_codigo_de_um_cadastro_nao_confirma_outro(banco, remetente):
    """O código é preso ao CADASTRO: removido e cadastrado de novo, o mesmo
    endereço ganha outro código, e o antigo não vale para ele."""
    antigo = _cadastrar("coord.ia@gmail.com")
    codigo_antigo = remetente.ultimo_codigo("coord.ia@gmail.com")
    _remover(antigo.id)
    assert _status(lambda: _confirmar_com(antigo.id, codigo_antigo)) == 404
    novo = _cadastrar("coord.ia@gmail.com")
    if codigo_antigo != remetente.ultimo_codigo("coord.ia@gmail.com"):   # um em um milhão: o mesmo número
        assert _status(lambda: _confirmar_com(novo.id, codigo_antigo)) == 400
    assert _confirmar(remetente, novo).confirmadoEm is not None


def test_reenviar_mata_o_codigo_anterior_e_zera_as_tentativas(banco, remetente):
    criado = _cadastrar("coord.ia@gmail.com")
    primeiro = remetente.ultimo_codigo("coord.ia@gmail.com")
    assert _status(lambda: _confirmar_com(criado.id, _codigo_errado(primeiro))) == 400
    assert _reenviar(criado.id).model_dump() == {"enviado": True}
    segundo = remetente.ultimo_codigo("coord.ia@gmail.com")
    assert len(remetente.para("coord.ia@gmail.com")) == 2
    assert banco["email_conta_ia_mcp"][criado.id]["tentativas_de_confirmacao"] == 0
    if primeiro != segundo:
        assert _status(lambda: _confirmar_com(criado.id, primeiro)) == 400
    assert _confirmar_com(criado.id, segundo).confirmadoEm is not None
    # Confirmado, não há o que reenviar.
    assert _status(lambda: _reenviar(criado.id)) == 409
    assert len(remetente.para("coord.ia@gmail.com")) == 2


@pytest.mark.parametrize("quem", [COORDENADOR, ADMINISTRADOR], ids=["coordenador", "administrador"])
def test_confirmar_ou_reenviar_o_de_outra_conta_e_404(banco, remetente, quem):
    """Quem lê a caixa não confirma por outra sessão: o cadastro alheio é 404,
    como na remoção — e nem o código certo muda isso."""
    dono = ADMINISTRADOR if quem is COORDENADOR else COORDENADOR
    alheio = _cadastrar("dono@gmail.com", dono)
    certo = remetente.ultimo_codigo("dono@gmail.com")
    assert _status(lambda: _confirmar_com(alheio.id, certo, quem)) == 404
    assert _status(lambda: _reenviar(alheio.id, quem)) == 404
    assert banco["email_conta_ia_mcp"][alheio.id].get("confirmado_em") is None
    assert len(remetente.para("dono@gmail.com")) == 1


def test_tetos_do_codigo_de_confirmacao(banco, remetente, monkeypatch):
    """Cada código é um e-mail da escola para um endereço que alguém digitou:
    por conta, por hora, e por e-mail, por dia, venha de que conta vier."""
    monkeypatch.setattr(mcp_emails_ia, "CODIGOS_POR_EMAIL_POR_DIA", 2)
    criado = _cadastrar("coord.ia@gmail.com")
    _reenviar(criado.id)
    assert _status(lambda: _reenviar(criado.id)) == 429
    _remover(criado.id)
    # O teto é do ENDEREÇO: cadastrar de novo, ou por outra conta, não o zera.
    assert _status(lambda: _cadastrar("coord.ia@gmail.com", ADMINISTRADOR)) == 429
    assert len(remetente.para("coord.ia@gmail.com")) == 2

    monkeypatch.setattr(mcp_emails_ia, "CODIGOS_POR_CONTA_POR_HORA", 3)
    mcp_emails_ia.TETO_DE_CODIGOS_POR_CONTA.limpar()
    for i in range(3):
        _cadastrar(f"outro{i}@gmail.com")
    assert _status(lambda: _cadastrar("mais.um@gmail.com")) == 429
    assert remetente.para("mais.um@gmail.com") == []
    assert not any(e["email"] == "mais.um@gmail.com" for e in banco["email_conta_ia_mcp"].values())


@pytest.mark.parametrize("app_env", ["production", "test"])
def test_sem_ses_fora_de_dev_fica_aguardando_e_e_503_sem_o_codigo_no_log(banco, monkeypatch, caplog, app_env):
    """Ninguém confirma sem o código, e fora de dev ele NUNCA vai ao log. O
    cadastro fica na lista, aguardando, para o "enviar outro" de depois."""
    from types import SimpleNamespace

    monkeypatch.setattr(mcp_emails_ia, "email_ses", RemetenteFalso(configurado=False))
    monkeypatch.setattr(mcp_emails_ia, "gerar_codigo", lambda: "731942")
    monkeypatch.setattr(
        mcp_emails_ia, "get_settings", lambda: SimpleNamespace(app_env=app_env, jwt_secret_key=SEGREDO)
    )
    with caplog.at_level("DEBUG"):
        assert _status(lambda: _cadastrar("coord.ia@gmail.com")) == 503
    assert not any("731942" in r.getMessage() for r in caplog.records)
    assert any(r.levelname == "ERROR" and "SES não configurado" in r.getMessage() for r in caplog.records)
    (pendente,) = mcp_emails_ia.listar_emails(COORDENADOR)
    assert pendente.email == "coord.ia@gmail.com" and pendente.confirmadoEm is None
    assert _status(lambda: _reenviar(pendente.id)) == 503


def test_sem_ses_em_dev_o_codigo_vai_ao_log_mascarado(banco, monkeypatch, caplog):
    monkeypatch.setattr(mcp_emails_ia, "email_ses", RemetenteFalso(configurado=False))
    monkeypatch.setattr(mcp_emails_ia, "gerar_codigo", lambda: "731942")
    with caplog.at_level("INFO", logger="sas.mcp.emails_ia"):
        criado = _cadastrar("coord.ia@gmail.com")
    mensagens = [r.getMessage() for r in caplog.records]
    assert any("[DEV]" in m and "731942" in m and "c***@gmail.com" in m for m in mensagens)
    assert not any("coord.ia@gmail.com" in m for m in mensagens)
    assert _confirmar_com(criado.id, "731942").confirmadoEm is not None


def test_erro_do_ses_vai_ao_log_sem_o_endereco_e_o_cadastro_fica_aguardando(banco, monkeypatch, caplog):
    """A recusa do SES em sandbox (MessageRejected) traz o endereço inteiro na
    mensagem; o log guarda só o tipo do erro e o e-mail mascarado."""

    class _SesQueRecusa(RemetenteFalso):
        def enviar_email(self, *, destinatario: str, assunto: str, corpo: str) -> None:
            raise RuntimeError(f"Email address is not verified: {destinatario}")

    monkeypatch.setattr(mcp_emails_ia, "email_ses", _SesQueRecusa())
    with caplog.at_level("INFO"):
        assert _status(lambda: _cadastrar("coord.ia@gmail.com")) == 503
    assert not any("coord.ia@gmail.com" in r.getMessage() for r in caplog.records)
    assert any("[AÇÃO NECESSÁRIA]" in r.getMessage() and "RuntimeError" in r.getMessage() for r in caplog.records)
    assert [e.confirmadoEm for e in mcp_emails_ia.listar_emails(COORDENADOR)] == [None]


def test_cadastrar_audita_com_o_email_mascarado(banco):
    criado = _cadastrar("coord.ia@gmail.com")
    (evento,) = banco["evento_auditoria"].values()
    assert evento["acao"] == mcp_emails_ia.ACAO_EMAIL_CADASTRADO and evento["canal"] == "mcp"
    assert evento["ator_tipo"] == "coordenador" and evento["ator_id"] == COORD_ID
    assert evento["recurso"] == f"email_conta_ia/{criado.id}" and evento["ip"] == "203.0.113.7"
    assert evento["detalhe"] == {"email": "c***@gmail.com"}
    assert "coord.ia@gmail.com" not in json.dumps(evento, default=str)


@pytest.mark.parametrize("email", ["", "coord", "coord@gmail", "coord ia@gmail.com", "x" * 400 + "@gmail.com"])
def test_email_invalido_e_recusado_no_corpo(email):
    with pytest.raises(ValidationError):
        mcp_emails_ia.CadastrarEmailBody(email=email)


@pytest.mark.parametrize("quem", [COORDENADOR, ADMINISTRADOR], ids=["a-mesma-conta", "outra-conta"])
def test_email_confirmado_em_qualquer_conta_e_409(banco, remetente, quem):
    """Um e-mail aprova em nome de UMA conta só (0073)."""
    _confirmar(remetente, _cadastrar("coord.ia@gmail.com"))
    with pytest.raises(HTTPException) as erro:
        _cadastrar("COORD.ia@gmail.com", quem)
    assert erro.value.status_code == 409
    assert len(banco["email_conta_ia_mcp"]) == 1
    assert len(remetente.para("coord.ia@gmail.com")) == 1


def test_o_que_aguarda_tranca_so_a_propria_conta(banco, remetente):
    """O que só aguarda não aprova nada. Na mesma conta, o segundo cadastro do
    endereço é 409 — o card já mostra o primeiro, com o campo do código. Em
    OUTRA conta ele entra: quem digitou o e-mail de outra pessoa não pode
    impedir o dono da caixa de cadastrá-lo. Fica com ele quem confirmar
    primeiro; a outra confirmação é 409."""
    da_coord = _cadastrar("caixa@gmail.com")
    assert _status(lambda: _cadastrar("caixa@gmail.com")) == 409
    do_admin = _cadastrar("caixa@gmail.com", ADMINISTRADOR)
    codigo_da_coord, codigo_do_admin = (
        re.findall(r"^\s+(\d{6})\s*$", e["corpo"], flags=re.M)[0] for e in remetente.para("caixa@gmail.com")
    )
    assert _confirmar_com(do_admin.id, codigo_do_admin, ADMINISTRADOR).confirmadoEm is not None
    assert _status(lambda: _confirmar_com(da_coord.id, codigo_da_coord)) == 409
    assert banco["email_conta_ia_mcp"][da_coord.id].get("confirmado_em") is None
    assert _status(lambda: _cadastrar("caixa@gmail.com")) == 409


def _remocoes(banco: dict) -> list[dict]:
    return [e for e in banco["evento_auditoria"].values() if e["acao"] == mcp_emails_ia.ACAO_EMAIL_REMOVIDO]


def test_email_preso_em_conta_desativada_e_liberado_pelo_cadastro(banco, remetente):
    """O e-mail confirmado de uma conta DESATIVADA não aprova mais nada, e
    ninguém o liberava: era 409 para sempre. O cadastro o libera — remove sem
    apagar, audita com o e-mail mascarado — e segue o caminho de sempre: o
    novo nasce aguardando, e só vale com o código que chegou à caixa. Com a
    conta ATIVA, continua 409."""
    antigo = _cadastrar("caixa@gmail.com", ADMINISTRADOR)
    _confirmar(remetente, antigo, ADMINISTRADOR)
    assert _status(lambda: _cadastrar("caixa@gmail.com")) == 409

    banco["usuario_coordenacao"][ADMIN_ID]["ativo"] = False
    novo = _cadastrar("caixa@gmail.com")
    assert novo.id != antigo.id and novo.confirmadoEm is None
    assert banco["email_conta_ia_mcp"][antigo.id]["removido_em"] is not None
    assert len(banco["email_conta_ia_mcp"]) == 2                      # nunca apagar
    (evento,) = _remocoes(banco)
    assert evento["recurso"] == f"email_conta_ia/{antigo.id}" and evento["ator_id"] == COORD_ID
    assert evento["detalhe"] == {"email": "c***@gmail.com", "motivo": mcp_emails_ia.MOTIVO_CONTA_DESATIVADA}
    assert "caixa@gmail.com" not in json.dumps(evento, default=str)
    # A posse ainda se prova: o código foi para a caixa, e confirmar vale.
    assert _confirmar(remetente, novo).confirmadoEm is not None


def test_conta_desativada_depois_do_cadastro_e_liberada_na_confirmacao(banco, remetente):
    """A coordenadora cadastra enquanto o e-mail só aguarda na outra conta (não
    tranca); a outra confirma primeiro e depois é desativada. Sem liberar na
    confirmação, o índice da 0073 recusaria a dela, e cadastrar de novo é 409
    na própria conta — presa sem saída."""
    do_admin = _cadastrar("caixa@gmail.com", ADMINISTRADOR)
    da_coord = _cadastrar("caixa@gmail.com")
    codigo_do_admin, codigo_da_coord = (
        re.findall(r"^\s+(\d{6})\s*$", e["corpo"], flags=re.M)[0] for e in remetente.para("caixa@gmail.com")
    )
    _confirmar_com(do_admin.id, codigo_do_admin, ADMINISTRADOR)
    banco["usuario_coordenacao"][ADMIN_ID]["ativo"] = False
    assert _confirmar_com(da_coord.id, codigo_da_coord).confirmadoEm is not None
    assert banco["email_conta_ia_mcp"][do_admin.id]["removido_em"] is not None
    (evento,) = _remocoes(banco)
    assert evento["detalhe"]["motivo"] == mcp_emails_ia.MOTIVO_CONTA_DESATIVADA


def test_conta_desativada_nao_cadastra_confirma_nem_reenvia_mas_lista_e_remove(banco, remetente):
    """A classe do defeito da emissão (prova de ponta a ponta de 27/10), no
    card: com o JWT de 8 h que tinha, a conta desativada cadastrava, confirmava
    e pedia outro código. O e-mail confirmado assim não aprova nada enquanto a
    conta está desativada (o /codigo e o /aprovar releem a conta), mas passaria
    a aprovar se ela fosse reativada. As três rotas que dão ao e-mail o poder de
    aprovar releem a conta na tabela: 403, sem gravar nem enviar nada. Listar e
    remover só tiram acesso, e ficam abertas."""
    aguardando = _cadastrar("coord.ia@gmail.com")
    certo = remetente.ultimo_codigo("coord.ia@gmail.com")
    banco["usuario_coordenacao"][COORD_ID]["ativo"] = False
    enviados = len(remetente.enviados)

    for chamada in (
        lambda: _cadastrar("outro.ia@gmail.com"),
        lambda: _confirmar_com(aguardando.id, certo),
        lambda: _reenviar(aguardando.id),
    ):
        with pytest.raises(HTTPException) as erro:
            chamada()
        assert erro.value.status_code == 403
        assert erro.value.detail == auth.MENSAGEM_CONTA_DESATIVADA
    assert len(remetente.enviados) == enviados
    emails = [linha["email"] for linha in banco["email_conta_ia_mcp"].values()]
    assert emails == ["coord.ia@gmail.com"]
    linha = banco["email_conta_ia_mcp"][aguardando.id]
    assert linha.get("confirmado_em") is None and linha["tentativas_de_confirmacao"] == 0
    acoes = [evento["acao"] for evento in banco["evento_auditoria"].values()]
    assert acoes == [mcp_emails_ia.ACAO_EMAIL_CADASTRADO]

    # Tirar acesso nunca depende de poder dar acesso.
    assert [e.id for e in mcp_emails_ia.listar_emails(COORDENADOR)] == [aguardando.id]
    assert _remover(aguardando.id).removidoEm is not None


def test_email_removido_pode_voltar_por_qualquer_conta(banco):
    antigo = _cadastrar("coord.ia@gmail.com")
    _remover(antigo.id)
    novo = _cadastrar("coord.ia@gmail.com", ADMINISTRADOR)
    assert novo.id != antigo.id
    # Nunca apagar: a removida continua lá, e é ela que o código antigo aponta.
    assert len(banco["email_conta_ia_mcp"]) == 2


@pytest.mark.parametrize("indice", [mcp_emails_ia._INDICE_DO_EMAIL_CONFIRMADO, mcp_emails_ia._INDICE_DO_EMAIL_NA_CONTA])
def test_dois_cadastros_ao_mesmo_tempo_o_indice_recusa_o_segundo_com_409(banco, remetente, monkeypatch, indice):
    """Os dois passam pela conferência; um dos índices parciais da 0073 recusa
    o segundo, e é pelo NOME dele que a rota o reconhece. Gravar vem antes de
    enviar: o recusado não manda código nenhum."""

    class _IndiceRecusa(FakeClienteDoMcp):
        def table(self, nome):
            tabela = super().table(nome)

            def insert(*_a, **_k):
                raise RuntimeError(f'duplicate key value violates unique constraint "{indice}"')

            tabela.insert = insert
            return tabela

    monkeypatch.setattr(mcp_emails_ia, "get_supabase", lambda: _IndiceRecusa(banco))
    with pytest.raises(HTTPException) as erro:
        _cadastrar("coord.ia@gmail.com")
    assert erro.value.status_code == 409
    assert banco["evento_auditoria"] == {} and remetente.enviados == []


def test_duas_confirmacoes_ao_mesmo_tempo_o_indice_recusa_a_segunda_com_409(banco, remetente, monkeypatch):
    """O mesmo endereço aguardando em duas contas, e as duas confirmações
    passando juntas pela conferência: o índice dos confirmados recusa a
    segunda, e ela vira 409 — sem evento de confirmação."""
    criado = _cadastrar("coord.ia@gmail.com")
    certo = remetente.ultimo_codigo("coord.ia@gmail.com")

    class _IndiceRecusa(FakeClienteDoMcp):
        def table(self, nome):
            tabela = super().table(nome)
            original = tabela.update

            def update(dados, **kw):
                if "confirmado_em" in dados:
                    raise RuntimeError(
                        f'duplicate key value violates unique constraint "{mcp_emails_ia._INDICE_DO_EMAIL_CONFIRMADO}"'
                    )
                return original(dados, **kw)

            tabela.update = update
            return tabela

    monkeypatch.setattr(mcp_emails_ia, "get_supabase", lambda: _IndiceRecusa(banco))
    assert _status(lambda: _confirmar_com(criado.id, certo)) == 409
    assert not any(e["acao"] == mcp_emails_ia.ACAO_EMAIL_CONFIRMADO for e in banco["evento_auditoria"].values())


def test_outra_falha_do_banco_no_cadastro_sobe(banco, remetente, monkeypatch):
    class _Fora(FakeClienteDoMcp):
        def table(self, nome):
            tabela = super().table(nome)

            def insert(*_a, **_k):
                raise RuntimeError("PostgREST fora")

            tabela.insert = insert
            return tabela

    monkeypatch.setattr(mcp_emails_ia, "get_supabase", lambda: _Fora(banco))
    with pytest.raises(RuntimeError, match="PostgREST fora"):
        _cadastrar("coord.ia@gmail.com")
    assert remetente.enviados == []


def test_teto_de_emails_por_conta(banco):
    for i in range(mcp_emails_ia.MAXIMO_DE_EMAILS_POR_CONTA):
        _cadastrar(f"coord{i}@gmail.com")
    with pytest.raises(HTTPException) as erro:
        _cadastrar("mais.um@gmail.com")
    assert erro.value.status_code == 400
    # Removido não conta: o teto é dos ATIVOS.
    _remover(next(iter(banco["email_conta_ia_mcp"])))
    assert _cadastrar("mais.um@gmail.com").email == "mais.um@gmail.com"


def test_listar_traz_so_os_ativos_da_propria_conta(banco):
    primeiro = _cadastrar("coord.ia@gmail.com")
    segundo = _cadastrar("coord.chatgpt@gmail.com")
    removido = _cadastrar("coord.velho@gmail.com")
    _remover(removido.id)
    do_admin = _cadastrar("admin.ia@gmail.com", ADMINISTRADOR)
    assert [e.id for e in mcp_emails_ia.listar_emails(COORDENADOR)] == [primeiro.id, segundo.id]
    # O administrador também só vê os dele: o que ele vê de todos são as conexões.
    assert [e.id for e in mcp_emails_ia.listar_emails(ADMINISTRADOR)] == [do_admin.id]


def test_remover_preenche_removido_em_audita_e_nao_apaga(banco):
    criado = _cadastrar("coord.ia@gmail.com")
    removido = _remover(criado.id)
    assert set(removido.model_dump()) == {"id", "removidoEm"} and removido.id == criado.id
    linha = banco["email_conta_ia_mcp"][criado.id]
    assert linha["removido_em"] == removido.removidoEm
    eventos = [e for e in banco["evento_auditoria"].values() if e["acao"] == mcp_emails_ia.ACAO_EMAIL_REMOVIDO]
    assert len(eventos) == 1 and eventos[0]["detalhe"] == {"email": "c***@gmail.com"}
    # De novo: o mesmo instante, sem segundo evento.
    assert _remover(criado.id).removidoEm == removido.removidoEm
    assert sum(e["acao"] == mcp_emails_ia.ACAO_EMAIL_REMOVIDO for e in banco["evento_auditoria"].values()) == 1


@pytest.mark.parametrize("quem", [COORDENADOR, ADMINISTRADOR], ids=["coordenador", "administrador"])
def test_email_de_outra_conta_e_404_para_qualquer_um(banco, quem):
    """404, e não 403, como a conexão alheia em mcp_tokens: "existe, mas não é
    seu" já contaria quem cadastrou o quê."""
    sessao_do_dono = ADMINISTRADOR if quem is COORDENADOR else COORDENADOR
    alheio = _cadastrar("dono@gmail.com", sessao_do_dono)
    with pytest.raises(HTTPException) as erro:
        _remover(alheio.id, quem)
    assert erro.value.status_code == 404
    assert banco["email_conta_ia_mcp"][alheio.id].get("removido_em") is None


@pytest.mark.parametrize("email_id", ["nao-e-uuid", "1; drop table", "e1000000-0000-4000-8000-00000000ffff"])
def test_id_torto_ou_inexistente_e_404(banco, email_id):
    with pytest.raises(HTTPException) as erro:
        _remover(email_id)
    assert erro.value.status_code == 404


# ─── O piso das rotas e os guards por HTTP ───────────────────────────────

PISO_ESPERADO = {
    ("GET", "/mcp/emails-ia"): "coordenador",
    ("POST", "/mcp/emails-ia"): "coordenador",
    # Confirmar e pedir outro código são do card, com sessão (regra 0): é a
    # sessão que diz em nome de quem o e-mail passa a aprovar.
    ("POST", "/mcp/emails-ia/{email_id}/confirmar"): "coordenador",
    ("POST", "/mcp/emails-ia/{email_id}/reenviar"): "coordenador",
    ("POST", "/mcp/emails-ia/{email_id}/remover"): "coordenador",
}


def _piso(rota) -> str:
    """O guard mais alto que a rota atravessa — a régua de test_papeis.py."""
    nomes, pilha = set(), [rota.dependant]
    while pilha:
        dependencia = pilha.pop()
        if dependencia.call is not None:
            nomes.add(getattr(dependencia.call, "__name__", ""))
        pilha.extend(dependencia.dependencies)
    if "get_current_administrador" in nomes:
        return "administrador"
    if "get_current_coordenador" in nomes:
        return "coordenador"
    return "SEM GUARD"


def test_matriz_das_rotas_dos_emails_da_ia():
    """Cadastrar é de qualquer conta da coordenação: um e-mail sozinho não dá
    acesso a nada, e o portão do administrador, quando ligado, vale no
    /codigo e no /aprovar (routes/oauth_mcp.py)."""
    assert {(sorted(r.methods)[0], r.path): _piso(r) for r in mcp_emails_ia.router.routes} == PISO_ESPERADO


@pytest.fixture
def api(monkeypatch, banco):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    from app.main import create_app

    yield TestClient(create_app())
    get_settings.cache_clear()


@pytest.mark.parametrize("claims", [
    {"sub": "a-1", "tipo": "aluno", "aluno_id": "a-1"},
    {"sub": "k-1", "tipo": "cantina", "cantina_id": "ct-1"},
], ids=["aluno", "cantina"])
def test_aluno_e_cantina_nao_chegam_aos_emails(api, banco, claims):
    cabecalho = {"Authorization": f"Bearer {auth.criar_token(claims)}"}
    assert api.get("/mcp/emails-ia", headers=cabecalho).status_code == 403
    assert api.post("/mcp/emails-ia", json={"email": "x@gmail.com"}, headers=cabecalho).status_code == 403
    assert banco["email_conta_ia_mcp"] == {}


def test_sem_sessao_ou_com_token_do_mcp_e_401(api, banco):
    assert api.get("/mcp/emails-ia").status_code == 401
    token, _, _ = tokens.gerar()
    assert api.get("/mcp/emails-ia", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_pelo_http_com_sessao_da_coordenacao(api, banco, remetente):
    sessao = {"Authorization": f"Bearer {auth.criar_token(COORDENADOR)}"}
    criado = api.post("/mcp/emails-ia", json={"email": "Coord.IA@gmail.com"}, headers=sessao)
    assert criado.status_code == 201 and criado.json()["email"] == "coord.ia@gmail.com"
    assert criado.json()["confirmadoEm"] is None
    assert api.post("/mcp/emails-ia", json={"email": "coord.ia@gmail.com"}, headers=sessao).status_code == 409
    assert api.post("/mcp/emails-ia", json={"email": "coord@gmail"}, headers=sessao).status_code == 422
    lista = api.get("/mcp/emails-ia", headers=sessao).json()
    assert lista == [criado.json()]

    caminho = f"/mcp/emails-ia/{criado.json()['id']}"
    errado = api.post(f"{caminho}/confirmar", json={"codigo": "12345"}, headers=sessao)
    assert errado.status_code == 400 and errado.json()["detail"] == mcp_emails_ia._CODIGO_RECUSADO
    assert api.post(f"{caminho}/reenviar", headers=sessao).status_code == 202
    codigo = remetente.ultimo_codigo("coord.ia@gmail.com")
    confirmado = api.post(f"{caminho}/confirmar", json={"codigo": f"{codigo[:3]} {codigo[3:]}"}, headers=sessao)
    assert confirmado.status_code == 200 and confirmado.json()["confirmadoEm"] is not None
    assert api.get("/mcp/emails-ia", headers=sessao).json() == [confirmado.json()]
    assert api.post(f"{caminho}/reenviar", headers=sessao).status_code == 409

    removido = api.post(f"{caminho}/remover", headers=sessao)
    assert removido.status_code == 200 and removido.json()["id"] == criado.json()["id"]
    assert api.get("/mcp/emails-ia", headers=sessao).json() == []
    assert api.post(f"{caminho}/confirmar", json={"codigo": codigo}, headers=sessao).status_code == 404
