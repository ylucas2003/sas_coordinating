"""Modo avançado da captação externa (docs/41, simplificação de 25/09/2026).

Não existe mais fila de fusão nem decisão permanente — o binário confirmar/
rejeitar, `candidato_externo_fusao_decisao` e a view `v_fusao_candidata`
saíram de cena (era exatamente esse mecanismo — um nome "decidido" ficava
escondido pra sempre, mesmo ganhando conquista nova depois — que causou o
bug achado em produção: "Yan Lucas Freitas de Araújo" tinha 12
`candidato_externo`, nenhum visível em lugar nenhum). Agrupar agora é só
manual: `criar_perfil`, `mover_conquista`, `remover_candidato_vazio` — sem
"concluir", cada arraste já persiste na hora, sozinho.

Convenção do arquivo: chama os handlers direto (são `def` desde 07/10/2026 —
api/CLAUDE.md, cliente PostgREST síncrono), `FakeCliente` no lugar do
PostgREST.

⚠️ `v_candidato_externo`, `v_candidato_externo_por_nome` e
`v_prova_externa_resumo` são VIEWS de verdade no Postgres (joins e GROUP BY)
— o `FakeCliente` não sabe agregar, então cada teste semeia essas "tabelas"
já com os números prontos, como se a view já tivesse rodado. O que fica sem
cobertura aqui é a SQL da view em si (migration 0063) — isso se confere com
`EXPLAIN` contra o Postgres de verdade, não em teste Python.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_captacao_perfis.py -q
"""

from __future__ import annotations

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
    de `v_candidato_externo_por_nome` (0063) nela; os testes não RODAM a
    tarefa (chamaria `criar_cliente_supabase()` de verdade), só confirmam
    que foi agendada onde o teste quiser checar isso."""
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
        "v_candidato_externo": {},
        "v_candidato_externo_por_nome": {},
        "v_prova_externa_resumo": {},
        "evento_auditoria": {},
    }
    monkeypatch.setattr(captacao, "get_supabase", lambda: FakeCliente(db))
    return db


# ─── criar perfil ───────────────────────────────────────────────────────────


def test_criar_perfil_aumenta_o_grupo_em_um(banco):
    banco["candidato_externo"]["cand-1"] = {
        "id": "cand-1", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA",
        "criado_em": "2024-01-01T00:00:00+00:00",
    }

    tarefas = _tarefas()
    resposta = captacao.criar_perfil(
        captacao.NomeNormalizadoBody(nome_normalizado="ANA BEATRIZ SOUZA"),
        _FakeRequest(),
        tarefas,
        COORDENADOR,
    )

    assert resposta["conquistas"] == []
    assert resposta["nome_normalizado"] == "ANA BEATRIZ SOUZA"
    assert resposta["nome"] == "Ana Beatriz Souza"  # herdado de quem já existia
    assert resposta["status_captacao"] == "novo"
    # Realmente gravado — não só devolvido na resposta.
    assert len(banco["candidato_externo"]) == 2
    assert banco["evento_auditoria"]  # auditou
    assert len(tarefas.tasks) == 1  # agendou o refresh da view por nome


def test_criar_perfil_404_sem_ninguem_no_nome(banco):
    with pytest.raises(HTTPException) as exc:
        captacao.criar_perfil(
            captacao.NomeNormalizadoBody(nome_normalizado="NINGUEM AQUI"), _FakeRequest(), _tarefas(), COORDENADOR
        )
    assert exc.value.status_code == 404


# ─── atualizar candidato: funil + retrato editável (docs/41 §17) ──────────


def test_atualizar_status_e_observacoes(banco):
    banco["candidato_externo"]["cand-1"] = {"id": "cand-1", "status_captacao": "novo"}

    resposta = captacao.atualizar_candidato(
        captacao.AtualizarCandidatoBody(status_captacao="contatado", observacoes="Ligou pra família"),
        _FakeRequest(),
        _tarefas(),
        "cand-1",
        COORDENADOR,
    )

    assert resposta["status_captacao"] == "contatado"
    assert resposta["observacoes"] == "Ligou pra família"
    # Status mudou -> auditou.
    assert banco["evento_auditoria"]


def test_atualizar_escola_trava_o_retrato(banco):
    """O guard central do docs/41 §17: editar escola/cidade/uf à mão marca
    `retrato_editado_a_mao`, pra `mover_conquista`/o resolver pararem de
    recalcular em cima da edição."""
    banco["candidato_externo"]["cand-1"] = {
        "id": "cand-1", "status_captacao": "novo", "escola": None, "retrato_editado_a_mao": False,
    }

    resposta = captacao.atualizar_candidato(
        captacao.AtualizarCandidatoBody(escola="Colégio Ari de Sá", cidade="Fortaleza", uf="CE"),
        _FakeRequest(),
        _tarefas(),
        "cand-1",
        COORDENADOR,
    )

    assert resposta["escola"] == "Colégio Ari de Sá"
    assert resposta["cidade"] == "Fortaleza"
    assert resposta["uf"] == "CE"
    assert resposta["retrato_editado_a_mao"] is True
    # Editar retrato não é "status" -> não auditou.
    assert not banco["evento_auditoria"]


def test_atualizar_400_sem_nenhum_campo(banco):
    banco["candidato_externo"]["cand-1"] = {"id": "cand-1", "status_captacao": "novo"}

    with pytest.raises(HTTPException) as exc:
        captacao.atualizar_candidato(
            captacao.AtualizarCandidatoBody(), _FakeRequest(), _tarefas(), "cand-1", COORDENADOR
        )
    assert exc.value.status_code == 400


def test_atualizar_404_candidato_inexistente(banco):
    with pytest.raises(HTTPException) as exc:
        captacao.atualizar_candidato(
            captacao.AtualizarCandidatoBody(status_captacao="contatado"),
            _FakeRequest(),
            _tarefas(),
            "fantasma",
            COORDENADOR,
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

    resposta = captacao.mover_conquista(
        captacao.MoverConquistaBody(conquista_id="q-ime", candidato_id="cand-a"),
        _FakeRequest(),
        _tarefas(),
        COORDENADOR,
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


def test_mover_pula_recalculo_de_quem_esta_travado(banco):
    """docs/41 §17: cand-a já foi editado à mão (`retrato_editado_a_mao`) —
    ganhar uma conquista não pode apagar a edição."""
    banco["candidato_externo"] = {
        "cand-a": {
            "id": "cand-a", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA",
            "escola": "Editado à mão", "retrato_editado_a_mao": True,
        },
        "cand-c": {"id": "cand-c", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA"},
    }
    banco["conquista_externa"] = {
        "q-ime": _conquista(
            id="q-ime", candidato_id="cand-c", ano=2024, resultado="Aprovado",
            escola_informada="Escola Nova", cidade_informada="Recife", uf_informada="PE",
        ),
    }

    captacao.mover_conquista(
        captacao.MoverConquistaBody(conquista_id="q-ime", candidato_id="cand-a"),
        _FakeRequest(),
        _tarefas(),
        COORDENADOR,
    )

    assert banco["conquista_externa"]["q-ime"]["candidato_id"] == "cand-a"  # moveu de verdade
    # Mas o retrato NÃO mudou — a edição manual venceu.
    assert banco["candidato_externo"]["cand-a"]["escola"] == "Editado à mão"
    assert "cidade" not in banco["candidato_externo"]["cand-a"]


def test_mover_recusa_candidato_de_outro_nome(banco):
    banco["candidato_externo"] = {
        "cand-a": {"id": "cand-a", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA"},
        "cand-x": {"id": "cand-x", "nome": "Outra Pessoa", "nome_normalizado": "OUTRA PESSOA"},
    }
    banco["conquista_externa"] = {
        "q-1": _conquista(id="q-1", candidato_id="cand-a"),
    }

    with pytest.raises(HTTPException) as exc:
        captacao.mover_conquista(
            captacao.MoverConquistaBody(conquista_id="q-1", candidato_id="cand-x"),
            _FakeRequest(),
            _tarefas(),
            COORDENADOR,
        )
    assert exc.value.status_code == 400
    # Nada foi movido.
    assert banco["conquista_externa"]["q-1"]["candidato_id"] == "cand-a"


def test_mover_404_conquista_inexistente(banco):
    with pytest.raises(HTTPException) as exc:
        captacao.mover_conquista(
            captacao.MoverConquistaBody(conquista_id="fantasma", candidato_id="cand-a"),
            _FakeRequest(),
            _tarefas(),
            COORDENADOR,
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

    resposta = captacao.remover_candidato_vazio(_FakeRequest(), _tarefas(), "cand-vazio", COORDENADOR)

    assert resposta == {"ok": True}
    assert "cand-vazio" not in banco["candidato_externo"]


def test_remover_recusa_perfil_com_conquista(banco):
    banco["candidato_externo"]["cand-a"] = {"id": "cand-a", "nome_normalizado": "ANA BEATRIZ SOUZA"}
    banco["v_candidato_externo"]["cand-a"] = {
        "id": "cand-a", "nome_normalizado": "ANA BEATRIZ SOUZA", "conquistas_total": 2,
    }

    with pytest.raises(HTTPException) as exc:
        captacao.remover_candidato_vazio(_FakeRequest(), _tarefas(), "cand-a", COORDENADOR)
    assert exc.value.status_code == 409
    assert "cand-a" in banco["candidato_externo"]  # não apagou


def test_remover_404_candidato_inexistente(banco):
    with pytest.raises(HTTPException) as exc:
        captacao.remover_candidato_vazio(_FakeRequest(), _tarefas(), "fantasma", COORDENADOR)
    assert exc.value.status_code == 404


# ─── obter_perfis_do_nome: a ficha de QUALQUER nome, não só "em disputa" ───


def test_obter_perfis_do_nome_com_um_candidato_nao_da_404(banco):
    """O guard crítico da simplificação: com tudo nascendo 1:1
    (resolver_candidatos_externos.py), a maioria esmagadora dos nomes tem
    exatamente 1 perfil — se o guard continuasse `< 2`, clicar em quase
    qualquer nome na lista geral daria 404."""
    banco["v_candidato_externo"]["cand-solo"] = {
        "id": "cand-solo", "nome": "Fulano Único", "nome_normalizado": "FULANO UNICO",
        "escola": None, "cidade": None, "uf": None, "serie_referencia_min": None,
        "serie_referencia_max": None, "ano_referencia_serie": None, "status_captacao": "novo",
        "observacoes": None, "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
        "conquistas_total": 1, "provas_distintas": 1, "ano_mais_recente": 2024,
    }

    resposta = captacao.obter_perfis_do_nome("FULANO UNICO")

    assert resposta["nome_normalizado"] == "FULANO UNICO"
    assert len(resposta["candidatos"]) == 1


def test_obter_perfis_do_nome_404_sem_ninguem(banco):
    with pytest.raises(HTTPException) as exc:
        captacao.obter_perfis_do_nome("NINGUEM")
    assert exc.value.status_code == 404


def test_obter_perfis_do_nome_com_varios_candidatos(banco):
    banco["v_candidato_externo"] = {
        "cand-a": {
            "id": "cand-a", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA",
            "escola": "Colégio Nova Era", "cidade": "Fortaleza", "uf": "CE",
            "serie_referencia_min": None, "serie_referencia_max": None, "ano_referencia_serie": 2023,
            "status_captacao": "novo", "observacoes": None,
            "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
            "conquistas_total": 1, "provas_distintas": 1, "ano_mais_recente": 2023,
        },
        "cand-b": {
            "id": "cand-b", "nome": "Ana Beatriz Souza", "nome_normalizado": "ANA BEATRIZ SOUZA",
            "escola": None, "cidade": None, "uf": "SP",
            "serie_referencia_min": None, "serie_referencia_max": None, "ano_referencia_serie": 2024,
            "status_captacao": "novo", "observacoes": None,
            "criado_em": "2024-02-01T00:00:00+00:00", "atualizado_em": "2024-02-01T00:00:00+00:00",
            "conquistas_total": 1, "provas_distintas": 1, "ano_mais_recente": 2024,
        },
    }

    resposta = captacao.obter_perfis_do_nome("ANA BEATRIZ SOUZA")

    assert len(resposta["candidatos"]) == 2


# ─── listar_candidatos: agrega por nome, filtros por conjunto ──────────────


def _listar(**over):
    """Chamada direta não passa pelo FastAPI, então todo `Query(None)` tem de
    vir explícito — senão chega o próprio objeto `Query`, que é "verdadeiro",
    e a rota acharia que há critério de conquista."""
    params = {
        "uf": None, "status_captacao": None, "conquistas_min": None, "busca": None,
        "prova": None, "faixa": None, "ano_min": None, "ano_max": None,
        "publico": None, "ano_ingresso": None,
        "pagina": 1, "por_pagina": captacao.POR_PAGINA_PADRAO,
    }
    params.update(over)
    return captacao.listar_candidatos(**params)


def test_listar_candidatos_le_a_view_por_nome(banco):
    banco["v_candidato_externo_por_nome"]["ANA BEATRIZ SOUZA"] = {
        "nome_normalizado": "ANA BEATRIZ SOUZA", "nome": "Ana Beatriz Souza",
        "escolas": ["Colégio Nova Era"], "cidades": ["Fortaleza", "São Paulo"], "ufs": ["CE", "SP"],
        "status_captacao": ["novo"], "conquistas_total": 3, "provas_distintas": 2,
        "perfis_no_grupo": 3, "ano_mais_recente": 2024,
        "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
    }

    resposta = _listar()

    assert resposta["total"] == 1
    linha = resposta["candidatos"][0]
    assert linha["perfis_no_grupo"] == 3
    assert linha["conquistas_total"] == 3  # já soma o grupo inteiro
    assert linha["ufs"] == ["CE", "SP"]  # conjunto, não um valor só


def test_listar_candidatos_filtra_por_uf_bate_se_qualquer_conquista_casar(banco):
    banco["v_candidato_externo_por_nome"] = {
        "a": {
            "nome_normalizado": "A", "nome": "A", "escolas": [], "cidades": [], "ufs": ["CE", "SP"],
            "status_captacao": ["novo"], "conquistas_total": 2, "provas_distintas": 2,
            "perfis_no_grupo": 2, "ano_mais_recente": 2024,
            "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
        },
        "b": {
            "nome_normalizado": "B", "nome": "B", "escolas": [], "cidades": [], "ufs": ["RJ"],
            "status_captacao": ["novo"], "conquistas_total": 1, "provas_distintas": 1,
            "perfis_no_grupo": 1, "ano_mais_recente": 2024,
            "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
        },
    }

    resposta = _listar(uf="SP")

    assert resposta["total"] == 1
    assert resposta["candidatos"][0]["nome_normalizado"] == "A"


def test_listar_candidatos_400_status_desconhecido(banco):
    with pytest.raises(HTTPException) as exc:
        _listar(status_captacao="inventado")
    assert exc.value.status_code == 400


def _linha_por_nome(nome_normalizado: str, **over) -> dict:
    base = {
        "nome_normalizado": nome_normalizado, "nome": nome_normalizado.title(),
        "escolas": [], "cidades": [], "ufs": [], "status_captacao": ["novo"],
        "conquistas_total": 1, "provas_distintas": 1, "participacoes": 0,
        "perfis_no_grupo": 1, "ano_mais_recente": 2024,
        "criado_em": "2024-01-01T00:00:00+00:00", "atualizado_em": "2024-01-01T00:00:00+00:00",
    }
    base.update(over)
    return base


def test_listar_busca_ignora_acento_e_maiuscula(banco):
    """Quem digita "goncalves" acha "Gonçalves" — a busca é sobre
    `nome_normalizado`, com o termo normalizado do mesmo jeito (docs/41 §20)."""
    banco["v_candidato_externo_por_nome"] = {
        "a": _linha_por_nome("ANA GONCALVES", nome="Ana Gonçalves"),
        "b": _linha_por_nome("BRUNO LIMA"),
    }

    sem_acento = _listar(busca="goncalves")
    com_acento = _listar(busca="Gonçalves")

    assert [c["nome"] for c in sem_acento["candidatos"]] == ["Ana Gonçalves"]
    assert [c["nome"] for c in com_acento["candidatos"]] == ["Ana Gonçalves"]


class _ClienteComRpc(FakeCliente):
    """`FakeCliente` não conhece RPC; a busca por conquista é uma função SQL
    (0068) — o que se testa aqui é o CONTRATO com ela (parâmetros que vão,
    forma do que volta), não a SQL, que se confere contra o Postgres."""

    def __init__(self, db, linhas):
        super().__init__(db)
        self.linhas = linhas
        self.chamadas: list[tuple[str, dict]] = []

    def rpc(self, funcao, params):
        self.chamadas.append((funcao, params))
        linhas = self.linhas
        return type("R", (), {"execute": lambda _self: type("Resp", (), {"data": linhas})()})()


def test_listar_com_criterio_de_conquista_usa_a_busca_por_conquista(banco, monkeypatch):
    evidencia = {"prova": "OBF", "ano": 2025, "faixa": "ouro", "resultado": "MEDALHA DE OURO", "nivel": "8º ano"}
    cliente = _ClienteComRpc(
        banco,
        [_linha_por_nome("JOAO", conquistas_casadas=1, evidencias=[evidencia], total_filtrado=108)],
    )
    monkeypatch.setattr(captacao, "get_supabase", lambda: cliente)

    resposta = _listar(
        prova=["OBF"], faixa=["ouro"], publico=["medio"], ano_ingresso=2027,
        uf="ce", busca="joão", pagina=3,
    )

    funcao, params = cliente.chamadas[0]
    assert funcao == "buscar_candidatos_por_conquista"
    assert params["p_provas"] == ["OBF"]
    assert params["p_faixas"] == ["ouro"]
    assert params["p_publicos"] == ["medio"]
    assert params["p_ano_ingresso"] == 2027
    assert params["p_uf"] == "CE"
    assert params["p_busca"] == "JOAO"  # normalizado, como nome_normalizado
    assert params["p_deslocamento"] == 2 * captacao.POR_PAGINA_PADRAO
    assert resposta["total"] == 108
    assert resposta["ano_ingresso"] == 2027
    linha = resposta["candidatos"][0]
    assert "total_filtrado" not in linha  # sai da linha, vira `total`
    assert linha["evidencias"] == [evidencia]


def test_listar_ano_ingresso_padrao_e_o_ano_que_vem(banco, monkeypatch):
    cliente = _ClienteComRpc(banco, [])
    monkeypatch.setattr(captacao, "get_supabase", lambda: cliente)
    monkeypatch.setattr(captacao, "_ano_ingresso_padrao", lambda: 2031)

    resposta = _listar(publico=["fundamental"])

    assert cliente.chamadas[0][1]["p_ano_ingresso"] == 2031
    assert resposta["total"] == 0
    assert resposta["ano_ingresso"] == 2031


def test_listar_sem_criterio_de_conquista_nao_chama_a_busca(banco, monkeypatch):
    cliente = _ClienteComRpc(banco, [])
    monkeypatch.setattr(captacao, "get_supabase", lambda: cliente)
    banco["v_candidato_externo_por_nome"]["a"] = _linha_por_nome("A")

    resposta = _listar(uf="CE", conquistas_min=2)

    assert cliente.chamadas == []
    assert "ano_ingresso" in resposta  # o front mostra "Público em <ano>" mesmo sem filtro


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("faixa", ["platina"]), ("publico", ["superior"])],
)
def test_listar_400_vocabulario_desconhecido(banco, campo, valor):
    with pytest.raises(HTTPException) as exc:
        _listar(**{campo: valor})
    assert exc.value.status_code == 400


# ─── listar_provas: rodapé de fontes carregadas ────────────────────────────


def test_listar_provas(banco):
    banco["v_prova_externa_resumo"]["ita"] = {
        "nome": "ITA", "categoria": "vestibular", "ano_min": 2020, "ano_max": 2025, "conquistas_total": 36679,
    }
    banco["v_prova_externa_resumo"]["obmep"] = {
        "nome": "OBMEP", "categoria": "olimpiada", "ano_min": 2016, "ano_max": 2025, "conquistas_total": 69653,
    }

    resposta = captacao.listar_provas()

    nomes = {p["nome"] for p in resposta["provas"]}
    assert nomes == {"ITA", "OBMEP"}
