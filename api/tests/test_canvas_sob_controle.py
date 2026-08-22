"""Canvas sob controle (docs/18 §2): nada sobe sem alguém clicar.

O que se prova aqui é contrato, não HTTP: (1) o retry automático nunca toca
um simulado 'divergente'; (2) um simulado agendado num ciclo 'divergente'
herda o estado em vez de virar 'falhou' eterno; (3) o sync continua
escrevendo `pontuacao` do jeito antigo e a edição do coordenador sobrevive —
isso último é o trigger da 0024, provado em psql (docs/18 §2.4), e aqui só o
contrato do módulo de escrita.
"""

from __future__ import annotations

import asyncio

from app.canvas_sync import agendamento, escrita
from tests.fake_postgrest import FakeCliente


def _db(**tabelas):
    """O fake guarda cada tabela como {id: linha}."""
    base = {"simulado": {}, "ciclo": {}, "nota": {}, "evento_auditoria": {}}
    for nome, linhas in tabelas.items():
        base[nome] = {l["id"]: l for l in linhas}
    return base


class TestRetryNuncaTocaDivergente:
    def test_reprocessar_ignora_divergente(self, monkeypatch):
        db = _db(simulado=[
            {"id": "s-div", "origem": "sas", "canvas_estado": "divergente", "canvas_tentativas": 0},
            {"id": "s-fal", "origem": "sas", "canvas_estado": "falhou", "canvas_tentativas": 1},
            {"id": "s-pen", "origem": "sas", "canvas_estado": "pendente", "canvas_tentativas": 0},
        ])
        tocados: list[str] = []

        async def fake_sync(cliente, canvas, *, simulado):
            tocados.append(simulado["id"])
            return "sincronizado"

        monkeypatch.setattr(agendamento, "sincronizar_simulado_no_canvas", fake_sync)
        resultado = asyncio.run(agendamento.reprocessar_canvas_pendentes(FakeCliente(db), canvas=None))

        assert sorted(tocados) == ["s-fal", "s-pen"]
        assert "s-div" not in tocados
        assert resultado == {"sincronizados": 2, "falharam": 0}


class TestSimuladoHerdaDivergenteDoCiclo:
    def test_ciclo_divergente_nao_vira_falhou(self):
        db = _db(simulado=[{
            "id": "s1", "nome": "x", "nota_maxima": 10, "data_aplicacao": "2026-09-01",
            "external_id": None, "canvas_tentativas": 0,
            "ciclo": {"canvas_assignment_group_id": None, "canvas_estado": "divergente",
                      "ano_letivo": {"canvas_course_id": "123"}},
        }])
        estado = asyncio.run(agendamento.sincronizar_simulado_no_canvas(
            FakeCliente(db), canvas=None, simulado=db["simulado"]["s1"]
        ))
        assert estado == "divergente"
        assert db["simulado"]["s1"]["canvas_estado"] == "divergente"
        # Não queimou tentativa: não é falha transitória.
        assert db["simulado"]["s1"].get("canvas_tentativas", 0) == 0

    def test_ciclo_sem_ids_por_sync_atrasado_continua_falhou(self):
        db = _db(simulado=[{
            "id": "s1", "nome": "x", "nota_maxima": 10, "data_aplicacao": "2026-09-01",
            "external_id": None, "canvas_tentativas": 0,
            "ciclo": {"canvas_assignment_group_id": None, "canvas_estado": None,
                      "ano_letivo": {"canvas_course_id": None}},
        }])
        estado = asyncio.run(agendamento.sincronizar_simulado_no_canvas(
            FakeCliente(db), canvas=None, simulado=db["simulado"]["s1"]
        ))
        assert estado == "falhou"
        assert "rode o sync" in db["simulado"]["s1"]["canvas_erro"]


class TestMarcarDivergente:
    def test_grava_estado_e_limpa_erro(self):
        db = _db(ciclo=[{"id": "c1", "canvas_estado": "falhou", "canvas_erro": "boom"}])
        escrita.marcar_divergente(FakeCliente(db), "ciclo", "c1")
        assert db["ciclo"]["c1"]["canvas_estado"] == "divergente"
        assert db["ciclo"]["c1"]["canvas_erro"] is None


class TestEnviarSimuladoSemCanvasConfigurado:
    def test_vira_estado_nao_excecao(self, monkeypatch):
        """Canvas não configurado é 'falhou' + erro na linha — o coordenador
        não leva 500 por isso."""
        from app import config

        monkeypatch.setattr(config, "get_settings", lambda: type("S", (), {
            "canvas_base_url": "", "canvas_api_token": ""})())
        monkeypatch.setattr(escrita, "get_settings", config.get_settings)
        db = _db(simulado=[{"id": "s1", "canvas_estado": "pendente"}])
        estado = asyncio.run(escrita.enviar_simulado(FakeCliente(db), "s1"))
        assert estado == "falhou"
        assert "não configurado" in db["simulado"]["s1"]["canvas_erro"]
