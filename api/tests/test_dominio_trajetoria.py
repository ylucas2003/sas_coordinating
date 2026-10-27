"""A trajetória do aluno num lugar só: `aluno_dados.trajetoria_do_aluno`.

Havia três cópias da mesma leitura — a rota `/alunos/{id}/trajetoria` (que o
`/me/trajetoria` reaproveita), a tool `trajetoria_aluno` da coordenação e o
gráfico `linha_temporal` de aluno do assistente — e ela se juntou antes de
nascer a quarta (docs/43 §4.3). O que se trava:

  1. **Quem entra na série**: só nota computável e presente, de prova que não
     foi anulada nem é agregada, com nota calculável — e a prova NÃO confiável
     fica (quem a perde é a estatística, não o histórico da pessoa).
  2. **Ordem e corte**: cronológica, e o `limite` guarda as mais recentes.
  3. **Cada consumidor devolve o que sempre devolveu**, e os três concordam
     sobre quais provas entram.
"""

from __future__ import annotations

import pytest

from app.chat.tools import artefato
from app.chat.tools import stats as tools_stats
from app.routes import alunos as rota_alunos
from app.stats import aluno_dados

from .fake_postgrest import FakeCliente

ALUNO = "aluno-1"
FISICA = "mat-fis"


def _simulado(id_: str, data: str | None, *, rotulo: str | None = None, materia: bool = True,
              nota_maxima: float | None = 10, **extra) -> dict:
    return {
        "id": id_, "nome": f"Simulado {id_}", "rotulo_curto": rotulo,
        "data_aplicacao": data, "anulado": False, "e_agregado": False,
        "nota_confiavel": True, "nota_maxima": nota_maxima,
        "materia_id": FISICA if materia else None, "tipo": "fase_1", "ciclo_id": "ciclo-4",
        # O embed `materia:materia_id(nome)` que o PostgREST devolveria.
        "materia": {"nome": "Física"} if materia else None,
        **extra,
    }


def _nota(id_: str, simulado: dict, pontuacao, *, aluno: str = ALUNO, presente: bool = True,
          computavel: bool = True) -> tuple[str, dict]:
    return id_, {"id": id_, "aluno_id": aluno, "presente": presente, "computavel": computavel,
                 "pontuacao": pontuacao, "simulado": simulado}


@pytest.fixture
def cliente() -> FakeCliente:
    notas = dict([
        _nota("n-mar", _simulado("s-mar", "2026-03-10", rotulo="P3"), 6),
        _nota("n-fev", _simulado("s-fev", "2026-02-01", materia=False, nota_maxima=12), 7),
        # A prova não confiável continua na linha do aluno.
        _nota("n-abr", _simulado("s-abr", "2026-04-05", rotulo="P4", nota_confiavel=False), "8"),
        # Sem data: vai para o começo da série, como sempre foi.
        _nota("n-sem-data", _simulado("s-sem-data", None, rotulo="P0"), 5),
        # Daqui para baixo, ninguém entra.
        _nota("n-zero", _simulado("s-zero", "2026-05-01"), 0, computavel=False),
        _nota("n-falta", _simulado("s-falta", "2026-05-02"), None, presente=False),
        _nota("n-anulado", _simulado("s-anulado", "2026-05-03", anulado=True), 9),
        _nota("n-agregado", _simulado("s-agregado", "2026-05-04", e_agregado=True), 9),
        _nota("n-sem-maxima", _simulado("s-sem-maxima", "2026-05-05", nota_maxima=0), 9),
        _nota("n-sem-pontuacao", _simulado("s-sem-pontuacao", "2026-05-06"), None),
        _nota("n-outro", _simulado("s-outro", "2026-05-07"), 10, aluno="aluno-2"),
    ])
    return FakeCliente({
        "nota": notas,
        "aluno": {ALUNO: {"id": ALUNO, "nome": "Ana"}},
        "materia": {FISICA: {"id": FISICA, "codigo": "fisica", "nome": "Física"}},
    })


# ─── 1 e 2 · A série ─────────────────────────────────────────────────────


class TestTrajetoriaDoAluno:
    def test_quem_entra_e_em_que_ordem(self, cliente):
        pontos = aluno_dados.trajetoria_do_aluno(cliente, ALUNO)
        assert [p["simuladoId"] for p in pontos] == ["s-sem-data", "s-fev", "s-mar", "s-abr"]

    def test_o_ponto_tem_tudo_que_os_consumidores_escolhem(self, cliente):
        pontos = {p["simuladoId"]: p for p in aluno_dados.trajetoria_do_aluno(cliente, ALUNO)}
        assert pontos["s-mar"] == {
            "simuladoId": "s-mar", "simulado": "Simulado s-mar", "rotuloCurto": "P3",
            "dataAplicacao": "2026-03-10", "materiaId": FISICA, "materia": "Física",
            "tipo": "fase_1", "cicloId": "ciclo-4", "nota": 6.0,
        }
        # 7 de 12 = 5,8333…, com duas casas; prova multi-matéria não tem matéria.
        assert (pontos["s-fev"]["nota"], pontos["s-fev"]["materia"]) == (5.83, None)
        # A pontuação chega do PostgREST como texto às vezes (numeric).
        assert pontos["s-abr"]["nota"] == 8.0

    def test_o_limite_guarda_as_mais_recentes(self, cliente):
        pontos = aluno_dados.trajetoria_do_aluno(cliente, ALUNO, 2)
        assert [p["simuladoId"] for p in pontos] == ["s-mar", "s-abr"]

    def test_limite_maior_que_a_serie_nao_corta(self, cliente):
        assert len(aluno_dados.trajetoria_do_aluno(cliente, ALUNO, 40)) == 4

    def test_aluno_sem_nota_e_lista_vazia(self, cliente):
        assert aluno_dados.trajetoria_do_aluno(cliente, "ninguem") == []


# ─── 3 · Os três consumidores ────────────────────────────────────────────


class TestConsumidores:
    def test_a_rota_devolve_a_forma_de_sempre(self, cliente, monkeypatch):
        monkeypatch.setattr(rota_alunos, "get_supabase", lambda: cliente)
        linhas = rota_alunos.trajetoria_aluno(ALUNO)
        assert linhas[2] == {
            "simuladoId": "s-mar", "simulado": "Simulado s-mar", "dataAplicacao": "2026-03-10",
            "materiaId": FISICA, "tipo": "fase_1", "pontuacao": 6.0,
        }
        assert all(set(l) == set(linhas[2]) for l in linhas)

    def test_a_tool_da_coordenacao_devolve_a_forma_de_sempre(self, cliente):
        r = tools_stats.trajetoria_aluno(cliente, aluno_id=ALUNO)
        assert r["total"] == 4
        assert r["trajetoria"][2] == {
            "simuladoId": "s-mar", "simulado": "Simulado s-mar", "rotuloCurto": "P3",
            "dataAplicacao": "2026-03-10", "materia": "Física", "tipo": "fase_1",
            "cicloId": "ciclo-4", "nota": 6.0,
        }

    def test_a_tool_conta_o_que_volta_depois_do_corte(self, cliente):
        r = tools_stats.trajetoria_aluno(cliente, aluno_id=ALUNO, limite=3)
        assert (r["total"], [p["simuladoId"] for p in r["trajetoria"]]) == (
            3, ["s-fev", "s-mar", "s-abr"]
        )

    def test_o_grafico_do_assistente_devolve_a_forma_de_sempre(self, cliente):
        grafico = artefato.gerar_grafico(
            cliente, tipo="linha_temporal", fonte="aluno", fonte_id=ALUNO
        )
        assert grafico["tipo"] == "linha_temporal"
        assert grafico["titulo"] == "Evolução — Ana"
        assert grafico["payload"]["alunoId"] == ALUNO
        assert grafico["payload"]["alunoNome"] == "Ana"
        assert grafico["payload"]["pontos"] == [
            {"data": None, "rotulo": "P0", "nota": 5.0, "simuladoId": "s-sem-data"},
            # Sem rótulo curto, o rótulo é o nome.
            {"data": "2026-02-01", "rotulo": "Simulado s-fev", "nota": 5.83, "simuladoId": "s-fev"},
            {"data": "2026-03-10", "rotulo": "P3", "nota": 6.0, "simuladoId": "s-mar"},
            {"data": "2026-04-05", "rotulo": "P4", "nota": 8.0, "simuladoId": "s-abr"},
        ]

    def test_os_tres_concordam_sobre_quais_provas_entram(self, cliente, monkeypatch):
        monkeypatch.setattr(rota_alunos, "get_supabase", lambda: cliente)
        da_rota = [l["simuladoId"] for l in rota_alunos.trajetoria_aluno(ALUNO)]
        da_tool = [p["simuladoId"] for p in tools_stats.trajetoria_aluno(cliente, aluno_id=ALUNO)["trajetoria"]]
        do_grafico = [
            p["simuladoId"]
            for p in artefato.gerar_grafico(
                cliente, tipo="linha_temporal", fonte="aluno", fonte_id=ALUNO
            )["payload"]["pontos"]
        ]
        assert da_rota == da_tool == do_grafico == ["s-sem-data", "s-fev", "s-mar", "s-abr"]
