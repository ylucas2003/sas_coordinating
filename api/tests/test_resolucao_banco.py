"""Trava sobre o mapa de resoluções do Ari (`app/banco/resolucao.py`).

Este teste existe por um motivo específico: **as constantes daquele módulo não
se reconstroem.** Os `reference_id` do IME (2023→3, 2024→2, 2025→4) e os offsets
de slide da 2ª fase do ITA foram descobertos conferindo link a link no site do
colégio, e já se perderam uma vez — estavam dentro de
`gerar_banco_unificado.py`, que saiu na migração do banco de questões por
"gerar HTML" e levou junto a tabela (docs/22 §1.2, recuperado em 23/08).

Os valores abaixo foram conferidos contra o site antigo construído: as 894
questões que ele renderizava bateram 894/894 com o que este módulo calcula.
Quem mudar um número aqui e vir o teste passar mudou o site do Ari junto — ou
quebrou o link de uma turma inteira.
"""

from __future__ import annotations

import pytest

from app.banco.resolucao import url_da_resolucao


@pytest.mark.parametrize(
    ("vestibular", "ano", "fase", "materia", "numero", "esperado"),
    [
        # ── ITA · 1ª fase ────────────────────────────────────────────────
        # 2019–2021: plataforma antiga, sem deep-link — cai na capa da prova.
        ("ITA", 2019, 1, "Física", 1,
         "http://login.aridesa.com.br/vestibular/ita2019/index.aspx"),
        ("ITA", 2021, 1, "Química", 50,
         "http://login.aridesa.com.br/vestibular/ita2021/index.aspx"),
        # 2022–2024: galeria por matéria, e o número da questão é ABSOLUTO na
        # prova — daí o offset (Matemática começa na 37, Química na 49).
        ("ITA", 2022, 1, "Física", 5,
         "https://servicos.aridesa.com.br/comentario/ita/2022/#gallery-1-5"),
        ("ITA", 2022, 1, "Matemática", 40,
         "https://servicos.aridesa.com.br/comentario/ita/2022/#gallery-4-4"),
        ("ITA", 2023, 1, "Química", 50,
         "https://servicos.aridesa.com.br/comentario/ita/2023/#gallery-5-2"),
        # 2025+: reference_id é ano-2024, e a galeria é única.
        ("ITA", 2025, 1, "Física", 13,
         "https://comentarios.aridesa.com.br/ita?reference_id=1#gallery-1-13"),
        # ── ITA · 2ª fase ────────────────────────────────────────────────
        ("ITA", 2020, 2, "Física", 3,
         "http://login.aridesa.com.br/vestibular/ita2020/index.aspx"),
        ("ITA", 2023, 2, "Matemática", 4,
         "https://servicos.aridesa.com.br/comentario/ita/2023/#gallery-6-4"),
        # 2024 reusa as galerias da 1ª fase; a Q1 da 2ª começa no slide 13.
        ("ITA", 2024, 2, "Física", 1,
         "https://servicos.aridesa.com.br/comentario/ita/2024/#gallery-1-13"),
        # 2025: Matemática no slide 1, Química no 11, Física no 21.
        ("ITA", 2025, 2, "Matemática", 1,
         "https://comentarios.aridesa.com.br/ita?reference_id=1&stage=2#gallery-1-1"),
        ("ITA", 2025, 2, "Física", 1,
         "https://comentarios.aridesa.com.br/ita?reference_id=1&stage=2#gallery-1-21"),
        # ── IME · 1ª fase ────────────────────────────────────────────────
        ("IME", 2018, 1, "Física", 16,
         "http://login.aridesa.com.br/vestibular/ime2018_2019/index.aspx"),
        # 2021–2022: galeria 1 = Matemática (1–15), 2 = Física (16–30), 3 = Química.
        ("IME", 2021, 1, "Física", 20,
         "https://servicos.aridesa.com.br/comentario/ime/2021-2022/#gallery-2-5"),
        ("IME", 2022, 1, "Química", 35,
         "https://servicos.aridesa.com.br/comentario/ime/2022-2023/#gallery-3-5"),
        # 2023–2025: reference_id sem fórmula, galeria única indexada pelo número.
        ("IME", 2024, 1, "Física", 21,
         "https://comentarios.aridesa.com.br/ime?reference_id=2#gallery-1-21"),
        ("IME", 2023, 1, "Matemática", 1,
         "https://comentarios.aridesa.com.br/ime?reference_id=3#gallery-1-1"),
        ("IME", 2025, 1, "Química", 40,
         "https://comentarios.aridesa.com.br/ime?reference_id=4#gallery-1-40"),
    ],
)
def test_url_da_resolucao(vestibular, ano, fase, materia, numero, esperado):
    assert url_da_resolucao(vestibular, ano, fase, materia, numero) == esperado


def test_ime_segunda_fase_nao_tem_resolucao_publicada():
    """As 210 questões sem link são todas IME · 2ª fase, e é assim mesmo.

    O Ari não comenta a discursiva do IME. Devolver None aqui é o que faz o
    cartão esconder o botão em vez de oferecer um link quebrado.
    """
    for ano in range(2019, 2026):
        for materia in ("Física", "Química", "Matemática"):
            assert url_da_resolucao("IME", ano, 2, materia, 1) is None


def test_ano_fora_do_mapa_nao_inventa_link():
    """Prova anterior a 2018 não tem página no Ari — e o módulo não chuta uma.

    Um link inventado é pior que link nenhum: manda o aluno para um 404 do
    colégio, e ele conclui que o banco está quebrado.
    """
    assert url_da_resolucao("ITA", 2015, 1, "Física", 1) is None
    assert url_da_resolucao("IME", 2010, 1, "Física", 1) is None
