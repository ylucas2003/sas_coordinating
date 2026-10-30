"""As tools da cantina (docs/43 §5, decisão de 30/10): o que a coordenação lê
nas telas, pelo registro de verdade, contra a escola sintética.

Quatro coisas importam aqui, e são as que um erro daria sem aviso:

  * a RESTRIÇÃO ALIMENTAR só sai por `restricoes_alimentares`. É dado de saúde
    de menor (LGPD art. 11): as outras seis não a devolvem nem a LEEM;
  * a CONTAGEM vem de duas fontes — a view nas rotas, as tabelas de base no MCP
    (`cantina_leitura`, cabeçalho) — e as duas têm de dar o mesmo número. A view
    é reconstruída aqui como a 0049 e a 0052 a definem, e o teste compara. No
    Postgres de verdade isso foi conferido também (docs/43 §5);
  * a LISTA BRANCA cobre o que as tools leem: o fake não tem privilégio
    nenhum, então `TestListaBranca` lê cada consulta gravada e confere coluna
    por coluna contra a 0071 + 0075. Sem isto, faltaria GRANT só em produção,
    como 42501, e o modelo ouviria "falhou do nosso lado";
  * a rota e a tool são a MESMA função: a rota da cantina não ganhou matrícula
    (não é dado do balcão), e a da coordenação não perdeu a restrição.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_chat_tools_cantina.py -q
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app import cantina_leitura as leitura
from app import cantina_relatorio
from app.banco.missao import FUSO_DA_ESCOLA
from app.chat.ferramentas import REGISTRO, Sessao
from app.chat.tools import cantina as tools
from app.routes import cantina as rotas
from scripts.verificar_papeis_do_mcp import lista_branca
from tests.esquema_das_migrations import esquema
from tests.test_cantina_retirada import _com_a_view
from tests.test_chat_tools_coordenacao import (
    MATRICULA,
    NOME,
    T1,
    A,
    B,
    C,
    D,
    E,
    F,
    _id,
    _partes,
    _tabela_do_embed,
    chamar,
    nova_escola,
)

COORDENACAO = Sessao(tipo="coordenador", usuario="coord:teste", papel="coordenador")

CANTINA, FOOD, FECHADA = _id(30, 1), _id(30, 2), _id(30, 3)
ALMOCO, JANTA, ALMOCO_FOOD = _id(31, 1), _id(31, 2), _id(31, 3)
RASCUNHO, FERIADO, ALMOCO_ANTIGO = _id(31, 4), _id(31, 5), _id(31, 6)
PROTEINA, GUARNICAO, B_JANTA = _id(32, 1), _id(32, 2), _id(32, 3)
FRANGO, OMELETE, ARROZ, FEIJAO, SOPA = (_id(33, n) for n in range(1, 6))

#: Texto que só existe na restrição: basta procurá-lo na resposta inteira.
SEM_LACTOSE = "SENTINELA-SAUDE sem lactose"
AMENDOIM = "SENTINELA-SAUDE alergia a amendoim"
SEIS_SEM_RESTRICAO = (
    "cantinas_e_regras", "calendario_da_cantina", "cardapio_da_cantina",
    "pedidos_da_refeicao", "custos_da_cantina", "direitos_a_refeicao",
)
TODAS = (*SEIS_SEM_RESTRICAO, "restricoes_alimentares")
#: Uma chamada que devolve dado, para cada tool.
CHAMADAS: dict[str, dict[str, Any]] = {
    "cantinas_e_regras": {},
    "calendario_da_cantina": {},
    "cardapio_da_cantina": {},
    "pedidos_da_refeicao": {"refeicao": "almoco"},
    "custos_da_cantina": {},
    "direitos_a_refeicao": {},
    "restricoes_alimentares": {},
}


def _hoje() -> date:
    return datetime.now(FUSO_DA_ESCOLA).date()


def semear_cantina(db: dict[str, dict]) -> None:
    """A cantina sobre os alunos da escola sintética: uma semana com os cinco
    estados, as duas portas e pedido sem preço. Aqui e em
    test_chat_exposicao_no_mcp.py, que roda as tools expostas contra ela.

    Os blocos carregam as opções dentro da linha porque é assim que o fake
    resolve embed de filho; `cardapio_opcao` existe também, porque o relatório
    a lê direto.
    """
    hoje = _hoje()
    futuro = f"{(hoje + timedelta(days=30)).isoformat()}T20:00:00+00:00"
    passado = f"{(hoje - timedelta(days=30)).isoformat()}T20:00:00+00:00"

    def regra(**resto) -> dict:
        return {
            "ativo": True, "prazo_padrao_dias_antes": 1, "prazo_padrao_hora": "20:00:00",
            "valor_almoco": 18.0, "valor_janta": None, "aceita_pedido_almoco": True,
            "aceita_pedido_janta": True, "aceita_presencial_almoco": True,
            "aceita_presencial_janta": False, "criado_em": passado, **resto,
        }

    db["cantina"] = {
        CANTINA: regra(id=CANTINA, nome="Cantina do Ari"),
        FOOD: regra(id=FOOD, nome="Food"),
        FECHADA: regra(id=FECHADA, nome="Antiga", ativo=False),
    }
    db["usuario_cantina"] = {
        "c1": {"id": "c1", "cantina_id": CANTINA, "email": "copa@escola.invalid", "nome": "COPA",
               "senha_hash": "pbkdf2_sha256$naoeparasair", "ativo": True},
    }

    def cardapio(cid, cantina, dia, refeicao, **resto) -> tuple[str, dict]:
        return cid, {
            "id": cid, "cantina_id": cantina, "data": dia.isoformat(), "refeicao": refeicao,
            "pedidos_ate": futuro, "publicado_em": passado, "sem_refeicao": False,
            "aceita_pedido": True, "aceita_presencial": True, "criado_por": "c1",
            "criado_em": passado, "atualizado_em": passado, **resto,
        }

    db["cardapio"] = dict([
        cardapio(ALMOCO, CANTINA, hoje, "almoco"),
        cardapio(JANTA, CANTINA, hoje, "janta", pedidos_ate=passado),
        cardapio(ALMOCO_FOOD, FOOD, hoje, "almoco"),
        cardapio(RASCUNHO, CANTINA, hoje + timedelta(days=1), "almoco", publicado_em=None),
        cardapio(FERIADO, CANTINA, hoje + timedelta(days=2), "almoco", sem_refeicao=True),
        cardapio(ALMOCO_ANTIGO, FECHADA, hoje, "almoco"),
    ])

    def opcao(oid, bloco, nome, ordem, **resto) -> dict:
        return {"id": oid, "bloco_id": bloco, "nome": nome, "ordem": ordem, "disponivel": True, **resto}

    # Fora de ordem de propósito: quem ordena é o domínio.
    opcoes_proteina = [opcao(OMELETE, PROTEINA, "Omelete", 2, disponivel=False),
                       opcao(FRANGO, PROTEINA, "Frango", 1)]
    opcoes_guarnicao = [opcao(FEIJAO, GUARNICAO, "Feijão", 2), opcao(ARROZ, GUARNICAO, "Arroz", 1)]
    opcoes_janta = [opcao(SOPA, B_JANTA, "Sopa", 1)]

    def bloco(bid, cid, nome, ordem, opcoes, **resto) -> tuple[str, dict]:
        return bid, {
            "id": bid, "cardapio_id": cid, "nome": nome, "ordem": ordem, "escolhas_minimas": 0,
            "escolhas_maximas": 1, "observacao": None, "cardapio_opcao": opcoes, **resto,
        }

    db["cardapio_bloco"] = dict([
        bloco(GUARNICAO, ALMOCO, "Guarnição", 2, opcoes_guarnicao, escolhas_maximas=2,
              observacao="  o feijão vem à parte  "),
        bloco(PROTEINA, ALMOCO, "Proteínas", 1, opcoes_proteina, escolhas_minimas=1),
        bloco(B_JANTA, JANTA, "Prato", 1, opcoes_janta),
    ])
    db["cardapio_opcao"] = {o["id"]: o for o in (*opcoes_proteina, *opcoes_guarnicao, *opcoes_janta)}

    def pedido(n, aluno, cid, modo="pedido", **resto) -> tuple[str, dict]:
        momento = db["cardapio"][cid]
        pid = _id(34, n)
        return pid, {
            "id": pid, "cardapio_id": cid, "aluno_id": aluno, "modo": modo, "criado_em": passado,
            "atualizado_em": passado, "retirado_em": None, "valor_cobrado": 18.0,
            "data": momento["data"], "refeicao": momento["refeicao"], **resto,
        }

    db["pedido_refeicao"] = dict([
        pedido(1, A, ALMOCO),
        pedido(2, B, ALMOCO, modo="presencial", retirado_em=passado, valor_cobrado=20.0),
        pedido(3, C, ALMOCO, modo="presencial"),
        pedido(4, D, JANTA, valor_cobrado=None),
        pedido(5, E, ALMOCO_FOOD),
    ])
    db["pedido_refeicao_item"] = {
        n: {"pedido_id": _id(34, p), "opcao_id": o}
        for n, (p, o) in enumerate(((1, FRANGO), (1, ARROZ), (1, FEIJAO), (4, SOPA)))
    }

    db["direito_refeicao_aluno"] = {
        n: {"aluno_id": a, "refeicao": r}
        for n, (a, r) in enumerate(((A, "almoco"), (A, "janta"), (B, "almoco"), (C, "almoco"), (D, "janta")))
    }
    db["aluno"][A]["restricao_alimentar"] = SEM_LACTOSE
    db["aluno"][B]["restricao_alimentar"] = "   "   # só espaço: não é restrição
    db["aluno"][D]["restricao_alimentar"] = AMENDOIM


@pytest.fixture
def escola():
    e = nova_escola()
    semear_cantina(e.db)
    return e


def _com_as_views(db: dict) -> dict:
    """As duas views como o Postgres as calcularia, a partir das tabelas."""
    _com_a_view(db)  # v_pedidos_por_cardapio, a agregação da 0052
    view = {}
    for bloco in db["cardapio_bloco"].values():
        for opcao in db["cardapio_opcao"].values():
            if opcao["bloco_id"] != bloco["id"]:
                continue
            view[opcao["id"]] = {
                "cardapio_id": bloco["cardapio_id"],
                "bloco_id": bloco["id"],
                "bloco": bloco["nome"],
                "bloco_ordem": bloco["ordem"],
                "opcao_id": opcao["id"],
                "opcao": opcao["nome"],
                "opcao_ordem": opcao["ordem"],
                "disponivel": opcao["disponivel"],
                # O LEFT JOIN da 0049: sem item, 0.
                "quantos": sum(
                    1 for i in db["pedido_refeicao_item"].values() if i["opcao_id"] == opcao["id"]
                ),
            }
    db["v_contagem_pedidos_por_opcao"] = view
    return db


def _texto(resultado: Any) -> str:
    return json.dumps(resultado, ensure_ascii=False, default=str)


# ─── A restrição alimentar ───────────────────────────────────────────────


class TestRestricaoAlimentar:
    @pytest.mark.parametrize("nome", SEIS_SEM_RESTRICAO)
    def test_as_outras_seis_nao_devolvem_nem_leem(self, escola, nome):
        cliente = escola.cliente()
        resultado = chamar(cliente, nome, **CHAMADAS[nome])
        assert "erro" not in resultado, resultado
        texto = _texto(resultado)
        assert "SENTINELA-SAUDE" not in texto
        assert "restricao" not in texto.casefold()
        # O que não é lido não vaza por um campo novo escrito às pressas.
        assert not [c.colunas for c in cliente.consultas if "restricao_alimentar" in c.colunas]

    def test_a_sua_tool_devolve_quem_tem_e_o_texto(self, escola):
        r = chamar(escola.cliente(), "restricoes_alimentares")
        assert r["total"] == 2
        assert {a["alunoId"]: a["restricaoAlimentar"] for a in r["alunos"]} == {A: SEM_LACTOSE, D: AMENDOIM}
        por_id = {a["alunoId"]: a for a in r["alunos"]}
        assert por_id[A]["matricula"] == MATRICULA[A] and por_id[A]["nome"] == NOME[A]
        assert por_id[A]["direitos"] == ["almoco", "janta"]
        assert "LGPD" in r["cuidado"]

    def test_so_espaco_nao_e_restricao(self, escola):
        r = chamar(escola.cliente(), "restricoes_alimentares", aluno_id=B)
        assert r["total"] == 0 and r["alunos"] == []

    def test_o_recorte_por_aluno(self, escola):
        r = chamar(escola.cliente(), "restricoes_alimentares", aluno_id=D)
        assert [a["alunoId"] for a in r["alunos"]] == [D]

    def test_o_recorte_por_refeicao_e_de_quem_vai_comer(self, escola):
        hoje = _hoje().isoformat()
        r = chamar(escola.cliente(), "restricoes_alimentares", data=hoje, refeicao="janta")
        assert [a["alunoId"] for a in r["alunos"]] == [D]
        r = chamar(escola.cliente(), "restricoes_alimentares", data=hoje, refeicao="almoco")
        assert [a["alunoId"] for a in r["alunos"]] == [A]

    def test_aluno_inativo_nao_sai(self, escola):
        """É a lista da tela de direitos: só os ativos."""
        escola.db["aluno"][D]["ativo"] = False
        assert D not in {a["alunoId"] for a in chamar(escola.cliente(), "restricoes_alimentares")["alunos"]}

    @pytest.mark.parametrize("args", [{"data": "2026-11-03"}, {"refeicao": "almoco"}])
    def test_data_e_refeicao_vem_juntas(self, escola, args):
        cliente = escola.cliente()
        assert "juntas" in chamar(cliente, "restricoes_alimentares", **args)["erro"]
        assert cliente.consultas == []

    def test_id_e_data_tortos_sao_erro_de_argumento(self, escola):
        assert "UUID" in chamar(escola.cliente(), "restricoes_alimentares", aluno_id="Ana")["erro"]
        r = chamar(escola.cliente(), "restricoes_alimentares", data="ontem", refeicao="almoco")
        assert "AAAA-MM-DD" in r["erro"]

    def test_o_limite_corta_a_lista_e_nao_o_total(self, escola):
        r = chamar(escola.cliente(), "restricoes_alimentares", limite=1)
        assert len(r["alunos"]) == 1 and r["total"] == 2 and r["truncado"] is True

    def test_a_descricao_avisa_que_e_sensivel_e_quando_usar(self):
        descricao = REGISTRO.obter(COORDENACAO, "restricoes_alimentares").descricao
        assert descricao.startswith("⚠️ Dado SENSÍVEL")
        assert "LGPD art. 11" in descricao and "SÓ quando a pergunta for sobre" in descricao

    def test_a_linha_propria_no_metadados_desliga_so_ela(self):
        """É a razão de ela ser uma tool: desligar não tira a cantina do ar."""
        import dataclasses

        from app.chat.ferramentas import Registro
        from app.mcp.catalogo import ferramentas_expostas

        assert tools.METADADOS["restricoes_alimentares"] == {"expor_no_mcp": True}
        ajustadas = [
            dataclasses.replace(f, expor_no_mcp=False) if f.nome == "restricoes_alimentares" else f
            for f in REGISTRO.catalogo("coordenacao")
        ]
        sobram = {f.nome for f in ferramentas_expostas(Registro(ajustadas))}
        assert "restricoes_alimentares" not in sobram
        assert set(SEIS_SEM_RESTRICAO) <= sobram


# ─── A contagem: duas fontes, um número ──────────────────────────────────


class TestAContagemEUmaSo:
    def test_o_calendario_da_view_e_o_das_tabelas_sao_iguais(self, escola):
        """A rota lê a view, o MCP as tabelas. Divergir aqui é a IA dizer 41 e
        a tela 42 para o mesmo almoço."""
        _com_as_views(escola.db)
        hoje = _hoje()
        janela = (hoje, hoje + timedelta(days=6))
        ids = [CANTINA, FOOD, FECHADA]
        pela_view = leitura.calendario(escola.cliente(), ids, *janela, contar=leitura.contar_pela_view)
        pelas_tabelas = leitura.calendario(escola.cliente(), ids, *janela, contar=leitura.contar_pelos_pedidos)
        assert pela_view == pelas_tabelas
        assert {c["id"]: c["pedidos"] for c in pela_view}[ALMOCO] == 3

    def test_a_contagem_por_opcao_da_view_e_a_dos_itens_sao_iguais(self, escola):
        _com_as_views(escola.db)
        cliente = escola.cliente()
        for cardapio in (ALMOCO, JANTA, ALMOCO_FOOD, RASCUNHO):
            blocos = leitura.blocos_por_cardapio(cliente, [cardapio]).get(cardapio, [])
            assert leitura.contagem_por_opcao_pelos_itens(
                cliente, cardapio, blocos
            ) == leitura.contagem_por_opcao_pela_view(cliente, cardapio)

    def test_cardapio_sem_pedido_vem_com_os_tres_zeros(self, escola):
        """O LEFT JOIN da 0052: dia sem pedido aparece com 0 em vez de sumir."""
        contagem = leitura.contar_pelos_pedidos(escola.cliente(), [RASCUNHO])
        assert contagem == {RASCUNHO: {"cardapio_id": RASCUNHO, "quantos": 0, "com_pedido": 0, "presenciais": 0}}

    def test_modo_ausente_conta_como_pedido(self):
        """O DEFAULT da 0051, como `_com_a_view` e a lista do balcão o leem."""
        assert leitura.contar_modos([None, "pedido", "presencial"]) == {
            "quantos": 3, "com_pedido": 2, "presenciais": 1,
        }

    @pytest.mark.parametrize("nome", TODAS)
    def test_nenhuma_tool_le_view(self, escola, nome):
        """O GRANT numa view exporia tudo o que ela lê, com o privilégio do dono
        (0071): sob o sas_mcp, ler uma daria 42501."""
        cliente = escola.cliente()
        chamar(cliente, nome, **CHAMADAS[nome])
        assert not [c.tabela for c in cliente.consultas if c.tabela in esquema().views]


# ─── A lista branca cobre o que as tools leem ────────────────────────────

#: A relação de cada embed: (coluna da tabela de fora, coluna da de dentro). O
#: PostgREST monta o join com elas, e o Postgres exige SELECT nas duas.
_JOINS = {
    ("pedido_refeicao", "aluno"): ("aluno_id", "id"),
    ("matricula_turma", "turma"): ("turma_id", "id"),
    ("cardapio_bloco", "cardapio_opcao"): ("id", "bloco_id"),
}


def _colunas_do_select(tabela: str, selecao: str) -> set[tuple[str, str]]:
    pedidas: set[tuple[str, str]] = set()
    for item in _partes(selecao):
        assert item not in ("", "*"), f"select=* em {tabela}: com GRANT por coluna dá 42501"
        if "(" in item:
            cabeca, resto = item.split("(", 1)
            filha = _tabela_do_embed(tabela, cabeca)
            de_fora, de_dentro = _JOINS[(tabela, filha)]
            pedidas |= {(tabela, de_fora), (filha, de_dentro)}
            pedidas |= _colunas_do_select(filha, resto[: resto.rfind(")")])
        else:
            pedidas.add((tabela, item.strip()))
    return pedidas


def _o_que_a_tool_le(cliente) -> set[tuple[str, str]]:
    lidas: set[tuple[str, str]] = set()
    for consulta in cliente.consultas:
        lidas |= _colunas_do_select(consulta.tabela, consulta.colunas)
        lidas |= {(consulta.tabela, coluna) for _, coluna, _ in consulta.filtros if coluna}
        lidas |= {(consulta.tabela, coluna) for coluna, _ in consulta._order}
    return lidas


class TestListaBranca:
    @pytest.mark.parametrize("nome", TODAS)
    def test_toda_coluna_lida_esta_na_lista_branca(self, escola, nome):
        branca = lista_branca()
        cliente = escola.cliente()
        assert "erro" not in chamar(cliente, nome, **CHAMADAS[nome])
        lidas = _o_que_a_tool_le(cliente)
        assert lidas, nome
        fora = sorted(par for par in lidas if par[1] not in (branca.get(par[0]) or ()))
        assert fora == [], f"{nome} leria com 42501 sob o sas_mcp: {fora}"

    def test_toda_coluna_da_0075_e_lida_por_alguma_tool(self, escola):
        """O outro lado de "nem mais": GRANT que nenhuma tool usa é dado saindo
        à toa. `cantina` e `aluno` entram: o que a 0075 deu nelas tem de ter
        leitor também."""
        lidas: set[tuple[str, str]] = set()
        cliente = escola.cliente()
        for nome, args in {
            **CHAMADAS,
            "restricoes_alimentares": {"data": _hoje().isoformat(), "refeicao": "almoco"},
        }.items():
            chamar(cliente, nome, **args)
        lidas = _o_que_a_tool_le(cliente)
        branca = lista_branca()
        for tabela in (
            "cantina", "cardapio", "cardapio_bloco", "cardapio_opcao", "direito_refeicao_aluno",
            "pedido_refeicao", "pedido_refeicao_item",
        ):
            sobra = sorted(c for c in branca[tabela] if (tabela, c) not in lidas)
            assert sobra == [], f"{tabela}: GRANT sem leitor: {sobra}"
        assert ("aluno", "restricao_alimentar") in lidas

    def test_a_conta_da_cantina_nao_e_lida_por_ninguem(self, escola):
        cliente = escola.cliente()
        for nome in TODAS:
            chamar(cliente, nome, **CHAMADAS[nome])
        assert cliente.em("usuario_cantina") == []


# ─── Cada tool ───────────────────────────────────────────────────────────


class TestCantinasERegras:
    def test_a_regra_da_casa_sem_as_contas(self, escola):
        cliente = escola.cliente()
        r = chamar(cliente, "cantinas_e_regras")
        assert [c["nome"] for c in r["cantinas"]] == ["Antiga", "Cantina do Ari", "Food"]
        ari = r["cantinas"][1]
        assert ari["id"] == CANTINA and ari["ativa"] is True
        assert ari["prazoPadrao"] == {"diasAntes": 1, "hora": "20:00"}
        assert ari["valorAlmoco"] == 18.0 and ari["valorJanta"] is None
        assert ari["modosDaCasa"]["almoco"] == {"aceitaPedido": True, "aceitaPresencial": True}
        assert ari["modosDaCasa"]["janta"] == {"aceitaPedido": True, "aceitaPresencial": False}
        texto = _texto(r)
        assert "copa@escola.invalid" not in texto and "naoeparasair" not in texto
        assert "contas" not in texto

    def test_o_limite(self, escola):
        r = chamar(escola.cliente(), "cantinas_e_regras", limite=1)
        assert len(r["cantinas"]) == 1 and r["total"] == 3 and r["truncado"] is True


class TestCalendario:
    def test_os_estados_e_as_portas(self, escola):
        r = chamar(escola.cliente(), "calendario_da_cantina", cantina_id=CANTINA)
        por_id = {c["cardapioId"]: c for c in r["cardapios"]}
        assert por_id[ALMOCO]["estado"] == "aberto"
        assert por_id[JANTA]["estado"] == "fechado"
        assert por_id[RASCUNHO]["estado"] == "rascunho"
        assert por_id[FERIADO]["estado"] == "sem-refeicao"
        almoco = por_id[ALMOCO]
        assert (almoco["pedidos"], almoco["comPedido"], almoco["presenciais"]) == (3, 1, 2)
        assert almoco["cantina"] == "Cantina do Ari"
        assert por_id[RASCUNHO]["pedidos"] == 0

    def test_sem_cantina_sao_as_ativas(self, escola):
        r = chamar(escola.cliente(), "calendario_da_cantina")
        assert {c["cantina"] for c in r["cardapios"]} == {"Cantina do Ari", "Food"}

    def test_a_cantina_pedida_vale_mesmo_inativa(self, escola):
        r = chamar(escola.cliente(), "calendario_da_cantina", cantina_id=FECHADA)
        assert [c["cardapioId"] for c in r["cardapios"]] == [ALMOCO_ANTIGO]

    def test_a_janela_padrao_e_de_uma_semana(self, escola):
        r = chamar(escola.cliente(), "calendario_da_cantina")
        hoje = _hoje()
        assert (r["de"], r["ate"]) == (hoje.isoformat(), (hoje + timedelta(days=6)).isoformat())

    @pytest.mark.parametrize(("args", "trecho"), [
        ({"de": "amanhã"}, "AAAA-MM-DD"),
        ({"de": "2026-11-10", "ate": "2026-11-01"}, "antes de de"),
        ({"de": "2026-01-01", "ate": "2026-03-01"}, f"até {tools.TETO_DE_DIAS_DO_CALENDARIO} dias"),
        ({"cantina_id": "a do Ari"}, "UUID"),
        ({"cantina_id": _id(30, 99)}, "não existe"),
    ])
    def test_argumento_torto_e_erro_que_o_modelo_le(self, escola, args, trecho):
        assert trecho in chamar(escola.cliente(), "calendario_da_cantina", **args)["erro"]

    def test_o_limite_corta_a_lista_e_nao_o_total(self, escola):
        r = chamar(escola.cliente(), "calendario_da_cantina", limite=2)
        assert len(r["cardapios"]) == 2 and r["total"] == 5 and r["truncado"] is True


class TestCardapio:
    def test_o_prato_na_ordem_da_bandeja(self, escola):
        r = chamar(escola.cliente(), "cardapio_da_cantina", refeicao="almoco", cantina_id=CANTINA)
        assert r["total"] == 1
        c = r["cardapios"][0]
        assert (c["cardapioId"], c["estado"], c["aceitaPresencial"]) == (ALMOCO, "aberto", True)
        proteinas, guarnicao = c["blocos"]
        assert proteinas["bloco"] == "Proteínas" and proteinas["escolhasMinimas"] == 1
        assert [o["opcao"] for o in proteinas["opcoes"]] == ["Frango", "Omelete"]
        assert [o["disponivel"] for o in proteinas["opcoes"]] == [True, False]
        assert guarnicao["escolhasMaximas"] == 2 and guarnicao["observacao"] == "o feijão vem à parte"

    def test_a_semana(self, escola):
        hoje = _hoje()
        r = chamar(
            escola.cliente(), "cardapio_da_cantina", data=hoje.isoformat(),
            ate=(hoje + timedelta(days=6)).isoformat(), cantina_id=CANTINA,
        )
        assert [c["cardapioId"] for c in r["cardapios"]] == [ALMOCO, JANTA, RASCUNHO, FERIADO]

    def test_nao_traz_contagem_nem_gente(self, escola):
        texto = _texto(chamar(escola.cliente(), "cardapio_da_cantina"))
        assert "quantos" not in texto and NOME[A] not in texto

    def test_a_janela_tem_teto_e_o_erro_cita_o_parametro_certo(self, escola):
        r = chamar(escola.cliente(), "cardapio_da_cantina", data="2026-11-01", ate="2026-11-20")
        assert f"até {tools.TETO_DE_DIAS_DO_CARDAPIO} dias" in r["erro"]
        r = chamar(escola.cliente(), "cardapio_da_cantina", data="2026-11-10", ate="2026-11-01")
        assert "antes de data" in r["erro"]


class TestPedidosDaRefeicao:
    def _almoco(self, escola, **args) -> dict:
        r = chamar(escola.cliente(), "pedidos_da_refeicao", refeicao="almoco", cantina_id=CANTINA, **args)
        assert len(r["cardapios"]) == 1
        return r["cardapios"][0]

    def test_o_que_cozinhar(self, escola):
        c = self._almoco(escola)
        assert (c["pedidos"], c["comPedido"], c["presenciais"]) == (3, 1, 2)
        assert c["presencial"] == {"pendentes": 1, "retirados": 1}
        quantos = {x["opcao"]: x["quantos"] for x in c["contagem"]}
        # A opção que ninguém pediu aparece com 0, e quem retira na hora não
        # entra: a soma não bate com `pedidos`, e é assim mesmo (docs/40 §10.1).
        assert quantos == {"Frango": 1, "Omelete": 0, "Arroz": 1, "Feijão": 1}
        assert next(x for x in c["contagem"] if x["opcao"] == "Omelete")["disponivel"] is False

    def test_quem_vai_comer_com_a_identidade_ao_lado_do_nome(self, escola):
        c = self._almoco(escola)
        assert c["totalDeAlunos"] == 3 and c["truncado"] is False
        por_id = {a["alunoId"]: a for a in c["alunos"]}
        assert set(por_id) == {A, B, C}
        ana = por_id[A]
        assert (ana["nome"], ana["matricula"]) == (NOME[A], MATRICULA[A])
        assert ana["turma"] == "3o ITA AD"
        assert ana["modo"] == "pedido" and ana["escolhas"] == ["Arroz", "Feijão", "Frango"]
        assert por_id[B]["modo"] == "presencial" and por_id[B]["escolhas"] == []
        assert por_id[B]["retiradoEm"] and por_id[C]["retiradoEm"] is None

    def test_o_limite_corta_os_nomes_e_nao_a_contagem(self, escola):
        c = self._almoco(escola, limite=1)
        assert len(c["alunos"]) == 1 and c["totalDeAlunos"] == 3 and c["truncado"] is True
        assert (c["pedidos"], c["comPedido"], c["presenciais"]) == (3, 1, 2)

    def test_sem_cantina_vem_cada_uma_das_ativas(self, escola):
        r = chamar(escola.cliente(), "pedidos_da_refeicao", refeicao="almoco")
        assert [c["cantina"] for c in r["cardapios"]] == ["Cantina do Ari", "Food"]

    def test_dia_sem_cardapio_avisa_em_vez_de_dizer_que_ninguem_pediu(self, escola):
        r = chamar(escola.cliente(), "pedidos_da_refeicao", refeicao="janta", data="2020-01-06")
        assert r["cardapios"] == [] and "Nenhuma cantina lançou" in r["aviso"]

    def test_refeicao_inventada_e_recusada_pelo_registro(self, escola):
        assert "deve ser um de" in chamar(escola.cliente(), "pedidos_da_refeicao", refeicao="cafe")["erro"]


class TestCustos:
    def test_os_mesmos_numeros_da_tela(self, escola):
        hoje = _hoje()
        de, ate = hoje.replace(day=1), tools._fim_do_mes(hoje)
        r = chamar(escola.cliente(), "custos_da_cantina", de=de.isoformat(), ate=ate.isoformat(), limite=100)
        tela = cantina_relatorio.agregados(escola.cliente(), de=de, ate=ate)
        for campo in ("de", "ate", "refeicoes", "total", "semValor"):
            assert r[campo] == tela[campo], campo
        assert r["porDia"] == tela["porDia"]
        for recorte in ("porTurma", "porAluno", "porCantina"):
            assert sorted(map(_texto, r[recorte])) == sorted(map(_texto, tela[recorte])), recorte

    def test_soma_o_preco_carimbado_e_conta_quem_ficou_sem(self, escola):
        r = chamar(escola.cliente(), "custos_da_cantina", cantina_id=CANTINA)
        # 18 + 20 + 18: o carimbo de cada pedido, e não o preço de hoje.
        assert r["refeicoes"] == 4 and r["total"] == 56.0 and r["semValor"] == 1

    def test_os_maiores_primeiro_e_o_dia_em_ordem_de_calendario(self, escola):
        r = chamar(escola.cliente(), "custos_da_cantina")
        assert r["porAluno"][0]["rotulo"] == NOME[B] and r["porAluno"][0]["total"] == 20.0
        assert r["porTurma"][0]["total"] >= r["porTurma"][-1]["total"]
        rotulos = [linha["rotulo"] for linha in r["porDia"]]
        assert rotulos == sorted(rotulos)

    def test_o_limite_corta_cada_recorte_e_diz_qual(self, escola):
        r = chamar(escola.cliente(), "custos_da_cantina", limite=1)
        assert len(r["porAluno"]) == 1 and r["linhas"]["porAluno"] == 5
        assert r["truncado"]["porAluno"] is True and r["truncado"]["porCantina"] is True
        assert r["refeicoes"] == 5   # o total não encolhe com o corte

    @pytest.mark.parametrize(("args", "de", "ate"), [
        ({"ate": "2026-10-15"}, "2026-10-01", "2026-10-15"),
        ({"de": "2026-02-10"}, "2026-02-10", "2026-02-28"),
        ({"de": "2028-02-01"}, "2028-02-01", "2028-02-29"),
        ({"de": "2026-12-05"}, "2026-12-05", "2026-12-31"),
    ])
    def test_a_janela_que_falta_vem_do_mes(self, escola, args, de, ate):
        r = chamar(escola.cliente(), "custos_da_cantina", **args)
        assert (r["de"], r["ate"]) == (de, ate)

    def test_sem_periodo_e_o_mes_corrente(self, escola):
        hoje = _hoje()
        r = chamar(escola.cliente(), "custos_da_cantina")
        assert (r["de"], r["ate"]) == (hoje.replace(day=1).isoformat(), tools._fim_do_mes(hoje).isoformat())

    def test_a_janela_tem_o_teto_das_exportacoes(self, escola):
        assert tools.TETO_DE_DIAS_DE_CUSTO == rotas._TETO_DE_DIAS_DA_EXPORTACAO
        r = chamar(escola.cliente(), "custos_da_cantina", de="2026-01-01", ate="2026-06-30")
        assert f"até {tools.TETO_DE_DIAS_DE_CUSTO} dias" in r["erro"]

    def test_um_periodo_cheio_nao_vira_uma_url_que_o_httpx_recusa(self, escola):
        """Com a lista de ids de pedido na URL, a tela e a tool de custos caíam
        com erro acima de ~1.300 pedidos. Só aparece no volume: o fake
        não tem URL, e por isso a conta aqui é a do tamanho do filtro."""
        hoje = _hoje()
        base = next(iter(escola.db["pedido_refeicao"].values()))
        for n in range(2000):
            pid = _id(35, n)
            escola.db["pedido_refeicao"][pid] = {**base, "id": pid}
        cliente = escola.cliente()
        r = chamar(cliente, "custos_da_cantina", de=hoje.replace(day=1).isoformat(), ate=tools._fim_do_mes(hoje).isoformat())
        assert "erro" not in r and r["refeicoes"] > 2000
        maior_filtro = max(
            (len(valor) for c in cliente.consultas for tipo, _, valor in c.filtros if tipo == "in"), default=0
        )
        assert maior_filtro * len("00000000-0000-0000-0000-000000000000,") < 65536

    def test_as_exportacoes_leem_os_itens_em_lotes_sem_perder_nenhum(self, escola):
        """As exportações leem os itens de CADA pedido, e o filtro com todos os
        ids ia inteiro na URL: acima de ~1.300 pedidos, erro nos XLSX e
        CSV. Em lotes, nenhum filtro passa do que a URL aguenta, e a soma dos
        lotes é a leitura inteira — quem perde item num lote erra a planilha
        sem erro nenhum."""
        hoje = _hoje()
        base = next(iter(escola.db["pedido_refeicao"].values()))
        for n in range(2000):
            pid = _id(35, n)
            escola.db["pedido_refeicao"][pid] = {**base, "id": pid}
            escola.db["pedido_refeicao_item"][_id(36, n)] = {"id": _id(36, n), "pedido_id": pid, "opcao_id": _id(37, n)}
        cliente = escola.cliente()
        dados = cantina_relatorio._ler(
            cliente, de=hoje.replace(day=1), ate=tools._fim_do_mes(hoje), cantina_id=None
        )
        maior_filtro = max(len(valor) for c in cliente.consultas for tipo, _, valor in c.filtros if tipo == "in")
        assert maior_filtro <= cantina_relatorio.LOTE_DE_IDS
        assert maior_filtro * len("00000000-0000-0000-0000-000000000000,") < 65536
        lidos = {i["pedido_id"] for i in dados["itens"]}
        assert {_id(35, n) for n in range(2000)} <= lidos

    def test_a_soma_nao_le_o_prato(self, escola):
        cliente = escola.cliente()
        chamar(cliente, "custos_da_cantina")
        assert not cliente.em("pedido_refeicao_item") and not cliente.em("cardapio_bloco")
        assert not cliente.em("cardapio_opcao")

    @pytest.mark.parametrize("args", [{"ate": "ontem"}, {"de": "ontem"}, {"cantina_id": "Ari"}])
    def test_argumento_torto(self, escola, args):
        assert "erro" in chamar(escola.cliente(), "custos_da_cantina", **args)

    def test_cantina_que_nao_existe_e_erro_e_nao_zero(self, escola):
        """Um uuid que não é de cantina nenhuma somava zero: a IA diria que a
        cantina não custou nada (prova de 30/10)."""
        assert "não existe" in chamar(escola.cliente(), "custos_da_cantina", cantina_id=_id(30, 99))["erro"]


class TestDireitos:
    def test_o_resumo_e_o_do_card_do_hub(self, escola):
        cliente = escola.cliente()
        r = chamar(cliente, "direitos_a_refeicao")
        assert r["resumo"] == leitura.resumo_dos_direitos(escola.cliente())
        assert r["resumo"]["comDireito"] == 4
        assert (r["resumo"]["almoco"], r["resumo"]["janta"]) == (3, 2)

    @pytest.mark.parametrize(("args", "esperados"), [
        ({}, {A, B, C, D}),
        ({"refeicao": "janta"}, {A, D}),
        ({"refeicao": "almoco"}, {A, B, C}),
        # F é ativo e não tem direito nenhum; E tem pedido, mas é inativa.
        ({"situacao": "sem_direito", "refeicao": "janta"}, {B, C, F}),
    ])
    def test_o_recorte(self, escola, args, esperados):
        r = chamar(escola.cliente(), "direitos_a_refeicao", **args)
        assert {a["alunoId"] for a in r["alunos"]} == esperados
        assert r["total"] == len(esperados)

    def test_sem_direito_nenhum_e_todos(self, escola):
        ativos = {a["id"] for a in escola.db["aluno"].values() if a["ativo"]}
        r = chamar(escola.cliente(), "direitos_a_refeicao", situacao="todos")
        assert {a["alunoId"] for a in r["alunos"]} == ativos
        r = chamar(escola.cliente(), "direitos_a_refeicao", situacao="sem_direito")
        assert {a["alunoId"] for a in r["alunos"]} == ativos - {A, B, C, D}

    def test_a_linha_tem_a_identidade_e_a_turma(self, escola):
        aluno = next(a for a in chamar(escola.cliente(), "direitos_a_refeicao")["alunos"] if a["alunoId"] == A)
        assert aluno == {
            "alunoId": A, "matricula": MATRICULA[A], "nome": NOME[A], "turma": "3o ITA AD",
            "direitos": ["almoco", "janta"],
        }

    def test_o_limite_corta_a_lista_e_nao_o_resumo(self, escola):
        r = chamar(escola.cliente(), "direitos_a_refeicao", limite=1)
        assert len(r["alunos"]) == 1 and r["total"] == 4 and r["truncado"] is True
        assert r["resumo"]["comDireito"] == 4


# ─── A rota e a tool são a mesma função ──────────────────────────────────


class TestARotaContinuaIgual:
    @pytest.fixture
    def com_rota(self, escola, monkeypatch):
        _com_as_views(escola.db)
        monkeypatch.setattr(rotas, "get_supabase", escola.cliente)
        return escola

    def test_a_rota_da_coordenacao_ve_a_restricao_e_nao_ganha_matricula(self, com_rota):
        pedidos = asyncio.run(rotas.cardapio_para_a_coordenacao(ALMOCO))["pedidos"]
        por_id = {p["alunoId"]: p for p in pedidos}
        assert por_id[A]["restricaoAlimentar"] == SEM_LACTOSE
        # A matrícula é do MCP, para o pseudônimo: não é dado do balcão.
        assert all("matricula" not in p for p in pedidos)

    def test_a_lista_do_balcao_e_a_do_mcp_dizem_o_mesmo(self, com_rota):
        da_rota = asyncio.run(rotas.cardapio_para_a_coordenacao(ALMOCO))["pedidos"]
        r = chamar(com_rota.cliente(), "pedidos_da_refeicao", refeicao="almoco", cantina_id=CANTINA)
        da_tool = r["cardapios"][0]["alunos"]
        tirar = ("restricaoAlimentar", "matricula")
        assert [{k: v for k, v in p.items() if k not in tirar} for p in da_rota] == [
            {k: v for k, v in p.items() if k not in tirar} for p in da_tool
        ]

    def test_a_tela_de_direitos_segue_com_a_restricao(self, com_rota):
        saida = asyncio.run(rotas.listar_direitos())
        por_id = {a["id"]: a for a in saida["alunos"]}
        assert por_id[A]["restricaoAlimentar"] == SEM_LACTOSE
        assert saida["comDireito"] == 4 and saida["total"] == len(saida["alunos"])

    def test_o_padrao_do_dominio_e_sem_a_restricao(self, escola):
        cliente = escola.cliente()
        lista = leitura.alunos_e_direitos(cliente)["alunos"]
        assert all("restricaoAlimentar" not in a for a in lista)
        linhas = leitura.pedidos_do_cardapio(cliente, ALMOCO, nomes_das_opcoes=dict)
        assert all("restricaoAlimentar" not in a and "matricula" not in a for a in linhas)
        assert not [c for c in cliente.consultas if "restricao_alimentar" in c.colunas]

    def test_a_lista_de_cantinas_traz_as_contas_e_a_regra(self, com_rota):
        por_nome = {c["nome"]: c for c in asyncio.run(rotas.listar_cantinas())}
        assert [conta["email"] for conta in por_nome["Cantina do Ari"]["contas"]] == ["copa@escola.invalid"]
        assert por_nome["Food"]["contas"] == []
        assert por_nome["Food"]["prazo_padrao_hora"] == "20:00:00"

    def test_o_calendario_das_rotas_segue_lendo_a_view(self, com_rota, monkeypatch):
        cliente = com_rota.cliente()
        monkeypatch.setattr(rotas, "get_supabase", lambda: cliente)
        hoje = _hoje()
        asyncio.run(rotas.calendario_da_coordenacao(hoje, hoje, CANTINA))
        assert cliente.em("v_pedidos_por_cardapio")


# ─── O catálogo ──────────────────────────────────────────────────────────


class TestCatalogo:
    @pytest.mark.parametrize("nome", TODAS)
    def test_descricao_nos_quatro_blocos(self, nome):
        descricao = REGISTRO.obter(COORDENACAO, nome).descricao
        blocos = ("Quando usar:", "Antes de chamar, confirme:", "Definições:", "Exemplo:")
        posicoes = [descricao.find(b) for b in blocos]
        assert -1 not in posicoes and posicoes == sorted(posicoes), nome

    @pytest.mark.parametrize("nome", TODAS)
    def test_toda_tool_tem_limite_e_diz_o_teto(self, nome):
        f = REGISTRO.obter(COORDENACAO, nome)
        assert re.search(r"até \d+", f.propriedades["limite"]["description"]), nome

    @pytest.mark.parametrize("nome", TODAS)
    def test_so_leem_e_vao_ao_mcp(self, nome):
        f = REGISTRO.obter(COORDENACAO, nome)
        assert f.expor_no_mcp and f.somente_leitura

    def test_o_modulo_nao_le_nem_cita_o_token_da_cantina(self):
        fonte = Path(tools.__file__).read_text(encoding="utf-8")
        assert "import cantina_token" not in fonte and "assinar_retirada" not in fonte
        assert "usuario_cantina\")" not in fonte

    def test_a_turma_do_fixture_existe(self, escola):
        """Guarda do fixture: sem matrícula ativa, os testes de turma passariam
        olhando `None`."""
        assert any(
            m["turma_id"] == T1 and m["ativo_ate"] is None for m in escola.db["matricula_turma"].values()
        )
