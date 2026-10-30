"""O servidor MCP da coordenação, de ponta a ponta, sem rede e sem banco.

Duas portas, as duas do próprio SDK:

  * o cliente EM MEMÓRIA (`create_connected_server_and_client_session`), para
    o que acontece dentro de uma chamada: catálogo, recusa de tool não
    listada, erro sem texto cru, pseudônimo, auditoria, limite por minuto,
    roteiros;
  * o TestClient do Starlette com Bearer, para o que acontece ANTES dela:
    401 sem token e com JWT de sessão da API, 405 no GET, 421 no Host de
    fora, 503 com o banco fora, e a identidade que chega à auditoria.

O registro é de MENTIRA (tools montadas aqui): o que se testa é o servidor,
qualquer que seja a política de exposição. O banco é o FakeCliente com a RPC
da 0072 emulada (`tests/test_mcp_tokens.py`).

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_mcp_servidor.py -q
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session
from postgrest.types import ReturnMethod
from starlette.testclient import TestClient

from app.chat import superficie
from app.chat.ferramentas import Ferramenta, Registro
from app.mcp import auditoria_mcp
from app.mcp.app import (
    AutenticacaoDoMcp,
    FalhasDeTokenPorIp,
    RequisicoesPorToken,
    TentativasDemais,
    VerificadorDeToken,
    montar_app,
)
from app.mcp.auditoria_mcp import ACAO_CHAMADA, CANAL, contar_linhas
from app.mcp.configuracao import ConfiguracaoMcp
from app.mcp.servidor import (
    MENSAGEM_LGPD,
    MENSAGEM_SEM_IDENTIDADE,
    MENSAGEM_SO_ADMINISTRADOR,
    IdentidadePeloToken,
    LimitePorMinuto,
    identidade_do_pedido,
    instrucoes,
    montar_servidor,
    roteiros_do_sas,
)
from app.mcp.tokens import Identidade, gerar
from tests.test_mcp_tokens import FabricaDeClientes, banco_com_token

TOKEN_ID = "70ce0000-0000-4000-8000-000000000001"
COORDENADOR = "c0ffee00-0000-4000-8000-000000000001"
# Administrador: consulta com MCP_EMISSAO_SO_ADMINISTRADOR ligada ou não (desde
# 26/10 o padrão é desligada — administrador e coordenador conectam).
IDENTIDADE = Identidade(token_id=TOKEN_ID, coordenador_id=COORDENADOR, nome="Leo Coordenação", papel="administrador")
COORDENADORA = Identidade(token_id=TOKEN_ID, coordenador_id=COORDENADOR, nome="Coordenadora", papel="coordenador")

A, B = "a1111111-0000-4000-8000-000000000001", "a1111111-0000-4000-8000-000000000002"
NOME_A, NOME_B = "ANA SINTETICA SOUZA", "BRUNO SINTETICO LIMA"
SEGREDO_DA_API = "segredo-de-teste-com-mais-de-32-caracteres"


# ─── O registro de mentira ───────────────────────────────────────────────


def _ciclos(cliente):
    return {"total": 1, "ciclos": [{"id": "c1", "nome": "Ciclo 1 · ITA · 2026"}]}


def _alunos(cliente, *, limite: int = 30):
    linhas = [{"alunoId": a, "nome": n, "zona": "risco"} for a, n in ((A, NOME_A), (B, NOME_B))]
    return {"total": len(linhas), "limiteRecebido": limite, "alunos": linhas[:limite]}


def _relatorio_sem_identidade(cliente):
    # O formato de `relatorio_ciclo`: nome de aluno sem alunoId nem matrícula.
    return {"alunosRisco": [{"nome": NOME_A, "zona": "risco", "mediaRecente": 3.0}]}


def _explode(cliente):
    raise RuntimeError("APIError em http://postgrest_mcp:3000/aluno?select=senha_hash")


def _lenta(cliente):
    import time

    time.sleep(0.5)
    return {"ok": True}


def _ferramenta(nome, handler, *, expor=True, escopo="coordenacao", parametros=None, prazo_s=90.0):
    return Ferramenta(
        nome=nome, descricao=f"descrição de {nome}", escopo=escopo, handler=handler,
        parametros=parametros or {"type": "object", "properties": {}},
        expor_no_mcp=expor, prazo_s=prazo_s,
    )


def registro_de_mentira() -> Registro:
    return Registro([
        _ferramenta("listar_ciclos", _ciclos),
        _ferramenta("listar_alunos", _alunos,
                    parametros={"type": "object", "properties": {"limite": {"type": "integer", "default": 30}}}),
        _ferramenta("relatorio_ciclo", _relatorio_sem_identidade),
        _ferramenta("explode", _explode),
        _ferramenta("lenta", _lenta, prazo_s=0.05),
        _ferramenta("gerar_grafico", _ciclos, expor=False),
        _ferramenta("minhas_notas", _ciclos, expor=False, escopo="aluno"),
    ])


def _banco() -> dict:
    db, _ = banco_com_token()
    db["aluno"] = {
        A: {"id": A, "matricula": "2026001", "nome": NOME_A, "email": "ana@exemplo.invalid"},
        B: {"id": B, "matricula": "2026002", "nome": NOME_B, "email": "bruno@exemplo.invalid"},
    }
    return db


def _config(**kw) -> ConfiguracaoMcp:
    return ConfiguracaoMcp(_env_file=None, **{"hosts_permitidos": "testserver", **kw})


def _com_pseudonimo(**kw) -> ConfiguracaoMcp:
    """O pseudônimo ligado: OPÇÃO desde 26/10, quando o nome real virou o
    padrão (decisão do dono). Os testes dele o ligam explicitamente."""
    return _config(mostrar_nome_do_aluno=False, **kw)


def _so_administrador(**kw) -> ConfiguracaoMcp:
    """O "só o administrador conecta": também OPÇÃO desde 26/10."""
    return _config(emissao_so_administrador=True, **kw)


class _RoteirosDeMentira:
    class R:
        def __init__(self, nome, escopo="coordenacao"):
            self.nome, self.titulo, self.descricao, self.escopo = nome, f"Título {nome}", f"Quando usar {nome}", escopo
            self.texto = f"# {nome}\n\nO método."

    def listar(self, escopo):
        return [self.R("diagnostico_de_ciclo"), self.R("preparo_de_reuniao")] if escopo == "coordenacao" else []

    def obter(self, escopo, nome):
        return next((r for r in self.listar(escopo) if r.nome == nome), None)


async def _fixa(_pedido):
    return IDENTIDADE


def _servidor(fabrica: FabricaDeClientes, **kw) -> Server:
    kw.setdefault("config", _config())
    kw.setdefault("identificar", _fixa)
    kw.setdefault("roteiros", _RoteirosDeMentira())
    kw.setdefault("criar_cliente", fabrica)
    kw.setdefault("registro", registro_de_mentira())
    return montar_servidor(**kw)


def _servidor_com(fabrica: FabricaDeClientes, *ferramentas: Ferramenta, **kw) -> Server:
    """O servidor com um registro feito só destas ferramentas."""
    return _servidor(fabrica, registro=Registro(list(ferramentas)), **kw)


def _em_memoria(servidor: Server, corpo):
    async def rodar():
        async with create_connected_server_and_client_session(servidor) as sessao:
            return await corpo(sessao)

    return asyncio.run(rodar())


def _texto(resultado) -> str:
    return resultado.content[0].text


def _eventos(db: dict) -> list[dict]:
    return [e for e in db["evento_auditoria"].values() if e.get("acao") == ACAO_CHAMADA]


# ─── Catálogo e chamada (cliente em memória) ─────────────────────────────


def test_tools_list_mostra_so_o_que_a_politica_expos():
    fabrica = FabricaDeClientes(_banco())

    async def corpo(s):
        return {t.name for t in (await s.list_tools()).tools}

    assert _em_memoria(_servidor(fabrica), corpo) == {"listar_ciclos", "listar_alunos", "relatorio_ciclo", "explode", "lenta"}


@pytest.mark.parametrize("nome", ["gerar_grafico", "minhas_notas", "inventada", "x" * 500])
def test_tool_nao_listada_e_recusada_pelo_nome(nome):
    """O SDK deixa a tool não listada chegar ao handler; o catálogo recusa,
    com a resposta de nome inventado — sem confirmar que ela existe fora."""
    db = _banco()
    fabrica = FabricaDeClientes(db)

    async def corpo(s):
        return await s.call_tool(nome, {})

    r = _em_memoria(_servidor(fabrica), corpo)
    assert r.isError and "não existe" in _texto(r)
    assert len(_texto(r)) < 300
    (evento,) = _eventos(db)
    # O nome pedido é texto do cliente: não entra na trilha.
    assert evento["detalhe"] == {"ferramenta": None, "desfecho": "inexistente", "duracaoMs": evento["detalhe"]["duracaoMs"], "linhas": 0}


def test_chamada_passa_pelo_registro_com_cliente_novo():
    db = _banco()
    fabrica = FabricaDeClientes(db)

    async def corpo(s):
        return await s.call_tool("listar_ciclos", {"argumento_inventado": 1})

    r = _em_memoria(_servidor(fabrica, config=_com_pseudonimo()), corpo)
    assert not r.isError
    assert json.loads(_texto(r))["ciclos"][0]["nome"] == "Ciclo 1 · ITA · 2026"
    # Despacho, cadastro de alunos (o do pseudônimo) e auditoria: cada um com o
    # seu cliente.
    assert fabrica.criados >= 3


def test_a_tool_sabe_que_a_chamada_veio_do_mcp():
    """`lembretes_agendados` lê o ambiente do processo, e o do MCP não é o da
    API (chat/superficie.py). A marca tem de chegar à THREAD da tool, e não só
    ao event loop — e sair dela depois, para não valer na chamada seguinte."""

    def marca(_cliente):
        return {"peloMcp": superficie.pelo_mcp()}

    fabrica = FabricaDeClientes(_banco())

    async def corpo(s):
        return await s.call_tool("marca", {})

    r = _em_memoria(_servidor_com(fabrica, _ferramenta("marca", marca)), corpo)
    assert json.loads(_texto(r)) == {"peloMcp": True}
    assert superficie.pelo_mcp() is False


def test_excecao_da_tool_vira_mensagem_generica():
    """O SDK mandaria `str(e)` — aqui com a URL do PostgREST e o nome de uma coluna."""
    db = _banco()

    async def corpo(s):
        return await s.call_tool("explode", {})

    r = _em_memoria(_servidor(FabricaDeClientes(db)), corpo)
    assert r.isError
    assert "postgrest" not in _texto(r).lower() and "senha_hash" not in _texto(r)
    assert "falhou do nosso lado" in _texto(r)


def test_excecao_fora_do_registro_tambem_nao_vaza(monkeypatch):
    """Até um erro no MEIO do servidor (o cadastro, a auditoria) vira a
    mensagem genérica: a última barreira do `call_tool`."""
    db = _banco()
    servidor = _servidor(FabricaDeClientes(db), config=_com_pseudonimo())

    def cadastro_quebrado(_criar):
        raise RuntimeError("connection refused http://postgrest_mcp:3000")

    async def corpo(s):
        return await s.call_tool("listar_alunos", {})

    from app.mcp import pseudonimo

    monkeypatch.setattr(pseudonimo.CadastroDeAlunos, "obter", lambda self, criar: cadastro_quebrado(criar))
    r = _em_memoria(servidor, corpo)
    assert r.isError and "postgrest" not in _texto(r).lower()
    assert _eventos(db)[0]["detalhe"]["desfecho"] == "falha"


def test_falha_ao_abrir_o_cliente_do_despacho_e_generica_e_auditada():
    db = _banco()
    fabrica = FabricaDeClientes(db)

    class _PrimeiraFalha:
        """Falha só a PRIMEIRA abertura — a do despacho; a da auditoria abre."""

        def __init__(self):
            self.vezes = 0

        def __call__(self):
            self.vezes += 1
            if self.vezes == 1:
                raise RuntimeError("Nenhum backend de dados configurado. Defina POSTGREST_URL")
            return fabrica()

    async def corpo(s):
        return await s.call_tool("listar_ciclos", {})

    r = _em_memoria(_servidor(fabrica, criar_cliente=_PrimeiraFalha()), corpo)
    assert r.isError and "POSTGREST" not in _texto(r) and "falhou do nosso lado" in _texto(r)
    assert [e["detalhe"]["desfecho"] for e in _eventos(db)] == ["falha"]


def test_prazo_da_tool_vale_no_mcp():
    db = _banco()

    async def corpo(s):
        return await s.call_tool("lenta", {})

    r = _em_memoria(_servidor(FabricaDeClientes(db)), corpo)
    assert r.isError and "foi abandonada" in _texto(r)


# ─── Pseudônimo ──────────────────────────────────────────────────────────


def test_com_o_pseudonimo_ligado_nome_de_aluno_nao_sai_vira_matricula():
    db = _banco()

    async def corpo(s):
        return await s.call_tool("listar_alunos", {})

    r = _em_memoria(_servidor(FabricaDeClientes(db), config=_com_pseudonimo()), corpo)
    texto = _texto(r)
    assert not r.isError
    assert NOME_A not in texto and NOME_B not in texto and "SINTETIC" not in texto
    nomes = [a["nome"] for a in json.loads(texto)["alunos"]]
    assert nomes == ["Aluno 2026001", "Aluno 2026002"]


def test_recusa_do_pseudonimo_e_a_chamada_inteira_como_erro():
    db = _banco()

    async def corpo(s):
        return await s.call_tool("relatorio_ciclo", {})

    r = _em_memoria(_servidor(FabricaDeClientes(db), config=_com_pseudonimo()), corpo)
    assert r.isError
    assert json.loads(_texto(r)) == {"erro": MENSAGEM_LGPD}       # nada parcial junto
    assert _eventos(db)[0]["detalhe"]["desfecho"] == "recusa_lgpd"
    assert _eventos(db)[0]["detalhe"]["linhas"] == 0


def test_por_padrao_o_nome_real_sai_e_o_portao_nao_se_aplica():
    """A decisão do dono de 26/10 (o item 1 do docs/43 §6): o padrão é o nome.
    O portão do pseudônimo não roda — nem o texto livre com nome, que ele
    recusaria inteiro, é recusado — e o cadastro de alunos nem é lido."""
    assert ConfiguracaoMcp(_env_file=None).mostrar_nome_do_aluno is True
    db = _banco()
    fabrica = FabricaDeClientes(db)

    async def corpo(s):
        return await s.call_tool("listar_alunos", {}), await s.call_tool("relatorio_ciclo", {})

    alunos, relatorio = _em_memoria(_servidor(fabrica), corpo)
    assert not alunos.isError and [a["nome"] for a in json.loads(_texto(alunos))["alunos"]] == [NOME_A, NOME_B]
    assert not relatorio.isError and NOME_A in _texto(relatorio)
    assert [e["detalhe"]["desfecho"] for e in _eventos(db)] == ["ok", "ok"]
    # Despacho e auditoria de cada chamada; nenhum cliente para o cadastro.
    assert fabrica.criados == 4


def test_tools_que_so_servem_com_o_nome_saem_do_catalogo_com_o_pseudonimo():
    """`buscar_aluno_por_nome` e `listar_alertas` (catalogo.SO_COM_NOME_DO_ALUNO):
    no catálogo com o nome real; fora — e não chamáveis pelo nome — com o
    pseudônimo, que não sabe trocar o nome digitado nem o do título."""
    registro = Registro([
        _ferramenta("listar_ciclos", _ciclos),
        _ferramenta("buscar_aluno_por_nome", lambda cliente: {"alunos": [{"id": A, "nome": NOME_A}]}),
        _ferramenta("listar_alertas", lambda cliente: {"alertas": [{"titulo": f"{NOME_A} caiu 2 pontos"}]}),
    ])

    async def corpo(s):
        nomes = {t.name for t in (await s.list_tools()).tools}
        return nomes, await s.call_tool("listar_alertas", {})

    com_nome, chamada = _em_memoria(_servidor(FabricaDeClientes(_banco()), registro=registro), corpo)
    assert com_nome == {"listar_ciclos", "buscar_aluno_por_nome", "listar_alertas"}
    assert not chamada.isError and NOME_A in _texto(chamada)

    db = _banco()
    sem_nome, chamada = _em_memoria(
        _servidor(FabricaDeClientes(db), registro=registro, config=_com_pseudonimo()), corpo
    )
    assert sem_nome == {"listar_ciclos"}
    assert chamada.isError and "não existe" in _texto(chamada) and "SINTETIC" not in _texto(chamada)
    assert _eventos(db)[0]["detalhe"]["desfecho"] == "inexistente"


class _Objeto:
    """Um objeto qualquer no resultado: o serializador o escreve pelo `str()`."""

    def __init__(self, nome):
        self.nome = nome

    def __str__(self):
        return f"_Objeto(nome={self.nome!r})"


@pytest.mark.parametrize(
    "retorno",
    [
        # `sorted(zip(...))` devolve tuplas — e o serializador as escreve como lista.
        lambda: {"ranking": sorted([(NOME_A, 7.5), (NOME_B, 6.0)], key=lambda par: -par[1])},
        lambda: {"turma": {NOME_A, NOME_B}},
        lambda: {"bruto": NOME_A.encode()},
        lambda: {"objeto": _Objeto(NOME_A)},
    ],
    ids=["lista_de_tuplas", "set", "bytes", "objeto"],
)
def test_nome_em_tupla_set_bytes_ou_objeto_nao_sai(retorno):
    """O caso da revisão de 24/10: o portão só descia em dict e list e só
    conferia str, e o serializador (`default=str`) escrevia o resto. O nome
    saía com isError=False."""
    db = _banco()

    async def corpo(s):
        return await s.call_tool("ranking", {})

    servidor = _servidor_com(
        FabricaDeClientes(db), _ferramenta("ranking", lambda cliente: retorno()), config=_com_pseudonimo()
    )
    r = _em_memoria(servidor, corpo)
    assert r.isError and json.loads(_texto(r)) == {"erro": MENSAGEM_LGPD}
    assert "SINTETIC" not in _texto(r)
    assert _eventos(db)[0]["detalhe"]["desfecho"] == "recusa_lgpd"


def test_aluno_dentro_de_tupla_sai_com_rotulo():
    """Dict de aluno dentro de tupla: a passada 1 nem o via, e ele saía cru."""
    db = _banco()
    alunos = tuple({"alunoId": a, "nome": n, "zona": "risco"} for a, n in ((A, NOME_A), (B, NOME_B)))

    async def corpo(s):
        return await s.call_tool("tupla", {})

    servidor = _servidor_com(
        FabricaDeClientes(db), _ferramenta("tupla", lambda cliente: {"alunos": alunos}), config=_com_pseudonimo()
    )
    r = _em_memoria(servidor, corpo)
    assert not r.isError
    assert [a["nome"] for a in json.loads(_texto(r))["alunos"]] == ["Aluno 2026001", "Aluno 2026002"]


def test_motivo_da_recusa_no_log_nao_traz_o_nome(caplog):
    """O motivo vai ao log em WARNING — e a chave do dict, quando é o nome do
    aluno, entrava no caminho (revisão de 24/10)."""
    db = _banco()

    def por_aluno(cliente):
        return {"porAluno": {NOME_A: {"nome": "x", "zona": "risco"}}, "porMatricula": {"2026001": {"t": NOME_B}}}

    async def corpo(s):
        return await s.call_tool("por_aluno", {})

    servidor = _servidor_com(FabricaDeClientes(db), _ferramenta("por_aluno", por_aluno), config=_com_pseudonimo())
    r = _em_memoria(servidor, corpo)
    assert r.isError
    mensagens = [registro.getMessage() for registro in caplog.records]
    assert any("$.porAluno.<chave>" in m for m in mensagens)
    assert not any("SINTETIC" in m or "2026001" in m for m in mensagens)


# ─── Teto de linhas ──────────────────────────────────────────────────────


def test_limite_pedido_acima_do_teto_e_cortado_antes_do_despacho():
    db = _banco()

    async def corpo(s):
        return await s.call_tool("listar_alunos", {"limite": 1000})

    r = _em_memoria(_servidor(FabricaDeClientes(db), config=_config(teto_de_linhas=1)), corpo)
    corpo_json = json.loads(_texto(r))
    assert corpo_json["limiteRecebido"] == 1 and len(corpo_json["alunos"]) == 1


# ─── Auditoria ───────────────────────────────────────────────────────────


def test_cada_chamada_vira_um_evento_com_returning_minimal():
    """Sem `return=minimal` o INSERT pediria RETURNING — e o sas_mcp não tem
    SELECT em evento_auditoria (0072): o evento sumiria calado."""
    db = _banco()
    fabrica = FabricaDeClientes(db)

    async def corpo(s):
        await s.call_tool("listar_alunos", {"limite": 5})
        await s.call_tool("listar_ciclos", {})

    _em_memoria(_servidor(fabrica), corpo)
    inserts = [i for i in fabrica.inserts if i["tabela"] == "evento_auditoria"]
    assert len(inserts) == 2
    assert all(i["kw"].get("returning") == ReturnMethod.minimal for i in inserts)

    primeiro = inserts[0]["linha"]
    assert primeiro["acao"] == ACAO_CHAMADA and primeiro["canal"] == CANAL == "mcp"
    assert primeiro["ator_tipo"] == "coordenador" and primeiro["ator_id"] == COORDENADOR
    assert primeiro["recurso"] == f"mcp_token/{TOKEN_ID}"
    assert set(primeiro["detalhe"]) == {"ferramenta", "desfecho", "duracaoMs", "linhas"}
    assert primeiro["detalhe"]["ferramenta"] == "listar_alunos"
    assert primeiro["detalhe"]["desfecho"] == "ok" and primeiro["detalhe"]["linhas"] == 2
    # Nem argumento nem resultado: o `5` pedido e os nomes não estão lá.
    texto = json.dumps(primeiro, ensure_ascii=False)
    assert NOME_A not in texto and "Aluno 2026001" not in texto and "limite" not in texto


def test_contar_linhas_conta_registros_nao_numeros():
    assert contar_linhas({"total": 2, "alunos": [{"a": 1}, {"a": 2}]}) == 2
    assert contar_linhas({"histograma": {"contagens": [1, 2, 3, 4]}}) == 1
    assert contar_linhas({"aluno": {"id": "x"}, "ciclos": [{"notas": [{"n": 1}, {"n": 2}]}]}) == 3


def test_o_que_vem_de_fora_cabe_no_gatilho_da_trilha():
    """O IP e o request id são texto de quem chama. Acima do teto do gatilho da
    0072, o INSERT voltava 42501 e a chamada saía sem linha na trilha."""
    assert auditoria_mcp.ip_da_trilha("a" * 200) == "a" * auditoria_mcp.TETO_DO_IP
    assert auditoria_mcp.ip_da_trilha("2001:db8::8a2e:370:7334") == "2001:db8::8a2e:370:7334"
    assert auditoria_mcp.ip_da_trilha("10.0.0.1\x00\n") == "10.0.0.1"
    assert auditoria_mcp.ip_da_trilha("") is None and auditoria_mcp.ip_da_trilha(None) is None
    assert auditoria_mcp.request_id_da_trilha("rid-legitimo_1") == "rid-legitimo_1"
    # Fora da forma, fica o da requisição — fora de uma, o "-".
    assert auditoria_mcp.request_id_da_trilha("r" * 200) == "-"
    assert auditoria_mcp.request_id_da_trilha(None) == "-"


class _TrilhaQueRecusa:
    """O banco que recusa o INSERT da trilha (42501 do gatilho, rede, disco)."""

    def table(self, nome):
        return self

    def insert(self, evento, **_kw):
        return self

    def execute(self):
        from postgrest.exceptions import APIError

        raise APIError({"code": "42501", "message": "o sas_mcp só grava na trilha evento do próprio MCP (0072)"})


def test_insert_da_trilha_que_falha_e_error_com_acao_necessaria(caplog):
    """Era um WARNING no stdout: a IA de fora lia e a tela de auditoria não
    mostrava, sem alarme nenhum (revisão final de 26/10). Melhor-esforço
    continua — a exceção não sobe —, mas alto."""
    with caplog.at_level("INFO", logger="sas.auditoria"):
        auditoria_mcp.registrar_chamada(
            _TrilhaQueRecusa(), identidade=IDENTIDADE, ferramenta="listar_ciclos", desfecho="ok",
            duracao_ms=1, linhas=1,
        )
    (erro,) = [r for r in caplog.records if r.levelname == "ERROR"]
    assert erro.getMessage().startswith("[AÇÃO NECESSÁRIA]") and erro.exc_info is not None
    assert erro.ferramenta == "listar_ciclos" and erro.usuario == COORDENADOR


# ─── Limite por minuto ───────────────────────────────────────────────────


class _Relogio:
    def __init__(self):
        self.agora = 100.0

    def __call__(self):
        return self.agora


def test_limite_por_minuto_por_token_audita_so_a_primeira_recusa():
    db = _banco()
    relogio = _Relogio()
    limite = LimitePorMinuto(2, relogio=relogio)

    async def corpo(s):
        respostas = [await s.call_tool("listar_ciclos", {}) for _ in range(4)]
        relogio.agora += 61
        respostas.append(await s.call_tool("listar_ciclos", {}))
        return respostas

    r = _em_memoria(_servidor(FabricaDeClientes(db), limite=limite), corpo)
    assert [x.isError for x in r] == [False, False, True, True, False]
    assert "Limite de 2 consultas por minuto" in _texto(r[2])
    desfechos = [e["detalhe"]["desfecho"] for e in _eventos(db)]
    # Duas ok, UMA recusa registrada (a de cada recusa encheria a trilha sem
    # teto), e a ok depois da janela.
    assert desfechos == ["ok", "ok", "limite", "ok"]


def test_limite_e_por_token_nao_global():
    limite = LimitePorMinuto(1, relogio=_Relogio())
    assert limite.admitir("token-a") == (True, False)
    assert limite.admitir("token-a") == (False, True)
    assert limite.admitir("token-a") == (False, False)
    assert limite.admitir("token-b") == (True, False)


# ─── Identidade ──────────────────────────────────────────────────────────


def test_sem_identidade_nada_roda():
    db = _banco()
    fabrica = FabricaDeClientes(db)

    async def ninguem(_pedido):
        return None

    async def corpo(s):
        return await s.call_tool("listar_ciclos", {})

    r = _em_memoria(_servidor(fabrica, identificar=ninguem), corpo)
    assert r.isError and _eventos(db) == []
    assert fabrica.criados == 0      # nem cliente chegou a abrir


def test_stdio_reconfere_o_token_a_cada_chamada():
    """Revogar no meio da sessão corta a próxima chamada, sem reiniciar nada."""
    db, token = banco_com_token()
    db["aluno"] = {}
    fabrica = FabricaDeClientes(db)
    servidor = _servidor(fabrica, identificar=IdentidadePeloToken(token, fabrica))

    async def corpo(s):
        antes = await s.call_tool("listar_ciclos", {})
        db["token_mcp"][TOKEN_ID]["revogado_em"] = datetime.now(UTC).isoformat()
        depois = await s.call_tool("listar_ciclos", {})
        return antes, depois

    antes, depois = _em_memoria(servidor, corpo)
    assert not antes.isError and depois.isError


# ─── Só o administrador consulta (MCP_EMISSAO_SO_ADMINISTRADOR) ──────────


async def _coordenadora(_pedido):
    return COORDENADORA


@pytest.mark.parametrize("nome", ["listar_alunos", "inventada"])
def test_coordenador_nao_consulta_enquanto_so_o_administrador_conecta(nome):
    """A regra valia só na emissão: o token de quem não é administrador
    consultava a escola inteira (revisão de 24/10). A resposta é a mesma para
    tool que existe e para nome inventado: quem não pode não descobre o que há."""
    db = _banco()
    fabrica = FabricaDeClientes(db)

    async def corpo(s):
        return await s.call_tool(nome, {})

    r = _em_memoria(_servidor(fabrica, identificar=_coordenadora, config=_so_administrador()), corpo)
    assert r.isError and json.loads(_texto(r)) == {"erro": MENSAGEM_SO_ADMINISTRADOR}
    (evento,) = _eventos(db)
    assert evento["detalhe"]["desfecho"] == "sem_permissao" and evento["detalhe"]["linhas"] == 0
    assert evento["detalhe"]["ferramenta"] == (None if nome == "inventada" else nome)
    assert fabrica.criados == 1      # só o da auditoria: nem despacho, nem cadastro


def test_por_padrao_o_coordenador_consulta():
    """A decisão do dono de 26/10: administrador E coordenador conectam."""
    assert ConfiguracaoMcp(_env_file=None).emissao_so_administrador is False

    async def corpo(s):
        return await s.call_tool("listar_alunos", {})

    servidor = _servidor(FabricaDeClientes(_banco()), identificar=_coordenadora)
    assert not _em_memoria(servidor, corpo).isError


async def _o_que_o_servidor_descreve(s) -> dict[str, str]:
    """tools/list, prompts/list e prompts/get: o texto do erro de cada um, ou "ok"."""
    saida = {}
    for metodo, chamada in (
        ("tools/list", s.list_tools),
        ("prompts/list", s.list_prompts),
        ("prompts/get", lambda: s.get_prompt("diagnostico_de_ciclo")),
        ("prompts/get inexistente", lambda: s.get_prompt("nao_existe")),
    ):
        try:
            await chamada()
            saida[metodo] = "ok"
        except McpError as erro:
            saida[metodo] = str(erro)
    return saida


def test_coordenador_nao_lista_ferramentas_nem_roteiros():
    """A regra só barrava o tools/call: o token de quem não é administrador
    abria o catálogo inteiro, com os schemas, e o texto dos roteiros da
    coordenação (revisão final de 26/10). A resposta é a mesma para roteiro
    que existe e para nome inventado."""
    db = _banco()
    servidor = _servidor(FabricaDeClientes(db), identificar=_coordenadora, config=_so_administrador())
    respostas = _em_memoria(servidor, _o_que_o_servidor_descreve)
    assert respostas == dict.fromkeys(respostas, MENSAGEM_SO_ADMINISTRADOR) and len(respostas) == 4
    assert _eventos(db) == []          # listar não é consulta: não vai à trilha


def test_administrador_e_regra_desligada_listam():
    fechada = _servidor(FabricaDeClientes(_banco()), config=_so_administrador())
    administrador = _em_memoria(fechada, _o_que_o_servidor_descreve)
    assert administrador["tools/list"] == administrador["prompts/list"] == administrador["prompts/get"] == "ok"
    assert "não existe" in administrador["prompts/get inexistente"]
    aberta = _servidor(FabricaDeClientes(_banco()), identificar=_coordenadora)
    assert _em_memoria(aberta, _o_que_o_servidor_descreve)["tools/list"] == "ok"


def test_sem_identidade_nao_lista():
    async def ninguem(_pedido):
        return None

    respostas = _em_memoria(_servidor(FabricaDeClientes(_banco()), identificar=ninguem), _o_que_o_servidor_descreve)
    assert set(respostas.values()) == {MENSAGEM_SEM_IDENTIDADE}


def test_stdio_reconfere_o_papel_a_cada_chamada():
    db, token = banco_com_token()
    db["aluno"] = {}
    fabrica = FabricaDeClientes(db)
    servidor = _servidor(fabrica, identificar=IdentidadePeloToken(token, fabrica), config=_so_administrador())

    async def corpo(s):
        antes = await s.call_tool("listar_ciclos", {})
        db["usuario_coordenacao"][COORDENADOR]["papel"] = "coordenador"
        depois = await s.call_tool("listar_ciclos", {})
        return antes, depois

    antes, depois = _em_memoria(servidor, corpo)
    assert not antes.isError
    assert json.loads(_texto(depois)) == {"erro": MENSAGEM_SO_ADMINISTRADOR}


# ─── Roteiros (prompts) ──────────────────────────────────────────────────


def test_roteiros_da_coordenacao_viram_prompts():
    async def corpo(s):
        lista = await s.list_prompts()
        prompt = await s.get_prompt("diagnostico_de_ciclo")
        return lista, prompt

    lista, prompt = _em_memoria(_servidor(FabricaDeClientes(_banco())), corpo)
    assert [p.name for p in lista.prompts] == ["diagnostico_de_ciclo", "preparo_de_reuniao"]
    assert lista.prompts[0].title == "Título diagnostico_de_ciclo"
    assert prompt.messages[0].role == "user" and "O método." in prompt.messages[0].content.text


def test_roteiro_inexistente_e_erro_com_texto_nosso():
    async def corpo(s):
        with pytest.raises(McpError) as erro:
            await s.get_prompt("nao_existe")
        return str(erro.value)

    assert "roteiro 'nao_existe' não existe" in _em_memoria(_servidor(FabricaDeClientes(_banco())), corpo)


def test_roteiro_que_quebra_nao_manda_a_excecao_crua():
    class _Quebrada(_RoteirosDeMentira):
        def obter(self, escopo, nome):
            raise RuntimeError("/app/app/chat/roteiros/coordenacao/x.md: Permission denied")

    async def corpo(s):
        with pytest.raises(McpError) as erro:
            await s.get_prompt("diagnostico_de_ciclo")
        return str(erro.value)

    mensagem = _em_memoria(_servidor(FabricaDeClientes(_banco()), roteiros=_Quebrada()), corpo)
    assert "Permission" not in mensagem and "/app/" not in mensagem


def test_os_roteiros_de_verdade_sao_os_da_coordenacao():
    """O módulo real (`app.chat.roteiros`), sem fake: o MCP serve os mesmos
    arquivos que o assistente do app carrega (docs/43 §4.3)."""
    fonte = roteiros_do_sas()
    assert fonte is not None
    nomes = [r.nome for r in fonte.listar("coordenacao")]
    assert nomes, "nenhum roteiro da coordenação"

    async def corpo(s):
        return [p.name for p in (await s.list_prompts()).prompts]

    servidor = montar_servidor(registro=registro_de_mentira(), config=_config(), identificar=_fixa,
                               criar_cliente=FabricaDeClientes(_banco()))
    assert _em_memoria(servidor, corpo) == nomes


def test_instrucoes_dizem_que_so_le_e_como_o_aluno_aparece():
    """Com o nome real (o padrão desde 26/10), nada de "matrícula": era a frase
    do pseudônimo, e o modelo trocaria um pelo outro por conta própria."""
    texto = instrucoes(_config())
    assert "só LÊ" in texto and "pelo nome" in texto and "adolescentes" in texto
    assert "matrícula" not in texto.lower() and "nunca pelo nome" not in texto
    com_pseudonimo = instrucoes(_com_pseudonimo())
    assert "só LÊ" in com_pseudonimo and "matrícula" in com_pseudonimo and "nunca pelo nome" in com_pseudonimo


# ─── HTTP: o que acontece antes da chamada ───────────────────────────────

CABECALHOS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def _app(db: dict, **kw):
    """O app HTTP com a identidade de VERDADE: a do token do request."""
    fabrica = kw.pop("fabrica", None) or FabricaDeClientes(db)
    config = kw.pop("config", None) or _config()
    servidor = _servidor(fabrica, config=config, identificar=identidade_do_pedido, **kw)
    return montar_app(config=config, servidor=servidor, criar_cliente=fabrica, app_env="test"), fabrica


def _com_alunos(db: dict) -> dict:
    db["aluno"] = _banco()["aluno"]
    return db


def _rpc(metodo, params=None, id_=1):
    corpo = {"jsonrpc": "2.0", "id": id_, "method": metodo}
    if params is not None:
        corpo["params"] = params
    return json.dumps(corpo)


def _post(c, corpo, token=None, **cabecalhos):
    h = {**CABECALHOS, **cabecalhos}
    if token:
        h["authorization"] = f"Bearer {token}"
    return c.post("/mcp", headers=h, content=corpo)


INICIO = {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "teste", "version": "0"}}


def test_sem_token_e_401_com_www_authenticate():
    app, fabrica = _app(_banco())
    with TestClient(app) as c:
        r = _post(c, _rpc("tools/list"))
    assert r.status_code == 401
    assert 'error="invalid_token"' in r.headers["www-authenticate"]
    assert fabrica.rpcs == []


def test_jwt_de_sessao_da_api_nao_abre_o_mcp():
    """A separação do docs/43 §5.3, no sentido MCP: um JWT de coordenação
    válido na API não é token do MCP — e nem chega a ir ao banco."""
    sessao = jwt.encode(
        {"sub": COORDENADOR, "tipo": "coordenador", "papel": "administrador",
         "exp": datetime.now(UTC) + timedelta(hours=1)},
        SEGREDO_DA_API, algorithm="HS256",
    )
    app, fabrica = _app(_banco())
    with TestClient(app) as c:
        assert _post(c, _rpc("tools/list"), sessao).status_code == 401
    assert fabrica.rpcs == []


def test_token_no_formato_mas_desconhecido_e_401():
    from app.mcp.tokens import gerar

    app, fabrica = _app(_banco())
    with TestClient(app) as c:
        assert _post(c, _rpc("tools/list"), gerar()[0]).status_code == 401
    assert len(fabrica.rpcs) == 1


def test_token_valido_inicializa_lista_e_chama():
    db, token = banco_com_token()
    app, _ = _app(_com_alunos(db))
    with TestClient(app) as c:
        inicio = _post(c, _rpc("initialize", INICIO), token)
        lista = _post(c, _rpc("tools/list", id_=2), token)
        chamada = _post(c, _rpc("tools/call", {"name": "listar_alunos", "arguments": {}}, id_=3), token,
                        **{"x-request-id": "rid-do-teste"})
    assert inicio.status_code == 200
    resultado = inicio.json()["result"]
    assert resultado["serverInfo"]["name"] == "sas-coordenacao"
    assert "só LÊ" in resultado["instructions"]
    assert {t["name"] for t in lista.json()["result"]["tools"]} == {
        "listar_ciclos", "listar_alunos", "relatorio_ciclo", "explode", "lenta"}
    assert chamada.status_code == 200
    texto = chamada.json()["result"]["content"][0]["text"]
    # O nome real, que é o padrão desde 26/10 (o pseudônimo tem os testes dele).
    assert NOME_A in texto and "Aluno 2026001" not in texto

    (evento,) = _eventos(db)
    # A identidade da auditoria é a do TOKEN deste request — não um argumento.
    assert evento["ator_id"] == COORDENADOR and evento["recurso"] == f"mcp_token/{TOKEN_ID}"
    assert evento["ip"] == "testclient"
    assert evento["request_id"] == "rid-do-teste"


def test_request_id_gerado_pelo_middleware_chega_a_auditoria():
    """Sem X-Request-Id do cliente, o id que o middleware da casa gera é o
    mesmo da resposta e do evento — é ele que costura a linha de log ao
    evento (0022). A chamada atravessa duas task groups do SDK até aqui."""
    db, token = banco_com_token()
    app, _ = _app(_com_alunos(db))
    with TestClient(app) as c:
        r = _post(c, _rpc("tools/call", {"name": "listar_ciclos", "arguments": {}}), token)
    assert r.headers["x-request-id"] == _eventos(db)[0]["request_id"]


@pytest.mark.parametrize("enviado", ["r" * 200, "x" * 129, "x" * 65, "id com espaco", "-", "rid;--"])
def test_x_request_id_fora_da_forma_nao_apaga_a_trilha(enviado):
    """O X-Request-Id ia cru até `evento_auditoria.request_id`, e o gatilho da
    0072 recusa (42501) o INSERT do sas_mcp acima de 128 caracteres: com 129,
    o tools/call devolvia o dado e a trilha ficava sem a linha — só um
    warning no log (revisão final de 26/10). O banco falso do MCP aplica o
    gatilho (`gatilho_da_0072_aceita`). Fora da forma aceita, o id é nosso, e
    é o mesmo na resposta e no evento."""
    db, token = banco_com_token()
    app, _ = _app(_com_alunos(db))
    with TestClient(app) as c:
        r = _post(c, _rpc("tools/call", {"name": "listar_ciclos", "arguments": {}}), token,
                  **{"x-request-id": enviado})
    assert r.json()["result"]["isError"] is False
    (evento,) = _eventos(db)
    assert evento["request_id"] != enviado
    assert evento["request_id"] == r.headers["x-request-id"]


def test_recusa_com_request_id_comprido_tambem_fica_na_trilha():
    """Os desfechos de recusa — inexistente, limite, sem_permissao — passam
    pelo mesmo INSERT: com o id cru, sumiam igual."""
    longo = {"x-request-id": "r" * 200}
    db, token = banco_com_token()
    app, _ = _app(_com_alunos(db), limite=LimitePorMinuto(2))
    with TestClient(app) as c:
        _post(c, _rpc("tools/call", {"name": "inventada", "arguments": {}}), token, **longo)
        _post(c, _rpc("tools/call", {"name": "listar_ciclos", "arguments": {}}), token, **longo)
        _post(c, _rpc("tools/call", {"name": "listar_ciclos", "arguments": {}}), token, **longo)
    coord, token_coord = banco_com_token(papel="coordenador")
    app, _ = _app(_com_alunos(coord), config=_so_administrador())
    with TestClient(app) as c:
        _post(c, _rpc("tools/call", {"name": "listar_ciclos", "arguments": {}}), token_coord, **longo)
    assert [e["detalhe"]["desfecho"] for e in _eventos(db)] == ["inexistente", "ok", "limite"]
    assert [e["detalhe"]["desfecho"] for e in _eventos(coord)] == ["sem_permissao"]


def test_ip_comprido_do_proxy_nao_apaga_a_trilha():
    """Uma location do nginx sem `proxy_set_header X-Forwarded-For` deixa o
    header do cliente passar, e com `forwarded_allow_ips='*'` o uvicorn usa a
    entrada mais à esquerda: o IP vira texto livre, e acima de 64 caracteres o
    gatilho da 0072 recusava o INSERT. O middleware é o do uvicorn de verdade."""
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    db, token = banco_com_token()
    app, _ = _app(_com_alunos(db))
    with TestClient(ProxyHeadersMiddleware(app, trusted_hosts="*")) as c:
        r = _post(c, _rpc("tools/call", {"name": "listar_ciclos", "arguments": {}}), token,
                  **{"x-forwarded-for": "a" * 200 + ", 203.0.113.9"})
    assert r.json()["result"]["isError"] is False
    (evento,) = _eventos(db)
    assert evento["ip"] == "a" * auditoria_mcp.TETO_DO_IP


def test_coordenador_inicializa_mas_nao_lista_pelo_http():
    """O mesmo pelo transporte de verdade: o token aceito de quem não é
    administrador inicializa — as instructions dizem o que o servidor é —,
    mas tools/list e prompts/list voltam erro JSON-RPC com o porquê."""
    db, token = banco_com_token(papel="coordenador")
    app, _ = _app(_com_alunos(db), config=_so_administrador())
    with TestClient(app) as c:
        inicio = _post(c, _rpc("initialize", INICIO), token).json()
        respostas = [_post(c, _rpc(m, id_=2), token).json() for m in ("tools/list", "prompts/list")]
    assert "só LÊ" in inicio["result"]["instructions"]
    for resposta in respostas:
        assert "result" not in resposta and resposta["error"]["message"] == MENSAGEM_SO_ADMINISTRADOR


def test_token_revogado_para_de_abrir_na_hora():
    db, token = banco_com_token()
    app, _ = _app(_com_alunos(db))
    with TestClient(app) as c:
        assert _post(c, _rpc("tools/list"), token).status_code == 200
        db["token_mcp"][TOKEN_ID]["revogado_em"] = datetime.now(UTC).isoformat()
        assert _post(c, _rpc("tools/list"), token).status_code == 401


def test_administrador_rebaixado_perde_o_mcp_na_hora():
    """O PATCH .../papel vale na próxima chamada — como em
    `auth.conta_ainda_e_administradora`: o papel vem da RPC, da tabela. Com a
    regra do administrador ligada, que desde 26/10 é opção."""
    db, token = banco_com_token()
    app, _ = _app(_com_alunos(db), config=_so_administrador())
    corpo = _rpc("tools/call", {"name": "listar_ciclos", "arguments": {}})
    with TestClient(app) as c:
        antes = _post(c, corpo, token).json()["result"]
        db["usuario_coordenacao"][COORDENADOR]["papel"] = "coordenador"
        depois = _post(c, corpo, token).json()["result"]
    assert antes["isError"] is False
    assert depois["isError"] is True
    assert json.loads(depois["content"][0]["text"]) == {"erro": MENSAGEM_SO_ADMINISTRADOR}
    assert [e["detalhe"]["desfecho"] for e in _eventos(db)] == ["ok", "sem_permissao"]


def test_token_de_coordenador_para_de_valer_quando_a_regra_volta():
    """Emitido com MCP_EMISSAO_SO_ADMINISTRADOR=false, ele não pode voltar a
    valer depois que a regra é religada."""
    db, token = banco_com_token(papel="coordenador")
    corpo = _rpc("tools/call", {"name": "listar_ciclos", "arguments": {}})
    aberta, _ = _app(_com_alunos(db))
    fechada, _ = _app(db, config=_so_administrador())
    with TestClient(aberta) as c:
        assert _post(c, corpo, token).json()["result"]["isError"] is False
    with TestClient(fechada) as c:
        resultado = _post(c, corpo, token).json()["result"]
    assert resultado["isError"] is True and "só o administrador" in resultado["content"][0]["text"]


def test_get_e_delete_em_mcp_sao_405():
    """No stateless o GET abriria um SSE que nunca fecha (o servidor não tem
    o que mandar por ele): a especificação manda 405 a quem não oferece."""
    db, token = banco_com_token()
    app, _ = _app(db)
    with TestClient(app) as c:
        h = {"authorization": f"Bearer {token}", "accept": "text/event-stream"}
        r = c.get("/mcp", headers=h)
        assert r.status_code == 405 and r.headers["allow"] == "POST"
        assert c.delete("/mcp", headers=h).status_code == 405
        # Sem token o GET leva 401 antes: quem não se autenticou nem descobre o método.
        assert c.get("/mcp").status_code == 401


def test_host_de_fora_e_421_e_origin_de_fora_e_403():
    db, token = banco_com_token()
    app, _ = _app(db)
    with TestClient(app) as c:
        assert _post(c, _rpc("tools/list"), token, host="evil.example").status_code == 421
        assert _post(c, _rpc("tools/list"), token, origin="https://evil.example").status_code == 403
        assert _post(c, _rpc("tools/list"), token).status_code == 200


def test_banco_fora_na_conferencia_e_503_sem_texto_cru():
    db, token = banco_com_token()
    fabrica = FabricaDeClientes(db, falha_na_rpc=RuntimeError("could not connect to postgrest_mcp:3000"))
    app, _ = _app(db, fabrica=fabrica)
    with TestClient(app) as c:
        r = _post(c, _rpc("tools/list"), token)
    assert r.status_code == 503
    assert r.json()["error"] == "temporarily_unavailable"
    assert "postgrest" not in r.text


def test_health_responde_sem_token_e_sem_banco():
    db, _ = banco_com_token()
    fabrica = FabricaDeClientes(db, falha_na_rpc=RuntimeError("fora"))
    app, _ = _app(db, fabrica=fabrica)
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


# ─── O custo de um token falso ───────────────────────────────────────────

_TOKEN_NO_FORMATO = "Bearer sas_mcp_" + "a" * 43


def test_so_a_rota_mcp_vai_ao_banco_por_token():
    """Com a autenticação no app inteiro, /health e caminho inexistente também
    custavam uma ida à RPC por token no formato (revisão de 24/10)."""
    db, _ = banco_com_token()
    app, fabrica = _app(db)
    with TestClient(app) as c:
        assert c.get("/health", headers={"authorization": _TOKEN_NO_FORMATO}).status_code == 200
        assert c.get("/qualquer", headers={"authorization": _TOKEN_NO_FORMATO}).status_code == 404
    assert fabrica.rpcs == []


def test_teto_de_tokens_recusados_poupa_o_banco_e_isenta_quem_ja_entrou():
    db, token = banco_com_token()
    app, fabrica = _app(_com_alunos(db), config=_config(falhas_de_token_por_minuto=3))
    lista = _rpc("tools/list")
    with TestClient(app) as c:
        assert _post(c, lista, token).status_code == 200                     # entrou: fica isento
        assert [_post(c, lista, gerar()[0]).status_code for _ in range(3)] == [401, 401, 401]
        antes = len(fabrica.rpcs)
        barrado = _post(c, lista, gerar()[0])
        assert barrado.status_code == 429 and barrado.headers["retry-after"] == "60"
        assert len(fabrica.rpcs) == antes                                     # nem foi ao banco
        # Atrás de um nginx mal configurado todo mundo tem o mesmo IP: o token
        # que já entrou continua passando — e continua sendo CONFERIDO.
        assert _post(c, lista, token).status_code == 200
        assert len(fabrica.rpcs) == antes + 1
        # A isenção não é cache: revogado, a próxima já é recusada.
        db["token_mcp"][TOKEN_ID]["revogado_em"] = datetime.now(UTC).isoformat()
        assert _post(c, lista, token).status_code == 401
        assert _post(c, lista, token).status_code == 429                     # e perdeu a isenção


def _conexao(ip: str, autorizacao: str):
    from starlette.requests import HTTPConnection

    return HTTPConnection({"type": "http", "headers": [(b"authorization", autorizacao.encode())],
                           "client": (ip, 40000)})


def test_ip_barrado_nao_barra_o_vizinho_e_lixo_nao_conta():
    db, _ = banco_com_token()
    fabrica = FabricaDeClientes(db)
    autenticacao = AutenticacaoDoMcp(VerificadorDeToken(fabrica), FalhasDeTokenPorIp(1), RequisicoesPorToken(100))

    async def rodar():
        # Fora do formato: nem banco nem contagem.
        for _ in range(5):
            assert await autenticacao.authenticate(_conexao("198.51.100.1", "Bearer lixo")) is None
        assert await autenticacao.authenticate(_conexao("198.51.100.1", f"Bearer {gerar()[0]}")) is None
        with pytest.raises(TentativasDemais):
            await autenticacao.authenticate(_conexao("198.51.100.1", f"Bearer {gerar()[0]}"))
        assert await autenticacao.authenticate(_conexao("198.51.100.2", f"Bearer {gerar()[0]}")) is None

    asyncio.run(rodar())
    assert len(fabrica.rpcs) == 2


def test_teto_por_ip_vence_com_a_janela_e_tem_teto_de_memoria():
    relogio = _Relogio()
    falhas = FalhasDeTokenPorIp(2, relogio=relogio)
    assert falhas.recusado("198.51.100.1", "h1") is False
    assert falhas.recusado("198.51.100.1", "h2") is True        # a que fecha o teto: loga uma vez
    assert falhas.barrado("198.51.100.1", "h3") and not falhas.barrado("198.51.100.2", "h3")
    relogio.agora += 61
    assert not falhas.barrado("198.51.100.1", "h3")

    falhas.MAXIMO_DE_CHAVES = 3
    for i in range(10):
        falhas.recusado(f"10.0.0.{i}", "h")
    assert len(falhas._falhas) == 3


def test_teto_de_requisicoes_por_token_vale_para_todo_metodo_e_poupa_o_banco():
    """Só o tools/call tinha teto: 150 tools/list de um token aceito em 0,9 s,
    cada um conferido pela RPC no pool de 3 do postgrest_mcp, o mesmo das
    tools (revisão final de 26/10). O token aceito fica isento do teto por IP,
    então era só ele."""
    db, token = banco_com_token()
    app, fabrica = _app(_com_alunos(db), config=_config(requisicoes_por_minuto=3))
    with TestClient(app) as c:
        codigos = [_post(c, _rpc(m), token).status_code for m in ("initialize", "tools/list", "prompts/list")]
        antes = len(fabrica.rpcs)
        barrado = _post(c, _rpc("tools/list"), token)
        get = c.get("/mcp", headers={"authorization": f"Bearer {token}"})
    assert codigos == [200, 200, 200]
    assert barrado.status_code == 429 and barrado.headers["retry-after"] == "60"
    assert barrado.json()["error"] == "too_many_requests"
    assert get.status_code == 429                    # o GET do SSE também conta
    assert len(fabrica.rpcs) == antes                # nem foi ao banco


def test_requisicoes_por_token_tem_janela_teto_de_memoria_e_e_por_token():
    relogio = _Relogio()
    teto = RequisicoesPorToken(2, relogio=relogio)
    assert [teto.admitir("h1") for _ in range(3)] == [True, True, False]
    assert teto.admitir("h2")                        # o vizinho não paga
    relogio.agora += 61
    assert teto.admitir("h1")
    teto.MAXIMO_DE_CHAVES = 3
    for i in range(10):
        teto.admitir(f"inventado-{i}")
    assert len(teto._por_token) == 3


def test_o_teto_geral_fica_acima_do_de_tools_call():
    """Quem só consulta tem de bater ANTES no limite do tools/call, que
    responde ao modelo com a mensagem e grava a linha de auditoria; o 429 do
    teto geral não diz nada ao modelo."""
    config = _config()
    assert config.requisicoes_por_minuto > config.limite_por_minuto


def test_cliente_oficial_do_sdk_conversa_com_o_app_de_ponta_a_ponta():
    """O cliente Streamable HTTP do próprio SDK — o mesmo protocolo do
    `mcp-remote` e do Claude Code: initialize, a notificação `initialized`
    (POST sem id, que o só-POST deixa passar), tools/list e tools/call."""
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    db, token = banco_com_token()
    app, _ = _app(_com_alunos(db))

    async def rodar():
        # O ASGITransport não roda o lifespan; sem ele o gerente do SDK não abre.
        async with app.router.lifespan_context(app), httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"authorization": f"Bearer {token}"},
        ) as http, streamable_http_client("http://testserver/mcp", http_client=http) as (leitura, escrita, _), \
                ClientSession(leitura, escrita) as sessao:
            inicio = await sessao.initialize()
            nomes = {t.name for t in (await sessao.list_tools()).tools}
            chamada = await sessao.call_tool("listar_alunos", {"limite": "1"})
            return inicio, nomes, chamada

    inicio, nomes, chamada = asyncio.run(rodar())
    assert inicio.serverInfo.name == "sas-coordenacao" and "só LÊ" in inicio.instructions
    assert "listar_alunos" in nomes and "gerar_grafico" not in nomes
    assert not chamada.isError
    assert json.loads(chamada.content[0].text)["alunos"] == [
        {"alunoId": A, "nome": NOME_A, "zona": "risco"}
    ]


def test_sem_emissor_oauth_nao_publica_metadado_nem_aponta_para_ele():
    """Fase 2: sem servidor de autorização, mandar o cliente procurar um seria
    pior que não dizer nada."""
    db, _ = banco_com_token()
    app, _ = _app(db, config=_config(url_publica="https://portalsas.online/mcp"))
    with TestClient(app) as c:
        assert c.get("/.well-known/oauth-protected-resource/mcp").status_code == 404
        assert "resource_metadata" not in _post(c, _rpc("tools/list")).headers["www-authenticate"]


def test_com_emissor_oauth_publica_o_rfc_9728():
    """O ponto em que a Fase 3 pluga: o metadado e o WWW-Authenticate."""
    db, _ = banco_com_token()
    config = _config(url_publica="https://portalsas.online/mcp", emissor_oauth="https://portalsas.online")
    app, _ = _app(db, config=config)
    with TestClient(app) as c:
        metadado = c.get("/.well-known/oauth-protected-resource/mcp")
        www = _post(c, _rpc("tools/list")).headers["www-authenticate"]
    assert metadado.status_code == 200
    assert metadado.json()["resource"] == "https://portalsas.online/mcp"
    assert metadado.json()["scopes_supported"] == ["sas.leitura"]
    assert 'resource_metadata="https://portalsas.online/.well-known/oauth-protected-resource/mcp"' in www
