"""O piso de anonimato das rotas do aluno (docs/27 §9, regra 4).

O vazamento que estes testes existem para não deixar voltar: numa prova em que
só duas pessoas têm nota, "a média da turma" é (a sua nota + a da colega) / 2,
e a nota da colega sai por conta — 2 × média − a sua. Até 26/10 essa média saía
inteira por quatro rotas do aluno: GET /me/simulados (`mediaGeral`),
GET /me/simulado/{id} (`grupos`, mais `posicao` e `percentil`, que com duas
notas dizem quem tirou mais), GET /me/evolucao (a série `turma`) e GET
/me/insight (o `mediaTurma` do payload que vai à OpenAI). E GET
/me/simulado/{id}/questoes devolvia, na mesma tela, o tempo médio da turma.

O que se trava aqui:

  1. sem o piso — o código de antes de 26/10 —, cada uma das quatro rotas
     entrega a nota da colega: é a reprodução do vazamento, e a prova de que o
     detector enxerga o que procura;
  2. com o piso, nenhuma porta deixa derivá-la: nem as quatro rotas, nem o tempo
     médio, nem o payload que iria à OpenAI, nem as tools do chat do aluno, que
     leem as mesmas funções de domínio;
  3. os bullets que o insight gerou com a média vazada não voltam do cache;
  4. com 10 notas ou mais, nada muda — salvo o top 15% e o inferior 15% até 19
     notas, quando o grupo teria uma ou duas pessoas.

O detector procura a nota DERIVADA, e não só a literal: qualquer número, em
qualquer profundidade da resposta, igual à média das duas notas ou à nota da
colega.

As rotas são chamadas pela camada HTTP (TestClient), com `get_supabase` trocado
pelo banco de mentira de `fake_postgrest.py` — com o filtro `neq` a mais, só
aqui — e a sessão do aluno injetada pela dependência. O embed (`simulado(...)`
dentro de `nota`) vem pré-montado na linha. Nada chama a OpenAI: o insight passa
por um dublê que guarda o payload que teria ido.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_piso_de_anonimato.py -q
"""

from __future__ import annotations

import statistics
from types import SimpleNamespace

import pytest

from app.auth import get_current_aluno
from app.chat import tools_aluno
from app.routes import me as rotas_me
from app.stats import aluno_dados, insight_aluno
from app.stats.utils import hash_payload_estavel

from .fake_postgrest import FakeCliente, Query, Tabela

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"

ANA = "a-ana"
BIA = "a-bia"
SESSAO_DA_ANA = {"tipo": "aluno", "aluno_id": ANA, "nome": "Ana Aluna"}

#: A prova de duas notas: só a Ana (a dona do token) e a Beatriz.
NOTA_DA_ANA, NOTA_DA_BIA = 7.0, 8.88
MEDIA_DAS_DUAS = (NOTA_DA_ANA + NOTA_DA_BIA) / 2  # 7,94 — e 2 × 7,94 − 7,0 = 8,88

#: Vinte colegas sem nome, para as outras provas passarem do piso.
COLEGAS = [f"a-{i:02d}" for i in range(1, 21)]
VALORES = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.5, 7.0, 7.5,
           8.0, 8.5, 3.2, 4.4, 5.6, 6.8, 7.2, 2.8, 5.1, 6.3]

MATERIAS = {
    "m-mat": {"id": "m-mat", "nome": "Matemática"},
    "m-fis": {"id": "m-fis", "nome": "Física"},
}
CICLOS = {
    "c-2": {"id": "c-2", "ordem": 2, "nome": "Ciclo 2", "vestibular_alvo": "ITA"},
    "c-3": {"id": "c-3", "ordem": 3, "nome": "Ciclo 3", "vestibular_alvo": "ITA"},
}

#: As tools do chat do aluno que leem as funções de domínio com número da turma.
TOOLS_DO_CHAT = {
    "minhas_notas": {},
    "meu_desempenho_em_simulado": {"simulado_id": "s-dupla"},
    "minha_evolucao": {},
    "meu_insight_do_ciclo": {},
}


# ─── O banco de mentira ──────────────────────────────────────────────────


class _Consulta(Query):
    """A consulta do fake, com o `neq` que a ficha da prova usa."""

    def neq(self, coluna, valor):
        self.filtros.append(("neq", coluna, valor))
        return self

    def _bate(self, linha):
        if any(t == "neq" and linha.get(c) == v for t, c, v in self.filtros):
            return False
        return super()._bate(linha)


class _Tabela(Tabela):
    def select(self, *colunas, count=None):
        consulta = _Consulta(self.db, self.nome, "select")
        consulta.colunas = ",".join(colunas)
        consulta.contagem = count
        return consulta


class Banco(FakeCliente):
    def table(self, nome):
        return _Tabela(self.db, nome)


def _simulado(id_, rotulo, data, materia_id, ciclo_id, *, duracao=None) -> dict:
    ciclo = CICLOS[ciclo_id]
    return {
        "id": id_, "nome": f"Simulado {rotulo}", "rotulo_curto": rotulo, "data_aplicacao": data,
        "nota_maxima": 10, "materia_id": materia_id, "tipo": "fase_2", "anulado": False,
        "e_agregado": False, "nota_confiavel": True, "motivo_nota_nao_confiavel": None,
        "ciclo_id": ciclo_id, "quiz_id": None, "duracao_media_segundos": duracao,
        # O embed que o PostgREST resolveria; o fake devolve a linha como está.
        "ciclo": {"id": ciclo_id, "ordem": ciclo["ordem"], "vestibular_alvo": ciclo["vestibular_alvo"]},
    }


def _banco_vazio() -> dict:
    return {
        "aluno": {ANA: {"id": ANA, "nome": "Ana Aluna"}, BIA: {"id": BIA, "nome": "Beatriz Colega"}},
        "materia": dict(MATERIAS),
        "ciclo": dict(CICLOS),
        "simulado": {},
        "nota": {},
        "metrica_simulado": {},
    }


def _lancar(db: dict, sim: dict, notas: dict[str, float]) -> None:
    """A prova, as notas e a linha geral de `metrica_simulado`, como o recálculo grava."""
    db["simulado"][sim["id"]] = sim
    for aluno, valor in notas.items():
        db["nota"][f"n-{aluno}-{sim['id']}"] = {
            "id": f"n-{aluno}-{sim['id']}", "aluno_id": aluno, "simulado_id": sim["id"],
            "pontuacao": valor, "presente": True, "computavel": True, "simulado": sim,
        }
    valores = list(notas.values())
    db["metrica_simulado"][sim["id"]] = {
        "id": f"met-{sim['id']}", "simulado_id": sim["id"], "recorte_tipo": "geral",
        "recorte_id": None, "media": round(statistics.mean(valores), 2),
        "mediana": round(statistics.median(valores), 2), "desvio_padrao": None,
        "n_presentes": len(valores), "n_ausentes": 0,
    }


def _com_quiz(db: dict, simulado_id: str) -> None:
    """Uma questão de quiz, para GET /me/simulado/{id}/questoes ter gabarito."""
    db["simulado"][simulado_id]["quiz_id"] = "777"
    db["questao"] = {
        "q-1": {"id": "q-1", "simulado_id": simulado_id, "posicao": 1, "texto": "Q1",
                "pontos": 1, "assunto": None},
    }


@pytest.fixture
def dupla() -> Banco:
    """Física grande nos ciclos 2 e 3; no ciclo 3, uma Matemática só da Ana e da Beatriz."""
    db = _banco_vazio()
    colegas = dict(zip(COLEGAS, VALORES, strict=True))
    _lancar(db, _simulado("s-fis-2", "ITA P1 Fís", "2026-08-20", "m-fis", "c-2"),
            {ANA: 5.0, BIA: 9.0, **colegas})
    _lancar(db, _simulado("s-fis-3", "ITA P2 Fís", "2026-10-01", "m-fis", "c-3"),
            {ANA: 6.0, BIA: 9.37, **colegas})
    _lancar(db, _simulado("s-dupla", "ITA P2 Mat", "2026-10-05", "m-mat", "c-3", duracao=3000),
            {ANA: NOTA_DA_ANA, BIA: NOTA_DA_BIA})
    return Banco(db)


def _uma_prova(n_notas: int, *, quiz: bool = False) -> Banco:
    """Uma prova de Física com a Ana (6,0) e mais `n_notas - 1` colegas."""
    db = _banco_vazio()
    valores = [6.0] + [round(2 + (i % 20) * 0.37, 2) for i in range(n_notas - 1)]
    alunos = [ANA, *(f"x-{i:02d}" for i in range(n_notas - 1))]
    _lancar(db, _simulado("s-1", "P1", "2026-10-01", "m-fis", "c-3", duracao=3000),
            dict(zip(alunos, valores, strict=True)))
    if quiz:
        _com_quiz(db, "s-1")
    return Banco(db)


# ─── O que o teste liga e desliga ────────────────────────────────────────


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    """APP_ENV=dev para o guard de boot deixar `create_app()` subir."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def enviados_a_openai(monkeypatch) -> list[dict]:
    """O dublê da OpenAI: guarda o payload que iria e devolve um bullet fixo.

    Autouse para nenhum teste daqui chegar à rede, mesmo com chave no ambiente.
    """
    enviados: list[dict] = []

    def _chamar_llm(*, api_key, modelo, stats_payload, contexto):
        enviados.append(stats_payload)
        return ["bullet novo"]

    monkeypatch.setattr(insight_aluno, "_disponivel", lambda chave: True)
    monkeypatch.setattr(
        insight_aluno,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="sk-teste", openai_modelo_insights="gpt-4o-mini"),
    )
    monkeypatch.setattr(insight_aluno, "_chamar_llm", _chamar_llm)
    return enviados


@pytest.fixture
def http(monkeypatch):
    """GET numa rota do aluno, pela camada HTTP, contra o banco que se passar."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_aluno] = lambda: SESSAO_DA_ANA
    cliente = TestClient(app)
    estado: dict = {}
    monkeypatch.setattr(rotas_me, "get_supabase", lambda: estado["banco"])

    def get(banco: Banco, caminho: str):
        estado["banco"] = banco
        resposta = cliente.get(caminho)
        assert resposta.status_code == 200, f"{caminho}: {resposta.status_code} {resposta.text}"
        return resposta.json()

    return get


def _sem_o_piso(m: pytest.MonkeyPatch) -> None:
    """O comportamento de antes de 26/10: nenhuma prova é pequena demais."""
    m.setattr(aluno_dados, "PISO_DE_ANONIMATO", 0)
    m.setattr(aluno_dados, "MINIMO_DO_GRUPO_DE_15", 0)


# ─── O detector ──────────────────────────────────────────────────────────


def _numeros(valor) -> list[float]:
    """Todo número da resposta, em qualquer profundidade."""
    if isinstance(valor, bool):
        return []
    if isinstance(valor, int | float):
        return [float(valor)]
    if isinstance(valor, dict):
        return [n for v in valor.values() for n in _numeros(v)]
    if isinstance(valor, list | tuple):
        return [n for v in valor for n in _numeros(v)]
    return []


def _o_que_entrega_a_colega(resultado) -> list[float]:
    """Os números de que a nota da Beatriz sai: ela mesma, ou a média das duas."""
    return [
        n for n in _numeros(resultado)
        if abs(n - NOTA_DA_BIA) < 0.006 or abs(n - MEDIA_DAS_DUAS) < 0.006
    ]


def _chat(banco: Banco, nome: str, args: dict) -> dict:
    resultado = tools_aluno.executar_para_aluno(nome, banco, args, aluno_id=ANA)
    # `executar_para_aluno` engole exceção e devolve {"erro"}: sem esta
    # conferência, uma tool quebrada passaria no detector por não ter número.
    assert "erro" not in resultado, f"{nome}: {resultado}"
    return resultado


# ─── 1 · A prova de duas notas ───────────────────────────────────────────


class TestProvaDeDuasNotas:
    def test_sem_o_piso_cada_rota_entrega_a_nota_da_colega(self, dupla, http, monkeypatch,
                                                           enviados_a_openai):
        """A reprodução do vazamento que a revisão de 25/10 achou, rota a rota.

        É o código de produção até este conserto, e é também a prova de que o
        detector de baixo enxerga o vazamento quando ele existe.
        """
        with monkeypatch.context() as m:
            _sem_o_piso(m)
            lista = {s["id"]: s for s in http(dupla, "/me/simulados")}
            ficha = http(dupla, "/me/simulado/s-dupla")
            evolucao = http(dupla, "/me/evolucao")
            http(dupla, "/me/insight")

        # GET /me/simulados: 2 × média − a nota da Ana.
        assert round(2 * lista["s-dupla"]["mediaGeral"] - NOTA_DA_ANA, 2) == NOTA_DA_BIA
        # GET /me/simulado/{id}: com duas notas, o "top 15%" é uma pessoa — ela.
        assert ficha["grupos"]["top15"] == NOTA_DA_BIA
        assert (ficha["posicao"], ficha["total"]) == (2, 2)
        # GET /me/evolucao: a turma de Matemática no ciclo 3 é a média das duas.
        turma = evolucao["materias"]["Matemática"]["turma"]
        assert round(2 * turma[-1] - NOTA_DA_ANA, 2) == NOTA_DA_BIA
        # GET /me/insight: o que iria à OpenAI.
        (payload,) = enviados_a_openai
        mat = next(p for p in payload["porMateria"] if p["materia"] == "Matemática")
        assert round(2 * mat["mediaTurma"] - mat["minhaNota"], 2) == NOTA_DA_BIA

        for porta, resultado in {"lista": lista, "ficha": ficha, "evolucao": evolucao,
                                 "insight": payload}.items():
            assert _o_que_entrega_a_colega(resultado), f"o detector não viu o vazamento em {porta}"

    def test_com_o_piso_nenhuma_porta_deixa_derivar_a_nota_da_colega(self, dupla, http,
                                                                      enviados_a_openai):
        portas = {
            caminho: http(dupla, caminho)
            for caminho in (
                "/me/simulados",
                "/me/simulados?incluirFaltas=true",
                "/me/simulado/s-dupla",
                "/me/simulado/s-dupla/questoes",
                "/me/evolucao",
                "/me/insight",
            )
        }
        # O chat do aluno lê as mesmas funções de domínio: o piso vale lá também.
        portas.update({f"chat: {nome}": _chat(dupla, nome, args) for nome, args in TOOLS_DO_CHAT.items()})
        assert enviados_a_openai, "o insight não chegou a montar o payload"
        portas["o que iria à OpenAI"] = list(enviados_a_openai)

        for porta, resultado in portas.items():
            assert not _o_que_entrega_a_colega(resultado), f"{porta} deixa derivar a nota da colega"

    def test_o_que_cada_rota_devolve(self, dupla, http, enviados_a_openai):
        """O contrato abaixo do piso: o número da turma vem `null`, a contagem fica."""
        lista = {s["id"]: s for s in http(dupla, "/me/simulados")}
        assert (lista["s-dupla"]["mediaGeral"], lista["s-dupla"]["nPresentes"]) == (None, 2)
        assert lista["s-dupla"]["nota"] == NOTA_DA_ANA and lista["s-dupla"]["novo"] is True
        assert lista["s-fis-3"]["mediaGeral"] is not None, "prova grande continua com a turma"

        ficha = http(dupla, "/me/simulado/s-dupla")
        assert (ficha["posicao"], ficha["percentil"], ficha["total"]) == (None, None, 2)
        assert ficha["grupos"] == {"voce": NOTA_DA_ANA, "geral": None, "top15": None, "bottom15": None}
        assert ficha["nota"] == NOTA_DA_ANA and ficha["deltaSelf"] == 1.5

        # O tempo médio é da turma, e sai pela mesma régua da ficha.
        assert http(dupla, "/me/simulado/s-dupla/questoes")["duracaoMediaSegundos"] is None

        evolucao = http(dupla, "/me/evolucao")
        assert evolucao["materias"]["Matemática"] == {"aluno": [None, NOTA_DA_ANA], "turma": [None, None]}
        assert None not in evolucao["materias"]["Física"]["turma"]

        insight = http(dupla, "/me/insight")
        assert insight["bullets"] == ["bullet novo"] and insight["cicloOrdem"] == 3
        (payload,) = enviados_a_openai
        mat = next(p for p in payload["porMateria"] if p["materia"] == "Matemática")
        fis = next(p for p in payload["porMateria"] if p["materia"] == "Física")
        assert (mat["minhaNota"], mat["mediaTurma"]) == (NOTA_DA_ANA, None)
        assert fis["mediaTurma"] == lista["s-fis-3"]["mediaGeral"]
        # A média geral da turma no ciclo é só a da prova grande.
        assert payload["geral"]["mediaTurma"] == lista["s-fis-3"]["mediaGeral"]

    def test_o_bullet_da_media_vazada_nao_volta_do_cache(self, dupla, http, monkeypatch,
                                                        enviados_a_openai):
        """O cache do insight é chaveado pelo hash do payload, e o payload mudou.

        Semeia o bullet que o insight de antes de 26/10 teria guardado — gerado
        com a média das duas notas — sob o hash daquele payload. Sem o piso ele
        volta do cache, como volta hoje em produção; com o piso, o hash é outro,
        o bullet não sai e o insight é regerado sem a média.
        """
        contexto = {"nomeAluno": SESSAO_DA_ANA["nome"]}
        with monkeypatch.context() as m:
            _sem_o_piso(m)
            ciclo, payload_velho = aluno_dados.payload_insight_ciclo(dupla, ANA)
        assert _o_que_entrega_a_colega(payload_velho)
        dupla.db["insight_aluno_ciclo"] = {
            "velho": {
                "id": "velho", "aluno_id": ANA, "ciclo_id": ciclo["id"],
                "hash_payload": hash_payload_estavel({"stats": payload_velho, "ctx": contexto}),
                "bullets": ["A turma tirou 7,94 em Matemática."], "modelo": "gpt-4o-mini",
            }
        }

        with monkeypatch.context() as m:
            _sem_o_piso(m)
            assert http(dupla, "/me/insight")["bullets"] == ["A turma tirou 7,94 em Matemática."]
        assert not enviados_a_openai, "sem o piso o bullet velho tinha de vir do cache"

        assert http(dupla, "/me/insight")["bullets"] == ["bullet novo"]
        (payload_novo,) = enviados_a_openai
        assert not _o_que_entrega_a_colega(payload_novo)


# ─── 2 · Os limites do piso ──────────────────────────────────────────────


class TestLimitesDoPiso:
    @pytest.mark.parametrize(
        "n,geral,grupos",
        [
            (2, False, False),   # a média seria a nota da colega
            (9, False, False),   # abaixo do piso da turma
            (10, True, False),   # turma no piso, mas o grupo de 15% é uma pessoa
            (19, True, False),   # o grupo é de duas: a nota da outra sai pela conta
            (20, True, True),    # o grupo é de três
        ],
    )
    def test_a_ficha_da_prova(self, n, geral, grupos):
        r = aluno_dados.detalhe_simulado_do_aluno(_uma_prova(n), ANA, "s-1")
        assert r["grupos"]["voce"] == 6.0 and r["total"] == n
        assert (r["grupos"]["geral"] is not None) is geral
        assert (r["posicao"] is not None) is geral and (r["percentil"] is not None) is geral
        assert (r["grupos"]["top15"] is not None) is grupos
        assert (r["grupos"]["bottom15"] is not None) is grupos

    @pytest.mark.parametrize("n,sai", [(2, False), (9, False), (10, True)])
    def test_o_tempo_medio_da_turma(self, n, sai):
        """Os dois caminhos de GET /me/simulado/{id}/questoes: sem quiz e com quiz."""
        sem_quiz = aluno_dados.questoes_do_aluno_no_simulado(_uma_prova(n), ANA, "s-1")
        com_quiz = aluno_dados.questoes_do_aluno_no_simulado(_uma_prova(n, quiz=True), ANA, "s-1")
        assert sem_quiz["temGabarito"] is False and com_quiz["temGabarito"] is True
        esperado = 3000.0 if sai else None
        assert sem_quiz["duracaoMediaSegundos"] == com_quiz["duracaoMediaSegundos"] == esperado
        # A régua é a da ficha da mesma prova, que sai na mesma tela.
        ficha = aluno_dados.detalhe_simulado_do_aluno(_uma_prova(n), ANA, "s-1")
        assert (ficha["grupos"]["geral"] is not None) is sai

    @pytest.mark.parametrize("n,sai", [(9, False), (10, True)])
    def test_a_lista_a_evolucao_e_o_insight(self, n, sai):
        banco = _uma_prova(n)
        (item,) = aluno_dados.simulados_do_aluno(banco, ANA)
        assert (item["mediaGeral"] is not None) is sai and item["nPresentes"] == n
        turma = aluno_dados.evolucao_do_aluno(banco, ANA)["materias"]["Física"]["turma"]
        assert (turma != [None]) is sai
        _, payload = aluno_dados.payload_insight_ciclo(banco, ANA)
        assert (payload["porMateria"][0]["mediaTurma"] is not None) is sai
        assert (payload["geral"]["mediaTurma"] is not None) is sai

    @pytest.mark.parametrize("n", [10, 19, 20, 35])
    def test_com_dez_ou_mais_notas_nada_muda(self, n, http, monkeypatch, enviados_a_openai):
        """Cada rota responde igual com e sem o piso — salvo os grupos de 15% até 19 notas."""
        banco = _uma_prova(n, quiz=True)
        caminhos = (
            "/me/simulados",
            "/me/simulados?incluirFaltas=true",
            "/me/simulado/s-1",
            "/me/simulado/s-1/questoes",
            "/me/evolucao",
            "/me/insight",
        )
        com_piso = {c: http(banco, c) for c in caminhos}
        with monkeypatch.context() as m:
            _sem_o_piso(m)
            sem_piso = {c: http(banco, c) for c in caminhos}

        grupos_com = com_piso["/me/simulado/s-1"]["grupos"]
        grupos_sem = sem_piso["/me/simulado/s-1"]["grupos"]
        if n < 20:
            # O grupo de 15% teria uma ou duas pessoas: a média dele é a nota de alguém.
            assert grupos_com["top15"] is None and grupos_com["bottom15"] is None
            assert grupos_sem["top15"] is not None and grupos_sem["bottom15"] is not None
            for grupos in (grupos_com, grupos_sem):
                grupos.pop("top15")
                grupos.pop("bottom15")
        assert com_piso == sem_piso
        assert com_piso["/me/simulado/s-1"]["posicao"] is not None
        assert com_piso["/me/simulado/s-1/questoes"]["duracaoMediaSegundos"] == 3000.0
        # O payload do insight não mudou: o hash também não, e a segunda leitura
        # veio do cache — a OpenAI foi chamada uma vez só.
        assert len(enviados_a_openai) == 1
