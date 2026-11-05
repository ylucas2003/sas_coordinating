"""A série do curso, do ciclo e da turma (migration 0078, docs/44 §3).

Cada bloco da coordenação é uma série: "3º e cursinho", "1º ano" e "2º ano". O
1º e o 2º ano fazem provas diferentes, então nunca dividem ciclo com ninguém, e
tudo o que já estava na plataforma continua sendo do 3º.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.canvas_sync import mapeador
from app.ingest.upsert import upsert_ciclo, upsert_curso_canvas
from app.routes import alertas as rota_alertas
from app.routes import ciclos as rota_ciclos
from app.routes import dimensoes
from app.stats import alertas, ciclo_estatisticas
from tests.esquema_das_migrations import esquema
from tests.fake_postgrest import FakeCliente

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "0078_serie_do_curso_e_do_ciclo.sql"


def _ciclo(cliente: FakeCliente, *, ordem: int = 1, **extra) -> str:
    return upsert_ciclo(cliente, ano_letivo_id="ano-2026", ordem=ordem, nome="Ciclo", **extra)


class TestCursoDoSync:
    def test_reconhece_so_o_curso_de_simulados_do_3o(self):
        assert mapeador.parsear_ano_curso_simulados("2026 3o ITA/IME Simulados") == 2026

    def test_curso_de_outra_serie_nao_toma_o_lugar_do_3o(self):
        """O sync pega o curso de maior ano; com `\\d+o` no padrão, um "2o" recém-criado
        poderia desviar a sincronização de produção sem erro nenhum."""
        assert mapeador.parsear_ano_curso_simulados("2027 2o ITA/IME Simulados") is None
        assert mapeador.parsear_ano_curso_simulados("2026 1o ITA/IME Avaliações") is None


class TestCicloPorSerie:
    def test_ciclo_sem_serie_declarada_e_do_3o(self):
        """A planilha e o curso de simulados não dizem a série: são do 3º."""
        db: dict = {}
        _ciclo(FakeCliente(db))
        assert [c["serie"] for c in db["ciclo"].values()] == [3]

    def test_a_mesma_ordem_em_tres_series_sao_tres_ciclos(self):
        """É o que a antiga chave (ano, ordem) impedia: a 1ª AP do 1º ano, a do 2º e o
        Ciclo 1 do 3º seriam a mesma linha."""
        cliente = FakeCliente({})
        ids = {_ciclo(cliente, serie=serie) for serie in (1, 2, 3)}
        assert len(ids) == 3

    def test_repetir_o_upsert_nao_duplica(self):
        db: dict = {}
        cliente = FakeCliente(db)
        _ciclo(cliente, serie=1)
        _ciclo(cliente, serie=1)
        assert len(db["ciclo"]) == 1

    def test_o_ciclo_anterior_nao_atravessa_a_serie(self):
        db: dict = {}
        cliente = FakeCliente(db)
        do_1o_ano = _ciclo(cliente, serie=1, vestibular_alvo="ITA")
        do_3o_ano = _ciclo(cliente, serie=3, vestibular_alvo="ITA")
        atual = {"ordem": 2, "serie": 3, "vestibular_alvo": "ITA", "ano_letivo_id": "ano-2026"}

        anterior = ciclo_estatisticas._carregar_ciclo_anterior(cliente, atual)

        assert anterior["id"] == do_3o_ano
        assert anterior["id"] != do_1o_ano


class TestCursoCanvas:
    def test_recriar_o_curso_no_canvas_troca_o_ponteiro(self):
        """Como `upsert_ano_letivo` sempre fez: um curso por série em cada ano."""
        db: dict = {}
        cliente = FakeCliente(db)
        upsert_curso_canvas(cliente, ano_letivo_id="ano-2026", serie=3, canvas_course_id="577")
        upsert_curso_canvas(cliente, ano_letivo_id="ano-2026", serie=3, canvas_course_id="700")
        assert [c["canvas_course_id"] for c in db["curso_canvas"].values()] == ["700"]

    def test_cada_serie_tem_o_proprio_curso_no_mesmo_ano(self):
        db: dict = {}
        cliente = FakeCliente(db)
        for serie, curso in ((3, "577"), (1, "578"), (2, "579")):
            upsert_curso_canvas(cliente, ano_letivo_id="ano-2026", serie=serie, canvas_course_id=curso)
        assert len(db["curso_canvas"]) == 3


class TestMigration:
    def test_as_colunas_novas_estao_no_schema(self):
        tabelas = esquema()
        assert "serie" in tabelas.colunas("ciclo")
        assert "serie_do_curso" in tabelas.colunas("turma")
        assert {"ano_letivo_id", "serie", "canvas_course_id"} <= set(tabelas.colunas("curso_canvas"))

    def test_a_coluna_lida_pelas_estatisticas_e_liberada_para_o_mcp(self):
        """`stats/ciclo_estatisticas.py` também roda sob o papel do MCP, cuja lista é
        coluna a coluna. Sem o GRANT, `estatisticas_ciclo` falharia só em produção."""
        assert "GRANT SELECT (serie) ON ciclo TO sas_leitura;" in MIGRATION.read_text(encoding="utf-8")


class TestAlertaPorSerie:
    def _db(self) -> dict:
        return {
            "alerta": {
                "a3": {"id": "a3", "serie": 3, "resolvido": False, "categoria": "QUEDA_RENDIMENTO",
                       "severidade": "ambar", "entidade_tipo": "aluno", "entidade_id": "x",
                       "titulo": "t", "subtitulo": "s", "dados_brutos": {}, "disparado_em": "2026-11-01T10:00:00+00:00"},
                "a1": {"id": "a1", "serie": 1, "resolvido": False, "categoria": "QUEDA_RENDIMENTO",
                       "severidade": "ambar", "entidade_tipo": "aluno", "entidade_id": "y",
                       "titulo": "t", "subtitulo": "s", "dados_brutos": {}, "disparado_em": "2026-11-02T10:00:00+00:00"},
            }
        }

    def test_o_painel_de_um_bloco_so_ve_os_alertas_dele(self, monkeypatch):
        monkeypatch.setattr(rota_alertas, "get_supabase", lambda: FakeCliente(self._db()))
        assert [a.id for a in asyncio.run(rota_alertas.listar_alertas(serie=1))] == ["a1"]
        assert [a.id for a in asyncio.run(rota_alertas.listar_alertas(serie=3))] == ["a3"]

    def test_sem_serie_a_rota_devolve_todos(self, monkeypatch):
        monkeypatch.setattr(rota_alertas, "get_supabase", lambda: FakeCliente(self._db()))
        assert {a.id for a in asyncio.run(rota_alertas.listar_alertas())} == {"a1", "a3"}

    def test_cada_alerta_nasce_com_a_serie_da_entidade(self):
        db = {
            "ciclo": {"c1": {"id": "c1", "serie": 2}},
            "simulado": {"s1": {"id": "s1", "ciclo_id": "c1", "ciclo": {"serie": 2}}},
            "turma": {"t1": {"id": "t1", "serie_do_curso": 1}},
            "matricula_turma": {
                "m1": {"aluno_id": "al1", "turma_id": "t1", "ativo_desde": "2026-01-20", "ativo_ate": None},
            },
        }
        do_simulado = {"entidade_tipo": "simulado", "entidade_id": "s1"}
        do_aluno = {"entidade_tipo": "aluno", "entidade_id": "al1"}
        sem_dono = {"entidade_tipo": "sede", "entidade_id": "qualquer"}

        alertas._marcar_serie(FakeCliente(db), [do_simulado, do_aluno, sem_dono])

        assert (do_simulado["serie"], do_aluno["serie"], sem_dono["serie"]) == (2, 1, 3)


class TestBlocos:
    def _rodar(self, monkeypatch, *, turmas, matriculas, alertas_abertos=()) -> list:
        db = {
            "turma": {t["id"]: t for t in turmas},
            "matricula_turma": {f"m{i}": m for i, m in enumerate(matriculas)},
            "alerta": {f"a{i}": a for i, a in enumerate(alertas_abertos)},
        }
        cliente = FakeCliente(db)
        monkeypatch.setattr(dimensoes, "get_supabase", lambda: cliente)
        return dimensoes.listar_blocos()

    def test_so_com_o_3o_o_rail_continua_igual_ao_de_sempre(self, monkeypatch):
        """É o que permite ir ao ar antes da importação sem mudar nada na tela."""
        blocos = self._rodar(
            monkeypatch,
            turmas=[{"id": "t3", "serie_do_curso": 3}],
            matriculas=[{"aluno_id": "a", "turma_id": "t3", "ativo_desde": "2026-01-01", "ativo_ate": None}],
        )
        assert [b.serie for b in blocos] == [3]

    def test_cada_serie_com_aluno_vira_um_bloco_com_o_3o_primeiro(self, monkeypatch):
        blocos = self._rodar(
            monkeypatch,
            turmas=[
                {"id": "t3", "serie_do_curso": 3},
                {"id": "t1", "serie_do_curso": 1},
                {"id": "t2", "serie_do_curso": 2},
            ],
            matriculas=[
                {"aluno_id": "a", "turma_id": "t2", "ativo_desde": "2026-01-01", "ativo_ate": None},
                {"aluno_id": "b", "turma_id": "t1", "ativo_desde": "2026-01-01", "ativo_ate": None},
                {"aluno_id": "c", "turma_id": "t1", "ativo_desde": "2026-01-01", "ativo_ate": None},
            ],
            alertas_abertos=[{"serie": 1, "resolvido": False}, {"serie": 1, "resolvido": True}],
        )
        assert [(b.serie, b.alunos, b.alertas) for b in blocos] == [(3, 0, 0), (1, 2, 1), (2, 1, 0)]

    def test_o_aluno_conta_so_na_serie_da_turma_mais_recente(self, monkeypatch):
        """Matrícula não fecha (docs/44 §5): quem passou do 1º para o 2º tem as duas abertas."""
        blocos = self._rodar(
            monkeypatch,
            turmas=[{"id": "t1", "serie_do_curso": 1}, {"id": "t2", "serie_do_curso": 2}],
            matriculas=[
                {"aluno_id": "a", "turma_id": "t1", "ativo_desde": "2025-01-20", "ativo_ate": None},
                {"aluno_id": "a", "turma_id": "t2", "ativo_desde": "2026-01-20", "ativo_ate": None},
            ],
        )
        assert [(b.serie, b.alunos) for b in blocos] == [(3, 0), (2, 1)]


class TestCadaItemDizASerie:
    def test_o_ciclo_diz_a_serie(self):
        ciclo = rota_ciclos._linha_para_ciclo(
            {"id": "c", "nome": "n", "ordem": 1, "serie": 2, "ano_letivo": {"ano": 2026}}, []
        )
        assert ciclo.serie == 2

    def test_ciclo_criado_pelo_sas_sem_a_coluna_na_resposta_e_do_3o(self):
        ciclo = rota_ciclos._linha_para_ciclo(
            {"id": "c", "nome": "n", "ordem": 1, "ano_letivo": {"ano": 2026}}, []
        )
        assert ciclo.serie == 3
