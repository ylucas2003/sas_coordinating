"""Progresso do aluno no acervo (`app/banco/progresso.py`).

O que este arquivo trava, em ordem de gravidade:

  1. **Um aluno não alcança o progresso de outro.** É dado pessoal de menor de
     idade, e o `aluno_id` sai do token — a rota usa `get_current_aluno`. O
     teste existe porque um filtro esquecido aqui não daria erro nenhum: daria
     o número de outra pessoa.
  2. **Todo número vem com o seu par.** "412 questões" não é progresso; "412 de
     2.693" é. O denominador sai do acervo, então ele existe mesmo para quem
     nunca marcou nada — e o estado vazio é a maioria dos alunos.
  3. **"Feitas" é `resolvida`, e só.** Uma linha de estudo pode existir só por
     causa de uma anotação ou de uma resposta de treino (0042); contá-la como
     feita inflaria o numerador sem ninguém ter marcado coisa alguma.
  4. **O buraco de acervo não vira buraco de estudo.** Par (matéria, ano) que
     não existe fica fora da grade, em vez de virar "0 de 0" — a tela precisa
     distinguir "não houve prova" de "houve e você não fez".
"""

from __future__ import annotations

import pytest

from app.banco import progresso
from app.banco.consultas import TOPICO_SEM_CLASSIFICACAO

from .fake_postgrest import FakeCliente

ALUNO = "aluno-a"
OUTRO = "aluno-b"
NOVO = "aluno-sem-nada"

# `mat_2019_q01` é MISTA: está em 1.1 e 1.2 ao mesmo tempo.
# `mat_2011_q04` não tem ligação nenhuma — é a órfã de classificação.
QUESTOES = [
    {"id": "mat_2019_q01", "materia": "Matemática", "ano": 2019},
    {"id": "mat_2019_q02", "materia": "Matemática", "ano": 2019},
    {"id": "mat_2011_q03", "materia": "Matemática", "ano": 2011},
    {"id": "mat_2011_q04", "materia": "Matemática", "ano": 2011},
    {"id": "qui_2019_q05", "materia": "Química", "ano": 2019},
]

LIGACOES = [
    {"questao_id": "mat_2019_q01", "materia": "Matemática", "topico_codigo": "1.1"},
    {"questao_id": "mat_2019_q01", "materia": "Matemática", "topico_codigo": "1.2"},
    {"questao_id": "mat_2019_q02", "materia": "Matemática", "topico_codigo": "1.1"},
    {"questao_id": "mat_2011_q03", "materia": "Matemática", "topico_codigo": "1.2"},
    {"questao_id": "qui_2019_q05", "materia": "Química", "topico_codigo": "1.1"},
]

TOPICOS = [
    {"materia": "Matemática", "codigo": "1.1", "nome": "Trigonometria",
     "bloco_nome": "Geometria", "ordem": 1},
    {"materia": "Matemática", "codigo": "1.2", "nome": "Geometria analítica",
     "bloco_nome": "Geometria", "ordem": 2},
    {"materia": "Matemática", "codigo": "9.9", "nome": "Logaritmos",
     "bloco_nome": "Álgebra", "ordem": 3},
    {"materia": "Química", "codigo": "1.1", "nome": "Estequiometria",
     "bloco_nome": "Físico-química", "ordem": 1},
]

ESTUDO = [
    {"aluno_id": ALUNO, "questao_id": "mat_2019_q01", "resolvida": True},
    {"aluno_id": ALUNO, "questao_id": "mat_2011_q04", "resolvida": True},
    # Linha que existe SÓ por causa de uma anotação: não é "feita".
    {"aluno_id": ALUNO, "questao_id": "mat_2019_q02", "resolvida": False,
     "anotacao": "revisar a conta"},
    {"aluno_id": OUTRO, "questao_id": "qui_2019_q05", "resolvida": True},
    {"aluno_id": OUTRO, "questao_id": "mat_2019_q02", "resolvida": True},
]


@pytest.fixture
def cliente() -> FakeCliente:
    return FakeCliente(
        {
            "questao_vestibular": {q["id"]: dict(q) for q in QUESTOES},
            "questao_vestibular_topico": {i: dict(l) for i, l in enumerate(LIGACOES)},
            "topico_taxonomia": {(t["materia"], t["codigo"]): dict(t) for t in TOPICOS},
            "questao_estudo_aluno": {
                (e["aluno_id"], e["questao_id"]): dict(e) for e in ESTUDO
            },
        }
    )


def materias(r) -> dict[str, tuple[int, int]]:
    return {m.materia: (m.feitas, m.total) for m in r.porMateria}


def assuntos(r, materia: str) -> dict[str, tuple[int, int]]:
    return {a.codigo: (a.feitas, a.total) for a in r.porAssunto if a.materia == materia}


def anos(r, materia: str) -> dict[int, tuple[int, int]]:
    return {a.ano: (a.feitas, a.total) for a in r.porAno if a.materia == materia}


# ─── 1 · Isolamento entre alunos ─────────────────────────────────────────


def test_um_aluno_nao_alcanca_o_progresso_de_outro(cliente):
    """O teste que o pedido exige. Sem o filtro por `aluno_id`, os dois alunos
    veriam a soma das marcações dos dois — e o número pareceria plausível."""
    a = progresso.progresso_do_aluno(cliente, ALUNO)
    b = progresso.progresso_do_aluno(cliente, OUTRO)

    assert a.feitas == 2
    assert b.feitas == 2
    # O denominador é o mesmo — é o acervo, não é de ninguém.
    assert a.total == b.total == 5
    # E o recorte por matéria não vaza de um para o outro.
    assert materias(a)["Química"] == (0, 1)
    assert materias(b)["Química"] == (1, 1)


def test_aluno_sem_marcacao_nenhuma_tem_denominador_inteiro(cliente):
    """O estado vazio é a maioria dos alunos, e é primeira classe: zero feitas,
    mas todos os totais no lugar. Uma tela sem denominador não teria o que
    ensinar."""
    r = progresso.progresso_do_aluno(cliente, NOVO)

    assert r.feitas == 0
    assert r.total == 5
    assert materias(r) == {"Matemática": (0, 4), "Química": (0, 1)}
    assert r.anos == [2011, 2019]


# ─── 2 · Todo número com o seu par ───────────────────────────────────────


def test_por_materia_traz_o_par_e_ordena_pelo_maior_buraco(cliente):
    r = progresso.progresso_do_aluno(cliente, ALUNO)

    assert materias(r) == {"Matemática": (2, 4), "Química": (0, 1)}
    # Matemática tem buraco 2, Química tem 1 — maior buraco primeiro.
    assert [m.materia for m in r.porMateria] == ["Matemática", "Química"]


def test_o_total_geral_e_a_soma_das_materias(cliente):
    r = progresso.progresso_do_aluno(cliente, ALUNO)

    assert sum(m.total for m in r.porMateria) == r.total
    assert sum(m.feitas for m in r.porMateria) == r.feitas


# ─── 3 · "Feitas" é `resolvida`, e só ────────────────────────────────────


def test_linha_de_estudo_sem_resolvida_nao_conta_como_feita(cliente):
    """`mat_2019_q02` tem linha para este aluno, com anotação e `resolvida =
    false`. Ela é "tocada", não "feita"."""
    r = progresso.progresso_do_aluno(cliente, ALUNO)

    assert materias(r)["Matemática"] == (2, 4)
    # 1.1 tem q01 (feita) e q02 (anotada, não feita).
    assert assuntos(r, "Matemática")["1.1"] == (1, 2)


def test_marcacao_de_questao_que_saiu_do_acervo_nao_infla(cliente):
    """`feitas` nunca pode passar de `total`: uma barra de 103% parece defeito
    de código, e o aluno não tem como saber que a questão foi removida."""
    cliente.db["questao_estudo_aluno"][(ALUNO, "questao_apagada")] = {
        "aluno_id": ALUNO,
        "questao_id": "questao_apagada",
        "resolvida": True,
    }

    r = progresso.progresso_do_aluno(cliente, ALUNO)

    assert r.feitas == 2
    assert r.feitas <= r.total


# ─── 4 · Assunto: a mista soma nos dois, e a órfã não some ───────────────


def test_soma_dos_assuntos_passa_do_total_por_causa_da_mista(cliente):
    """Não é bug: questão mista caiu nos dois assuntos, e dividir a ocorrência
    pela metade subestimaria ambos (docs/22 §1.5). É também a razão de esta
    lista nunca virar pizza nem barra empilhada em 100%."""
    r = progresso.progresso_do_aluno(cliente, ALUNO)
    da_materia = assuntos(r, "Matemática")

    assert sum(total for _, total in da_materia.values()) > materias(r)["Matemática"][1]


def test_topico_que_nunca_caiu_continua_na_lista(cliente):
    r = progresso.progresso_do_aluno(cliente, ALUNO)
    assert assuntos(r, "Matemática")["9.9"] == (0, 0)


def test_as_sem_classificacao_viram_linha_clicavel(cliente):
    """Com o código sentinela que `GET /banco/questoes` aceita como filtro —
    senão a linha seria um número que o aluno vê e não consegue abrir."""
    r = progresso.progresso_do_aluno(cliente, ALUNO)
    orfas = assuntos(r, "Matemática")[TOPICO_SEM_CLASSIFICACAO]

    assert orfas == (1, 1)
    linha = next(a for a in r.porAssunto if a.codigo == TOPICO_SEM_CLASSIFICACAO)
    assert linha.nome == progresso.NOME_SEM_CLASSIFICACAO


def test_quimica_nao_tem_linha_de_sem_classificacao(cliente):
    """A linha das órfãs só aparece na matéria que TEM órfã. Emiti-la sempre
    encheria a tela de "0 de 0"."""
    r = progresso.progresso_do_aluno(cliente, ALUNO)
    assert TOPICO_SEM_CLASSIFICACAO not in assuntos(r, "Química")


# ─── 5 · A grade por ano ─────────────────────────────────────────────────


def test_grade_por_ano_traz_so_o_par_que_existe_no_acervo(cliente):
    """Química não teve prova em 2011. O par tem de FALTAR, e não vir "0 de 0":
    a tela desenha ausência de acervo diferente de ausência de estudo."""
    r = progresso.progresso_do_aluno(cliente, ALUNO)

    assert anos(r, "Matemática") == {2011: (1, 2), 2019: (1, 2)}
    assert anos(r, "Química") == {2019: (0, 1)}
    assert 2011 not in anos(r, "Química")


def test_anos_e_o_dominio_da_grade_e_nao_o_que_o_aluno_tocou(cliente):
    """O eixo x sai do acervo. Se saísse das marcações, um aluno que só mexeu em
    2019 veria uma grade de uma coluna — e concluiria que o banco só tem 2019."""
    r = progresso.progresso_do_aluno(cliente, NOVO)
    assert r.anos == [2011, 2019]
