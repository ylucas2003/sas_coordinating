"""Round-trip das gramáticas de nome SAS ↔ Canvas.

O agendamento (P1) COMPÕE nomes que o sync depois PARSEIA. Se as duas
gramáticas saírem de sincronia, o simulado criado pelo SAS vira "fora da
gramática" no sync e some silenciosamente — este teste é o que impede isso.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/ -q
"""

from datetime import date

import pytest

from app.canvas_sync.mapeador import (
    compor_nome_assignment,
    compor_nome_grupo_ciclo,
    parsear_grupo_ciclo,
    parsear_nome_assignment,
)

# (ciclo_ordem, rotulo, materia_nome, materia_codigo, data)
CASOS_ASSIGNMENT = [
    (1, "P1", "Matemática", "matematica", date(2026, 2, 8)),
    (3, "P2", "Física", "fisica", date(2026, 9, 20)),
    (10, "P27", "Química", "quimica", date(2026, 11, 3)),
    (11, "P30", "Português", "portugues", date(2026, 12, 1)),
    (2, "P5", "Inglês", "ingles", date(2026, 3, 15)),
    (4, "P12", "Redação", "redacao", date(2026, 5, 30)),
]


@pytest.mark.parametrize("ordem, rotulo, materia_nome, materia_codigo, data", CASOS_ASSIGNMENT)
def test_roundtrip_nome_assignment(ordem, rotulo, materia_nome, materia_codigo, data):
    nome = compor_nome_assignment(
        ciclo_ordem=ordem,
        rotulo_curto=rotulo,
        materia_nome=materia_nome,
        data_aplicacao=data,
    )
    parsed = parsear_nome_assignment(nome)
    assert parsed is not None, f"sync não reconheceria {nome!r}"
    assert parsed["rotulo_curto"] == rotulo
    assert parsed["materia_codigo"] == materia_codigo
    assert parsed["data_aplicacao"] == data


def test_nome_assignment_exemplo_literal():
    """O formato exato documentado em docs/08-integracao-canvas.md."""
    nome = compor_nome_assignment(
        ciclo_ordem=1,
        rotulo_curto="P1",
        materia_nome="Matemática",
        data_aplicacao=date(2026, 2, 8),
    )
    assert nome == "1_P1 - Matemática - 08/02/2026"


@pytest.mark.parametrize("ordem, vestibular", [(1, "IME"), (3, "ITA"), (11, "IME")])
def test_roundtrip_nome_grupo_ciclo(ordem, vestibular):
    nome = compor_nome_grupo_ciclo(ordem=ordem, vestibular=vestibular)
    parsed = parsear_grupo_ciclo(nome)
    assert parsed == (ordem, vestibular), f"sync não reconheceria {nome!r}"


def test_grupo_ciclo_exemplo_literal():
    assert compor_nome_grupo_ciclo(ordem=3, vestibular="ITA") == "3° CICLO - ITA"
