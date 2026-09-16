"""Raspa os premiados NACIONAIS da OBMEP (medalhas de ouro/prata/bronze,
escolas públicas e privadas) e grava um JSON cru por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/obmep.py --anos 2022 2023 2024 2025
    ./.venv/bin/python pipeline/obmep.py --anos 2016 2017 2018 2019 2021

Cada ano vira dados/obmep_{ano}.json — uma lista de registros no formato que
api/scripts/importar_captacao_externa.py espera (chaves: prova_nome, ano,
nivel_texto, serie_referencia_min/max, resultado, nome_informado,
escola_informada, cidade_informada, uf_informada, fonte_url).

Por que só Ouro/Prata/Bronze nacional, sem Menção Honrosa: Menção Honrosa só
existe por UF (27 estados × 3 níveis × pública/privada = 162 requisições por
edição) e é sinal mais fraco pra captação — fica pra quando a fase de medalha
já tiver sido validada (ver "Dossiê de Provas", arquivo 05, nota sobre o
volume da OBMEP).

## Por que é ANO, e não EDIÇÃO (docs/41 §8, item 5 — lacuna fechada)

A primeira rodada (17ª-20ª = 2022-2025) parametrizava por número de edição e
montava a URL como `{edição}obmep`. Isso quebra pra trás: o próprio
`obmep.org.br/premiados.htm` — achado no "Dossiê de Provas", arquivo 01 —
lista TRÊS convenções de URL diferentes conforme o ano, e a numeração de
edição não é linear (2020 não existe: a pandemia suspendeu aquela edição
inteira, sem numeração reaproveitada depois). Editar por ANO em vez de EDIÇÃO
elimina essa aritmética frágil — o ano é a chave real (`conquista_externa.ano`),
a edição é só como o site se chama por dentro.

`SEGMENTO_POR_ANO` é o mapa dessas três convenções, uma entrada por ano
verificado manualmente (não adivinhado por fórmula):

  * 2022-2025 → `{N}obmep/mapa.htm` (a convenção corrente);
  * 2021      → `16aobmep/mapa.htm` (a ÚNICA edição com o sufixo "a" —
                acidente de nomenclatura do próprio site, achado ao seguir o
                link real de `premiados.htm`, não documentado em lugar nenhum);
  * 2016-2019 → `{ano}/mapa.htm` ou `{ano}/mapa_premiacao_content.htm`
                (convenção anterior, indexada pelo ANO em vez da edição).

2020 não está em `SEGMENTO_POR_ANO` de propósito: não existe OBMEP daquele
ano em lugar nenhum do site (a "Dossiê de Provas" já registrou a ausência na
página-índice) — pedir 2020 é erro de quem chamou, não 404 de rede.

## A tabela de 2016 é de outro molde (docs/41 §8, item 5)

2016 (e presumivelmente anos mais antigos, fora do escopo de 5-7 anos do
docs/41 §2) não tem as âncoras `<a name="nivelN">` que 2017+ usa pra amarrar
cada tabela ao nível, e a linha não tem a coluna de posição na frente — 6
células por linha em vez de 7. `_tabelas_por_nivel` e o corte `celulas[-6:]`
(em vez de `celulas[:7]`) resolvem os dois casos com o MESMO código, lendo o
nível de dentro da própria tabela (o cabeçalho "Nível N" está lá nos dois
formatos) em vez de depender da âncora.

Também não existe lista de rede PRIVADA pra 2016 —
`verRelatorioPremiadosOuro.privada.do.htm` 404 nesse ano; os três valores de
"Tipo" que aparecem na lista pública (F/E/M = federal/estadual/municipal) são
todos rede pública. Tratado como ausência esperada (aviso, não erro fatal) —
ver `_paginas_do_ano`.
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

# ano → (segmento da URL, nome do arquivo-mapa que estabelece o referer/sessão
# antes dos relatórios). Ver o §"Por que é ANO" no docstring do módulo — cada
# linha foi conferida abrindo o site, não calculada por fórmula.
SEGMENTO_POR_ANO: dict[int, tuple[str, str]] = {
    2016: ("2016", "mapa_premiacao_content.htm"),
    2017: ("2017", "mapa_premiacao_content.htm"),
    2018: ("2018", "mapa.htm"),
    2019: ("2019", "mapa.htm"),
    2021: ("16aobmep", "mapa.htm"),
    2022: ("17obmep", "mapa.htm"),
    2023: ("18obmep", "mapa.htm"),
    2024: ("19obmep", "mapa.htm"),
    2025: ("20obmep", "mapa.htm"),
}

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


def raspar_pagina(sessao: requests.Session, url: str, referer: str) -> str:
    resp = sessao.get(url, headers={**HEADERS, "Referer": referer}, timeout=30)
    resp.raise_for_status()
    return resp.text


def _conferir_ano(html: str, ano_esperado: int) -> None:
    """Sanidade barata: quando o título grava um ano de 4 dígitos, ele tem que
    bater com o que `SEGMENTO_POR_ANO` prometeu. Pega erro de mapeamento
    (segmento certo, ano errado no dicionário) sem depender do texto pra
    DECIDIR o ano — só pra CONFERIR."""
    m = re.search(r"OBMEP (\d{4})", html)
    if m and int(m.group(1)) != ano_esperado:
        raise ValueError(
            f"segmento prometia {ano_esperado}, página diz {m.group(1)} — "
            f"confira SEGMENTO_POR_ANO"
        )


def _tabelas_por_nivel(sopa: BeautifulSoup) -> list[tuple[str, Tag]]:
    """[(nível, tabela), ...] pra uma página de relatório.

    Prefere as âncoras `<a name="nivelN">` (2017+, inclusive 16aobmep): cada
    uma aponta pra tabela seguinte, e é o jeito mais direto de amarrar as
    duas. Sem âncora nenhuma (2016), cai pra tabela por tabela na ORDEM da
    página — nível 1, 2, 3 sempre nessa sequência nos dois formatos —, lendo
    o rótulo do próprio cabeçalho da tabela em vez de inventar um.
    """
    ancoras = sopa.find_all("a", attrs={"name": re.compile(r"^nivel\d$")})
    if ancoras:
        saida: list[tuple[str, Tag]] = []
        for ancora in ancoras:
            tabela = ancora.find_next("table", class_="list")
            if tabela is None:
                continue
            rotulo_tag = tabela.find("font", size="+2")
            rotulo = rotulo_tag.get_text(strip=True) if rotulo_tag else ancora["name"]
            saida.append((rotulo, tabela))
        return saida

    saida = []
    for tabela in sopa.find_all("table", class_="list"):
        rotulo_tag = tabela.find("font", size="+2")
        if rotulo_tag is None:
            continue
        saida.append((rotulo_tag.get_text(strip=True), tabela))
    return saida


def parsear_pagina_medalha(html: str, prova_nome: str, ano: int, medalha: str, rede: str, fonte_url: str) -> list[Registro]:
    sopa = BeautifulSoup(html, "lxml")
    registros: list[Registro] = []

    for nivel_texto, tabela in _tabelas_por_nivel(sopa):
        serie_min, serie_max = NIVEL_SERIE.get(nivel_texto, (None, None))

        corpo = tabela.find("tbody")
        if corpo is None:
            continue
        for linha in corpo.find_all("tr"):
            celulas = [c.get_text(strip=True) for c in linha.find_all("td")]
            # 7 células com posição na frente (2017+) ou 6 sem ela (2016) —
            # os últimos 6 campos são sempre [nome, escola, tipo, município,
            # uf, medalha], então pegamos pelo FIM, não pelo início.
            if len(celulas) < 6:
                continue
            nome, escola, _tipo, municipio, uf, medalha_cel = celulas[-6:]
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


def raspar_ano(ano: int) -> list[Registro]:
    segmento, arquivo_mapa = SEGMENTO_POR_ANO[ano]
    sessao = requests.Session()
    mapa_url = f"{BASE}/{segmento}/{arquivo_mapa}"
    raspar_pagina(sessao, mapa_url, mapa_url)  # estabelece o referer real
    time.sleep(0.5)

    registros: list[Registro] = []
    for medalha in MEDALHAS:
        for sufixo, rede in REDES.items():
            url = f"{BASE}/{segmento}/verRelatorioPremiados{medalha}{sufixo}.do.htm"
            try:
                html = raspar_pagina(sessao, url, mapa_url)
            except requests.HTTPError as e:
                # Ausência ESPERADA, não erro: 2016 não publica lista de rede
                # privada pro Ouro/Prata/Bronze (docstring do módulo). Uma
                # falha de qualquer OUTRO tipo (DNS, timeout, 500) continua
                # subindo — só o 404 de uma combinação (medalha, rede)
                # conhecida por faltar é engolido.
                print(f"    sem {medalha}/{rede} em {ano}: {e}", file=sys.stderr)
                continue
            _conferir_ano(html, ano)
            registros.extend(parsear_pagina_medalha(html, "OBMEP", ano, medalha, rede, url))
            time.sleep(0.5)

    return registros


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--anos", type=int, nargs="+", required=True,
        help=f"Anos a raspar, entre {sorted(SEGMENTO_POR_ANO)} (2020 não existe: pandemia)",
    )
    args = parser.parse_args()

    DIR_DADOS.mkdir(exist_ok=True)

    for ano in args.anos:
        if ano not in SEGMENTO_POR_ANO:
            print(f"OBMEP {ano}: sem segmento de URL conhecido (ver SEGMENTO_POR_ANO) — pulando", file=sys.stderr)
            continue

        print(f"OBMEP {ano} — raspando...", file=sys.stderr)
        try:
            registros = raspar_ano(ano)
        except requests.HTTPError as e:
            print(f"  falhou: {e}", file=sys.stderr)
            continue

        if not registros:
            print(f"  0 registros — algo mudou no site, confira antes de importar", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"obmep_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  OBMEP {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
