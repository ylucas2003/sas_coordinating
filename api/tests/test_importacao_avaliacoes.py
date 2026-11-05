"""A importação do 1º e do 2º ano (docs/44 §3 e §4, etapa 3).

O mesmo núcleo do sync do 3º lê o curso "{ano} {1|2}o ITA/IME Avaliações": só AP e
AG entram, cada grupo de etapa vira um ciclo da série, e os nomes que o Canvas tem
de verdade precisam passar (ou ficar de fora) sem quebrar nada. Os casos saem do
levantamento de 05/11/2026 nos cursos 578 e 579.
"""

from __future__ import annotations

import asyncio

import pytest

from app.canvas_sync import mapeador, sincronizar
from app.canvas_sync.cursos import curso_do_ciclo
from app.config import _series_da_lista
from app.lembretes.aplicacoes import aluno_simulado
from app.routes import auth_canvas
from app.stats import aluno_jornada
from tests.fake_postgrest import FakeCliente

CURSO_DO_1O = {"id": 578, "name": "2026 1o ITA/IME Avaliações"}

GRUPOS = [
    {"id": 1, "name": "2026 - 1ª ETAPA - AP's"},
    {"id": 2, "name": "2026 - 1ª ETAPA - AG's"},
    {"id": 3, "name": "2026 - 3º ETAPA - AG's"},
    {"id": 4, "name": "2026 - 1ª ETAPA - ASC's"},
    {"id": 5, "name": "2025 - AR's"},
    {"id": 6, "name": "2025 - 3ª ETAPA - AP's"},
]


def _prova(id_, nome, grupo, pontos=15.0):
    return {
        "id": id_, "name": nome, "assignment_group_id": grupo, "published": True,
        "points_possible": pontos, "quiz_id": None,
    }


PROVAS = [
    _prova(101, "1_AP1 - Matemática - 09/02/2026", 1),
    _prova(102, "1_AP1 - Física - 09/02/2026", 1),
    _prova(103, "1_ AP2 - Matemática - 23/02/2026", 1, pontos=10.0),
    _prova(104, "1_AP1 - Matemática - 10/02/2026 (Atividade de Resolução)", 1, pontos=0.5),
    _prova(105, "1_AP5 - Português - 12/03/2025", 1),
    _prova(106, "1_AP6 - Biologia - 23/03/2026", 1),
    _prova(201, "1_AG2 - Matemática - 06/04/2026", 2, pontos=0.0),
    _prova(202, "1_AG1 - Inglês - 30/03/2026", 2, pontos=12.0),
    _prova(203, "1_AP3 - Física - 02/03/2026", 2),
    _prova(301, "3_AG1 - Física - 03/11/2026 ", 3, pontos=12.0),
    _prova(401, "1_ASC1 - Matemática - 28/04/2026", 4, pontos=20.0),
    _prova(501, "AR1 - Matemática - 08/12/2025", 5, pontos=20.0),
]


class FakeCanvas:
    def __init__(self, submissions=()):
        self._submissions = list(submissions)

    async def listar_sections(self, course_id):
        return [{"id": 9, "name": CURSO_DO_1O["name"]}]

    async def listar_matriculas_de_alunos(self, course_id):
        return [{
            "id": 77, "course_section_id": 9, "enrollment_state": "active",
            "created_at": "2026-01-20T10:00:00Z",
            "user": {"id": 5001, "sis_user_id": "RA-1", "name": "Aluna Teste"},
        }]

    async def listar_grupos_de_avaliacao(self, course_id):
        return GRUPOS

    async def listar_assignments(self, course_id):
        return PROVAS

    async def listar_submissions(self, course_id, *, graded_since=None):
        return self._submissions


def _banco() -> dict:
    """Um banco com o 3º já sincronizado, que é como produção está."""
    return {
        "ano_letivo": {"a26": {"id": "a26", "ano": 2026, "canvas_course_id": "577"}},
        "materia": {
            f"m-{c}": {"id": f"m-{c}", "codigo": c}
            for c in ("matematica", "fisica", "quimica", "portugues", "ingles", "redacao", "biologia")
        },
    }


def _importar(db: dict, submissions=()) -> sincronizar.ResumoSincronizacao:
    resumo = sincronizar.ResumoSincronizacao()
    asyncio.run(
        sincronizar._sincronizar_curso_simulados(
            cliente=FakeCliente(db), canvas=FakeCanvas(submissions), curso=CURSO_DO_1O,
            ano=2026, graded_since=None, resumo=resumo, serie=1,
        )
    )
    return resumo


def _por_nome(db: dict, tabela: str, campo: str = "nome") -> dict:
    return {linha[campo]: linha for linha in db.get(tabela, {}).values()}


class TestLeitura:
    @pytest.mark.parametrize(
        ("nome", "esperado"),
        [
            ("2026 - 1ª ETAPA - AP's", (2026, 1, "AP")),
            ("2026 - 3º ETAPA - AG's", (2026, 3, "AG")),
            ("2026 - 2ª ETAPA - ASC's", None),
            ("1º SIMULADO NACIONAL - 1ª FASE ITA (2026)", None),
            ("Imported Assignments", None),
        ],
    )
    def test_grupo(self, nome, esperado):
        assert mapeador.parsear_grupo_etapa(nome) == esperado

    def test_ap_e_ime_e_ag_e_ita_com_a_ap_antes(self):
        assert mapeador.ciclo_da_etapa(1, "AP") == (1, "IME")
        assert mapeador.ciclo_da_etapa(1, "AG") == (2, "ITA")
        assert mapeador.ciclo_da_etapa(3, "AG") == (6, "ITA")

    def test_curso(self):
        assert mapeador.parsear_curso_avaliacoes("2026 2o ITA/IME Avaliações") == (2026, 2)
        assert mapeador.parsear_curso_avaliacoes("2026 3o ITA/IME Simulados") is None
        assert mapeador.parsear_curso_avaliacoes("2022 2o ITA/IME Português 1") is None


class TestImportacao:
    def test_o_curso_do_3o_continua_sendo_o_do_ano(self):
        """`ano_letivo.canvas_course_id` é onde o agendamento cria provas: o curso
        do 1º ano tomando o lugar mandaria o simulado do 3º para lá."""
        db = _banco()
        _importar(db)
        assert db["ano_letivo"]["a26"]["canvas_course_id"] == "577"
        assert [(c["serie"], c["canvas_course_id"]) for c in db["curso_canvas"].values()] == [
            (1, "578")
        ]

    def test_a_turma_e_da_serie_do_curso_e_nao_divide_com_o_3o(self):
        db = _banco()
        _importar(db)
        (turma,) = db["turma"].values()
        assert (turma["serie"], turma["serie_do_curso"]) == (1, 1)

    def test_so_ap_e_ag_viram_ciclo_e_cada_etapa_tem_dois(self):
        db = _banco()
        _importar(db)
        ciclos = sorted((c["ordem"], c["vestibular_alvo"], c["serie"], c["nome"]) for c in db["ciclo"].values())
        assert ciclos == [
            (1, "IME", 1, "1ª etapa · AP · 1º ano · 2026"),
            (2, "ITA", 1, "1ª etapa · AG · 1º ano · 2026"),
            (6, "ITA", 1, "3ª etapa · AG · 1º ano · 2026"),
        ]

    def test_entram_as_provas_certas(self):
        db = _banco()
        _importar(db)
        assert set(_por_nome(db, "simulado")) == {
            "1_AP1 - Matemática - 09/02/2026",
            "1_AP1 - Física - 09/02/2026",
            "1_ AP2 - Matemática - 23/02/2026",
            "1_AP6 - Biologia - 23/03/2026",
            "1_AG2 - Matemática - 06/04/2026",
            "1_AG1 - Inglês - 30/03/2026",
            "3_AG1 - Física - 03/11/2026",
        }

    def test_atividade_de_resolucao_fica_de_fora_sem_aviso(self):
        db = _banco()
        resumo = _importar(db)
        assert not any("Resolução" in aviso for aviso in resumo.avisos)

    def test_copia_do_ano_anterior_e_prova_fora_do_grupo_viram_aviso(self):
        db = _banco()
        resumo = _importar(db)
        assert any("1_AP5 - Português - 12/03/2025" in a and "outro ano" in a for a in resumo.avisos)
        assert any("1_AP3 - Física - 02/03/2026" in a and "não bate" in a for a in resumo.avisos)
        assert any("2025 - 3ª ETAPA - AP's" in a for a in resumo.avisos)

    def test_prova_discursiva_de_0_ponto_vale_10(self):
        """Com máximo 0, `nota_real` devolveria None e a prova sumiria (docs/44 §5)."""
        db = _banco()
        _importar(db)
        provas = _por_nome(db, "simulado")
        assert provas["1_AG2 - Matemática - 06/04/2026"]["nota_maxima"] == 10.0
        assert provas["1_AG1 - Inglês - 30/03/2026"]["nota_maxima"] == 12.0

    def test_a_ap1_combinada_e_fase_1_e_a_ap2_e_fase_2(self):
        db = _banco()
        _importar(db)
        provas = _por_nome(db, "simulado")
        assert provas["1_AP1 - Matemática - 09/02/2026"]["tipo"] == "fase_1"
        assert provas["1_ AP2 - Matemática - 23/02/2026"]["tipo"] == "fase_2"

    def test_a_nota_entra(self):
        db = _banco()
        _importar(db, submissions=[{
            "assignment_id": 201, "user_id": 5001, "score": 8.5,
            "workflow_state": "graded", "missing": False,
        }])
        (nota,) = db["nota"].values()
        assert (nota["pontuacao"], nota["presente"]) == (8.5, True)


class TestCursoDoCiclo:
    def test_o_3o_le_o_campo_de_sempre(self):
        ciclo = {"serie": 3, "ano_letivo_id": "a26", "ano_letivo": {"canvas_course_id": "577"}}
        assert curso_do_ciclo(FakeCliente({}), ciclo) == "577"

    def test_ciclo_sem_serie_e_do_3o(self):
        assert curso_do_ciclo(FakeCliente({}), {"ano_letivo": {"canvas_course_id": "577"}}) == "577"

    def test_as_outras_series_leem_o_proprio_curso(self):
        db = {"curso_canvas": {"c": {"id": "c", "ano_letivo_id": "a26", "serie": 2, "canvas_course_id": "579"}}}
        ciclo = {"serie": 2, "ano_letivo_id": "a26", "ano_letivo": {"canvas_course_id": "577"}}
        assert curso_do_ciclo(FakeCliente(db), ciclo) == "579"

    def test_sem_curso_gravado_e_none_e_nunca_o_do_3o(self):
        ciclo = {"serie": 1, "ano_letivo_id": "a26", "ano_letivo": {"canvas_course_id": "577"}}
        assert curso_do_ciclo(FakeCliente({}), ciclo) is None


class TestSeries:
    def test_o_3o_esta_sempre_na_lista(self):
        assert _series_da_lista("") == {3}
        assert _series_da_lista("1, 2") == {1, 2, 3}
        assert _series_da_lista("1;9;x") == {1, 3}

    def _matriculado(self, *turmas) -> dict:
        return {
            "matricula_turma": {
                f"m{i}": {"aluno_id": "al", "turma_id": t["id"], "ativo_desde": "2026-01-20", "ativo_ate": None}
                for i, t in enumerate(turmas)
            },
            "turma": {t["id"]: t for t in turmas},
        }

    def test_vale_o_ano_mais_recente(self):
        """Matrícula não fecha: quem fez o 1º em 2025 e está no 2º em 2026 é do 2º."""
        db = self._matriculado(
            {"id": "t25", "serie_do_curso": 1, "ano_letivo": {"ano": 2025}},
            {"id": "t26", "serie_do_curso": 2, "ano_letivo": {"ano": 2026}},
        )
        assert aluno_jornada.series_atuais_do_aluno(FakeCliente(db), "al") == {2}

    def test_quem_esta_no_2o_e_no_3o_ao_mesmo_tempo_tem_as_duas(self):
        db = self._matriculado(
            {"id": "a", "serie_do_curso": 2, "ano_letivo": {"ano": 2026}},
            {"id": "b", "serie_do_curso": 3, "ano_letivo": {"ano": 2026}},
        )
        assert aluno_jornada.series_atuais_do_aluno(FakeCliente(db), "al") == {2, 3}

    def test_acesso_fechado_para_o_1o_enquanto_a_serie_nao_abre(self, monkeypatch):
        db = self._matriculado({"id": "t", "serie_do_curso": 1, "ano_letivo": {"ano": 2026}})
        monkeypatch.setenv("SERIES_COM_ACESSO_DO_ALUNO", "3")
        auth_canvas.get_settings.cache_clear()
        try:
            assert auth_canvas._acesso_liberado(FakeCliente(db), "al") is False
            monkeypatch.setenv("SERIES_COM_ACESSO_DO_ALUNO", "1,3")
            auth_canvas.get_settings.cache_clear()
            assert auth_canvas._acesso_liberado(FakeCliente(db), "al") is True
        finally:
            auth_canvas.get_settings.cache_clear()

    def test_a_trava_nao_tira_o_acesso_de_quem_ja_entrava(self):
        db_3o = self._matriculado({"id": "t", "serie_do_curso": 3, "ano_letivo": {"ano": 2026}})
        assert auth_canvas._acesso_liberado(FakeCliente(db_3o), "al") is True
        assert auth_canvas._acesso_liberado(FakeCliente({}), "sem-matricula") is True

    def test_o_lembrete_do_3o_nao_vai_para_o_1o_ano(self):
        db = {
            "turma": {
                "t3": {"id": "t3", "ano_letivo_id": "a26", "serie_do_curso": 3},
                "t1": {"id": "t1", "ano_letivo_id": "a26", "serie_do_curso": 1},
            },
            "matricula_turma": {
                "m3": {"aluno_id": "do3", "turma_id": "t3", "ativo_ate": None},
                "m1": {"aluno_id": "do1", "turma_id": "t1", "ativo_ate": None},
            },
            "aluno": {
                "do3": {"id": "do3", "nome": "Três", "email": "tres@x.com", "ativo": True},
                "do1": {"id": "do1", "nome": "Um", "email": "um@x.com", "ativo": True},
            },
        }
        audiencia = aluno_simulado.resolver_audiencia(
            FakeCliente(db), ano_letivo_ids={"a26"}, invalidos=set(), series={3}
        )
        assert [a["aluno_id"] for a in audiencia] == ["do3"]
