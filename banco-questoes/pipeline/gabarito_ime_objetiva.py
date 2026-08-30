"""Gabarito da prova OBJETIVA do IME (fase 1), lido do PDF que vem ao lado da prova.

Por que este arquivo existe separado de `extrair_gabarito.py`: aquele lê o
gabarito do ITA, que é uma tabela estável. O do IME **não tem formato**: ao longo
de 2007–2018 o mesmo documento aparece em quatro geometrias diferentes, e a
leitura em ordem de texto (`pdftotext`) devolve coisas diferentes em cada uma:

    2007, 2008, 2012   duas colunas intercaladas   "01 ANULADA 21 E"
    2013, 2014         coluna única                "1 C / 2 ANULADA / 3 C"
    2015               a página inteira ROTACIONADA 90°, a resposta fica ACIMA
                       do número, e os números nem saem na ordem do texto
    2018               todos os números primeiro, todas as letras depois
                       ("Questão 1..15" e só então "Gabarito D D E B ...")

Nenhuma leitura em ordem de texto atravessa as quatro. Por isso aqui se lê por
COORDENADA — e por duas estratégias independentes, que precisam **concordar**:

    por linha    a resposta pertence ao número da mesma faixa vertical, o mais
                 próximo à esquerda. Resolve as colunas intercaladas, onde o
                 vizinho mais próximo em distância pode ser o da linha de cima.
    por vizinho  a resposta pertence ao número mais próximo em distância. É o
                 único que sobrevive à página rotacionada, onde "à esquerda"
                 não quer dizer nada.

Onde as duas concordam e cobrem 1–40 sem furo, o gabarito entra. Onde divergem,
**o ano não entra** e o relatório diz qual questão divergiu — errar aqui é o
tipo de erro que não aparece na tela: o aluno estuda e confere com a letra
errada. Ver docs/23 §23.

**Quando duas respostas caem no mesmo número, vence a desenhada por último.**
Não é desempate arbitrário: é o que a pessoa enxerga. O IME publica correção
carimbando por cima do valor antigo, sem tirar o antigo do arquivo — em
`CFG-Objetiva-2016-2017-Gabarito.pdf` a tabela é Calibri 11 e as correções das
questões 25 e 27 são Arial 10, em blocos próprios, depois no fluxo. Quem lê o
PDF vê D e A; quem guardasse a primeira gravaria C e B, que são as respostas
substituídas. `ANULADA` cai na mesma regra, sem precisar de caso especial —
o carimbo também vem depois.

Toda sobreposição é reportada em `avisos`, mesmo quando resolvida. Guardar a
primeira **em silêncio** foi o que pôs duas letras erradas no banco em 29/08,
e as duas leituras abaixo não pegaram porque erraram igual (docs/23 §23.7).

Questão anulada entra com `gabarito = None` — a banca disse que não há resposta
única, e sugerir uma seria inventar (mesma regra que docs/23 §2.2 pede para o ITA).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pymupdf

_RESPOSTA = re.compile(r"^([A-E])$")
_ANULADA = re.compile(r"^ANULAD[AO]$", re.IGNORECASE)
# `0?` porque 2007 e 2008 escrevem "01".."09" com zero à esquerda.
_NUMERO = re.compile(r"^0?(\d{1,2})$")

ANULADA = "ANULADA"


def _palavras(pagina, maximo: int) -> tuple[list, list]:
    """Números de questão e respostas da página, cada um com centro, caixa e ORDEM.

    A ordem é o índice no fluxo de conteúdo, que é a ordem em que o PDF pinta —
    quem vem depois cobre quem veio antes. É o que decide a correção carimbada.
    """
    numeros, respostas = [], []
    for ordem, (x0, y0, x1, y1, texto, *_) in enumerate(pagina.get_text("words")):
        t = texto.strip()
        centro = ((x0 + x1) / 2, (y0 + y1) / 2)
        if (m := _NUMERO.match(t)) and 1 <= int(m.group(1)) <= maximo:
            numeros.append((int(m.group(1)), centro, x0, x1, y0, y1))
        elif _RESPOSTA.match(t) or _ANULADA.match(t):
            letra = ANULADA if _ANULADA.match(t) else t.upper()
            respostas.append((letra, centro, x0, x1, y0, y1, ordem))
    return numeros, respostas


def _juntar(achados: dict[int, tuple[str, int]], numero: int, letra: str, ordem: int,
            sobreposicoes: list[str]) -> None:
    """Grava `(letra, ordem)`, deixando vencer a desenhada por último.

    Sobreposição nunca passa calada, mesmo resolvida: é sinal de correção
    publicada por cima — e foi ignorá-la que produziu o erro do §23.7.
    """
    atual = achados.get(numero)
    if atual is None:
        achados[numero] = (letra, ordem)
        return
    letra_atual, ordem_atual = atual
    if letra_atual == letra:
        return
    vencedora, perdedora = ((letra, letra_atual) if ordem > ordem_atual
                            else (letra_atual, letra))
    sobreposicoes.append(f"q{numero}: {perdedora} coberta por {vencedora}")
    if ordem > ordem_atual:
        achados[numero] = (letra, ordem)


def _por_linha(numeros, respostas, sobreposicoes) -> dict[int, tuple[str, int]]:
    achados: dict[int, tuple[str, int]] = {}
    for letra, (_, rcy), rx0, _, ry0, ry1, ordem in respostas:
        tolerancia = max(ry1 - ry0, 6) * 0.6
        candidatos = [n for n in numeros if abs(n[1][1] - rcy) <= tolerancia and n[3] <= rx0 + 1]
        if candidatos:
            _juntar(achados, max(candidatos, key=lambda n: n[3])[0], letra, ordem, sobreposicoes)
    return achados


def _por_vizinho(numeros, respostas, sobreposicoes) -> dict[int, tuple[str, int]]:
    achados: dict[int, tuple[str, int]] = {}
    for letra, (rx, ry), *_, ordem in respostas:
        if numeros:
            perto = min(numeros, key=lambda n: math.hypot(n[1][0] - rx, n[1][1] - ry))
            _juntar(achados, perto[0], letra, ordem, sobreposicoes)
    return achados


def ler(pdf: Path, maximo: int = 40) -> tuple[dict[int, str] | None, list[str]]:
    """Devolve `({numero: letra|ANULADA}, avisos)`, ou `(None, avisos)` se não deu.

    `None` não é "o PDF é ruim": é "as duas leituras não convergiram, e uma letra
    errada aqui não teria sintoma nenhum". Quem chama decide se importa a prova
    sem gabarito ou se segura o ano.
    """
    documento = pymupdf.open(pdf)
    mapas: dict[str, dict[int, tuple[str, int]]] = {"linha": {}, "vizinho": {}}
    # Sobreposição por estratégia, não numa lista só: a leitura por vizinho
    # embaralha as colunas intercaladas de 2007, 2008 e 2012 e acusaria vinte
    # carimbos que não existem. Aviso que grita à toa ensina a ignorar aviso.
    marcas: dict[str, list[str]] = {"linha": [], "vizinho": []}
    deslocamento = 0
    for pagina in documento:
        numeros, respostas = _palavras(pagina, maximo)
        # A ordem tem de crescer entre páginas, senão a resposta da página 2
        # pareceria anterior à da página 1 na hora de decidir quem cobre quem.
        respostas = [(*r[:-1], r[-1] + deslocamento) for r in respostas]
        deslocamento += len(pagina.get_text("words"))
        for chave, estrategia in (("linha", _por_linha), ("vizinho", _por_vizinho)):
            achado = estrategia(numeros, respostas, marcas[chave])
            for n, (letra, ordem) in achado.items():
                _juntar(mapas[chave], n, letra, ordem, marcas[chave])
    documento.close()

    completas = {chave: {n: letra for n, (letra, _) in mapa.items()}
                 for chave, mapa in mapas.items()
                 if set(mapa) == set(range(1, maximo + 1))}
    avisos: list[str] = []
    if not completas:
        faltam = sorted(set(range(1, maximo + 1)) - (set(mapas["linha"]) | set(mapas["vizinho"])))
        avisos.append(f"nenhuma leitura cobriu 1–{maximo}; sem resposta para {faltam}")
        return None, avisos
    if len(completas) == 2:
        a, b = completas["linha"], completas["vizinho"]
        divergem = sorted(n for n in a if a[n] != b[n])
        if divergem:
            detalhe = ", ".join(f"q{n}: linha={a[n]} vizinho={b[n]}" for n in divergem)
            avisos.append(f"as duas leituras divergem em {len(divergem)} questão(ões) — {detalhe}")
            return None, avisos
    else:
        avisos.append("só uma das duas leituras cobriu a prova inteira — confira à mão")

    escolhida = next(iter(completas))
    for texto in dict.fromkeys(marcas[escolhida]):
        avisos.append(f"resposta carimbada por cima de outra — {texto}")
    escolhido = completas[escolhida]
    anuladas = sorted(n for n, letra in escolhido.items() if letra == ANULADA)
    if anuladas:
        avisos.append(f"anuladas pela banca: {anuladas}")
    return escolhido, avisos
