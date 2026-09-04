"""Recorrência por tópico do banco ITA · IME (`app/banco/estatisticas.py`).

O que este arquivo trava são as três formas de a tela mentir sem dar erro:

  1. **Somar os tópicos para saber o tamanho da prova.** Questão mista soma nos
     DOIS tópicos de propósito (docs/22 §1.5), então a soma passa do total —
     usá-la como denominador de "% da prova" devolve percentual menor que a
     verdade. É por isso que `questoesPorAno` existe: um `Counter` sobre as
     questões, não sobre as ligações.
  2. **Confundir "não caiu" com "não temos a prova".** O acervo do IME começa
     em 1996 e o do ITA em 2008 (migration 0031). `anos` é o domínio da série e
     tem de encolher junto com o recorte — desenhar o ITA em zero antes de 2008
     AFIRMA que o assunto não caía lá.
  3. **Filtrar metade.** `vestibular` e `fase` estreitam a resposta inteira, e
     não só a contagem por tópico: numerador e denominador precisam sair do
     mesmo recorte.

E a quarta, que não é mentira mas é omissão: tópico com `total = 0` e questão
sem classificação continuam na resposta. "Não caiu em 18 anos" é informação de
estudo, e um recorte incompleto sem aviso é pior que nenhum recorte.
"""

from __future__ import annotations

import pytest

from app.banco import estatisticas

from .fake_postgrest import FakeCliente

# ─── O acervo de brinquedo ───────────────────────────────────────────────
#
# Cinco questões de Matemática e uma de Física. A de Física existe só para
# provar que a matéria filtra: '1.1' é "Conjuntos e Lógica" em Matemática e
# "Fundamentos" em Física, e somar as duas daria um número sem significado
# (0028).
#
# `ita_2019_f1_q01` é MISTA — está em 1.1 e 1.2 ao mesmo tempo. É ela que faz a
# soma dos tópicos passar do total, que é o ponto do teste 1.
# `ita_2021_f1_q04` não tem ligação nenhuma: é a "sem classificação".

QUESTOES = [
    {"id": "ime_1996_f2_q01", "materia": "Matemática", "ano": 1996, "fase": 2, "vestibular": "IME"},
    {"id": "ita_2019_f1_q01", "materia": "Matemática", "ano": 2019, "fase": 1, "vestibular": "ITA"},
    {"id": "ita_2019_f1_q02", "materia": "Matemática", "ano": 2019, "fase": 1, "vestibular": "ITA"},
    {"id": "ita_2019_f2_q03", "materia": "Matemática", "ano": 2019, "fase": 2, "vestibular": "ITA"},
    {"id": "ita_2021_f1_q04", "materia": "Matemática", "ano": 2021, "fase": 1, "vestibular": "ITA"},
    {"id": "ita_2019_f1_fis", "materia": "Física", "ano": 2019, "fase": 1, "vestibular": "ITA"},
]

LIGACOES = [
    {"questao_id": "ime_1996_f2_q01", "materia": "Matemática", "topico_codigo": "1.1"},
    {"questao_id": "ita_2019_f1_q01", "materia": "Matemática", "topico_codigo": "1.1"},
    {"questao_id": "ita_2019_f1_q01", "materia": "Matemática", "topico_codigo": "1.2"},
    {"questao_id": "ita_2019_f1_q02", "materia": "Matemática", "topico_codigo": "1.2"},
    {"questao_id": "ita_2019_f2_q03", "materia": "Matemática", "topico_codigo": "1.1"},
    {"questao_id": "ita_2019_f1_fis", "materia": "Física", "topico_codigo": "1.1"},
]

TOPICOS = [
    {"materia": "Matemática", "codigo": "1.1", "nome": "Trigonometria",
     "bloco_nome": "Geometria", "ordem": 1},
    {"materia": "Matemática", "codigo": "1.2", "nome": "Geometria analítica",
     "bloco_nome": "Geometria", "ordem": 2},
    # No edital e nunca caiu. Continua na resposta de propósito.
    {"materia": "Matemática", "codigo": "9.9", "nome": "Logaritmos",
     "bloco_nome": "Álgebra", "ordem": 3},
    {"materia": "Física", "codigo": "1.1", "nome": "Fundamentos",
     "bloco_nome": "Mecânica", "ordem": 1},
]


@pytest.fixture
def cliente() -> FakeCliente:
    return FakeCliente(
        {
            "questao_vestibular": {q["id"]: dict(q) for q in QUESTOES},
            "questao_vestibular_topico": {i: dict(l) for i, l in enumerate(LIGACOES)},
            "topico_taxonomia": {
                (t["materia"], t["codigo"]): dict(t) for t in TOPICOS
            },
        }
    )


def por_codigo(resposta) -> dict[str, int]:
    return {t.codigo: t.total for t in resposta.topicos}


# ─── 1 · O denominador não sai da soma dos tópicos ───────────────────────


def test_questoes_por_ano_conta_questoes_e_nao_ligacoes(cliente):
    """A armadilha do percentual: em 2019 há 3 questões e 4 ligações.

    Se `questoesPorAno[2019]` fosse a soma dos tópicos, daria 4, e "% da prova"
    de um tópico com 2 questões leria 50% em vez de 67%. O erro é silencioso —
    não há exceção nem tela quebrada, só um número menor.
    """
    r = estatisticas.recorrencia(cliente, "Matemática")

    assert r.questoesPorAno == {1996: 1, 2019: 3, 2021: 1}

    ligacoes_em_2019 = sum(t.porAno.get(2019, 0) for t in r.topicos)
    assert ligacoes_em_2019 == 4
    assert ligacoes_em_2019 > r.questoesPorAno[2019]


def test_questoes_por_ano_soma_o_total_do_recorte(cliente):
    """Somar o denominador ano a ano tem de devolver o total. É o invariante
    que pega um filtro aplicado em metade da resposta."""
    r = estatisticas.recorrencia(cliente, "Matemática")
    assert sum(r.questoesPorAno.values()) == r.totalQuestoes == 5


# ─── 2 · `anos` é o domínio da série, e encolhe com o recorte ────────────


def test_anos_do_ita_comecam_depois_dos_do_ime(cliente):
    """Ausência de prova não é zero (migration 0031).

    O acervo do IME começa antes; pedindo só ITA, 1996 tem de SUMIR da lista de
    anos — é assim que o front sabe onde a linha do ITA começa, em vez de
    desenhá-la em zero e afirmar que o assunto não caía lá.
    """
    ambos = estatisticas.recorrencia(cliente, "Matemática")
    so_ita = estatisticas.recorrencia(cliente, "Matemática", vestibular="ITA")
    so_ime = estatisticas.recorrencia(cliente, "Matemática", vestibular="IME")

    assert ambos.anos == [1996, 2019, 2021]
    assert so_ita.anos == [2019, 2021]
    assert so_ime.anos == [1996]


def test_ano_sem_ocorrencia_do_topico_nao_aparece_em_por_ano(cliente):
    """`porAno` só traz ano com ocorrência — é o contrato, e é por isso que o
    front preenche o zero contra `anos` (`dominio/banco.ts::seriesPorAno`)."""
    r = estatisticas.recorrencia(cliente, "Matemática")
    trigonometria = next(t for t in r.topicos if t.codigo == "1.1")

    assert trigonometria.porAno == {1996: 1, 2019: 2}
    assert 2021 not in trigonometria.porAno
    assert 2021 in r.anos


# ─── 3 · O recorte estreita a resposta inteira ───────────────────────────


def test_fase_estreita_numerador_e_denominador_juntos(cliente):
    """Só a 2ª fase: sobram a do IME 1996 e a do ITA 2019.

    O que se confere aqui é que TUDO andou junto — tópicos, anos, denominador,
    total e as sem classificação. Uma peneira no front mexeria só na primeira
    coluna, e o percentual continuaria dividido pela prova inteira.
    """
    r = estatisticas.recorrencia(cliente, "Matemática", fase=2)

    assert r.totalQuestoes == 2
    assert r.anos == [1996, 2019]
    assert r.questoesPorAno == {1996: 1, 2019: 1}
    assert por_codigo(r) == {"1.1": 2, "1.2": 0, "9.9": 0}
    # A única sem classificação é de 1ª fase e ficou de fora do recorte.
    assert r.semClassificacao == 0


def test_vestibular_e_fase_se_combinam(cliente):
    """ITA · 1ª fase: duas de 2019 e a sem classificação de 2021."""
    r = estatisticas.recorrencia(cliente, "Matemática", vestibular="ITA", fase=1)

    assert r.totalQuestoes == 3
    assert r.questoesPorAno == {2019: 2, 2021: 1}
    assert por_codigo(r) == {"1.1": 1, "1.2": 2, "9.9": 0}
    assert r.semClassificacao == 1


def test_materia_filtra_a_ligacao_tambem(cliente):
    """'1.1' existe nas três matérias e significa coisa diferente em cada uma.

    A ligação de Física não pode somar no '1.1' de Matemática — seria um número
    errado sem nada na tela indicando erro (0028).
    """
    matematica = estatisticas.recorrencia(cliente, "Matemática")
    fisica = estatisticas.recorrencia(cliente, "Física")

    assert por_codigo(matematica)["1.1"] == 3
    assert por_codigo(fisica) == {"1.1": 1}
    assert fisica.totalQuestoes == 1


# ─── 4 · O que não caiu, e o que ninguém classificou, continuam lá ───────


def test_topico_que_nunca_caiu_continua_na_resposta(cliente):
    """"Não apareceu em nenhuma prova do acervo" é informação de estudo."""
    r = estatisticas.recorrencia(cliente, "Matemática")
    logaritmos = next(t for t in r.topicos if t.codigo == "9.9")

    assert logaritmos.total == 0
    assert logaritmos.porAno == {}
    assert logaritmos.nome == "Logaritmos"


def test_sem_classificacao_e_contada_e_nao_sumida(cliente):
    """A questão sem ligação nenhuma não entra em tópico algum, mas o total da
    matéria continua contando com ela — senão o aluno leria um recorte
    incompleto sem saber que é incompleto (docs/22 §8, risco 3)."""
    r = estatisticas.recorrencia(cliente, "Matemática")

    assert r.semClassificacao == 1
    assert r.totalQuestoes == 5


def test_ordem_e_recorrencia_decrescente_com_desempate_pelo_edital(cliente):
    """1.1 tem 3, 1.2 tem 2, 9.9 tem 0 — e o empate desempata pela `ordem`."""
    r = estatisticas.recorrencia(cliente, "Matemática")
    assert [t.codigo for t in r.topicos] == ["1.1", "1.2", "9.9"]


# ─── O índice de importância, pelo caminho do endpoint ───────────────────
#
# A matemática tem teste próprio em `test_importancia.py`. O que ESTES travam é
# a fiação: que o índice chega na resposta, que o denominador usado é o do
# recorte, e que a régua vai junto para a tela poder mostrá-la.


def test_o_indice_chega_na_resposta_e_e_percentual(cliente):
    r = estatisticas.recorrencia(cliente, materia="Matemática")

    # 2019 tem 3 questões; o tópico 1.1 aparece em 2 delas.
    t11 = next(t for t in r.topicos if t.codigo == "1.1")
    assert 0 < t11.importancia <= 100, "é percentual da prova, não contagem"
    assert t11.importanciaRanking > 0


def test_o_maior_indice_do_recorte_tem_ranking_100(cliente):
    r = estatisticas.recorrencia(cliente, materia="Matemática")
    maior = max(r.topicos, key=lambda t: t.importancia)

    assert maior.importanciaRanking == pytest.approx(100.0)


def test_topico_que_nunca_caiu_tem_indice_zero_e_continua_na_lista(cliente):
    """Mesma regra do `total`: "esse assunto não apareceu em oito anos" é
    informação de estudo, e some se a lista só trouxer quem teve ocorrência."""
    r = estatisticas.recorrencia(cliente, materia="Matemática")
    nunca = [t for t in r.topicos if t.total == 0]

    assert nunca, "a fixture precisa ter um tópico sem ocorrência"
    assert all(t.importancia == 0.0 for t in nunca)


def test_a_regua_do_ranking_vai_na_resposta(cliente):
    """Mesma razão de o Painel mostrar "régua: Tio Leo" ao lado do número: um
    ranking sem a régua à vista não é conferível. `versaoParametro` nulo
    significa "de fábrica, a coordenação nunca girou o botão"."""
    r = estatisticas.recorrencia(cliente, materia="Matemática")

    assert r.meiaVidaAnos == 5.0
    assert r.versaoParametro is None


def test_o_indice_segue_o_recorte_como_o_resto_da_resposta(cliente):
    """⚠️ A armadilha que o docstring de `recorrencia` descreve: se o índice
    usasse o denominador do acervo inteiro enquanto o numerador já foi
    filtrado, a fatia sairia MENOR que a verdade e sem erro na tela."""
    largo = estatisticas.recorrencia(cliente, materia="Matemática")
    estreito = estatisticas.recorrencia(
        cliente, materia="Matemática", vestibular="ITA"
    )

    idx = lambda r: {t.codigo: t.importancia for t in r.topicos}  # noqa: E731
    assert idx(largo) != idx(estreito), "o recorte tem de mover o índice"
    # E o denominador do estreito é mesmo o do recorte, não o do acervo.
    assert sum(estreito.questoesPorAno.values()) == estreito.totalQuestoes


def test_a_coordenacao_girando_o_botao_muda_o_ranking(cliente):
    """⚠️ O caminho do override, que é a razão de a D2 ter escolhido o banco.

    Sem este teste, `carregar_parametro` poderia estar sempre caindo no valor
    de fábrica — os outros testes passariam igual, porque o `FakeCliente` da
    fixture não tem a tabela, e ninguém veria que a tela de edição não faz nada.
    """
    cliente.db["parametro_importancia"] = {
        "p1": {
            "id": "p1",
            "versao": 7,
            "meia_vida_anos": "1.0",  # só o ano mais recente conta, na prática
            "janela_tendencia_anos": 3,
            "ativo": True,
        }
    }

    r = estatisticas.recorrencia(cliente, materia="Matemática")

    assert r.meiaVidaAnos == 1.0
    assert r.versaoParametro == 7, "a tela precisa saber que não é o de fábrica"

    # E o número mudou de verdade: com meia-vida curtíssima, o índice tende à
    # fatia do ano mais recente, e não à média dos anos.
    de_fabrica = {t.codigo: t.importancia for t in estatisticas.recorrencia(
        FakeCliente({k: v for k, v in cliente.db.items() if k != "parametro_importancia"}),
        materia="Matemática",
    ).topicos}
    girado = {t.codigo: t.importancia for t in r.topicos}

    assert girado != de_fabrica, "girar o botão tem de mover o índice"
