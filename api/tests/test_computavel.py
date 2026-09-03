"""A regra do zero que não é desempenho (docs/32 §1).

O que estes testes protegem, em ordem de custo se quebrar:

  1. A ORDEM dentro do sync. A evidência mora em `questao_resposta_aluno`, que
     o sync popula DEPOIS da nota. Avaliar antes classifica todo mundo como
     computável e some com o efeito sem erro nenhum — nenhuma exceção, nenhum
     log. É a falha silenciosa mais provável do sprint.
  2. A ESTREITEZA da regra. Ela só pega quem não marcou NADA. Quem respondeu
     tudo e errou tudo tirou zero, e o zero conta.
  3. A REVERSIBILIDADE. Evidência que muda tem de mover o veredicto nos dois
     sentidos, senão o banco acumula conclusões de uma regra que não vale mais.
"""

from __future__ import annotations

import pytest

from app.stats.computavel import TODAS_EM_BRANCO, avaliar_computavel, decidir
from app.stats.utils import simulado_entra_no_agregado

from .fake_postgrest import FakeCliente

# ─── A regra, pura ────────────────────────────────────────────────────────


def test_todas_em_branco_sai_da_conta():
    respostas = [
        {"alternativa_id": None, "balde_sem_alternativa": "none"},
        {"alternativa_id": None, "balde_sem_alternativa": "none"},
    ]
    assert decidir(respostas) == (False, TODAS_EM_BRANCO)


def test_uma_alternativa_marcada_ja_faz_a_nota_contar():
    respostas = [
        {"alternativa_id": None, "balde_sem_alternativa": "none"},
        {"alternativa_id": "alt-1", "balde_sem_alternativa": None},
    ]
    assert decidir(respostas) == (True, None)


def test_sem_evidencia_nao_se_conclui_nada():
    """89,7% dos zeros não têm dado de questão. Ali o zero conta."""
    assert decidir([]) == (True, None)


def test_balde_other_e_resposta_nao_e_branco():
    """`other` é marcação numa alternativa que não existe mais — não é branco.

    Até a 0043 os dois baldes viravam `alternativa_id IS NULL`, e a regra
    ficaria apoiada nessa conflação.
    """
    respostas = [{"alternativa_id": None, "balde_sem_alternativa": "other"}]
    assert decidir(respostas) == (True, None)


def test_linha_anterior_a_0043_conta_como_branco():
    """Balde nulo é linha gravada antes da coluna existir: ali `alternativa_id
    NULL` significava branco, e é assim que ela deve ser lida."""
    respostas = [{"alternativa_id": None, "balde_sem_alternativa": None}]
    assert decidir(respostas) == (False, TODAS_EM_BRANCO)


# ─── A régua do agregado ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "simulado, entra",
    [
        ({}, True),
        ({"anulado": True}, False),
        ({"e_agregado": True}, False),
        ({"nota_confiavel": False}, False),
        ({"nota_confiavel": True}, True),
        # Select que não pediu a coluna não pode esvaziar a estatística: o
        # default do banco é `true`, e presumir o contrário seria pior.
        ({"anulado": False, "e_agregado": False}, True),
    ],
)
def test_simulado_entra_no_agregado(simulado, entra):
    assert simulado_entra_no_agregado(simulado) is entra


# ─── O avaliador, contra o fake ───────────────────────────────────────────


def _banco(respostas: list[dict], notas: list[dict]) -> FakeCliente:
    return FakeCliente(
        {
            "questao": {
                "q1": {"id": "q1", "simulado_id": "S1"},
                "q2": {"id": "q2", "simulado_id": "S1"},
            },
            "questao_resposta_aluno": {
                (r["aluno_id"], r["questao_id"]): dict(r) for r in respostas
            },
            "nota": {(n["aluno_id"], n["simulado_id"]): dict(n) for n in notas},
        }
    )


BRANCO = {"alternativa_id": None, "balde_sem_alternativa": "none"}
ZERO_PRESENTE = {"pontuacao": 0, "presente": True, "computavel": True}


def test_avaliador_marca_quem_nao_respondeu_nada():
    cliente = _banco(
        respostas=[
            {"aluno_id": "A1", "questao_id": "q1", **BRANCO},
            {"aluno_id": "A1", "questao_id": "q2", **BRANCO},
        ],
        notas=[{"aluno_id": "A1", "simulado_id": "S1", **ZERO_PRESENTE}],
    )
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 1
    assert cliente.db["nota"][("A1", "S1")]["computavel"] is False
    assert cliente.db["nota"][("A1", "S1")]["motivo_nao_computavel"] == TODAS_EM_BRANCO


def test_avaliador_nao_toca_em_quem_respondeu_e_errou_tudo():
    cliente = _banco(
        respostas=[
            {"aluno_id": "A1", "questao_id": "q1", "alternativa_id": "x",
             "balde_sem_alternativa": None},
            {"aluno_id": "A1", "questao_id": "q2", "alternativa_id": "y",
             "balde_sem_alternativa": None},
        ],
        notas=[{"aluno_id": "A1", "simulado_id": "S1", **ZERO_PRESENTE}],
    )
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 0
    assert cliente.db["nota"][("A1", "S1")]["computavel"] is True


def test_a_regra_so_fala_de_zero_com_presenca():
    """Nota positiva com tudo em branco seria contradição do Canvas, não nossa
    — e a regra não pode 'corrigir' o Canvas por conta própria."""
    cliente = _banco(
        respostas=[
            {"aluno_id": "A1", "questao_id": "q1", **BRANCO},
            {"aluno_id": "A1", "questao_id": "q2", **BRANCO},
        ],
        notas=[{"aluno_id": "A1", "simulado_id": "S1",
                "pontuacao": 7, "presente": True, "computavel": True}],
    )
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 0
    assert cliente.db["nota"][("A1", "S1")]["computavel"] is True


def test_ausente_nao_vira_assunto_da_regra():
    cliente = _banco(
        respostas=[{"aluno_id": "A1", "questao_id": "q1", **BRANCO}],
        notas=[{"aluno_id": "A1", "simulado_id": "S1",
                "pontuacao": None, "presente": False, "computavel": True}],
    )
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 0
    assert cliente.db["nota"][("A1", "S1")]["computavel"] is True


def test_ordem_avaliar_antes_das_respostas_nao_marca_ninguem():
    """⚠️ O teste que existe por causa da falha silenciosa.

    Reproduz o sync rodando na ordem ERRADA: a nota já está gravada, as
    respostas ainda não chegaram. O avaliador tem de concluir 'não sei' — e o
    ponto do teste é que esse resultado é INDISTINGUÍVEL de 'está tudo certo'
    quando visto de fora. Só a ordem no `sincronizar.py` garante o contrário.
    """
    cliente = _banco(
        respostas=[],
        notas=[{"aluno_id": "A1", "simulado_id": "S1", **ZERO_PRESENTE}],
    )
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 0
    assert cliente.db["nota"][("A1", "S1")]["computavel"] is True

    # E, quando as respostas chegam, a segunda passada conclui.
    cliente.db["questao_resposta_aluno"] = {
        ("A1", "q1"): {"aluno_id": "A1", "questao_id": "q1", **BRANCO},
        ("A1", "q2"): {"aluno_id": "A1", "questao_id": "q2", **BRANCO},
    }
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 1
    assert cliente.db["nota"][("A1", "S1")]["computavel"] is False


def test_veredicto_volta_atras_quando_a_evidencia_muda():
    cliente = _banco(
        respostas=[
            {"aluno_id": "A1", "questao_id": "q1", **BRANCO},
            {"aluno_id": "A1", "questao_id": "q2", **BRANCO},
        ],
        notas=[{"aluno_id": "A1", "simulado_id": "S1", "pontuacao": 0,
                "presente": True, "computavel": False,
                "motivo_nao_computavel": TODAS_EM_BRANCO}],
    )
    # A resposta aparece (recorreção, re-sync): o veredicto tem de cair.
    cliente.db["questao_resposta_aluno"][("A1", "q1")]["alternativa_id"] = "alt-1"
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 1
    assert cliente.db["nota"][("A1", "S1")]["computavel"] is True
    assert cliente.db["nota"][("A1", "S1")]["motivo_nao_computavel"] is None


def test_idempotente():
    cliente = _banco(
        respostas=[
            {"aluno_id": "A1", "questao_id": "q1", **BRANCO},
            {"aluno_id": "A1", "questao_id": "q2", **BRANCO},
        ],
        notas=[{"aluno_id": "A1", "simulado_id": "S1", **ZERO_PRESENTE}],
    )
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 1
    assert avaliar_computavel(cliente, simulado_ids=["S1"]) == 0


def test_sem_simulado_nao_faz_consulta_nenhuma():
    cliente = _banco(respostas=[], notas=[])
    assert avaliar_computavel(cliente, simulado_ids=[]) == 0
