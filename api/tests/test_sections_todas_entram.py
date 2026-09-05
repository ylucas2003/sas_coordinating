"""Toda Section do curso de simulados vira turma (decisão de 04/09/2026).

Até aqui, só entrava Section que casasse com "{série}o {trilha} {sede}". As
outras viravam um aviso no resumo e **toda matrícula nelas era pulada**: no
curso de 2026, 521 dos 1.079 alunos não existiam no SAS por estarem em
"AD Online", "MF Online", "PB", "Escolas Parceiras SAS" ou
"Proposito (Objetivo)". Sem linha em `aluno` não há lista, não há estatística,
e o login pelo Canvas responde "sem conta" — foi assim que o caso apareceu.

O que estes testes seguram:

  1. as oito sections reais de 2026 entram, cada uma com sua turma;
  2. duas sections nunca colidem na chave (sede, ano, série, trilha) — é por
     causa dessa chave que "AD Online" não pode herdar a sede "AD": cairia em
     cima de "3o ITA AD" e misturaria presencial com online;
  3. o que já está no banco não se mexe — "3o ITA AD" e "Online" continuam
     caindo exatamente na turma de sempre.
"""

from __future__ import annotations

import asyncio

from app.canvas_sync import sincronizar
from app.ingest.header import parsear_section
from tests.fake_postgrest import FakeCliente

# Os nomes reais das sections do curso 577 ("2026 3o ITA/IME Simulados"),
# lidos do Canvas em 04/09/2026.
SECTIONS_2026 = [
    "3o ITA AD",
    "3o ITA MF",
    "2026 3o ITA/IME Simulados",
    "AD Online",
    "Escolas Parceiras SAS",
    "MF Online",
    "PB",
    "Proposito (Objetivo)",
]


class TestParsearSection:
    def test_padrao_classico_continua_igual(self):
        p = parsear_section("3o ITA AD")
        assert (p.serie, p.trilha, p.sede_codigo, p.modalidade) == (3, "ITA", "AD", "presencial")

    def test_padrao_do_canvas_com_barra(self):
        p = parsear_section("3o ITA/IME MF")
        assert (p.serie, p.trilha, p.sede_codigo) == (3, "ITA/IME", "MF")

    def test_online_puro_cai_na_turma_que_ja_existe(self):
        """A turma (ONLINE, 0, 'ONLINE') tem 327 alunos desde 2025. Série e
        trilha explícitas no parser é o que faz ingest e sync concordarem."""
        p = parsear_section("Online")
        assert (p.serie, p.trilha, p.sede_codigo, p.modalidade) == (0, "ONLINE", "ONLINE", "online")

    def test_sede_com_online_no_nome_vira_sede_propria(self):
        for nome, codigo in (("AD Online", "AD_ONLINE"), ("MF Online", "MF_ONLINE")):
            p = parsear_section(nome)
            assert p.sede_codigo == codigo
            assert p.modalidade == "online"
            assert p.nome_sede == nome

    def test_codigo_de_sede_nao_carrega_pontuacao_nem_acento(self):
        p = parsear_section("Proposito (Objetivo)")
        assert p.sede_codigo == "PROPOSITO_OBJETIVO"
        assert p.nome_sede == "Proposito (Objetivo)"
        assert p.modalidade == "presencial"

    def test_nenhuma_section_real_colide_com_outra(self):
        chaves = {
            (p.sede_codigo, p.serie or 0, p.trilha or "INDEFINIDA")
            for p in map(parsear_section, SECTIONS_2026)
        }
        assert len(chaves) == len(SECTIONS_2026)


class FakeCanvas:
    """Só o que `_sincronizar_curso_simulados` chama. Sem assignment nem
    submission: o que está sob teste é a passada de sections/matrículas."""

    def __init__(self, sections, enrollments):
        self._sections = sections
        self._enrollments = enrollments

    async def listar_sections(self, course_id):
        return self._sections

    async def listar_matriculas_de_alunos(self, course_id):
        return self._enrollments

    async def listar_grupos_de_avaliacao(self, course_id):
        return []

    async def listar_assignments(self, course_id):
        return []

    async def listar_submissions(self, course_id, *, graded_since=None):
        return []


def _rodar_sync(sections, enrollments):
    db: dict = {}
    cliente = FakeCliente(db)
    resumo = sincronizar.ResumoSincronizacao()
    asyncio.run(
        sincronizar._sincronizar_curso_simulados(
            cliente=cliente,
            canvas=FakeCanvas(sections, enrollments),
            curso={"id": 577, "name": "2026 3o ITA/IME Simulados"},
            ano=2026,
            graded_since=None,
            resumo=resumo,
        )
    )
    return db, resumo


def _enrollment(id_, section_id, user_id, sis, nome):
    return {
        "id": id_,
        "course_section_id": section_id,
        "enrollment_state": "active",
        "created_at": "2026-01-20T20:24:47Z",
        "user": {"id": user_id, "sis_user_id": sis, "name": nome},
    }


class TestTodaSectionViraTurma:
    def test_oito_sections_oito_turmas(self):
        sections = [{"id": 860 + i, "name": nome} for i, nome in enumerate(SECTIONS_2026)]
        db, resumo = _rodar_sync(sections, [])
        assert len(db["turma"]) == len(SECTIONS_2026)
        assert resumo.turmas_processadas == len(SECTIONS_2026)
        assert {t["section_original"] for t in db["turma"].values()} == set(SECTIONS_2026)

    def test_aluno_de_section_ignorada_agora_entra(self):
        """O caso que abriu o assunto: matrícula ativa em "MF Online" e
        nenhuma linha em `aluno`."""
        sections = [{"id": 863, "name": "3o ITA MF"}, {"id": 865, "name": "MF Online"}]
        db, _ = _rodar_sync(
            sections,
            [_enrollment(94945, 865, 5759, "26402618", "JOSE LEVI ALEXANDRE DE PAULA SILVA")],
        )
        alunos = list(db["aluno"].values())
        assert [a["matricula"] for a in alunos] == ["26402618"]
        assert alunos[0]["canvas_user_id"] == "5759"
        turma_online = next(
            t for t in db["turma"].values() if t["section_original"] == "MF Online"
        )
        matriculas = list(db["matricula_turma"].values())
        assert [m["turma_id"] for m in matriculas] == [turma_online["id"]]

    def test_online_e_presencial_da_mesma_sede_nao_viram_a_mesma_turma(self):
        sections = [{"id": 862, "name": "3o ITA AD"}, {"id": 864, "name": "AD Online"}]
        db, _ = _rodar_sync(sections, [])
        turmas = list(db["turma"].values())
        assert len({t["sede_id"] for t in turmas}) == 2
        assert len(turmas) == 2

    def test_section_default_do_curso_nao_vira_sede_com_o_nome_do_ano(self):
        """Ela herda o nome do curso; sem tratamento nasceria uma sede
        "2026_3O_ITA_IME_SIMULADOS" — e outra no ano que vem."""
        db, _ = _rodar_sync([{"id": 857, "name": "2026 3o ITA/IME Simulados"}], [])
        assert [s["codigo"] for s in db["sede"].values()] == ["SEM_SECTION"]
