"""O índice de importância do assunto (docs/34 §3).

O que este arquivo trava, e por que cada coisa importa:

  1. **A unidade é fatia da prova, não contagem.** Um tópico com 5 ocorrências
     numa prova de 20 questões é MAIS importante que um com 8 numa de 50 — e a
     contagem bruta diz o contrário. É a razão de o índice existir.
  2. **A recência pesa, e pesa liso.** Meia-vida, não janela: nenhum ano some
     de repente.
  3. **Ano sem ocorrência entra na média como zero.** Iterar sobre `porAno`
     (que só traz anos COM ocorrência) inflaria justamente os tópicos raros —
     os que mais precisam aparecer como raros.
  4. **O ano de referência não muda o resultado.** O código afirma isso num
     comentário; um comentário que ninguém verifica é uma promessa.
  5. **O parâmetro nunca derruba o índice.** Banco mudo devolve o valor de
     fábrica, nunca exceção.
"""

from __future__ import annotations

import itertools
from types import SimpleNamespace

import pytest

from app.banco import importancia
from app.banco.importancia import (
    JANELA_TENDENCIA_PADRAO,
    MEIA_VIDA_PADRAO,
    ParametroImportancia,
    carregar_parametro,
    indice_de_importancia,
    peso_do_ano,
    ranking_0_a_100,
)

# ─── 1 · Fatia da prova, não contagem ────────────────────────────────────


def test_o_indice_e_percentual_da_prova_e_nao_contagem():
    """Cinco ocorrências em 20 questões (25%) valem mais que oito em 50 (16%).

    Se o índice fosse contagem, o segundo ganharia — e a leitura "esse assunto
    cai muito" ficaria refém do tamanho da prova daquele ano.
    """
    ano = {2025: 1}
    magro = indice_de_importancia({2025: 5}, {2025: 20})
    gordo = indice_de_importancia({2025: 8}, {2025: 50})

    assert magro == pytest.approx(25.0)
    assert gordo == pytest.approx(16.0)
    assert magro > gordo
    assert ano  # o recorte de um ano só é o caso mais simples e tem de fechar


def test_ano_sem_prova_nao_entra_no_denominador():
    """Um ano com zero questões não contribui nem infla a média."""
    com = indice_de_importancia({2025: 5}, {2024: 0, 2025: 20})
    sem = indice_de_importancia({2025: 5}, {2025: 20})

    assert com == pytest.approx(sem)


# ─── 2 · A recência pesa, e pesa liso ────────────────────────────────────


def test_uma_meia_vida_atras_pesa_metade():
    assert peso_do_ano(2020, 2025, meia_vida_anos=5) == pytest.approx(0.5)
    assert peso_do_ano(2015, 2025, meia_vida_anos=5) == pytest.approx(0.25)
    assert peso_do_ano(2025, 2025, meia_vida_anos=5) == pytest.approx(1.0)


def test_o_assunto_recente_vence_o_antigo_com_a_mesma_fatia():
    """Mesma fatia (10%), anos diferentes. Quem caiu agora importa mais."""
    questoes = {2015: 20, 2025: 20}
    recente = indice_de_importancia({2025: 2}, questoes)
    antigo = indice_de_importancia({2015: 2}, questoes)

    assert recente > antigo


def test_meia_vida_maior_valoriza_o_historico():
    """`H` alto trata o edital como estável; `H` baixo diz que só o recente
    conta. É o botão que a coordenação gira (docs/34 §5 · D2), então precisa
    mover o número na direção certa."""
    questoes = {2015: 20, 2025: 20}
    so_antigo = {2015: 4}

    curta = indice_de_importancia(so_antigo, questoes, ParametroImportancia(meia_vida_anos=2))
    longa = indice_de_importancia(so_antigo, questoes, ParametroImportancia(meia_vida_anos=50))

    assert longa > curta


def test_nenhum_ano_some_de_repente():
    """A diferença entre meia-vida e janela, em número.

    Com janela de 5 anos, o ano 2019 contribuiria e o 2018 valeria ZERO — um
    degrau. Com meia-vida, 2018 pesa pouco mas pesa, e a diferença entre dois
    anos vizinhos é sempre pequena.
    """
    pesos = [peso_do_ano(a, 2025, MEIA_VIDA_PADRAO) for a in range(2005, 2026)]
    saltos = [abs(b - a) for a, b in itertools.pairwise(pesos)]

    assert all(p > 0 for p in pesos), "nenhum ano vale zero"
    assert max(saltos) < 0.15, "nenhum degrau entre anos vizinhos"


# ─── 3 · Ano sem ocorrência entra como zero ──────────────────────────────


def test_ano_sem_ocorrencia_puxa_a_media_para_baixo():
    """⚠️ O teste que impede o erro mais fácil deste módulo.

    `porAno` só traz anos COM ocorrência. Iterar sobre ele em vez de sobre
    `questoesPorAno` faria um tópico que caiu uma vez em dez anos ter o mesmo
    índice de um que cai todo ano — e o ranking colocaria o raro no topo.
    """
    questoes = {ano: 20 for ano in range(2016, 2026)}
    todo_ano = indice_de_importancia({ano: 2 for ano in range(2016, 2026)}, questoes)
    uma_vez = indice_de_importancia({2025: 2}, questoes)

    assert todo_ano == pytest.approx(10.0)
    assert uma_vez < todo_ano
    # E ele não é 10% só porque o único ano em que caiu tinha 10%.
    assert uma_vez < 5.0


def test_topico_que_nunca_caiu_vale_zero_e_nao_some():
    """"Esse assunto não apareceu em oito anos" é informação de estudo."""
    assert indice_de_importancia({}, {2024: 30, 2025: 30}) == 0.0


# ─── 4 · A invariância que o comentário promete ──────────────────────────


def test_o_ano_de_referencia_nao_muda_o_indice():
    """O código diz que o fator de `ref` cancela por aparecer nos dois lados da
    divisão. Aqui isso vira teste: mesmo recorte, deslocado no tempo, mesmo
    índice. Se alguém trocar a média ponderada por uma soma pesada, quebra."""
    base = indice_de_importancia({2020: 3, 2024: 5}, {2020: 20, 2024: 25})
    deslocado = indice_de_importancia({2030: 3, 2034: 5}, {2030: 20, 2034: 25})

    assert base == pytest.approx(deslocado)


def test_o_indice_fica_entre_a_menor_e_a_maior_fatia():
    """Média ponderada nunca escapa do intervalo dos valores que pondera. É o
    que garante que o número continua se lendo como percentual da prova."""
    indice = indice_de_importancia({2020: 2, 2025: 8}, {2020: 20, 2025: 20})

    assert 10.0 <= indice <= 40.0


# ─── O ranking 0–100 ─────────────────────────────────────────────────────


def test_o_maior_do_recorte_vira_100():
    r = ranking_0_a_100({"a": 4.0, "b": 8.0, "c": 0.0})

    assert r == {"a": 50.0, "b": 100.0, "c": 0.0}


def test_ranking_de_recorte_vazio_ou_todo_zero_nao_explode():
    assert ranking_0_a_100({}) == {}
    assert ranking_0_a_100({"a": 0.0, "b": 0.0}) == {"a": 0.0, "b": 0.0}


# ─── 5 · O parâmetro nunca derruba o índice ──────────────────────────────


class ClienteMudo:
    """Banco que levanta em qualquer leitura — PostgREST fora, schema cache
    velho depois de migration (armadilha 1), tabela ainda não criada."""

    def table(self, *_a, **_k):
        raise RuntimeError("PostgREST fora do ar")


class ClienteVazio:
    def table(self, *_a, **_k):
        return self

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class ClienteComLinha(ClienteVazio):
    def __init__(self, linha):
        self.linha = linha

    def execute(self):
        return SimpleNamespace(data=[self.linha])


def test_banco_fora_do_ar_devolve_o_valor_de_fabrica():
    """⚠️ A trava que a D2 exige: um índice que some porque uma linha de
    configuração não respondeu é pior que um índice com o valor de fábrica."""
    p = carregar_parametro(ClienteMudo())

    assert p.meia_vida_anos == MEIA_VIDA_PADRAO
    assert p.janela_tendencia_anos == JANELA_TENDENCIA_PADRAO
    assert p.versao is None, "versão nula = de fábrica, e a tela diz isso"


def test_tabela_vazia_devolve_o_valor_de_fabrica():
    assert carregar_parametro(ClienteVazio()).meia_vida_anos == MEIA_VIDA_PADRAO


def test_linha_ativa_vence_o_padrao():
    p = carregar_parametro(
        ClienteComLinha({"versao": 3, "meia_vida_anos": "2.5", "janela_tendencia_anos": 4})
    )

    assert p.meia_vida_anos == 2.5
    assert p.janela_tendencia_anos == 4
    assert p.versao == 3


def test_linha_malformada_nao_derruba_a_leitura():
    """O CHECK da 0044 impede pelo caminho normal; se chegou aqui, alguém
    escreveu direto no banco. Ainda assim o índice tem de sair."""
    p = carregar_parametro(ClienteComLinha({"versao": 1, "meia_vida_anos": "cinco"}))

    assert p.meia_vida_anos == MEIA_VIDA_PADRAO


def test_o_parametro_e_imutavel():
    """Cálculo em andamento não muda no meio."""
    import dataclasses

    p = ParametroImportancia()
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.meia_vida_anos = 1  # type: ignore[misc]


# ─── A migration e o código não podem divergir ───────────────────────────


def test_a_semente_da_migration_bate_com_o_valor_de_fabrica():
    """⚠️ Dois lugares guardam o mesmo número — o `INSERT` da 0044 e as
    constantes deste módulo. Eles têm de concordar, senão "de fábrica" e
    "recém-instalado" viram coisas diferentes e ninguém percebe.
    """
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1] / "migrations" / "0044_parametro_importancia.sql"
    ).read_text(encoding="utf-8")

    assert f"SELECT 1, {int(MEIA_VIDA_PADRAO)}, {JANELA_TENDENCIA_PADRAO}," in sql


def test_o_modulo_nao_importa_nada_de_io():
    """O contrato de pureza do docstring, verificado. Só `carregar_parametro`
    toca o banco, e ela recebe o cliente por argumento."""
    fonte = (
        __import__("pathlib").Path(importancia.__file__).read_text(encoding="utf-8")
    )

    for proibido in ("import httpx", "get_supabase", "criar_cliente_supabase"):
        assert proibido not in fonte, f"{proibido} quebra a pureza do módulo"
