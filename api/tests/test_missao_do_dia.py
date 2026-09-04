"""A missão do dia (`app/banco/missao.py`).

O bug que estes testes existem para não deixar voltar está em docs/35 §9.1: o
cartão da aba Hoje imprimia `nome: 'Termodinâmica'` ao lado de
`topicoCodigo: '7.2'`, e na taxonomia de Física 7.2 é "Ondas e Acústica". A tela
lia a ETIQUETA do fixture e a fila de treino lia o ENDEREÇO no banco — como o
endereço existia e devolvia questões, nada quebrava: só mentia. Por isso o
primeiro teste do arquivo é o que amarra nome e código na MESMA linha da
taxonomia.

O resto trava as três decisões de 04/09:

  * o desafio é o MESMO para todos e determinístico pela data;
  * "hoje" é America/Fortaleza, não UTC — senão a missão vira às 21h, bem na
    hora do estudo, e vira para todo mundo junto;
  * a elegibilidade conta só questão OBJETIVA, porque é o que a fila de treino
    aceita: cortar pelo número cru da taxonomia deixaria a missão prometer 10 e
    entregar menos, que é exatamente a classe de bug em conserto.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_missao_do_dia.py -q
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.banco import missao

from .fake_postgrest import FakeCliente

# A taxonomia do teste é a de verdade no que importa: 7.2 é "Ondas e Acústica",
# e "Termodinâmica" é OUTRO código. Um par trocado aqui reproduziria o bug.
TAXONOMIA = [
    ("Física", "7.2", "Ondas e Acústica", 0),
    ("Física", "9.1", "Termodinâmica", 1),
    ("Física", "4.1", "Eletrostática", 2),
    ("Química", "3.1", "Estequiometria", 0),
    ("Química", "9.5", "Radioatividade", 1),
    ("Matemática", "5.4", "Análise Combinatória", 0),
]

# Quantas questões cada tópico tem, e quantas delas são dissertativas.
# `9.5` e `5.4` existem para provar as duas formas de ficar de fora: uma por
# lastro pequeno, outra porque metade do lastro é dissertativa.
ACERVO = {
    ("Física", "7.2"): (14, 0),
    ("Física", "9.1"): (10, 0),
    ("Física", "4.1"): (11, 1),
    ("Química", "3.1"): (12, 2),
    ("Química", "9.5"): (12, 5),
    ("Matemática", "5.4"): (4, 0),
}

ELEGIVEIS = {("Física", "7.2"), ("Física", "9.1"), ("Física", "4.1"), ("Química", "3.1")}


def montar_banco() -> dict:
    questoes: dict[str, dict] = {}
    ligacoes: dict[str, dict] = {}
    topicos: dict[str, dict] = {}

    for materia, codigo, nome, ordem in TAXONOMIA:
        topicos[f"{materia}|{codigo}"] = {
            "materia": materia,
            "codigo": codigo,
            "nome": nome,
            "ordem": ordem,
        }
        total, dissertativas = ACERVO[(materia, codigo)]
        for i in range(total):
            qid = f"{materia}_{codigo}_q{i:02d}"
            questoes[qid] = {
                "id": qid,
                "materia": materia,
                "dissertativa": i < dissertativas,
            }
            ligacoes[qid] = {
                "questao_id": qid,
                "materia": materia,
                "topico_codigo": codigo,
            }

    return {
        "questao_vestibular": questoes,
        "questao_vestibular_topico": ligacoes,
        "topico_taxonomia": topicos,
    }


@pytest.fixture
def cliente() -> FakeCliente:
    return FakeCliente(montar_banco())


def um_ciclo_de_dias(quantos: int) -> list[date]:
    """Os `quantos` dias de um ciclo alinhado — um rodízio completo.

    Alinhado de propósito: o rodízio é `divmod(ordinal, n)`, então uma janela
    que atravessa a virada de ciclo mistura duas permutações e não teria por que
    ser livre de repetição.
    """
    base = (date(2026, 9, 4).toordinal() // quantos) * quantos
    return [date.fromordinal(base + i) for i in range(quantos)]


# ─── 1 · O bug de 04/09: etiqueta e endereço na mesma linha ──────────────


def test_o_nome_vem_da_taxonomia_e_nunca_de_texto_solto(cliente):
    """O par (código, nome) de toda missão possível bate com `topico_taxonomia`.

    É o teste que impede o fixture de 7.2 = "Termodinâmica" de voltar por
    qualquer caminho: nome que não saia da mesma linha do código falha aqui.
    """
    nome_por_codigo = {(m, c): nome for m, c, nome, _ in TAXONOMIA}

    for dia in um_ciclo_de_dias(len(ELEGIVEIS)):
        m = missao.missao_do_dia(cliente, dia)
        assert m is not None
        assert m.nome == nome_por_codigo[(m.materia, m.topicoCodigo)]


def test_o_codigo_sorteado_tem_questoes_de_verdade_no_acervo(cliente):
    """O endereço que a fila de treino vai consultar existe e tem lastro — é a
    outra metade do bug: o código do mock existia, e por isso nada quebrava."""
    for dia in um_ciclo_de_dias(len(ELEGIVEIS)):
        m = missao.missao_do_dia(cliente, dia)
        assert m is not None
        assert (m.materia, m.topicoCodigo) in ELEGIVEIS


# ─── 2 · O mesmo desafio para todos, e determinístico ────────────────────


def test_mesma_data_mesma_missao_em_clientes_diferentes():
    """Dois alunos, duas requisições, o mesmo assunto.

    Clientes distintos sobre o mesmo acervo, porque é assim que a rota chega:
    uma sessão por aluno. Nada na assinatura recebe `aluno_id` — a igualdade é
    estrutural, e este teste é o que a prova de fora.
    """
    dia = date(2026, 9, 4)
    primeira = missao.missao_do_dia(FakeCliente(montar_banco()), dia)
    segunda = missao.missao_do_dia(FakeCliente(montar_banco()), dia)

    assert primeira is not None
    assert primeira == segunda


def test_o_rodizio_passa_por_todos_antes_de_repetir(cliente):
    """Um ciclo completo cobre cada tópico elegível exatamente uma vez.

    É o que separa rodízio de `hash % n`: com sorteio independente por dia, um
    assunto repetiria em poucos dias por acaso e outro passaria semanas sem
    aparecer.
    """
    dias = um_ciclo_de_dias(len(ELEGIVEIS))
    escolhidos = [
        (m.materia, m.topicoCodigo)
        for m in (missao.missao_do_dia(cliente, dia) for dia in dias)
        if m is not None
    ]

    assert len(escolhidos) == len(dias)
    assert set(escolhidos) == ELEGIVEIS
    assert len(set(escolhidos)) == len(escolhidos)


def test_dias_seguidos_trocam_de_assunto(cliente):
    """A missão de amanhã não é a de hoje — o rodízio de fato anda."""
    hoje = missao.missao_do_dia(cliente, date(2026, 9, 4))
    amanha = missao.missao_do_dia(cliente, date(2026, 9, 5))

    assert hoje is not None and amanha is not None
    assert (hoje.materia, hoje.topicoCodigo) != (amanha.materia, amanha.topicoCodigo)


# ─── 3 · O fuso ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("instante", "esperado"),
    [
        # 21h00 em Fortaleza (UTC−3) ainda é o mesmo dia — é a virada que o UTC
        # anteciparia, bem na hora do estudo.
        (datetime(2026, 9, 5, 0, 0, tzinfo=UTC), date(2026, 9, 4)),
        (datetime(2026, 9, 5, 2, 59, tzinfo=UTC), date(2026, 9, 4)),
        # 00h00 em Fortaleza: aí sim vira.
        (datetime(2026, 9, 5, 3, 0, tzinfo=UTC), date(2026, 9, 5)),
    ],
)
def test_hoje_e_o_dia_de_fortaleza_e_nao_o_de_greenwich(instante, esperado):
    assert missao.hoje_na_escola(instante) == esperado


# ─── 4 · Elegibilidade: só questão objetiva conta ────────────────────────


def test_topico_com_lastro_pequeno_fica_de_fora(cliente):
    """Matemática 5.4 tem 4 questões: prometer 10 sobre ele seria a mentira de
    volta, com outra roupa."""
    for dia in um_ciclo_de_dias(len(ELEGIVEIS)):
        m = missao.missao_do_dia(cliente, dia)
        assert m is not None
        assert m.topicoCodigo != "5.4"


def test_dissertativa_nao_conta_para_a_elegibilidade(cliente):
    """Química 9.5 tem 12 questões e só 7 objetivas.

    Pelo `totalQuestoes` da taxonomia ele passaria — e a fila de treino, que
    descarta dissertativa (`Treino.tsx::respondivel`), entregaria 7 de 10.
    """
    contagem = missao.contar_objetivas_por_topico(cliente)

    assert contagem[("Química", "9.5")] == 7
    assert ("Química", "9.5") not in {
        (t["materia"], t["codigo"]) for t in missao.topicos_elegiveis(cliente, contagem)
    }


def test_o_topico_no_limite_entra(cliente):
    """Física 9.1 tem exatamente 10 objetivas. O corte é `>=`, não `>`."""
    contagem = missao.contar_objetivas_por_topico(cliente)

    assert contagem[("Física", "9.1")] == missao.QUESTOES_DA_MISSAO
    assert ("Física", "9.1") in {
        (t["materia"], t["codigo"]) for t in missao.topicos_elegiveis(cliente, contagem)
    }


def test_questao_mista_nao_infla_o_lastro():
    """Duas ligações da MESMA questão no mesmo tópico contam uma vez.

    Contagem de linhas em vez de conjunto de ids faria uma duplicata no
    `questao_vestibular_topico` empurrar um tópico raso para dentro do sorteio.
    """
    banco = montar_banco()
    original = banco["questao_vestibular_topico"]["Matemática_5.4_q00"]
    banco["questao_vestibular_topico"]["duplicata"] = dict(original)

    contagem = missao.contar_objetivas_por_topico(FakeCliente(banco))

    assert contagem[("Matemática", "5.4")] == 4


# ─── 5 · O que a missão promete ──────────────────────────────────────────


def test_a_missao_pede_sempre_dez_questoes(cliente):
    for dia in um_ciclo_de_dias(len(ELEGIVEIS)):
        m = missao.missao_do_dia(cliente, dia)
        assert m is not None
        assert m.quantidade == missao.QUESTOES_DA_MISSAO == 10


def test_a_razao_fala_do_acervo_e_nao_do_acerto_do_aluno(cliente):
    """A frase antiga era "Cai em 7% da prova do ITA. Você acerta 41%." — a
    segunda metade é pessoal e não sobrevive a um desafio igual para todos."""
    m = missao.missao_do_dia(cliente, date(2026, 9, 4))

    assert m is not None
    assert "%" in m.razao
    assert "acerta" not in m.razao.lower()


def test_acervo_sem_topico_elegivel_devolve_none():
    """Sem lastro a missão é `None`, não erro: a aba Hoje tem tela para isso —
    o convite "escolha um assunto" — e um 500 viraria faixa de erro no herói."""
    vazio = FakeCliente(
        {"questao_vestibular": {}, "questao_vestibular_topico": {}, "topico_taxonomia": {}}
    )

    assert missao.missao_do_dia(vazio, date(2026, 9, 4)) is None
