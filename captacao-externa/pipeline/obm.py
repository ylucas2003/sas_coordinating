"""Raspa os premiados NACIONAIS da OBM (Olimpíada Brasileira de Matemática —
SBM, não confundir com a OBMEP do IMPA) e grava um JSON cru por ano em
dados/.

Uso:
    ./.venv/bin/python pipeline/obm.py --anos 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025

Cada ano vira dados/obm_{ano}.json, no mesmo formato que
api/scripts/importar_captacao_externa.py espera (ver pipeline/obmep.py pro
contrato completo dos campos).

## Uma página por ano, sem o problema de volume da OBMEP

`obm.org.br/premiados-obm-{ano}/` é uma URL por ano, 1979-2025, sem os
esconderijos que a OBMEP tinha (docs/41 §5) — nem 2020 falta aqui. Uma
requisição por ano, ~300 linhas cada (Ouro/Prata/Bronze/Menção Honrosa dos
Níveis 1-3 somados) — nada perto do volume que fez a OBMEP excluir Menção
Honrosa de propósito (docs/41 §5: 162 requisições por edição só pra ela). Na
OBM ela já vem de graça na mesma página, então ENTRA — mais sinal, custo zero.

`Nível Universitário` é ignorado: quem já está na faculdade não é lead de
ITA/IME.

## ⚠️ A OBM não publica ESCOLA (achado real, não suposição do docs/41)

O §1 do docs/41 assumia que "olimpíada científica quase sempre publica
[escola] junto do nome" — vale pra OBMEP, não pra OBM: a tabela só tem Nome,
Cidade–Estado, Pontos e Prêmio. Sem escola, a chave de match do resolver
(nome + escola exatos, `scripts/resolver_candidatos_externos.py`) não tem o
que comparar — e o próprio resolver já trata isso: **toda linha com
`escola_informada` vazia vira candidato_externo PRÓPRIO, nunca se funde com
outra** (`chave_do_grupo`, o ramo `if not escola`). Efeito prático: um aluno
que ganhou OBMEP E OBM entra como DOIS `candidato_externo` diferentes — a OBM
não enriquece o cruzamento da OBMEP automaticamente. Anexar por nome (+
cidade/UF como confiança extra) a um candidato que a OBMEP já resolveu é a
"variação do resolver ainda não escrita" que o docs/41 §6 já apontava pra
vestibular; a OBM cai na mesma categoria.

`escola_informada` sai como `""` (nunca `None`) de propósito: o índice único
da 0057 trata NULL como sempre-diferente-de-NULL (SQL padrão), e duas raspagens
do mesmo ano duplicariam a linha inteira em vez de fazer upsert. String vazia
participa do índice normalmente — idempotência preservada, e o resolver já lê
`""` e `None` como a mesma coisa (`(x or "").strip()`).

## Colunas fora de ordem, e uma delas com erro de digitação

O HTML não tem classe nem id — só `<table>` cru, um por nível, cada um
precedido por um `<p><strong>Nível N...</strong></p>` que diz a que nível a
tabela seguinte pertence (não dá pra contar "a Nª tabela da página", a ORDEM
das colunas Nome/Cidade–Estado/Pontos/Prêmio muda de ano pra ano — 2016 tem
Pontos antes de Cidade, por exemplo. `_indice_das_colunas` lê o cabeçalho de
CADA tabela e resolve pelo nome da coluna, nunca por posição fixa.

E MEIO YEAR (2018, nível 3) grafou "Fortaleza – cE" — UF minúscula. O regex
de corte é case-insensitive e o grupo capturado sempre vira `.upper()`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

BASE = "https://www.obm.org.br"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

# Mesma definição pública da OBMEP (docs/41, pipeline/obmep.py) — as duas
# olimpíadas de matemática usam a MESMA divisão oficial de nível por série.
NIVEL_SERIE = {
    "Nível 1": (6, 7),
    "Nível 2": (8, 9),
    "Nível 3": (10, 12),
}

# "Cidade – Estado", "Cidade —Estado", "Cidade-Estado"... o traço varia; a UF
# é sempre as duas letras finais, e vira maiúscula mesmo quando a fonte errou
# (2018, nível 3: "Fortaleza – cE").
_PADRAO_CIDADE_UF = re.compile(r"^(?P<cidade>.+?)\s*[-–—]\s*(?P<uf>[A-Za-zÀ-ú]{2})$")

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


def _normalizar_cabecalho(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def _indice_das_colunas(linha_cabecalho: list[str]) -> dict[str, int]:
    """{'nome': i, 'cidade': i, 'premio': i} — por NOME da coluna, nunca por
    posição: a ordem muda de ano pra ano (docstring do módulo)."""
    indice: dict[str, int] = {}
    for i, celula in enumerate(linha_cabecalho):
        normal = _normalizar_cabecalho(celula)
        if "nome" in normal:
            indice["nome"] = i
        elif "cidade" in normal:
            indice["cidade"] = i
        elif "premio" in normal:
            indice["premio"] = i
    faltando = {"nome", "cidade", "premio"} - indice.keys()
    if faltando:
        raise ValueError(f"cabeçalho sem coluna(s) {faltando}: {linha_cabecalho}")
    return indice


def _nivel_da_tabela(tabela: Tag) -> str | None:
    """Lê o `<p>`/`<strong>` mais próximo ANTES da tabela. `None` pra
    'Nível Universitário' (fora do escopo — não é lead de ensino médio)."""
    rotulo = tabela.find_previous(["p", "strong", "h1", "h2", "h3", "h4"])
    if rotulo is None:
        return None
    texto = rotulo.get_text(strip=True)
    m = re.match(r"Nível\s*(\d)", texto)
    return f"Nível {m.group(1)}" if m else None


def parsear_pagina_do_ano(html: str, ano: int, fonte_url: str) -> list[Registro]:
    sopa = BeautifulSoup(html, "lxml")
    registros: list[Registro] = []

    for tabela in sopa.find_all("table"):
        nivel_texto = _nivel_da_tabela(tabela)
        if nivel_texto is None:
            continue  # Nível Universitário, ou tabela que não é de premiados
        serie_min, serie_max = NIVEL_SERIE[nivel_texto]

        linhas = tabela.find_all("tr")
        if not linhas:
            continue
        cabecalho = [c.get_text(strip=True) for c in linhas[0].find_all("td")]
        try:
            idx = _indice_das_colunas(cabecalho)
        except ValueError as exc:
            print(f"  aviso: {exc} — pulando esta tabela", file=sys.stderr)
            continue

        for linha in linhas[1:]:
            celulas = [c.get_text(strip=True) for c in linha.find_all("td")]
            if len(celulas) <= max(idx.values()):
                continue
            nome = celulas[idx["nome"]]
            if not nome:
                continue
            cidade_uf = celulas[idx["cidade"]]
            m = _PADRAO_CIDADE_UF.match(cidade_uf)
            cidade, uf = (m.group("cidade"), m.group("uf").upper()) if m else (cidade_uf, "")

            registros.append(
                Registro(
                    prova_nome="OBM",
                    ano=ano,
                    nivel_texto=nivel_texto,
                    serie_referencia_min=serie_min,
                    serie_referencia_max=serie_max,
                    resultado=celulas[idx["premio"]],
                    nome_informado=nome,
                    escola_informada="",  # a OBM não publica escola — ver docstring do módulo
                    cidade_informada=cidade,
                    uf_informada=uf,
                    fonte_url=fonte_url,
                )
            )
    return registros


def raspar_ano(ano: int) -> list[Registro]:
    url = f"{BASE}/premiados-obm-{ano}/"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return parsear_pagina_do_ano(resp.text, ano, url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--anos", type=int, nargs="+", required=True, help="Anos a raspar (a OBM cobre 1979-2025)")
    args = parser.parse_args()

    DIR_DADOS.mkdir(exist_ok=True)

    for ano in args.anos:
        print(f"OBM {ano} — raspando...", file=sys.stderr)
        try:
            registros = raspar_ano(ano)
        except requests.HTTPError as e:
            print(f"  falhou: {e}", file=sys.stderr)
            continue

        if not registros:
            print("  0 registros — algo mudou no site, confira antes de importar", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"obm_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  OBM {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
