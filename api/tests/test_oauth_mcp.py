"""O OAuth dos conectores do MCP (docs/43 §5.3, Fase 3): os MUST dos RFCs, um por teste.

Sem rede e sem banco. A API vai pelo TestClient, com o FakeCliente — e a RPC
da 0072 emulada (tests/test_mcp_tokens.py) — no lugar do PostgREST, e o app do
MCP roda sobre o MESMO banco falso. O ponta a ponta faz o caminho inteiro de um
conector: descoberta → cadastro → authorize → pedido → código no e-mail da
conta de IA → aprovar com ele → código do RFC → token com PKCE → /mcp →
refresh com rotação → o antigo dá 401 → revoke.

O e-mail não sai: o SES de lembretes/email.py é trocado pelo `RemetenteFalso`,
que guarda cada envio — é dele que os testes leem o código, como a pessoa o
leria na caixa de entrada (decisão do dono de 26/10: aprovar é pela posse do
e-mail, não pela sessão do SAS).

⚠️ O fake não tem privilégio nem CHECK: que o sas_mcp não enxerga as tabelas
da 0073, e que os CHECKs dela aceitam o que a rota grava, se prova contra o
Postgres de verdade (o relato desta frente tem o roteiro).

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_oauth_mcp.py -q
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from app import auth
from app.config import Settings
from app.mcp import emails_ia, tokens
from app.mcp.configuracao import (
    ConfiguracaoMcp,
    problemas_do_emissor,
    problemas_do_oauth,
    validar_configuracao_do_mcp,
)
from app.routes import mcp_emails_ia, oauth_mcp
from tests.test_mcp_tokens import FabricaDeClientes, FakeClienteDoMcp

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"

EMISSOR = "https://portalsas.online/api"
RECURSO = "https://portalsas.online/mcp"
APP = "https://portalsas.online"
VOLTA = "https://claude.ai/api/mcp/auth_callback"

ADMIN_ID = "ad000000-0000-4000-8000-000000000001"
COORD_ID = "c0000000-0000-4000-8000-000000000002"

#: Os e-mails das contas de IA de cada um (routes/mcp_emails_ia.py): é para
#: eles que o código vai, e é em nome do dono que a conexão nasce.
EMAIL_DO_ADMIN = "admin.ia@exemplo.com"
EMAIL_DA_COORD = "coordenadora.ia@exemplo.com"
EMAIL_ADMIN_ID = "e1000000-0000-4000-8000-000000000001"
EMAIL_COORD_ID = "e1000000-0000-4000-8000-000000000002"
#: Um e-mail que ninguém cadastrou.
EMAIL_SEM_CADASTRO = "ninguem@exemplo.com"

#: Caracteres que desenham em branco, pelo código: escritos literais, seriam
#: invisíveis no próprio teste (`oauth_mcp._DESENHAM_EM_BRANCO`).
BRAILLE_VAZIO = chr(0x2800)
PREENCHIMENTO_HANGUL = chr(0x3164)


def _email_da_ia(email_id: str, dono: str, email: str) -> dict:
    """Um e-mail da IA JÁ CONFIRMADO: é o único que recebe o código de aprovar
    (routes/mcp_emails_ia.py, regra 0). O que só aguarda tem teste próprio."""
    return {
        "id": email_id, "usuario_coordenacao_id": dono, "email": email,
        "criado_em": "2026-10-26T12:00:00.000000Z", "confirmado_em": "2026-10-26T12:05:00.000000Z",
        "hash_codigo_de_confirmacao": None, "confirmacao_expira_em": None, "tentativas_de_confirmacao": 0,
        "ultimo_uso_em": None, "removido_em": None,
    }


def _banco() -> dict:
    return {
        "usuario_coordenacao": {
            ADMIN_ID: {"id": ADMIN_ID, "nome": "Admin da Casa", "papel": "administrador", "ativo": True},
            COORD_ID: {"id": COORD_ID, "nome": "Coordenadora", "papel": "coordenador", "ativo": True},
        },
        "token_mcp": {},
        "evento_auditoria": {},
        "aluno": {},
        "oauth_cliente_mcp": {},
        "oauth_pedido_mcp": {},
        "oauth_codigo_mcp": {},
        "oauth_refresh_mcp": {},
        "email_conta_ia_mcp": {
            EMAIL_ADMIN_ID: _email_da_ia(EMAIL_ADMIN_ID, ADMIN_ID, EMAIL_DO_ADMIN),
            EMAIL_COORD_ID: _email_da_ia(EMAIL_COORD_ID, COORD_ID, EMAIL_DA_COORD),
        },
        "oauth_codigo_por_email_mcp": {},
    }


class RemetenteFalso:
    """O SES de mentira (lembretes/email.py): configurado, e cada envio fica
    aqui em vez de sair. `configurado=False` é o ambiente sem SES."""

    def __init__(self, *, configurado: bool = True) -> None:
        self.configurado = configurado
        self.enviados: list[dict[str, str]] = []

    def email_configurado(self) -> bool:
        return self.configurado

    def enviar_email(self, *, destinatario: str, assunto: str, corpo: str) -> None:
        self.enviados.append({"destinatario": destinatario, "assunto": assunto, "corpo": corpo})

    def para(self, email: str) -> list[dict[str, str]]:
        return [e for e in self.enviados if e["destinatario"] == email]

    def ultimo_codigo(self, email: str) -> str | None:
        """O código do último e-mail que chegou a `email`, como a pessoa o leria."""
        recebidos = self.para(email)
        if not recebidos:
            return None
        (codigo,) = re.findall(r"^\s+(\d{6})\s*$", recebidos[-1]["corpo"], flags=re.M)
        return codigo


def _cfg(**kw) -> ConfiguracaoMcp:
    base = {"emissor_oauth": EMISSOR, "url_publica": RECURSO, "url_do_app": APP, "habilitado": True}
    return ConfiguracaoMcp(_env_file=None, **{**base, **kw})


def _passado(minutos: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutos)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@pytest.fixture(autouse=True)
def _tetos_zerados():
    """Os tetos por IP e a faxina dos pedidos são do processo: um teste não
    pode gastar a cota do outro, nem herdar a hora da última faxina."""
    estado = (
        oauth_mcp.TETO_DO_CADASTRO, oauth_mcp.TETO_DO_TOKEN, oauth_mcp.TETO_DO_AUTHORIZE, oauth_mcp.FAXINA_DOS_PEDIDOS,
        oauth_mcp.FAXINA_DOS_CLIENTES, oauth_mcp.TETO_DO_CONSENTIMENTO, oauth_mcp.TETO_DE_CODIGOS_POR_IP,
        oauth_mcp.TETO_DE_CODIGOS_POR_PEDIDO, oauth_mcp.TETO_DE_CODIGOS_POR_EMAIL,
        # Os do código que confirma o e-mail no card (routes/mcp_emails_ia.py).
        mcp_emails_ia.TETO_DE_CODIGOS_POR_CONTA, mcp_emails_ia.TETO_DE_CODIGOS_POR_EMAIL,
    )
    for item in estado:
        item.limpar()
    yield
    for item in estado:
        item.limpar()


@pytest.fixture
def banco(monkeypatch) -> dict:
    """O MESMO banco para a rota, para a tarefa de fundo do /codigo (que abre
    cliente próprio) e para o guard de administrador — é o que deixa rebaixar
    na tabela valer na hora, como em test_papeis.py."""
    db = _banco()
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: FakeClienteDoMcp(db))
    monkeypatch.setattr(oauth_mcp, "criar_cliente_supabase", lambda: FakeClienteDoMcp(db))
    monkeypatch.setattr(mcp_emails_ia, "get_supabase", lambda: FakeClienteDoMcp(db))
    monkeypatch.setattr(auth, "get_supabase", lambda: FakeClienteDoMcp(db))
    return db


@pytest.fixture
def remetente(monkeypatch) -> RemetenteFalso:
    """Os DOIS remetentes: o do código de aprovar (oauth_mcp) e o do código que
    confirma o e-mail no card (mcp_emails_ia) caem na mesma caixa falsa, como
    cairiam na mesma caixa de entrada."""
    falso = RemetenteFalso()
    monkeypatch.setattr(oauth_mcp, "email_ses", falso)
    monkeypatch.setattr(mcp_emails_ia, "email_ses", falso)
    return falso


@pytest.fixture
def config(monkeypatch):
    atual = {"cfg": _cfg()}
    monkeypatch.setattr(oauth_mcp, "get_configuracao_mcp", lambda: atual["cfg"])

    def trocar(**kw):
        atual["cfg"] = _cfg(**kw)

    return trocar


@pytest.fixture
def api(monkeypatch, banco, config, remetente):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    from app.main import create_app

    cliente = TestClient(create_app())
    # Pendurado no cliente para os auxiliares acharem o código sem mais um
    # parâmetro em cada teste.
    cliente.remetente = remetente
    yield cliente
    get_settings.cache_clear()


def _sessao(sub: str = ADMIN_ID, **claims) -> dict[str, str]:
    """O Bearer de uma sessão da API (o JWT do login), como a tela o manda."""
    payload = {"sub": sub, "tipo": "coordenador", "papel": "administrador", "nome": "x", **claims}
    return {"Authorization": f"Bearer {auth.criar_token(payload)}"}


def _pkce() -> tuple[str, str]:
    """(verificador, desafio S256) — calculado aqui, à parte do módulo."""
    verificador = secrets.token_urlsafe(48)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    return verificador, desafio


def _cadastrar(api, **meta) -> dict:
    corpo = {
        "client_name": "Claude",
        "redirect_uris": [VOLTA],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        **meta,
    }
    r = api.post("/oauth/register", json={k: v for k, v in corpo.items() if v is not None})
    assert r.status_code == 201, r.text
    return r.json()


def _autorizar(api, cliente: dict, desafio: str, *, cabecalhos: dict | None = None, **extra):
    params = {
        "response_type": "code",
        "client_id": cliente["client_id"],
        "redirect_uri": VOLTA,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
        "state": "estado-do-app",
        "scope": "sas.leitura",
        "resource": RECURSO,
        **extra,
    }
    return api.get(
        "/oauth/authorize", params={k: v for k, v in params.items() if v is not None}, follow_redirects=False,
        headers=cabecalhos or {},
    )


#: Como o browser pede a página: é para ele que o /authorize escreve HTML.
COMO_BROWSER = {"accept": "text/html,application/xhtml+xml"}


def _link_de_volta(pagina: str) -> str | None:
    """O link de volta ao app que a página de erro oferece — ou None."""
    achado = re.search(r'<a href="([^"]+)"', pagina)
    return html.unescape(achado.group(1)) if achado else None


def _pedido_da(resposta) -> str:
    assert resposta.status_code == 302, resposta.text
    destino = urlsplit(resposta.headers["location"])
    assert f"{destino.scheme}://{destino.netloc}{destino.path}" == f"{APP}/conectar-ia"
    return parse_qs(destino.query)["pedido"][0]


def _params(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def _pedir_codigo(api, pedido: str, email: str = EMAIL_DO_ADMIN):
    return api.post(f"/oauth/pedidos/{pedido}/codigo", json={"email": email})


def _aprovar_com(api, pedido: str, email: str, codigo: str, **kw):
    return api.post(f"/oauth/pedidos/{pedido}/aprovar", json={"email": email, "codigo": codigo}, **kw)


def _aprovar(api, pedido: str, email: str = EMAIL_DO_ADMIN):
    """O caminho da tela, SEM sessão nenhuma: pede o código ao e-mail da conta
    de IA, lê o que o remetente falso recebeu e aprova com ele. Sem e-mail
    recebido (não cadastrado, pedido encerrado), aprova com um código qualquer
    — a resposta é a do /aprovar, que é o que os testes conferem."""
    _pedir_codigo(api, pedido, email)
    codigo = api.remetente.ultimo_codigo(email) or "000000"
    return _aprovar_com(api, pedido, email, codigo)


def _trocar(api, cliente: dict, codigo: str, verificador: str, *, cabecalhos: dict | None = None, **extra):
    dados = {
        "grant_type": "authorization_code",
        "code": codigo,
        "code_verifier": verificador,
        "redirect_uri": VOLTA,
        "client_id": cliente["client_id"],
        **extra,
    }
    return api.post("/oauth/token", data={k: v for k, v in dados.items() if v is not None}, headers=cabecalhos or {})


def _girar(api, cliente: dict, refresh: str, **extra):
    dados = {"grant_type": "refresh_token", "refresh_token": refresh, "client_id": cliente["client_id"], **extra}
    return api.post("/oauth/token", data={k: v for k, v in dados.items() if v is not None})


def _codigo(api, cliente: dict, email: str = EMAIL_DO_ADMIN, **extra) -> tuple[str, str]:
    """(código do RFC, verificador): authorize + código no e-mail + aprovar."""
    verificador, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, cliente, desafio, **extra))
    volta = _aprovar(api, pedido, email)
    assert volta.status_code == 200, volta.text
    return _params(volta.json()["redirecionarPara"])["code"], verificador


def _conectar(api, cliente: dict | None = None, email: str = EMAIL_DO_ADMIN) -> tuple[dict, dict]:
    cliente = cliente or _cadastrar(api)
    codigo, verificador = _codigo(api, cliente, email)
    r = _trocar(api, cliente, codigo, verificador)
    assert r.status_code == 200, r.text
    return cliente, r.json()


def _unica(banco: dict, tabela: str) -> dict:
    (linha,) = banco[tabela].values()
    return linha


def _erro(resposta, status: int, erro: str) -> dict:
    assert resposta.status_code == status, resposta.text
    corpo = resposta.json()
    assert corpo["error"] == erro, corpo
    # RFC 6749 §5.2: a descrição só em ASCII imprimível, sem aspas nem barra invertida.
    assert all(0x20 <= ord(c) <= 0x7E and c not in '"\\' for c in corpo["error_description"])
    return corpo


# ─── O app do MCP sobre o mesmo banco ────────────────────────────────────


def _mcp(db: dict, **kw):
    from app.chat.ferramentas import Ferramenta, Registro
    from app.mcp.app import montar_app
    from app.mcp.servidor import montar_servidor

    fabrica = FabricaDeClientes(db)
    cfg = ConfiguracaoMcp(
        _env_file=None, hosts_permitidos="testserver", emissor_oauth=EMISSOR, url_publica=RECURSO, **kw
    )
    registro = Registro([Ferramenta(
        nome="listar_ciclos", descricao="ciclos", parametros={"type": "object", "properties": {}},
        escopo="coordenacao", handler=lambda cliente: {"total": 0, "ciclos": []}, expor_no_mcp=True,
    )])
    servidor = montar_servidor(config=cfg, registro=registro, criar_cliente=fabrica)
    return montar_app(config=cfg, servidor=servidor, criar_cliente=fabrica, app_env="test"), fabrica


def _chamar_mcp(c, token: str):
    corpo = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": "listar_ciclos", "arguments": {}}})
    cabecalhos = {"accept": "application/json", "content-type": "application/json",
                  "authorization": f"Bearer {token}"}
    return c.post("/mcp", headers=cabecalhos, content=corpo)


# ─── Ponta a ponta ───────────────────────────────────────────────────────


def test_ponta_a_ponta_do_conector(api, banco):
    mcp, _ = _mcp(banco)
    # Um TestClient só para o MCP: o gerente de sessão do SDK abre uma vez por app.
    with TestClient(mcp) as c:
        _caminho_do_conector(api, banco, c)


def _instante_de(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def test_card_mostra_o_app_e_o_fim_da_conexao_oauth_nao_o_do_access(api, banco, monkeypatch):
    """No card (`GET /mcp/tokens`), a conexão OAuth leva o nome que o app
    declarou e o fim da CONEXÃO — o do refresh, 30 dias da aprovação —, não o
    do access de 60 min: com ele, o card dizia "expirou" uma hora depois de
    quem conectou pelo claude.ai ou pelo ChatGPT, com a conexão viva. Girar o
    refresh troca o access e não mexe nesse fim; revogar devolve o mesmo."""
    from app.routes import mcp_tokens

    monkeypatch.setattr(mcp_tokens, "get_supabase", lambda: FakeClienteDoMcp(banco))
    cliente, emitido = _conectar(api, _cadastrar(api, client_name="ChatGPT"))
    (conexao,) = api.get("/mcp/tokens", headers=_sessao()).json()
    acesso = _unica(banco, "token_mcp")["expira_em"]
    fim = _unica(banco, "oauth_refresh_mcp")["expira_em"]
    assert conexao["origem"] == "oauth" and conexao["cliente"] == "ChatGPT"
    assert conexao["expiraEm"] == fim
    assert _instante_de(fim) - _instante_de(acesso) > timedelta(days=29)

    girado = _girar(api, cliente, emitido["refresh_token"])
    assert girado.status_code == 200, girado.text
    (depois,) = api.get("/mcp/tokens", headers=_sessao()).json()
    assert depois["expiraEm"] == fim and _unica(banco, "token_mcp")["expira_em"] != acesso

    revogada = api.post(f"/mcp/tokens/{conexao['id']}/revogar", headers=_sessao())
    assert revogada.status_code == 200, revogada.text
    assert revogada.json()["cliente"] == "ChatGPT" and revogada.json()["expiraEm"] == fim


def test_card_sem_refresh_mostra_o_fim_do_access_que_e_o_da_conexao(api, banco, monkeypatch):
    """App cadastrado sem `refresh_token` não renova: a conexão acaba com o
    access, e é essa a data que o card mostra."""
    from app.routes import mcp_tokens

    monkeypatch.setattr(mcp_tokens, "get_supabase", lambda: FakeClienteDoMcp(banco))
    _conectar(api, _cadastrar(api, grant_types=["authorization_code"]))
    (conexao,) = api.get("/mcp/tokens", headers=_sessao()).json()
    assert not banco["oauth_refresh_mcp"]
    assert conexao["expiraEm"] == _unica(banco, "token_mcp")["expira_em"] and conexao["cliente"] == "Claude"


def _confirmar_no_card(api, email_id: str, email: str, sessao: dict):
    """O passo do card: quem cadastrou digita, logado, o código de confirmação
    que chegou ao e-mail (routes/mcp_emails_ia.py, regra 0)."""
    codigo = api.remetente.ultimo_codigo(email)
    assert codigo is not None
    return api.post(f"/mcp/emails-ia/{email_id}/confirmar", json={"codigo": codigo}, headers=sessao)


def test_cadastrar_o_email_no_card_e_conectar_com_ele(api, banco):
    """O caminho de uma coordenadora (decisão de 26/10): cadastra no card, com
    a sessão do SAS, o e-mail da conta de IA dela, e o CONFIRMA com o código
    que chegou a ele; conecta o claude.ai SEM sessão, com o código de aprovar
    que chegou àquele e-mail; a conexão é dela, e o MCP a identifica. Removido
    o e-mail no card, ele não aprova mais nada."""
    sessao = _sessao(COORD_ID, papel="coordenador")
    novo = "coordenadora.claude@exemplo.org"
    criado = api.post("/mcp/emails-ia", json={"email": novo.upper()}, headers=sessao)
    assert criado.status_code == 201 and criado.json()["email"] == novo
    assert criado.json()["confirmadoEm"] is None
    confirmado = _confirmar_no_card(api, criado.json()["id"], novo, sessao)
    assert confirmado.status_code == 200 and confirmado.json()["confirmadoEm"] is not None

    _, par = _conectar(api, email=novo)
    assert _unica(banco, "token_mcp")["usuario_coordenacao_id"] == COORD_ID
    (cadastro,) = [e for e in api.get("/mcp/emails-ia", headers=sessao).json() if e["email"] == novo]
    assert cadastro["ultimoUsoEm"] is not None
    mcp, _ = _mcp(banco)
    with TestClient(mcp) as c:
        assert _chamar_mcp(c, par["access_token"]).json()["result"]["isError"] is False
    (chamada,) = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_ferramenta_chamada"]
    assert chamada["ator_id"] == COORD_ID

    assert api.post(f"/mcp/emails-ia/{criado.json()['id']}/remover", headers=sessao).status_code == 200
    _, pedido, _ = _pedido_novo(api)
    enviados_antes = len(api.remetente.para(novo))
    assert _aprovar(api, pedido, novo).status_code == 400
    assert len(api.remetente.para(novo)) == enviados_antes and _nada_aprovado(banco, pedido)


def test_email_que_aguarda_confirmacao_nao_recebe_nem_aprova(api, banco):
    """A prova de posse (revisão de segurança de 26/10): o e-mail cadastrado no
    card só aprova conexão depois de confirmado, com o código que chegou a ele.
    Antes disso o /codigo não manda o código de APROVAR para lá — a resposta
    continua a mesma de sempre —, e o código de confirmar não aprova nada."""
    sessao = _sessao(COORD_ID, papel="coordenador")
    novo = "coordenadora.claude@exemplo.org"
    criado = api.post("/mcp/emails-ia", json={"email": novo}, headers=sessao).json()
    (confirmacao,) = api.remetente.para(novo)
    assert "confirmar" in confirmacao["assunto"].lower()
    codigo_de_confirmar = api.remetente.ultimo_codigo(novo)

    _, pedido, _ = _pedido_novo(api)
    assert _pedir_codigo(api, pedido, novo).json() == {"enviado": True}
    assert len(api.remetente.para(novo)) == 1
    (linha,) = banco["oauth_codigo_por_email_mcp"].values()
    assert linha["email_conta_ia_id"] is None
    recusado = _aprovar_com(api, pedido, novo, codigo_de_confirmar)
    assert recusado.status_code == 400 and recusado.json()["erro"] == oauth_mcp._CODIGO_RECUSADO
    assert _nada_aprovado(banco, pedido) and banco["token_mcp"] == {}

    # Confirmado no card, o MESMO pedido aprova — em nome dela.
    assert _confirmar_no_card(api, criado["id"], novo, sessao).status_code == 200
    assert _aprovar(api, pedido, novo).status_code == 200
    assert _unica(banco, "oauth_codigo_mcp")["usuario_coordenacao_id"] == COORD_ID


def test_email_digitado_errado_no_card_nao_entrega_o_acesso_a_quem_le_a_caixa(api, banco):
    """O caminho da revisão de 26/10, que terminava num token em nome da
    coordenadora: ela digita o domínio errado no card, e o dono da caixa
    digitada (um catch-all de "gmial.com") abre um pedido do PRÓPRIO app. O
    que chega à caixa dele é o código de CONFIRMAR, que só vale no card, com a
    sessão dela; o de aprovar nunca sai para um e-mail que ninguém confirmou."""
    sessao = _sessao(COORD_ID, papel="coordenador")
    digitado_errado = "coordenadora@gmial.com"
    criado = api.post("/mcp/emails-ia", json={"email": digitado_errado}, headers=sessao)
    assert criado.status_code == 201 and criado.json()["confirmadoEm"] is None
    na_caixa_dele = api.remetente.ultimo_codigo(digitado_errado)

    volta_dele = "https://atacante.example/cb"
    cliente = _cadastrar(api, client_name="Claude", redirect_uris=[volta_dele])
    _, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, cliente, desafio, redirect_uri=volta_dele))
    assert _pedir_codigo(api, pedido, digitado_errado).status_code == 202
    assert len(api.remetente.para(digitado_errado)) == 1
    assert _aprovar_com(api, pedido, digitado_errado, na_caixa_dele).status_code == 400
    # Nem com a sessão de OUTRA conta da coordenação: o cadastro alheio é 404.
    alheio = api.post(
        f"/mcp/emails-ia/{criado.json()['id']}/confirmar", json={"codigo": na_caixa_dele}, headers=_sessao(ADMIN_ID)
    )
    assert alheio.status_code == 404
    assert _nada_aprovado(banco, pedido) and banco["token_mcp"] == {}
    assert banco["email_conta_ia_mcp"][criado.json()["id"]].get("confirmado_em") is None


def _caminho_do_conector(api, banco: dict, c) -> None:
    # Descoberta: o 401 do MCP aponta para o RFC 9728, que aponta para o emissor
    # da API — e o `issuer` dela é o MESMO texto (RFC 8414 §3.3).
    sem_token = _chamar_mcp(c, "lixo")
    prm = c.get("/.well-known/oauth-protected-resource/mcp").json()
    assert sem_token.status_code == 401
    assert ('resource_metadata="https://portalsas.online/.well-known/oauth-protected-resource/mcp"'
            in sem_token.headers["www-authenticate"])
    metadado = api.get("/.well-known/oauth-authorization-server/api").json()
    assert prm["authorization_servers"] == [metadado["issuer"]] == [EMISSOR]
    assert prm["resource"] == RECURSO

    cliente = _cadastrar(api)
    verificador, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, cliente, desafio, state="s-123"))

    # A tela, no browser da IA, sem sessão do SAS: lê o pedido, pede o código
    # ao e-mail da conta de IA e aprova com o que chegou.
    lido = api.get(f"/oauth/pedidos/{pedido}")
    assert lido.status_code == 200 and lido.json()["cliente"] == {"nome": "Claude", "redirectHost": "claude.ai"}
    pedido_de_codigo = _pedir_codigo(api, pedido, EMAIL_DO_ADMIN)
    assert pedido_de_codigo.status_code == 202 and pedido_de_codigo.json() == {"enviado": True}
    (recebido,) = api.remetente.para(EMAIL_DO_ADMIN)
    assert "claude.ai" in recebido["corpo"] and recebido["assunto"] == "Código para conectar uma IA ao SAS"
    aprovado = _aprovar_com(api, pedido, EMAIL_DO_ADMIN, api.remetente.ultimo_codigo(EMAIL_DO_ADMIN))
    assert aprovado.status_code == 200 and aprovado.headers["cache-control"] == "no-store"
    volta = aprovado.json()["redirecionarPara"]
    params = _params(volta)
    assert volta.startswith(VOLTA + "?")
    assert params["state"] == "s-123" and params["iss"] == EMISSOR
    assert banco["email_conta_ia_mcp"][EMAIL_ADMIN_ID]["ultimo_uso_em"] is not None

    r = _trocar(api, cliente, params["code"], verificador)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store" and r.headers["pragma"] == "no-cache"
    par = r.json()
    assert par["token_type"] == "Bearer" and par["scope"] == "sas.leitura"
    assert 3500 < par["expires_in"] <= 3600
    assert tokens.formato_valido(par["access_token"]) and par["refresh_token"].startswith("sas_rt_")

    assert _chamar_mcp(c, par["access_token"]).status_code == 200

    novo = _girar(api, cliente, par["refresh_token"])
    assert novo.status_code == 200, novo.text
    novo = novo.json()
    assert novo["access_token"] != par["access_token"] and novo["refresh_token"] != par["refresh_token"]
    assert _chamar_mcp(c, par["access_token"]).status_code == 401      # o access antigo morreu
    assert _chamar_mcp(c, novo["access_token"]).status_code == 200

    revogado = api.post("/oauth/revoke", data={"token": novo["refresh_token"], "client_id": cliente["client_id"]})
    assert revogado.status_code == 200 and revogado.content == b""
    assert _chamar_mcp(c, novo["access_token"]).status_code == 401

    # Uma conexão, não uma linha por access: a tela vê uma só, revogada.
    linha = _unica(banco, "token_mcp")
    assert linha["origem"] == "oauth" and linha["oauth_cliente_id"] == cliente["client_id"]
    assert linha["usuario_coordenacao_id"] == ADMIN_ID and linha.get("revogado_em") is not None
    assert linha["nome"] == "Claude (claude.ai)"


# ─── RFC 8414: o metadado do authorization server ────────────────────────


def test_metadado_nos_dois_caminhos_com_none_s256_e_issuer_sem_barra(api):
    raiz = api.get("/.well-known/oauth-authorization-server")
    com_caminho = api.get("/.well-known/oauth-authorization-server/api")
    assert raiz.status_code == com_caminho.status_code == 200
    assert raiz.json() == com_caminho.json()
    m = raiz.json()
    assert m["issuer"] == EMISSOR
    assert m["authorization_endpoint"] == f"{EMISSOR}/oauth/authorize"
    assert m["token_endpoint"] == f"{EMISSOR}/oauth/token"
    assert m["registration_endpoint"] == f"{EMISSOR}/oauth/register"
    assert m["revocation_endpoint"] == f"{EMISSOR}/oauth/revoke"
    assert "none" in m["token_endpoint_auth_methods_supported"]
    assert {"client_secret_basic", "client_secret_post"} <= set(m["token_endpoint_auth_methods_supported"])
    assert m["code_challenge_methods_supported"] == ["S256"]
    assert m["grant_types_supported"] == ["authorization_code", "refresh_token"]
    assert m["response_types_supported"] == ["code"]
    assert m["scopes_supported"] == ["sas.leitura"]


def test_metadado_so_no_caminho_do_emissor(api):
    assert api.get("/.well-known/oauth-authorization-server/outra").status_code == 404
    assert api.get("/.well-known/oauth-authorization-server/api/mais").status_code == 404


def test_emissor_configurado_com_barra_sai_sem_ela_dos_dois_lados(api, config, banco):
    """A barra que o SDK punha (`https://portalsas.online/`) faria o cliente
    descartar o metadado: o RFC 8414 §3.3 compara o issuer letra por letra."""
    config(emissor_oauth="https://portalsas.online/")
    m = api.get("/.well-known/oauth-authorization-server").json()
    assert m["issuer"] == "https://portalsas.online"
    from app.mcp.app import metadado_do_recurso

    assert metadado_do_recurso(_cfg(emissor_oauth="https://portalsas.online/"))["authorization_servers"] == [
        m["issuer"]
    ]
    # Sem caminho no emissor, não há endereço com caminho para publicar.
    assert api.get("/.well-known/oauth-authorization-server/api").status_code == 404


@pytest.mark.parametrize("campo", ["emissor_oauth", "url_publica", "url_do_app"])
def test_sem_oauth_configurado_tudo_e_404(api, config, campo):
    config(**{campo: ""})
    assert api.get("/.well-known/oauth-authorization-server").status_code == 404
    assert api.post("/oauth/register", json={"redirect_uris": [VOLTA]}).status_code == 404
    assert api.get("/oauth/authorize", params={"client_id": "x"}).status_code == 404
    assert api.post("/oauth/token", data={"grant_type": "x"}).status_code == 404
    assert api.post("/oauth/revoke", data={"token": "x"}).status_code == 404
    assert api.get("/oauth/pedidos/" + "a" * 43).status_code == 404
    assert _pedir_codigo(api, "a" * 43).status_code == 404
    assert _aprovar_com(api, "a" * 43, EMAIL_DO_ADMIN, "123456").status_code == 404
    assert api.remetente.enviados == []


def test_oauth_inseguro_fora_de_dev_fica_desligado(api, config, monkeypatch):
    """Emissor em http em produção: o OAuth não existe, e o motivo vai ao log."""
    from types import SimpleNamespace

    config(emissor_oauth="http://portalsas.online/api")
    assert api.get("/.well-known/oauth-authorization-server").status_code == 200   # dev aceita
    monkeypatch.setattr(oauth_mcp, "get_settings", lambda: SimpleNamespace(app_env="production"))
    assert api.get("/.well-known/oauth-authorization-server").status_code == 404


# ─── RFC 7591: o cadastro dinâmico ───────────────────────────────────────


def test_cadastro_publico_devolve_a_resposta_completa(api, banco):
    r = api.post("/oauth/register", json={
        "client_name": "Claude", "redirect_uris": [VOLTA], "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "logo_uri": "https://claude.ai/logo.png",   # metadado desconhecido: ignorado (§2)
    })
    assert r.status_code == 201 and r.headers["cache-control"] == "no-store"
    c = r.json()
    assert set(c) == {"client_id", "client_id_issued_at", "redirect_uris", "token_endpoint_auth_method",
                      "grant_types", "response_types", "scope", "client_name"}
    assert c["token_endpoint_auth_method"] == "none" and "client_secret" not in c
    assert c["grant_types"] == ["authorization_code", "refresh_token"] and c["response_types"] == ["code"]
    assert c["redirect_uris"] == [VOLTA] and c["scope"] == "sas.leitura"
    assert abs(c["client_id_issued_at"] - datetime.now(UTC).timestamp()) < 60
    linha = _unica(banco, "oauth_cliente_mcp")
    assert linha["client_id"] == c["client_id"] and linha["client_secret_hash"] is None


@pytest.mark.parametrize("metodo", ["client_secret_post", "client_secret_basic", None])
def test_cadastro_confidencial_mostra_o_segredo_uma_vez_e_guarda_o_hash(api, banco, metodo):
    """Sem método declarado, o default do RFC 7591 §2 é client_secret_basic."""
    c = _cadastrar(api, token_endpoint_auth_method=metodo)
    assert c["token_endpoint_auth_method"] == (metodo or "client_secret_basic")
    assert c["client_secret"] and c["client_secret_expires_at"] == 0
    linha = _unica(banco, "oauth_cliente_mcp")
    assert linha["client_secret_hash"] == hashlib.sha256(c["client_secret"].encode()).hexdigest()
    assert c["client_secret"] not in json.dumps(banco, default=str)


def test_cadastro_so_com_authorization_code_e_aceito(api):
    """O SDK recusava cliente sem refresh_token em grant_types (lacuna do mapa)."""
    c = _cadastrar(api, grant_types=["authorization_code"])
    assert c["grant_types"] == ["authorization_code"]
    sem_nada = api.post("/oauth/register", json={"redirect_uris": [VOLTA], "token_endpoint_auth_method": "none"})
    assert sem_nada.status_code == 201 and sem_nada.json()["grant_types"] == ["authorization_code"]


#: Cada volta aceita e o `new URL(uri).host` dela no Node 26 — o parser WHATWG,
#: o mesmo do browser —, anotado à mão em 26/10 (o teste não roda Node). É o
#: texto que a tela mostra, e ele tem de ser o do browser LETRA POR LETRA: a
#: tela confere o destino contra o que mostrou, sem reler
#: (web/src/dominio/conexoesDeIa.ts::destinoDaVolta).
HOST_DO_BROWSER = {
    "https://claude.ai/api/mcp/auth_callback": "claude.ai",
    "https://chatgpt.com/connector_platform_oauth_redirect": "chatgpt.com",
    "http://localhost:3334/oauth/callback": "localhost:3334",
    "http://LOCALHOST:3334/cb": "localhost:3334",
    "http://127.0.0.1:53682/callback": "127.0.0.1:53682",
    "http://[::1]:8080/cb": "[::1]:8080",
    "https://[2001:DB8::1]/cb": "[2001:db8::1]",
    "https://Claude.AI/cb": "claude.ai",
    "https://claude.ai./cb": "claude.ai.",
    "https://claude.ai:8443/cb": "claude.ai:8443",
    "https://claude.ai:80/cb": "claude.ai:80",        # padrão do http, não do https: fica
    "http://localhost:443/cb": "localhost:443",
    "https://127.0.0.1:8443/cb": "127.0.0.1:8443",     # IPv4 canônico: o browser lê igual
    "https://exemplo.com/volta?app=1": "exemplo.com",
    "https://xn--exmplo-gva.com/volta%20a?x=1&y=(2);z=*": "xn--exmplo-gva.com",
    "https://xn--80ak6aa92e.com/cb": "xn--80ak6aa92e.com",  # "аррӏе" cirílico: a tela mostra o punycode
}


@pytest.mark.parametrize(("uri", "host"), HOST_DO_BROWSER.items())
def test_redirect_uri_aceita_e_a_tela_mostra_o_host_do_browser(uri, host):
    assert oauth_mcp.redirect_aceitavel(uri)
    assert oauth_mcp._host_de_volta(uri) == host


@pytest.mark.parametrize("uri", [
    "http://claude.ai/api/mcp/auth_callback",      # http fora do loopback
    "https://claude.ai/cb#fragmento",               # fragmento (RFC 6749 §3.1.2)
    "https://claude.ai@evil.example/cb",            # usuário na autoridade engana quem lê
    "javascript:alert(1)",
    "com.exemplo.app:/volta",                       # esquema de app: sem host para a tela mostrar
    "https:///sem-host",
    "/relativa",
    "https://exemplo.com/com espaco",
    "https://exemplо.com/cb",                       # "о" cirílico: só ASCII
    "https://exemplo.com:99999/cb",                 # porta inválida
    "https://" + "a" * 2000 + ".com/",
    "",
    None,
    42,
    # O que o browser (WHATWG) lê diferente do urlsplit — revisão de 25/10.
    # A tela mostraria "atacante.example\.claude.ai"; o browser vai a atacante.example.
    "https://atacante.example\\.claude.ai/api/mcp/auth_callback",
    "https://claude.ai\\@evil.example/cb",
    "https:\\\\atacante.example/cb",                # sem "//": o urlsplit não vê host; o browser lê \\ como //
    "https://claude.ai/cb\\..\\..\\outra",          # a \ fora da autoridade também: o RFC 3986 não a tem
    "https://claude.ai/cb?volta=\\x",
    "https://claude%2eai/cb",                       # o browser decodifica o host: claude.ai
    "https://0x7f.1/cb",                            # o browser lê IPv4: 127.0.0.1
    "https://2130706433/cb",                        # idem
    "https://010.0.0.1/cb",                         # octal: 8.0.0.1
    "https://claude.ai.123/cb",                     # último rótulo numérico: o browser falha
    "https://claude.ai:/cb",                        # porta vazia
    "https://claude.ai:0/cb",
    "https://claude.ai:+443/cb",
    "https://my_host.example/cb",
    "https://claude..ai/cb",
    "https://[fe80::1%25eth0]/cb",                  # zona de IPv6
    "https://claude.ai/c|b",                        # fora do RFC 3986
    "https://claude.ai/cb?x={1}",
    'https://claude.ai/"cb"',
    "https://claude.ai/cb?x=%zz",                   # percent-encoding torto
    # O browser lê o MESMO host, mas o ESCREVE de outro jeito: a tela
    # mostraria um texto e conferiria o destino contra outro. Entre
    # parênteses, o `URL.host` do Node 26.
    "https://claude.ai:443/api/mcp/auth_callback",  # (claude.ai) a porta padrão some
    "http://localhost:80/cb",                       # (localhost)
    "https://claude.ai:0443/cb",                    # (claude.ai) e o zero à esquerda
    "http://localhost:03334/cb",                    # (localhost:3334)
    "https://[0:0:0:0:0:0:0:1]/cb",                 # ([::1]) o IPv6 sai comprimido
    "https://[2001:db8::0001]/cb",                  # ([2001:db8::1])
    "https://[::ffff:127.0.0.1]/cb",                # ([::ffff:7f00:1]) e sem o IPv4 embutido
    # Punycode que o browser recusa (a URL inteira é inválida para ele).
    "https://xn--zz.example/cb",
    "https://xn--abc-.example/cb",                  # decodifica para ASCII puro
    "https://xn--.example/cb",
])
def test_redirect_uri_recusada(uri):
    assert not oauth_mcp.redirect_aceitavel(uri)


def test_barra_invertida_na_volta_e_recusada_no_cadastro(api, banco):
    """A revisão de 25/10: a tela mostrava o host "atacante.example\\.claude.ai"
    — que TERMINA em .claude.ai —, a conferência do front batia (ela relê o
    host com o parser do browser), e o código ia para atacante.example."""
    corpo = {"redirect_uris": ["https://atacante.example\\.claude.ai/api/mcp/auth_callback"],
             "token_endpoint_auth_method": "none"}
    _erro(api.post("/oauth/register", json=corpo), 400, "invalid_redirect_uri")
    assert banco["oauth_cliente_mcp"] == {}


def test_cadastro_antigo_com_volta_torta_nao_serve_no_authorize(api, banco):
    """A regra vale de novo no /authorize: um cadastro gravado antes de ela
    endurecer não volta a servir só porque o texto bate."""
    torta = "https://atacante.example\\.claude.ai/cb"
    client_id = "7d0e7c2a-0000-4000-8000-0000000000aa"
    banco["oauth_cliente_mcp"][client_id] = {
        "client_id": client_id, "client_secret_hash": None, "client_name": "Claude", "redirect_uris": [torta],
        "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
    }
    _, desafio = _pkce()
    for volta in (torta, None):   # explícita e, com uma só cadastrada, implícita
        r = _autorizar(api, {"client_id": client_id}, desafio, redirect_uri=volta, cabecalhos=COMO_BROWSER)
        assert r.status_code == 400 and "location" not in r.headers, volta
        assert _link_de_volta(r.text) is None
    assert banco["oauth_pedido_mcp"] == {}


def test_cadastro_com_redirect_ruim_e_invalid_redirect_uri(api, banco):
    for uris in ([], None, ["http://claude.ai/cb"], [VOLTA, "https://x.com/#f"], [VOLTA] * 11, "https://x.com"):
        corpo = {"redirect_uris": uris, "token_endpoint_auth_method": "none"}
        _erro(api.post("/oauth/register", json=corpo), 400, "invalid_redirect_uri")
    assert banco["oauth_cliente_mcp"] == {}


@pytest.mark.parametrize("meta", [
    {"grant_types": ["client_credentials"]},
    {"grant_types": ["refresh_token"]},
    {"grant_types": ["authorization_code", "implicit"]},
    {"response_types": ["token"]},
    {"response_types": ["code", "id_token"]},
    {"token_endpoint_auth_method": "private_key_jwt"},
    {"client_name": "x" * 101},
    {"client_name": 7},
])
def test_cadastro_com_metadado_ruim_e_invalid_client_metadata(api, banco, meta):
    corpo = {"redirect_uris": [VOLTA], "token_endpoint_auth_method": "none", **meta}
    _erro(api.post("/oauth/register", json=corpo), 400, "invalid_client_metadata")
    assert banco["oauth_cliente_mcp"] == {}


def test_cadastro_que_nao_e_objeto_json(api):
    _erro(api.post("/oauth/register", content=b"[]", headers={"content-type": "application/json"}),
          400, "invalid_client_metadata")
    _erro(api.post("/oauth/register", content=b"{nao json", headers={"content-type": "application/json"}),
          400, "invalid_client_metadata")
    _erro(api.post("/oauth/register", data={"redirect_uris": VOLTA}), 400, "invalid_client_metadata")


def test_nome_declarado_sai_limpo(api, banco):
    c = _cadastrar(api, client_name="  Claude\x00\n  Desktop​ ")
    assert c["client_name"] == "Claude Desktop"


def test_nome_declarado_perde_o_que_desenha_em_branco(api, banco):
    """U+2800 (Braille vazio) é categoria So e passava pelo filtro de controle:
    62 deles depois de "Claude (claude.ai)" empurravam o host de verdade para
    fora do nome (revisão de 25/10). Os preenchimentos do hangul, idem."""
    hangul = "".join(map(chr, (0x3164, 0x115F, 0x1160, 0xFFA0)))
    c = _cadastrar(api, client_name=f"Claude{BRAILLE_VAZIO * 2}(claude.ai){hangul}fim{BRAILLE_VAZIO}")
    assert c["client_name"] == "Claude (claude.ai) fim"


@pytest.mark.parametrize("corpo", [b"[" * 15000, b'{"a":' * 3000], ids=["lista", "objeto"])
def test_cadastro_com_json_aninhado_demais_e_invalid_client_metadata(api, banco, corpo):
    """RecursionError não é ValueError: o aninhamento cabe no teto de 16 KiB,
    estoura a pilha do decodificador e era 500 numa porta anônima."""
    assert len(corpo) < 16 * 1024
    _erro(api.post("/oauth/register", content=corpo, headers={"content-type": "application/json"}),
          400, "invalid_client_metadata")
    assert banco["oauth_cliente_mcp"] == {}


def test_teto_de_cadastros_por_ip(api, config, banco):
    config(oauth_cadastros_por_hora=2)
    _cadastrar(api)
    _cadastrar(api)
    r = api.post("/oauth/register", json={"redirect_uris": [VOLTA], "token_endpoint_auth_method": "none"})
    _erro(r, 429, "too_many_requests")
    assert r.headers["retry-after"] == "3600"
    assert len(banco["oauth_cliente_mcp"]) == 2


def _de_ips_diferentes(monkeypatch) -> None:
    """Cada requisição de um IP novo: o teto por IP não alcança ninguém."""
    contador = iter(range(1, 10_000))
    monkeypatch.setattr(oauth_mcp, "_ip", lambda request: f"198.51.100.{next(contador)}")


def _envelhecer(banco: dict, client_id: str, **tempo) -> None:
    linha = next(c for c in banco["oauth_cliente_mcp"].values() if c["client_id"] == client_id)
    linha["criado_em"] = oauth_mcp._instante(datetime.now(UTC) - timedelta(**tempo))


def test_teto_de_cadastros_no_total_vale_para_todos_os_ips(api, config, banco, monkeypatch):
    """O teto era só por IP e em memória: com muitos IPs, `oauth_cliente_mcp`
    crescia sem limite, uma linha de até ~16 KiB por cadastro (revisão final
    de 26/10). O do total é contado no banco, na última hora."""
    config(oauth_cadastros_por_hora_no_total=2)
    _de_ips_diferentes(monkeypatch)
    primeiro, _ = _cadastrar(api), _cadastrar(api)
    r = api.post("/oauth/register", json={"redirect_uris": [VOLTA], "token_endpoint_auth_method": "none"})
    _erro(r, 503, "temporarily_unavailable")
    assert r.headers["retry-after"] == "3600"
    assert len(banco["oauth_cliente_mcp"]) == 2
    # A janela anda: o cadastro de mais de uma hora atrás sai da conta.
    _envelhecer(banco, primeiro["client_id"], hours=1, minutes=1)
    _cadastrar(api)
    assert len(banco["oauth_cliente_mcp"]) == 3


def test_cadastro_invalido_nao_gasta_o_teto_do_total(api, config, banco):
    """Só o que vira linha conta: quem manda metadado ruim não grava nada, e
    não pode trancar o cadastro de quem conecta de verdade."""
    config(oauth_cadastros_por_hora_no_total=1)
    for _ in range(3):
        _erro(api.post("/oauth/register", json={"redirect_uris": ["http://evil.example/cb"]}), 400,
              "invalid_redirect_uri")
    _cadastrar(api)


def test_faxina_apaga_so_o_cliente_velho_que_nunca_foi_usado(api, banco):
    """O nunca usado — sem pedido e sem conexão, há mais de uma semana — sai
    quando alguém se cadastra. O que tem história fica (a FK da 0073 nem
    deixaria apagar), e o novo ainda pode estar a caminho do /authorize."""
    velho, com_pedido, com_conexao, novo = (_cadastrar(api)["client_id"] for _ in range(4))
    _, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, {"client_id": com_pedido}, desafio))
    assert _aprovar(api, pedido).status_code == 200
    banco["token_mcp"]["t-oauth"] = {"id": "t-oauth", "origem": "oauth", "oauth_cliente_id": com_conexao}
    for client_id in (velho, com_pedido, com_conexao):
        _envelhecer(banco, client_id, days=8)
    oauth_mcp.FAXINA_DOS_CLIENTES.limpar()           # a do primeiro cadastro acabou de rodar
    recem = _cadastrar(api)["client_id"]
    sobrou = {c["client_id"] for c in banco["oauth_cliente_mcp"].values()}
    assert sobrou == {com_pedido, com_conexao, novo, recem}


def test_faxina_dos_clientes_que_falha_nao_derruba_o_cadastro(api, banco, monkeypatch):
    cliente = _cadastrar(api)["client_id"]
    _envelhecer(banco, cliente, days=30)
    oauth_mcp.FAXINA_DOS_CLIENTES.limpar()
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: _SemDelete(banco))
    _cadastrar(api)
    assert len(banco["oauth_cliente_mcp"]) == 2


def test_corpo_grande_demais_e_413(api):
    grande = b'{"client_name": "' + b"x" * 20_000 + b'"}'
    assert api.post("/oauth/register", content=grande, headers={"content-type": "application/json"}).status_code == 413
    form = b"grant_type=authorization_code&code=" + b"x" * 20_000
    r = api.post("/oauth/token", content=form, headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 413


# ─── /oauth/authorize (RFC 6749 §4.1, RFC 7636, RFC 8707) ────────────────


def test_authorize_grava_o_pedido_e_manda_para_o_consentimento(api, banco):
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    r = _autorizar(api, cliente, desafio, state="xyz")
    pedido_id = _pedido_da(r)
    assert r.headers["cache-control"] == "no-store"
    pedido = banco["oauth_pedido_mcp"][pedido_id]
    assert pedido["client_id"] == cliente["client_id"] and pedido["redirect_uri"] == VOLTA
    assert pedido["redirect_uri_explicita"] is True and pedido["code_challenge"] == desafio
    assert pedido["state"] == "xyz" and pedido["resource"] == RECURSO and pedido["scope"] == "sas.leitura"
    assert pedido.get("decidido_em") is None
    validade = datetime.fromisoformat(pedido["expira_em"]) - datetime.fromisoformat(pedido["criado_em"])
    assert validade == timedelta(minutes=10)


@pytest.mark.parametrize("client_id", ["7d0e7c2a-0000-4000-8000-000000000000", "nao-e-uuid", None])
def test_client_id_desconhecido_nunca_redireciona(api, banco, client_id):
    _, desafio = _pkce()
    r = _autorizar(api, {"client_id": client_id}, desafio, client_id=client_id)
    assert r.status_code == 400 and "location" not in r.headers
    assert r.json()["error"] in ("invalid_client", "invalid_request")
    html = api.get("/oauth/authorize", params={"client_id": client_id or ""}, headers={"accept": "text/html"})
    assert html.status_code == 400 and "text/html" in html.headers["content-type"]
    assert "location" not in html.headers and "<script" not in html.text
    assert html.headers["content-security-policy"].startswith("default-src 'none'")
    assert banco["oauth_pedido_mcp"] == {}


def test_redirect_uri_nao_cadastrada_nunca_redireciona(api, banco):
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    for outra in ("https://evil.example/cb", VOLTA + "/", VOLTA + "?x=1", "HTTPS://claude.ai/api/mcp/auth_callback"):
        r = _autorizar(api, cliente, desafio, redirect_uri=outra)
        assert r.status_code == 400 and "location" not in r.headers, outra
        assert "evil.example" not in r.text
    assert banco["oauth_pedido_mcp"] == {}


def test_loopback_aceita_outra_porta_e_nada_mais(api, banco):
    """RFC 8252 §7.3: o app nativo pega uma porta livre na hora, e o servidor
    TEM de aceitar qualquer porta no loopback. Só a porta."""
    registrada = "http://127.0.0.1:3334/callback"
    cliente = _cadastrar(api, redirect_uris=[registrada])
    verificador, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, cliente, desafio, redirect_uri="http://127.0.0.1:51999/callback"))
    assert banco["oauth_pedido_mcp"][pedido]["redirect_uri"] == "http://127.0.0.1:51999/callback"
    lido = api.get(f"/oauth/pedidos/{pedido}").json()
    assert lido["cliente"]["redirectHost"] == "127.0.0.1:51999"
    volta = _aprovar(api, pedido).json()["redirecionarPara"]
    assert volta.startswith("http://127.0.0.1:51999/callback?code=")
    # E a troca confere a redirect_uri DESTE pedido, com a porta dele.
    r = _trocar(api, cliente, _params(volta)["code"], verificador, redirect_uri="http://127.0.0.1:51999/callback")
    assert r.status_code == 200, r.text

    for outra in ("http://127.0.0.1:51999/outro", "http://localhost:3334/callback", "http://127.0.0.1:3334/callback?x=1"):
        r = _autorizar(api, cliente, desafio, redirect_uri=outra)
        assert r.status_code == 400 and "location" not in r.headers, outra


def test_https_nao_tem_excecao_de_porta():
    assert not oauth_mcp.redirect_registrada("https://claude.ai:8443/cb", ["https://claude.ai/cb"])
    assert oauth_mcp.redirect_registrada("https://claude.ai/cb", ["https://claude.ai/cb"])


def test_sem_redirect_uri_so_quando_ha_uma_cadastrada(api, banco):
    """RFC 6749 §3.1.2.3; e a troca então dispensa a redirect_uri (§4.1.3)."""
    uma = _cadastrar(api)
    verificador, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, uma, desafio, redirect_uri=None))
    assert banco["oauth_pedido_mcp"][pedido]["redirect_uri_explicita"] is False
    codigo = _params(_aprovar(api, pedido).json()["redirecionarPara"])["code"]
    assert _trocar(api, uma, codigo, verificador, redirect_uri=None).status_code == 200

    duas = _cadastrar(api, redirect_uris=[VOLTA, "https://claude.ai/outra"])
    r = _autorizar(api, duas, desafio, redirect_uri=None)
    assert r.status_code == 400 and "location" not in r.headers


@pytest.mark.parametrize(("extra", "erro"), [
    ({"code_challenge": None}, "invalid_request"),                   # PKCE ausente
    ({"code_challenge_method": "plain"}, "invalid_request"),         # plain recusado
    ({"code_challenge_method": None}, "invalid_request"),            # sem método = plain (RFC 7636 §4.3)
    ({"code_challenge": "curto"}, "invalid_request"),
    ({"response_type": "token"}, "unsupported_response_type"),
    ({"response_type": None}, "invalid_request"),
    ({"resource": "https://portalsas.online/outra"}, "invalid_target"),
    ({"resource": "https://evil.example/mcp"}, "invalid_target"),
    ({"state": "s" * 2049}, "invalid_request"),
])
def test_erro_depois_do_cliente_nao_redireciona_e_oferece_a_volta(api, banco, extra, erro):
    """RFC 9700 §4.11.2: o /authorize é anônimo, e a redirect_uri "conferida"
    é a que o próprio app cadastrou. Um 302 de erro fazia do SAS um
    redirecionador para qualquer site. A volta — com o erro, o `state` e o
    `iss` do RFC 6749 §4.1.2.1 e do RFC 9207 — vira um link que a PESSOA segue."""
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    pedido = {"state": "meu-state", **extra}
    r = _autorizar(api, cliente, desafio, **pedido)
    assert r.status_code == 400 and "location" not in r.headers
    _erro(r, 400, erro)

    pagina = _autorizar(api, cliente, desafio, cabecalhos=COMO_BROWSER, **pedido)
    assert pagina.status_code == 400 and "location" not in pagina.headers
    assert "text/html" in pagina.headers["content-type"]
    assert "<script" not in pagina.text and "refresh" not in pagina.text.lower()
    assert ">Voltar para claude.ai</a>" in pagina.text
    volta = _link_de_volta(pagina.text)
    assert volta.startswith(VOLTA + "?")
    params = _params(volta)
    assert params["error"] == erro and params["iss"] == EMISSOR
    assert params["state"] == extra.get("state", "meu-state")
    assert all(0x20 <= ord(c) <= 0x7E and c not in '"\\' for c in params["error_description"])
    assert banco["oauth_pedido_mcp"] == {}


def test_authorize_anonimo_nao_redireciona_para_o_site_de_quem_se_cadastrou(api, banco):
    """O caso da revisão de 25/10: alguém cadastra a própria isca (o cadastro é
    aberto) e espalha portalsas.online/api/oauth/authorize?… sem
    response_type. Era 302 direto para a isca, sem login e sem pedido
    gravado. Agora é a página do SAS, que diz para onde o link leva."""
    isca = "https://phishing.example/login-do-sas"
    cliente = _cadastrar(api, client_name="Qualquer", redirect_uris=[isca])
    for extra in ({}, {"response_type": "code"}, {"response_type": "code", "code_challenge": "x" * 43}):
        params = {"client_id": cliente["client_id"], "redirect_uri": isca, **extra}
        for cabecalhos in ({}, COMO_BROWSER):
            r = api.get("/oauth/authorize", params=params, headers=cabecalhos, follow_redirects=False)
            assert r.status_code == 400 and not r.is_redirect and "location" not in r.headers, extra
        assert "Voltar para phishing.example" in r.text and "feche esta aba" in r.text
    assert banco["oauth_pedido_mcp"] == {}


def test_resource_na_forma_canonica_e_aceito(api, banco):
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    for recurso in ("https://PortalSAS.online/mcp/", "https://portalsas.online:443/mcp", RECURSO):
        _pedido_da(_autorizar(api, cliente, desafio, resource=recurso))
    _pedido_da(_autorizar(api, cliente, desafio, resource=None))   # resource é opcional


def test_parametro_repetido_no_authorize(api, banco):
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    base = [("response_type", "code"), ("client_id", cliente["client_id"]), ("redirect_uri", VOLTA),
            ("code_challenge", desafio), ("code_challenge_method", "S256")]
    r = api.get("/oauth/authorize", params=[*base, ("state", "a"), ("state", "b")], follow_redirects=False)
    assert r.status_code == 400 and "location" not in r.headers
    assert "state" in _erro(r, 400, "invalid_request")["error_description"]
    r = api.get("/oauth/authorize", params=[*base, ("client_id", cliente["client_id"])], follow_redirects=False)
    assert r.status_code == 400 and "location" not in r.headers
    # O nome de um parâmetro que o OAuth não tem é texto livre de quem montou
    # o link: a página do SAS não o repete (nem o aviso que vai ao app).
    isca = "Sua senha venceu, entre em sas-login.example"
    r = api.get("/oauth/authorize", params=[*base, (isca, "a"), (isca, "b")], headers=COMO_BROWSER,
                follow_redirects=False)
    assert r.status_code == 400 and "sas-login" not in r.text
    assert "sas-login" not in _params(_link_de_volta(r.text))["error_description"]
    # `resource` pode repetir (RFC 8707 §2), desde que todos sejam o MCP.
    r = api.get("/oauth/authorize", params=[*base, ("resource", RECURSO), ("resource", RECURSO)],
                follow_redirects=False)
    _pedido_da(r)


def test_escopo_desconhecido_leva_so_o_de_leitura(api, banco):
    cliente = _cadastrar(api)
    verificador, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, cliente, desafio, scope="openid admin"))
    assert banco["oauth_pedido_mcp"][pedido]["scope"] == "sas.leitura"
    codigo = _params(_aprovar(api, pedido).json()["redirecionarPara"])["code"]
    assert _trocar(api, cliente, codigo, verificador).json()["scope"] == "sas.leitura"


def test_teto_do_authorize(api, config, banco):
    config(oauth_tentativas_por_minuto=1)
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    _pedido_da(_autorizar(api, cliente, desafio))
    r = _autorizar(api, cliente, desafio)
    assert r.status_code == 429 and "location" not in r.headers
    assert len(banco["oauth_pedido_mcp"]) == 1


def test_teto_de_pedidos_abertos_por_app(api, banco, config):
    """O teto por IP limita a velocidade, não o volume: um IP gravava ~375 MB
    por dia de pedidos sem login (revisão de 25/10). Aberto é o que ainda não
    foi decidido nem venceu — decidir ou vencer devolve a vaga."""
    config(oauth_pedidos_abertos_por_cliente=2)
    cliente, outro = _cadastrar(api), _cadastrar(api)
    _, desafio = _pkce()
    primeiro = _pedido_da(_autorizar(api, cliente, desafio))
    segundo = _pedido_da(_autorizar(api, cliente, desafio))
    r = _autorizar(api, cliente, desafio)
    _erro(r, 429, "temporarily_unavailable")
    assert "location" not in r.headers and r.headers["retry-after"] == "600"
    assert set(banco["oauth_pedido_mcp"]) == {primeiro, segundo}
    _pedido_da(_autorizar(api, outro, desafio))                  # o teto é de cada app

    assert _aprovar(api, primeiro).status_code == 200
    terceiro = _pedido_da(_autorizar(api, cliente, desafio))
    banco["oauth_pedido_mcp"][segundo]["expira_em"] = _passado()
    _pedido_da(_autorizar(api, cliente, desafio))
    _erro(_autorizar(api, cliente, desafio), 429, "temporarily_unavailable")
    assert terceiro in banco["oauth_pedido_mcp"]


def test_teto_de_pedidos_abertos_no_total(api, banco, config):
    """Com o teto por app, quem quer encher a tabela cadastra mais apps: o
    teto da casa inteira é o que segura o disco."""
    config(oauth_pedidos_abertos_no_total=2)
    a, b, c = _cadastrar(api), _cadastrar(api), _cadastrar(api)
    _, desafio = _pkce()
    _pedido_da(_autorizar(api, a, desafio))
    _pedido_da(_autorizar(api, b, desafio))
    r = _autorizar(api, c, desafio, cabecalhos=COMO_BROWSER)
    assert r.status_code == 503 and "location" not in r.headers
    assert _params(_link_de_volta(r.text))["error"] == "temporarily_unavailable"
    assert len(banco["oauth_pedido_mcp"]) == 2


def test_faxina_apaga_so_o_pedido_vencido_sem_decisao(api, banco):
    """Vencido e sem decisão não responde nada — some. O decidido é a história
    de quem aprovou que app (0073), e o aberto ainda vale."""
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    aberto = _pedido_da(_autorizar(api, cliente, desafio))
    vencido = _pedido_da(_autorizar(api, cliente, desafio))
    decidido = _pedido_da(_autorizar(api, cliente, desafio))
    assert _aprovar(api, decidido).status_code == 200
    for pedido in (vencido, decidido):
        banco["oauth_pedido_mcp"][pedido]["expira_em"] = _passado()
    oauth_mcp.FAXINA_DOS_PEDIDOS.limpar()      # a do primeiro pedido acabou de rodar
    novo = _pedido_da(_autorizar(api, cliente, desafio))
    assert set(banco["oauth_pedido_mcp"]) == {aberto, decidido, novo}
    assert len(banco["oauth_codigo_mcp"]) == 1


def test_faxina_roda_no_maximo_uma_vez_por_intervalo():
    class Relogio:
        agora = 0.0

        def __call__(self):
            return self.agora

    relogio = Relogio()
    faxina = oauth_mcp.FaxinaDosPedidos(60.0, relogio=relogio)
    assert faxina.devida() and not faxina.devida()
    relogio.agora += 59
    assert not faxina.devida()
    relogio.agora += 2
    assert faxina.devida() and not faxina.devida()
    faxina.limpar()
    assert faxina.devida()


class _SemDelete(FakeClienteDoMcp):
    """O banco em que o DELETE falha (permissão, rede): a faxina é manutenção."""

    def table(self, nome):
        tabela = super().table(nome)

        def delete(**_kw):
            raise RuntimeError("permission denied for table oauth_pedido_mcp")

        tabela.delete = delete
        return tabela


def test_faxina_que_falha_nao_derruba_o_pedido(api, banco, monkeypatch):
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: _SemDelete(banco))
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    _pedido_da(_autorizar(api, cliente, desafio))
    assert len(banco["oauth_pedido_mcp"]) == 1


# ─── O consentimento (o contrato da tela /conectar-ia) ───────────────────


def _pedido_novo(api, **extra) -> tuple[dict, str, str]:
    cliente = _cadastrar(api)
    verificador, desafio = _pkce()
    return cliente, _pedido_da(_autorizar(api, cliente, desafio, **extra)), verificador


def _nada_aprovado(banco: dict, pedido: str) -> bool:
    """O pedido segue sem decisão, e nenhum código do RFC saiu dele."""
    return banco["oauth_pedido_mcp"][pedido].get("decidido_em") is None and not any(
        codigo.get("pedido_id") == pedido for codigo in banco["oauth_codigo_mcp"].values()
    )


def test_pedido_no_formato_do_contrato(api):
    _, pedido, _ = _pedido_novo(api)
    r = api.get(f"/oauth/pedidos/{pedido}")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    corpo = r.json()
    assert set(corpo) == {"id", "cliente", "expiraEm"} and corpo["id"] == pedido
    assert corpo["cliente"] == {"nome": "Claude", "redirectHost": "claude.ai"}
    expira = datetime.fromisoformat(corpo["expiraEm"])
    assert timedelta(minutes=9) < expira - datetime.now(UTC) <= timedelta(minutes=10)


def test_app_sem_nome_aparece_como_tal(api):
    cliente = _cadastrar(api, client_name=None)
    _, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, cliente, desafio))
    assert api.get(f"/oauth/pedidos/{pedido}").json()["cliente"]["nome"] == "App sem nome"


def test_pedido_vencido_inexistente_torto_ou_decidido_e_404(api, banco):
    _, pedido, _ = _pedido_novo(api)
    for torto in ("x", "a" * 43, "../" + "a" * 40):
        assert api.get(f"/oauth/pedidos/{torto}").status_code == 404
    banco["oauth_pedido_mcp"][pedido]["expira_em"] = _passado()
    assert api.get(f"/oauth/pedidos/{pedido}").status_code == 404
    assert _pedir_codigo(api, pedido).status_code == 404
    assert _aprovar(api, pedido).status_code == 404
    assert api.post(f"/oauth/pedidos/{pedido}/recusar").status_code == 404
    assert banco["oauth_codigo_mcp"] == {} and api.remetente.enviados == []

    _, outro, _ = _pedido_novo(api)
    assert _aprovar(api, outro).status_code == 200
    assert _aprovar(api, outro).status_code == 404                      # decidido não volta
    assert api.get(f"/oauth/pedidos/{outro}").status_code == 404
    assert api.post(f"/oauth/pedidos/{outro}/recusar").status_code == 404
    assert len(banco["oauth_codigo_mcp"]) == 1
    # A frase vai no `erro` do contrato da tela e no `detail`, onde o cliente
    # HTTP do front a procura.
    corpo = api.get(f"/oauth/pedidos/{outro}").json()
    assert corpo == {"erro": oauth_mcp._PEDIDO_ENCERRADO, "detail": oauth_mcp._PEDIDO_ENCERRADO}


def test_recusar_nao_pede_sessao_nem_codigo_e_nao_tem_autor(api, banco):
    """Tirar acesso nunca depende de poder dar acesso: quem tem o link recusa.
    Anônima, a recusa vai ao log e não à trilha — e o pedido a guarda sem
    autor (0073)."""
    _, pedido, _ = _pedido_novo(api, state="st")
    r = api.post(f"/oauth/pedidos/{pedido}/recusar")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    params = _params(r.json()["redirecionarPara"])
    assert params["error"] == "access_denied" and params["state"] == "st" and params["iss"] == EMISSOR
    assert "code" not in params
    linha = banco["oauth_pedido_mcp"][pedido]
    assert linha["aprovado"] is False and linha["decidido_por"] is None and linha["decidido_em"]
    assert banco["evento_auditoria"] == {}
    # Recusado não se aprova depois.
    assert _aprovar(api, pedido).status_code == 404 and banco["oauth_codigo_mcp"] == {}


def test_por_padrao_o_email_da_coordenadora_aprova_em_nome_dela(api, banco):
    """A decisão do dono de 26/10: administrador E coordenador conectam — a
    conexão nasce em nome do DONO do e-mail que recebeu o código."""
    _conectar(api, email=EMAIL_DA_COORD)
    assert _unica(banco, "token_mcp")["usuario_coordenacao_id"] == COORD_ID
    assert _unica(banco, "oauth_pedido_mcp")["decidido_por"] == COORD_ID
    assert _unica(banco, "oauth_codigo_mcp")["usuario_coordenacao_id"] == COORD_ID


def test_com_so_o_administrador_ligado_o_email_da_coordenadora_nao_recebe_nem_aprova(api, banco, config):
    """MCP_EMISSAO_SO_ADMINISTRADOR=true, que desde 26/10 é opção: o código só
    vai ao e-mail de administrador — e a resposta do /codigo não muda por isso."""
    config(emissao_so_administrador=True)
    _, pedido, _ = _pedido_novo(api)
    r = _pedir_codigo(api, pedido, EMAIL_DA_COORD)
    assert r.status_code == 202 and r.json() == {"enviado": True}
    assert api.remetente.enviados == []
    (linha,) = banco["oauth_codigo_por_email_mcp"].values()
    assert linha["email_conta_ia_id"] is None          # ninguém recebeu: não aprova
    r = _aprovar(api, pedido, EMAIL_DA_COORD)
    assert r.status_code == 400 and r.json()["erro"] == oauth_mcp._CODIGO_RECUSADO
    assert _nada_aprovado(banco, pedido)
    # O administrador aprova, no mesmo pedido.
    assert _aprovar(api, pedido, EMAIL_DO_ADMIN).status_code == 200
    assert _unica(banco, "oauth_codigo_mcp")["usuario_coordenacao_id"] == ADMIN_ID


def test_com_so_o_administrador_ligado_o_rebaixado_nao_aprova(api, banco, config):
    """Rebaixado antes do código, ele nem sai; rebaixado entre o código e a
    aprovação, o código certo não basta — a tabela é relida no /aprovar."""
    config(emissao_so_administrador=True)
    _, antes, _ = _pedido_novo(api)
    banco["usuario_coordenacao"][ADMIN_ID]["papel"] = "coordenador"
    assert _aprovar(api, antes).status_code == 400 and api.remetente.enviados == []

    banco["usuario_coordenacao"][ADMIN_ID]["papel"] = "administrador"
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido)
    banco["usuario_coordenacao"][ADMIN_ID]["papel"] = "coordenador"
    r = _aprovar_com(api, pedido, EMAIL_DO_ADMIN, api.remetente.ultimo_codigo(EMAIL_DO_ADMIN))
    assert r.status_code == 400 and r.json()["erro"] == oauth_mcp._CONTA_SEM_PERMISSAO
    assert _nada_aprovado(banco, pedido)


@pytest.mark.parametrize("claims", [
    {"sub": ADMIN_ID, "tipo": "coordenador", "papel": "administrador", "nome": "x"},
    {"sub": "a-1", "tipo": "aluno", "aluno_id": "a-1"},
    {"sub": "k-1", "tipo": "cantina", "cantina_id": "ct-1"},
], ids=["administrador", "aluno", "cantina"])
def test_sessao_nenhuma_aprova_sem_o_codigo(api, banco, claims):
    """UMA porta só (26/10): a sessão de administrador, que antes aprovava
    sozinha, hoje não muda nada — como a do aluno e a da cantina."""
    _, pedido, _ = _pedido_novo(api)
    cabecalho = {"Authorization": f"Bearer {auth.criar_token(claims)}"}
    assert api.get(f"/oauth/pedidos/{pedido}", headers=cabecalho).status_code == 200
    assert api.post(f"/oauth/pedidos/{pedido}/aprovar", headers=cabecalho).status_code == 422
    assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, "123456", headers=cabecalho).status_code == 400
    assert _nada_aprovado(banco, pedido)


def test_o_consentimento_nao_pede_sessao(api, banco):
    """O browser da IA não tem sessão do SAS: ler, pedir o código e aprovar vão
    sem cabeçalho nenhum."""
    _, pedido, _ = _pedido_novo(api)
    assert api.get(f"/oauth/pedidos/{pedido}").status_code == 200
    assert _aprovar(api, pedido).status_code == 200
    assert _unica(banco, "oauth_codigo_mcp")["usuario_coordenacao_id"] == ADMIN_ID


def test_aprovar_audita_quem_para_onde_e_por_qual_email_sem_codigo_nenhum(api, banco, monkeypatch):
    # Um código fixo, para procurá-lo sem chance de coincidir com o que mais
    # estiver no banco.
    monkeypatch.setattr(oauth_mcp.emails_ia, "gerar_codigo", lambda: "731942")
    cliente, pedido, _ = _pedido_novo(api, state="segredo-do-state")
    _pedir_codigo(api, pedido)
    assert api.remetente.ultimo_codigo(EMAIL_DO_ADMIN) == "731942"
    volta = _aprovar_com(api, pedido, EMAIL_DO_ADMIN, "731942").json()["redirecionarPara"]
    codigo = _params(volta)["code"]
    (evento,) = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_oauth_aprovado"]
    assert evento["ator_tipo"] == "coordenador" and evento["ator_id"] == ADMIN_ID
    assert evento["recurso"] == f"oauth_cliente/{cliente['client_id']}" and evento["canal"] == "mcp"
    assert evento["detalhe"] == {
        "cliente": "Claude", "redirectHost": "claude.ai", "email": "a***@exemplo.com", "emailIaId": EMAIL_ADMIN_ID,
    }
    trilha = json.dumps(banco["evento_auditoria"], default=str)
    # Nem os códigos, nem o state, nem o e-mail inteiro vão para a trilha.
    for segredo in (codigo, "731942", "segredo-do-state", EMAIL_DO_ADMIN):
        assert segredo not in trilha, segredo
    # O código do RFC só como sha256; o do e-mail, como HMAC com a chave da API
    # — nem o código nem o e-mail digitado ficam na linha.
    assert codigo not in json.dumps(banco, default=str)
    assert _unica(banco, "oauth_codigo_mcp")["hash_codigo"] == hashlib.sha256(codigo.encode()).hexdigest()
    linha = _unica(banco, "oauth_codigo_por_email_mcp")
    assert "731942" not in linha.values() and EMAIL_DO_ADMIN not in linha.values()
    assert linha["hash_codigo"] != hashlib.sha256(b"731942").hexdigest()
    assert linha["usado_em"] is not None and linha["tentativas"] == 1


def test_a_volta_mantem_a_query_da_redirect_uri(api, banco):
    """RFC 6749 §3.1.2: a query que a redirect_uri já tinha é mantida."""
    com_query = "https://exemplo.com/volta?app=1"
    cliente = _cadastrar(api, redirect_uris=[com_query])
    _, desafio = _pkce()
    pedido = _pedido_da(_autorizar(api, cliente, desafio, redirect_uri=com_query))
    volta = _aprovar(api, pedido).json()["redirecionarPara"]
    assert volta.startswith("https://exemplo.com/volta?app=1&code=")


# ─── O código no e-mail da conta de IA (decisão do dono de 26/10) ────────


def _codigo_errado(certo: str) -> str:
    return f"{(int(certo) + 1) % 10**6:06d}"


def _visivel(resposta) -> tuple:
    """O que quem chama enxerga de uma resposta, menos o que muda a cada uma."""
    cabecalhos = {k: v for k, v in resposta.headers.items() if k.lower() not in ("x-request-id", "date")}
    return resposta.status_code, resposta.content, cabecalhos


def test_email_sem_cadastro_recebe_a_mesma_resposta_e_nenhum_envio(api, banco):
    """Nada de enumerar e-mail: o /codigo e o /aprovar respondem igual para o
    cadastrado e para o que ninguém cadastrou — e só o cadastrado recebe."""
    _, pedido, _ = _pedido_novo(api)
    cadastrado = _pedir_codigo(api, pedido, EMAIL_DO_ADMIN)
    sem_cadastro = _pedir_codigo(api, pedido, EMAIL_SEM_CADASTRO)
    assert _visivel(cadastrado) == _visivel(sem_cadastro)
    assert cadastrado.status_code == 202 and cadastrado.json() == {"enviado": True}
    assert [e["destinatario"] for e in api.remetente.enviados] == [EMAIL_DO_ADMIN]
    # As duas viraram linha de código: é o que deixa o /aprovar igual nos dois.
    assert sorted(
        (linha["email_conta_ia_id"] or "") for linha in banco["oauth_codigo_por_email_mcp"].values()
    ) == ["", EMAIL_ADMIN_ID]

    certo = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)
    errado_com_cadastro = _aprovar_com(api, pedido, EMAIL_DO_ADMIN, _codigo_errado(certo))
    errado_sem_cadastro = _aprovar_com(api, pedido, EMAIL_SEM_CADASTRO, certo)
    assert _visivel(errado_com_cadastro) == _visivel(errado_sem_cadastro)
    assert errado_com_cadastro.status_code == 400
    assert errado_com_cadastro.json() == {"erro": oauth_mcp._CODIGO_RECUSADO, "detail": oauth_mcp._CODIGO_RECUSADO}
    # E os dois gastaram a tentativa do mesmo jeito.
    assert [linha["tentativas"] for linha in banco["oauth_codigo_por_email_mcp"].values()] == [1, 1]
    assert _nada_aprovado(banco, pedido)


def test_o_codigo_responde_antes_de_procurar_o_email(api, banco, monkeypatch):
    """O tempo da resposta não pode depender do cadastro: a rota só lê o pedido
    e responde; o e-mail é procurado DEPOIS, na tarefa de fundo."""
    _, pedido, _ = _pedido_novo(api)
    lidas: list[str] = []

    class Espia(FakeClienteDoMcp):
        def table(self, nome):
            lidas.append(nome)
            return super().table(nome)

    adiadas: list[tuple] = []
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: Espia(banco))
    monkeypatch.setattr(oauth_mcp, "_preparar_codigo", lambda *args: adiadas.append(args))
    for email in (EMAIL_DO_ADMIN, EMAIL_SEM_CADASTRO):
        assert _pedir_codigo(api, pedido, email).status_code == 202
    assert set(lidas) == {"oauth_pedido_mcp"}
    assert [(p, e) for p, e, _ in adiadas] == [(pedido, EMAIL_DO_ADMIN), (pedido, EMAIL_SEM_CADASTRO)]


def test_email_digitado_em_maiusculas_e_com_espaco_e_o_mesmo(api, banco):
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido, "  Admin.IA@Exemplo.COM ")
    certo = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)
    assert certo is not None
    assert _aprovar_com(api, pedido, "ADMIN.ia@exemplo.com", certo[:3] + " " + certo[3:]).status_code == 200


def test_codigo_errado_vencido_de_outro_pedido_ou_de_outro_email_nao_aprova(api, banco):
    """O código é preso ao pedido E ao e-mail, vale 10 minutos, e a mensagem é
    uma só para todo erro: qualquer diferença contaria o que o chute acertou."""
    _, pedido, _ = _pedido_novo(api)
    _, outro, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido, EMAIL_DO_ADMIN)
    certo = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)
    _pedir_codigo(api, outro, EMAIL_DA_COORD)
    respostas = [
        _aprovar_com(api, pedido, EMAIL_DO_ADMIN, _codigo_errado(certo)),   # errado
        _aprovar_com(api, outro, EMAIL_DO_ADMIN, certo),                     # de outro pedido
        _aprovar_com(api, pedido, EMAIL_DA_COORD, certo),                    # de outro e-mail
        _aprovar_com(api, pedido, EMAIL_DO_ADMIN, "12345"),                  # fora do formato
    ]
    assert [r.status_code for r in respostas] == [400] * 4
    assert {r.json()["erro"] for r in respostas} == {oauth_mcp._CODIGO_RECUSADO}
    assert _nada_aprovado(banco, pedido) and _nada_aprovado(banco, outro)

    (linha,) = [x for x in banco["oauth_codigo_por_email_mcp"].values() if x["email_conta_ia_id"] == EMAIL_ADMIN_ID]
    linha["expira_em"] = _passado()
    vencido = _aprovar_com(api, pedido, EMAIL_DO_ADMIN, certo)
    assert vencido.status_code == 400 and vencido.json()["erro"] == oauth_mcp._CODIGO_RECUSADO
    assert _nada_aprovado(banco, pedido)


def test_codigo_de_email_sem_cadastro_nao_aprova_nem_acertado(api, banco, monkeypatch):
    """A linha do e-mail sem cadastro tem um código que ninguém recebeu — e
    nem quem o acertasse no chute aprovaria: não há dono em nome de quem."""
    monkeypatch.setattr(oauth_mcp.emails_ia, "gerar_codigo", lambda: "731942")
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido, EMAIL_SEM_CADASTRO)
    assert api.remetente.enviados == []
    r = _aprovar_com(api, pedido, EMAIL_SEM_CADASTRO, "731942")
    assert r.status_code == 400 and r.json()["erro"] == oauth_mcp._CODIGO_RECUSADO
    assert _nada_aprovado(banco, pedido)


def test_codigo_ja_usado_nao_aprova_de_novo(api, banco):
    """Uso único. A conta desativada entre o código e a aprovação derruba a
    aprovação DEPOIS de o código bater — e ele fica gasto, mesmo reativada a
    conta. Um código novo aprova."""
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido)
    certo = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)
    banco["usuario_coordenacao"][ADMIN_ID]["ativo"] = False
    r = _aprovar_com(api, pedido, EMAIL_DO_ADMIN, certo)
    assert r.status_code == 400 and r.json()["erro"] == oauth_mcp._CONTA_SEM_PERMISSAO
    banco["usuario_coordenacao"][ADMIN_ID]["ativo"] = True
    r = _aprovar_com(api, pedido, EMAIL_DO_ADMIN, certo)
    assert r.status_code == 400 and r.json()["erro"] == oauth_mcp._CODIGO_RECUSADO
    assert _nada_aprovado(banco, pedido)
    assert _aprovar(api, pedido).status_code == 200


def test_conta_desativada_nao_recebe_codigo(api, banco):
    banco["usuario_coordenacao"][COORD_ID]["ativo"] = False
    _, pedido, _ = _pedido_novo(api)
    assert _pedir_codigo(api, pedido, EMAIL_DA_COORD).status_code == 202
    assert api.remetente.enviados == []
    assert _aprovar(api, pedido, EMAIL_DA_COORD).status_code == 400
    assert _nada_aprovado(banco, pedido)


def test_email_removido_nao_recebe_e_o_codigo_que_ja_saiu_nao_aprova(api, banco):
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido, EMAIL_DA_COORD)
    certo = api.remetente.ultimo_codigo(EMAIL_DA_COORD)
    banco["email_conta_ia_mcp"][EMAIL_COORD_ID]["removido_em"] = _passado(0)
    r = _aprovar_com(api, pedido, EMAIL_DA_COORD, certo)
    assert r.status_code == 400 and r.json()["erro"] == oauth_mcp._EMAIL_SEM_CADASTRO
    assert _nada_aprovado(banco, pedido)
    # Removido, nem recebe mais.
    _, outro, _ = _pedido_novo(api)
    assert _pedir_codigo(api, outro, EMAIL_DA_COORD).status_code == 202
    assert len(api.remetente.para(EMAIL_DA_COORD)) == 1


def test_tentativas_esgotadas_nem_o_codigo_certo_aprova(api, banco):
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido)
    certo = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)
    for _ in range(emails_ia.TENTATIVAS_POR_CODIGO):
        assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, _codigo_errado(certo)).status_code == 400
    r = _aprovar_com(api, pedido, EMAIL_DO_ADMIN, certo)
    assert r.status_code == 400 and r.json()["erro"] == oauth_mcp._CODIGO_RECUSADO
    linha = _unica(banco, "oauth_codigo_por_email_mcp")
    assert linha["tentativas"] == emails_ia.TENTATIVAS_POR_CODIGO == 5 and linha.get("usado_em") is None
    assert _nada_aprovado(banco, pedido)


def test_pedir_outro_codigo_mata_o_anterior(api, banco):
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido)
    primeiro = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)
    _pedir_codigo(api, pedido)
    segundo = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)
    if primeiro != segundo:                       # um em um milhão: o mesmo número duas vezes
        assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, primeiro).status_code == 400
    assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, segundo).status_code == 200


def test_tentativa_e_gasta_antes_de_comparar(api, banco, monkeypatch):
    """Dez chutes ao mesmo tempo não viram dez comparações: quem perde a vez de
    gastar a tentativa (o UPDATE condicional na contagem lida) não compara —
    nem com o código certo."""
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido)
    certo = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)

    def outro_chute_gastou_a_vez():
        _unica(banco, "oauth_codigo_por_email_mcp")["tentativas"] += 1

    corrida = _ComCorrida(banco, "oauth_codigo_por_email_mcp", outro_chute_gastou_a_vez)
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: corrida)
    assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, certo).status_code == 400
    assert _nada_aprovado(banco, pedido)
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: FakeClienteDoMcp(banco))
    assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, certo).status_code == 200
    assert _unica(banco, "oauth_codigo_por_email_mcp")["tentativas"] == 2


def test_teto_de_codigos_por_pedido(api, banco, config):
    config(oauth_codigos_por_pedido=2)
    _, pedido, _ = _pedido_novo(api)
    assert [_pedir_codigo(api, pedido, e).status_code for e in (EMAIL_SEM_CADASTRO, EMAIL_DO_ADMIN)] == [202, 202]
    r = _pedir_codigo(api, pedido, EMAIL_DA_COORD)
    assert r.status_code == 429 and r.headers["retry-after"] == "600" and "erro" in r.json()
    assert api.remetente.para(EMAIL_DA_COORD) == []


def test_teto_de_codigos_por_email_conta_qualquer_email_igual(api, banco, config):
    """O teto que segura o chute: por e-mail, por dia — contado para o
    cadastrado e para o que não é, senão o 429 diria quais estão."""
    config(oauth_codigos_por_email_por_dia=2)
    pedidos = [_pedido_novo(api)[1] for _ in range(3)]
    barrados = []
    for email in (EMAIL_DO_ADMIN, EMAIL_SEM_CADASTRO):
        assert [_pedir_codigo(api, p, email).status_code for p in pedidos[:2]] == [202, 202]
        barrados.append(_pedir_codigo(api, pedidos[2], email))
    assert _visivel(barrados[0]) == _visivel(barrados[1])
    assert barrados[0].status_code == 429 and barrados[0].headers["retry-after"] == "86400"
    assert len(api.remetente.para(EMAIL_DO_ADMIN)) == 2


def test_teto_de_codigos_por_ip(api, banco, config):
    config(oauth_codigos_por_ip_por_hora=2)
    _, pedido, _ = _pedido_novo(api)
    assert [_pedir_codigo(api, pedido, e).status_code for e in (EMAIL_DO_ADMIN, EMAIL_DA_COORD)] == [202, 202]
    r = _pedir_codigo(api, pedido, EMAIL_SEM_CADASTRO)
    assert r.status_code == 429 and r.headers["retry-after"] == "3600"


def test_teto_do_consentimento_por_ip(api, banco, config):
    """Ler, aprovar e recusar são anônimos: dividem um teto por IP."""
    config(oauth_tentativas_por_minuto=2)
    _, pedido, _ = _pedido_novo(api)
    assert api.get(f"/oauth/pedidos/{pedido}").status_code == 200
    assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, "123456").status_code == 400
    r = api.post(f"/oauth/pedidos/{pedido}/recusar")
    assert r.status_code == 429 and r.headers["retry-after"] == "60" and r.json()["erro"]
    assert banco["oauth_pedido_mcp"][pedido].get("decidido_em") is None


def test_sem_ses_o_codigo_vai_ao_log_so_em_dev(api, banco, monkeypatch, caplog):
    """APP_ENV=dev e SES sem configurar: é como se testa o fluxo na máquina."""
    monkeypatch.setattr(oauth_mcp, "email_ses", RemetenteFalso(configurado=False))
    monkeypatch.setattr(oauth_mcp.emails_ia, "gerar_codigo", lambda: "731942")
    _, pedido, _ = _pedido_novo(api)
    with caplog.at_level("INFO", logger="sas.oauth"):
        assert _pedir_codigo(api, pedido).status_code == 202
    mensagens = [r.getMessage() for r in caplog.records]
    assert any("[DEV]" in m and "731942" in m and "a***@exemplo.com" in m for m in mensagens)
    assert not any(EMAIL_DO_ADMIN in m for m in mensagens)          # só mascarado
    assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, "731942").status_code == 200


@pytest.mark.parametrize("app_env", ["production", "test"])
def test_sem_ses_fora_de_dev_o_codigo_nunca_vai_ao_log(api, banco, monkeypatch, caplog, app_env):
    """Fora de dev, quem lesse o log aprovaria em nome de qualquer coordenador."""
    from types import SimpleNamespace

    monkeypatch.setattr(oauth_mcp, "email_ses", RemetenteFalso(configurado=False))
    monkeypatch.setattr(oauth_mcp.emails_ia, "gerar_codigo", lambda: "731942")
    monkeypatch.setattr(oauth_mcp, "get_settings", lambda: SimpleNamespace(app_env=app_env, jwt_secret_key=SEGREDO))
    _, pedido, _ = _pedido_novo(api)
    with caplog.at_level("DEBUG"):
        assert _pedir_codigo(api, pedido).status_code == 202
    mensagens = [r.getMessage() for r in caplog.records]
    assert not any("731942" in m for m in mensagens)
    assert any(r.levelname == "ERROR" and "SES não configurado" in r.getMessage() for r in caplog.records)


def test_falha_na_tarefa_de_fundo_vai_ao_log_e_nao_derruba_a_resposta(api, banco, monkeypatch, caplog):
    class _SemInsert(FakeClienteDoMcp):
        def table(self, nome):
            tabela = super().table(nome)
            if nome == "oauth_codigo_por_email_mcp":
                def insert(*_a, **_k):
                    raise RuntimeError("PostgREST fora")
                tabela.insert = insert
            return tabela

    monkeypatch.setattr(oauth_mcp, "criar_cliente_supabase", lambda: _SemInsert(banco))
    _, pedido, _ = _pedido_novo(api)
    with caplog.at_level("ERROR", logger="sas.oauth"):
        assert _pedir_codigo(api, pedido).status_code == 202
    assert api.remetente.enviados == []
    assert any("[AÇÃO NECESSÁRIA]" in r.getMessage() for r in caplog.records)


# ─── /oauth/token: o código ──────────────────────────────────────────────


def test_a_troca_cria_uma_linha_oauth_de_token_mcp_que_guarda_so_o_hash(api, banco):
    cliente, par = _conectar(api)
    linha = _unica(banco, "token_mcp")
    assert linha["hash_acesso"] == tokens.hash_do_token(par["access_token"])
    assert linha["prefixo"] == par["access_token"][:12]
    validade = datetime.fromisoformat(linha["expira_em"]) - datetime.fromisoformat(linha["criado_em"])
    assert validade == timedelta(hours=1)
    refresh = _unica(banco, "oauth_refresh_mcp")
    assert refresh["hash_refresh"] == hashlib.sha256(par["refresh_token"].encode()).hexdigest()
    assert refresh["token_mcp_id"] == linha["id"] and refresh["client_id"] == cliente["client_id"]
    conexao = datetime.fromisoformat(refresh["expira_em"]) - datetime.fromisoformat(refresh["criado_em"])
    assert conexao == timedelta(days=30)
    texto = json.dumps(banco, default=str)
    assert par["access_token"] not in texto and par["refresh_token"] not in texto
    (evento,) = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_token_emitido"]
    assert evento["detalhe"] == {"nome": "Claude (claude.ai)", "origem": "oauth"}
    assert evento["recurso"] == f"mcp_token/{linha['id']}" and evento["ator_id"] == ADMIN_ID


@pytest.mark.parametrize("declarado", [
    "x" * 100,                                          # nome longo e honesto
    "Claude (claude.ai)" + BRAILLE_VAZIO * 62,                # host falso + Braille vazio
    "Claude (claude.ai)" + PREENCHIMENTO_HANGUL * 30 + "y" * 40,  # idem, com o preenchimento do hangul
], ids=["nome-longo", "braille-vazio", "hangul"])
def test_nome_da_conexao_leva_o_host_de_volta_inteiro(api, banco, declarado):
    """A revisão de 25/10: o nome era `f"{declarado} ({host})"[:80]`, e um nome
    de 80 empurrava o host para fora — a conexão de um app qualquer ficava
    igual à do Claude na lista de Conexões de IA e na auditoria. Agora quem
    encolhe é o nome declarado."""
    volta = "https://atacante.example/cb"
    cliente = _cadastrar(api, client_name=declarado, redirect_uris=[volta])
    codigo, verificador = _codigo(api, cliente, redirect_uri=volta, resource=None)
    assert _trocar(api, cliente, codigo, verificador, redirect_uri=volta).status_code == 200
    nome = _unica(banco, "token_mcp")["nome"]
    assert nome.endswith(" (atacante.example)") and len(nome) <= 80
    assert BRAILLE_VAZIO not in nome and PREENCHIMENTO_HANGUL not in nome
    (evento,) = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_token_emitido"]
    assert evento["detalhe"]["nome"] == nome


def test_nome_da_conexao_com_host_enorme_guarda_o_fim_do_host():
    """Host maior que o nome inteiro (só no limite do DNS) perde o começo: o
    fim é o domínio que alguém registrou."""
    host = "a" * 50 + "." + "b" * 40 + ".example"
    cliente = oauth_mcp.ClienteOAuth("id", "Claude", (f"https://{host}/cb",), "none", ("authorization_code",), None)
    nome = oauth_mcp._nome_da_conexao(cliente, f"https://{host}/cb")
    assert len(nome) <= 80 and nome.endswith(f"…{host[-76:]})")


def test_validades_vem_da_configuracao(api, banco, config):
    config(validade_do_acesso_oauth_minutos=5, validade_do_refresh_oauth_dias=2)
    _, par = _conectar(api)
    assert 290 < par["expires_in"] <= 300
    refresh = _unica(banco, "oauth_refresh_mcp")
    assert datetime.fromisoformat(refresh["expira_em"]) - datetime.fromisoformat(refresh["criado_em"]) == timedelta(days=2)


def test_verifier_errado_e_invalid_grant_e_nao_gasta_o_codigo(api, banco):
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    errado, _ = _pkce()
    _erro(_trocar(api, cliente, codigo, errado), 400, "invalid_grant")
    _erro(_trocar(api, cliente, codigo, "curto"), 400, "invalid_request")
    _erro(_trocar(api, cliente, codigo, None), 400, "invalid_request")       # PKCE obrigatório
    assert banco["token_mcp"] == {}
    # Nada foi gasto pelas tentativas erradas: o dono do verificador ainda troca.
    assert _trocar(api, cliente, codigo, verificador).status_code == 200


def test_codigo_reusado_e_recusado_e_derruba_a_conexao_que_gerou(api, banco):
    """RFC 6749 §4.1.2: uso duplo MUST ser negado e SHOULD revogar o que saiu dele."""
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    assert _trocar(api, cliente, codigo, verificador).status_code == 200
    _erro(_trocar(api, cliente, codigo, verificador), 400, "invalid_grant")
    assert _unica(banco, "token_mcp").get("revogado_em") is not None
    assert _unica(banco, "oauth_refresh_mcp").get("revogado_em") is not None
    (evento,) = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_token_revogado"]
    assert evento["detalhe"]["motivo"] == "codigo_reapresentado" and evento["ator_tipo"] == "sistema"


def test_redirect_uri_da_troca_tem_de_ser_a_do_pedido(api, banco):
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    _erro(_trocar(api, cliente, codigo, verificador, redirect_uri="https://claude.ai/outra"), 400, "invalid_grant")
    _erro(_trocar(api, cliente, codigo, verificador, redirect_uri=None), 400, "invalid_request")
    assert banco["token_mcp"] == {}


def test_codigo_de_outro_cliente_e_invalid_grant(api, banco):
    dono, intruso = _cadastrar(api), _cadastrar(api)
    codigo, verificador = _codigo(api, dono)
    _erro(_trocar(api, intruso, codigo, verificador), 400, "invalid_grant")
    assert banco["token_mcp"] == {}


def test_codigo_vencido_ou_inventado_e_invalid_grant(api, banco):
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    _unica(banco, "oauth_codigo_mcp")["expira_em"] = _passado()
    _erro(_trocar(api, cliente, codigo, verificador), 400, "invalid_grant")
    _erro(_trocar(api, cliente, secrets.token_urlsafe(32), verificador), 400, "invalid_grant")
    assert banco["token_mcp"] == {}


def test_conta_rebaixada_entre_aprovar_e_trocar_nao_recebe_token(api, banco, config):
    """A regra do administrador, quando ligada, também na conferência, não só
    na aprovação."""
    config(emissao_so_administrador=True)
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    banco["usuario_coordenacao"][ADMIN_ID]["papel"] = "coordenador"
    _erro(_trocar(api, cliente, codigo, verificador), 400, "invalid_grant")
    assert banco["token_mcp"] == {}


def test_conta_desativada_entre_aprovar_e_trocar_nao_recebe_token(api, banco):
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    banco["usuario_coordenacao"][ADMIN_ID]["ativo"] = False
    _erro(_trocar(api, cliente, codigo, verificador), 400, "invalid_grant")


def test_resource_da_troca_tem_de_ser_o_mcp(api, banco):
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    _erro(_trocar(api, cliente, codigo, verificador, resource="https://evil.example/mcp"), 400, "invalid_target")
    assert _trocar(api, cliente, codigo, verificador, resource=RECURSO).status_code == 200


def _basic(client_id: str, segredo: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"{client_id}:{segredo}".encode()).decode()}


def test_confidencial_autentica_por_basic_ou_pelo_corpo(api, banco):
    """Os dois jeitos do RFC 6749 §2.3.1, seja qual for o método cadastrado —
    e no Basic sem `client_id` no corpo (o SDK o exigia: lacuna do mapa)."""
    for metodo in ("client_secret_post", "client_secret_basic"):
        cliente = _cadastrar(api, token_endpoint_auth_method=metodo)
        codigo, verificador = _codigo(api, cliente)
        pelo_corpo = _trocar(api, cliente, codigo, verificador, client_secret=cliente["client_secret"])
        assert pelo_corpo.status_code == 200, pelo_corpo.text
        codigo, verificador = _codigo(api, cliente)
        pelo_basic = _trocar(api, cliente, codigo, verificador, client_id=None,
                             cabecalhos=_basic(cliente["client_id"], cliente["client_secret"]))
        assert pelo_basic.status_code == 200, pelo_basic.text


def test_confidencial_com_segredo_errado_ou_sem_segredo_e_401(api, banco):
    cliente = _cadastrar(api, token_endpoint_auth_method="client_secret_post")
    codigo, verificador = _codigo(api, cliente)
    _erro(_trocar(api, cliente, codigo, verificador), 401, "invalid_client")
    _erro(_trocar(api, cliente, codigo, verificador, client_secret="errado"), 401, "invalid_client")
    r = _trocar(api, cliente, codigo, verificador, client_id=None, cabecalhos=_basic(cliente["client_id"], "errado"))
    _erro(r, 401, "invalid_client")
    assert r.headers["www-authenticate"].startswith("Basic")
    # Os dois jeitos ao mesmo tempo, não (§2.3); e id do corpo diferente do Basic, menos ainda.
    _erro(_trocar(api, cliente, codigo, verificador, client_secret=cliente["client_secret"],
                  cabecalhos=_basic(cliente["client_id"], cliente["client_secret"])), 400, "invalid_request")
    outro = _cadastrar(api)
    _erro(_trocar(api, cliente, codigo, verificador, client_id=outro["client_id"],
                  cabecalhos=_basic(cliente["client_id"], cliente["client_secret"])), 401, "invalid_client")
    # O código não foi gasto por nenhuma tentativa: quem prova o segredo ainda troca.
    assert _trocar(api, cliente, codigo, verificador, client_secret=cliente["client_secret"]).status_code == 200


def test_cliente_publico_vazio_no_segredo_vale_como_ausente(api, banco):
    """RFC 6749 §3.1: parâmetro sem valor é parâmetro omitido."""
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    assert _trocar(api, cliente, codigo, verificador, client_secret="").status_code == 200


@pytest.mark.parametrize(("dados", "status", "erro"), [
    ({"grant_type": "password"}, 400, "unsupported_grant_type"),
    ({"grant_type": "client_credentials"}, 400, "unsupported_grant_type"),
    ({}, 400, "invalid_request"),
    ({"grant_type": "authorization_code", "client_id": "nao-existe"}, 401, "invalid_client"),
])
def test_token_com_pedido_ruim(api, banco, dados, status, erro):
    _erro(api.post("/oauth/token", data=dados), status, erro)


def test_token_recusa_parametro_repetido_e_corpo_que_nao_e_form(api, banco):
    """RFC 6749 §3.2: parâmetro repetido é recusado — mesmo quando o pedido,
    lido pelo último valor, seria válido."""
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)
    corpo = (f"grant_type=authorization_code&client_id={cliente['client_id']}&redirect_uri={VOLTA}"
             f"&code_verifier={verificador}&code={codigo}&code={codigo}")
    r = api.post("/oauth/token", content=corpo, headers={"content-type": "application/x-www-form-urlencoded"})
    assert "repetido" in _erro(r, 400, "invalid_request")["error_description"]
    _erro(api.post("/oauth/token", json={"grant_type": "authorization_code"}), 400, "invalid_request")
    assert banco["token_mcp"] == {}


class _ComCorrida(FakeClienteDoMcp):
    """A outra requisição que ganha a corrida: logo depois do PRIMEIRO select
    na tabela, `corrida()` muda o banco — como se outra troca (ou outra aba)
    tivesse gravado entre a leitura e o UPDATE condicional. É o caso que só o
    `.is_(…, "null")` do UPDATE pega: em sequência, a leitura já recusa."""

    def __init__(self, db: dict, tabela: str, corrida) -> None:
        super().__init__(db)
        self._alvo = tabela
        self._corrida = corrida
        self._feito = False

    def table(self, nome):
        tabela = super().table(nome)
        if nome != self._alvo:
            return tabela
        selecionar = tabela.select

        def select(*colunas, **kw):
            consulta = selecionar(*colunas, **kw)
            executar = consulta.execute

            def execute():
                resposta = executar()
                if not self._feito:
                    self._feito = True
                    self._corrida()
                return resposta

            consulta.execute = execute
            return consulta

        tabela.select = select
        return tabela


def test_duas_trocas_do_mesmo_codigo_ao_mesmo_tempo_so_uma_ganha(api, banco, monkeypatch):
    cliente = _cadastrar(api)
    codigo, verificador = _codigo(api, cliente)

    def a_outra_troca_gastou():
        _unica(banco, "oauth_codigo_mcp")["usado_em"] = _passado(0)

    corrida = _ComCorrida(banco, "oauth_codigo_mcp", a_outra_troca_gastou)
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: corrida)
    _erro(_trocar(api, cliente, codigo, verificador), 400, "invalid_grant")
    assert banco["token_mcp"] == {}


def test_dois_giros_do_mesmo_refresh_ao_mesmo_tempo_derrubam_a_conexao(api, banco, monkeypatch):
    cliente, par = _conectar(api)

    def o_outro_giro_ganhou():
        _unica(banco, "oauth_refresh_mcp")["revogado_em"] = _passado(0)

    corrida = _ComCorrida(banco, "oauth_refresh_mcp", o_outro_giro_ganhou)
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: corrida)
    _erro(_girar(api, cliente, par["refresh_token"]), 400, "invalid_grant")
    conexao = _unica(banco, "token_mcp")
    assert conexao.get("revogado_em") is not None
    assert conexao["hash_acesso"] == tokens.hash_do_token(par["access_token"])   # não girou


def test_duas_abas_respondendo_ao_mesmo_tempo_geram_uma_decisao(api, banco, monkeypatch):
    """A outra aba recusa entre a leitura do pedido e a decisão desta: o código
    do e-mail bateu, mas o UPDATE condicional da decisão perde — e nenhum
    código do RFC sai."""
    _, pedido, _ = _pedido_novo(api)
    _pedir_codigo(api, pedido)
    certo = api.remetente.ultimo_codigo(EMAIL_DO_ADMIN)

    def a_outra_aba_recusou():
        banco["oauth_pedido_mcp"][pedido].update(decidido_em=_passado(0), decidido_por=None, aprovado=False)

    corrida = _ComCorrida(banco, "oauth_pedido_mcp", a_outra_aba_recusou)
    monkeypatch.setattr(oauth_mcp, "get_supabase", lambda: corrida)
    assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, certo).status_code == 404
    assert banco["oauth_codigo_mcp"] == {}
    assert banco["oauth_pedido_mcp"][pedido]["aprovado"] is False


def test_cliente_sem_refresh_cadastrado_nao_recebe_nem_usa_refresh(api, banco):
    cliente = _cadastrar(api, grant_types=["authorization_code"])
    _, par = _conectar(api, cliente)
    assert "refresh_token" not in par and banco["oauth_refresh_mcp"] == {}
    _erro(_girar(api, cliente, "sas_rt_" + "a" * 43), 400, "unauthorized_client")


def test_teto_do_token(api, config, banco):
    config(oauth_tentativas_por_minuto=2)
    for _ in range(2):
        _erro(api.post("/oauth/token", data={"grant_type": "x"}), 400, "unsupported_grant_type")
    r = api.post("/oauth/token", data={"grant_type": "x"})
    _erro(r, 429, "too_many_requests")
    assert r.headers["retry-after"] == "60"


# ─── /oauth/token: o refresh, com rotação ────────────────────────────────


def test_refresh_gira_na_mesma_conexao_e_o_par_antigo_morre(api, banco):
    cliente, par = _conectar(api)
    conexao = _unica(banco, "token_mcp")
    velho = _unica(banco, "oauth_refresh_mcp")
    novo = _girar(api, cliente, par["refresh_token"])
    assert novo.status_code == 200 and novo.headers["cache-control"] == "no-store"
    novo = novo.json()

    # O access novo é a MESMA linha com outro hash: o antigo não existe mais.
    assert _unica(banco, "token_mcp") is conexao
    assert conexao["hash_acesso"] == tokens.hash_do_token(novo["access_token"])
    assert conexao.get("revogado_em") is None
    # O refresh velho morreu apontando para o novo, que herda o prazo dele.
    assert velho.get("revogado_em") is not None
    (o_novo,) = [r for r in banco["oauth_refresh_mcp"].values() if r is not velho]
    assert velho["substituido_por"] == o_novo["id"] and o_novo.get("revogado_em") is None
    assert o_novo["expira_em"] == velho["expira_em"]


def test_refresh_girado_reapresentado_derruba_a_conexao_inteira(api, banco):
    """RFC 9700 §4.14.2: um dos dois — o app ou o ladrão — tem o velho. A
    conexão cai, inclusive o par novo."""
    cliente, par = _conectar(api)
    novo = _girar(api, cliente, par["refresh_token"]).json()
    _erro(_girar(api, cliente, par["refresh_token"]), 400, "invalid_grant")
    assert _unica(banco, "token_mcp").get("revogado_em") is not None
    assert all(r.get("revogado_em") is not None for r in banco["oauth_refresh_mcp"].values())
    _erro(_girar(api, cliente, novo["refresh_token"]), 400, "invalid_grant")
    eventos = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_token_revogado"]
    assert [e["detalhe"]["motivo"] for e in eventos] == ["refresh_reapresentado"]


def test_refresh_na_mao_de_outro_cliente_derruba_a_conexao(api, banco):
    _, par = _conectar(api)
    intruso = _cadastrar(api)
    _erro(_girar(api, intruso, par["refresh_token"]), 400, "invalid_grant")
    assert _unica(banco, "token_mcp").get("revogado_em") is not None


def test_refresh_vencido_ou_inventado(api, banco):
    cliente, par = _conectar(api)
    _erro(_girar(api, cliente, "sas_rt_" + "b" * 43), 400, "invalid_grant")
    _erro(_girar(api, cliente, "outra-coisa"), 400, "invalid_grant")
    _unica(banco, "oauth_refresh_mcp")["expira_em"] = _passado()
    _erro(_girar(api, cliente, par["refresh_token"]), 400, "invalid_grant")


def test_conexao_revogada_na_tela_nao_gira(api, banco):
    """Revogar a linha em Conexões de IA corta o refresh junto — senão o app
    pegaria um access novo no minuto seguinte."""
    cliente, par = _conectar(api)
    _unica(banco, "token_mcp")["revogado_em"] = _passado(0)
    _erro(_girar(api, cliente, par["refresh_token"]), 400, "invalid_grant")
    assert all(r.get("revogado_em") is not None for r in banco["oauth_refresh_mcp"].values())


def test_conta_rebaixada_nao_gira_e_perde_a_conexao(api, banco, config):
    """MCP_EMISSAO_SO_ADMINISTRADOR, ligada, na conferência: rebaixar vale na
    próxima troca, não no fim dos 30 dias."""
    config(emissao_so_administrador=True)
    cliente, par = _conectar(api)
    banco["usuario_coordenacao"][ADMIN_ID]["papel"] = "coordenador"
    _erro(_girar(api, cliente, par["refresh_token"]), 400, "invalid_grant")
    assert _unica(banco, "token_mcp").get("revogado_em") is not None


def test_refresh_nao_pede_escopo_que_nao_foi_concedido(api, banco):
    cliente, par = _conectar(api)
    _erro(_girar(api, cliente, par["refresh_token"], scope="sas.leitura admin"), 400, "invalid_scope")
    assert _girar(api, cliente, par["refresh_token"], scope="sas.leitura").status_code == 200


def test_access_nunca_passa_do_fim_da_conexao(api, banco):
    cliente, par = _conectar(api)
    fim = datetime.now(UTC) + timedelta(minutes=10)
    _unica(banco, "oauth_refresh_mcp")["expira_em"] = fim.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    novo = _girar(api, cliente, par["refresh_token"]).json()
    assert novo["expires_in"] <= 600


# ─── /oauth/revoke (RFC 7009) ────────────────────────────────────────────


def _revogar(api, cliente: dict, token: str, **extra):
    return api.post("/oauth/revoke", data={"token": token, "client_id": cliente["client_id"], **extra})


@pytest.mark.parametrize("qual", ["refresh_token", "access_token"])
def test_revogar_o_access_ou_o_refresh_derruba_a_conexao(api, banco, qual):
    cliente, par = _conectar(api)
    r = _revogar(api, cliente, par[qual], token_type_hint=qual)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert _unica(banco, "token_mcp").get("revogado_em") is not None
    assert _unica(banco, "oauth_refresh_mcp").get("revogado_em") is not None
    (evento,) = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_token_revogado"]
    assert evento["ator_tipo"] == "oauth_cliente" and evento["ator_id"] == cliente["client_id"]
    _erro(_girar(api, cliente, par["refresh_token"]), 400, "invalid_grant")


def test_dica_errada_nao_impede_a_revogacao(api, banco):
    """§2.1: a dica é dica — sem achar por ela, o servidor procura nos outros tipos."""
    cliente, par = _conectar(api)
    assert _revogar(api, cliente, par["refresh_token"], token_type_hint="access_token").status_code == 200
    assert _unica(banco, "token_mcp").get("revogado_em") is not None


def test_revogar_token_desconhecido_ou_de_outro_app_e_200_sem_efeito(api, banco):
    """§2.2: inválido devolve 200; e o de outro app não é revogado nem confirmado."""
    cliente, par = _conectar(api)
    outro = _cadastrar(api)
    assert _revogar(api, cliente, "qualquer-coisa").status_code == 200
    assert _revogar(api, outro, par["refresh_token"]).status_code == 200
    assert _revogar(api, outro, par["access_token"]).status_code == 200
    assert _unica(banco, "token_mcp").get("revogado_em") is None


def test_revoke_de_cliente_publico_nao_pede_client_secret(api, banco):
    """O SDK exigia a chave client_secret até de cliente público (lacuna do mapa)."""
    cliente, par = _conectar(api)
    corpo = f"token={par['refresh_token']}&client_id={cliente['client_id']}"
    r = api.post("/oauth/revoke", content=corpo, headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 200 and _unica(banco, "token_mcp").get("revogado_em") is not None


def test_revoke_nao_revoga_token_pessoal(api, banco):
    cliente = _cadastrar(api)
    pessoal, hash_acesso, prefixo = tokens.gerar()
    banco["token_mcp"]["70ce0000-0000-4000-8000-000000000009"] = {
        "id": "70ce0000-0000-4000-8000-000000000009", "usuario_coordenacao_id": ADMIN_ID, "nome": "pessoal",
        "origem": "pessoal", "hash_acesso": hash_acesso, "prefixo": prefixo, "revogado_em": None,
    }
    assert _revogar(api, cliente, pessoal).status_code == 200
    assert banco["token_mcp"]["70ce0000-0000-4000-8000-000000000009"].get("revogado_em") is None


def test_revoke_com_pedido_ruim(api, banco):
    cliente = _cadastrar(api)
    _erro(api.post("/oauth/revoke", data={"client_id": cliente["client_id"]}), 400, "invalid_request")
    _erro(api.post("/oauth/revoke", data={"token": "x", "client_id": "nao-existe"}), 401, "invalid_client")
    confidencial = _cadastrar(api, token_endpoint_auth_method="client_secret_basic")
    _erro(api.post("/oauth/revoke", data={"token": "x", "client_id": confidencial["client_id"]}),
          401, "invalid_client")


# ─── As portas não se misturam ───────────────────────────────────────────


@pytest.mark.parametrize("rota", ["/mcp/tokens", "/mcp/emails-ia", "/chat/threads", "/administracao/coordenadores"])
def test_access_do_oauth_nao_abre_as_rotas_da_api(api, banco, rota):
    """O access é opaco: `get_current_user` não o decodifica como JWT — o
    mesmo que vale para o token pessoal (test_mcp_rotas.py)."""
    _, par = _conectar(api)
    for token in (par["access_token"], par["refresh_token"]):
        assert api.get(rota, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_access_do_oauth_nao_aprova_outra_conexao(api, banco):
    """O consentimento não lê Bearer nenhum: o access de uma conexão não serve
    de sessão para aprovar outra — sem o código do e-mail, nada."""
    _, par = _conectar(api)
    _, pedido, _ = _pedido_novo(api)
    cabecalho = {"Authorization": f"Bearer {par['access_token']}"}
    assert api.post(f"/oauth/pedidos/{pedido}/aprovar", headers=cabecalho).status_code == 422
    assert _aprovar_com(api, pedido, EMAIL_DO_ADMIN, "123456", headers=cabecalho).status_code == 400
    assert banco["oauth_pedido_mcp"][pedido].get("decidido_em") is None


def test_refresh_como_bearer_no_mcp_nem_vai_ao_banco(api, banco):
    _, par = _conectar(api)
    mcp, fabrica = _mcp(banco)
    with TestClient(mcp) as c:
        assert _chamar_mcp(c, par["refresh_token"]).status_code == 401
    assert fabrica.rpcs == []


def test_access_do_oauth_de_conta_rebaixada_e_recusado_pelo_mcp(api, banco, config):
    """O MCP reconfere o papel a cada chamada (servidor._pode_consultar) — o
    access OAuth não é exceção. Com a regra do administrador ligada nos DOIS
    processos, como ela tem de estar."""
    config(emissao_so_administrador=True)
    _, par = _conectar(api)
    mcp, _ = _mcp(banco, emissao_so_administrador=True)
    with TestClient(mcp) as c:
        antes = _chamar_mcp(c, par["access_token"]).json()["result"]
        banco["usuario_coordenacao"][ADMIN_ID]["papel"] = "coordenador"
        depois = _chamar_mcp(c, par["access_token"]).json()["result"]
    assert antes["isError"] is False and depois["isError"] is True


# ─── O lado do MCP: RFC 9728 ─────────────────────────────────────────────


def test_metadado_do_recurso_nos_dois_caminhos(banco):
    mcp, fabrica = _mcp(banco)
    with TestClient(mcp) as c:
        com_caminho = c.get("/.well-known/oauth-protected-resource/mcp")
        raiz = c.get("/.well-known/oauth-protected-resource", headers={"origin": "https://inspector.example"})
    assert com_caminho.status_code == raiz.status_code == 200
    assert com_caminho.json() == raiz.json() == {
        "resource": RECURSO,
        "authorization_servers": [EMISSOR],
        "scopes_supported": ["sas.leitura"],
        "bearer_methods_supported": ["header"],
        "resource_name": "SAS — coordenação",
    }
    assert raiz.headers["access-control-allow-origin"] == "*"
    assert fabrica.rpcs == []                               # público e sem banco


def test_emissor_sem_caminho_e_recurso_na_raiz():
    from app.mcp.app import (
        caminhos_do_metadado_do_recurso,
        metadado_do_recurso,
        url_do_metadado_do_recurso,
    )

    assert caminhos_do_metadado_do_recurso("https://portalsas.online/mcp/") == [
        "/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource"]
    assert caminhos_do_metadado_do_recurso("https://mcp.portalsas.online") == ["/.well-known/oauth-protected-resource"]
    assert url_do_metadado_do_recurso(RECURSO) == "https://portalsas.online/.well-known/oauth-protected-resource/mcp"
    cfg = ConfiguracaoMcp(_env_file=None, emissor_oauth="https://portalsas.online/", url_publica="https://portalsas.online/mcp/")
    assert metadado_do_recurso(cfg)["authorization_servers"] == ["https://portalsas.online"]
    assert metadado_do_recurso(cfg)["resource"] == RECURSO


# ─── Configuração ────────────────────────────────────────────────────────


def test_problemas_do_oauth_fora_de_dev():
    assert problemas_do_oauth(_cfg(), "production") == []
    assert problemas_do_oauth(_cfg(emissor_oauth=""), "production") == []                # desligado
    assert any("https" in p for p in problemas_do_oauth(_cfg(emissor_oauth="http://portalsas.online/api"), "production"))
    assert any("localhost" in p for p in problemas_do_oauth(_cfg(emissor_oauth="https://localhost/api"), "production"))
    assert any("https" in p for p in problemas_do_oauth(_cfg(url_do_app="http://portalsas.online"), "production"))
    assert problemas_do_oauth(_cfg(url_do_app=""), "dev")
    assert problemas_do_oauth(_cfg(url_publica=""), "dev")
    assert problemas_do_oauth(_cfg(emissor_oauth="https://portalsas.online/api?x=1"), "dev")
    # Em dev, http e localhost valem — é o compose.
    assert problemas_do_oauth(_cfg(emissor_oauth="http://localhost:8000", url_do_app="http://localhost:8080"), "dev") == []


def test_guard_do_mcp_recusa_emissor_inseguro_em_producao():
    settings = Settings(_env_file=None, app_env="production", postgrest_url="http://postgrest_mcp:3000")
    validar_configuracao_do_mcp(_cfg(), settings)
    with pytest.raises(RuntimeError, match="MCP_EMISSOR_OAUTH"):
        validar_configuracao_do_mcp(_cfg(emissor_oauth="http://portalsas.online/api"), settings)
    assert problemas_do_emissor(_cfg(emissor_oauth=""), "production") == []


def test_escopo_da_api_e_o_do_mcp():
    from app.mcp.servidor import ESCOPO_DE_LEITURA

    assert oauth_mcp.ESCOPO == ESCOPO_DE_LEITURA


def test_a_api_nao_importa_o_sdk_do_mcp():
    """A API importa `app.mcp.tokens` e `app.mcp.configuracao`; o SDK, nunca —
    puxaria o servidor MCP inteiro para o processo dela (app/mcp/__init__.py).
    Num processo novo, porque neste os testes do MCP já carregaram o SDK."""
    codigo = "import sys, app.main; print(any(n == 'mcp' or n.startswith('mcp.') for n in sys.modules))"
    resultado = subprocess.run(  # noqa: S603 — argv fixo, o próprio interpretador
        [sys.executable, "-c", codigo],
        cwd=Path(__file__).resolve().parent.parent,
        env={**os.environ, "APP_ENV": "dev"},
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert resultado.returncode == 0, resultado.stderr[-2000:]
    # A última linha: antes dela, no mesmo stdout, vêm as do log do boot (o
    # valor efetivo de MCP_*, configuracao.registrar_no_log).
    assert resultado.stdout.strip().splitlines()[-1] == "False"


# ─── Funções puras ───────────────────────────────────────────────────────


def test_desafio_s256_do_apendice_b_do_rfc_7636():
    assert oauth_mcp.desafio_s256("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def test_descricao_de_erro_so_em_ascii():
    assert oauth_mcp._ascii('Código "inválido" \\ — já usado') == "Codigo invalido   ja usado"


def test_teto_por_ip_tem_janela_e_teto_de_memoria():
    class Relogio:
        agora = 0.0

        def __call__(self):
            return self.agora

    relogio = Relogio()
    teto = oauth_mcp.TetoPorIp(60.0, relogio=relogio)
    assert teto.admitir("198.51.100.1", 2) and teto.admitir("198.51.100.1", 2)
    assert not teto.admitir("198.51.100.1", 2) and teto.admitir("198.51.100.2", 2)
    relogio.agora += 61
    assert teto.admitir("198.51.100.1", 2)
    teto.MAXIMO_DE_CHAVES = 3
    for i in range(10):
        teto.admitir(f"10.0.0.{i}", 5)
    assert len(teto._por_ip) == 3


def test_validar_cadastro_e_pura_e_tira_repeticao():
    cadastro = oauth_mcp.validar_cadastro({"redirect_uris": [VOLTA, VOLTA], "grant_types": ["authorization_code"] * 2})
    assert cadastro.redirect_uris == (VOLTA,) and cadastro.concessoes == ("authorization_code",)
    assert cadastro.metodo == "client_secret_basic" and cadastro.nome is None


# ─── O piso das rotas ────────────────────────────────────────────────────

PISO_ESPERADO = {
    # O protocolo: público, como o RFC manda — o que protege é o PKCE, a
    # redirect_uri cadastrada e o consentimento.
    ("GET", "/.well-known/oauth-authorization-server"): "SEM GUARD",
    ("GET", "/.well-known/oauth-authorization-server/{caminho:path}"): "SEM GUARD",
    ("POST", "/oauth/register"): "SEM GUARD",
    ("GET", "/oauth/authorize"): "SEM GUARD",
    ("POST", "/oauth/token"): "SEM GUARD",
    ("POST", "/oauth/revoke"): "SEM GUARD",
    # O consentimento: público desde 26/10 (decisão do dono). Quem aprova prova
    # a posse do e-mail da conta de IA com o código enviado a ele, e o "só
    # administrador", quando ligado, é conferido DENTRO da rota, contra a
    # tabela. Um guard de sessão aqui reabriria a segunda porta de aprovação.
    ("GET", "/oauth/pedidos/{pedido_id}"): "SEM GUARD",
    ("POST", "/oauth/pedidos/{pedido_id}/codigo"): "SEM GUARD",
    ("POST", "/oauth/pedidos/{pedido_id}/aprovar"): "SEM GUARD",
    ("POST", "/oauth/pedidos/{pedido_id}/recusar"): "SEM GUARD",
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


def test_matriz_das_rotas_do_oauth():
    """Rota nova quebra este teste até alguém declarar de que lado ela fica."""
    rotas = [*oauth_mcp.router.routes, *oauth_mcp.router_consentimento.routes]
    assert {(sorted(r.methods)[0], r.path): _piso(r) for r in rotas} == PISO_ESPERADO


# ─── Regressões da revisão de segurança de 26/10 (lente "codigo-do-email") ───


_VOLTA_LONGA = "https://exemplo.com/" + "a" * 1900


def test_recusa_anonima_vencida_e_varrida_e_o_aprovado_fica(api, banco):
    """(ALTA) O pedido RECUSADO é decidido mas não é história — a recusa vai ao
    log, nada nasce dele (nenhum código do RFC, nenhum refresh). Vencido, a
    faxina tem de varrê-lo; senão authorize→recusar em laço, com um cliente só e
    sem sessão, grava linhas permanentes de até ~4 KB sem teto de volume, no
    banco dos alunos (a reabertura do buraco que a 25/10 fechou). O APROVADO
    vencido NÃO é varrido: é a história de quem conectou que app (0073)."""
    cliente = _cadastrar(api, redirect_uris=[_VOLTA_LONGA])

    recusados = []
    for _ in range(12):  # 12 > teto de abertos por app (10): só passa porque recusar "fecha" a vaga
        _, desafio = _pkce()
        p = _pedido_da(
            _autorizar(api, cliente, desafio, redirect_uri=_VOLTA_LONGA, state="s" * 2048, resource=None)
        )
        assert api.post(f"/oauth/pedidos/{p}/recusar").status_code == 200
        recusados.append(p)

    # Um pedido APROVADO, sem passar pelo fluxo de e-mail/código: a `_decidir`
    # grava a mesma linha que a aprovação grava (aprovado=True, com autor).
    _, desafio = _pkce()
    aprovado = _pedido_da(_autorizar(api, cliente, desafio, redirect_uri=_VOLTA_LONGA, resource=None))
    assert oauth_mcp._decidir(oauth_mcp.get_supabase(), aprovado, ADMIN_ID, True, datetime.now(UTC))

    # Tudo vence; o próximo authorize dispara a faxina (uma vez por intervalo).
    for linha in banco["oauth_pedido_mcp"].values():
        linha["expira_em"] = _passado(30)
    oauth_mcp.FAXINA_DOS_PEDIDOS.limpar()
    _, desafio = _pkce()
    novo = _pedido_da(_autorizar(api, cliente, desafio, redirect_uri=_VOLTA_LONGA, resource=None))

    restantes = set(banco["oauth_pedido_mcp"])
    assert not (set(recusados) & restantes), "pedido recusado vencido sobreviveu à faxina"
    assert aprovado in restantes, "a faxina apagou a história de uma aprovação"
    assert novo in restantes


def test_recusado_que_ainda_vale_nao_e_varrido(api, banco):
    """A faxina só varre o recusado VENCIDO — não o que acabou de ser recusado e
    ainda está no prazo (a mesma semântica de 'vencido' dos sem decisão)."""
    cliente = _cadastrar(api)
    _, desafio = _pkce()
    recusado = _pedido_da(_autorizar(api, cliente, desafio))
    assert api.post(f"/oauth/pedidos/{recusado}/recusar").status_code == 200

    oauth_mcp._apagar_pedidos_vencidos(oauth_mcp.get_supabase(), datetime.now(UTC))
    assert recusado in banco["oauth_pedido_mcp"], "recusado dentro do prazo não devia ser varrido"


class _SesQueVazaNoErro:
    """(MÉDIA) O SES que falha como o botocore no sandbox (docs/15): a mensagem
    do erro carrega o endereço (MessageRejected de destinatário não verificado)."""

    def email_configurado(self) -> bool:
        return True

    def enviar_email(self, *, destinatario: str, assunto: str, corpo: str) -> None:
        raise RuntimeError(
            "An error occurred (MessageRejected): Email address is not verified. The following "
            f"identities failed the check in region US-EAST-1: {destinatario}"
        )


def test_erro_do_ses_nao_vaza_o_email_inteiro_no_log(api, banco, monkeypatch, caplog):
    """Com o SES recusando o envio, o log de produção (o _FormatadorJSON) não
    pode conter o e-mail INTEIRO — só o mascarado. Antes do conserto, o
    `log.exception` de `_preparar_codigo` gravava a exceção do botocore (com o
    endereço) no campo `excecao`, contra a máscara do resto do módulo."""
    import logging

    from app.observabilidade import _FormatadorJSON

    # O e-mail precisa estar confirmado para o envio chegar a ser tentado
    # (_cadastro_que_aprova). Posto à mão, sem depender do fluxo de confirmação.
    banco["email_conta_ia_mcp"][EMAIL_ADMIN_ID]["confirmado_em"] = "2026-10-26T12:00:00.000000Z"
    monkeypatch.setattr(oauth_mcp, "email_ses", _SesQueVazaNoErro())

    _, pedido, _ = _pedido_novo(api)
    with caplog.at_level(logging.INFO, logger="sas.oauth"):
        assert _pedir_codigo(api, pedido, EMAIL_DO_ADMIN).status_code == 202

    linhas = [_FormatadorJSON().format(r) for r in caplog.records if r.name == "sas.oauth"]
    assert linhas, "nada foi logado — o envio não chegou a ser tentado"
    assert not any(EMAIL_DO_ADMIN in linha for linha in linhas), "o e-mail inteiro vazou no log"
    mascarado = emails_ia.mascarar_email(EMAIL_DO_ADMIN)  # a***@exemplo.com
    assert any(mascarado in linha and '"nivel": "ERROR"' in linha for linha in linhas)
