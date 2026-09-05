"""A corrente do aluno: o que conta como falta, e o que a sequência conta.

Estas duas regras são as que erram CALADAS — nenhuma delas levanta exceção
quando está errada, ela só desenha um quadrado a mais ou a menos na Jornada de
900 pessoas. Por isso são funções puras (docs/36 §2.1 e §2.3) e por isso o
teste as chama direto, sem passar pelo PostgREST: um teste que fosse pelo
cliente estaria testando o cliente.

⚠️ O número que motiva o arquivo inteiro: medindo o banco em 05/09, **58,7% das
notas têm `presente = false`** e **440 alunos de 1.229 têm 100% de falta**. O
booleano cru NÃO é ausência — é ausência misturada com "esta prova nunca foi
minha". Um `NOT presente` ingênuo desenharia a maioria da corrente vazada.
"""

from __future__ import annotations

from app.stats.aluno_jornada import aplicar_regra_da_falta, contar_sequencia


def prova(data: str, *, presente: bool, ciclo: int = 1) -> dict:
    return {
        "id": f"sim-{data}",
        "rotulo": data,
        "dataAplicacao": data,
        "presente": presente,
        "nota": 7.0 if presente else None,
        "cicloOrdem": ciclo,
        "cicloId": f"ciclo-{ciclo}",
    }


def matricula(desde: str) -> dict:
    return {"turma_id": "t1", "ativo_desde": desde}


# ─── A regra da falta ─────────────────────────────────────────────────────


def test_falta_antes_da_matricula_nao_conta():
    """Quem entrou em março não faltou às provas de fevereiro.

    É o caso que separa "ausência" de "esta prova não era minha" para o aluno
    transferido — e sem ele a corrente de quem chega no meio do ano nasce
    vazada por provas que aconteceram antes de ele existir no colégio.
    """
    itens = [
        prova("2026-02-10", presente=False),
        prova("2026-03-15", presente=True),
        prova("2026-04-20", presente=False),
    ]
    saida = aplicar_regra_da_falta(itens, [matricula("2026-03-01")])

    datas = [i["dataAplicacao"] for i in saida]
    assert datas == ["2026-03-15", "2026-04-20"]


def test_nota_feita_antes_da_matricula_permanece():
    """O recorte tira FALTA antiga, não NOTA antiga.

    Se o aluno fez a prova, ele fez — a data da matrícula não apaga o que ele
    já mostrou. Tirar a nota junto seria esconder desempenho real.
    """
    itens = [prova("2026-02-10", presente=True), prova("2026-04-20", presente=True)]
    saida = aplicar_regra_da_falta(itens, [matricula("2026-03-01")])

    assert [i["dataAplicacao"] for i in saida] == ["2026-02-10", "2026-04-20"]


def test_sem_matricula_ativa_some_toda_falta():
    """Sem vínculo vivo não há como acusar ausência.

    Quadrado vazado é uma acusação: ele diz "você devia estar lá". Sem
    matrícula ativa o SAS não pode afirmar isso, e perder a corrente é melhor
    que inventá-la.
    """
    itens = [prova("2026-03-10", presente=True), prova("2026-04-20", presente=False)]
    saida = aplicar_regra_da_falta(itens, [])

    assert [i["presente"] for i in saida] == [True]


def test_a_trilha_nao_entra_no_filtro():
    """`INDEFINIDA` são 664 alunos REAIS, e a regra não os trata diferente.

    A trilha ficou fora do filtro de propósito (docs/36 §1.1): são alunos cuja
    `section` do Canvas o parser não entendeu (commit 59cc7ce), e excluí-los
    seria punir o aluno por um defeito de ingest. A regra só olha matrícula e
    data — a função pura nem recebe trilha, e este teste guarda isso.
    """
    itens = [prova("2026-03-10", presente=False)]
    saida = aplicar_regra_da_falta(itens, [matricula("2026-01-01")])

    assert len(saida) == 1 and saida[0]["presente"] is False


def test_devolve_em_ordem_cronologica():
    """Toda contagem daqui depende da ordem, então ela é contrato, não acaso."""
    itens = [
        prova("2026-05-01", presente=True),
        prova("2026-03-01", presente=True),
        prova("2026-04-01", presente=False),
    ]
    saida = aplicar_regra_da_falta(itens, [matricula("2026-01-01")])

    assert [i["dataAplicacao"] for i in saida] == ["2026-03-01", "2026-04-01", "2026-05-01"]


# ─── A sequência ──────────────────────────────────────────────────────────


def test_corrente_conta_do_fim_para_tras():
    itens = [
        prova("2026-01-01", presente=True),
        prova("2026-02-01", presente=False),
        prova("2026-03-01", presente=True),
        prova("2026-04-01", presente=True),
    ]
    atual, _ = contar_sequencia(itens)
    assert atual == 2


def test_falta_no_ultimo_zera_a_corrente_e_preserva_o_recorde():
    """O recorde sobrevive à quebra — é o ponto de guardá-lo separado.

    Sem isso, faltar a UMA prova apagaria a prova de que a pessoa compareceu a
    cinco seguidas, que é justamente o que dá peso à sequência.
    """
    itens = [
        prova("2026-01-01", presente=True),
        prova("2026-02-01", presente=True),
        prova("2026-03-01", presente=True),
        prova("2026-04-01", presente=False),
    ]
    atual, melhor = contar_sequencia(itens)
    assert (atual, melhor) == (0, 3)


def test_recorde_atravessa_a_virada_de_ciclo():
    """Os dois números cobrem o ANO, não o ciclo (docs/36 §1.3).

    Se o recorde fosse por ciclo, uma sequência de 6 que começa no ciclo 1 e
    termina no 2 nunca apareceria — e o aluno veria "melhor: 3" tendo feito 6
    seguidas.
    """
    itens = [prova(f"2026-0{m}-01", presente=True, ciclo=1 if m < 4 else 2) for m in range(1, 7)]
    atual, melhor = contar_sequencia(itens)
    assert (atual, melhor) == (6, 6)


def test_aluno_sem_nenhuma_prova():
    assert contar_sequencia([]) == (0, 0)
