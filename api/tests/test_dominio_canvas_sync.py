"""O Canvas visto de dentro: pendências de um ciclo e o estado do sync.

As duas leituras moravam numa rota — `_pendencias_do_ciclo` em
`routes/ciclos.py`, o "sync atrasado" dentro do `/health/ready` — e desceram
para `canvas_sync/` porque a tool do assistente faz as mesmas perguntas
(docs/43 §4.3). O que se trava:

  1. **Pendências**: ciclo inexistente é `None` (a rota e o lote o traduzem no
     mesmo 404 de antes, sem escrever nada), o teto de 80 notas continua dito
     e a leitura não escreve.
  2. **Sync atrasado**: a idade EXATA contra o limite, o último SUCESSO (rodada
     com erro não conta), `SYNC_ALERTA_MINUTOS` lido como sempre.
  3. **O /health/ready responde igual**: mesmo status, mesmo corpo, mesma
     mensagem, nos cinco caminhos.
"""

from __future__ import annotations

import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app import main as app_main
from app.canvas_sync import estado, pendencias
from app.routes import ciclos as rota_ciclos

from .fake_postgrest import FakeCliente

COORD = {"sub": "coord-1"}


class _Request:
    client = None


class ClienteQuebrado:
    def table(self, _nome):
        raise RuntimeError("sem banco")


# ─── 1 · Pendências do ciclo ─────────────────────────────────────────────


def _nota(aluno: str, simulado: str, no_sas, no_canvas) -> dict:
    return {
        "aluno_id": aluno, "simulado_id": simulado,
        "pontuacao_sas": no_sas, "pontuacao_canvas": no_canvas,
        # O embed que o PostgREST devolveria (`aluno:aluno_id(nome)` etc.).
        "aluno": {"nome": f"Aluno {aluno}"},
        "simulado": {"nome": "P1 - Matemática", "rotulo_curto": "P1"},
    }


@pytest.fixture
def db() -> dict:
    return {
        "ciclo": {
            "c1": {"id": "c1", "nome": "Ciclo 4 · ITA · 2026",
                   "canvas_estado": "divergente", "canvas_erro": None},
            "c2": {"id": "c2", "nome": "Ciclo em dia",
                   "canvas_estado": "sincronizado", "canvas_erro": None},
        },
        "simulado": {
            "s1": {"id": "s1", "ciclo_id": "c1", "nome": "P1 - Matemática",
                   "rotulo_curto": "P1", "origem": "sas",
                   "canvas_estado": "falhou", "canvas_erro": "Client error '401 Unauthorized'"},
            # Nasceu no Canvas: nunca é pendência de escrita do SAS.
            "s2": {"id": "s2", "ciclo_id": "c1", "nome": "P2 - Física",
                   "rotulo_curto": "P2", "origem": "canvas",
                   "canvas_estado": "divergente", "canvas_erro": None},
        },
        "nota": {
            ("a1", "s1"): _nota("a1", "s1", 8, 5),
            ("a2", "s1"): _nota("a2", "s1", 7, 7),       # igual: não diverge
            ("a3", "s1"): _nota("a3", "s1", None, 6),    # SAS nunca mexeu
        },
        "evento_auditoria": {},
    }


class TestPendenciasDoCiclo:
    def test_ciclo_inexistente_e_none(self, db):
        assert pendencias.pendencias_do_ciclo(FakeCliente(db), "nao-existe") is None

    def test_le_os_tres_tipos(self, db):
        p = pendencias.pendencias_do_ciclo(FakeCliente(db), "c1")
        assert p == {
            "cicloId": "c1",
            "nome": "Ciclo 4 · ITA · 2026",
            "grupo": {"pendente": True, "estado": "divergente", "erro": None},
            "simulados": [
                {"id": "s1", "nome": "P1", "estado": "falhou",
                 "erro": "Client error '401 Unauthorized'"},
            ],
            "notas": [
                {"alunoId": "a1", "simuladoId": "s1", "aluno": "Aluno a1",
                 "simulado": "P1", "noSas": 8, "noCanvas": 5},
            ],
            "notasAlemDoTeto": 0,
            "total": 3,
        }

    def test_ciclo_em_dia_nao_tem_pendencia(self, db):
        p = pendencias.pendencias_do_ciclo(FakeCliente(db), "c2")
        assert (p["grupo"]["pendente"], p["simulados"], p["notas"], p["total"]) == (
            False, [], [], 0
        )

    def test_nao_escreve_nada(self, db):
        antes = copy.deepcopy(db)
        pendencias.pendencias_do_ciclo(FakeCliente(db), "c1")
        assert db == antes

    def test_o_teto_corta_e_diz_quanto_cortou(self, db):
        teto = pendencias.TETO_NOTAS_POR_LOTE
        for i in range(teto + 5):
            db["nota"][(f"x{i}", "s1")] = _nota(f"x{i}", "s1", 9, 1)
        p = pendencias.pendencias_do_ciclo(FakeCliente(db), "c1")
        assert len(p["notas"]) == teto
        # As 85 novas mais a de a1 = 86 divergentes; 80 vão, 6 ficam ditas.
        assert p["notasAlemDoTeto"] == 6
        assert p["total"] == 1 + 1 + teto

    def test_a_rota_ainda_expoe_o_teto(self):
        assert rota_ciclos.TETO_NOTAS_POR_LOTE == pendencias.TETO_NOTAS_POR_LOTE == 80


class TestRotasDoCicloTraduzemONone:
    def test_pendencias_da_404(self, db, monkeypatch):
        monkeypatch.setattr(rota_ciclos, "get_supabase", lambda: FakeCliente(db))
        with pytest.raises(HTTPException) as exc:
            rota_ciclos.pendencias_canvas("nao-existe", COORD)
        assert (exc.value.status_code, exc.value.detail) == (404, "ciclo nao-existe não encontrado")

    def test_o_lote_da_o_mesmo_404_sem_escrever_nada(self, db, monkeypatch):
        monkeypatch.setattr(rota_ciclos, "get_supabase", lambda: FakeCliente(db))

        async def nao_pode(*_a, **_k):
            raise AssertionError("ciclo inexistente não chega à escrita")

        for nome in ("criar_grupo_do_ciclo", "enviar_simulado", "enviar_nota"):
            monkeypatch.setattr(rota_ciclos.escrita, nome, nao_pode)

        with pytest.raises(HTTPException) as exc:
            asyncio.run(rota_ciclos.enviar_ciclo_ao_canvas_em_lote("nao-existe", _Request(), COORD))
        assert (exc.value.status_code, exc.value.detail) == (404, "ciclo nao-existe não encontrado")
        assert db["evento_auditoria"] == {}


# ─── 2 · O sync está atrasado? ───────────────────────────────────────────

AGORA = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)


def _execucoes(*linhas: tuple[str, datetime | str]) -> FakeCliente:
    return FakeCliente(
        {
            "canvas_sync_execucao": {
                i: {
                    "id": i,
                    "status": status,
                    "finalizado_em": quando if isinstance(quando, str) else quando.isoformat(),
                }
                for i, (status, quando) in enumerate(linhas)
            }
        }
    )


@pytest.fixture(autouse=True)
def _sem_variavel(monkeypatch):
    monkeypatch.delenv("SYNC_ALERTA_MINUTOS", raising=False)


class TestUltimoSync:
    def test_nunca_sincronizou_e_atraso(self):
        assert estado.ultimo_sync(_execucoes(), AGORA) == {
            "ultimoSync": None, "haMinutos": None, "limiteMinutos": 30, "atrasado": True,
        }

    def test_rodada_com_erro_nao_conta(self):
        cliente = _execucoes(("erro", AGORA - timedelta(minutes=1)))
        assert estado.ultimo_sync(cliente, AGORA)["ultimoSync"] is None

    def test_em_dia(self):
        cliente = _execucoes(("sucesso", AGORA - timedelta(minutes=4)))
        assert estado.ultimo_sync(cliente, AGORA) == {
            "ultimoSync": "2026-10-24T14:56:00+00:00",
            "haMinutos": 4,
            "limiteMinutos": 30,
            "atrasado": False,
        }

    def test_vale_o_ultimo_sucesso_mesmo_com_erro_mais_novo(self):
        cliente = _execucoes(
            ("sucesso", AGORA - timedelta(minutes=50)),
            ("sucesso", AGORA - timedelta(hours=5)),
            ("erro", AGORA - timedelta(minutes=2)),
        )
        r = estado.ultimo_sync(cliente, AGORA)
        assert (r["haMinutos"], r["atrasado"]) == (50, True)

    def test_compara_a_idade_exata_e_nao_os_minutos(self):
        """30 min e 30 s com limite 30 é atraso, embora `haMinutos` diga 30."""
        passou = estado.ultimo_sync(_execucoes(("sucesso", AGORA - timedelta(minutes=30, seconds=30))), AGORA)
        assert (passou["haMinutos"], passou["atrasado"]) == (30, True)
        no_limite = estado.ultimo_sync(_execucoes(("sucesso", AGORA - timedelta(minutes=30))), AGORA)
        assert (no_limite["haMinutos"], no_limite["atrasado"]) == (30, False)

    def test_aceita_o_z_do_fim(self):
        r = estado.ultimo_sync(_execucoes(("sucesso", "2026-10-24T14:56:00Z")), AGORA)
        assert (r["ultimoSync"], r["haMinutos"]) == ("2026-10-24T14:56:00+00:00", 4)

    def test_o_limite_vem_do_ambiente(self, monkeypatch):
        monkeypatch.setenv("SYNC_ALERTA_MINUTOS", "60")
        r = estado.ultimo_sync(_execucoes(("sucesso", AGORA - timedelta(minutes=50))), AGORA)
        assert (r["limiteMinutos"], r["atrasado"]) == (60, False)

    def test_o_limite_explicito_vence_o_ambiente(self, monkeypatch):
        monkeypatch.setenv("SYNC_ALERTA_MINUTOS", "60")
        r = estado.ultimo_sync(
            _execucoes(("sucesso", AGORA - timedelta(minutes=50))), AGORA, limite_minutos=10
        )
        assert (r["limiteMinutos"], r["atrasado"]) == (10, True)

    def test_variavel_invalida_e_erro_de_configuracao(self, monkeypatch):
        monkeypatch.setenv("SYNC_ALERTA_MINUTOS", "meia hora")
        with pytest.raises(ValueError):
            estado.limite_em_minutos()

    def test_nao_engole_erro_do_banco(self):
        with pytest.raises(RuntimeError):
            estado.ultimo_sync(ClienteQuebrado(), AGORA)


# ─── 3 · O /health/ready responde igual ──────────────────────────────────


class _SoOHistoricoQuebrado(FakeCliente):
    def table(self, nome):
        if nome == "canvas_sync_execucao":
            raise RuntimeError("tabela sumiu")
        return super().table(nome)


def _health(monkeypatch, cliente) -> tuple[int, dict]:
    monkeypatch.setattr(app_main, "get_supabase", lambda: cliente)
    rota = next(
        r for r in app_main.create_app().routes if getattr(r, "path", None) == "/health/ready"
    )
    resposta = asyncio.run(rota.endpoint())
    if isinstance(resposta, JSONResponse):
        return resposta.status_code, json.loads(resposta.body)
    return 200, resposta


def _banco(*linhas: tuple[str, datetime]) -> FakeCliente:
    cliente = _execucoes(*linhas)
    cliente.db["materia"] = {"m1": {"id": "m1"}}
    return cliente


class TestHealthReady:
    def test_em_dia_e_200(self, monkeypatch):
        quando = datetime.now(UTC) - timedelta(minutes=5, seconds=30)
        assert _health(monkeypatch, _banco(("sucesso", quando))) == (
            200,
            {"status": "ok", "banco": "ok", "ultimo_sync": quando.isoformat(), "ha_minutos": 5},
        )

    def test_atrasado_e_503_com_a_mensagem_de_sempre(self, monkeypatch):
        quando = datetime.now(UTC) - timedelta(hours=2, seconds=30)
        status, corpo = _health(monkeypatch, _banco(("sucesso", quando)))
        assert status == 503
        assert corpo == {
            "status": "degradado",
            "problemas": ["sem sync bem-sucedido há 120 min (limite 30)"],
            "banco": "ok",
            "ultimo_sync": quando.isoformat(),
            "ha_minutos": 120,
        }
        assert list(corpo) == ["status", "problemas", "banco", "ultimo_sync", "ha_minutos"]

    def test_nunca_sincronizou_e_503_sem_ha_minutos(self, monkeypatch):
        assert _health(monkeypatch, _banco(("erro", datetime.now(UTC)))) == (
            503,
            {
                "status": "degradado",
                "problemas": ["nenhuma sincronização com sucesso registrada"],
                "banco": "ok",
                "ultimo_sync": None,
            },
        )

    def test_banco_fora_e_503_sem_ler_o_sync(self, monkeypatch):
        assert _health(monkeypatch, ClienteQuebrado()) == (
            503,
            {"status": "degradado", "problemas": ["banco inacessível: RuntimeError"], "banco": "falhou"},
        )

    def test_historico_ilegivel_e_503_sem_ultimo_sync(self, monkeypatch):
        cliente = _SoOHistoricoQuebrado({"materia": {"m1": {"id": "m1"}}})
        assert _health(monkeypatch, cliente) == (
            503,
            {
                "status": "degradado",
                "problemas": ["não consegui ler o histórico de sync: RuntimeError"],
                "banco": "ok",
            },
        )

    def test_limite_do_ambiente_entra_na_mensagem(self, monkeypatch):
        monkeypatch.setenv("SYNC_ALERTA_MINUTOS", "45")
        quando = datetime.now(UTC) - timedelta(minutes=50, seconds=30)
        status, corpo = _health(monkeypatch, _banco(("sucesso", quando)))
        assert (status, corpo["problemas"]) == (503, ["sem sync bem-sucedido há 50 min (limite 45)"])

    def test_variavel_invalida_derruba_a_rota_como_antes(self, monkeypatch):
        """Erro de configuração vira 500, e não "não consegui ler o histórico"."""
        monkeypatch.setenv("SYNC_ALERTA_MINUTOS", "meia hora")
        with pytest.raises(ValueError):
            _health(monkeypatch, ClienteQuebrado())
