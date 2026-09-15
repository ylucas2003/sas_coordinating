"""Raspa os premiados NACIONAIS da OBMEP (medalhas de ouro/prata/bronze,
escolas públicas e privadas) e grava um JSON cru por edição em dados/.

Uso:
    ./.venv/bin/python pipeline/obmep.py --edicoes 17 18 19 20

Cada edição vira dados/obmep_{ano}.json — uma lista de registros no formato
que api/scripts/importar_captacao_externa.py espera (chaves: prova_nome, ano,
nivel_texto, serie_referencia_min/max, resultado, nome_informado,
escola_informada, cidade_informada, uf_informada, fonte_url).

Por que só Ouro/Prata/Bronze nacional, sem Menção Honrosa: Menção Honrosa só
existe por UF (27 estados × 3 níveis × pública/privada = 162 requisições por
edição) e é sinal mais fraco pra captação — fica pra quando a fase de medalha
já tiver sido validada (ver "Dossiê de Provas", arquivo 05, nota sobre o
volume da OBMEP).

Cobertura real: as edições existem em premiacao.obmep.org.br/{N}obmep/ só a
partir da 17ª (2022) — 14ª/15ª/16ª (2019/2020/2021) devolvem 404 nesse
domínio. O "Dossiê de Provas" já registrou isso em parte (falta o ano 2020 na
página-índice obmep.org.br/premiados.htm); os anos 2019/2021 podem estar
hospedados noutro lugar — não investigado ainda, fica pra uma próxima rodada.
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
from bs4 import BeautifulSoup

BASE = "https://premiacao.obmep.org.br"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

# Nível → faixa de série (6 = 6º ano EF ... 12 = 3º ano do médio). Nível 1 é
# 6º-7º EF, Nível 2 é 8º-9º EF, Nível 3 é toda a série do médio — definição
# pública da própria OBMEP, estável desde a criação da prova.
NIVEL_SERIE = {
    "Nível 1": (6, 7),
    "Nível 2": (8, 9),
    "Nível 3": (10, 12),
}

# Âncora conhecida: a 20ª OBMEP é 2025 (confirmado no próprio HTML). Editições
# sem o ano escrito no cabeçalho (17ª e 18ª, nesta pesquisa) usam esta conta.
EDICAO_ANCORA, ANO_ANCORA = 20, 2025

MEDALHAS = ["Ouro", "Prata", "Bronze"]
REDES = {"": "pública", ".privada": "privada"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


@dataclass
class Registro:
    prova_nome: str
    ano: int
    nivel_texto: str
    serie_referencia_min: int
    serie_referencia_max: int
    resultado: str
    nome_informado: str
    escola_informada: str
    cidade_informada: str
    uf_informada: str
    fonte_url: str


def ano_da_edicao(edicao: int, html_ouro_publica: str) -> int:
    """Extrai o ano do cabeçalho da página; cai pra conta por âncora se a
    fonte não escreveu o ano (aconteceu nas edições 17ª/18ª)."""
    m = re.search(r"\d+ª OBMEP (\d{4})", html_ouro_publica)
    if m:
        return int(m.group(1))
    return ANO_ANCORA - (EDICAO_ANCORA - edicao)


def raspar_pagina(sessao: requests.Session, url: str, referer: str) -> str:
    resp = sessao.get(url, headers={**HEADERS, "Referer": referer}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parsear_pagina_medalha(html: str, prova_nome: str, ano: int, medalha: str, rede: str, fonte_url: str) -> list[Registro]:
    sopa = BeautifulSoup(html, "lxml")
    registros: list[Registro] = []

    for ancora in sopa.find_all("a", attrs={"name": re.compile(r"^nivel\d$")}):
        tabela = ancora.find_next("table", class_="list")
        if tabela is None:
            continue
        nivel_texto_tag = tabela.find("font", size="+2")
        nivel_texto = nivel_texto_tag.get_text(strip=True) if nivel_texto_tag else ancora["name"]
        serie_min, serie_max = NIVEL_SERIE.get(nivel_texto, (None, None))

        corpo = tabela.find("tbody")
        if corpo is None:
            continue
        for linha in corpo.find_all("tr"):
            celulas = [c.get_text(strip=True) for c in linha.find_all("td")]
            # [seq (às vezes vazio), nome, escola, tipo, município, uf, medalha]
            if len(celulas) < 7:
                continue
            _seq, nome, escola, _tipo, municipio, uf, medalha_cel = celulas[:7]
            if not nome:
                continue
            registros.append(
                Registro(
                    prova_nome=prova_nome,
                    ano=ano,
                    nivel_texto=nivel_texto,
                    serie_referencia_min=serie_min,
                    serie_referencia_max=serie_max,
                    resultado=f"{medalha_cel or medalha} — rede {rede}",
                    nome_informado=nome,
                    escola_informada=escola,
                    cidade_informada=municipio,
                    uf_informada=uf,
                    fonte_url=fonte_url,
                )
            )
    return registros


def raspar_edicao(edicao: int) -> tuple[int, list[Registro]]:
    sessao = requests.Session()
    mapa_url = f"{BASE}/{edicao}obmep/mapa.htm"
    raspar_pagina(sessao, mapa_url, mapa_url)  # estabelece o referer real
    time.sleep(0.5)

    registros: list[Registro] = []
    ano: int | None = None

    for medalha in MEDALHAS:
        for sufixo, rede in REDES.items():
            url = f"{BASE}/{edicao}obmep/verRelatorioPremiados{medalha}{sufixo}.do.htm"
            html = raspar_pagina(sessao, url, mapa_url)
            if ano is None:
                ano = ano_da_edicao(edicao, html)
            registros.extend(parsear_pagina_medalha(html, "OBMEP", ano, medalha, rede, url))
            time.sleep(0.5)

    assert ano is not None
    return ano, registros


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--edicoes", type=int, nargs="+", required=True, help="Números de edição da OBMEP (ex.: 17 18 19 20)")
    args = parser.parse_args()

    DIR_DADOS.mkdir(exist_ok=True)

    for edicao in args.edicoes:
        print(f"OBMEP {edicao}ª — raspando...", file=sys.stderr)
        try:
            ano, registros = raspar_edicao(edicao)
        except requests.HTTPError as e:
            print(f"  falhou: {e}", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"obmep_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  {edicao}ª OBMEP = {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
