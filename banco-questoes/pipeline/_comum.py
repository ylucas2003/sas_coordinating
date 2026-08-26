"""Lógica compartilhada entre scripts do pipeline do acervo histórico.

`eh_historico()` existia duplicada entre `montar_manifesto_correcao.py` e um
script de correção via OpenAI (fora do repo hoje) sem que uma correção
aplicada num propagasse pro outro — causou `ime_2018_fase1` (prova já em
produção) ser reprocessada por engano duas vezes (docs/23 §9.3, §9.7). Quem
precisar decidir "isto é histórico" importa daqui, não reimplementa.
"""

import re


def eh_historico(prova_id: str) -> bool:
    """True para provas do acervo histórico (lotes A/B, docs/23 §1-3):
    ITA 2008-2018 e IME 1996-2018 fase 2. `ime_2018_fase1` é produção — a
    faixa de ano sozinha não basta para excluí-la (mesmo vestibular/ano tem
    fase em produção e fase nova no mesmo lote), por isso a exclusão
    explícita vem primeiro. Mantida idêntica à versão original de
    `montar_manifesto_correcao.py` — só o lugar mudou.
    """
    if prova_id.startswith("ime_2018_fase1"):
        return False
    m = re.match(r"(ita|ime)_(\d{4})_fase", prova_id)
    if not m:
        return False
    vest, ano = m.group(1), int(m.group(2))
    return (vest == "ita" and 2008 <= ano <= 2018) or (vest == "ime" and 1996 <= ano <= 2018)
