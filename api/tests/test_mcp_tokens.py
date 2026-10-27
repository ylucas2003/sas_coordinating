"""O token do MCP e o guard de boot do processo (docs/43 §5.3, migration 0072).

O token é opaco e só o sha256 dele vive no banco; quem confere é a RPC
`mcp_conferir_token`, que aqui é EMULADA em Python (`conferir_como_a_0072`)
com as mesmas regras do plpgsql: revogado, vencido e conta desativada não
devolvem nada. A emulação mora neste arquivo e os outros testes do MCP a
importam — `test_mcp_rotas.py` emite pela rota e confere pelo MCP sobre o
MESMO banco falso.

⚠️ O fake não tem privilégio nenhum (tests/fake_postgrest.py): que o
`sas_mcp` só consiga o que a 0071/0072 dão se prova contra o PostgREST de
verdade, com `scripts/verificar_papeis_do_mcp.py`.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_mcp_tokens.py -q
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from postgrest.exceptions import APIError

from app.config import Settings
from app.mcp import tokens
from app.mcp.configuracao import (
    ConfiguracaoMcp,
    segredos_da_api_no_ambiente,
    validar_configuracao_do_mcp,
)
from tests.fake_postgrest import FakeCliente, Resp, Tabela

# ─── O banco falso com RPC ───────────────────────────────────────────────


def conferir_como_a_0072(db: dict, p_hash: str) -> list[dict]:
    """O corpo de `mcp_conferir_token` (0072) em Python, regra por regra."""
    agora = datetime.now(UTC)
    for linha in db.get("token_mcp", {}).values():
        if linha.get("hash_acesso") != p_hash or linha.get("revogado_em") is not None:
            continue
        expira = linha.get("expira_em")
        if expira is not None and datetime.fromisoformat(str(expira)) <= agora:
            continue
        conta = db.get("usuario_coordenacao", {}).get(linha.get("usuario_coordenacao_id"))
        if not conta or not conta.get("ativo"):
            continue
        ultimo = linha.get("ultimo_uso_em")
        if ultimo is None or datetime.fromisoformat(str(ultimo)) < agora - timedelta(minutes=1):
            linha["ultimo_uso_em"] = agora.isoformat()
        return [
            {
                "token_id": linha["id"],
                "coordenador_id": linha["usuario_coordenacao_id"],
                "nome": conta.get("nome"),
                "papel": conta.get("papel"),
            }
        ]
    return []


class _Rpc:
    def __init__(self, fazer):
        self._fazer = fazer

    def execute(self) -> Resp:
        return Resp(self._fazer())


#: As duas ações que o sas_mcp grava: a chamada de tool (app/mcp/auditoria_mcp)
#: e a prova do verificador (scripts/verificar_papeis_do_mcp), esta sem ator.
ACOES_DO_SAS_MCP = ("mcp_ferramenta_chamada", "mcp_verificacao_papeis")


def gatilho_da_0072_aceita(evento: dict) -> bool:
    """O gatilho `evento_auditoria_so_do_mcp` (0072) em Python: o que o sas_mcp
    consegue inserir na trilha. tests/test_migrations_do_mcp confere que o SQL
    diz o mesmo, regra por regra; a `FabricaDeClientes` o aplica a todo INSERT
    do MCP, como o Postgres aplica ao sas_mcp."""

    def tamanho(chave: str) -> int:
        return len(str(evento.get(chave) or ""))

    acao = evento.get("acao")
    detalhe = evento.get("detalhe")
    return (
        evento.get("canal") == "mcp"
        and (acao == ACOES_DO_SAS_MCP[0] or (acao == ACOES_DO_SAS_MCP[1] and evento.get("ator_id") is None))
        and evento.get("ator_tipo") == "coordenador"
        and tamanho("ator_id") <= 64
        and tamanho("recurso") <= 200
        and tamanho("ip") <= 64
        and tamanho("request_id") <= 128
        and (detalhe is None or len(json.dumps(detalhe, ensure_ascii=False).encode()) <= 4096)
    )


class _RecusaDoGatilho:
    """O `execute` do INSERT que o gatilho da 0072 recusa: o 42501 do PostgREST."""

    def execute(self):
        raise APIError({
            "code": "42501",
            "message": "o sas_mcp só grava na trilha evento do próprio MCP (0072)",
            "hint": None,
            "details": None,
        })


class _TabelaEspia(Tabela):
    """Grava os kwargs de cada insert — é por eles que se vê o `returning`."""

    def __init__(self, db, nome, inserts: list, *, com_gatilho: bool = False):
        super().__init__(db, nome)
        self._inserts = inserts
        self._com_gatilho = com_gatilho

    def insert(self, json, **kw):
        self._inserts.append({"tabela": self.nome, "linha": json, "kw": kw})
        if self._com_gatilho and self.nome == "evento_auditoria" and not gatilho_da_0072_aceita(json):
            return _RecusaDoGatilho()
        return super().insert(json, **kw)


class FakeClienteDoMcp(FakeCliente):
    """O FakeCliente com `rpc` — o de tests/fake_postgrest.py não tem.

    `com_gatilho=True` é o cliente do sas_mcp: o INSERT na trilha passa pelo
    gatilho da 0072 (`gatilho_da_0072_aceita`). Sem ele, o cliente da API, que
    o gatilho não confina."""

    def __init__(self, db: dict, *, rpcs: list | None = None, inserts: list | None = None,
                 falha_na_rpc: Exception | None = None, com_gatilho: bool = False):
        super().__init__(db)
        self.rpcs = rpcs if rpcs is not None else []
        self.inserts = inserts if inserts is not None else []
        self.falha_na_rpc = falha_na_rpc
        self.com_gatilho = com_gatilho

    def table(self, nome):
        return _TabelaEspia(self.db, nome, self.inserts, com_gatilho=self.com_gatilho)

    def rpc(self, funcao: str, params: dict, **_kw):
        self.rpcs.append((funcao, dict(params)))
        if self.falha_na_rpc is not None:
            raise self.falha_na_rpc
        if funcao != "mcp_conferir_token":
            raise AssertionError(f"RPC inesperada: {funcao}")
        return _Rpc(lambda: conferir_como_a_0072(self.db, params["p_hash"]))


class FabricaDeClientes:
    """O `criar_cliente` dos testes: um cliente NOVO a cada chamada, como o
    `criar_cliente_supabase`, todos sobre o mesmo banco e as mesmas listas.

    É o cliente do MCP, e por isso COM o gatilho da 0072: um evento que o
    Postgres recusaria ao sas_mcp também falha aqui — e some da trilha como
    sumiria lá, que é o que um teste tem de ver (revisão final de 26/10)."""

    def __init__(self, db: dict, *, falha_na_rpc: Exception | None = None):
        self.db = db
        self.rpcs: list = []
        self.inserts: list = []
        self.criados = 0
        self.falha_na_rpc = falha_na_rpc

    def __call__(self) -> FakeClienteDoMcp:
        self.criados += 1
        return FakeClienteDoMcp(self.db, rpcs=self.rpcs, inserts=self.inserts, falha_na_rpc=self.falha_na_rpc,
                                com_gatilho=True)


def banco_com_token(*, ativo: bool = True, papel: str = "administrador", **linha_extra) -> tuple[dict, str]:
    """Um banco com uma conta e um token válido dela. Devolve (db, token em claro).

    A conta é de ADMINISTRADOR por padrão porque ele consulta pelo MCP com
    MCP_EMISSAO_SO_ADMINISTRADOR ligada ou não (`servidor._pode_consultar`) —
    desde 26/10 a regra é opção, desligada por padrão. O coordenador tem os
    testes dele, com o papel explícito."""
    token, hash_acesso, prefixo = tokens.gerar()
    db = {
        "usuario_coordenacao": {
            "c0ffee00-0000-4000-8000-000000000001": {
                "id": "c0ffee00-0000-4000-8000-000000000001", "nome": "Leo Coordenação",
                "email": "leo@ari.com.br", "papel": papel, "ativo": ativo,
            },
        },
        "token_mcp": {
            "70ce0000-0000-4000-8000-000000000001": {
                "id": "70ce0000-0000-4000-8000-000000000001",
                "usuario_coordenacao_id": "c0ffee00-0000-4000-8000-000000000001",
                "nome": "Claude Code do Leo", "origem": "pessoal",
                "hash_acesso": hash_acesso, "prefixo": prefixo,
                "criado_em": datetime.now(UTC).isoformat(),
                "expira_em": None, "ultimo_uso_em": None, "revogado_em": None,
                **linha_extra,
            },
        },
        "evento_auditoria": {},
    }
    return db, token


# ─── gerar / hash / formato ──────────────────────────────────────────────


def test_gerar_devolve_token_no_formato_hash_e_prefixo():
    token, hash_acesso, prefixo = tokens.gerar()
    assert token.startswith("sas_mcp_")
    assert len(token) == len("sas_mcp_") + 43   # token_urlsafe(32)
    assert tokens.formato_valido(token)
    # O que a 0072 guarda: sha256 hex minúsculo — e o CHECK de lá recusa o
    # token em claro por não ser hex de 64.
    assert hash_acesso == hashlib.sha256(token.encode()).hexdigest()
    assert len(hash_acesso) == 64 and hash_acesso == hash_acesso.lower()
    assert token not in hash_acesso
    # O prefixo cabe no CHECK (1 a 20) e mostra só 4 caracteres do segredo.
    assert prefixo == token[:12] and 1 <= len(prefixo) <= 20


def test_dois_tokens_nunca_saem_iguais():
    assert len({tokens.gerar()[0] for _ in range(50)}) == 50


@pytest.mark.parametrize(
    "candidato",
    [
        None, "", "sas_mcp_", "sas_mcp_curto",
        "sas_mcp_" + "a" * 42, "sas_mcp_" + "a" * 44,
        "SAS_MCP_" + "a" * 43, " sas_mcp_" + "a" * 43,
        "sas_mcp_" + "a" * 42 + "=",          # padding de base64 não existe no urlsafe sem pad
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.assinatura",   # um JWT
    ],
)
def test_formato_recusa_o_que_nao_e_token_do_mcp(candidato):
    assert not tokens.formato_valido(candidato)


# ─── conferir ────────────────────────────────────────────────────────────


def test_conferir_devolve_a_identidade_do_dono():
    db, token = banco_com_token(papel="administrador")
    cliente = FakeClienteDoMcp(db)
    identidade = tokens.conferir(cliente, token)
    assert identidade == tokens.Identidade(
        token_id="70ce0000-0000-4000-8000-000000000001",
        coordenador_id="c0ffee00-0000-4000-8000-000000000001",
        nome="Leo Coordenação",
        papel="administrador",
    )
    # Pergunta ao banco pelo HASH, nunca pelo token em claro.
    assert cliente.rpcs == [("mcp_conferir_token", {"p_hash": tokens.hash_do_token(token)})]
    assert token not in str(cliente.rpcs)


def test_token_fora_do_formato_nem_vai_ao_banco():
    db, _ = banco_com_token()
    cliente = FakeClienteDoMcp(db)
    for lixo in ("Bearer x", "eyJhbGciOi.x.y", "sas_mcp_curto", ""):
        assert tokens.conferir(cliente, lixo) is None
    assert cliente.rpcs == []


@pytest.mark.parametrize(
    "estado",
    [
        {"revogado_em": "2026-10-01T00:00:00+00:00"},
        {"expira_em": "2026-01-01T00:00:00+00:00"},
    ],
)
def test_revogado_e_vencido_nao_conferem(estado):
    db, token = banco_com_token(**estado)
    assert tokens.conferir(FakeClienteDoMcp(db), token) is None


def test_conta_desativada_derruba_o_token_na_hora():
    db, token = banco_com_token(ativo=False)
    assert tokens.conferir(FakeClienteDoMcp(db), token) is None


def test_token_que_nao_existe_nao_confere():
    db, _ = banco_com_token()
    outro, _, _ = tokens.gerar()
    assert tokens.conferir(FakeClienteDoMcp(db), outro) is None


def test_papel_desconhecido_vale_coordenador():
    """Fail-closed, como `auth.papel_da_sessao`: valor torto não vira admin."""
    db, token = banco_com_token(papel="superadmin")
    assert tokens.conferir(FakeClienteDoMcp(db), token).papel == "coordenador"


def test_erro_de_banco_sobe_em_vez_de_virar_token_invalido():
    """Quem decide se é 401 ou 503 é quem chama (app.py devolve 503)."""
    db, token = banco_com_token()
    with pytest.raises(RuntimeError):
        tokens.conferir(FakeClienteDoMcp(db, falha_na_rpc=RuntimeError("caiu")), token)


def test_ultimo_uso_e_gravado_pela_rpc():
    db, token = banco_com_token()
    tokens.conferir(FakeClienteDoMcp(db), token)
    assert db["token_mcp"]["70ce0000-0000-4000-8000-000000000001"]["ultimo_uso_em"] is not None


# ─── O guard de boot ─────────────────────────────────────────────────────


def _settings(**kw) -> Settings:
    base = {"app_env": "production", "postgrest_url": "http://postgrest_mcp:3000"}
    return Settings(_env_file=None, **{**base, **kw})


def _config(**kw) -> ConfiguracaoMcp:
    base = {"habilitado": True, "url_publica": "https://portalsas.online/mcp"}
    return ConfiguracaoMcp(_env_file=None, **{**base, **kw})


def test_guard_aceita_a_configuracao_de_producao():
    validar_configuracao_do_mcp(_config(), _settings())


def test_guard_pula_em_dev():
    validar_configuracao_do_mcp(ConfiguracaoMcp(_env_file=None), _settings(app_env="dev", postgrest_url=""))


@pytest.mark.parametrize(
    ("config", "settings", "trecho"),
    [
        ({"habilitado": False}, {}, "MCP_HABILITADO"),
        ({}, {"postgrest_url": ""}, "POSTGREST_URL vazia"),
        ({}, {"postgrest_url": "http://postgrest:3000"}, "sas_service"),
        ({}, {"postgrest_token": "eyJ.x.y"}, "POSTGREST_TOKEN"),
        ({}, {"jwt_secret_key": "x" * 40}, "JWT_SECRET_KEY"),
        ({}, {"openai_api_key": "sk-x", "canvas_api_token": "t"}, "OPENAI_API_KEY, CANVAS_API_TOKEN"),
        ({"url_publica": ""}, {}, "MCP_URL_PUBLICA vazia"),
        ({"url_publica": "http://portalsas.online/mcp"}, {}, "https"),
        ({"url_publica": "https://localhost/mcp"}, {}, "localhost"),
    ],
)
def test_guard_recusa_subir_inseguro(config, settings, trecho):
    with pytest.raises(RuntimeError) as erro:
        validar_configuracao_do_mcp(_config(**config), _settings(**settings))
    assert trecho in str(erro.value)


def test_stdio_fora_de_dev_e_recusado():
    """No stdio o processo roda na máquina de quem chama: o pseudônimo e o teto
    seriam lidos do ambiente dele, e o acesso ao dado é o anônimo do
    postgrest_mcp. Fora de dev/test a IA conecta pelo HTTP (`mcp-remote`)."""
    with pytest.raises(RuntimeError) as erro:
        validar_configuracao_do_mcp(_config(url_publica=""), _settings(), "stdio")
    assert "--stdio só em dev/test" in str(erro.value)
    # Em dev continua de pé: é a porta de desenvolvimento.
    validar_configuracao_do_mcp(_config(url_publica=""), _settings(app_env="dev"), "stdio")


def test_guard_recusa_o_postgrest_da_api_com_ponto_final():
    """`postgrest.` é o mesmo host que `postgrest` (FQDN com o ponto da raiz)."""
    with pytest.raises(RuntimeError, match="sas_service"):
        validar_configuracao_do_mcp(_config(), _settings(postgrest_url="http://postgrest.:3000"))


# ─── A sonda de privilégio do boot (dados.exigir_papel_restrito) ─────────


class _ClienteDaSonda:
    """Responde à sonda como um PostgREST: devolve linhas, ou levanta o erro dado."""

    def __init__(self, erro: Exception | None = None):
        self.erro = erro
        self.consultas: list[str] = []

    def table(self, nome):
        self.consultas.append(nome)
        return self

    def select(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        if self.erro is not None:
            raise self.erro
        return Resp([{"id": "c0ffee00-0000-4000-8000-000000000001"}])


def _negado():
    from postgrest.exceptions import APIError

    return APIError({"code": "42501", "message": "permission denied for table usuario_coordenacao"})


def test_sonda_aceita_o_papel_que_nao_le_usuario_coordenacao():
    from app.mcp.dados import TABELA_DA_SONDA, problema_de_privilegio

    cliente = _ClienteDaSonda(_negado())
    assert problema_de_privilegio(lambda: cliente) is None
    assert cliente.consultas == [TABELA_DA_SONDA] == ["usuario_coordenacao"]


@pytest.mark.parametrize(
    "url",
    ["http://postgrest.:3000", "http://sas-postgrest-1:3000", "http://172.18.0.3:3000"],
)
def test_o_postgrest_da_api_por_outro_nome_passa_pelo_guard_mas_nao_pela_sonda(url):
    """O caso da revisão de 24/10: o guard só olha o NOME do host. A sonda
    pergunta ao PostgREST — e o da API (sas_service) LÊ usuario_coordenacao."""
    from app.mcp import dados

    if url != "http://postgrest.:3000":     # este o guard já pega (teste acima)
        validar_configuracao_do_mcp(_config(), _settings(postgrest_url=url))   # o guard não vê
    dormidas: list[float] = []
    with pytest.raises(RuntimeError) as erro:
        dados.exigir_papel_restrito("production", lambda: _ClienteDaSonda(), dormir=dormidas.append)
    assert "LÊ usuario_coordenacao" in str(erro.value)
    assert dormidas == []      # resposta definitiva: não fica tentando


def test_sonda_tenta_de_novo_enquanto_o_postgrest_sobe():
    import httpx

    from app.mcp import dados

    respostas = [_ClienteDaSonda(httpx.ConnectError("conexão recusada")), _ClienteDaSonda(_negado())]
    dormidas: list[float] = []
    dados.exigir_papel_restrito("production", lambda: respostas.pop(0), espera_s=0.5, dormir=dormidas.append)
    assert dormidas == [0.5] and respostas == []


def test_sonda_sem_resposta_recusa_subir_sem_vazar_a_url():
    import httpx

    from app.mcp import dados

    def cair():
        return _ClienteDaSonda(httpx.ConnectError("http://postgrest_mcp:3000 recusou"))

    with pytest.raises(RuntimeError) as erro:
        dados.exigir_papel_restrito("production", cair, tentativas=3, dormir=lambda _s: None)
    assert "não consegui fazer a sonda" in str(erro.value)
    assert "postgrest_mcp:3000" not in str(erro.value)


@pytest.mark.parametrize("codigo", ["PGRST001", "PGRST003"])
def test_postgrest_sem_banco_e_transitorio(codigo):
    from postgrest.exceptions import APIError

    from app.mcp.dados import SondaIndisponivel, problema_de_privilegio

    with pytest.raises(SondaIndisponivel):
        problema_de_privilegio(lambda: _ClienteDaSonda(APIError({"code": codigo, "message": "x"})))


def test_resposta_que_nao_e_do_postgrest_recusa():
    from postgrest.exceptions import APIError

    from app.mcp.dados import problema_de_privilegio

    # O erro genérico do postgrest-py para resposta que nem é JSON: code int.
    problema = problema_de_privilegio(lambda: _ClienteDaSonda(APIError({"code": 404, "message": "x"})))
    assert problema is not None and "404" in problema


def test_sonda_em_dev_so_avisa(caplog):
    from app.mcp import dados

    dados.exigir_papel_restrito("dev", lambda: _ClienteDaSonda(), dormir=lambda _s: pytest.fail("dormiu em dev"))
    assert any("sonda de privilégio" in r.getMessage() for r in caplog.records)


def test_segredos_da_api_sao_citados_pelo_nome_nunca_pelo_valor():
    vazados = segredos_da_api_no_ambiente(_settings(jwt_secret_key="segredo-de-verdade-1234567890-xyz"))
    assert vazados == ["JWT_SECRET_KEY"]
    with pytest.raises(RuntimeError) as erro:
        validar_configuracao_do_mcp(_config(), _settings(jwt_secret_key="segredo-de-verdade-1234567890-xyz"))
    assert "segredo-de-verdade" not in str(erro.value)


def test_hosts_saem_da_url_e_ganham_localhost_so_em_dev():
    config = _config()
    assert config.lista_de_hosts("production") == ["portalsas.online"]
    assert "localhost:*" in config.lista_de_hosts("dev")
    assert _config(hosts_permitidos="a.com, b.com:*").lista_de_hosts("dev") == ["a.com", "b.com:*"]
    # Sem URL e fora de dev: lista vazia — o transporte recusa tudo com 421.
    assert _config(url_publica="").lista_de_hosts("production") == []


def test_limites_tem_de_ser_positivos():
    with pytest.raises(ValueError):
        ConfiguracaoMcp(_env_file=None, limite_por_minuto=0)
    with pytest.raises(ValueError):
        ConfiguracaoMcp(_env_file=None, teto_de_linhas=0)


# ─── O valor efetivo no log, ao subir (configuracao.registrar_no_log) ─────
#
# A API e o MCP leem MCP_EMISSAO_SO_ADMINISTRADOR e MCP_MOSTRAR_NOME_DO_ALUNO
# cada um do seu ambiente, e a divergência não dá erro: a tela aprova o que o
# MCP recusa, ou diz "só o administrador" com o MCP servindo coordenador. A
# linha de cada processo é como se compara.


class _Linhas:
    """As linhas do logger da configuração. Handler no PRÓPRIO logger, e não o
    `caplog`: o `configurar_logging` do boot limpa os handlers da raiz."""

    def __init__(self) -> None:
        import logging

        self.logger = logging.getLogger("sas.mcp.configuracao")
        self.linhas: list[tuple[str, str]] = []
        linhas = self.linhas

        class _Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                linhas.append((record.levelname, record.getMessage()))

        self.handler = _Handler(logging.DEBUG)
        self.nivel = self.logger.level

    def __enter__(self) -> list[tuple[str, str]]:
        self.logger.addHandler(self.handler)
        self.logger.setLevel("INFO")
        return self.linhas

    def __exit__(self, *_exc: object) -> None:
        self.logger.removeHandler(self.handler)
        self.logger.setLevel(self.nivel)


@pytest.fixture
def config_do_ambiente(monkeypatch):
    """MCP_* lido do ambiente de verdade, com o `lru_cache` limpo antes e
    depois: a config de um teste não pode vazar para o outro."""
    from app.config import get_settings
    from app.mcp.configuracao import get_configuracao_mcp

    get_settings.cache_clear()
    get_configuracao_mcp.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    yield monkeypatch
    get_configuracao_mcp.cache_clear()
    get_settings.cache_clear()


def test_registrar_no_log_escreve_os_dois_valores_efetivos_e_nada_mais():
    from app.mcp.configuracao import registrar_no_log

    config = _config(emissao_so_administrador=True, mostrar_nome_do_aluno=False, emissor_oauth="https://x.example/api")
    with _Linhas() as linhas:
        registrar_no_log(config, "mcp")
    assert linhas == [
        ("INFO", "mcp: MCP_EMISSAO_SO_ADMINISTRADOR=true (valor efetivo)"),
        ("INFO", "mcp: MCP_MOSTRAR_NOME_DO_ALUNO=false (valor efetivo)"),
    ]
    assert "x.example" not in json.dumps(linhas)


def test_a_api_escreve_no_log_ao_subir_o_que_leu_do_proprio_ambiente(config_do_ambiente):
    config_do_ambiente.setenv("MCP_EMISSAO_SO_ADMINISTRADOR", "true")
    config_do_ambiente.setenv("MCP_MOSTRAR_NOME_DO_ALUNO", "false")
    from app.main import create_app

    with _Linhas() as linhas:
        create_app()
    assert ("INFO", "api: MCP_EMISSAO_SO_ADMINISTRADOR=true (valor efetivo)") in linhas
    assert ("INFO", "api: MCP_MOSTRAR_NOME_DO_ALUNO=false (valor efetivo)") in linhas


def test_a_api_com_os_padroes_escreve_os_padroes(config_do_ambiente):
    from app.main import create_app

    # Sem o ambiente nem o `.env` de quem roda: o teste é sobre o padrão do código.
    config_do_ambiente.setattr("app.main.get_configuracao_mcp", lambda: ConfiguracaoMcp(_env_file=None))
    config_do_ambiente.delenv("MCP_EMISSAO_SO_ADMINISTRADOR", raising=False)
    config_do_ambiente.delenv("MCP_MOSTRAR_NOME_DO_ALUNO", raising=False)
    with _Linhas() as linhas:
        create_app()
    assert ("INFO", "api: MCP_EMISSAO_SO_ADMINISTRADOR=false (valor efetivo)") in linhas
    assert ("INFO", "api: MCP_MOSTRAR_NOME_DO_ALUNO=true (valor efetivo)") in linhas


def test_mcp_torto_no_ambiente_da_api_nao_derruba_a_api(config_do_ambiente):
    config_do_ambiente.setenv("MCP_LIMITE_POR_MINUTO", "zero")
    from app.main import create_app

    with _Linhas() as linhas:
        assert create_app() is not None
    assert [nivel for nivel, texto in linhas if "inválida no ambiente da API" in texto] == ["ERROR"]


def test_o_mcp_escreve_no_log_ao_subir_o_que_leu_do_proprio_ambiente(config_do_ambiente):
    from app.mcp import __main__ as entrada

    config = _config(emissao_so_administrador=True, mostrar_nome_do_aluno=False)
    config_do_ambiente.setattr(entrada, "get_configuracao_mcp", lambda: config)
    config_do_ambiente.setattr(entrada, "exigir_papel_restrito", lambda _app_env: None)
    config_do_ambiente.setattr(entrada, "_rodar_http", lambda *_args: 0)
    with _Linhas() as linhas:
        assert entrada.main([]) == 0
    assert ("INFO", "mcp: MCP_EMISSAO_SO_ADMINISTRADOR=true (valor efetivo)") in linhas
    assert ("INFO", "mcp: MCP_MOSTRAR_NOME_DO_ALUNO=false (valor efetivo)") in linhas
