"""Raspa os premiados da OBF (Olimpíada Brasileira de Física — SBF, não
confundir com a OBFEP, prova irmã só de escola pública) e grava um JSON cru
por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/obf.py --anos 2023 2024 2025

Olimpíada: aqui vale o recorte por medalha (docs/41, feedback registrado
16/09/2026 — "vestibular/concurso captura todos os classificados nomeados,
olimpíada fica só na medalha"), não o "todos os alunos" que a ITA passou a
fazer. E como Ouro/Prata/Bronze/Menção Honrosa já vêm TODOS na MESMA página
por série (nada parecido com o custo de UF-por-UF que a OBMEP tem pra Menção
Honrosa — docs/41 §5), Menção Honrosa entra de graça, mesmo raciocínio que
já valeu pra OBM (pipeline/obm.py).

## Cada ano tem 7 páginas — uma por série —, e o ID delas MUDA

Cada série (6º ao 9º ano, 1ª à 3ª série do médio) tem página própria, tipo
`.../index.php/382-premiados-obf-2025-da-3-serie`. O "382" é um ID de
página do Joomla que **muda a cada publicação** — o Dossiê de Provas já
tinha registrado isso ("sem URL fixa reutilizável entre anos"). Por isso
`_achar_paginas_do_ano` não crava número nenhum: usa a BUSCA interna do
próprio site (`component/search/?searchword=premiados-obf-{ano}`), que
devolve os 7 links com o ID certo pra aquele ano — descoberto rodando de
verdade, não documentado em lugar nenhum do site.

⚠️ **O resultado de um ano pode estar hospedado no site do ano SEGUINTE.**
A OBF publica resultado final em fev/mar do ano seguinte (Dossiê de
Provas), e a busca confirma: as 7 páginas de 2023 existem tanto em
`/olimpiada/2023/` quanto em `/olimpiada/2024/` (mesmo ID nos dois — é a
mesma instalação por trás, só o prefixo de URL muda). Por isso a busca tenta
o site do PRÓPRIO ano primeiro e o do ano seguinte depois, e junta o que
achar nos dois (sem duplicar: mesmo ID vira a mesma URL final).

## Confirmado só 2023-2025

A busca não achou nada pra 2019/2021/2022 (o Dossiê de Provas confirmou
esses anos abrindo página por página no navegador — a busca interna do site
não os indexa, ou o índice daquela instalação antiga está fora do ar; as
categorias devolveram 403/404 nas tentativas automatizadas). Lacuna
registrada, não investigada a fundo — mesmo padrão da OBMEP antes de virar
`SEGMENTO_POR_ANO` (pipeline/obmep.py): não vale a pena descobrir na unha
antes de alguém pedir esses anos especificamente.

## Escola E Uf — melhor qualidade de match que OBM/ITA/IME

Ao contrário da OBM (pipeline/obm.py), a OBF publica ESCOLA — mesma
qualidade da OBMEP, e o resolver (nome+escola exatos) cruza de verdade em
vez de virar candidato avulso. Não tem cidade, só UF (a coluna do relatório
é só "UF"): `cidade_informada` sai `""`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DOMINIO = "https://www1.fisica.org.br"
BASE = f"{DOMINIO}/olimpiada"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# "premiados-obf-2025-da-3-serie" / "...-do-9-ano" / formas sem "da-"/"do-"
# vistas em anos diferentes — todas com o mesmo par (número, ano|série).
_PADRAO_SERIE = re.compile(r"premiados-obf-(\d{4})-(?:d[ao]-)?(\d)-(ano|serie)")

_PALAVRAS_RESULTADO = ("MEDALHA", "MENÇÃO", "MENCAO", "HONROSA")


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


def _rotulo_da_serie(numero: str, tipo: str) -> tuple[str, int]:
    """('6º ano', 6) ou ('3ª série', 12) — a série do médio conta a partir do
    9 (1ª série = 10º ano equivalente), pra ficar na mesma escala 6-12 que
    OBMEP/OBM já usam em `serie_referencia_min/max`."""
    n = int(numero)
    if tipo == "ano":
        return f"{n}º ano", n
    return f"{n}ª série", n + 9


def _achar_paginas_do_ano(sessao: requests.Session, ano: int) -> dict[str, str]:
    """{'6-ano': url, ..., '3-serie': url} pra um ano — via busca interna do
    site, porque o ID da página muda a cada publicação (docstring do
    módulo). Tenta o site do próprio ano e o do ano seguinte (resultado
    sai fev/mar do ano seguinte) e junta o que achar nos dois.
    """
    paginas: dict[str, str] = {}
    for site_ano in (ano, ano + 1):
        url_busca = f"{BASE}/{site_ano}/index.php/component/search/"
        try:
            # "premiados", palavra solta — o buscador do Joomla indexa
            # palavra, não slug inteiro; "premiados-obf-2025" como termo de
            # busca não bate com nada (achado rodando: dava 0 resultado
            # sempre, pra qualquer ano). O ANO é filtrado depois, no regex
            # sobre os links devolvidos, não na própria busca.
            resp = sessao.get(
                url_busca,
                params={"searchword": "premiados", "searchphrase": "all"},
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.HTTPError:
            continue
        for m in re.finditer(r'href="([^"]*premiados-obf-\d{4}-[^"]*)"', resp.text):
            href = m.group(1).replace("&amp;", "&")
            m_serie = _PADRAO_SERIE.search(href)
            if not m_serie or int(m_serie.group(1)) != ano:
                continue
            chave = f"{m_serie.group(2)}-{m_serie.group(3)}"
            if chave in paginas:
                continue
            # `href` já vem com o caminho inteiro ("/olimpiada/2023/index.php/...")
            # quando é relativo — urljoin resolve os dois casos sem duplicar
            # o prefixo, o que um f-string concatenando à mão fazia.
            paginas[chave] = urljoin(f"{DOMINIO}/", href)
    return paginas


def parsear_pagina_da_serie(html_texto: str, ano: int, nivel_texto: str, serie: int, fonte_url: str) -> list[Registro]:
    sopa = BeautifulSoup(html_texto, "lxml")
    registros: list[Registro] = []

    for tr in sopa.find_all("tr"):
        celulas = tr.find_all("td")
        if len(celulas) != 4:
            continue
        nome, escola, uf, resultado = (c.get_text(strip=True) for c in celulas)
        # A forma da linha É o filtro: UF de 2 letras maiúsculas + resultado
        # que cita medalha/menção. Sem cabeçalho fixo pra comparar (a página
        # não tem `<th>` nem rótulo "Nome"/"Escola"), então casar pelo
        # FORMATO da linha é mais robusto que contar posição de tabela.
        if len(uf) != 2 or not uf.isupper() or not any(p in resultado.upper() for p in _PALAVRAS_RESULTADO):
            continue
        if not nome:
            continue

        registros.append(
            Registro(
                prova_nome="OBF",
                ano=ano,
                nivel_texto=nivel_texto,
                serie_referencia_min=serie,
                serie_referencia_max=serie,
                resultado=resultado,
                nome_informado=nome,
                escola_informada=escola,
                cidade_informada="",
                uf_informada=uf,
                fonte_url=fonte_url,
            )
        )
    return registros


def raspar_ano(ano: int) -> list[Registro]:
    sessao = requests.Session()
    paginas = _achar_paginas_do_ano(sessao, ano)
    if not paginas:
        print(f"  nenhuma página achada pra {ano} (busca interna não indexou — ver docstring)", file=sys.stderr)
        return []

    registros: list[Registro] = []
    for chave, url in sorted(paginas.items()):
        numero, tipo = chave.split("-")
        nivel_texto, serie = _rotulo_da_serie(numero, tipo)
        resp = sessao.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        da_pagina = parsear_pagina_da_serie(resp.text, ano, nivel_texto, serie, url)
        registros.extend(da_pagina)
        print(f"    {nivel_texto}: {len(da_pagina)} premiados", file=sys.stderr)

    if len(paginas) < 7:
        print(f"  aviso: só achei {len(paginas)}/7 séries pra {ano}", file=sys.stderr)
    return registros


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--anos", type=int, nargs="+", required=True, help="Anos a raspar — só 2023-2025 confirmados (ver docstring)")
    args = parser.parse_args()

    DIR_DADOS.mkdir(exist_ok=True)

    for ano in args.anos:
        print(f"OBF {ano} — raspando...", file=sys.stderr)
        registros = raspar_ano(ano)

        if not registros:
            print(f"  0 registros pra {ano} — pulando", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"obf_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  OBF {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
