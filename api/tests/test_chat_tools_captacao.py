"""As tools da captação externa — gente de FORA do colégio (docs/41; docs/43 §5).

Tudo passa pelo REGISTRO de verdade, contra a escola sintética de
test_chat_tools_coordenacao.py: é o caminho do chat e do MCP. O que estes testes
travam é o que erraria calado:

  * a saída é o que a tela mostra: nem o texto livre do funil, onde um telefone
    anotado à mão apareceria, nem o bastidor da raspagem saem — e nem são
    PEDIDOS ao banco, que é o que torna a lista branca da 0076 verdadeira;
  * cada coluna que as tools citam (select, filtro e ordem) está na lista
    branca: sem isso a tool passa aqui e dá 42501 só no MCP;
  * as duas populações não se confundem: toda descrição diz que não são alunos;
  * a tela e a tool são a MESMA função (docs/43 §4.4), então os filtros, o
    público e os curingas valem para as duas.

A SQL das views e da função da 0068 se prova contra o Postgres, com
`scripts/verificar_papeis_do_mcp.py --ferramentas`, não aqui.

Dados 100% sintéticos.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_chat_tools_captacao.py -q
"""

from __future__ import annotations

import inspect
import json
import re
from typing import Any

import pytest

from app.captacao import consultas
from app.chat.ferramentas import REGISTRO
from app.chat.tools import captacao as tools
from app.mcp.catalogo import SO_COM_NOME_DO_ALUNO, Catalogo
from scripts.verificar_papeis_do_mcp import DIR_MIGRATIONS, lista_branca
from tests import fake_captacao as fake
from tests.test_chat_tools_coordenacao import ConsultaRica, Escola, _partes, chamar, nova_escola

TODAS = ("buscar_candidatos_externos", "buscar_candidatos_por_conquista", "perfil_do_candidato_externo", "provas_da_captacao")
COM_PESSOA = TODAS[:3]


@pytest.fixture
def escola() -> Escola:
    return nova_escola()


def _nomes(resultado: dict) -> list[str]:
    return [c["nomeNormalizado"] for c in resultado["candidatos"]]


# ─── A política ──────────────────────────────────────────────────────────


class TestPolitica:
    @pytest.mark.parametrize("nome", TODAS)
    def test_expostas_e_so_de_leitura(self, nome):
        f = next(f for f in REGISTRO.catalogo("coordenacao") if f.nome == nome)
        assert f.expor_no_mcp and f.somente_leitura

    def test_as_tres_com_pessoa_saem_com_o_pseudonimo_e_as_provas_ficam(self):
        assert set(COM_PESSOA) <= SO_COM_NOME_DO_ALUNO
        assert "provas_da_captacao" not in SO_COM_NOME_DO_ALUNO
        com_pseudonimo = set(Catalogo(REGISTRO, teto_de_linhas=50, com_nome_do_aluno=False).nomes())
        assert "provas_da_captacao" in com_pseudonimo
        assert not com_pseudonimo & set(COM_PESSOA)

    @pytest.mark.parametrize("nome", COM_PESSOA)
    def test_a_descricao_diz_que_nao_sao_alunos_e_que_ha_menores(self, nome):
        descricao = next(f.descricao for f in REGISTRO.catalogo("coordenacao") if f.nome == nome)
        assert "EXTERNOS" in descricao
        assert "NÃO são alunos do SAS" in descricao
        assert "menores de idade" in descricao
        assert "Quando usar:" in descricao

    def test_a_das_provas_tambem_diz(self):
        descricao = next(f.descricao for f in REGISTRO.catalogo("coordenacao") if f.nome == "provas_da_captacao")
        assert "não de alunos do SAS" in descricao
        assert "Quando usar:" in descricao

    @pytest.mark.parametrize("nome", COM_PESSOA)
    def test_toda_lista_de_pessoa_tem_limite(self, nome):
        f = next(f for f in REGISTRO.catalogo("coordenacao") if f.nome == nome)
        assert f.propriedades["limite"]["type"] == "integer"

    def test_nao_ha_pagina_nem_deslocamento(self):
        """De propósito: paginar devolveria a base inteira de gente de fora, uma
        chamada de cada vez. O modelo estreita o filtro (minimização, art. 6º, III)."""
        for nome in COM_PESSOA:
            f = next(f for f in REGISTRO.catalogo("coordenacao") if f.nome == nome)
            assert not {"pagina", "por_pagina", "deslocamento", "offset"} & set(f.propriedades)


# ─── A lista branca é o que as tools citam ───────────────────────────────


def _coluna(item: str) -> str:
    return item.split("::")[0].split(":")[-1].split("->")[0].strip()


def _citadas(consulta: ConsultaRica) -> set[str]:
    colunas = {_coluna(item) for item in _partes(consulta.colunas or "")}
    colunas |= {coluna for _, coluna, _ in consulta.filtros if coluna}
    return colunas | {coluna for coluna, _ in consulta._order}


class TestListaBranca:
    def _todas_as_chamadas(self, cliente) -> None:
        chamar(cliente, "buscar_candidatos_externos", nome="ana", uf="CE", status_captacao="novo", conquistas_min=1)
        chamar(cliente, "buscar_candidatos_por_conquista", provas=["OBF"], publicos=["medio"])
        chamar(cliente, "perfil_do_candidato_externo", nome_normalizado=fake.ANA)
        chamar(cliente, "provas_da_captacao")

    def test_toda_coluna_citada_esta_na_lista_branca(self, escola):
        """O fake não tem privilégio: sem esta conferência, coluna nova numa
        tool passaria aqui e voltaria 42501 só no MCP — ou, pior, viraria um
        GRANT feito às pressas numa coluna que não devia sair do SAS."""
        cliente = escola.cliente()
        self._todas_as_chamadas(cliente)
        branca = lista_branca(DIR_MIGRATIONS)
        consultas_feitas = cliente.consultas
        assert {c.tabela for c in consultas_feitas} == {
            "v_candidato_externo_por_nome", "prova_externa", "candidato_externo", "conquista_externa",
            "v_prova_externa_resumo",
        }
        for consulta in consultas_feitas:
            fora = _citadas(consulta) - branca[consulta.tabela]
            assert not fora, (consulta.tabela, fora)

    def test_a_tela_pede_o_que_a_ia_nao_pede(self):
        """A prova de que as colunas são de quem chama: a rota segue com o funil
        inteiro, e a lista branca só tem o que a tool pede."""
        branca = lista_branca(DIR_MIGRATIONS)
        assert "observacoes" in consultas.COLUNAS_CANDIDATO
        assert "observacoes" not in tools.COLUNAS_CANDIDATO
        assert "observacoes" not in branca["candidato_externo"]
        assert {"nome_informado", "raspado_em"} <= set(_partes(consultas.COLUNAS_CONQUISTA))
        assert not {"nome_informado", "raspado_em"} & set(_partes(tools.COLUNAS_CONQUISTA))
        assert not {"nome_informado", "raspado_em"} & branca["conquista_externa"]

    def test_nenhuma_le_as_views_de_fora(self, escola):
        cliente = escola.cliente()
        self._todas_as_chamadas(cliente)
        assert not [c for c in cliente.consultas if c.tabela == "v_candidato_externo"]

    def test_nao_escrevem(self, escola):
        cliente = escola.cliente()
        self._todas_as_chamadas(cliente)
        assert cliente.escritas == []
        assert [nome for nome, _ in cliente.rpcs] == ["buscar_candidatos_por_conquista"]


# ─── O que não sai ───────────────────────────────────────────────────────


class TestOQueNaoSai:
    def test_nem_o_funil_escrito_nem_o_bastidor(self, escola):
        cliente = escola.cliente()
        saidas = [
            chamar(cliente, "buscar_candidatos_externos"),
            chamar(cliente, "buscar_candidatos_por_conquista", ano_min=2020),
            chamar(cliente, "perfil_do_candidato_externo", nome_normalizado=fake.ANA),
            chamar(cliente, "provas_da_captacao"),
        ]
        texto = json.dumps(saidas, ensure_ascii=False)
        assert "99999" not in texto
        assert fake.OBSERVACAO_COM_TELEFONE not in texto
        assert fake.NOME_RASPADO not in texto
        for chave in ("observacoes", "nome_informado", "raspado_em", "retrato_editado_a_mao", "total_filtrado"):
            assert chave not in texto, chave


# ─── buscar_candidatos_externos ──────────────────────────────────────────


class TestBuscarCandidatosExternos:
    def test_um_nome_por_linha_de_quem_mais_cruzou_para_quem_menos(self, escola):
        r = chamar(escola.cliente(), "buscar_candidatos_externos")
        assert _nomes(r) == [fake.ANA, fake.BRUNO, fake.CAIO]
        ana = r["candidatos"][0]
        assert ana["conquistasTotal"] == 3
        assert ana["participacoes"] == 1
        assert ana["perfis"] == 2
        assert ana["ufs"] == ["CE", "SP"]
        assert (r["total"], r["mostrados"], r["truncado"]) == (3, 3, False)

    @pytest.mark.parametrize(
        ("filtro", "esperados"),
        [
            ({"uf": "ce"}, [fake.ANA, fake.CAIO]),
            ({"status_captacao": "interessado"}, [fake.ANA]),
            ({"conquistas_min": 3}, [fake.ANA]),
            ({"nome": "bruno"}, [fake.BRUNO]),
            ({"nome": "Brúno"}, [fake.BRUNO]),
        ],
    )
    def test_filtros_do_nome(self, escola, filtro, esperados):
        assert _nomes(chamar(escola.cliente(), "buscar_candidatos_externos", **filtro)) == esperados

    @pytest.mark.parametrize("curinga", ["%", "_", "%%", "__", "\\", "c_ndidat%", "c*o"])
    def test_curinga_e_letra(self, escola, curinga):
        """`nome='__'` listava a escola inteira em `buscar_aluno_por_nome` antes
        de `literal_no_like`: aqui, nada casa, porque nome não tem esses sinais."""
        r = chamar(escola.cliente(), "buscar_candidatos_externos", nome=curinga)
        assert r["total"] == 0

    def test_limite_e_truncado(self, escola):
        r = chamar(escola.cliente(), "buscar_candidatos_externos", limite=2)
        assert (r["total"], r["mostrados"], r["truncado"]) == (3, 2, True)

    def test_teto_do_handler(self, escola):
        cliente = escola.cliente()
        chamar(cliente, "buscar_candidatos_externos", limite=5000)
        assert cliente.em("v_candidato_externo_por_nome")[-1]._range == (0, tools.TETO_DE_CANDIDATOS - 1)

    def test_locais_cortados_dizem_quantos_faltam(self, escola):
        linha = escola.db["v_candidato_externo_por_nome"][fake.BRUNO]
        linha["escolas"] = [f"Escola {n}" for n in range(tools.LIMITE_DE_LOCAIS + 4)]
        r = chamar(escola.cliente(), "buscar_candidatos_externos", nome="bruno")
        candidato = r["candidatos"][0]
        assert len(candidato["escolas"]) == tools.LIMITE_DE_LOCAIS
        assert candidato["escolasAMais"] == 4
        assert "cidadesAMais" not in candidato

    def test_status_fora_do_vocabulario_o_registro_recusa(self, escola):
        assert "erro" in chamar(escola.cliente(), "buscar_candidatos_externos", status_captacao="inventado")

    def test_conquistas_min_invalido_vira_erro_que_o_modelo_le(self, escola):
        r = chamar(escola.cliente(), "buscar_candidatos_externos", conquistas_min=0)
        assert "conquistas_min" in r["erro"]


# ─── buscar_candidatos_por_conquista ─────────────────────────────────────


class TestBuscarPorConquista:
    def test_sem_criterio_de_conquista_manda_para_a_busca_por_nome(self, escola):
        cliente = escola.cliente()
        r = chamar(cliente, "buscar_candidatos_por_conquista", uf="CE")
        assert "buscar_candidatos_externos" in r["erro"]
        assert cliente.rpcs == []

    def test_devolve_as_evidencias_e_o_ano_de_ingresso(self, escola):
        r = chamar(escola.cliente(), "buscar_candidatos_por_conquista", provas=["OBF"], faixas=["ouro"],
                   publicos=["medio"], ano_ingresso=2027)
        assert r["anoIngresso"] == 2027
        # Os dois têm ouro e estarão no Médio em 2027 (9º ano em 2025 e 8º em
        # 2024): vem antes quem tem a melhor conquista mais recente (0068).
        assert _nomes(r) == [fake.ANA, fake.CAIO]
        ana = r["candidatos"][0]
        assert ana["conquistasCasadas"] == 1
        assert ana["evidencias"] == [{
            "prova": "OBF", "ano": 2025, "faixa": "ouro", "resultado": "MEDALHA DE OURO", "nivel": "9º ano",
        }]

    def test_todo_criterio_vale_para_a_mesma_conquista(self, escola):
        """Ana tem ouro na OBF de 2025 e prata na de 2024: 'ouro' e '2024' são
        duas conquistas diferentes, e ninguém pode entrar por elas (docs/41 §20)."""
        r = chamar(escola.cliente(), "buscar_candidatos_por_conquista", faixas=["ouro"], ano_min=2024, ano_max=2024)
        assert _nomes(r) == [fake.CAIO]

    def test_o_padrao_do_ano_de_ingresso_e_o_do_dominio(self, escola, monkeypatch):
        monkeypatch.setattr(consultas, "ano_ingresso_padrao", lambda: 2031)
        cliente = escola.cliente()
        r = chamar(cliente, "buscar_candidatos_por_conquista", publicos=["medio"])
        assert r["anoIngresso"] == 2031
        assert cliente.rpcs[0][1]["p_ano_ingresso"] == 2031

    def test_prova_sem_acento_nem_caixa_vira_o_nome_do_banco(self, escola):
        """A função compara o nome exato: sem isto, 'obf' voltaria vazio, e
        vazio pareceria 'ninguém ganhou'."""
        cliente = escola.cliente()
        r = chamar(cliente, "buscar_candidatos_por_conquista", provas=["obf", "escola  naval"])
        assert cliente.rpcs[0][1]["p_provas"] == ["OBF", "Escola Naval"]
        assert r["total"] == 2

    def test_prova_desconhecida_e_erro_com_as_que_existem(self, escola):
        cliente = escola.cliente()
        r = chamar(cliente, "buscar_candidatos_por_conquista", provas=["Inventada"])
        assert "Inventada" in r["erro"] and "OBMEP" in r["erro"]
        assert cliente.rpcs == []

    @pytest.mark.parametrize(
        "argumentos",
        [{"provas": [1, 2]}, {"provas": [""]}, {"faixas": ["platina"]}, {"publicos": ["superior"]},
         {"ano_min": 1000}, {"ano_max": 3000}, {"faixas": ["ouro"], "ano_ingresso": 1500}],
    )
    def test_filtro_torto_vira_erro_e_nao_chega_a_funcao(self, escola, argumentos):
        cliente = escola.cliente()
        r = chamar(cliente, "buscar_candidatos_por_conquista", **argumentos)
        assert "erro" in r
        assert cliente.rpcs == []

    def test_curinga_no_nome_e_letra_tambem_aqui(self, escola):
        cliente = escola.cliente()
        r = chamar(cliente, "buscar_candidatos_por_conquista", provas=["OBF"], nome="c_ndidat%")
        assert cliente.rpcs[0][1]["p_busca"] == "C\\_NDIDAT\\%"
        assert r["total"] == 0

    def test_o_teto_vai_para_a_funcao(self, escola):
        cliente = escola.cliente()
        chamar(cliente, "buscar_candidatos_por_conquista", ano_min=2020, limite=5000)
        assert cliente.rpcs[0][1]["p_limite"] == tools.TETO_DE_CANDIDATOS

    def test_o_total_nao_fica_nas_linhas(self, escola):
        r = chamar(escola.cliente(), "buscar_candidatos_por_conquista", ano_min=2020, limite=1)
        assert (r["total"], r["mostrados"], r["truncado"]) == (3, 1, True)
        assert "total_filtrado" not in r["candidatos"][0]


# ─── perfil_do_candidato_externo ─────────────────────────────────────────


class TestPerfil:
    def test_os_homonimos_cada_um_com_as_proprias_conquistas(self, escola):
        r = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado=fake.ANA)
        assert r["perfis"] == 2
        ana, homonima = r["candidatos"]
        assert [ana["id"], homonima["id"]] == [fake.PERFIL_ANA, fake.PERFIL_ANA_HOMONIMA]
        assert [c["ano"] for c in ana["conquistas"]] == [2025, 2024, 2023]
        assert ana["conquistasTotal"] == 3
        assert ana["provasDistintas"] == 2
        assert ana["anoMaisRecente"] == 2025
        assert ana["serieDeReferencia"] == {"min": 9, "max": 9, "ano": 2025}
        assert ana["status"] == "interessado"
        assert homonima["conquistasTotal"] == 1  # participação conta no perfil (docs/41 §20.2)
        assert homonima["conquistas"][0]["notasPorMateria"] == {"mat": 8.3, "fis": 7.5}

    def test_cada_conquista_diz_a_prova_a_faixa_e_a_fonte(self, escola):
        ana = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado=fake.ANA)["candidatos"][0]
        assert ana["conquistas"][0] == {
            "id": fake._id(22, 1), "prova": "OBF", "categoria": "olimpiada", "ano": 2025,
            "resultado": "MEDALHA DE OURO", "faixa": "ouro", "nivel": "9º ano",
            "escolaInformada": "Colégio Exemplo", "cidadeInformada": "Fortaleza", "ufInformada": "CE",
            "notasPorMateria": None, "fonte": "https://exemplo.invalid/resultado/1",
        }

    def test_nome_de_exibicao_tambem_acha(self, escola):
        r = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado="Candidata  Externa Ána")
        assert r["nomeNormalizado"] == fake.ANA

    def test_um_perfil_so(self, escola):
        r = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado=fake.ANA,
                   candidato_id=fake.PERFIL_ANA_HOMONIMA)
        assert [c["id"] for c in r["candidatos"]] == [fake.PERFIL_ANA_HOMONIMA]

    def test_perfil_de_outro_nome_e_erro(self, escola):
        r = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado=fake.ANA,
                   candidato_id=fake.PERFIL_BRUNO)
        assert "erro" in r

    @pytest.mark.parametrize(("filtro", "anos"), [({"ano": 2024}, [2024]), ({"prova": "obmep"}, [2023]), ({"prova": "ITA"}, [])])
    def test_filtros_da_ficha_de_leitura(self, escola, filtro, anos):
        r = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado=fake.ANA,
                   candidato_id=fake.PERFIL_ANA, **filtro)
        perfil = r["candidatos"][0]
        assert [c["ano"] for c in perfil["conquistas"]] == anos
        assert perfil["conquistasNoFiltro"] == len(anos)
        assert perfil["conquistasTotal"] == 3  # o resumo é do perfil, não do filtro

    def test_o_limite_corta_a_saida_e_nao_o_resumo(self, escola):
        r = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado=fake.ANA,
                   candidato_id=fake.PERFIL_ANA, limite=1)
        perfil = r["candidatos"][0]
        assert len(perfil["conquistas"]) == 1
        assert perfil["truncado"] is True
        assert perfil["conquistasTotal"] == 3

    def test_nome_inexistente_manda_para_a_busca(self, escola):
        r = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado="NINGUEM")
        assert "buscar_candidatos_externos" in r["erro"]

    def test_nome_vazio(self, escola):
        assert "erro" in chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado="   ")

    def test_perfil_sem_serie_nao_inventa(self, escola):
        r = chamar(escola.cliente(), "perfil_do_candidato_externo", nome_normalizado=fake.BRUNO)
        assert r["candidatos"][0]["serieDeReferencia"] is None


# ─── provas_da_captacao ──────────────────────────────────────────────────


def test_provas_na_ordem_do_rodape(escola):
    r = chamar(escola.cliente(), "provas_da_captacao")
    assert [p["nome"] for p in r["provas"]] == ["Escola Naval", "OBF", "OBMEP", "ITA"]
    assert r["provas"][1] == {
        "nome": "OBF", "categoria": "olimpiada", "anoMin": 2024, "anoMax": 2025, "conquistasTotal": 3,
    }


def test_provas_nao_tem_parametro_de_limite():
    """Catálogo fixo de 10 linhas, sem pessoa — como `listar_ciclos`."""
    assert not inspect.signature(tools.provas_da_captacao).parameters.keys() - {"cliente"}


# ─── A mesma função que a rota chama ─────────────────────────────────────


def test_a_emulacao_cita_o_que_a_funcao_cita():
    """A emulação da 0068 (tests/fake_captacao.py) só vale enquanto a função for
    a que ela imita: os parâmetros e a força das faixas, lidos da migration."""
    corpo = (DIR_MIGRATIONS / "0068_captacao_busca_por_conquista.sql").read_text(encoding="utf-8")
    assert set(re.findall(r"^\s+(p_\w+)\s", corpo[corpo.index("CREATE FUNCTION"):corpo.index("RETURNS TABLE")], re.M)) == {
        "p_provas", "p_faixas", "p_ano_min", "p_ano_max", "p_publicos", "p_ano_ingresso", "p_uf", "p_status",
        "p_conquistas_min", "p_busca", "p_limite", "p_deslocamento",
    }
    forca: dict[str, int] = {f: int(n) for f, n in re.findall(r"WHEN '(\w+)'\s+THEN (\d)", corpo)}
    assert forca == fake._FORCA


def test_a_tool_nao_traz_regra_propria():
    """O vocabulário é do domínio: a tool publica o mesmo que a rota recusa."""
    schema: dict[str, Any] = dict(tools._SCHEMA_POR_CONQUISTA)
    propriedades = schema["parameters"]["properties"]
    assert propriedades["publicos"]["items"]["enum"] == list(consultas.PUBLICOS)
    assert propriedades["status_captacao"]["enum"] == list(consultas.STATUS_CAPTACAO)
