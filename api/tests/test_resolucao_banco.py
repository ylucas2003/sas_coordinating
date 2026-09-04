"""Trava sobre o mapa de resoluções do Ari (`app/banco/resolucao.py`).

Este teste existe por um motivo específico: **as constantes daquele módulo não
se reconstroem.** Os `reference_id` do IME (2023→3, 2024→2, 2025→4) e os offsets
de slide da 2ª fase do ITA foram descobertos conferindo link a link no site do
colégio, e já se perderam uma vez — estavam dentro de
`gerar_banco_unificado.py`, que saiu na migração do banco de questões por
"gerar HTML" e levou junto a tabela (docs/22 §1.2, recuperado em 23/08).

⚠️ **A referência é a página do Ari, não este módulo — e não o site antigo.**
A versão anterior deste arquivo dizia ter conferido 894/894 contra o HTML
estático que o `gerar_banco_unificado.py` produzia. Só que aquele HTML era
gerado pela MESMA tabela: bater 894/894 provava que o gerador e a tabela
concordavam, não que o link abria. Foi assim que 146 URLs da plataforma nova
ficaram cravadas erradas aqui — o teste passava com o deep-link quebrado
(docs/35 §0.2).

ESTAS páginas foram abertas e lidas em 04/09/2026, e só destas os valores saem
conferidos: `comentarios.aridesa.com.br/ita?reference_id=1` (com e sem
`&stage=2`), `/ime?reference_id=2|3|4`, e
`servicos.aridesa.com.br/comentario/ita/2022` e `/2023`. Cada caso conferido
aponta para o `data-src` que a página tem naquele índice.

⚠️ Os casos de `ita/2024` e de `ime/2021-2022` e `/2022-2023` NÃO foram
reconferidos nesta passagem: seguem valendo pela conferência antiga. Quem mexer
neles abra a página antes — e troque este parágrafo, que é o registro do que
está provado e do que só está herdado.

A releitura achou um segundo defeito, além do nome da galeria que motivou a
docs/35 §2: a 1ª fase do ITA de 2022 tem 70 questões e uma régua própria, e o
offset dela estava errado. Não quebrava link vivo — não há questão de ITA 2022 ·
1ª fase no acervo —, mas quebraria em silêncio no dia em que ela entrasse.
Corrigido em `_ITA_F1_OFFSET_POR_ANO`.

Quem mudar um número aqui: abra a página antes. Comparar com o código só
confirma o que o código já acha.
"""

from __future__ import annotations

import re

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
        # prova — daí o offset. Em 2023 e 2024 a prova tem 60 questões e
        # Matemática começa na 37, Química na 49; Física, que abre a prova, é a
        # única faixa que 2022 compartilha (Q1–15 lá, Q1–12 nos outros dois).
        ("ITA", 2022, 1, "Física", 5,
         "https://servicos.aridesa.com.br/comentario/ita/2022/#gallery-1-5"),
        ("ITA", 2023, 1, "Matemática", 37,
         "https://servicos.aridesa.com.br/comentario/ita/2023/#gallery-4-1"),
        ("ITA", 2023, 1, "Química", 50,
         "https://servicos.aridesa.com.br/comentario/ita/2023/#gallery-5-2"),
        ("ITA", 2024, 1, "Química", 49,
         "https://servicos.aridesa.com.br/comentario/ita/2024/#gallery-5-1"),
        # A 1ª fase de 2022 tem 70 questões numa régua PRÓPRIA (Fís 1–15 ·
        # Port 16–30 · Ing 31–40 · Mat 41–55 · Quí 56–70), e por isso o offset
        # dela é 40/55 e não 36/48. Conferido na página: gallery-4 índice 1 é
        # `MAT-1_Q41.gif`, rótulo `41-B`. Com a régua de 2023 a q41 caía no
        # índice 5, que é a q45.
        ("ITA", 2022, 1, "Matemática", 41,
         "https://servicos.aridesa.com.br/comentario/ita/2022/#gallery-4-1"),
        ("ITA", 2022, 1, "Química", 56,
         "https://servicos.aridesa.com.br/comentario/ita/2022/#gallery-5-1"),
        ("ITA", 2022, 1, "Física", 1,
         "https://servicos.aridesa.com.br/comentario/ita/2022/#gallery-1-1"),
        # 2025+: reference_id é ano-2024, galeria única, e o nome dela é
        # `gallery-stage-1` — a plataforma nova numera pelo stage, não por
        # matéria. Conferido na página: índice 36 → QUI-1_Q36.gif, rótulo "36 - C".
        ("ITA", 2025, 1, "Física", 13,
         "https://comentarios.aridesa.com.br/ita?reference_id=1#gallery-stage-1-13"),
        ("ITA", 2025, 1, "Química", 36,
         "https://comentarios.aridesa.com.br/ita?reference_id=1#gallery-stage-1-36"),
        # ── ITA · 2ª fase ────────────────────────────────────────────────
        ("ITA", 2020, 2, "Física", 3,
         "http://login.aridesa.com.br/vestibular/ita2020/index.aspx"),
        ("ITA", 2023, 2, "Matemática", 4,
         "https://servicos.aridesa.com.br/comentario/ita/2023/#gallery-6-4"),
        # 2024 reusa as galerias da 1ª fase; a Q1 da 2ª começa no slide 13.
        ("ITA", 2024, 2, "Física", 1,
         "https://servicos.aridesa.com.br/comentario/ita/2024/#gallery-1-13"),
        # 2025: Matemática no slide 1, Química no 11, Física no 21 — e a galeria
        # é `gallery-stage-2`, acompanhando o `stage=2` da query.
        ("ITA", 2025, 2, "Matemática", 1,
         "https://comentarios.aridesa.com.br/ita?reference_id=1&stage=2#gallery-stage-2-1"),
        ("ITA", 2025, 2, "Física", 1,
         "https://comentarios.aridesa.com.br/ita?reference_id=1&stage=2#gallery-stage-2-21"),
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
         "https://comentarios.aridesa.com.br/ime?reference_id=2#gallery-stage-1-21"),
        ("IME", 2023, 1, "Matemática", 1,
         "https://comentarios.aridesa.com.br/ime?reference_id=3#gallery-stage-1-1"),
        ("IME", 2025, 1, "Química", 40,
         "https://comentarios.aridesa.com.br/ime?reference_id=4#gallery-stage-1-40"),
    ],
)
def test_url_da_resolucao(vestibular, ano, fase, materia, numero, esperado):
    assert url_da_resolucao(vestibular, ano, fase, materia, numero) == esperado


# Domínio inteiro do que o banco pode ter: 2018–2026, as duas fases, as três
# matérias, e número de questão até 50 (a 1ª fase do ITA vai até 60, e até 70
# em 2022; 50 já cobre as três faixas de matéria, e o que se testa aqui é o
# NOME da galeria, que não depende do número).
_ANOS = range(2018, 2027)
_MATERIAS = ("Física", "Química", "Matemática")

# Só o NOME da galeria, sem o índice: o índice não é assunto desta varredura.
# Ela passa por combinações que o banco não tem — Química q1 na 1ª fase do ITA
# de 2022, cuja Química começa na 49 —, e ali o offset dá número negativo. Quem
# trava índice são os casos parametrizados acima, conferidos contra a página.
_NOME_GALERIA_ANTIGA = re.compile(r"#gallery-\d+-")
_NOME_GALERIA_NOVA = re.compile(r"#gallery-stage-[12]-")


def test_cada_plataforma_nomeia_a_galeria_do_seu_jeito():
    """O nome da galeria é do HOST, não do vestibular nem do ano.

    Esta é a regra que o defeito de 146 questões violava (docs/35 §2): o código
    montava `#gallery-1-` nos dois hosts, e na plataforma nova nenhuma galeria
    casa com esse nome — o Fancybox abre a capa em vez do slide pedido.

    Invariante, lida do `data-fancybox` de cada página:

        servicos.aridesa.com.br     → gallery-1 … gallery-8
        comentarios.aridesa.com.br  → gallery-stage-1 e gallery-stage-2

    Vale para as duas bancas e todos os anos, então é varredura e não amostra:
    prova nova que entre no mapa cai aqui sem ninguém lembrar de adicionar caso.
    """
    vistos_antigos = vistos_novos = 0
    for vestibular in ("ITA", "IME"):
        for ano in _ANOS:
            for fase in (1, 2):
                for materia in _MATERIAS:
                    for numero in range(1, 51):
                        url = url_da_resolucao(vestibular, ano, fase, materia, numero)
                        if url is None:
                            continue
                        contexto = f"{vestibular} {ano} fase{fase} {materia} q{numero}: {url}"
                        if url.startswith("https://servicos.aridesa.com.br/"):
                            assert _NOME_GALERIA_ANTIGA.search(url), contexto
                            assert "gallery-stage" not in url, contexto
                            vistos_antigos += 1
                        elif url.startswith("https://comentarios.aridesa.com.br/"):
                            assert _NOME_GALERIA_NOVA.search(url), contexto
                            vistos_novos += 1
                        else:
                            # Plataforma de 2018–2021: capa da prova, sem hash.
                            assert "#" not in url, contexto

    # Sem isto o teste passaria vazio se alguém apagasse os dois ramos.
    assert vistos_antigos > 0
    assert vistos_novos > 0


def test_a_fase_manda_no_numero_do_stage():
    """`gallery-stage-N` tem o N da FASE, não um índice de galeria.

    Era o que confundia: na plataforma antiga o número depois de `gallery-` é a
    galeria da matéria (1 a 8); na nova é o stage, e ele casa com o `stage=` da
    query string. Confundir os dois é o que produziu `#gallery-1-` na 2ª fase.
    """
    primeira = url_da_resolucao("ITA", 2025, 1, "Matemática", 40)
    segunda = url_da_resolucao("ITA", 2025, 2, "Matemática", 1)
    assert primeira is not None and segunda is not None
    assert "stage=" not in primeira and "#gallery-stage-1-" in primeira
    assert "&stage=2#" in segunda and "#gallery-stage-2-" in segunda


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
