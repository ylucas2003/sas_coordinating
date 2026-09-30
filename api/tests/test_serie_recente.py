"""`aluno_serie_recente` (migration 0066): as séries que saíram da requisição.

Abrir UM aluno custava 1,04 s porque a sparkline era calculada varrendo as ~78
mil notas de TODOS. Agora ela é gravada quando a classificação é recalculada e
lida como tabela. O que estes testes trancam é a parte que dá para errar sem
ninguém ver:

  · o aluno que PERDEU todas as notas (prova anulada, nota apagada) tem a linha
    zerada — senão a sparkline antiga fica para sempre;
  · o recálculo incremental grava só os alunos pedidos e não mexe nos outros;
  · a leitura de um aluno não devolve o de outro;
  · o vetor do kNN tem a forma que `/similares` espera (uma média por matéria,
    em ordem alfabética do nome, depois desvio e slope).

A equivalência com o cálculo antigo (0 divergências em 788 alunos) foi medida à
mão contra o banco local em 29/09/2026; ela não cabe num fake.
"""

import pytest

from app.stats import serie_recente

from .fake_postgrest import FakeCliente

A1, A2, A3 = "a1", "a2", "a3"


def _banco(**tabelas):
    return {nome: dict(linhas) for nome, linhas in tabelas.items()}


def _serie(aluno_id, sparkline, vetor=None):
    return {"aluno_id": aluno_id, "sparkline": sparkline, "vetor_similares": vetor}


@pytest.fixture
def sem_vetores(monkeypatch):
    """Isola a gravação do cálculo do vetor, que tem teste próprio abaixo."""
    monkeypatch.setattr(serie_recente, "calcular_vetores", lambda cliente, aluno_ids=None: {})


def _notas(*pontuacoes):
    return [{"pontuacao": p} for p in pontuacoes]


def test_grava_a_sparkline_na_ordem_recebida(sem_vetores):
    db = _banco()
    serie_recente.gravar(FakeCliente(db), notas_recentes={A1: _notas(4.0, 5.5, 7.0)})

    assert serie_recente.sparklines(FakeCliente(db)) == {A1: [4.0, 5.5, 7.0]}


def test_recalculo_completo_zera_quem_ficou_sem_nota(sem_vetores):
    db = _banco(
        aluno_serie_recente={
            A1: _serie(A1, [4.0, 5.0]),
            A2: _serie(A2, [9.0, 9.5]),  # A2 perdeu todas as notas
        }
    )
    serie_recente.gravar(FakeCliente(db), notas_recentes={A1: _notas(6.0, 7.0)})

    lidas = serie_recente.sparklines(FakeCliente(db))
    assert lidas[A1] == [6.0, 7.0]
    # A linha continua, mas vazia: sparkline velha seria um número que o aluno
    # já não tem, exibido como se fosse dele.
    assert lidas[A2] == []


def test_recalculo_incremental_so_toca_os_alunos_pedidos(sem_vetores):
    db = _banco(
        aluno_serie_recente={
            A1: _serie(A1, [1.0, 2.0]),
            A2: _serie(A2, [8.0, 9.0]),
        }
    )
    # O sync incremental lê as notas da turma inteira (para o percentil), mas
    # só regrava os alunos que o Canvas tocou.
    serie_recente.gravar(
        FakeCliente(db),
        notas_recentes={A1: _notas(3.0, 4.0), A2: _notas(0.5, 0.5)},
        aluno_ids=[A1],
    )

    lidas = serie_recente.sparklines(FakeCliente(db))
    assert lidas[A1] == [3.0, 4.0]
    assert lidas[A2] == [8.0, 9.0]


def test_incremental_zera_o_aluno_pedido_que_nao_tem_mais_nota(sem_vetores):
    db = _banco(aluno_serie_recente={A1: _serie(A1, [1.0, 2.0])})
    serie_recente.gravar(FakeCliente(db), notas_recentes={}, aluno_ids=[A1])

    assert serie_recente.sparklines(FakeCliente(db)) == {A1: []}


def test_ler_um_aluno_nao_traz_o_de_outro():
    db = _banco(
        aluno_serie_recente={
            A1: _serie(A1, [1.0]),
            A2: _serie(A2, [2.0]),
            A3: _serie(A3, [3.0]),
        }
    )
    assert serie_recente.sparklines(FakeCliente(db), aluno_ids=[A2]) == {A2: [2.0]}


def test_vetores_ignora_quem_nao_tem_vetor():
    db = _banco(
        aluno_serie_recente={
            A1: _serie(A1, [1.0], [5.0, None, 0.1]),
            A2: _serie(A2, [2.0], None),
        }
    )
    assert serie_recente.vetores(FakeCliente(db)) == {A1: [5.0, None, 0.1]}


# ─── O vetor do kNN ───────────────────────────────────────────────────────


def _linha_de_nota(aluno_id, materia_id, pontuacao, nota_maxima=10, **simulado):
    return {
        "aluno_id": aluno_id,
        "pontuacao": pontuacao,
        "simulado": {"materia_id": materia_id, "nota_maxima": nota_maxima, **simulado},
    }


def test_vetor_tem_uma_media_por_materia_em_ordem_alfabetica_depois_desvio_e_slope(monkeypatch):
    db = _banco(
        # Fora de ordem de propósito: a posição no vetor vem do NOME, não do id.
        materia={
            "m-mat": {"id": "m-mat", "nome": "Matemática"},
            "m-fis": {"id": "m-fis", "nome": "Física"},
        },
        classificacao_aluno={A1: {"aluno_id": A1, "coef_tendencia": "0.250"}},
    )
    monkeypatch.setattr(
        serie_recente,
        "_notas_para_vetor",
        lambda cliente, escopo: [
            _linha_de_nota(A1, "m-fis", 4, nota_maxima=10),
            _linha_de_nota(A1, "m-fis", 8, nota_maxima=10),
            _linha_de_nota(A1, "m-mat", 5, nota_maxima=20),  # 5/20 → 2,5 na escala 0–10
        ],
    )

    vetor = serie_recente.calcular_vetores(FakeCliente(db))[A1]

    # [Física, Matemática, desvio, slope]
    assert vetor[0] == pytest.approx(6.0)
    assert vetor[1] == pytest.approx(2.5)
    assert vetor[2] == pytest.approx(2.8431, abs=1e-3)  # desvio amostral de 4, 8 e 2,5
    assert vetor[3] == pytest.approx(0.25)


def test_vetor_deixa_none_onde_nao_ha_nota_da_materia(monkeypatch):
    db = _banco(
        materia={
            "m-fis": {"id": "m-fis", "nome": "Física"},
            "m-qui": {"id": "m-qui", "nome": "Química"},
        },
    )
    monkeypatch.setattr(
        serie_recente, "_notas_para_vetor", lambda cliente, escopo: [_linha_de_nota(A1, "m-fis", 6)]
    )

    vetor = serie_recente.calcular_vetores(FakeCliente(db))[A1]

    assert vetor == [6.0, None, None, None]  # uma nota só: sem desvio; sem classificação: sem slope


def test_vetor_descarta_prova_anulada_e_agregada(monkeypatch):
    db = _banco(materia={"m-fis": {"id": "m-fis", "nome": "Física"}})
    monkeypatch.setattr(
        serie_recente,
        "_notas_para_vetor",
        lambda cliente, escopo: [
            _linha_de_nota(A1, "m-fis", 10, anulado=True),
            _linha_de_nota(A2, "m-fis", 10, e_agregado=True),
            _linha_de_nota(A3, "m-fis", 7),
        ],
    )

    vetores = serie_recente.calcular_vetores(FakeCliente(db))

    assert set(vetores) == {A3}
