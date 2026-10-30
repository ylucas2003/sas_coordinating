"""O catálogo do MCP: o que `tools/list` mostra e o que `tools/call` aceita.

Quase tudo contra um registro de MENTIRA, montado aqui: quem decide quais
tools reais saem do SAS é a política de `app/chat/ferramentas.py`
(`expor_no_mcp`), e o catálogo tem de seguir a política, seja ela qual for.
Contra o registro de VERDADE ficam só as higienes que valem para qualquer
política — nome, schema e teto de toda tool que estiver exposta, e nenhuma
descrição do tools/list mandando a uma tool fora do catálogo, nos dois modos —
e as trocas de texto que o MCP faz hoje (`TROCAS_*`).

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_mcp_catalogo.py -q
"""

from __future__ import annotations

import asyncio
import json
import re

import jsonschema
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from app.chat.ferramentas import REGISTRO, Ferramenta, Registro
from app.mcp.catalogo import (
    INTEIROS_QUE_NAO_SAO_LIMITE,
    NOMES_DE_LIMITE,
    SO_COM_NOME_DO_ALUNO,
    Catalogo,
    aplicar_teto,
    normalizar_schema,
)
from app.mcp.configuracao import ConfiguracaoMcp
from app.mcp.servidor import montar_servidor
from app.mcp.tokens import Identidade


def _h(cliente, **kw):
    return {"ok": True, **kw}


def _ferramenta(nome, *, escopo="coordenacao", expor=True, leitura=True, parametros=None, handler=_h):
    return Ferramenta(
        nome=nome, descricao=f"descrição de {nome}",
        parametros=parametros or {"type": "object", "properties": {}},
        escopo=escopo, handler=handler, somente_leitura=leitura, expor_no_mcp=expor,
    )


def _com_limite(cliente, *, limite: int = 30):
    return {"limite": limite}


def _sem_teto(cliente, *, limite: int | None = None):
    return {"limite": limite}


def _padrao_grande(cliente, *, k: int = 500):
    return {"k": k}


def registro_de_mentira() -> Registro:
    return Registro([
        _ferramenta("exposta"),
        _ferramenta("nao_exposta", expor=False),
        # Tool do aluno nem pode ser marcada (o Registro recusa no import);
        # aqui ela existe para provar que o catálogo nem olha o escopo dela.
        _ferramenta("do_aluno", escopo="aluno", expor=False),
        _ferramenta("escreve", leitura=False),
        _ferramenta(
            "com_limite", handler=_com_limite,
            parametros={"type": "object", "properties": {
                "limite": {"type": "integer", "default": 30, "description": "Máx. de linhas."},
            }},
        ),
        _ferramenta("sem_teto", handler=_sem_teto,
                    parametros={"type": "object", "properties": {"limite": {"type": "integer"}}}),
        _ferramenta("padrao_grande", handler=_padrao_grande,
                    parametros={"type": "object", "properties": {"k": {"type": "integer", "default": 500}}}),
    ])


def _f(nome: str) -> Ferramenta:
    """A ferramenta de mentira pelo nome, sem passar por sessão nenhuma."""
    return next(
        f for escopo in ("coordenacao", "aluno") for f in registro_de_mentira().catalogo(escopo) if f.nome == nome
    )


# ─── Quem entra ──────────────────────────────────────────────────────────


def test_so_entram_tools_de_coordenacao_marcadas_e_somente_leitura():
    catalogo = Catalogo(registro_de_mentira(), teto_de_linhas=50)
    nomes = {t.name for t in catalogo.listar()}
    assert nomes == {"exposta", "com_limite", "sem_teto", "padrao_grande"}
    # O que não está listado também não é chamável pelo nome: é a guarda que
    # o SDK não faz (ele deixa tool não listada chegar ao handler).
    for fora in ("nao_exposta", "do_aluno", "escreve", "inventada", None, 42):
        assert catalogo.obter(fora) is None


def test_com_o_pseudonimo_as_que_so_servem_com_o_nome_ficam_fora():
    """SO_COM_NOME_DO_ALUNO: no catálogo com o nome real (o padrão desde 26/10),
    fora dele — e não chamáveis pelo nome — com o pseudônimo ligado."""
    registro = Registro([
        _ferramenta("exposta"), *(_ferramenta(nome) for nome in sorted(SO_COM_NOME_DO_ALUNO)),
    ])
    com_nome = Catalogo(registro, teto_de_linhas=50)
    assert {t.name for t in com_nome.listar()} == {"exposta", *SO_COM_NOME_DO_ALUNO}
    com_pseudonimo = Catalogo(registro, teto_de_linhas=50, com_nome_do_aluno=False)
    assert {t.name for t in com_pseudonimo.listar()} == {"exposta"}
    assert all(com_pseudonimo.obter(nome) is None for nome in SO_COM_NOME_DO_ALUNO)
    esperadas = {
        "buscar_aluno_por_nome", "listar_alertas",
        # A captação externa (30/10): o nome é o objeto delas, e é de gente de fora.
        "buscar_candidatos_externos", "buscar_candidatos_por_conquista", "perfil_do_candidato_externo",
    }
    assert esperadas == SO_COM_NOME_DO_ALUNO


def test_toda_tool_vai_anotada_como_leitura_sem_mundo_aberto():
    for tool in Catalogo(registro_de_mentira(), teto_de_linhas=50).listar():
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.openWorldHint is False


def test_o_catalogo_nao_altera_o_schema_do_registro():
    """O chat do app continua vendo o schema de sempre, com `default`."""
    registro = registro_de_mentira()
    antes = json.dumps([f.parametros for f in registro.catalogo("coordenacao")], sort_keys=True)
    Catalogo(registro, teto_de_linhas=10).listar()
    assert json.dumps([f.parametros for f in registro.catalogo("coordenacao")], sort_keys=True) == antes


# ─── O schema ────────────────────────────────────────────────────────────


def test_schema_sem_schema_format_default_e_tupla():
    entrada = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "ciclo_id": {"type": "string", "format": "uuid", "description": "O ciclo."},
            "limite": {"type": "integer", "default": 30},
            "ids": {"type": "array", "items": [{"type": "string"}, {"type": "string"}]},
            "par": {"type": "array", "prefixItems": [{"type": "string"}, {"type": "integer"}]},
            # Parâmetros CHAMADOS format e default: são nomes, não palavras do schema.
            "format": {"type": "string", "enum": ["csv", "json"]},
            "default": {"type": "boolean"},
        },
        "required": ["ciclo_id", "fantasma"],
    }
    saida = normalizar_schema(entrada)
    texto = json.dumps(saida)
    assert "$schema" not in texto and '"uuid"' not in texto and "prefixItems" not in texto
    propriedades = saida["properties"]
    assert "format" not in propriedades["ciclo_id"]
    assert "default" not in propriedades["limite"]
    assert propriedades["limite"]["description"] == "Padrão: 30."
    assert propriedades["ids"]["items"] == {"type": "string"}       # tupla homogênea vira lista
    assert "items" not in propriedades["par"]                        # heterogênea perde o tipo de item
    assert set(propriedades) >= {"format", "default"}                # os PARÂMETROS ficaram
    assert saida["required"] == ["ciclo_id"]                         # obrigatório inexistente sai
    jsonschema.Draft202012Validator.check_schema(saida)


def test_default_vai_para_o_fim_da_descricao():
    saida = normalizar_schema({"type": "object", "properties": {
        "zona": {"type": "string", "default": "risco", "description": "Qual zona."}}})
    assert saida["properties"]["zona"]["description"] == 'Qual zona. Padrão: "risco".'


def test_schema_vazio_vira_objeto_com_properties():
    assert normalizar_schema(None) == {"type": "object", "properties": {}}
    assert normalizar_schema({}) == {"type": "object", "properties": {}}


def test_limite_ganha_teto_no_schema_e_na_descricao():
    tool = next(t for t in Catalogo(registro_de_mentira(), teto_de_linhas=50).listar() if t.name == "com_limite")
    limite = tool.inputSchema["properties"]["limite"]
    assert limite["minimum"] == 1 and limite["maximum"] == 50
    assert limite["description"] == "Máx. de linhas. Padrão: 30. No máximo 50."


# ─── O teto de linhas ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("pedido", "esperado"),
    [
        (10, 10), (50, 50), (1000, 50), ("1000", 50), (1000.0, 50),
        (0, 1), (-1, 1), ("-5", 1),
        # O que não é inteiro inequívoco fica como veio: o registro recusa
        # com a mensagem certa ("deveria ser um número inteiro").
        (True, True), ("dez", "dez"), (3.5, 3.5),
    ],
)
def test_teto_corrige_o_limite_pedido(pedido, esperado):
    assert aplicar_teto(_f("com_limite"), {"limite": pedido}, 50)["limite"] == esperado


def test_teto_respeita_o_default_do_handler_quando_cabe():
    assert aplicar_teto(_f("com_limite"), {}, 50) == {}      # o handler aplica os 30 dele


def test_teto_entra_quando_o_default_passa_dele_ou_nao_existe():
    assert aplicar_teto(_f("padrao_grande"), {}, 50) == {"k": 50}
    assert aplicar_teto(_f("sem_teto"), {}, 50) == {"limite": 50}
    assert aplicar_teto(_f("sem_teto"), {"limite": None}, 50) == {"limite": 50}


def test_teto_nao_toca_os_outros_argumentos_nem_a_entrada():
    entrada = {"limite": 999, "ciclo_id": "c1"}
    assert aplicar_teto(_f("com_limite"), entrada, 50) == {"limite": 50, "ciclo_id": "c1"}
    assert entrada == {"limite": 999, "ciclo_id": "c1"}
    assert aplicar_teto(_f("com_limite"), None, 50) == {}


# ─── Higiene do registro de VERDADE (vale para qualquer política) ────────

EXPOSTAS = [f for f in REGISTRO.catalogo("coordenacao") if f.expor_no_mcp]
# Lista, e não `ids=lambda`: com a política ainda sem nenhuma tool exposta, o
# parametrize vazio chamaria a lambda com o marcador NotSet e quebraria a coleta.
IDS_EXPOSTAS = [f.nome for f in EXPOSTAS]
_NOME_DE_TOOL = re.compile(r"^[A-Za-z0-9._-]{1,128}$")   # mcp/shared/tool_name_validation.py


def test_catalogo_real_e_exatamente_a_politica_do_registro():
    catalogo = Catalogo(REGISTRO, teto_de_linhas=50)
    esperadas = {f.nome for f in EXPOSTAS if f.somente_leitura}
    assert {t.name for t in catalogo.listar()} == esperadas
    assert not {f.nome for f in REGISTRO.catalogo("aluno")} & esperadas


@pytest.mark.parametrize("f", EXPOSTAS, ids=IDS_EXPOSTAS)
def test_tool_exposta_tem_nome_e_schema_que_cliente_estrito_aceita(f):
    assert _NOME_DE_TOOL.fullmatch(f.nome)
    schema = normalizar_schema(f.parametros)
    jsonschema.Draft202012Validator.check_schema(schema)
    texto = json.dumps(schema)
    assert "$schema" not in texto and "prefixItems" not in texto


@pytest.mark.parametrize("f", EXPOSTAS, ids=IDS_EXPOSTAS)
def test_todo_inteiro_de_tool_exposta_e_limite_conhecido_ou_declarado(f):
    """Tool nova com um `max_linhas` passaria sem teto. Ou o nome entra em
    NOMES_DE_LIMITE, ou em INTEIROS_QUE_NAO_SAO_LIMITE — por escrito."""
    inteiros = {n for n, e in f.propriedades.items() if (e or {}).get("type") == "integer"}
    desconhecidos = inteiros - NOMES_DE_LIMITE - INTEIROS_QUE_NAO_SAO_LIMITE
    assert not desconhecidos, f"{f.nome}: {sorted(desconhecidos)}"


class _TabelaQueRecusaEscrita:
    def __init__(self, nome: str, escritas: list):
        self._nome, self._escritas = nome, escritas

    def select(self, *args, **kw):
        return _CONSULTA_VAZIA

    def _escrever(self, operacao: str):
        self._escritas.append(f"{operacao}:{self._nome}")
        raise PermissionError("42501: o sas_mcp não escreve")

    def insert(self, *a, **k):
        return self._escrever("insert")

    def update(self, *a, **k):
        return self._escrever("update")

    def upsert(self, *a, **k):
        return self._escrever("upsert")

    def delete(self, *a, **k):
        return self._escrever("delete")


class _ConsultaVazia:
    """Toda consulta devolve vazio, encadeando qualquer filtro."""

    data: list = []   # noqa: RUF012 — atributo de leitura, nunca mutado
    count = 0

    def __getattr__(self, _nome):
        return lambda *a, **k: self

    def execute(self):
        return self


_CONSULTA_VAZIA = _ConsultaVazia()


class _ClienteQueRecusaEscrita:
    def __init__(self):
        self.escritas: list[str] = []

    def table(self, nome):
        return _TabelaQueRecusaEscrita(nome, self.escritas)

    def rpc(self, funcao, *_a, **_k):
        # O sas_mcp executa duas funções (FUNCOES_EXECUTAVEIS do verificador):
        # mcp_conferir_token (0072), que é do portão e não de tool, e a busca
        # por conquista (0068), SECURITY INVOKER, que só lê o que a 0076 lhe deu.
        # Qualquer outra RPC numa tool exposta é 42501 em produção, mesmo que
        # ela só leia.
        if funcao == "buscar_candidatos_por_conquista":
            return _CONSULTA_VAZIA
        self.escritas.append(f"rpc:{funcao}")
        raise PermissionError("42501: o sas_mcp não executa esta função")


def _argumentos_de_mentira(f: Ferramenta) -> dict:
    from app.chat.ferramentas import parametros_do_handler

    _, obrigatorios = parametros_do_handler(f.handler)
    exemplo_de_id = "00000000-0000-4000-8000-000000000000"
    args: dict = {}
    for nome in obrigatorios:
        esquema = f.propriedades.get(nome) or {}
        if esquema.get("enum"):
            args[nome] = esquema["enum"][0]
        elif esquema.get("type") == "integer":
            args[nome] = 1
        elif esquema.get("type") == "number":
            args[nome] = 1.0
        elif esquema.get("type") == "boolean":
            args[nome] = False
        elif esquema.get("type") == "array":
            args[nome] = [exemplo_de_id, "00000000-0000-4000-8000-000000000001"]
        else:
            args[nome] = exemplo_de_id
    return args


_FALHA_DO_REGISTRO = "falhou do nosso lado"   # a mensagem de ferramentas._executar


def _rodar_isolada(registro: Registro, f: Ferramenta, monkeypatch) -> tuple[dict, list[str], list[str]]:
    """Roda a tool com o banco que recusa escrita e a rede gravada.

    Devolve (resultado, escritas e RPCs, tentativas de rede). Três portas por
    onde uma tool escaparia do cliente injetado, todas fechadas aqui:
      * cliente criado POR DENTRO (`get_supabase`, `criar_cliente_supabase`):
        troca-se o nome em todo módulo `app.*` que o importou, e ele devolve o
        mesmo cliente que recusa — a escrita por ele também é gravada;
      * socket e DNS: gravados e recusados (Canvas, AWS, OpenAI, PostgREST);
      * e a falha engolida: o registro transforma exceção em "falhou do nosso
        lado", e é por ela que uma tentativa barrada ficaria invisível.
    """
    import socket
    import sys

    from app import supabase_client
    from app.chat.ferramentas import Sessao

    rede: list[str] = []

    def sem_rede(_sock, endereco, *_a, **_k):
        rede.append(f"connect:{endereco}")
        raise OSError("rede bloqueada no teste")

    def sem_dns(host, *_a, **_k):
        rede.append(f"dns:{host}")
        raise OSError("dns bloqueado no teste")

    monkeypatch.setattr(socket.socket, "connect", sem_rede)
    monkeypatch.setattr(socket, "getaddrinfo", sem_dns)

    cliente = _ClienteQueRecusaEscrita()
    originais = {supabase_client.get_supabase, supabase_client.criar_cliente_supabase}
    for nome_do_modulo, modulo in list(sys.modules.items()):
        if modulo is None or not (nome_do_modulo == "app" or nome_do_modulo.startswith("app.")):
            continue
        for nome in ("get_supabase", "criar_cliente_supabase"):
            atual = getattr(modulo, nome, None)
            if any(atual is original for original in originais):
                monkeypatch.setattr(modulo, nome, lambda *_a, **_k: cliente)

    sessao = Sessao(tipo="coordenador", usuario="coord:teste", papel="coordenador")
    resultado = registro.despachar(sessao, f.nome, cliente, _argumentos_de_mentira(f))
    return resultado, cliente.escritas, rede


@pytest.mark.parametrize("f", EXPOSTAS, ids=IDS_EXPOSTAS)
def test_tool_exposta_nao_escreve_nem_chama_rpc(f, monkeypatch):
    """O grep de test_chat_tools.py só vê o PRIMEIRO nível; aqui a tool RODA,
    com tudo que ela chama por dentro, contra um banco que recusa escrita e
    RPC e devolve vazio a toda leitura. Sob o `sas_mcp` a escrita viraria só
    a falha genérica (invariante 6) — este teste a mostra antes, pelo nome.

    ⚠️ Com o banco vazio, a maioria das tools para no "não encontrado": o que
    se prova é o caminho do vazio, não o de um ciclo cheio."""
    resultado, escritas, rede = _rodar_isolada(REGISTRO, f, monkeypatch)
    assert escritas == [], f"{f.nome} tentou: {escritas}"
    assert rede == [], f"{f.nome} tentou a rede: {rede}"
    assert _FALHA_DO_REGISTRO not in str(resultado.get("erro", "")), f"{f.nome} quebrou: {resultado}"


def test_a_higiene_pega_escrita_por_cliente_proprio_e_rede():
    """O caso da revisão de 24/10: a versão anterior só olhava o cliente
    injetado e ignorava o resultado — estas duas passavam verdes."""

    def escreve_por_fora(cliente):
        from app.supabase_client import criar_cliente_supabase

        criar_cliente_supabase().table("aluno").update({"nome": "x"}).eq("id", "1").execute()
        return {"ok": True}

    def chama_a_openai(cliente):
        import httpx

        httpx.get("https://api.openai.com/v1/models")
        return {"ok": True}

    registro = Registro([_ferramenta("escreve_por_fora", handler=escreve_por_fora),
                         _ferramenta("chama_a_openai", handler=chama_a_openai)])
    with pytest.MonkeyPatch.context() as mp:
        resultado, escritas, _ = _rodar_isolada(registro, _f_de(registro, "escreve_por_fora"), mp)
    assert escritas == ["update:aluno"] and _FALHA_DO_REGISTRO in resultado["erro"]
    with pytest.MonkeyPatch.context() as mp:
        resultado, escritas, rede = _rodar_isolada(registro, _f_de(registro, "chama_a_openai"), mp)
    assert rede and _FALHA_DO_REGISTRO in resultado["erro"]


def _f_de(registro: Registro, nome: str) -> Ferramenta:
    return next(f for f in registro.catalogo("coordenacao") if f.nome == nome)


@pytest.mark.parametrize("f", EXPOSTAS, ids=IDS_EXPOSTAS)
def test_tool_exposta_e_somente_leitura(f):
    """A anotação readOnlyHint=True não pode mentir — e o catálogo exclui a
    que não é. Este teste avisa ANTES de ela sumir do MCP em silêncio."""
    assert f.somente_leitura


# ─── O texto que o tools/list publica, nos DOIS modos ────────────────────

#: Toda tool do registro, dos dois escopos. A que o catálogo de um modo não
#: tem é uma que a IA de fora não acha.
REGISTRADAS = frozenset(
    f.nome for escopo in ("coordenacao", "aluno") for f in REGISTRO.catalogo(escopo)
)


def _tools_list(com_nome_do_aluno: bool) -> list:
    """O tools/list de verdade: o servidor do MCP com o REGISTRO do SAS e a
    configuração do modo, pelo cliente em memória do SDK — o que a IA de fora
    recebe, e não o que o catálogo diz que monta."""

    async def administradora(_pedido):
        return Identidade(token_id="t", coordenador_id="c", nome="Admin", papel="administrador")

    def sem_banco():
        raise AssertionError("o tools/list não abre cliente PostgREST")

    servidor = montar_servidor(
        config=ConfiguracaoMcp(_env_file=None, mostrar_nome_do_aluno=com_nome_do_aluno),
        registro=REGISTRO,
        identificar=administradora,
        criar_cliente=sem_banco,
    )

    async def listar():
        async with create_connected_server_and_client_session(servidor) as sessao:
            return (await sessao.list_tools()).tools

    return asyncio.run(listar())


def _descricoes(tool) -> list[tuple[str, str]]:
    """(onde, texto) de cada descrição publicada de uma tool: a dela e a de
    cada nó do inputSchema que tem uma — parâmetro, item de lista, o que for."""
    achadas = [("description", tool.description or "")]
    pilha: list[tuple[str, object]] = [("inputSchema", tool.inputSchema)]
    while pilha:
        caminho, no = pilha.pop()
        if isinstance(no, dict):
            for chave, valor in no.items():
                if chave == "description" and isinstance(valor, str):
                    achadas.append((f"{caminho}.description", valor))
                else:
                    pilha.append((f"{caminho}.{chave}", valor))
        elif isinstance(no, list):
            pilha.extend((f"{caminho}[{i}]", item) for i, item in enumerate(no))
    return achadas


@pytest.mark.parametrize("com_nome_do_aluno", [True, False], ids=["nome-real", "pseudonimo"])
def test_o_tools_list_nao_manda_usar_tool_que_nao_esta_nele(com_nome_do_aluno):
    """As descrições nascem no chat, onde toda tool citada existe. No MCP, não:
    `exportar_csv` fica fora nos dois modos, e o pseudônimo tira
    `buscar_aluno_por_nome` — e a IA de fora, mandada à tool citada, recebia
    "tool '…' não existe" (prova de ponta a ponta de 27/10). Vale para a
    descrição da tool e para a de cada parâmetro, com o nome como palavra
    inteira. Os roteiros (prompts) ficam de fora: eles já mandam seguir com as
    tools que a conexão tiver."""
    tools = _tools_list(com_nome_do_aluno)
    fora = REGISTRADAS - {t.name for t in tools}
    assert {"exportar_csv", "gerar_grafico", "navegar_para"} <= fora
    assert ("buscar_aluno_por_nome" in fora) == (not com_nome_do_aluno)
    citacao = re.compile(r"\b(" + "|".join(sorted(map(re.escape, fora))) + r")\b")
    citadas = [
        f"{tool.name} → {onde} cita {achado.group(1)}"
        for tool in tools
        for onde, texto in _descricoes(tool)
        for achado in citacao.finditer(texto)
    ]
    assert citadas == []


def test_a_troca_e_so_no_mcp_e_aponta_para_a_tool_que_ele_tem():
    """No chat as frases ficam, porque lá `exportar_csv` e
    `buscar_aluno_por_nome` existem. No MCP, `notas_simulado` diz como a lista
    vem cortada, e, com o pseudônimo, a porta de entrada é a matrícula — na
    instrução e no exemplo, que com nome de pessoa ensinaria o modelo a pedir
    nome. Com o nome real, `obter_aluno` e `comparar_alunos` saem como no chat."""
    chat = {f.nome: f.descricao for f in REGISTRO.catalogo("coordenacao")}
    com_nome = {t.name: t.description for t in _tools_list(True)}
    pseudonimo = {t.name: t.description for t in _tools_list(False)}

    assert "exportar_csv" in chat["notas_simulado"]
    assert "truncado" in com_nome["notas_simulado"] and "truncado" in pseudonimo["notas_simulado"]
    for nome in ("obter_aluno", "comparar_alunos"):
        assert "buscar_aluno_por_nome" in chat[nome]
        assert com_nome[nome] == chat[nome]
        assert "buscar_aluno_por_matricula" in pseudonimo[nome]
    assert "Ana" not in pseudonimo["comparar_alunos"]
    assert "Aluno 2026001" in pseudonimo["comparar_alunos"]


def test_toda_troca_ainda_acha_o_trecho_que_troca():
    """A troca cujo trecho saiu da descrição do chat não troca mais nada —
    sobra como configuração morta. Se a frase nova voltar a citar a tool
    ausente, quem reprova é o teste do tools/list, acima."""
    from app.mcp.catalogo import TROCAS_COM_PSEUDONIMO, TROCAS_NOS_DOIS_MODOS

    chat = {f.nome: f.descricao for f in REGISTRO.catalogo("coordenacao")}
    for trocas in (TROCAS_NOS_DOIS_MODOS, TROCAS_COM_PSEUDONIMO):
        for nome, pares in trocas.items():
            assert nome in chat, nome
            for trecho, _no_mcp in pares:
                assert trecho in chat[nome], (nome, trecho)


#: Um identificador em snake_case — é como toda tool se chama (`obter_aluno`).
_IDENTIFICADOR = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


def test_o_texto_novo_de_cada_troca_so_cita_tool_do_catalogo_do_modo():
    """O guarda do tools/list, acima, só enxerga nome de tool REGISTRADA. Uma
    troca que aponte para uma tool que não existe — renomeada no chat, ou
    digitada errado — passaria por ele, e a IA voltaria a receber "tool '…'
    não existe" (revisão de 27/10). Aqui o lado do MCP de cada troca é lido
    por identificador: todo nome em snake_case tem de ser tool do catálogo do
    modo em que a troca vale."""
    from app.mcp.catalogo import TROCAS_COM_PSEUDONIMO, TROCAS_NOS_DOIS_MODOS

    com_nome = {t.name for t in _tools_list(True)}
    pseudonimo = {t.name for t in _tools_list(False)}
    casos = [(TROCAS_NOS_DOIS_MODOS, com_nome & pseudonimo), (TROCAS_COM_PSEUDONIMO, pseudonimo)]
    fora = [
        (nome, citado)
        for trocas, catalogo in casos
        for nome, pares in trocas.items()
        for _trecho, no_mcp in pares
        for citado in _IDENTIFICADOR.findall(no_mcp)
        if citado not in catalogo
    ]
    assert fora == []
