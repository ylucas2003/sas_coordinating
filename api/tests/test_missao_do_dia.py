"""A missão do dia (`app/banco/missao.py`).

O bug que estes testes existem para não deixar voltar está em docs/35 §9.1: o
cartão da aba Hoje imprimia `nome: 'Termodinâmica'` ao lado de
`topicoCodigo: '7.2'`, e na taxonomia de Física 7.2 é "Ondas e Acústica". A tela
lia a ETIQUETA do fixture e a fila de treino lia o ENDEREÇO no banco — como o
endereço existia e devolvia questões, nada quebrava: só mentia. Por isso o
primeiro teste do arquivo é o que amarra nome e código na MESMA linha da
taxonomia.

O resto trava as decisões de 04/09:

  * o desafio é o MESMO para todos e determinístico pela data;
  * "hoje" é America/Fortaleza, não UTC — senão a missão vira às 21h, bem na
    hora do estudo, e vira para todo mundo junto;
  * a elegibilidade conta só o que a FILA DE TREINO aceita, e ela pede três
    coisas (`Treino.tsx::respondivel`): não ser dissertativa, ter gabarito e ter
    alternativa. Contar objetiva sem olhar as outras duas deixaria a missão
    prometer 10 e entregar menos — a classe de bug em conserto;
  * a razão impressa fala de QUESTÕES, então conta questões: numerador e
    denominador são conjuntos de ids, e não linhas de `questao_vestibular_topico`.

O fixture modela os três descartes e a questão em dois tópicos da mesma matéria
justamente porque, sem eles, as duas contagens erradas passavam verdes.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_missao_do_dia.py -q
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.banco import missao

from .fake_postgrest import FakeCliente

# A taxonomia do teste é a de verdade: os oito pares (código, nome) abaixo saem
# de `topico_taxonomia` do banco de desenvolvimento, com a `ordem` do edital.
# 7.2 é "Ondas e Acústica" e "Termodinâmica" é OUTRO código — um par trocado
# aqui reproduziria o bug de 04/09.
TAXONOMIA = [
    ("Física", "4.1", "Dinâmica", 3),
    ("Física", "7.2", "Ondas e Acústica", 7),
    ("Física", "9.1", "Termodinâmica", 9),
    ("Química", "1.1", "Estrutura Atômica", 0),
    ("Química", "3.1", "Estequiometria", 7),
    ("Química", "11.3", "Ácidos e Bases Orgânicas", 20),
    ("Matemática", "10.1", "Análise Combinatória", 13),
    ("Matemática", "10.2", "Probabilidade", 14),
]

# Quantas questões cada tópico tem e como cada uma sai da fila de treino:
# (total, dissertativas, sem gabarito, sem alternativa). As três formas de
# descarte de `Treino.tsx::respondivel` estão aqui, cada uma sozinha num tópico,
# para o teste dizer QUAL regra quebrou quando quebrar.
#
# Química 11.3 não é exemplo inventado: é o tópico que, no banco de 04/09,
# passava pela contagem antiga com 10 objetivas e entregava 9 na fila.
ACERVO = {
    ("Física", "4.1"): (11, 1, 0, 0),
    ("Física", "7.2"): (14, 0, 0, 0),
    ("Física", "9.1"): (10, 0, 0, 0),
    ("Química", "1.1"): (12, 5, 0, 0),
    ("Química", "3.1"): (12, 2, 0, 0),
    ("Química", "11.3"): (12, 0, 3, 0),
    ("Matemática", "10.1"): (4, 0, 0, 0),
    ("Matemática", "10.2"): (11, 0, 0, 2),
}

# Quatro tópicos com 10+ respondíveis. Os outros quatro ficam de fora por um
# motivo diferente cada: lastro pequeno (10.1), dissertativa (1.1), sem gabarito
# (11.3) e sem alternativa (10.2).
ELEGIVEIS = {("Física", "4.1"), ("Física", "7.2"), ("Física", "9.1"), ("Química", "3.1")}

# As primeiras respondíveis de Física 4.1 caem TAMBÉM em 9.1 — é o caso real:
# `ime_1998_fase2_q08` está classificada em 4.1 Dinâmica, 5.1 Energia e 9.1
# Termodinâmica ao mesmo tempo. Com isso Física tem 38 LIGAÇÕES para 34
# QUESTÕES, e é essa diferença que o teste do denominador persegue.
MISTAS_DE_FISICA = 4

# Física: 14 (7.2) + 10 (4.1) + 10 (9.1) — as 4 mistas já estão contadas em 4.1.
QUESTOES_DE_FISICA = 34


def montar_banco() -> dict:
    questoes: dict[str, dict] = {}
    alternativas: dict[str, dict] = {}
    ligacoes: dict[str, dict] = {}
    topicos: dict[str, dict] = {}

    def ligar(qid: str, materia: str, codigo: str) -> None:
        ligacoes[f"{qid}|{materia}|{codigo}"] = {
            "questao_id": qid,
            "materia": materia,
            "topico_codigo": codigo,
        }

    for materia, codigo, nome, ordem in TAXONOMIA:
        topicos[f"{materia}|{codigo}"] = {
            "materia": materia,
            "codigo": codigo,
            "nome": nome,
            "ordem": ordem,
        }
        total, dissertativas, sem_gabarito, sem_alternativa = ACERVO[(materia, codigo)]
        for i in range(total):
            qid = f"{materia}_{codigo}_q{i:02d}"
            dissertativa = i < dissertativas
            # Dissertativa sem gabarito e sem alternativa é o estado REAL do
            # acervo (0028): 2ª fase não tem letra a conferir.
            faltando_gabarito = dissertativas <= i < dissertativas + sem_gabarito
            faltando_alternativa = (
                dissertativas + sem_gabarito <= i < dissertativas + sem_gabarito + sem_alternativa
            )
            questoes[qid] = {
                "id": qid,
                "materia": materia,
                "dissertativa": dissertativa,
                # O branco existe para provar o `.strip()`: gabarito com espaço
                # é o mesmo que gabarito nenhum, como em `temGabarito`.
                "gabarito": None
                if dissertativa or (faltando_gabarito and i % 2 == 0)
                else "   "
                if faltando_gabarito
                else "C",
            }
            if not dissertativa and not faltando_alternativa:
                for letra in "ABCDE":
                    alternativas[f"{qid}|{letra}"] = {
                        "questao_id": qid,
                        "letra": letra,
                        "texto": f"alternativa {letra}",
                    }
            ligar(qid, materia, codigo)

    for i in range(1, 1 + MISTAS_DE_FISICA):
        ligar(f"Física_4.1_q{i:02d}", "Física", "9.1")

    return {
        "questao_vestibular": questoes,
        "questao_vestibular_alternativa": alternativas,
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


def missoes_de_um_ciclo(cliente: FakeCliente) -> dict[tuple[str, str], missao.MissaoDoDia]:
    """A missão de cada tópico elegível, indexada por (materia, codigo).

    Um ciclo inteiro porque é o que passa por todos os elegíveis uma vez — e é
    assim que o teste alcança um tópico específico sem depender de qual dia o
    embaralhamento deu a ele.
    """
    do_ciclo = {}
    for dia in um_ciclo_de_dias(len(ELEGIVEIS)):
        m = missao.missao_do_dia(cliente, dia)
        assert m is not None
        do_ciclo[(m.materia, m.topicoCodigo)] = m
    return do_ciclo


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


# ─── 4 · Elegibilidade: só conta o que a fila de treino aceita ───────────


def test_topico_com_lastro_pequeno_fica_de_fora(cliente):
    """Matemática 10.1 tem 4 questões: prometer 10 sobre ele seria a mentira de
    volta, com outra roupa."""
    for dia in um_ciclo_de_dias(len(ELEGIVEIS)):
        m = missao.missao_do_dia(cliente, dia)
        assert m is not None
        assert m.topicoCodigo != "10.1"


def test_dissertativa_nao_conta_para_a_elegibilidade(cliente):
    """Química 1.1 tem 12 questões e só 7 objetivas.

    Pelo `totalQuestoes` da taxonomia ele passaria — e a fila de treino, que
    descarta dissertativa (`Treino.tsx::respondivel`), entregaria 7 de 10.
    """
    lastro = missao.ids_respondiveis_por_topico(cliente)

    assert len(lastro[("Química", "1.1")]) == 7
    assert ("Química", "1.1") not in {
        (t["materia"], t["codigo"]) for t in missao.topicos_elegiveis(cliente, lastro)
    }


def test_objetiva_sem_gabarito_nao_conta_para_a_elegibilidade(cliente):
    """Química 11.3 tem 12 objetivas e 3 sem gabarito — 9 respondíveis.

    Este é o G3: a contagem antiga parava em `dissertativa = false` e daria 12,
    o cartão prometeria 10 e a sessão entregaria 9, porque a fila também exige
    letra a conferir. Uma das três está com gabarito em BRANCO, não nulo: é o
    `.strip()` de `temGabarito` que precisa valer dos dois lados.
    """
    lastro = missao.ids_respondiveis_por_topico(cliente)

    assert len(lastro[("Química", "11.3")]) == 9
    assert ("Química", "11.3") not in {
        (t["materia"], t["codigo"]) for t in missao.topicos_elegiveis(cliente, lastro)
    }


def test_objetiva_sem_alternativa_nao_conta_para_a_elegibilidade(cliente):
    """Matemática 10.2 tem 11 objetivas e 2 sem nenhuma alternativa — 9.

    A terceira condição de `respondivel`: sem alternativa não há o que marcar, e
    a sessão pararia na questão. No acervo de 04/09 são 22 objetivas assim.
    """
    lastro = missao.ids_respondiveis_por_topico(cliente)

    assert len(lastro[("Matemática", "10.2")]) == 9
    assert ("Matemática", "10.2") not in {
        (t["materia"], t["codigo"]) for t in missao.topicos_elegiveis(cliente, lastro)
    }


def test_o_topico_no_limite_entra(cliente):
    """Física 9.1 tem 10 questões próprias e mais 4 mistas: o corte é `>=`, não
    `>`, e quem está exatamente em 10 (Física 4.1) entra."""
    lastro = missao.ids_respondiveis_por_topico(cliente)

    assert len(lastro[("Física", "4.1")]) == missao.QUESTOES_DA_MISSAO
    assert ("Física", "4.1") in {
        (t["materia"], t["codigo"]) for t in missao.topicos_elegiveis(cliente, lastro)
    }


def test_questao_mista_nao_infla_o_lastro():
    """Duas ligações da MESMA questão no mesmo tópico contam uma vez.

    Contagem de linhas em vez de conjunto de ids faria uma duplicata no
    `questao_vestibular_topico` empurrar um tópico raso para dentro do sorteio.
    """
    banco = montar_banco()
    original = banco["questao_vestibular_topico"]["Matemática_10.1_q00|Matemática|10.1"]
    banco["questao_vestibular_topico"]["duplicata"] = dict(original)

    lastro = missao.ids_respondiveis_por_topico(FakeCliente(banco))

    assert len(lastro[("Matemática", "10.1")]) == 4


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


def test_o_denominador_da_razao_conta_questoes_e_nao_ligacoes(cliente):
    """A frase diz "das questões de Física", então o denominador é questão.

    Este é o G4. Física tem 34 questões respondíveis e 38 ligações, porque 4
    questões de Dinâmica caem também em Termodinâmica. Ondas e Acústica tem 14
    delas: 14/34 = 41%. Somando as contagens por tópico daria 14/38 = 37% — a
    frase afirmaria questões e mostraria uma proporção de ligações, encolhida
    porque o denominador conta gente repetida.
    """
    ondas = missoes_de_um_ciclo(cliente)[("Física", "7.2")]

    assert ondas.razao.startswith("41% das questões de Física")
    assert "14 no total" in ondas.razao


def test_a_razao_nao_mistura_materias_no_denominador(cliente):
    """Química 3.1 tem 10 das 26 respondíveis DE QUÍMICA — 38%.

    Se o denominador fosse o acervo inteiro — 34 de Física, 26 de Química e 13
    de Matemática —, a mesma questão viraria 14%, e "14% de tudo que já caiu"
    não se lê sozinho.
    """
    estequiometria = missoes_de_um_ciclo(cliente)[("Química", "3.1")]

    assert estequiometria.razao.startswith("38% das questões de Química")


def test_o_denominador_e_o_mesmo_conjunto_do_numerador(cliente):
    """Numerador e denominador saem da mesma peneira: nenhum tópico passa de 100%.

    Contar "todas as objetivas" embaixo e "as respondíveis" em cima daria uma
    fração de duas réguas — e a soma dos tópicos de uma matéria, com as mistas
    contadas uma vez, não pode ultrapassar o total dela.
    """
    lastro = missao.ids_respondiveis_por_topico(cliente)
    de_fisica: set[str] = set()
    for (materia, _), ids in lastro.items():
        if materia == "Física":
            de_fisica |= ids

    assert len(de_fisica) == QUESTOES_DE_FISICA
    assert sum(len(ids) for (m, _), ids in lastro.items() if m == "Física") > QUESTOES_DE_FISICA


def test_acervo_sem_topico_elegivel_devolve_none():
    """Sem lastro a missão é `None`, não erro: a aba Hoje tem tela para isso —
    o convite "escolha um assunto" — e um 500 viraria faixa de erro no herói."""
    vazio = FakeCliente(
        {
            "questao_vestibular": {},
            "questao_vestibular_alternativa": {},
            "questao_vestibular_topico": {},
            "topico_taxonomia": {},
        }
    )

    assert missao.missao_do_dia(vazio, date(2026, 9, 4)) is None
