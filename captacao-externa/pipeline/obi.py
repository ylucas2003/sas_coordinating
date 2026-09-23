"""Raspa o Quadro de Medalhas da OBI (Olimpíada Brasileira de Informática) —
Ouro/Prata/Bronze (e, onde a própria tabela já trouxer, Menção Honrosa) por
modalidade/nível — e grava um JSON cru por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/obi.py --anos 2022 2023 2024 2025
    ./.venv/bin/python pipeline/obi.py --anos 2016 2017 2018 2019 2020 2021

Cada ano vira dados/obi_{ano}.json — mesmo formato dos outros scrapers (ver
docstring de pipeline/obmep.py pro contrato de campos).

## Descoberta de modalidade é DINÂMICA, não uma lista fixa

`olimpiada.ic.unicamp.br/passadas/OBI{ano}/` lista, em cada ano, links pro
Quadro de Medalhas de cada modalidade/nível
(`/passadas/OBI{ano}/qmerito/{código}/`). O CÓDIGO da URL muda de sentido
entre edições — `pu` foi "Modalidade Universitária" em 2015 e "Modalidade
Programação Nível Sênior" em 2020+; `ij` (Iniciação Júnior) só passou a
existir por volta de 2020 — então este scraper nunca hardcoda a lista de
modalidades: ele lê os links de fato presentes na página-índice de cada ano e
usa o TEXTO do link (menos o prefixo "Modalidade ") como `nivel_texto`.

## Dois achados de formato, nenhum óbvio sem abrir o HTML de verdade

1. **A largura da tabela varia (6 ou 7 células) segundo o ano tem ou não uma
   coluna de "Pontos"/"Nota"** — mas isso não importa pra este pipeline:
   `conquista_externa` não guarda pontuação nem posição, só identidade e
   resultado. Por isso o parser lê o marcador de medalha pela PRIMEIRA célula
   e nome/escola/cidade/estado pelas ÚLTIMAS QUATRO, ignorando o que sobra no
   meio (classificação, pontos) — mesmo truque do `celulas[-6:]` de
   `pipeline/obmep.py`, adaptado pra largura que também varia pela ponta de
   trás em vez de só pela da frente.
2. **2008 e 2009 têm uma tabela-FANTASMA antes da de verdade** — um
   `<table>` de uma linha só, artefato de espaçamento da legenda de medalhas
   ("=Medalha de Ouro, =Medalha de Prata..."), com todas as células vazias.
   `soup.find("table")` pega essa e devolve zero registro em silêncio; a
   correção é pegar a tabela com MAIS linhas na página, não a primeira.

## O marcador de medalha muda de forma: imagem, ou texto puro

2005 escreve a medalha como TEXTO puro na primeira célula ("Ouro"/"Prata"/
"Bronze"), sem coluna de classificação nenhuma. De 2006 em diante a medalha
vira uma `<img src=".../medalhinha_{cor}.gif">`, e a Menção Honrosa (que
existe desde pelo menos 2006) aparece como texto puro "HM" na MESMA célula,
na MESMA tabela — diferente da OBMEP, aqui entra de graça, sem requisição
extra, mesmo raciocínio que já valia pra Menção Honrosa da OBM/OBF
(docs/41 §5.1/§5.2).

⚠️ **A partir de 2025 isso mudou**: a Menção Honrosa saiu da tabela principal
e passou a viver numa página SEPARADA por UF ("Honra ao Mérito Estadual",
`/passadas/OBI{ano}/honra_estadual/{nível}/`, uma pra cada uma de ~24
unidades federativas) — o mesmo custo (uma requisição por UF) que fez a
OBMEP excluir Menção Honrosa de propósito (docs/41 §5). Esta versão do
scraper não segue esse link: Menção Honrosa de 2025 em diante fica de fora,
mesma decisão de custo/sinal, documentada aqui em vez de escondida.

## Competição Feminina (CF-OBI) é prova PRÓPRIA, fora de escopo

Desde 2023 a página também lista `/passadas/OBI{ano}/cfqmerito/...` — o
Quadro de Medalhas da Competição Feminina da OBI, que o próprio regulamento
descreve como "opcional" e com "resultado independente do resultado da OBI".
Por ser uma competição distinta (não um recorte do mesmo resultado), fica de
fora desta rodada — entraria como fonte própria, não como extensão da OBI.
O filtro de link (`_PADRAO_LINK_QMERITO`) já a exclui: casa `/qmerito/`
precedido de `/`, e `cfqmerito` nunca tem essa barra ali.

## Anos suportados: a partir de 2005

`/passadas/OBI{ano}/qmerito/` só existe a partir de 2005 — 1999-2004
publicam só `/passadas/OBI{ano}/iniciacao/` e `/programacao/` inteiros, sem
quebrar por nível, num formato mais antigo ainda não investigado (e de valor
baixo pra captação: são resultados de 20+ anos atrás — docs/41 §2, "resultado
antigo é lead frio"). Pedir um ano sem link de `qmerito` sai com aviso, não
erro.

⚠️ **2018 não existe — confirmado abrindo a URL, não suposição.** O índice
`/passadas/` lista um link pra `OBI2018/`, mas a página em si devolve 404 (não
é bug deste scraper: `curl` direto no mesmo endereço confirma). Mesma
categoria do buraco de 2020 da OBMEP (docs/41 §5) — ausência real do lado do
site, não falha de raspagem; `raspar_ano` deixa o `HTTPError` subir e `main`
já pula pro próximo ano da lista sozinho.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

BASE = "https://olimpiada.ic.unicamp.br"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# nivel_texto (já sem o prefixo "Modalidade ") -> faixa de série, só pros
# níveis que o regulamento da OBI define com precisão (fundamenta.org/info/
# regulamento/). Nível 1/2 de Programação valem tanto pro fundamental quanto
# pro médio ("alunos do Ensino Fundamental e até o 3º ano do Médio") — faixa
# tão larga que guardar um número específico inventaria precisão que a fonte
# não dá (mesmo cuidado do docs/41 §3 com serie_referencia), por isso ficam
# de fora do dict e caem no default (None, None).
NIVEL_SERIE: dict[str, tuple[int, int]] = {
    "Iniciação Nível Júnior": (4, 5),
    "Iniciação Nível 1": (6, 7),
    "Iniciação Nível 2": (8, 9),
    "Programação Nível Júnior": (8, 9),
}

_MEDALHA_POR_ARQUIVO = {"ouro": "Ouro", "prata": "Prata", "bronze": "Bronze"}
_PADRAO_ANO = re.compile(r"OBI(\d{4})")


@dataclass
class Registro:
    prova_nome: str
    ano: int
    nivel_texto: str
    serie_referencia_min: int | None
    serie_referencia_max: int | None
    resultado: str
    nome_informado: str
    escola_informada: str
    cidade_informada: str
    uf_informada: str
    fonte_url: str


def _links_qmerito(html: str, ano: int) -> list[tuple[str, str]]:
    """[(nivel_texto, url), ...] — lidos de verdade da página-índice do ano,
    nunca de uma lista fixa de códigos (docstring do módulo)."""
    padrao = re.compile(rf"^/passadas/OBI{ano}/qmerito/[\w-]+/$")
    sopa = BeautifulSoup(html, "lxml")
    vistos: set[str] = set()
    links: list[tuple[str, str]] = []
    for a in sopa.find_all("a", href=True):
        href = a["href"]
        if not padrao.match(href) or href in vistos:
            continue
        vistos.add(href)
        nivel_texto = re.sub(r"^Modalidade\s+", "", a.get_text(strip=True))
        links.append((nivel_texto, f"{BASE}{href}"))
    return links


def _tabela_resultado(sopa: BeautifulSoup) -> Tag | None:
    """A tabela com MAIS linhas na página — nunca a primeira encontrada:
    2008/2009 têm uma tabela-fantasma de uma linha só (espaçamento da
    legenda) antes da tabela de resultado de verdade."""
    tabelas = sopa.find_all("table")
    if not tabelas:
        return None
    return max(tabelas, key=lambda t: len(t.find_all("tr")))


def _medalha(celula: Tag) -> str | None:
    """A medalha vem como imagem (`medalhinha_{cor}.gif`) desde 2006, ou
    como texto puro em 2005 (a própria palavra) e na Menção Honrosa de
    qualquer ano ("HM"). Célula de cabeçalho/legenda não casa nenhum dos
    dois formatos e devolve None, sinal pra pular a linha."""
    img = celula.find("img")
    if img is not None:
        m = re.search(r"medalhinha_(\w+)\.gif", img.get("src", ""))
        return _MEDALHA_POR_ARQUIVO.get(m.group(1)) if m else None
    texto = celula.get_text(strip=True)
    if texto == "HM":
        return "Menção Honrosa"
    if texto in _MEDALHA_POR_ARQUIVO.values():
        return texto
    return None


def parsear_pagina_nivel(html: str, ano: int, nivel_texto: str, fonte_url: str) -> list[Registro]:
    sopa = BeautifulSoup(html, "lxml")

    m_ano = _PADRAO_ANO.search(sopa.get_text(" "))
    if not m_ano or int(m_ano.group(1)) != ano:
        achado = m_ano.group(0) if m_ano else "nenhum ano"
        print(f"    aviso: {fonte_url} não confirma OBI{ano} (achei {achado!r}) — pulando", file=sys.stderr)
        return []

    tabela = _tabela_resultado(sopa)
    if tabela is None:
        print(f"    aviso: nenhuma tabela em {fonte_url}", file=sys.stderr)
        return []

    serie_min, serie_max = NIVEL_SERIE.get(nivel_texto, (None, None))
    registros: list[Registro] = []
    for linha in tabela.find_all("tr"):
        celulas = linha.find_all("td")
        if len(celulas) < 5:
            continue
        medalha = _medalha(celulas[0])
        if medalha is None:
            continue  # cabeçalho ou legenda, não linha de dado
        nome, escola, cidade, uf = (c.get_text(strip=True) for c in celulas[-4:])
        if not nome:
            continue
        registros.append(
            Registro(
                prova_nome="OBI",
                ano=ano,
                nivel_texto=nivel_texto,
                serie_referencia_min=serie_min,
                serie_referencia_max=serie_max,
                resultado=medalha,
                nome_informado=nome,
                escola_informada=escola,
                cidade_informada=cidade,
                uf_informada=uf,
                fonte_url=fonte_url,
            )
        )
    return registros


def raspar_ano(ano: int) -> list[Registro]:
    resp = requests.get(f"{BASE}/passadas/OBI{ano}/", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    links = _links_qmerito(resp.text, ano)
    if not links:
        print(f"  OBI {ano}: nenhum link de /qmerito/ — ano fora do formato suportado (ver docstring)", file=sys.stderr)
        return []

    registros: list[Registro] = []
    for nivel_texto, url in links:
        time.sleep(0.5)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.HTTPError as e:
            print(f"    aviso: falhou {url}: {e}", file=sys.stderr)
            continue
        novos = parsear_pagina_nivel(resp.text, ano, nivel_texto, url)
        registros.extend(novos)
        print(f"    {nivel_texto}: {len(novos)} registros", file=sys.stderr)
    return registros


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--anos", type=int, nargs="+", required=True, help="Anos a raspar (>= 2005 — ver docstring)")
    args = parser.parse_args()

    DIR_DADOS.mkdir(exist_ok=True)

    for ano in args.anos:
        print(f"OBI {ano} — raspando...", file=sys.stderr)
        try:
            registros = raspar_ano(ano)
        except requests.HTTPError as e:
            print(f"  falhou: {e}", file=sys.stderr)
            continue

        if not registros:
            print("  0 registros — algo mudou no site, confira antes de importar", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"obi_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  OBI {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
