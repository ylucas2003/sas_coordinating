"""As rotas de Conexões de IA na API: emitir, listar e revogar o token do MCP.

Os handlers são `def` e são chamados direto, com o FakeCliente no lugar do
PostgREST — o padrão de test_papeis.py ("passar por HTTP só acrescentaria
ruído"). Por HTTP ficam só as duas coisas que falham ANTES do banco: o token
do MCP não abre rota de sessão da API.

E um ponta a ponta sem rede: emite pela ROTA, chama o MCP com o token sobre o
MESMO banco falso (a RPC da 0072 emulada em test_mcp_tokens.py), revoga pela
rota, e o MCP passa a dar 401.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_mcp_rotas.py -q
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.testclient import TestClient

from app import auth
from app.mcp import tokens
from app.mcp.configuracao import ConfiguracaoMcp
from app.routes import mcp_tokens
from tests.test_mcp_tokens import FabricaDeClientes, FakeClienteDoMcp

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"

ADMIN_ID = "ad000000-0000-4000-8000-000000000001"
COORD_ID = "c0000000-0000-4000-8000-000000000002"
ADMINISTRADOR = {"sub": ADMIN_ID, "tipo": "coordenador", "papel": "administrador", "nome": "Admin"}
COORDENADOR = {"sub": COORD_ID, "tipo": "coordenador", "papel": "coordenador", "nome": "Coord"}


def _contas() -> dict:
    return {
        "usuario_coordenacao": {
            ADMIN_ID: {"id": ADMIN_ID, "nome": "Admin da Casa", "papel": "administrador", "ativo": True},
            COORD_ID: {"id": COORD_ID, "nome": "Coordenadora", "papel": "coordenador", "ativo": True},
        },
        "token_mcp": {},
        "evento_auditoria": {},
    }


@pytest.fixture
def banco(monkeypatch) -> dict:
    """O mesmo banco para a rota e para o guard de administrador — é o que
    deixa rebaixar na tabela valer na hora, como em test_papeis.py."""
    db = _contas()
    monkeypatch.setattr(mcp_tokens, "get_supabase", lambda: FakeClienteDoMcp(db))
    monkeypatch.setattr(auth, "get_supabase", lambda: FakeClienteDoMcp(db))
    return db


@pytest.fixture
def config(monkeypatch):
    """A configuração que a rota lê. Por padrão a de produção: desde 26/10,
    administrador E coordenador emitem (decisão do dono). Os testes trocam os
    campos que precisam — o "só o administrador" é opção, com testes próprios."""
    atual = {"cfg": ConfiguracaoMcp(_env_file=None, url_publica="https://portalsas.online/mcp", habilitado=True)}
    monkeypatch.setattr(mcp_tokens, "get_configuracao_mcp", lambda: atual["cfg"])

    def trocar(**kw):
        atual["cfg"] = ConfiguracaoMcp(_env_file=None, **kw)

    return trocar


class _Pedido:
    def __init__(self, ip: str | None = "203.0.113.7"):
        self.client = type("C", (), {"host": ip})()


def _emitir(sessao=ADMINISTRADOR, nome="Claude Code do Leo"):
    return mcp_tokens.emitir_conexao(mcp_tokens.EmitirConexaoBody(nome=nome), _Pedido(), sessao)


def _revogar(conexao_id, sessao=ADMINISTRADOR):
    return mcp_tokens.revogar_conexao(conexao_id, _Pedido(), sessao)


# ─── Emitir ──────────────────────────────────────────────────────────────


def test_emitir_mostra_o_token_uma_vez_e_guarda_so_o_hash(banco, config):
    criada = _emitir()
    assert tokens.formato_valido(criada.token)
    assert criada.prefixo == criada.token[:12] and criada.origem == "pessoal"
    assert criada.dono.id == ADMIN_ID and criada.dono.nome == "Admin da Casa"

    (linha,) = banco["token_mcp"].values()
    assert linha["hash_acesso"] == tokens.hash_do_token(criada.token)
    # O token em claro não está em NENHUM valor da linha — nem pedaço dele além do prefixo.
    assert all(criada.token not in str(v) for v in linha.values())
    assert criada.token[12:] not in json.dumps(linha, default=str)


def test_a_auditoria_da_emissao_guarda_so_o_nome(banco, config):
    criada = _emitir()
    (evento,) = banco["evento_auditoria"].values()
    assert evento["acao"] == "mcp_token_emitido" and evento["canal"] == "mcp"
    assert evento["ator_tipo"] == "coordenador" and evento["ator_id"] == ADMIN_ID
    assert evento["recurso"] == f"mcp_token/{criada.id}"
    assert evento["detalhe"] == {"nome": "Claude Code do Leo"}
    texto = json.dumps(evento, default=str)
    assert criada.token not in texto
    assert tokens.hash_do_token(criada.token) not in texto
    assert criada.prefixo not in texto


def test_token_pessoal_vence_na_validade_configurada(banco, config):
    from datetime import datetime, timedelta

    config(validade_do_token_dias=30)
    criada = _emitir()
    dias = datetime.fromisoformat(criada.expiraEm) - datetime.fromisoformat(criada.criadaEm)
    assert dias == timedelta(days=30)

    config(validade_do_token_dias=0)
    assert _emitir(nome="sem validade").expiraEm is None


def test_com_so_o_administrador_ligado_o_coordenador_leva_403(banco, config):
    config(emissao_so_administrador=True)
    with pytest.raises(HTTPException) as erro:
        _emitir(COORDENADOR)
    assert erro.value.status_code == 403
    assert banco["token_mcp"] == {}
    assert _emitir(ADMINISTRADOR).dono.id == ADMIN_ID


def test_por_padrao_o_coordenador_emite_para_si(banco, config):
    """A decisão do dono de 26/10: administrador E coordenador conectam, cada
    um em nome da própria conta."""
    criada = _emitir(COORDENADOR)
    assert criada.dono.id == COORD_ID
    (linha,) = banco["token_mcp"].values()
    assert linha["usuario_coordenacao_id"] == COORD_ID


def test_administrador_rebaixado_na_tabela_nao_emite_com_o_token_velho(banco, config):
    """O papel viaja num token de 8 h; quem decide é a tabela (como em
    `get_current_administrador`) — com a regra do administrador ligada."""
    config(emissao_so_administrador=True)
    banco["usuario_coordenacao"][ADMIN_ID]["papel"] = "coordenador"
    with pytest.raises(HTTPException) as erro:
        _emitir(ADMINISTRADOR)
    assert erro.value.status_code == 403


#: A recusa do modo só-administrador, letra por letra: a prova de ponta a ponta
#: de 27/10 compara o texto.
FRASE_SO_ADMINISTRADOR = (
    "Conectar uma IA ao SAS está, neste ambiente, restrito ao administrador "
    "(MCP_EMISSAO_SO_ADMINISTRADOR, docs/43 §5.4)."
)


@pytest.mark.parametrize(
    "sessao", [COORDENADOR, ADMINISTRADOR], ids=["coordenador", "administrador"]
)
def test_conta_desativada_nao_emite_com_o_jwt_que_ja_tinha(banco, config, sessao):
    """O defeito da prova de ponta a ponta de 27/10. `get_current_coordenador`
    decide só pelo JWT, que vale 8 h, e a conta desativada no meio dele emitia
    token pessoal (201). O token nascia morto — a RPC da 0072 exige a conta
    ativa —, mas REVIVIA se a conta fosse reativada. A emissão relê a conta na
    tabela, com a régua da aprovação OAuth: 403 com frase própria, e nada
    gravado, nem a linha nem a auditoria."""
    banco["usuario_coordenacao"][sessao["sub"]]["ativo"] = False
    with pytest.raises(HTTPException) as erro:
        _emitir(sessao)
    assert erro.value.status_code == 403
    assert erro.value.detail == auth.MENSAGEM_CONTA_DESATIVADA
    assert banco["token_mcp"] == {} and banco["evento_auditoria"] == {}
    # A releitura é a cada pedido: reativada, a conta volta a emitir.
    banco["usuario_coordenacao"][sessao["sub"]]["ativo"] = True
    assert _emitir(sessao).dono.id == sessao["sub"]


def test_com_so_o_administrador_ligado_cada_recusa_tem_a_sua_frase(banco, config):
    """A do só-administrador fica como era; a da conta desativada é outra, e
    vale também para o administrador: desativado, ninguém conecta, e dizer a
    ele que a emissão é "restrita ao administrador" daria o motivo errado."""
    config(emissao_so_administrador=True)
    with pytest.raises(HTTPException) as erro:
        _emitir(COORDENADOR)
    assert (erro.value.status_code, erro.value.detail) == (403, FRASE_SO_ADMINISTRADOR)

    banco["usuario_coordenacao"][ADMIN_ID]["ativo"] = False
    with pytest.raises(HTTPException) as erro:
        _emitir(ADMINISTRADOR)
    assert erro.value.status_code == 403 and erro.value.detail != FRASE_SO_ADMINISTRADOR
    assert erro.value.detail == auth.MENSAGEM_CONTA_DESATIVADA
    assert banco["token_mcp"] == {}


def test_a_tela_conhece_a_frase_da_conta_desativada_letra_por_letra():
    """Emitir token tem dois 403, e a tela de Conexões de IA os separa pela
    frase: a do só-administrador ela troca pela dela, que diz a quem recorrer,
    e a da conta desativada ela mostra (`fraseDoProibido`, em
    web/src/dominio/conexoesDeIa.ts). Com as duas cópias separadas, a conta
    desativada voltava a ler "só do administrador", o motivo errado.

    IGUAL, e não só contida: um sufixo concatenado no .ts (`'…' + '…'`)
    passaria por um `in` e separaria as duas (revisão de 27/10). Como o
    CATALOGO_DE_ARTEFATOS de test_chat_ferramentas, a constante é lida pela
    forma — uma string só, entre aspas simples —, e mudar a forma reprova."""
    dominio = Path(__file__).resolve().parents[2] / "web" / "src" / "dominio" / "conexoesDeIa.ts"
    if not dominio.exists():
        pytest.skip("web/ fora deste checkout (container da API)")
    achado = re.search(r"export const MENSAGEM_CONTA_DESATIVADA =\s*'([^']*)';", dominio.read_text(encoding="utf-8"))
    assert achado, "MENSAGEM_CONTA_DESATIVADA sumiu do .ts ou mudou de forma (uma string só, entre aspas simples)"
    assert achado.group(1) == auth.MENSAGEM_CONTA_DESATIVADA


def test_conta_desativada_ainda_lista_e_revoga_as_suas(banco, config):
    """Só a emissão recusa a conta desativada. Listar e revogar só tiram
    acesso, e tirar acesso nunca depende de poder dar acesso."""
    criada = _emitir(COORDENADOR)
    banco["usuario_coordenacao"][COORD_ID]["ativo"] = False
    assert [c.id for c in mcp_tokens.listar_conexoes(COORDENADOR)] == [criada.id]
    assert _revogar(criada.id, COORDENADOR).revogadaEm is not None


@pytest.mark.parametrize("nome", ["", "   ", "x" * 81])
def test_nome_da_conexao_tem_de_1_a_80(nome):
    with pytest.raises(ValidationError):
        mcp_tokens.EmitirConexaoBody(nome=nome)


def test_nome_da_conexao_sai_aparado():
    assert mcp_tokens.EmitirConexaoBody(nome="  Claude Desktop  ").nome == "Claude Desktop"
    assert mcp_tokens.EmitirConexaoBody(nome="x" * 80).nome == "x" * 80


# ─── Listar ──────────────────────────────────────────────────────────────


def test_listar_nunca_traz_hash(banco, config):
    _emitir()
    (conexao,) = mcp_tokens.listar_conexoes(ADMINISTRADOR)
    dump = conexao.model_dump()
    assert "hash_acesso" not in dump and "token" not in dump
    assert not any(isinstance(v, str) and len(v) == 64 for v in dump.values())
    assert set(dump) == {"id", "nome", "prefixo", "origem", "cliente", "criadaEm", "ultimoUsoEm",
                         "expiraEm", "revogadaEm", "dono"}


def test_coordenador_ve_so_as_suas_e_administrador_ve_todas(banco, config):
    do_admin = _emitir(ADMINISTRADOR, "do admin")
    da_coord = _emitir(COORDENADOR, "da coordenadora")
    assert [c.id for c in mcp_tokens.listar_conexoes(COORDENADOR)] == [da_coord.id]
    assert {c.id for c in mcp_tokens.listar_conexoes(ADMINISTRADOR)} == {do_admin.id, da_coord.id}


# ─── Revogar ─────────────────────────────────────────────────────────────


def test_coordenador_nao_revoga_a_de_outro_404(banco, config):
    alheia = _emitir(ADMINISTRADOR)
    with pytest.raises(HTTPException) as erro:
        _revogar(alheia.id, COORDENADOR)
    # 404 e não 403: "existe, mas não é sua" já contaria quem tem conexão.
    assert erro.value.status_code == 404
    assert banco["token_mcp"][alheia.id].get("revogado_em") is None


def test_administrador_revoga_a_de_qualquer_um(banco, config):
    da_coord = _emitir(COORDENADOR)
    revogada = _revogar(da_coord.id, ADMINISTRADOR)
    assert revogada.revogadaEm is not None and revogada.dono.id == COORD_ID
    linha = banco["token_mcp"][da_coord.id]
    assert linha["revogado_por"] == ADMIN_ID
    eventos = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_token_revogado"]
    assert len(eventos) == 1 and eventos[0]["detalhe"] == {"nome": "Claude Code do Leo"}
    assert eventos[0]["ator_id"] == ADMIN_ID and eventos[0]["recurso"] == f"mcp_token/{da_coord.id}"


def test_coordenador_revoga_a_propria_mesmo_com_emissao_fechada(banco, config):
    """Tirar acesso nunca depende de poder dar acesso."""
    propria = _emitir(COORDENADOR)
    config(emissao_so_administrador=True)
    assert _revogar(propria.id, COORDENADOR).revogadaEm is not None


def test_revogar_de_novo_devolve_igual_sem_segundo_evento(banco, config):
    criada = _emitir()
    primeira = _revogar(criada.id)
    segunda = _revogar(criada.id)
    assert segunda.revogadaEm == primeira.revogadaEm
    assert sum(e["acao"] == "mcp_token_revogado" for e in banco["evento_auditoria"].values()) == 1


@pytest.mark.parametrize("conexao_id", ["nao-e-uuid", "1; drop table", "70ce0000-0000-4000-8000-00000000ffff"])
def test_id_torto_ou_inexistente_e_404(banco, config, conexao_id):
    with pytest.raises(HTTPException) as erro:
        _revogar(conexao_id)
    assert erro.value.status_code == 404


# ─── Disponibilidade ─────────────────────────────────────────────────────


def test_disponibilidade_no_formato_do_contrato(config):
    # O mesmo contrato de antes; o padrão de emissaoSoAdministrador é que virou
    # false em 26/10 (administrador e coordenador conectam).
    assert mcp_tokens.disponibilidade().model_dump() == {
        "habilitado": True, "emissaoSoAdministrador": False, "urlDoServidor": "https://portalsas.online/mcp",
    }
    config()
    assert mcp_tokens.disponibilidade().model_dump() == {
        "habilitado": False, "emissaoSoAdministrador": False, "urlDoServidor": None,
    }
    config(emissao_so_administrador=True)
    assert mcp_tokens.disponibilidade().emissaoSoAdministrador is True


# ─── O piso das rotas ────────────────────────────────────────────────────

PISO_ESPERADO = {
    ("GET", "/mcp/disponibilidade"): "coordenador",
    ("GET", "/mcp/tokens"): "coordenador",
    ("POST", "/mcp/tokens"): "coordenador",
    ("POST", "/mcp/tokens/{conexao_id}/revogar"): "coordenador",
}


def _piso(rota) -> str:
    """O guard mais alto que a rota atravessa — a mesma régua de test_papeis.py.

    Tudo aqui é piso de coordenação: o "só administrador" da emissão depende
    de configuração e é conferido DENTRO da rota, contra a tabela."""
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


def test_matriz_das_rotas_do_mcp():
    assert {(sorted(r.methods)[0], r.path): _piso(r) for r in mcp_tokens.router.routes} == PISO_ESPERADO


# ─── O token do MCP não abre a API ───────────────────────────────────────


@pytest.fixture
def api(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    from app.main import create_app

    yield TestClient(create_app())
    get_settings.cache_clear()


@pytest.mark.parametrize("rota", ["/chat/threads", "/mcp/tokens", "/administracao/coordenadores"])
def test_token_do_mcp_como_bearer_na_api_e_401(api, rota):
    """O irmão de test_auth_chat.py: o token do MCP é opaco, não decodifica
    como JWT, e por isso `get_current_user` o recusa antes de qualquer banco.
    Um token de MCP nunca abre rota de sessão (docs/43 §5.3)."""
    token, _, _ = tokens.gerar()
    assert api.get(rota, headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ─── O script de operação ────────────────────────────────────────────────


def test_script_grava_o_token_em_arquivo_600_e_nunca_no_stdout(tmp_path, monkeypatch, capsys):
    """scripts/criar_token_mcp.py: o stdout de um Job é retido pelo coletor de
    logs, então o token vai para um arquivo chmod 600 — o mesmo cuidado de
    scripts/criar_coordenador.py com a senha."""
    import stat

    from scripts import criar_token_mcp

    db = _contas()
    db["usuario_coordenacao"][COORD_ID]["email"] = "coord@ari.com.br"
    monkeypatch.setenv("SAS_SAIDA_TOKEN", str(tmp_path))
    # Conta de coordenador: só emite com a regra do administrador desligada.
    monkeypatch.setattr(criar_token_mcp, "get_configuracao_mcp",
                        lambda: ConfiguracaoMcp(_env_file=None, validade_do_token_dias=7,
                                                emissao_so_administrador=False))

    assert criar_token_mcp._emitir(FakeClienteDoMcp(db), "Coord@Ari.com.br", "Claude Desktop") == 0

    (arquivo,) = tmp_path.iterdir()
    token = arquivo.read_text().strip()
    assert tokens.formato_valido(token)
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    saida = capsys.readouterr().out
    assert token not in saida and token[12:] not in saida
    (linha,) = db["token_mcp"].values()
    assert linha["hash_acesso"] == tokens.hash_do_token(token) and linha["usuario_coordenacao_id"] == COORD_ID
    assert linha["expira_em"] is not None

    # E revoga pelo id que o --listar mostra, sem autor (quem roda não é conta do SAS).
    assert criar_token_mcp._revogar(FakeClienteDoMcp(db), linha["id"]) == 0
    assert linha["revogado_em"] is not None and linha.get("revogado_por") is None


def test_script_recusa_conta_desativada(tmp_path, monkeypatch):
    from scripts import criar_token_mcp

    db = _contas()
    db["usuario_coordenacao"][COORD_ID].update(email="coord@ari.com.br", ativo=False)
    monkeypatch.setenv("SAS_SAIDA_TOKEN", str(tmp_path))
    assert criar_token_mcp._emitir(FakeClienteDoMcp(db), "coord@ari.com.br", "x") == 1
    assert db["token_mcp"] == {} and list(tmp_path.iterdir()) == []


def test_script_segue_a_regra_do_administrador(tmp_path, monkeypatch, capsys):
    """A tela recusava, o script emitia para qualquer conta ativa (revisão de
    24/10) — e o MCP recusaria as chamadas desse token de qualquer jeito."""
    from scripts import criar_token_mcp

    db = _contas()
    db["usuario_coordenacao"][COORD_ID]["email"] = "coord@ari.com.br"
    monkeypatch.setenv("SAS_SAIDA_TOKEN", str(tmp_path))
    monkeypatch.setattr(criar_token_mcp, "get_configuracao_mcp",
                        lambda: ConfiguracaoMcp(_env_file=None, emissao_so_administrador=True))
    assert criar_token_mcp._emitir(FakeClienteDoMcp(db), "coord@ari.com.br", "x") == 1
    assert "não é administrador" in capsys.readouterr().out
    assert db["token_mcp"] == {} and list(tmp_path.iterdir()) == []


def _conta_de_admin_com_email(db: dict) -> str:
    db["usuario_coordenacao"][ADMIN_ID]["email"] = "admin@ari.com.br"
    return "admin@ari.com.br"


def test_script_cria_o_arquivo_do_token_ja_fechado_e_exclusivo(tmp_path, monkeypatch):
    """`touch()` + `chmod(0o600)` deixava o arquivo com 0644 entre os dois — no
    /tmp compartilhado, outro usuário o abria nessa janela e lia o token depois
    (revisão de 24/10). Agora ele NASCE com 0600, e com O_EXCL."""
    import os

    from scripts import criar_token_mcp

    aberturas: list[tuple[int, int]] = []
    abrir = os.open

    def espia(caminho, bandeiras, modo=0o777, *a, **k):
        if str(caminho).startswith(str(tmp_path)):
            aberturas.append((bandeiras, modo))
        return abrir(caminho, bandeiras, modo, *a, **k)

    db = _contas()
    email = _conta_de_admin_com_email(db)
    monkeypatch.setenv("SAS_SAIDA_TOKEN", str(tmp_path))
    monkeypatch.setattr(criar_token_mcp, "get_configuracao_mcp", lambda: ConfiguracaoMcp(_env_file=None))
    monkeypatch.setattr(os, "open", espia)
    assert criar_token_mcp._emitir(FakeClienteDoMcp(db), email, "Claude Code") == 0

    assert len(aberturas) == 1, "o arquivo do token tem de nascer num os.open só"
    bandeiras, modo = aberturas[0]
    assert bandeiras & os.O_CREAT and bandeiras & os.O_EXCL and modo == 0o600


def test_script_nao_escreve_em_arquivo_ou_symlink_plantado(tmp_path, monkeypatch):
    import os

    from scripts import criar_token_mcp

    alvo = tmp_path / "do-outro.txt"
    alvo.write_text("")
    alvo.chmod(0o644)
    (tmp_path / "plantado.txt").symlink_to(alvo)
    monkeypatch.setenv("SAS_SAIDA_TOKEN", str(tmp_path))
    with pytest.raises(FileExistsError):
        criar_token_mcp._abrir_destino_do_token("plantado.txt")
    # O `touch()` + `chmod` de antes seguiam o symlink e mexiam no arquivo do outro.
    assert alvo.read_text() == "" and alvo.stat().st_mode & 0o777 == 0o644

    # E o `_emitir` para ANTES do banco, sem traceback.
    def ja_existe(_nome):
        raise FileExistsError(17, os.strerror(17))

    db = _contas()
    email = _conta_de_admin_com_email(db)
    monkeypatch.setattr(criar_token_mcp, "get_configuracao_mcp", lambda: ConfiguracaoMcp(_env_file=None))
    monkeypatch.setattr(criar_token_mcp, "_abrir_destino_do_token", ja_existe)
    assert criar_token_mcp._emitir(FakeClienteDoMcp(db), email, "x") == 1
    assert db["token_mcp"] == {}


def test_script_apaga_o_arquivo_vazio_se_o_banco_falha(tmp_path, monkeypatch):
    from scripts import criar_token_mcp

    def _recusa(*_a, **_k):
        raise RuntimeError("PostgREST fora")

    class _BancoQueRecusaInsert(FakeClienteDoMcp):
        def table(self, nome):
            tabela = super().table(nome)
            if nome == "token_mcp":
                tabela.insert = _recusa
            return tabela

    db = _contas()
    email = _conta_de_admin_com_email(db)
    monkeypatch.setenv("SAS_SAIDA_TOKEN", str(tmp_path))
    monkeypatch.setattr(criar_token_mcp, "get_configuracao_mcp", lambda: ConfiguracaoMcp(_env_file=None))
    with pytest.raises(RuntimeError):
        criar_token_mcp._emitir(_BancoQueRecusaInsert(db), email, "x")
    assert list(tmp_path.iterdir()) == []


# ─── Ponta a ponta: emite pela rota, usa no MCP, revoga pela rota ────────


def test_emitido_pela_rota_abre_o_mcp_e_revogado_fecha(banco, config):
    from app.chat.ferramentas import Ferramenta, Registro
    from app.mcp.app import montar_app
    from app.mcp.servidor import montar_servidor

    criada = _emitir()
    banco["aluno"] = {}
    fabrica = FabricaDeClientes(banco)
    cfg = ConfiguracaoMcp(_env_file=None, hosts_permitidos="testserver")
    registro = Registro([Ferramenta(
        nome="listar_ciclos", descricao="ciclos", parametros={"type": "object", "properties": {}},
        escopo="coordenacao", handler=lambda cliente: {"total": 0, "ciclos": []}, expor_no_mcp=True,
    )])
    app = montar_app(config=cfg, criar_cliente=fabrica, app_env="test",
                     servidor=montar_servidor(config=cfg, registro=registro, criar_cliente=fabrica))
    cabecalhos = {"accept": "application/json", "content-type": "application/json",
                  "authorization": f"Bearer {criada.token}"}
    corpo = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": "listar_ciclos", "arguments": {}}})

    with TestClient(app) as c:
        assert c.post("/mcp", headers=cabecalhos, content=corpo).status_code == 200
        _revogar(criada.id)
        assert c.post("/mcp", headers=cabecalhos, content=corpo).status_code == 401

    chamadas = [e for e in banco["evento_auditoria"].values() if e["acao"] == "mcp_ferramenta_chamada"]
    assert len(chamadas) == 1 and chamadas[0]["ator_id"] == ADMIN_ID
    assert banco["token_mcp"][criada.id]["ultimo_uso_em"] is not None
