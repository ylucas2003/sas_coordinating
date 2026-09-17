r"""Raspa o CPAEN (Concurso Público de Admissão à Escola Naval) e grava um
JSON cru por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/escola_naval.py
    ./.venv/bin/python pipeline/escola_naval.py --anos 2023 2024 2025

## `id_file` curado à mão, não descoberto por padrão de URL

Os PDFs ficam em `www.inscricao.marinha.mil.br/marinha/<nome-livre>.pdf?
id_file=<N>` — o nome do arquivo na URL é cosmético, só o `id_file` importa.
Esse número é um contador SEQUENCIAL GLOBAL, compartilhado por TODO concurso
da Marinha (CPAEN, CPACN/Colégio Naval, CPAEAM, QC...), e a página
institucional que LISTA os arquivos por ano/concurso está atrás de
Cloudflare managed challenge — não dá pra descobrir o `id_file` certo
navegando o site. `_DOCUMENTOS` é o resultado de pesquisa dirigida (busca +
confirmação baixando e lendo o PDF, nunca confiando só no nome do arquivo —
dois candidatos que pareciam CPAEN eram na verdade CP-CEM e CP-PMS, outros
concursos da mesma casa), pesquisada em 17/09/2026: 7 de 11 anos entre 2016 e
2025 (faltam 2015, 2017, 2019 — não achados; 2020 existe mas é só uma
retificação de EDITAL, sem nome de candidato nenhum, por isso fora da lista).

Cobertura desigual de propósito, não preguiça: cada ano trouxe o documento
de MAIOR classificação disponível achado na pesquisa — Resultado Final
(titular+reserva, o mais valioso) pra 2016/2018/2021/2023/2025, e "não
eliminados nas provas escritas" (a única fase com nome publicado naqueles
ciclos) pra 2022/2024. Não é o padrão "todas as fases, todo ano" dos outros
vestibulares militares (§2 do docs/41) porque a fonte não permite escolher —
é o que a busca conseguiu confirmar contra o PDF de verdade, sem inventar.

## Duas gerações de layout, mesma âncora funciona nas duas

2016-2018 trazem Classificação (`Clas.`) e Média das Provas (`ME`) junto do
nome; 2021/2023/2025 (Resultado Final) só trazem inscrição+nome+OREL;
2022/2024 trazem 2 a 6 colunas de nota. `_PADRAO_LINHA` não tenta casar essas
colunas: âncora na INSCRIÇÃO (`\d{5,6}-\d`, sempre no início da linha) e no
código de OREL (sempre o ÚLTIMO token da linha, nunca puramente numérico —
mesmo quando tem dígito, tipo "Com8ºDN"), e trata tudo no meio como "nome
seguido de zero ou mais números" — o `.+?` (nome, preguiçoso) só para de
crescer no ponto em que o resto da linha vira só números e o código final.

## OREL não é cidade do candidato, e a maioria nem é lugar nenhum

Diferente de ITA/IME (`BANCA`) e EFOMM (`ODE`), que são sempre nome de
cidade, o "OREL" (Organização Responsável pela Execução Local) da Marinha é
uma unidade ADMINISTRATIVA — `SSPM`/`DEnsM` é o próprio órgão central no Rio,
não um lugar; `Com7ºDN` é comando de Distrito Naval, que cobre VÁRIOS
estados; só uma fração (`EAMCE`, `EAMPE`, `EAMSC`...) tem nome de estado
embutido, e olhando errado dava pra inventar uma UF pra `CFPA`/`CPMA`/`CN`/
`SNNF` que eu não tenho como confirmar. Por isso, ao contrário de TODAS as
fontes anteriores, `cidade_informada`/`uf_informada` saem SEMPRE vazias
aqui — inventar sinal geográfico fraco é pior que não ter nenhum (mesmo
princípio do `serie_referencia_min/max` da ITA saindo `None`).

## Sem escola — mesma fila de revisão por nome de sempre

Nenhum dos 7 documentos publica escola. Cai na fila de enriquecimento por
nome (docs/41 §9), como OBM/ITA/IME/EFOMM.

## Mesmo certificado incompleto do IME e da EFOMM

`www.inscricao.marinha.mil.br` também não manda a cadeia intermediária —
`curl` completa com o que já tem por perto, o verificador do Python não
(`unable to get local issuer certificate`). `verify=False` de propósito,
mesma justificativa de `pipeline/ime.py` e `pipeline/efomm.py`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://www.inscricao.marinha.mil.br/marinha"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# ano -> (id_file, descrição da fase, tem_secao_titular_reserva) — pesquisa
# dirigida de 17/09/2026 (docstring do módulo). `tem_secao_titular_reserva`
# distingue os dois formatos: Resultado Final separa titular/reserva em
# seções; "não eliminados" é uma lista só, sem essa distinção.
_DOCUMENTOS: dict[int, tuple[int, str, bool]] = {
    2016: (3354, "Resultado Final", True),
    2018: (4296, "Resultado da Seleção Inicial", True),
    2021: (6360, "Resultado Final da Seleção", True),
    2022: (7000, "Não eliminado nas provas escritas (seleção inicial)", False),
    2023: (7883, "Resultado Final", True),
    2024: (8335, "Não eliminado nas provas escritas (seleção inicial)", False),
    2025: (9220, "Resultado Final da Seleção", True),
}

# Inscrição sempre no início (âncora inequívoca — nunca aparece em nome), zero
# ou mais colunas de nota (dígito e vírgula, formato brasileiro "84,58"), e o
# código de OREL como ÚLTIMO token da linha (docstring do módulo).
_PADRAO_LINHA = re.compile(
    r"^\s*(?P<insc>\d{5,6}-\d)\s+(?P<nome>.+?)\s+(?:[\d,]+\s+)*(?P<orel>\S+)\s*$",
    re.MULTILINE,
)
# ⚠️ Achado rodando de verdade: o parágrafo de ABERTURA de todo PDF já diz
# "relação dos candidatos titulares e dos candidatos reservas" — se o
# marcador de seção não distinguir isso de um cabeçalho de verdade, ele vira
# a ÚLTIMA marca vista antes de QUALQUER linha de dado, e o documento inteiro
# sai "Reserva" (foi o que aconteceu com 2023 e 2025: 100/100 e 68/68).
# Cabeçalho de verdade só existe DEPOIS de "Aspirante Masculino/Feminino" —
# `_MARCA_INICIO_LISTAGEM` corta a abertura fora da busca.
_MARCA_INICIO_LISTAGEM = re.compile(r"aspirante\s+(masculino|feminino)", re.IGNORECASE)
_MARCA_SECAO = re.compile(r"\b(titulares|reservas)\b", re.IGNORECASE)


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


def _resultado_da_posicao(texto: str, inicio_real: int, posicao: int, fase: str, tem_secoes: bool) -> str:
    """Titular ou reserva, pela seção mais próxima ANTES da posição da linha,
    nunca buscando antes de `inicio_real` (docstring de `_MARCA_INICIO_LISTAGEM`)
    — e nunca um único corte fixo no meio do documento, porque masculino e
    feminino repetem titular→reserva cada um."""
    if not tem_secoes:
        return fase
    ultima = None
    for m in _MARCA_SECAO.finditer(texto, inicio_real, posicao):
        ultima = m.group(1).lower()
    if ultima is None:
        return fase
    return f"{fase} — {'Titular' if ultima == 'titulares' else 'Reserva'}"


def parsear_pdf(conteudo: bytes, ano: int, fase: str, tem_secoes: bool, fonte_url: str) -> list[Registro]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    texto = "\n".join(pagina.get_text("text", sort=True) for pagina in doc)

    m_inicio = _MARCA_INICIO_LISTAGEM.search(texto)
    inicio_real = m_inicio.start() if m_inicio else 0

    registros: list[Registro] = []
    for m in _PADRAO_LINHA.finditer(texto):
        nome = re.sub(r"\s+", " ", m.group("nome")).strip()
        if not nome or len(nome.split()) < 2:
            print(f"  aviso: linha sem nome reconhecível, pulando: {m.group(0)!r}", file=sys.stderr)
            continue

        registros.append(
            Registro(
                prova_nome="Escola Naval (CPAEN)",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                resultado=_resultado_da_posicao(texto, inicio_real, m.start(), fase, tem_secoes),
                nome_informado=nome,
                escola_informada="",
                # Nunca uma cidade: OREL é unidade administrativa, não local
                # de moradia — ver docstring do módulo ("OREL não é cidade").
                cidade_informada="",
                uf_informada="",
                fonte_url=fonte_url,
            )
        )
    return registros


def raspar_ano(ano: int) -> list[Registro]:
    id_file, fase, tem_secoes = _DOCUMENTOS[ano]
    url = f"{BASE}/x.pdf?id_file={id_file}"
    resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)
    resp.raise_for_status()
    return parsear_pdf(resp.content, ano, fase, tem_secoes, url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--anos",
        type=int,
        nargs="+",
        default=sorted(_DOCUMENTOS),
        help=f"Anos a raspar — só os curados em _DOCUMENTOS: {sorted(_DOCUMENTOS)}",
    )
    args = parser.parse_args()

    DIR_DADOS.mkdir(exist_ok=True)

    for ano in args.anos:
        if ano not in _DOCUMENTOS:
            print(f"  {ano}: sem id_file curado, pulando (ver _DOCUMENTOS)", file=sys.stderr)
            continue

        print(f"Escola Naval (CPAEN) {ano} — raspando...", file=sys.stderr)
        try:
            registros = raspar_ano(ano)
        except requests.HTTPError as e:
            print(f"  falhou: {e}", file=sys.stderr)
            continue

        if not registros:
            print("  0 registros — algo mudou no site, confira antes de importar", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"escola_naval_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  Escola Naval {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
