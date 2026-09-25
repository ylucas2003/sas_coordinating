"""Modo avançado da fila de fusão (docs/41 §8 item 1, pedido de 24/09/2026).

O binário `confirmar_fusao`/`rejeitar_fusao` (sem teste até aqui — cobertura
zero em `routes/captacao.py`) decide o grupo INTEIRO de uma vez. As rotas
novas testadas aqui dão o controle fino que falta: mover um resultado pra
outro perfil, criar um perfil vazio pra separar homônimo, remover o que
sobrar vazio, e concluir a revisão reaproveitando os dois status que já
existem em `candidato_externo_fusao_decisao` (sem migration no CHECK).

Convenção do arquivo (como em `test_foto_perfil.py`): chama os handlers
`async def` direto com `asyncio.run`, `FakeCliente` no lugar do PostgREST.

⚠️ `v_candidato_externo`, `v_candidato_externo_agrupado` e `v_fusao_candidata`
são VIEWS de verdade no Postgres (joins e GROUP BY) — o `FakeCliente` não
sabe agregar, então cada teste semeia essas "tabelas" já com os números
prontos, como se a view já tivesse rodado. O que fica sem cobertura aqui é a
SQL da view em si (migrations 0061/0062) — isso se confere com `EXPLAIN`
contra o Postgres de verdade, não em teste Python (ver plano de verificação).

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_captacao_fusao_avancada.py -q
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.routes import captacao
from tests.fake_postgrest import FakeCliente

COORDENADOR = {"sub": "c-1", "nome": "Coord Teste"}


class _FakeRequest:
    """Só o que os handlers leem de `Request`: `client.host`."""

    def __init__(self, ip: str | None = "203.0.113.7"):
        self.client = type("C", (), {"host": ip})() if ip else None


def _tarefas() -> BackgroundTasks:
    """`BackgroundTasks` de verdade — as rotas escritoras agendam o refresh
    de `v_candidato_externo_agrupado` nela (0062); os testes não RODAM a
    tarefa (chamaria `criar_cliente_supabase()` de verdade), só confirmam que
    foi agendada onde o teste quiser checar isso."""
    return BackgroundTasks()


def _conquista(**over) -> dict:
    base = {
        "id": "q-1",
        "prova_id": "p-1",
        "candidato_id": "cand-1",
        "ano": 2024,
        "nivel_texto": None,
        "serie_referencia_min": 3,
        "serie_referencia_max": 3,
        "resultado": "Medalha de prata",
        "nome_informado": "Ana Beatriz Souza",
        "escola_informada": "Colégio Nova Era",
        "cidade_informada": "Fortaleza",
        "uf_informada": "CE",
        "fonte_url": "https://exemplo.org/resultado",
        "raspado_em": "2024-01-01T00:00:00+00:00",
        "notas_por_materia": None,
    }
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def banco(monkeypatch) -> dict:
    db: dict = {
        "candidato_externo": {},
        "conquista_externa": {},
        "prova_externa": {},
        "candidato_externo_fusao_decisao": {},
        "v_candidato_externo": {},
        "v_candidato_externo_agrupado": {},
        "v_fusao_candidata": {},
        "evento_auditoria": {},
    }
    monkeypatch.setattr(captacao, "get_supabase", lambda: FakeCliente(db))
    return db


# ─── criar-perfil ───────────────────────────────────────────────────────────


def test_criar_perfil_aumenta_o_grupo_em_um(banco):
    banco["candidato_externo"]["cand-1"] = {
        "id": "cand-1", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA",
        "criado_em": "2024-01-01T00:00:00+00:00",
    }

    tarefas = _tarefas()
    resposta = asyncio.run(
        captacao.criar_perfil_no_grupo(
            captacao.FusaoBody(nome_normalizado="ANA BEATRIZ SOUZA"),
            _FakeRequest(),
            tarefas,
            COORDENADOR,
        )
    )

    assert resposta["conquistas"] == []
    assert resposta["nome_normalizado"] == "ANA BEATRIZ SOUZA"
    assert resposta["nome"] == "Ana Beatriz Souza"  # herdado de quem já existia
    assert resposta["status_captacao"] == "novo"
    # Realmente gravado — não só devolvido na resposta.
    assert len(banco["candidato_externo"]) == 2
    assert banco["evento_auditoria"]  # auditou
    assert len(tarefas.tasks) == 1  # agendou o refresh da view agrupada


def test_criar_perfil_404_sem_ninguem_no_nome(banco):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            captacao.criar_perfil_no_grupo(
                captacao.FusaoBody(nome_normalizado="NINGUEM AQUI"), _FakeRequest(), _tarefas(), COORDENADOR
            )
        )
    assert exc.value.status_code == 404


# ─── mover conquista ────────────────────────────────────────────────────────


def test_mover_reatribui_e_recalcula_os_dois_retratos(banco):
    banco["candidato_externo"] = {
        "cand-a": {"id": "cand-a", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA"},
        "cand-c": {"id": "cand-c", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA"},
    }
    # cand-a tem OBMEP 2023; cand-c tem IME 2024 (a conquista que vai mudar de dono).
    banco["conquista_externa"] = {
        "q-obmep": _conquista(id="q-obmep", candidato_id="cand-a", ano=2023, resultado="Medalha de prata"),
        "q-ime": _conquista(
            id="q-ime", candidato_id="cand-c", ano=2024, resultado="Aprovado",
            nome_informado="Ana Beatriz Souza", escola_informada=None,
            cidade_informada=None, uf_informada="CE",
        ),
    }

    resposta = asyncio.run(
        captacao.mover_conquista(
            captacao.MoverConquistaBody(conquista_id="q-ime", candidato_id="cand-a"),
            _FakeRequest(),
            _tarefas(),
            COORDENADOR,
        )
    )

    assert resposta == {"ok": True}
    assert banco["conquista_externa"]["q-ime"]["candidato_id"] == "cand-a"
    # cand-a ganhou a conquista mais recente (2024) — retrato recalculado por ela.
    assert banco["candidato_externo"]["cand-a"]["ano_referencia_serie"] == 2024
    assert banco["candidato_externo"]["cand-a"]["uf"] == "CE"
    # cand-c ficou sem nenhuma conquista — recompute pula ele (não quebra em
    # lista vazia), retrato continua como estava antes.
    assert "ano_referencia_serie" not in banco["candidato_externo"]["cand-c"]
    assert banco["evento_auditoria"]


def test_mover_recusa_candidato_de_outro_nome(banco):
    banco["candidato_externo"] = {
        "cand-a": {"id": "cand-a", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA"},
        "cand-x": {"id": "cand-x", "nome": "Outra Pessoa", "nome_normalizado": "OUTRA PESSOA"},
    }
    banco["conquista_externa"] = {
        "q-1": _conquista(id="q-1", candidato_id="cand-a"),
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            captacao.mover_conquista(
                captacao.MoverConquistaBody(conquista_id="q-1", candidato_id="cand-x"),
                _FakeRequest(),
                _tarefas(),
                COORDENADOR,
            )
        )
    assert exc.value.status_code == 400
    # Nada foi movido.
    assert banco["conquista_externa"]["q-1"]["candidato_id"] == "cand-a"


def test_mover_404_conquista_inexistente(banco):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            captacao.mover_conquista(
                captacao.MoverConquistaBody(conquista_id="fantasma", candidato_id="cand-a"),
                _FakeRequest(),
                _tarefas(),
                COORDENADOR,
            )
        )
    assert exc.value.status_code == 404


# ─── remover perfil vazio ───────────────────────────────────────────────────


def test_remover_aceita_perfil_vazio(banco):
    banco["candidato_externo"]["cand-vazio"] = {
        "id": "cand-vazio", "nome": "Novo Perfil", "nome_normalizado": "ANA BEATRIZ SOUZA",
    }
    banco["v_candidato_externo"]["cand-vazio"] = {
        "id": "cand-vazio", "nome_normalizado": "ANA BEATRIZ SOUZA", "conquistas_total": 0,
    }

    resposta = asyncio.run(
        captacao.remover_candidato_vazio(_FakeRequest(), _tarefas(), "cand-vazio", COORDENADOR)
    )

    assert resposta == {"ok": True}
    assert "cand-vazio" not in banco["candidato_externo"]


def test_remover_recusa_perfil_com_conquista(banco):
    banco["candidato_externo"]["cand-a"] = {"id": "cand-a", "nome_normalizado": "ANA BEATRIZ SOUZA"}
    banco["v_candidato_externo"]["cand-a"] = {
        "id": "cand-a", "nome_normalizado": "ANA BEATRIZ SOUZA", "conquistas_total": 2,
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(captacao.remover_candidato_vazio(_FakeRequest(), _tarefas(), "cand-a", COORDENADOR))
    assert exc.value.status_code == 409
    assert "cand-a" in banco["candidato_externo"]  # não apagou


def test_remover_404_candidato_inexistente(banco):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(captacao.remover_candidato_vazio(_FakeRequest(), _tarefas(), "fantasma", COORDENADOR))
    assert exc.value.status_code == 404


# ─── concluir revisão ───────────────────────────────────────────────────────


def test_concluir_com_um_sobrevivente_grava_confirmada(banco):
    # Depois de mover tudo pra cand-a na mão, cand-c ficou vazio.
    banco["candidato_externo"] = {
        "cand-a": {"id": "cand-a", "nome_normalizado": "ANA BEATRIZ SOUZA"},
        "cand-c": {"id": "cand-c", "nome_normalizado": "ANA BEATRIZ SOUZA"},
    }
    banco["v_candidato_externo"] = {
        "cand-a": {"id": "cand-a", "nome_normalizado": "ANA BEATRIZ SOUZA", "conquistas_total": 3},
        "cand-c": {"id": "cand-c", "nome_normalizado": "ANA BEATRIZ SOUZA", "conquistas_total": 0},
    }

    resposta = asyncio.run(
        captacao.concluir_fusao(
            captacao.FusaoBody(nome_normalizado="ANA BEATRIZ SOUZA"), _FakeRequest(), _tarefas(), COORDENADOR
        )
    )

    assert resposta == {"status": "confirmada", "perfis_finais": 1}
    assert "cand-c" not in banco["candidato_externo"]  # vazio, limpo
    assert "cand-a" in banco["candidato_externo"]
    # O fake do PostgREST guarda o upsert sob um id gerado, não sob a chave de
    # conflito — busca pelo valor, igual o PostgREST real faria por índice.
    decisao = next(
        v for v in banco["candidato_externo_fusao_decisao"].values()
        if v["nome_normalizado"] == "ANA BEATRIZ SOUZA"
    )
    assert decisao["status"] == "confirmada"
    assert decisao["decidido_por"] == "Coord Teste"


def test_concluir_com_dois_sobreviventes_grava_rejeitada(banco):
    banco["candidato_externo"] = {
        "cand-a": {"id": "cand-a", "nome_normalizado": "ANA BEATRIZ SOUZA"},
        "cand-b": {"id": "cand-b", "nome_normalizado": "ANA BEATRIZ SOUZA"},
    }
    banco["v_candidato_externo"] = {
        "cand-a": {"id": "cand-a", "nome_normalizado": "ANA BEATRIZ SOUZA", "conquistas_total": 2},
        "cand-b": {"id": "cand-b", "nome_normalizado": "ANA BEATRIZ SOUZA", "conquistas_total": 1},
    }

    resposta = asyncio.run(
        captacao.concluir_fusao(
            captacao.FusaoBody(nome_normalizado="ANA BEATRIZ SOUZA"), _FakeRequest(), _tarefas(), COORDENADOR
        )
    )

    assert resposta == {"status": "rejeitada", "perfis_finais": 2}
    assert set(banco["candidato_externo"]) == {"cand-a", "cand-b"}  # ninguém apagado
    decisao = next(
        v for v in banco["candidato_externo_fusao_decisao"].values()
        if v["nome_normalizado"] == "ANA BEATRIZ SOUZA"
    )
    assert decisao["status"] == "rejeitada"


def test_concluir_404_nome_sem_candidato(banco):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            captacao.concluir_fusao(
                captacao.FusaoBody(nome_normalizado="NINGUEM"), _FakeRequest(), _tarefas(), COORDENADOR
            )
        )
    assert exc.value.status_code == 404


# ─── obter_candidato: duplicatas_pendentes / tem_conflito_nivel ────────────


def test_obter_candidato_sinaliza_duplicata_pendente(banco):
    banco["v_candidato_externo"]["cand-a"] = {
        "id": "cand-a", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA",
        "conquistas_total": 2, "provas_distintas": 2, "ano_mais_recente": 2024,
        "escola": None, "cidade": None, "uf": "CE", "serie_referencia_min": None,
        "serie_referencia_max": None, "ano_referencia_serie": None, "status_captacao": "novo",
        "observacoes": None, "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
    }
    banco["v_fusao_candidata"]["ANA BEATRIZ SOUZA"] = {
        "nome_normalizado": "ANA BEATRIZ SOUZA", "candidatos": 3, "ufs_distintas": 2,
        "tem_conflito_nivel": True,
    }

    resposta = asyncio.run(captacao.obter_candidato("cand-a"))

    assert resposta["nome_normalizado"] == "ANA BEATRIZ SOUZA"
    assert resposta["duplicatas_pendentes"] == 2  # 3 no grupo, menos ela mesma
    assert resposta["tem_conflito_nivel"] is True


def test_obter_candidato_sem_duplicata_zera_o_sinal(banco):
    banco["v_candidato_externo"]["cand-solo"] = {
        "id": "cand-solo", "nome": "Fulano Único", "nome_normalizado": "FULANO UNICO",
        "conquistas_total": 1, "provas_distintas": 1, "ano_mais_recente": 2024,
        "escola": None, "cidade": None, "uf": None, "serie_referencia_min": None,
        "serie_referencia_max": None, "ano_referencia_serie": None, "status_captacao": "novo",
        "observacoes": None, "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
    }

    resposta = asyncio.run(captacao.obter_candidato("cand-solo"))

    assert resposta["duplicatas_pendentes"] == 0
    assert resposta["tem_conflito_nivel"] is False


# ─── listar_candidatos: dedupe (view agrupada) e listar_fusoes: filtro novo ─


def test_listar_candidatos_le_a_view_agrupada(banco):
    banco["v_candidato_externo_agrupado"]["cand-a"] = {
        "id": "cand-a", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA",
        "escola": None, "cidade": None, "uf": "CE", "serie_referencia_min": None,
        "serie_referencia_max": None, "ano_referencia_serie": None, "status_captacao": "novo",
        "observacoes": None, "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
        "conquistas_total": 3, "provas_distintas": 2, "ano_mais_recente": 2024,
        "perfis_no_grupo": 3, "tem_conflito_nivel": False,
    }

    resposta = asyncio.run(
        captacao.listar_candidatos(
            uf=None, status_captacao=None, conquistas_min=None, prova_id=None,
            busca=None, pagina=1, por_pagina=captacao.POR_PAGINA_PADRAO,
        )
    )

    assert resposta["total"] == 1
    linha = resposta["candidatos"][0]
    assert linha["perfis_no_grupo"] == 3
    assert linha["conquistas_total"] == 3  # já soma o grupo, não só o representante


def test_listar_fusoes_filtra_por_conflito_de_nivel(banco):
    banco["v_fusao_candidata"] = {
        "SO UF": {"nome_normalizado": "SO UF", "candidatos": 2, "ufs_distintas": 2, "tem_conflito_nivel": False},
        "CONFLITO": {"nome_normalizado": "CONFLITO", "candidatos": 2, "ufs_distintas": 2, "tem_conflito_nivel": True},
    }

    todos = asyncio.run(
        captacao.listar_fusoes(
            uf_incerta=False, so_conflito_nivel=False, pagina=1, por_pagina=captacao.POR_PAGINA_PADRAO,
        )
    )
    assert todos["total"] == 2

    so_conflito = asyncio.run(
        captacao.listar_fusoes(
            uf_incerta=False, so_conflito_nivel=True, pagina=1, por_pagina=captacao.POR_PAGINA_PADRAO,
        )
    )
    assert so_conflito["total"] == 1
    assert so_conflito["grupos"][0]["nome_normalizado"] == "CONFLITO"
