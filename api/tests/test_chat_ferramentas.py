"""O registro único das ferramentas do assistente (docs/43 §3).

O que se tranca aqui é a fronteira entre os dois escopos — o do aluno
(individual: só os dados dele, com o `aluno_id` do token) e o da coordenação
(coletivo: qualquer aluno) — e as guardas que o despacho aplica antes de uma
tool rodar. Uma classe por invariante do docs/43 §3.2, na mesma ordem.

Nenhum teste aqui toca banco nem OpenAI. As tools são de mentira, e o cliente é
um objeto que EXPLODE se alguém tentar usá-lo: é assim que se prova que uma
chamada recusada nem chegou a consultar nada.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_chat_ferramentas.py -q
"""

import asyncio
import copy
import datetime
import json
import logging
import threading
import time
import types

import pytest

from app.chat import ferramentas, roteiros, tools_aluno
from app.chat import tools as tools_coordenacao
from app.chat.ferramentas import (
    LIMITE_DO_TITULO,
    PRAZO_PADRAO_S,
    REGISTRO,
    TIPOS_DE_ARTEFATO,
    Ferramenta,
    Registro,
    RespostaDePrazo,
    Sessao,
    SessaoRecusada,
    Volta,
    artefatos_do_resultado,
    parametros_do_handler,
    serializar_para_modelo,
    sessao_do_token,
)
from app.chat.perfis import perfil_aluno, perfil_coordenador

ALUNO = Sessao(tipo="aluno", usuario="aluno:a1", aluno_id="a1", nome="Ana")
COORDENACAO = Sessao(tipo="coordenador", usuario="coord:c1", papel="coordenador")


class ClienteIntocavel:
    """O cliente que nenhuma chamada recusada pode tocar."""

    def table(self, *_args, **_kwargs):
        raise AssertionError("a chamada devia ter sido recusada antes de ler o banco")


def _ferramenta(nome, handler, escopo="coordenacao", propriedades=None, required=None, **extra):
    parametros = {"type": "object", "properties": propriedades or {}}
    if required:
        parametros["required"] = required
    return Ferramenta(
        nome=nome,
        descricao="Ferramenta de teste do registro único de ferramentas.",
        parametros=parametros,
        escopo=escopo,
        handler=handler,
        **extra,
    )


# ─── A sessão ─────────────────────────────────────────────────────────────


class TestSessao:
    def test_aluno_e_coordenacao_viram_sessao(self):
        aluno = sessao_do_token({"tipo": "aluno", "aluno_id": "a1", "nome": " Ana "})
        assert (aluno.escopo, aluno.usuario, aluno.aluno_id, aluno.nome) == (
            "aluno", "aluno:a1", "a1", "Ana",
        )
        coord = sessao_do_token({"tipo": "coordenador", "sub": "c1", "papel": "administrador"})
        assert (coord.escopo, coord.usuario, coord.papel) == (
            "coordenacao", "coord:c1", "administrador",
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"tipo": "cantina", "sub": "copa"},           # terceiro tipo de sessão
            {"tipo": "download_arquivo", "sub": "x"},     # token de capacidade
            {"tipo": None, "sub": "x"},
            {"sub": "x"},
            {"tipo": "coordenador"},                      # sem identidade
            {"tipo": "aluno"},                            # sem identidade
        ],
    )
    def test_o_que_nao_e_sessao_de_assistente_e_recusado(self, payload):
        with pytest.raises(SessaoRecusada):
            sessao_do_token(payload)

    def test_papel_desconhecido_cai_no_menos_poderoso(self):
        """Mesma regra de `auth.papel_da_sessao`: token velho não vira admin."""
        coord = sessao_do_token({"tipo": "coordenador", "sub": "c1", "papel": "superusuario"})
        assert coord.papel == "coordenador"


# ─── O catálogo do SAS ────────────────────────────────────────────────────


class TestCatalogoDoSAS:
    def test_os_dois_catalogos_sao_o_que_os_modulos_declaram(self):
        """O registro recolhe, não escolhe: cada escopo vê exatamente as tools
        dos módulos dele — e os roteiros entram como uma tool por escopo."""
        aluno = {f.nome for f in REGISTRO.catalogo("aluno")}
        coordenacao = {f.nome for f in REGISTRO.catalogo("coordenacao")}
        assert aluno == {
            schema["name"] for schema, _ in [*tools_aluno.TOOLS, *roteiros.TOOLS_ALUNO]
        }
        assert coordenacao == set(tools_coordenacao.HANDLERS) | {
            schema["name"] for schema, _ in roteiros.TOOLS_COORDENACAO
        }
        assert "roteiro_do_mentor" in aluno
        assert "roteiro_da_coordenacao" in coordenacao
        assert not aluno & coordenacao

    def test_nenhuma_tool_do_aluno_declara_identidade(self):
        """O `aluno_id` vem do token. Declarado no schema, o modelo o veria
        como algo que se pode escolher."""
        declaram = [
            f.nome for f in REGISTRO.catalogo("aluno") if "aluno_id" in f.propriedades
        ]
        assert not declaram

    def test_schema_e_assinatura_do_handler_concordam(self):
        """O schema é o que o modelo vê; a assinatura é o que quebra.

        Uma propriedade que o handler não aceita viraria `TypeError` em toda
        chamada que a usasse; um parâmetro obrigatório fora do schema faria a
        tool falhar sempre, porque o despacho descarta chave fora do schema.
        """
        erros = []
        for escopo in ("aluno", "coordenacao"):
            for f in REGISTRO.catalogo(escopo):
                aceitos, obrigatorios = parametros_do_handler(f.handler)
                injetados = {"aluno_id"} if escopo == "aluno" else set()
                props = set(f.propriedades)
                for p in props - aceitos:
                    erros.append(f"{f.nome}: o schema declara {p!r}, que o handler não aceita")
                for p in obrigatorios - injetados - props:
                    erros.append(f"{f.nome}: o handler exige {p!r}, que o schema não declara")
                for p in set((f.parametros or {}).get("required") or []) - props:
                    erros.append(f"{f.nome}: required {p!r} sem propriedade")
        assert not erros, "\n".join(erros)

    def test_tipo_do_schema_bate_com_a_anotacao_do_handler(self):
        """O despacho CONVERTE pelo tipo do schema (`10` vira `"10"` onde o
        schema diz `string`). Se o schema mentisse sobre o tipo, a conversão
        quebraria uma tool que hoje funciona — sem erro, só resposta errada."""
        import types
        import typing

        esperado = {
            "string": {str}, "integer": {int}, "number": {int, float},
            "boolean": {bool}, "array": {list},
        }

        def bases(anotacao):
            if typing.get_origin(anotacao) in (typing.Union, types.UnionType):
                return {typing.get_origin(a) or a for a in typing.get_args(anotacao)} - {type(None)}
            return {typing.get_origin(anotacao) or anotacao}

        erros = []
        for escopo in ("aluno", "coordenacao"):
            for f in REGISTRO.catalogo(escopo):
                dicas = typing.get_type_hints(f.handler)
                for campo, esquema in f.propriedades.items():
                    tipo, anotacao = (esquema or {}).get("type"), dicas.get(campo)
                    if tipo in esperado and anotacao is not None and not bases(anotacao) & esperado[tipo]:
                        erros.append(f"{f.nome}.{campo}: schema {tipo}, handler {anotacao}")
        assert not erros, "\n".join(erros)

    def test_toda_tool_do_aluno_se_explica(self):
        """A mesma higiene que test_chat_tools.py aplica à coordenação."""
        curtas = [f.nome for f in REGISTRO.catalogo("aluno") if len(f.descricao) < 40]
        assert not curtas, f"descrição curta demais: {curtas}"

    def test_nenhuma_tool_do_aluno_vai_ao_mcp(self):
        """QUAIS tools da coordenação vão ao MCP é política de quem as escreve
        (docs/43 §5.4); que nenhuma do aluno vai é invariante do registro."""
        assert not [f.nome for f in REGISTRO.catalogo("aluno") if f.expor_no_mcp]


# ─── Metadados por módulo ─────────────────────────────────────────────────


def _modulo(nome="tools_de_mentira", tools=None, metadados=None, **listas):
    """Um módulo de tools de mentira, no formato dos de verdade."""
    modulo = types.ModuleType(nome)
    modulo.TOOLS = tools if tools is not None else []
    for atributo, valor in listas.items():
        setattr(modulo, atributo, valor)
    if metadados is not None:
        modulo.METADADOS = metadados
    return modulo


def _tupla(nome, handler=None):
    schema = {
        "name": nome,
        "description": "Ferramenta de mentira para testar o METADADOS do módulo.",
        "parameters": {"type": "object", "properties": {}},
    }
    return schema, handler or (lambda cliente, **_: {"ok": True})


class TestMetadados:
    """O `METADADOS` opcional de cada módulo de tools (docs/43 §3)."""

    def test_sem_metadados_vale_o_padrao(self):
        [f] = ferramentas._ferramentas_do_modulo(
            _modulo(tools=[_tupla("t")]), ("TOOLS", "coordenacao")
        )
        assert (f.prazo_s, f.expor_no_mcp) == (PRAZO_PADRAO_S, False)

    def test_o_modulo_ajusta_prazo_e_mcp_de_uma_tool_so(self):
        modulo = _modulo(
            tools=[_tupla("lenta"), _tupla("outra")],
            metadados={"lenta": {"prazo_s": 12, "expor_no_mcp": True}},
        )
        lenta, outra = ferramentas._ferramentas_do_modulo(modulo, ("TOOLS", "coordenacao"))
        assert (lenta.prazo_s, lenta.expor_no_mcp) == (12.0, True)
        assert isinstance(lenta.prazo_s, float)
        assert (outra.prazo_s, outra.expor_no_mcp) == (PRAZO_PADRAO_S, False)

    def test_toda_chave_e_opcional(self):
        modulo = _modulo(tools=[_tupla("t")], metadados={"t": {}})
        [f] = ferramentas._ferramentas_do_modulo(modulo, ("TOOLS", "coordenacao"))
        assert (f.prazo_s, f.expor_no_mcp) == (PRAZO_PADRAO_S, False)

    @pytest.mark.parametrize(
        "metadados,trecho",
        [
            ({"t": {"prazo": 12}}, "chave desconhecida"),        # erro de digitação
            ({"t": {"expor_mcp": True}}, "chave desconhecida"),
            ({"t": {"somente_leitura": False}}, "chave desconhecida"),
            ({"sumiu": {"prazo_s": 5}}, "não está nas tools do módulo"),
            ({"t": {"prazo_s": "30"}}, "prazo_s"),
            ({"t": {"prazo_s": True}}, "prazo_s"),               # bool é int em Python
            ({"t": {"prazo_s": 0}}, "prazo_s"),
            ({"t": {"prazo_s": -1}}, "prazo_s"),
            ({"t": {"prazo_s": float("inf")}}, "prazo_s"),
            ({"t": {"prazo_s": 301}}, "prazo_s"),                # o nginx corta antes
            ({"t": {"expor_no_mcp": "sim"}}, "expor_no_mcp"),
            ({"t": True}, "tem de ser um dict"),
        ],
    )
    def test_o_que_nao_cabe_falha_fechado(self, metadados, trecho):
        modulo = _modulo(tools=[_tupla("t")], metadados=metadados)
        with pytest.raises(ValueError, match=trecho):
            ferramentas._ferramentas_do_modulo(modulo, ("TOOLS", "coordenacao"))

    def test_metadados_que_nao_e_dict_falha_fechado(self):
        modulo = _modulo(tools=[_tupla("t")], metadados=[("t", {"prazo_s": 5})])
        with pytest.raises(ValueError, match="dict por nome de tool"):
            ferramentas._ferramentas_do_modulo(modulo, ("TOOLS", "coordenacao"))

    def test_tool_do_aluno_nao_vai_ao_mcp(self):
        """O MCP é da coordenação (docs/43 §0): seria o dado de um menor numa IA
        de fora, sem o `aluno_id` do token para amarrá-lo a alguém."""
        modulo = _modulo(tools=[_tupla("minha")], metadados={"minha": {"expor_no_mcp": True}})
        with pytest.raises(ValueError, match="não vai ao MCP"):
            ferramentas._ferramentas_do_modulo(modulo, ("TOOLS", "aluno"))

    def test_no_aluno_o_prazo_vale(self):
        modulo = _modulo(tools=[_tupla("minha")], metadados={"minha": {"prazo_s": 20}})
        [f] = ferramentas._ferramentas_do_modulo(modulo, ("TOOLS", "aluno"))
        assert (f.escopo, f.prazo_s) == ("aluno", 20.0)

    def test_um_modulo_com_duas_listas_de_escopos_diferentes(self):
        """O caso de `roteiros.py`: o METADADOS vale para as duas listas, e o
        escopo de cada tool é o da lista de onde ela veio."""
        modulo = _modulo(
            TOOLS_ALUNO=[_tupla("do_aluno")],
            TOOLS_COORDENACAO=[_tupla("da_coordenacao")],
            metadados={"da_coordenacao": {"expor_no_mcp": True}, "do_aluno": {"prazo_s": 3}},
        )
        aluno, coord = ferramentas._ferramentas_do_modulo(
            modulo, ("TOOLS_ALUNO", "aluno"), ("TOOLS_COORDENACAO", "coordenacao")
        )
        assert (aluno.escopo, aluno.prazo_s, aluno.expor_no_mcp) == ("aluno", 3.0, False)
        assert (coord.escopo, coord.expor_no_mcp) == ("coordenacao", True)

    def test_o_registro_recusa_mcp_fora_da_coordenacao(self):
        """A mesma regra no Registro, para quem monta Ferramenta à mão."""
        with pytest.raises(ValueError, match="não pode ir ao MCP"):
            Registro([
                _ferramenta("x", lambda cliente, *, aluno_id: {}, escopo="aluno", expor_no_mcp=True)
            ])

    def test_montar_registro_le_o_metadados_de_cada_modulo(self, monkeypatch):
        """O caminho de verdade: `_montar_registro` passa por `tools._MODULOS`,
        por `tools_aluno` e por `roteiros`, cada um com o próprio METADADOS."""
        coord = _modulo("tools.de_mentira", tools=[_tupla("c1")], metadados={"c1": {"prazo_s": 7}})
        aluno = _modulo(
            "tools_aluno_de_mentira", tools=[_tupla("a1")], metadados={"a1": {"prazo_s": 9}}
        )
        monkeypatch.setattr(ferramentas, "_tools_coordenacao", types.SimpleNamespace(_MODULOS=(coord,)))
        monkeypatch.setattr(ferramentas, "_tools_aluno", aluno)

        registro = ferramentas._montar_registro()

        assert registro.obter(COORDENACAO, "c1").prazo_s == 7.0
        assert registro.obter(ALUNO, "a1").prazo_s == 9.0
        assert registro.obter(ALUNO, "roteiro_do_mentor") is not None
        assert registro.obter(COORDENACAO, "roteiro_da_coordenacao") is not None

    def test_metadados_errado_num_modulo_derruba_o_import(self, monkeypatch):
        coord = _modulo("tools.de_mentira", tools=[_tupla("c1")], metadados={"c2": {"prazo_s": 7}})
        monkeypatch.setattr(ferramentas, "_tools_coordenacao", types.SimpleNamespace(_MODULOS=(coord,)))
        with pytest.raises(ValueError, match=r"tools\.de_mentira\.METADADOS cita 'c2'"):
            ferramentas._montar_registro()

    def test_o_prazo_do_modulo_e_o_que_o_despacho_aplica(self):
        def lenta(cliente):
            time.sleep(0.5)
            return {"ok": True}

        modulo = _modulo(tools=[_tupla("lenta", lenta)], metadados={"lenta": {"prazo_s": 0.05}})
        registro = Registro(ferramentas._ferramentas_do_modulo(modulo, ("TOOLS", "coordenacao")))

        async def cenario():
            inicio = time.perf_counter()
            resultado = await registro.despachar_async(COORDENACAO, "lenta", None, {})
            return resultado, time.perf_counter() - inicio

        resultado, decorrido = asyncio.run(cenario())
        assert "passou de" in resultado["erro"]
        assert decorrido < 0.4


# ─── 1 · Escopo ───────────────────────────────────────────────────────────


class TestEscopo:
    def test_aluno_nao_alcanca_tool_de_coordenacao_nem_pelo_nome(self):
        """A barreira que importa: o catálogo do aluno nem lista
        `listar_alunos`, mas o modelo pode chamá-la pelo nome mesmo assim —
        por alucinação ou por injeção. O despacho tem de recusar sozinho."""
        resultado = REGISTRO.despachar(ALUNO, "listar_alunos", ClienteIntocavel(), {})
        assert resultado == {"erro": "tool 'listar_alunos' não existe"}

    def test_a_recusa_e_identica_a_de_um_nome_inventado(self):
        """Responder diferente já diria ao aluno que a tool existe."""
        fora_do_escopo = REGISTRO.despachar(ALUNO, "relatorio_aluno", ClienteIntocavel(), {})
        inventada = REGISTRO.despachar(ALUNO, "tool_que_nao_existe", ClienteIntocavel(), {})
        assert fora_do_escopo["erro"].replace("relatorio_aluno", "X") == inventada[
            "erro"
        ].replace("tool_que_nao_existe", "X")

    def test_coordenacao_nao_usa_tool_do_aluno(self):
        """Sem `aluno_id` na sessão, a tool do aluno não tem de quem ler."""
        resultado = REGISTRO.despachar(COORDENACAO, "minhas_notas", ClienteIntocavel(), {})
        assert "não existe" in resultado["erro"]

    def test_o_modelo_recebe_so_o_catalogo_do_escopo(self):
        nomes_aluno = {s["function"]["name"] for s in perfil_aluno(ALUNO).schemas}
        assert nomes_aluno == {f.nome for f in REGISTRO.catalogo("aluno")}
        nomes_coord = {s["function"]["name"] for s in perfil_coordenador(COORDENACAO).schemas}
        assert nomes_coord == {f.nome for f in REGISTRO.catalogo("coordenacao")}

    def test_perfil_nao_aceita_sessao_do_outro_escopo(self):
        with pytest.raises(ValueError):
            perfil_coordenador(ALUNO)
        with pytest.raises(ValueError):
            perfil_aluno(COORDENACAO)


# ─── 2 · Identidade ───────────────────────────────────────────────────────


class TestIdentidade:
    def test_aluno_id_do_argumento_e_trocado_pelo_do_token(self, caplog):
        recebidos = []

        def minhas_notas(cliente, *, aluno_id):
            recebidos.append(aluno_id)
            return {"ok": True}

        registro = Registro([_ferramenta("minhas_notas", minhas_notas, escopo="aluno")])
        caplog.set_level(logging.WARNING, logger="sas.chat.ferramentas")

        registro.despachar(ALUNO, "minhas_notas", None, {"aluno_id": "colega"})

        assert recebidos == ["a1"]
        assert any("identidade no argumento" in r.getMessage() for r in caplog.records), (
            "aluno_id num escopo que não o declara é sinal de alucinação ou de "
            "tentativa de ler outro aluno — precisa deixar rastro"
        )

    def test_na_coordenacao_aluno_id_e_argumento_legitimo(self):
        """No escopo coletivo, `aluno_id` escolhe QUEM olhar."""
        recebidos = []

        def obter_aluno(cliente, *, aluno_id):
            recebidos.append(aluno_id)
            return {"ok": True}

        registro = Registro([
            _ferramenta(
                "obter_aluno", obter_aluno,
                propriedades={"aluno_id": {"type": "string"}}, required=["aluno_id"],
            )
        ])
        registro.despachar(COORDENACAO, "obter_aluno", None, {"aluno_id": "a7"})
        assert recebidos == ["a7"]


# ─── 3 · Argumentos ───────────────────────────────────────────────────────


class TestArgumentos:
    def _registro(self, handler, propriedades, required=None):
        return Registro([_ferramenta("t", handler, propriedades=propriedades, required=required)])

    def test_chave_inventada_e_descartada_em_vez_de_quebrar(self):
        recebidos = []

        def t(cliente, *, nome):
            recebidos.append(nome)
            return {"ok": True}

        registro = self._registro(t, {"nome": {"type": "string"}})
        resultado = registro.despachar(COORDENACAO, "t", None, {"nome": "Ana", "inventada": 1})
        assert resultado == {"ok": True}
        assert recebidos == ["Ana"]

    def test_none_deixa_o_default_do_handler_valer(self):
        recebidos = []

        def t(cliente, *, limite=8):
            recebidos.append(limite)
            return {"ok": True}

        registro = self._registro(t, {"limite": {"type": "integer"}})
        registro.despachar(COORDENACAO, "t", None, {"limite": None})
        assert recebidos == [8]

    def test_obrigatorio_faltando_nao_chega_ao_handler(self):
        def t(cliente, *, simulado_id):
            raise AssertionError("não devia ter sido chamado")

        registro = self._registro(t, {"simulado_id": {"type": "string"}}, ["simulado_id"])
        resultado = registro.despachar(COORDENACAO, "t", None, {})
        assert resultado["erro"] == "argumentos inválidos para 't': falta simulado_id"

    def test_o_inequivoco_e_convertido(self):
        recebidos = {}

        def t(cliente, *, limite=None, nota=None, ativo=None, matricula=None):
            recebidos.update(limite=limite, nota=nota, ativo=ativo, matricula=matricula)
            return {"ok": True}

        registro = self._registro(t, {
            "limite": {"type": "integer"},
            "nota": {"type": "number"},
            "ativo": {"type": "boolean"},
            "matricula": {"type": "string"},
        })
        registro.despachar(
            COORDENACAO, "t", None,
            {"limite": "10", "nota": "4,5", "ativo": "true", "matricula": 2024001},
        )
        assert recebidos == {"limite": 10, "nota": 4.5, "ativo": True, "matricula": "2024001"}

    @pytest.mark.parametrize(
        "valor,mensagem",
        [
            ("dez", "'limite' deveria ser um número inteiro"),
            (True, "'limite' deveria ser um número inteiro"),   # bool é int em Python
            (2.5, "'limite' deveria ser um número inteiro"),
        ],
    )
    def test_tipo_errado_vira_erro_que_o_modelo_entende(self, valor, mensagem):
        def t(cliente, *, limite=8):
            raise AssertionError("não devia ter sido chamado")

        registro = self._registro(t, {"limite": {"type": "integer"}})
        resultado = registro.despachar(COORDENACAO, "t", None, {"limite": valor})
        assert resultado["erro"].endswith(mensagem)

    def test_enum_e_conferido_no_servidor(self):
        """O enum do schema é o que o modelo VÊ; quem garante é o despacho."""

        def t(cliente, *, zona=None):
            raise AssertionError("não devia ter sido chamado")

        registro = self._registro(t, {"zona": {"type": "string", "enum": ["top", "risco"]}})
        resultado = registro.despachar(COORDENACAO, "t", None, {"zona": "todas"})
        assert "'zona' deve ser um de: top, risco" in resultado["erro"]


# ─── 4 · Repetição ────────────────────────────────────────────────────────


class TestRepeticao:
    def _contador(self, devolve=None):
        chamadas = []

        def t(cliente, *, ciclo_id):
            chamadas.append(ciclo_id)
            return devolve if devolve is not None else {"ok": True}

        registro = Registro([
            _ferramenta("t", t, propriedades={"ciclo_id": {"type": "string"}}, required=["ciclo_id"])
        ])
        return registro, chamadas

    def test_a_mesma_consulta_roda_uma_vez_por_resposta(self):
        registro, chamadas = self._contador()
        volta = Volta()
        primeira = registro.despachar(COORDENACAO, "t", None, {"ciclo_id": "c6"}, volta=volta)
        segunda = registro.despachar(COORDENACAO, "t", None, {"ciclo_id": "c6"}, volta=volta)
        assert primeira == {"ok": True}
        assert "já foi feita nesta mesma resposta" in segunda["erro"]
        assert chamadas == ["c6"]

    def test_argumento_diferente_ou_resposta_nova_roda_de_novo(self):
        registro, chamadas = self._contador()
        volta = Volta()
        registro.despachar(COORDENACAO, "t", None, {"ciclo_id": "c6"}, volta=volta)
        registro.despachar(COORDENACAO, "t", None, {"ciclo_id": "c5"}, volta=volta)
        registro.despachar(COORDENACAO, "t", None, {"ciclo_id": "c6"}, volta=Volta())
        assert chamadas == ["c6", "c5", "c6"]

    def test_erro_de_dominio_nao_conta_como_consulta_feita(self):
        """Tentar de novo depois de um erro é legítimo — o disjuntor da
        Solomon só conta chamada que deu certo, pelo mesmo motivo."""
        registro, chamadas = self._contador(devolve={"erro": "sem notas"})
        volta = Volta()
        registro.despachar(COORDENACAO, "t", None, {"ciclo_id": "c6"}, volta=volta)
        registro.despachar(COORDENACAO, "t", None, {"ciclo_id": "c6"}, volta=volta)
        assert chamadas == ["c6", "c6"]

    def test_argumento_convertido_conta_como_o_mesmo(self):
        """`"10"` e `10` são a mesma consulta depois da conversão."""
        chamadas = []

        def t(cliente, *, limite=8):
            chamadas.append(limite)
            return {"ok": True}

        registro = Registro([_ferramenta("t", t, propriedades={"limite": {"type": "integer"}})])
        volta = Volta()
        registro.despachar(COORDENACAO, "t", None, {"limite": "10"}, volta=volta)
        registro.despachar(COORDENACAO, "t", None, {"limite": 10}, volta=volta)
        assert chamadas == [10]


# ─── 5 · Prazo ────────────────────────────────────────────────────────────


class TestPrazo:
    def test_tool_que_passa_do_prazo_e_abandonada(self):
        def lenta(cliente):
            time.sleep(0.5)
            return {"ok": True}

        registro = Registro([_ferramenta("lenta", lenta, prazo_s=0.05)])

        async def cenario():
            # O relógio fica DENTRO da corrotina: `asyncio.run` espera as
            # threads do executor terminarem ao fechar o loop, e mediria a
            # tool inteira em vez do prazo.
            inicio = time.perf_counter()
            resultado = await registro.despachar_async(COORDENACAO, "lenta", None, {})
            return resultado, time.perf_counter() - inicio

        resultado, decorrido = asyncio.run(cenario())
        assert "passou de" in resultado["erro"]
        assert decorrido < 0.4, f"o prazo não cortou: {decorrido:.2f}s"

    def test_tool_dentro_do_prazo_responde_normalmente(self):
        registro = Registro([_ferramenta("rapida", lambda cliente: {"ok": True})])
        resultado = asyncio.run(registro.despachar_async(COORDENACAO, "rapida", None, {}))
        assert resultado == {"ok": True}
        assert not isinstance(resultado, RespostaDePrazo)

    def test_consulta_abandonada_no_prazo_nao_conta_como_feita(self):
        """A thread que o prazo abandonou termina DEPOIS, com sucesso. Se ela
        registrasse a consulta na volta, a chamada idêntica seguinte ouviria
        "o resultado está acima" — um resultado que o modelo nunca viu, e que
        o convidava a dizer que não há dado, ou a inventar (revisão antecipada
        do motor, 25/10). Quem registra é quem ENTREGA o resultado."""
        chamadas = []

        def lenta(cliente, *, ciclo_id):
            chamadas.append(ciclo_id)
            if len(chamadas) == 1:
                time.sleep(0.3)
            return {"ciclo": ciclo_id}

        registro = Registro([
            _ferramenta(
                "lenta", lenta, propriedades={"ciclo_id": {"type": "string"}}, required=["ciclo_id"],
                prazo_s=0.05,
            )
        ])
        volta = Volta()
        args = {"ciclo_id": "c6"}

        async def cenario():
            primeira = await registro.despachar_async(COORDENACAO, "lenta", None, args, volta=volta)
            # Até a abandonada terminar de fato — era aí que ela registrava.
            await asyncio.wait_for(primeira.thread, timeout=2)
            segunda = await registro.despachar_async(COORDENACAO, "lenta", None, args, volta=volta)
            terceira = await registro.despachar_async(COORDENACAO, "lenta", None, args, volta=volta)
            return primeira, segunda, terceira

        primeira, segunda, terceira = asyncio.run(cenario())
        assert "passou de" in primeira["erro"]
        # Roda de novo, e este o modelo VÊ...
        assert segunda == {"ciclo": "c6"}
        # ...e é este que o "está acima" passa a apontar.
        assert "já foi feita" in terceira["erro"]
        assert chamadas == ["c6", "c6"]

    def test_a_resposta_de_prazo_diz_quando_a_thread_termina_de_fato(self):
        """`thread` é para quem emprestou recurso à chamada (o agente: o
        cliente extra e a vaga): resolve no fim da thread, não no prazo."""
        solta = threading.Event()

        def presa(cliente):
            solta.wait(2)
            return {"ok": True}

        registro = Registro([_ferramenta("presa", presa, prazo_s=0.05)])

        async def cenario():
            resposta = await registro.despachar_async(COORDENACAO, "presa", None, {})
            rodando_no_prazo = not resposta.thread.done()
            solta.set()
            await asyncio.wait_for(resposta.thread, timeout=2)
            return resposta, rodando_no_prazo

        resposta, rodando_no_prazo = asyncio.run(cenario())
        assert isinstance(resposta, RespostaDePrazo)
        assert rodando_no_prazo, "o Future resolveu no prazo, e não no fim da thread"
        # Para o JSON, o histórico e qualquer cópia, é um dict de erro como os
        # outros: o Future não viaja.
        assert json.loads(json.dumps(resposta)) == {"erro": resposta["erro"]}
        assert type(copy.deepcopy(resposta)) is dict
        assert copy.deepcopy(resposta) == resposta
        assert type(copy.copy(resposta)) is dict

    def test_no_async_a_consulta_entregue_conta_como_feita(self):
        chamadas = []

        def t(cliente, *, ciclo_id):
            chamadas.append(ciclo_id)
            return {"ok": True}

        registro = Registro([
            _ferramenta("t", t, propriedades={"ciclo_id": {"type": "string"}}, required=["ciclo_id"])
        ])
        volta = Volta()

        async def cenario():
            primeira = await registro.despachar_async(COORDENACAO, "t", None, {"ciclo_id": "c6"}, volta=volta)
            segunda = await registro.despachar_async(COORDENACAO, "t", None, {"ciclo_id": "c6"}, volta=volta)
            return primeira, segunda

        primeira, segunda = asyncio.run(cenario())
        assert primeira == {"ok": True}
        assert "já foi feita" in segunda["erro"]
        assert chamadas == ["c6"]


# ─── 6 · Erro ─────────────────────────────────────────────────────────────


class TestErro:
    def test_o_texto_da_excecao_nao_chega_ao_modelo(self, caplog):
        """O modelo repetiria o texto ao usuário — e texto de exceção carrega
        URL do PostgREST (docs/14 §5)."""

        def quebra(cliente):
            raise RuntimeError("http://postgrest:3000/nota?select=* senha=segredo")

        registro = Registro([_ferramenta("quebra", quebra)])
        caplog.set_level(logging.ERROR, logger="sas.chat.ferramentas")

        resultado = registro.despachar(COORDENACAO, "quebra", None, {})

        assert "postgrest" not in resultado["erro"]
        assert "segredo" not in resultado["erro"]
        assert "falhou do nosso lado" in resultado["erro"]
        falhas = [r for r in caplog.records if r.getMessage() == "ferramenta falhou"]
        assert falhas and falhas[0].exc_info, "o stack precisa ir para o log"

    def test_resultado_que_nao_e_dict_e_embrulhado(self):
        registro = Registro([_ferramenta("lista", lambda cliente: [1, 2])])
        assert registro.despachar(COORDENACAO, "lista", None, {}) == {"resultado": [1, 2]}


# ─── 7 · Tamanho ──────────────────────────────────────────────────────────


class TestTamanho:
    def test_resultado_pequeno_sai_como_sempre(self):
        resultado = {"total": 1, "alunos": [{"nome": "Ana Sá"}]}
        assert serializar_para_modelo(resultado) == json.dumps(resultado, ensure_ascii=False)

    def test_lista_grande_encolhe_mantendo_comeco_e_fim(self):
        resultado = {
            "total": 5000,
            "alunos": [{"id": f"A{i:04d}", "nome": "x" * 40} for i in range(5000)],
        }
        texto = serializar_para_modelo(resultado, limite=20_000)

        assert len(texto) <= 20_000
        dados = json.loads(texto)
        assert dados["total"] == 5000
        assert dados["alunos"][0]["id"] == "A0000", "o topo de um ranking fica"
        assert dados["alunos"][-1]["id"] == "A4999", "a ponta recente de uma série fica"
        assert dados["_compactado"]["itens_omitidos"]["alunos"] == 5000 - len(dados["alunos"])
        assert "Não afirme nada sobre os itens omitidos" in dados["_compactado"]["aviso"]

    def test_lista_aninhada_diz_o_caminho(self):
        resultado = {"materias": {"fisica": {"serie": [{"nota": i / 10} for i in range(4000)]}}}
        dados = json.loads(serializar_para_modelo(resultado, limite=8_000))
        assert "materias.fisica.serie" in dados["_compactado"]["itens_omitidos"]

    def test_texto_gigante_ainda_sai_json_valido(self):
        resultado = {"texto": 'aspas " e barras \\ ' * 20_000}
        texto = serializar_para_modelo(resultado, limite=10_000)
        assert len(texto) <= 10_000
        assert "inicio" in json.loads(texto)

    def test_o_original_nao_e_alterado(self):
        """Quem persiste o artefato lê o resultado CHEIO depois de serializar."""
        resultado = {"alunos": list(range(10_000))}
        antes = copy.deepcopy(resultado)
        serializar_para_modelo(resultado, limite=2_000)
        assert resultado == antes

    def test_data_esquecida_numa_tool_nao_derruba_a_volta(self):
        import datetime

        texto = serializar_para_modelo({"quando": datetime.date(2026, 10, 24)})
        assert json.loads(texto) == {"quando": "2026-10-24"}


# ─── 8 · Registro ─────────────────────────────────────────────────────────


class TestRegistroDaChamada:
    def test_toda_chamada_deixa_linha_com_desfecho_e_duracao(self, caplog):
        registro = Registro([_ferramenta("t", lambda cliente: {"ok": True})])
        caplog.set_level(logging.INFO, logger="sas.chat.ferramentas")

        registro.despachar(COORDENACAO, "t", None, {})
        registro.despachar(COORDENACAO, "nao_existe", None, {})

        linhas = [r for r in caplog.records if getattr(r, "desfecho", None)]
        assert [(r.ferramenta, r.desfecho) for r in linhas] == [("t", "ok"), ("nao_existe", "inexistente")]
        assert all(r.escopo == "coordenacao" and r.usuario == "coord:c1" for r in linhas)
        assert all(isinstance(r.duracao_ms, int) for r in linhas)

    def test_nome_repetido_entre_escopos_e_recusado(self):
        """O log, a auditoria e o MCP identificam a tool só pelo nome."""
        with pytest.raises(ValueError):
            Registro([
                _ferramenta("x", lambda cliente: {}),
                _ferramenta("x", lambda cliente, *, aluno_id: {}, escopo="aluno"),
            ])


# ─── Artefatos ────────────────────────────────────────────────────────────

BARRAS = {
    "tipo": "barras_corte",
    "titulo": "Régua Tio Leo",
    "payload": {"materias": [{"materia": "Química", "nota": 3.8, "corte": 4.0}]},
}


class TestArtefatos:
    """`artefatos_do_resultado` — a única leitura, no backend, de "que cartão
    esta tool anexou" (docs/43 §4.1, defeito 6)."""

    def test_o_catalogo_do_aluno_e_o_que_o_front_aceita(self):
        """O front espelha o catálogo em `chatStream.ts`; divergir é mostrar ao
        vivo um cartão que some ao recarregar (ou o contrário)."""
        import pathlib
        import re

        arquivo = (
            pathlib.Path(__file__).resolve().parents[2] / "web/src/dominio/chatStream.ts"
        )
        if not arquivo.exists():
            pytest.skip("sem o front ao lado (imagem só da API)")
        bloco = re.search(r"CATALOGO_DE_ARTEFATOS = \[(.*?)\] as const", arquivo.read_text(), re.S)
        assert bloco, "CATALOGO_DE_ARTEFATOS sumiu de chatStream.ts"
        do_front = set(re.findall(r"'([a-z_]+)'", bloco.group(1)))
        assert do_front == TIPOS_DE_ARTEFATO["aluno"]
        assert do_front == ferramentas._TIPOS_DO_CAMPO_GENERICO

    @pytest.mark.parametrize(
        "nome_tool,resultado,esperado",
        [
            (
                "gerar_grafico",
                {"tipo": "histograma", "titulo": "Distribuição — P22", "payload": {"contagens": [1, 2]}},
                {"tipo": "histograma", "titulo": "Distribuição — P22", "payload": {"contagens": [1, 2]}},
            ),
            (
                "gerar_grafico",
                {"tipo": "linha_temporal", "titulo": "Evolução", "payload": {"pontos": []}},
                {"tipo": "linha_temporal", "titulo": "Evolução", "payload": {"pontos": []}},
            ),
            (
                "navegar_para",
                {"tipo": "navegacao", "titulo": "Ana", "payload": {"rota": "/alunos/A1"}},
                {"tipo": "navegacao", "titulo": "Ana", "payload": {"rota": "/alunos/A1"}},
            ),
            (
                "exportar_csv",
                {"tipo": "csv", "titulo": "export", "nLinhas": 2, "conteudo": "a\n1\n2\n"},
                {"tipo": "csv", "titulo": "export", "payload": {"conteudo": "a\n1\n2\n", "nLinhas": 2}},
            ),
        ],
    )
    def test_as_formas_antigas_continuam_como_eram(self, nome_tool, resultado, esperado):
        assert artefatos_do_resultado(nome_tool, resultado, "coordenacao") == [esperado]

    @pytest.mark.parametrize("tipo_no_topo", ["fase_1", "histograma", "navegacao", "csv"])
    def test_tipo_no_topo_de_outra_tool_nao_vira_artefato(self, tipo_no_topo):
        """`meu_desempenho_em_simulado` devolve `tipo` = o tipo do SIMULADO."""
        resultado = {"id": "s1", "tipo": tipo_no_topo, "titulo": "x", "payload": {"a": 1}}
        assert artefatos_do_resultado("meu_desempenho_em_simulado", resultado, "aluno") == []
        assert artefatos_do_resultado("obter_simulado", resultado, "coordenacao") == []

    def test_o_campo_generico_vale_para_qualquer_tool(self):
        resultado = {"zona": "risco", "artefato": {**BARRAS, "sobra": "descartada"}}
        assert artefatos_do_resultado("minha_zona", resultado, "aluno") == [BARRAS]

    def test_titulo_ausente_vira_none(self):
        resultado = {"nota": 7.0, "artefato": {"tipo": "prova", "payload": {"simuladoId": "s1"}}}
        assert artefatos_do_resultado("meu_desempenho_em_simulado", resultado, "aluno") == [
            {"tipo": "prova", "titulo": None, "payload": {"simuladoId": "s1"}}
        ]

    def test_o_campo_generico_respeita_o_catalogo_do_escopo(self):
        """Cartão do aluno não é gravado na coordenação, e vice-versa."""
        assert artefatos_do_resultado("x", {"artefato": BARRAS}, "coordenacao") == []
        extrato = {"tipo": "extrato_xp", "payload": {"pontos": 10}}   # o XP é mock
        assert artefatos_do_resultado("x", {"artefato": extrato}, "aluno") == []
        histograma = {"tipo": "histograma", "payload": {"contagens": []}}
        assert len(artefatos_do_resultado("x", {"artefato": histograma}, "coordenacao")) == 1

    @pytest.mark.parametrize("tipo", ["navegacao", "csv"])
    def test_link_e_csv_so_nascem_da_tool_propria(self, tipo, caplog):
        """Pelo campo genérico, qualquer tool fabricaria um link — a rota tem
        de ser a que `navegar_para` monta no servidor (docs/31 §2.4)."""
        caplog.set_level(logging.WARNING, logger="sas.chat.ferramentas")
        anexado = {"tipo": tipo, "payload": {"rota": "https://fora.example"}}
        assert artefatos_do_resultado("x", {"artefato": anexado}, "coordenacao") == []
        assert any("artefato descartado" in r.getMessage() for r in caplog.records)

    @pytest.mark.parametrize(
        "anexado",
        [
            {"tipo": "barras_corte", "payload": [1, 2]},
            {"tipo": "barras_corte", "payload": None},
            {"tipo": "barras_corte"},
            {"tipo": "barras_corte", "payload": {}, "titulo": "x" * (LIMITE_DO_TITULO + 1)},
            {"tipo": "barras_corte", "payload": {}, "titulo": 42},
            {"tipo": None, "payload": {}},
            {"tipo": ["barras_corte"], "payload": {}},
            "barras_corte",
            ["barras_corte"],
        ],
    )
    def test_o_que_nao_cabe_e_descartado_com_aviso(self, anexado, caplog):
        caplog.set_level(logging.WARNING, logger="sas.chat.ferramentas")
        assert artefatos_do_resultado("minha_zona", {"artefato": anexado}, "aluno") == []
        avisos = [r for r in caplog.records if "artefato descartado" in r.getMessage()]
        assert avisos and avisos[0].ferramenta == "minha_zona"

    def test_titulo_no_limite_passa(self):
        anexado = {**BARRAS, "titulo": "x" * LIMITE_DO_TITULO}
        assert len(artefatos_do_resultado("minha_zona", {"artefato": anexado}, "aluno")) == 1

    def test_forma_antiga_tambem_passa_pelo_catalogo_do_escopo(self):
        """Defesa de sobra: o aluno não alcança `navegar_para` (invariante 1),
        e ainda assim o catálogo dele não aceitaria o link."""
        resultado = {"tipo": "navegacao", "titulo": "Ana", "payload": {"rota": "/alunos/A1"}}
        assert artefatos_do_resultado("navegar_para", resultado, "aluno") == []

    def test_sem_artefato_nao_e_descarte(self, caplog):
        caplog.set_level(logging.WARNING, logger="sas.chat.ferramentas")
        assert artefatos_do_resultado("minhas_notas", {"total": 0, "artefato": None}, "aluno") == []
        assert artefatos_do_resultado("minhas_notas", {"total": 0}, "aluno") == []
        assert not caplog.records

    @pytest.mark.parametrize("resultado", [{"erro": "sem nota", "artefato": BARRAS}, [BARRAS], None, "x"])
    def test_erro_ou_resultado_que_nao_e_dict_nao_tem_artefato(self, resultado):
        assert artefatos_do_resultado("minha_zona", resultado, "aluno") == []

    def test_o_aviso_nao_carrega_o_payload(self, caplog):
        """O payload pode ter dado do aluno; o log fica com tipo e motivo."""
        caplog.set_level(logging.WARNING, logger="sas.chat.ferramentas")
        anexado = {"tipo": "barras_corte", "payload": ["Ana Souza 3,8"]}
        artefatos_do_resultado("minha_zona", {"artefato": anexado}, "aluno")
        assert all("Ana Souza" not in r.getMessage() for r in caplog.records)


class TestArtefatoParaOModelo:
    """O payload é da tela: ao modelo vai só que o cartão existe."""

    def test_o_payload_vira_aviso_de_anexo(self):
        resultado = {"zona": "risco", "artefato": BARRAS}
        dados = json.loads(serializar_para_modelo(resultado))
        assert dados == {"zona": "risco", "artefato": {"tipo": "barras_corte", "anexado": True}}

    @pytest.mark.parametrize(
        "anexado,tipo",
        [
            ({"tipo": "extrato_xp", "payload": {}}, "extrato_xp"),
            ({"tipo": "barras_corte", "payload": [1]}, "barras_corte"),
            ({"tipo": "navegacao", "payload": {"rota": "/x"}}, "navegacao"),
            ("barras_corte", None),
        ],
    )
    def test_o_que_nao_seria_gravado_diz_que_nao_anexou(self, anexado, tipo):
        """Senão o modelo diria "veja o cartão abaixo" sem cartão nenhum."""
        dados = json.loads(serializar_para_modelo({"artefato": anexado}))
        assert dados["artefato"] == {"tipo": tipo, "anexado": False}

    def test_a_forma_antiga_vai_inteira(self):
        """Nela o payload É o resultado — é o que o modelo lia antes."""
        resultado = {"tipo": "histograma", "titulo": "P22", "payload": {"contagens": [1, 2]}}
        assert serializar_para_modelo(resultado) == json.dumps(resultado, ensure_ascii=False)

    def test_sem_artefato_nada_muda(self):
        resultado = {"total": 0, "artefato": None}
        assert serializar_para_modelo(resultado) == json.dumps(resultado, ensure_ascii=False)

    def test_o_original_continua_com_o_payload(self):
        """Quem grava o artefato (rotas.py) lê o resultado CHEIO depois."""
        resultado = {"zona": "risco", "artefato": copy.deepcopy(BARRAS)}
        serializar_para_modelo(resultado)
        assert resultado["artefato"] == BARRAS

    def test_a_troca_vale_tambem_quando_o_resultado_encolhe(self):
        resultado = {
            "artefato": {**BARRAS, "payload": {"materias": ["x" * 50] * 2000}},
            "notas": [{"nota": i} for i in range(5000)],
        }
        dados = json.loads(serializar_para_modelo(resultado, limite=8_000))
        assert dados["artefato"] == {"tipo": "barras_corte", "anexado": True}
        assert "_compactado" in dados

    def test_data_no_payload_nao_derruba(self):
        resultado = {"artefato": {"tipo": "prova", "payload": {"quando": datetime.date(2026, 10, 24)}}}
        assert json.loads(serializar_para_modelo(resultado))["artefato"]["anexado"] is True
