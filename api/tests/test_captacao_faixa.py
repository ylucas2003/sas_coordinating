"""Régua de faixa da captação (docs/41 §20, `_captacao_comum.classificar_faixa`).

Os pares abaixo são textos REAIS de `conquista_externa.resultado`, um de cada
forma que cada fonte publica (levantados do banco em 07/10/2026). Fonte nova,
ou texto novo numa fonte velha, entra aqui junto com a regra que a cobre — o
importador recusa o lote inteiro enquanto a régua não souber classificar.
"""

from __future__ import annotations

import pytest

from scripts._captacao_comum import FAIXAS, classificar_faixa

CASOS = [
    ("OBMEP", "Ouro — rede pública", "ouro"),
    ("OBMEP", "Prata — rede privada", "prata"),
    ("OBMEP", "Bronze — rede pública", "bronze"),
    ("OBM", "Ouro Especial", "ouro"),
    ("OBM", "Menção Honrosa", "mencao"),
    ("OBF", "MEDALHA DE OURO", "ouro"),
    ("OBF", "MENÇÃO HONROSA", "mencao"),
    ("OBI", "Bronze", "bronze"),
    ("OBQ", "Demais Classificados", "finalista"),
    ("OBQ Jr", "Prata", "prata"),
    ("ITA", "Realizou a 1ª fase", "participou"),
    ("ITA", "Ausente — 1ª fase", "ausente"),
    ("ITA", "Convocado — 2ª fase", "passou_de_fase"),
    ("ITA", "Não classificado — 2ª fase", "passou_de_fase"),
    ("ITA", "Classificado — 2ª fase (nº 93)", "classificado_final"),
    ("ITA", "Ampla Concorrência", "aprovado"),
    ("ITA", "RESERVA (Cota Racial)", "aprovado"),  # carreira militar, não lista de espera
    ("IME", "Habilitado — 2ª fase (ATIVA)", "passou_de_fase"),
    ("IME", "Não aprovado — 2ª fase (nota mínima: FIS)", "passou_de_fase"),
    ("IME", "Não aprovado — 2ª fase (inapto em redação)", "passou_de_fase"),
    ("IME", "ATIVA — excedente", "classificado_final"),
    ("IME", "RESERVA", "aprovado"),
    ("IME", "ATIVA — Lei 12.990 (cota racial)", "aprovado"),
    ("EFOMM", "CIABA — Pós-classificado (1ª fase)", "passou_de_fase"),
    ("EFOMM", "CIAGA — Pós-classificado (2ª convocação, 1ª fase)", "passou_de_fase"),
    ("EFOMM", "CIAGA — Titular (classificação final)", "aprovado"),
    ("EFOMM", "CIAGA — Reserva (classificação final)", "classificado_final"),  # lista de espera
    ("Escola Naval (CPAEN)", "Não eliminado nas provas escritas (seleção inicial)", "passou_de_fase"),
    ("Escola Naval (CPAEN)", "Resultado da Seleção Inicial — Reserva", "passou_de_fase"),
    ("Escola Naval (CPAEN)", "Resultado Final da Seleção — Titular", "aprovado"),
    ("Escola Naval (CPAEN)", "Resultado Final — Reserva", "classificado_final"),
]


@pytest.mark.parametrize(("prova", "resultado", "esperada"), CASOS)
def test_classificar_faixa(prova, resultado, esperada):
    assert classificar_faixa(prova, resultado) == esperada


def test_toda_faixa_esperada_existe_no_vocabulario():
    # O CHECK da migration 0068 tem a mesma lista — divergir quebraria o
    # importador com 23514 no meio de um lote.
    assert {esperada for *_, esperada in CASOS} <= set(FAIXAS)


def test_prova_sem_regua_falha_alto():
    with pytest.raises(ValueError, match="sem régua"):
        classificar_faixa("OBA", "Ouro")


def test_resultado_desconhecido_falha_alto():
    with pytest.raises(ValueError, match="não casa"):
        classificar_faixa("OBMEP", "Platina — rede pública")
