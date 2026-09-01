"""Trava sobre o saneamento de `resolucao_md` no importador do banco.

O bug que originou este arquivo custou meses sem ninguém ver: a resolução é
escrita por LLM e volta dentro de um campo de string JSON, e quando o modelo
escreve `\\text{...}` sem escapar a barra, quem lê o JSON faz o que a
especificação manda — `\\t` é uma tabulação. Chegou ao banco `<TAB>ext{...}`,
`<FF>rac{...}`, `<BS>oldsymbol` em 20 das 1.500 resoluções. Passou despercebido
porque o texto ia CRU para a tela: ninguém lê LaTeX cru, então ninguém
distinguia uma barra a menos do resto da notação.

A migration 0039 consertou o acervo; `_resolucao_saneada` impede a próxima
importação de trazer de volta. O que este teste protege é a ORDEM: se alguém
puser `_sem_controles` antes da reposição da barra, o backspace some e
`\\boldsymbol` vira `oldsymbol` — o conserto vira perda silenciosa, que é
exatamente o modo de falha original.
"""

from __future__ import annotations

import pytest

from app.banco.importador import _resolucao_saneada


@pytest.mark.parametrize(
    ("corrompido", "esperado", "comando"),
    [
        ("$a=\tfrac{1}{2}$", "$a=\\tfrac{1}{2}$", "\\tfrac"),
        ("o campo $\boldsymbol B$", "o campo $\\boldsymbol B$", "\\boldsymbol"),
        ("$u=\frac{m v}{2}$", "$u=\\frac{m v}{2}$", "\\frac"),
        ("$x\right)$", "$x\\right)$", "\\right"),
    ],
)
def test_repoe_a_barra_que_o_parser_de_json_comeu(corrompido, esperado, comando):
    assert _resolucao_saneada(corrompido) == esperado
    assert comando in _resolucao_saneada(corrompido)


def test_a_reposicao_vem_antes_da_limpeza_de_controles():
    """Backspace e formfeed são C0: `_sem_controles` os APAGARIA.

    Se a ordem inverter, o resultado vira `oldsymbol`/`rac` — texto plausível,
    erro invisível. É o pior modo de falha possível para este dado.
    """
    saneado = _resolucao_saneada("$\begin{pmatrix}a\frac12\bigr$")

    assert saneado == "$\\begin{pmatrix}a\\frac12\\bigr$"
    assert "oldsymbol" not in saneado
    assert "\x08" not in saneado and "\x0c" not in saneado


def test_crlf_e_fim_de_linha_e_nao_right_picado():
    """Um JSON salvo no Windows não pode ganhar um `\\r` literal por quebra."""
    assert _resolucao_saneada("linha um\r\nlinha dois") == "linha um\nlinha dois"


def test_controle_que_nao_e_escape_de_json_continua_saindo():
    """O ETX do PDF da ITA 2008 não vira comando nenhum — some, como antes."""
    assert _resolucao_saneada("campo \x03B\x03 sai") == "campo B sai"


def test_texto_limpo_atravessa_intacto():
    limpo = "Pela equação de Nernst: $E = E^\\circ - \\dfrac{0,059}{3}\\log Q$.\n\n$$E=-1,73$$"

    assert _resolucao_saneada(limpo) == limpo


@pytest.mark.parametrize("vazio", [None, ""])
def test_vazio_vira_none_como_a_coluna_espera(vazio):
    """`resolucao_md` é opcional, e o CHECK da 0031 lê NULL — não string vazia."""
    assert _resolucao_saneada(vazio) is None
