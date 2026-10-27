"""A régua como dado: `descrever_criterio` e `listar_com_estado` (docs/43 §4.3).

`descrever_criterio` nasceu em `routes/ciclos.py` e desceu para
`stats/criterios.py`, para a tool que explica a régua não importar de
`routes/`. O que se trava:

  1. **A descrição resolve o corte**, inclusive o que vem do `*`, mantém o
     mínimo em acertos como acertos e cita o artigo do edital — é o que impede
     o front (e o assistente) de reimplementar `corte_da_materia`.
  2. **As rotas descrevem pelo domínio**: as três leituras de régua devolvem
     exatamente `descrever_criterio` mais o que é delas.
  3. **"Não consegui ler as criadas" não vira "só existem as cinco".**
     `listar` continua falhando aberto, e `listar_com_estado` diz quando falhou.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.routes import ciclos as rota_ciclos
from app.routes import criterios as rota_criterios
from app.stats import criterios, criterios_repo

from .fake_postgrest import FakeCliente

CHAVES = {
    "slug", "nome", "descricao", "fase", "combinador", "desempate", "cortes",
    "corteGenerico", "corteMedia", "eliminatorias", "predicados",
}

META_7 = {
    "slug": "meta-7-exatas",
    "nome": "Meta 7 nas exatas",
    "descricao": "7 em Mat/Fís/Quím e acima de 4 em Português.",
    "combinador": "algum",
    "fase": None,
    "desempate": ["media", "matematica"],
    "predicados": [
        {"materia": "matematica", "operador": ">=", "valor_nota": 7.0, "fonte": "meta da casa"},
        {"materia": "portugues", "operador": ">", "valor_nota": 4.0},
    ],
}


def banco_vazio() -> FakeCliente:
    return FakeCliente({"criterio_classificacao": {}, "predicado_criterio": {}})


class ClienteQuebrado:
    def table(self, _nome):
        raise RuntimeError("sem banco")


# ─── 1 · A descrição resolve o corte ─────────────────────────────────────


class TestDescreverCriterio:
    def test_o_asterisco_vira_corte_em_cada_materia(self):
        """A régua do colégio fala em "qualquer disciplina" sem listar nenhuma."""
        d = criterios.descrever_criterio(criterios.TIO_LEO)
        assert d["cortes"] == dict.fromkeys(criterios.MATERIAS_CONHECIDAS, 4.0)
        assert d["corteGenerico"] == 4.0
        assert d["corteMedia"] == 5.0
        assert d["eliminatorias"] == ["ingles"]

    def test_acertos_ficam_acertos_e_o_artigo_vem_junto(self):
        d = criterios.descrever_criterio(criterios.ITA_FASE_1)
        quimica = next(p for p in d["predicados"] if p["materia"] == "quimica")
        assert quimica["minimo"] == {"acertos": 5, "de": 12}
        assert quimica["fonte"] == "ITA §4.6.2.1"
        # O corte resolvido é a mesma régua em nota: 5 de 12.
        assert d["cortes"]["quimica"] == pytest.approx(5 / 12 * 10)
        # Sem predicado para Português e sem `*`: não há corte a inventar.
        assert "portugues" not in d["cortes"]
        assert d["corteGenerico"] is None
        assert d["corteMedia"] == 5.0

    def test_media_geral_aparece_como_materia_none(self):
        d = criterios.descrever_criterio(criterios.ITA_FASE_1)
        media = [p for p in d["predicados"] if p["materia"] is None]
        assert [(p["minimo"], p["fonte"]) for p in media] == [(5.0, "ITA §4.6.2.2")]

    @pytest.mark.parametrize("slug", sorted(criterios.CRITERIOS))
    def test_forma_e_ordem_estaveis_e_serializavel(self, slug):
        regua = criterios.CRITERIOS[slug]
        d = criterios.descrever_criterio(regua)
        assert set(d) == CHAVES
        assert d["slug"] == slug
        assert d["desempate"] == list(regua.desempate)
        assert len(d["predicados"]) == len(regua.predicados)
        # A ordem de `cortes` e `eliminatorias` é a de MATERIAS_CONHECIDAS:
        # reordenar a constante muda o JSON das rotas.
        ordem = list(criterios.MATERIAS_CONHECIDAS)
        assert list(d["cortes"]) == [m for m in ordem if m in d["cortes"]]
        assert d["eliminatorias"] == [m for m in ordem if m in d["eliminatorias"]]
        json.dumps(d)

    def test_materias_validas_do_repo_derivam_da_mesma_lista(self):
        assert frozenset(criterios.MATERIAS_CONHECIDAS) == criterios_repo.MATERIAS_VALIDAS


# ─── 2 · As rotas descrevem pelo domínio ─────────────────────────────────


@pytest.fixture
def com_regua_criada(monkeypatch) -> FakeCliente:
    cliente = banco_vazio()
    criterios_repo.criar(cliente, META_7, criado_por="coord-1")
    monkeypatch.setattr(rota_ciclos, "get_supabase", lambda: cliente)
    monkeypatch.setattr(rota_criterios, "get_supabase", lambda: cliente)
    return cliente


def _esperado(cliente) -> list[dict]:
    return [
        {**criterios.descrever_criterio(c), "embutido": c.slug in criterios.CRITERIOS}
        for c in criterios_repo.listar(cliente)
    ]


class TestRotas:
    def test_seletor_do_painel(self, com_regua_criada):
        resposta = rota_ciclos.criterios_disponiveis()
        assert resposta == _esperado(com_regua_criada)
        assert [r["slug"] for r in resposta][-1] == "meta-7-exatas"
        assert resposta[-1]["embutido"] is False

    def test_lista_de_reguas(self, com_regua_criada):
        assert asyncio.run(rota_criterios.listar_criterios()) == _esperado(com_regua_criada)

    def test_uma_regua_embutida(self, com_regua_criada):
        resposta = asyncio.run(rota_criterios.obter_criterio("ita-f1"))
        assert resposta == {
            **criterios.descrever_criterio(criterios.ITA_FASE_1),
            "embutido": True,
            "versoes": [],
        }

    def test_uma_regua_criada_traz_as_versoes(self, com_regua_criada):
        resposta = asyncio.run(rota_criterios.obter_criterio("meta-7-exatas"))
        regua = criterios_repo.resolver(com_regua_criada, "meta-7-exatas")
        assert {k: resposta[k] for k in CHAVES} == criterios.descrever_criterio(regua)
        assert resposta["embutido"] is False
        assert [(v["versao"], v["ativo"], v["criadoPor"]) for v in resposta["versoes"]] == [
            (1, True, "coord-1")
        ]


# ─── 3 · Falha aberta, mas dita ──────────────────────────────────────────


class TestListarComEstado:
    def test_sem_regua_criada_sao_as_cinco_e_nada_falhou(self):
        reguas, indisponiveis = criterios_repo.listar_com_estado(banco_vazio())
        assert [r.slug for r in reguas] == list(criterios.CRITERIOS)
        assert indisponiveis is False

    def test_a_criada_vem_depois_das_embutidas(self):
        cliente = banco_vazio()
        criterios_repo.criar(cliente, META_7)
        reguas, indisponiveis = criterios_repo.listar_com_estado(cliente)
        assert [r.slug for r in reguas] == [*criterios.CRITERIOS, "meta-7-exatas"]
        assert indisponiveis is False

    def test_banco_fora_diz_que_as_criadas_nao_vieram(self):
        reguas, indisponiveis = criterios_repo.listar_com_estado(ClienteQuebrado())
        assert [r.slug for r in reguas] == list(criterios.CRITERIOS)
        assert indisponiveis is True

    def test_listar_continua_falhando_aberto_e_igual(self):
        """O Painel classifica pelas cinco mesmo com o banco fora — isso não muda."""
        assert len(criterios_repo.listar(ClienteQuebrado())) == len(criterios.CRITERIOS)
        cliente = banco_vazio()
        criterios_repo.criar(cliente, META_7)
        assert [r.slug for r in criterios_repo.listar(cliente)] == [
            r.slug for r in criterios_repo.listar_com_estado(cliente)[0]
        ]
