"""Cadastro de aluno no Canvas (docs/46).

O que se prova aqui é o que erra calado: o pacote da série montado a partir
dos nomes de curso (a section padrão do 3º é a sede fantasma), a planilha
lida como uma pessoa a escreve (";" do Excel, matrícula que virou número),
o lote que nunca reescreve conta existente, e o cadastro de um aluno que
pode ser repetido depois de falhar no meio. O HTTP de verdade com o Canvas
NÃO é testado aqui — é a §5 do docs/46, no curso sandbox.
"""

from __future__ import annotations

import asyncio
import csv
import io
import zipfile

import httpx
import pytest
from fastapi import HTTPException
from openpyxl import Workbook
from starlette.requests import Request

from app.auth import get_current_administrador
from app.canvas_sync import cadastro
from app.routes import cadastro_canvas
from tests.fake_postgrest import FakeCliente

# ─── O Canvas de 2026, em miniatura ───────────────────────────────────────

CURSOS = [
    {"id": 577, "name": "2026 3o ITA/IME Simulados", "sis_course_id": "577"},
    {"id": 559, "name": "2026 3o ITA/IME Matemática 1", "sis_course_id": "559"},
    {"id": 564, "name": "2026 3o ITA/IME Física 1", "sis_course_id": "564"},
    {"id": 578, "name": "2026 1o ITA/IME Avaliações", "sis_course_id": "578"},
    {"id": 579, "name": "2026 2o ITA/IME Avaliações", "sis_course_id": "579"},
    # Não é curso de série: fica fora de todo pacote.
    {"id": 581, "name": "SAS Preparatório ITA/IME 2026", "sis_course_id": "581"},
    # Outro ano: fica fora do pacote de 2026.
    {"id": 551, "name": "2025 3o ITA/IME Simulados", "sis_course_id": "551"},
]

SECTIONS = {
    "577": [
        {"id": 862, "name": "3o ITA AD", "sis_section_id": "862"},
        {"id": 864, "name": "AD Online", "sis_section_id": "864"},
        {"id": 868, "name": "Proposito (Objetivo)", "sis_section_id": "868"},
        # A section padrão — a sede fantasma.
        {"id": 857, "name": "2026 3o ITA/IME Simulados", "sis_section_id": "857"},
    ],
    "578": [{"id": 858, "name": "2026 1o ITA/IME Avaliações", "sis_section_id": "858a"}],
    "579": [{"id": 859, "name": "2026 2o ITA/IME Avaliações", "sis_section_id": "859"}],
}


def _pacotes() -> dict[int, cadastro.Pacote]:
    return cadastro.montar_pacotes(CURSOS, SECTIONS, ano=2026)


def _erro_http(status: int, corpo: dict | None = None) -> httpx.HTTPStatusError:
    requisicao = httpx.Request("POST", "https://canvas.test/api/v1/x")
    resposta = httpx.Response(status, json=corpo or {}, request=requisicao)
    return httpx.HTTPStatusError("erro", request=requisicao, response=resposta)


class CanvasFalso:
    """Só os métodos que o cadastro usa, com o estado que eles mudam."""

    def __init__(self, *, usuarios: dict[str, dict] | None = None, falhar_em: set[str] | None = None):
        self.usuarios = usuarios or {}          # sis_user_id → usuário
        self.matriculas: list[dict] = []        # o que já existe ou foi criado
        self.falhar_em = falhar_em or set()     # course_ids cuja matrícula falha
        self.criados: list[dict] = []
        self.imports: list[bytes] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def listar_cursos_para_cadastro(self, account_id):
        return CURSOS

    async def listar_sections(self, course_id):
        return SECTIONS.get(str(course_id), [])

    async def obter_usuario_por_sis(self, sis):
        return self.usuarios.get(sis)

    async def listar_matriculas_ativas_do_usuario(self, user_id):
        return [m for m in self.matriculas if m["user_id"] == user_id]

    async def criar_usuario_aluno(self, account_id, *, nome, matricula, email):
        usuario = {"id": 9000 + len(self.criados), "name": nome, "sis_user_id": matricula}
        self.criados.append({"nome": nome, "matricula": matricula, "email": email})
        self.usuarios[matricula] = usuario
        return usuario

    async def matricular_aluno(self, course_id, user_id, *, section_id=None):
        if course_id in self.falhar_em:
            raise _erro_http(400, {"errors": [{"message": "curso fechado para matrícula"}]})
        secao = section_id or f"padrao-{course_id}"
        self.matriculas.append({"user_id": user_id, "course_id": course_id, "course_section_id": secao})
        return {"id": len(self.matriculas)}

    async def enviar_sis_import(self, account_id, *, arquivo_zip):
        self.imports.append(arquivo_zip)
        return {"id": 4242, "workflow_state": "created", "progress": 0}


# ─── O pacote da série ────────────────────────────────────────────────────


class TestPacote:
    def test_terceiro_tem_todos_os_cursos_da_serie_e_a_sede_no_de_provas(self):
        p = _pacotes()[3]
        assert {c.id for c in p.cursos} == {"577", "559", "564"}
        assert p.curso_de_provas is not None and p.curso_de_provas.id == "577"
        assert p.exige_sede

    def test_a_section_padrao_nao_e_sede(self):
        """Quem cai nela vira "Sem section no Canvas" no SAS (06/11/2026)."""
        nomes = [s.nome for s in _pacotes()[3].sedes]
        assert "2026 3o ITA/IME Simulados" not in nomes
        assert nomes == ["3o ITA AD", "AD Online", "Proposito (Objetivo)"]

    def test_primeiro_e_segundo_nao_pedem_sede(self):
        pacotes = _pacotes()
        for serie in (1, 2):
            assert [c.id for c in pacotes[serie].cursos] == [str(577 + serie)]
            assert not pacotes[serie].exige_sede

    def test_curso_sem_serie_e_outro_ano_ficam_fora(self):
        ids = {c.id for p in _pacotes().values() for c in p.cursos}
        assert "581" not in ids and "551" not in ids

    def test_anos_oferecidos_cortam_os_cursos_mortos(self):
        assert cadastro.anos_oferecidos([2027, 2026, 2025, 2021], ano_atual=2026) == [2027, 2026]
        # Janeiro, antes de a escola criar o ano: fica o mais novo.
        assert cadastro.anos_oferecidos([2026, 2025], ano_atual=2027) == [2026]

    def test_ano_padrao(self):
        assert cadastro.ano_padrao([2027, 2026], "") == 2027
        assert cadastro.ano_padrao([2027, 2026], "2026") == 2026
        # Configurado, mas sem curso no Canvas: não vale.
        assert cadastro.ano_padrao([2027, 2026], "2024") == 2027

    def test_curso_sem_sis_id_nao_cabe_no_lote(self):
        cursos = [*CURSOS[:2], {"id": 600, "name": "2026 3o ITA/IME Redação", "sis_course_id": None}]
        p = cadastro.montar_pacotes(cursos, SECTIONS, ano=2026)[3]
        assert cadastro.problemas_do_pacote_no_lote(p) == [
            "o curso 2026 3o ITA/IME Redação não tem SIS ID no Canvas"
        ]


# ─── Texto ────────────────────────────────────────────────────────────────


class TestSede:
    sedes = _pacotes()[3].sedes

    @pytest.mark.parametrize("valor", ["3o ITA AD", "3O ita ad", "862", " 3o  ITA AD "])
    def test_por_nome_id_ou_espacos(self, valor):
        sede, erro = cadastro.achar_sede(valor, self.sedes)
        assert erro is None and sede is not None and sede.id == "862"

    def test_palavra_unica_acha(self):
        sede, _ = cadastro.achar_sede("Propósito", self.sedes)
        assert sede is not None and sede.id == "868"

    def test_palavra_que_casa_com_duas_e_erro_e_nao_chute(self):
        sede, erro = cadastro.achar_sede("AD", self.sedes)
        assert sede is None and "ambígua" in erro

    def test_inexistente_lista_as_sedes(self):
        sede, erro = cadastro.achar_sede("Aldeota", self.sedes)
        assert sede is None and "AD Online" in erro


@pytest.mark.parametrize(
    ("valor", "serie"),
    [("3", 3), (3, 3), ("3º", 3), ("3o", 3), ("3ª série", 3), ("3º ano", 3), ("1° ano", 1),
     ("2a serie", 2), ("4", None), ("terceiro", None), ("", None), ("2026", None)],
)
def test_serie(valor, serie):
    assert cadastro.normalizar_serie(valor) == serie


class TestMatricula:
    def test_oito_digitos(self):
        assert cadastro.validar_matricula(" 12345678 ") == ("12345678", None)

    def test_sete_digitos_explica_o_zero_que_o_excel_comeu(self):
        _, erro = cadastro.validar_matricula("1234567")
        assert "zero à esquerda" in erro

    def test_letra(self):
        _, erro = cadastro.validar_matricula("1234567A")
        assert "não é dígito" in erro


@pytest.mark.parametrize(
    ("digitado", "canvas", "bate"),
    [
        ("Ana Beatriz Souza", "ANA BEATRIZ SOUZA", True),
        ("Ana Souza", "Ana Beatriz de Souza", True),
        ("José Araújo", "Jose Araujo", True),
        ("Ana Souza", "Pedro Lima", False),
        ("Ana Souza", "Ana Lima", False),
        ("", "Ana", False),
    ],
)
def test_nomes_batem(digitado, canvas, bate):
    assert cadastro.nomes_batem(digitado, canvas) is bate


# ─── A planilha ───────────────────────────────────────────────────────────


class TestPlanilha:
    def test_csv_do_excel_em_portugues(self):
        """Ponto e vírgula, cabeçalho com acento, cp1252 e linha em branco."""
        texto = "Matrícula;Nome;E-mail;Série;Sede\n12345678;João Ávila;j@x.com;3º;AD Online\n\n"
        linhas = cadastro.ler_planilha(texto.encode("cp1252"), "lote.csv")
        assert linhas == [{
            "linha": 2, "matricula": "12345678", "nome": "João Ávila",
            "email": "j@x.com", "serie": "3º", "sede": "AD Online",
        }]

    def test_xlsx_com_matricula_numerica(self):
        livro = Workbook()
        folha = livro.active
        folha.append(["matricula", "nome", "serie"])
        folha.append([12345678, "Ana", 1])
        folha.append([12345679.0, "Bia", 2])
        buffer = io.BytesIO()
        livro.save(buffer)
        linhas = cadastro.ler_planilha(buffer.getvalue(), "lote.xlsx")
        assert [linha["matricula"] for linha in linhas] == ["12345678", "12345679"]
        assert [linha["linha"] for linha in linhas] == [2, 3]

    def test_coluna_faltando(self):
        with pytest.raises(ValueError, match="serie"):
            cadastro.ler_planilha(b"matricula,nome\n12345678,Ana\n", "lote.csv")

    def test_so_cabecalho(self):
        with pytest.raises(ValueError, match="só tem o cabeçalho"):
            cadastro.ler_planilha(b"matricula,nome,serie\n", "lote.csv")


# ─── Linhas do lote ───────────────────────────────────────────────────────


def _linha(**campos):
    base = {"linha": 2, "matricula": "12345678", "nome": "Ana Souza", "email": "ana@x.com",
            "serie": "3", "sede": "AD Online"}
    return cadastro.validar_linha({**base, **campos}, _pacotes(), ano=2026)


class TestLinhaDoLote:
    def test_linha_boa(self):
        linha = _linha()
        assert linha.situacao == "nova" and linha.sede is not None and linha.sede.id == "864"

    def test_terceiro_sem_sede_e_erro(self):
        assert "falta a sede" in _linha(sede="").erros

    def test_primeiro_ano_com_sede_so_avisa(self):
        linha = _linha(serie="1", sede="AD Online")
        assert linha.situacao == "nova" and linha.sede is None
        assert "sede ignorada" in linha.avisos[0]

    def test_serie_sem_curso_no_ano(self):
        pacotes = {s: p for s, p in _pacotes().items() if s != 2}
        linha = cadastro.validar_linha({"matricula": "12345678", "nome": "A", "serie": "2"}, pacotes, ano=2026)
        assert "não há curso do 2º ano de 2026" in linha.erros[0]

    def test_repetida_marca_as_duas(self):
        linhas = [_linha(linha=2), _linha(linha=5)]
        cadastro.marcar_repetidas(linhas)
        assert all(linha.situacao == "erro" for linha in linhas)
        assert "linhas 2, 5" in linhas[0].erros[0]

    def test_conta_nova_sem_email_e_erro(self):
        linha = _linha(email="")
        cadastro.aplicar_existentes([linha], {})
        assert linha.situacao == "erro" and "e-mail" in linha.erros[0]

    def test_conta_existente_dispensa_email_e_avisa_nome_diferente(self):
        linha = _linha(email="")
        cadastro.aplicar_existentes([linha], {"12345678": cadastro.ContaExistente("77", "Pedro Lima")})
        assert linha.situacao == "existente"
        assert linha.nome_no_canvas == "Pedro Lima"
        assert "Pedro Lima" in linha.avisos[0]


# ─── O lote como SIS Import ───────────────────────────────────────────────


def _ler_csv(texto: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(texto)))


class TestCsvDoLote:
    def test_conta_existente_nao_entra_em_users_csv(self):
        nova, existente = _linha(matricula="11111111"), _linha(matricula="22222222")
        cadastro.aplicar_existentes(
            [nova, existente], {"22222222": cadastro.ContaExistente("77", "Ana Souza")}
        )
        usuarios = _ler_csv(cadastro.montar_csv_usuarios([nova]))
        assert [u["user_id"] for u in usuarios] == ["11111111"]
        assert usuarios[0]["login_id"] == "11111111"
        assert usuarios[0]["canvas_password_notification"] == "true"
        assert usuarios[0]["authentication_provider_id"] == "canvas"

    def test_matriculas_usam_sis_id_e_a_sede_so_no_curso_de_provas(self):
        linha = _linha()
        matriculas = _ler_csv(cadastro.montar_csv_matriculas([linha], _pacotes()))
        por_curso = {m["course_id"]: m["section_id"] for m in matriculas}
        assert por_curso == {"577": "864", "559": "", "564": ""}
        assert {m["status"] for m in matriculas} == {"active"}

    def test_section_usa_a_sis_id_e_nao_o_id(self):
        """578 tem section 858 com SIS ID "858a": o CSV só entende a SIS ID."""
        linha = _linha(serie="1")
        matriculas = _ler_csv(cadastro.montar_csv_matriculas([linha], _pacotes()))
        assert matriculas == [{"course_id": "578", "user_id": "12345678", "role": "student",
                               "section_id": "", "status": "active"}]

    def test_zip_sem_conta_nova_nao_leva_users_csv(self):
        linha = _linha()
        cadastro.aplicar_existentes([linha], {"12345678": cadastro.ContaExistente("77", "Ana Souza")})
        with zipfile.ZipFile(io.BytesIO(cadastro.montar_zip_do_lote([linha], _pacotes()))) as z:
            assert z.namelist() == ["enrollments.csv"]

    def test_linha_com_erro_nao_entra(self):
        boa, ruim = _linha(matricula="11111111"), _linha(matricula="123")
        texto = cadastro.montar_csv_matriculas([boa, ruim], _pacotes())
        assert "123," not in texto and "11111111" in texto


@pytest.mark.parametrize(
    ("estado_canvas", "estado"),
    [("importing", "processando"), ("created", "processando"), ("imported", "concluido"),
     ("imported_with_messages", "concluido_com_avisos"), ("failed_with_messages", "falhou"),
     ("aborted", "falhou")],
)
def test_resumo_do_sis_import(estado_canvas, estado):
    resumo = cadastro.resumir_sis_import({
        "id": 7, "workflow_state": estado_canvas, "progress": 40,
        "data": {"counts": {"users": 3, "enrollments": 57}},
        "processing_errors": [["enrollments.csv", "Usuário 1 não existe"]],
    })
    assert resumo["estado"] == estado
    assert (resumo["contas"], resumo["matriculas"]) == (3, 57)
    assert resumo["erros"] == ["Usuário 1 não existe"]


# ─── Um aluno por vez ─────────────────────────────────────────────────────


def _cadastrar(canvas, *, matricula="12345678", nome="Ana Souza", email="ana@x.com",
               serie=3, sede_nome="AD Online", confirmar=False):
    pacote = _pacotes()[serie]
    sede = next((s for s in pacote.sedes if s.nome == sede_nome), None)
    return asyncio.run(cadastro.cadastrar_aluno(
        canvas, account_id="1", pacote=pacote, sede=sede, matricula=matricula,
        nome=nome, email=email, confirmar_nome=confirmar,
    ))


class TestCadastrarUmAluno:
    def test_conta_nova_matricula_em_tudo_e_a_sede_so_no_de_provas(self):
        canvas = CanvasFalso()
        resultado = _cadastrar(canvas)
        assert resultado["conta"] == "criada" and resultado["email_enviado"] and resultado["completo"]
        assert canvas.criados == [{"nome": "Ana Souza", "matricula": "12345678", "email": "ana@x.com"}]
        secoes = {m["course_id"]: m["course_section_id"] for m in canvas.matriculas}
        assert secoes == {"577": "864", "559": "padrao-559", "564": "padrao-564"}

    def test_conta_nova_sem_email_nao_escreve_nada(self):
        canvas = CanvasFalso()
        with pytest.raises(cadastro.EmailObrigatorio):
            _cadastrar(canvas, email=None)
        assert canvas.criados == [] and canvas.matriculas == []

    def test_matricula_de_outra_pessoa_para_antes_de_escrever(self):
        canvas = CanvasFalso(usuarios={"12345678": {"id": 77, "name": "Pedro Lima"}})
        with pytest.raises(cadastro.NomeNaoBate) as erro:
            _cadastrar(canvas)
        assert erro.value.nome_no_canvas == "Pedro Lima"
        assert canvas.matriculas == []

    def test_conta_existente_confirmada_nao_e_recriada_nem_alterada(self):
        canvas = CanvasFalso(usuarios={"12345678": {"id": 77, "name": "Pedro Lima"}})
        resultado = _cadastrar(canvas, confirmar=True, email=None)
        assert resultado["conta"] == "existente" and not resultado["email_enviado"]
        assert resultado["nome_no_canvas"] == "Pedro Lima"
        assert canvas.criados == []
        assert len(canvas.matriculas) == 3

    def test_falha_no_meio_e_repetir_faz_so_o_que_falta(self):
        canvas = CanvasFalso(falhar_em={"559"})
        primeira = _cadastrar(canvas)
        assert not primeira["completo"]
        por_curso = {c["id"]: c for c in primeira["cursos"]}
        assert por_curso["559"]["estado"] == "falhou"
        assert por_curso["559"]["detalhe"] == "curso fechado para matrícula"

        canvas.falhar_em.clear()
        segunda = _cadastrar(canvas)
        estados = {c["id"]: c["estado"] for c in segunda["cursos"]}
        assert estados == {"577": "ja_estava", "559": "matriculado", "564": "ja_estava"}
        assert segunda["conta"] == "existente" and segunda["completo"]
        assert len(canvas.criados) == 1 and len(canvas.matriculas) == 3

    def test_outra_sede_nao_vira_duas_sedes(self):
        canvas = CanvasFalso(usuarios={"12345678": {"id": 77, "name": "Ana Souza"}})
        canvas.matriculas.append({"user_id": "77", "course_id": "577", "course_section_id": "862"})
        resultado = _cadastrar(canvas, sede_nome="AD Online")
        estados = {c["id"]: c["estado"] for c in resultado["cursos"]}
        assert estados["577"] == "outra_sede"
        assert not resultado["completo"]
        assert not any(m["course_section_id"] == "864" for m in canvas.matriculas)


# ─── As rotas ─────────────────────────────────────────────────────────────


ADMINISTRADOR = {"sub": "u-admin", "tipo": "coordenador", "papel": "administrador"}


def _request() -> Request:
    return Request({"type": "http", "client": ("10.0.0.1", 0), "headers": []})


@pytest.fixture
def ambiente(monkeypatch):
    canvas = CanvasFalso()
    db = {"aluno": {}, "evento_auditoria": {}}
    monkeypatch.setattr(cadastro, "abrir_canvas", lambda: canvas)
    monkeypatch.setattr(cadastro_canvas, "get_supabase", lambda: FakeCliente(db))
    monkeypatch.setattr(
        cadastro_canvas, "get_settings",
        lambda: type("S", (), {"canvas_account_id": "1", "canvas_ano_vigente": "2026"})(),
    )
    return canvas, db


def test_o_router_inteiro_e_de_administrador():
    """Nenhuma rota daqui é de coordenação: o token cria login na conta do colégio."""
    assert any(d.dependency is get_current_administrador for d in cadastro_canvas.router.dependencies)


class TestRotaDoLote:
    def test_envio_recusa_o_lote_inteiro_se_uma_linha_tem_erro(self, ambiente):
        canvas, _ = ambiente
        corpo = cadastro_canvas.EnvioDoLoteBody(ano=2026, linhas=[
            {"matricula": "11111111", "nome": "Ana", "email": "a@x.com", "serie": "3", "sede_id": "864"},
            {"matricula": "123", "nome": "Bia", "email": "b@x.com", "serie": "3", "sede_id": "864"},
        ])
        with pytest.raises(HTTPException) as erro:
            asyncio.run(cadastro_canvas.enviar_lote(corpo, _request(), ADMINISTRADOR))
        assert erro.value.status_code == 422
        assert canvas.imports == []

    def test_envio_sobe_um_import_e_audita_sem_nome_nem_email(self, ambiente):
        canvas, db = ambiente
        # Já tem conta: o SAS sabe sem perguntar ao Canvas.
        db["aluno"]["a1"] = {"id": "a1", "matricula": "22222222", "nome": "Bia Lima",
                             "canvas_user_id": "500"}
        corpo = cadastro_canvas.EnvioDoLoteBody(ano=2026, linhas=[
            {"matricula": "11111111", "nome": "Ana Souza", "email": "a@x.com", "serie": "3", "sede_id": "864"},
            {"matricula": "22222222", "nome": "Bia Lima", "serie": "1"},
        ])
        resposta = asyncio.run(cadastro_canvas.enviar_lote(corpo, _request(), ADMINISTRADOR))
        assert resposta["id"] == "4242" and resposta["linhas"]["novas"] == 1
        assert resposta["linhas"]["existentes"] == 1

        with zipfile.ZipFile(io.BytesIO(canvas.imports[0])) as z:
            usuarios = _ler_csv(z.read("users.csv").decode())
            matriculas = _ler_csv(z.read("enrollments.csv").decode())
        assert [u["user_id"] for u in usuarios] == ["11111111"]
        assert {(m["user_id"], m["course_id"]) for m in matriculas} == {
            ("11111111", "577"), ("11111111", "559"), ("11111111", "564"), ("22222222", "578"),
        }

        (evento,) = db["evento_auditoria"].values()
        assert evento["acao"] == "lote_enviado_ao_canvas"
        assert "Ana" not in str(evento["detalhe"]) and "@" not in str(evento["detalhe"])


class TestRotaDeUmAluno:
    def test_nome_diferente_vira_409_com_o_nome_do_canvas(self, ambiente):
        canvas, _ = ambiente
        canvas.usuarios["12345678"] = {"id": 77, "name": "Pedro Lima"}
        corpo = cadastro_canvas.CadastroDeAlunoBody(
            matricula="12345678", nome="Ana Souza", email="a@x.com", serie=3, sede_id="864"
        )
        with pytest.raises(HTTPException) as erro:
            asyncio.run(cadastro_canvas.cadastrar_um_aluno(corpo, _request(), ADMINISTRADOR))
        assert erro.value.status_code == 409 and "Pedro Lima" in erro.value.detail

    def test_terceiro_sem_sede_e_422_antes_de_tocar_o_canvas(self, ambiente):
        canvas, _ = ambiente
        corpo = cadastro_canvas.CadastroDeAlunoBody(
            matricula="12345678", nome="Ana Souza", email="a@x.com", serie=3
        )
        with pytest.raises(HTTPException) as erro:
            asyncio.run(cadastro_canvas.cadastrar_um_aluno(corpo, _request(), ADMINISTRADOR))
        assert erro.value.status_code == 422
        assert canvas.criados == []

    def test_sucesso_audita_a_matricula_e_nao_o_nome(self, ambiente):
        _, db = ambiente
        corpo = cadastro_canvas.CadastroDeAlunoBody(
            matricula="12345678", nome="Ana Souza", email="a@x.com", serie=3, sede_id="864"
        )
        resultado = asyncio.run(cadastro_canvas.cadastrar_um_aluno(corpo, _request(), ADMINISTRADOR))
        assert resultado["completo"]
        (evento,) = db["evento_auditoria"].values()
        assert evento["detalhe"]["matricula"] == "12345678"
        assert evento["detalhe"]["matriculado"] == 3
        assert "Ana" not in str(evento["detalhe"]) and "@" not in str(evento["detalhe"])

    def test_matricula_de_sete_digitos_e_recusada_no_corpo(self):
        with pytest.raises(ValueError, match="zero à esquerda"):
            cadastro_canvas.CadastroDeAlunoBody(matricula="1234567", nome="Ana", serie=3)
