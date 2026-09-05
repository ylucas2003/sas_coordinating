"""Os dois cortes de cada zona — o que o aluno já cruzou e o que falta cruzar.

⚠️ Este arquivo existe por causa da migration 0037. Até ela, a regra de corte
tinha DUAS implementações — `thresholds.py` com matérias core fixas e mínimo
4,0 fixo, e `criterios.py` com a régua de verdade — e as duas discordavam sobre
o mesmo aluno, sem erro nenhum. `/me/zona` é a terceira tela a fazer a mesma
pergunta, e a única defesa contra a terceira cópia é o corte sair sempre do
avaliador.

O que se testa aqui é a tradução ZONA → CORTES, que é onde o produto pede algo
que o avaliador não devolve: o avaliador diz aprovado/reprovado, e a tela
precisa de "quanto falta" e "quanto sobra".
"""

from __future__ import annotations

import pytest

from app.stats import criterios
from app.stats.aluno_zona import cortes_na_regua

CASA = criterios.por_slug(criterios.CRITERIO_DA_CASA)


CORTE = criterios.corte_da_media(CASA)
CONFORTAVEL = CORTE + criterios.MARGEM_CONFORTAVEL


def test_a_fronteira_sai_da_zona_nao_da_media():
    """⚠️ Bug 1, achado rodando contra o banco.

    A fronteira é a linha que a escada desenha no TOPO da faixa do aluno, então
    ela tem de sair da faixa. Tirando-a da média, um aluno em `risco` com média
    5,1 recebia o rótulo "CORTE 6,0" sobre a divisa risco→cinzenta, que vale
    5,0 — a linha certa com o número da linha de cima.
    """
    _, proxima = cortes_na_regua(CASA, "risco", 5.1)
    assert proxima == CORTE

    _, proxima = cortes_na_regua(CASA, "cinzenta", 5.1)
    assert proxima == CONFORTAVEL


def test_o_corte_cruzado_sai_da_media_nao_da_zona():
    """⚠️ Bug 2, do mesmo dia.

    `corteAtual` é uma afirmação sobre a PESSOA — "você já passou disto" —, e o
    critério da casa combina com "todos": só corta quem falha em TUDO
    (docs/18 §1.7). Um aluno com média 4,67 fica em `cinzenta` sem ter passado
    o mínimo de 5,0, e a primeira versão saía da zona: anunciava um corte
    cruzado que ele não cruzou, e a folga sairia negativa.
    """
    atual, _ = cortes_na_regua(CASA, "cinzenta", 4.67)
    assert atual is None

    atual, _ = cortes_na_regua(CASA, "cinzenta", 5.5)
    assert atual == CORTE


def test_top_nao_tem_proxima_fronteira():
    """`top` é terminal: inventar um alvo acima do topo seria inventar régua."""
    atual, proxima = cortes_na_regua(CASA, "top", CONFORTAVEL + 0.5)
    assert proxima is None
    assert atual == CONFORTAVEL


def test_exatamente_no_corte_conta_como_cruzado():
    """`>=` e não `>`: o edital corta quem fica ABAIXO do mínimo, não quem o atinge."""
    atual, _ = cortes_na_regua(CASA, "cinzenta", CORTE)
    assert atual == CORTE


def test_zona_e_media_podem_discordar_e_isso_e_o_caso_interessante():
    """Média acima da fronteira e o aluno ainda cortado — quem corta é a matéria.

    Acontece de verdade: média 5,1 em `risco`. Os dois números saem coerentes
    (já cruzou 5,0; a fronteira da faixa dele é 5,0), e é a ROTA que resolve o
    resto pondo `distancia: None` — a tela então esconde a cota, porque medir
    uma distância de média que não é o que segura o aluno apontaria para o
    lugar errado. Quem nomeia o problema é `materiaMaisCurta`.
    """
    atual, proxima = cortes_na_regua(CASA, "risco", 5.1)
    assert atual == CORTE
    assert proxima == CORTE
    assert proxima - 5.1 < 0


def test_criterio_sem_exigencia_de_media_nao_opina():
    """Régua feita só de mínimos por matéria não tem corte de média a mostrar.

    `corte_da_media` devolve `None` nesse caso, e a tela precisa receber os dois
    nulos em vez de um zero — 0,0 seria lido como "o corte é zero", que é o
    oposto de "esta régua não cobra média".
    """
    so_materias = criterios.Criterio(
        slug="so-materias",
        nome="Só matérias",
        combinador="algum",
        predicados=tuple(
            p for p in CASA.predicados if p.materia is not criterios.MEDIA_GERAL
        ),
    )
    assert criterios.corte_da_media(so_materias) is None
    assert cortes_na_regua(so_materias, "cinzenta", 6.0) == (None, None)


@pytest.mark.parametrize("media", [0.0, 3.0, 5.0, 5.5, 6.0, 8.0, 10.0])
@pytest.mark.parametrize("zona", ["risco", "cinzenta", "top"])
def test_o_corte_cruzado_nunca_passa_da_media(zona, media):
    """A invariante que o desenho da escada assume, para QUALQUER par.

    Se `corteAtual` pudesse ser maior que a média, a folga do topo sairia
    negativa e a linha dourada apareceria do lado errado do ponto do aluno.
    """
    atual, _ = cortes_na_regua(CASA, zona, media)
    if atual is not None:
        assert atual <= media


@pytest.mark.parametrize("slug", ["ita-f1", "ita-f2", "ime-f1", "tio-leo"])
def test_as_reguas_com_media_respondem(slug):
    """As réguas que o aluno vê depois do onboarding (docs/36 §1.4).

    Elas vêm do ARQUIVO (`criterios.CRITERIOS`), não do banco, então uma delas
    perder a exigência de média seria uma mudança silenciosa que apagaria a
    cota da escada da Jornada — é o que este teste guarda.
    """
    criterio = criterios.por_slug(slug)
    corte = criterios.corte_da_media(criterio)
    assert corte is not None
    atual, proxima = cortes_na_regua(criterio, "cinzenta", corte + 0.1)
    assert atual is not None and proxima is not None


def test_ime_f2_nao_tem_corte_de_media_e_isso_esta_certo():
    """⚠️ `ime-f2` é a única régua sem exigência de média, e é fiel ao edital.

    Os mínimos do IME na 2ª fase são todos POR MATÉRIA (Art. 37, III: pesos
    3 / 2,5 / 2,5 / 1 / 1, com 4,0 em cada) — não existe um número de média no
    edital para a escada apontar.

    O teste existe para que a resposta `(None, None)` seja DELIBERADA e não
    apareça um dia como bug: a tela esconde a cota nesse caso
    (`temCota` em `Jornada.tsx`) em vez de desenhar "CORTE 0,0", que seria
    inventar régua — o pecado que a migration 0037 corrigiu. O veredito
    continua honesto porque o nome do critério fica no cabeçalho (docs/24 §2) e
    as distâncias que existem são as das barras por matéria.
    """
    ime_f2 = criterios.por_slug("ime-f2")
    assert criterios.corte_da_media(ime_f2) is None
    assert cortes_na_regua(ime_f2, "cinzenta", 8.0) == (None, None)
    assert cortes_na_regua(ime_f2, "risco", 2.0) == (None, None)
