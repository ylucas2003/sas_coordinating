"""A série do curso, do ciclo e da turma (migration 0078, docs/44 §3).

Cada bloco da coordenação é uma série: "3º e cursinho", "1º ano" e "2º ano". O
1º e o 2º ano fazem provas diferentes, então nunca dividem ciclo com ninguém, e
tudo o que já estava na plataforma continua sendo do 3º.
"""

from __future__ import annotations

from pathlib import Path

from app.canvas_sync import mapeador
from app.ingest.upsert import upsert_ciclo, upsert_curso_canvas
from app.stats import ciclo_estatisticas
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
