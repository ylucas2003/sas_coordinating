r"""Raspa a Classificação Inicial (1ª fase) e a Classificação Final
(titulares + reservas) do processo seletivo da EFOMM — CIAGA (Rio de
Janeiro) e CIABA (Belém) — e grava um JSON cru em dados/.

Uso:
    ./.venv/bin/python pipeline/efomm.py

## Sem `--anos`, mesmo motivo do IME (pipeline/ime.py)

Os PDFs de resultado ficam em `assets.marinha.mil.br/ciaga/.../files/...` com
nome **sem o ano** ("CANDIDATOS TITULARES - convocados para o CIAGA_0.pdf") —
o mesmo caminho é sobrescrito a cada ciclo novo, não existe arquivo por ano
pra voltar atrás. `ano` vem de dentro do PDF ("PROCESSO SELETIVO EFOMM AAAA"
no cabeçalho), nunca de argumento de linha de comando. Pesquisado em
16-17/09/2026 (docs/41 §10): não há snapshot nenhum no Wayback Machine pra
esse caminho, então isto é retrato do ciclo CORRENTE — cobertura histórica
2016-2025 não é recuperável com confiança por este scraper; ele cresce ano a
ano a partir de quando passou a rodar.

## Dois hosts com comportamento diferente — use SEMPRE `assets.`

`www.marinha.mil.br/ciaga/*` (páginas institucionais Drupal) está atrás de
Cloudflare managed challenge (403 pra requisição simples). Os PDFs de
resultado, hospedados no espelho de assets estático
(`assets.marinha.mil.br/ciaga/sites/www.marinha.mil.br.ciaga/files/...`),
**não** passam por esse desafio — servidor estático plano, sem bloqueio. As
URLs abaixo usam sempre `assets.`, nunca `www.`, de propósito.

## Reservas: CIAGA tem lista única, CIABA não (achado, não lacuna preguiçosa)

CIAGA publica "Candidatos na condição de RESERVAS" como documento único e
estável, igual titulares. CIABA não — a convocação de reserva de lá sai como
boletins numerados incrementais ("10 CONVOCAÇÃO DOS RESERVAS-CIABA.pdf", que
vira "11...", "12..." a cada substituição de titular), sem nome de arquivo
fixo pra apontar. Por isso a reserva da CIABA fica de fora por enquanto —
puxar cada boletim exigiria descobrir o número mais recente a cada rodada,
sem padrão de URL estável (mesma régua de "não dá pra confiar" do IME/AFA).

## Nome pode quebrar em 3 linhas no `pdftotext -layout` — nome muito comprido

Um nome com 6+ palavras não cabe na largura da coluna e o extrator devolve a
PRIMEIRA parte na linha ACIMA da linha de dado, e a ÚLTIMA palavra (o
sobrenome final) na linha ABAIXO — a linha de dado em si fica com um "buraco"
onde o nome deveria estar (só rank + inscrição + notas + cidade + data).
`_consertar_nomes_quebrados` funde as três linhas de volta antes do parser
principal rodar. Confirmado contra os 2.364 registros reais de 17/09/2026:
sem o conserto, 6 de 800 na Classificação Inicial do CIAGA saem sem nome.

## Ordem de Nome/Inscrição muda entre fase 1 e fase 4 — mesmo problema da OBM

Fase 1: `Clas. | Insc. | Nome | ... | Dt_Nasc`. Fase 4 (titulares/reservas):
`Clas. | Nome | Insc. | ... | Data_Nasc` — **nome e inscrição trocam de
lugar**. `_PADRAO_LINHA` não fixa a ordem: captura o trecho inteiro entre o
rank e o bloco de notas como `meio`, acha a inscrição por regex DENTRO dele
(`\d{5,6}-\d`, formato que nunca aparece no nome) e trata o resto de `meio`
como nome — funciona nas duas ordens sem precisar saber qual é qual.

## Sem escola — cidade é onde fez a prova (ODE), não onde mora

Mesma ressalva de ITA/IME: o candidato faz prova na banca mais perto, não na
própria cidade. `_UF_DA_CIDADE` traduz os 19 nomes de cidade-sede vistos nos
5 PDFs reais de 17/09/2026 pra UF — não é lista genérica de capital, é
conferida contra todo valor de ODE observado (inclui Corumbá/MS, Paranaguá/PR,
Parnaíba/PI e Santarém/PA, que não são capital).

## `assets.marinha.mil.br` também não manda a cadeia intermediária

Mesmo achado do IME (`inscricoes.ime.eb.br`, ver pipeline/ime.py): `curl`
valida normal (completa a cadeia com o que já tem por perto), o verificador
de certificado do Python não (`unable to get local issuer certificate`). Não
é downgrade de segurança escolhido à toa — é o único jeito de falar com este
servidor específico —, e o aviso correspondente é silenciado de propósito.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://assets.marinha.mil.br/ciaga/sites/www.marinha.mil.br.ciaga/files"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# (casco, fase, arquivo, resultado-base) — resultado final é ajustado por
# seção (Classificado/Pós-classificado) só na fase 1; nas outras já é fixo.
_DOCUMENTOS: list[tuple[str, str, str]] = [
    ("CIAGA", "Processos Seletivos/CANDIDATOS CLASSIFICADOS E PÓS-CLASSIFCADOS_CIAGA_0.pdf", "fase1"),
    ("CIABA", "Processos Seletivos/CANDIDATOS CLASSIFICADOS E PÓS-CLASSIFICADOS_CIABA.pdf", "fase1"),
    ("CIAGA", "Processo Seletivo/Candidatos TITULARES - convocados para o CIAGA_0.pdf", "titular"),
    ("CIABA", "Processo Seletivo/Candidatos TITULARES - convocados para o CIABA_0.pdf", "titular"),
    ("CIAGA", "Processo Seletivo/Candidatos na condição de RESERVAS - CIAGA - Retificada_0.pdf", "reserva"),
]

_UF_DA_CIDADE: dict[str, str] = {
    "AMAPA": "AP",
    "BELEM": "PA",
    "BELO HORIZONTE": "MG",
    "BRASILIA": "DF",
    "CORUMBA": "MS",
    "FLORIANOPOLIS": "SC",
    "FORTALEZA": "CE",
    "MANAUS": "AM",
    "NATAL": "RN",
    "PARANAGUA": "PR",
    "PARNAIBA": "PI",
    "PORTO ALEGRE": "RS",
    "RECIFE": "PE",
    "RIO DE JANEIRO": "RJ",
    "SALVADOR": "BA",
    "SANTAREM": "PA",
    "SAO LUIS": "MA",
    "SAO PAULO": "SP",
    "VITORIA": "ES",
}

# rank, [nome ou inscrição, em ordem que muda entre fases — ver docstring],
# bloco de 4 a 7 notas (scores + total), cidade, data de nascimento.
#
# `prefixo`/`sufixo` cobrem o nome comprido demais pra coluna (docstring do
# módulo): o PyMuPDF (`sort=True`) não quebra em 3 linhas como o
# `pdftotext -layout` fez na inspeção manual — ele intercala tudo numa linha
# SÓ, com o início do nome ANTES do rank e o sobrenome final DEPOIS da data
# ("MIGUEL CLAUDIO FERRO DE SÁ FERREIRA 90    102823-2 ... 30/10/2006
# VASCONCELOS"). Os dois grupos são opcionais e vazios em toda linha normal.
_PADRAO_LINHA = re.compile(
    r"^\s*(?P<prefixo>[A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ '\-]*?)?"
    r"\s*(?P<rank>\d+)\s*(?P<meio>.+?)\s+"
    r"(?:\d{1,3}\s+){3,6}\d{1,3}\s+"
    r"(?P<cidade>[A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ '\-]*?)\s+"
    r"(?P<data>\d{2}/\d{2}/\d{4})"
    r"\s*(?P<sufixo>[A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ'\-]*)?\s*$",
    re.MULTILINE,
)
_INSCRICAO = re.compile(r"\d{5,6}-\d")
_PADRAO_ANO = re.compile(r"EFOMM (\d{4})")
# Âncora ESPECÍFICA do título da seção "b)", não da palavra solta —
# "PÓS-CLASSIFICADOS" sozinha aparece primeiro no parágrafo de abertura do
# PDF (antes de qualquer linha de dado), e usar só ela marcava TODO CANDIDATO
# como pós-classificado (achado rodando de verdade, 17/09/2026: 800/800 saíam
# pós quando deviam ser 59 classificados + 741 pós).
_MARCA_POS_CLASSIFICADO = re.compile(r"Rela[çc][ãa]o dos candidatos P[ÓO]S", re.IGNORECASE)


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


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


def parsear_pdf(conteudo: bytes, casco: str, fase: str, fonte_url: str) -> tuple[int, list[Registro]]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    # `sort=True` aproxima a ordem visual (coluna por coluna) — sem isso a
    # extração vem token a token, uma linha por número/palavra, impossível
    # de casar por regex de linha inteira.
    texto = "\n".join(pagina.get_text("text", sort=True) for pagina in doc)

    m_ano = _PADRAO_ANO.search(texto)
    if not m_ano:
        raise ValueError(f"não achei 'EFOMM AAAA' no cabeçalho de {fonte_url} — layout mudou?")
    ano = int(m_ano.group(1))

    pos_marca = _MARCA_POS_CLASSIFICADO.search(texto)
    pos_classificado_a_partir_de = pos_marca.start() if pos_marca else None

    registros: list[Registro] = []
    for m in _PADRAO_LINHA.finditer(texto):
        meio = f"{m.group('prefixo') or ''} {m.group('meio')} {m.group('sufixo') or ''}"
        insc_m = _INSCRICAO.search(meio)
        if not insc_m:
            continue
        nome = (meio[: insc_m.start()] + meio[insc_m.end() :]).strip()
        nome = re.sub(r"\s+", " ", nome)
        if not nome or len(nome.split()) < 2:
            print(f"  aviso: linha sem nome reconhecível, pulando: {meio!r}", file=sys.stderr)
            continue

        cidade = m.group("cidade").strip()
        uf = _UF_DA_CIDADE.get(_sem_acento(cidade).upper(), "")
        if not uf:
            print(f"  aviso: cidade-sede desconhecida {cidade!r} — sem UF", file=sys.stderr)

        if fase == "fase1":
            eh_pos = pos_classificado_a_partir_de is not None and m.start() > pos_classificado_a_partir_de
            resultado = f"{casco} — Pós-classificado (1ª fase)" if eh_pos else f"{casco} — Classificado (1ª fase)"
        elif fase == "titular":
            resultado = f"{casco} — Titular (classificação final)"
        else:
            resultado = f"{casco} — Reserva (classificação final)"

        registros.append(
            Registro(
                prova_nome="EFOMM",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                resultado=resultado,
                nome_informado=nome,
                escola_informada="",
                cidade_informada=cidade.title(),
                uf_informada=uf,
                fonte_url=fonte_url,
            )
        )
    return ano, registros


def raspar() -> tuple[int, list[Registro]]:
    todos: list[Registro] = []
    ano_visto: int | None = None
    for casco, caminho, fase in _DOCUMENTOS:
        url = f"{BASE}/{requests.utils.quote(caminho)}"
        resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        resp.raise_for_status()
        ano, registros = parsear_pdf(resp.content, casco, fase, url)
        if ano_visto is not None and ano != ano_visto:
            raise ValueError(f"documentos de anos diferentes no mesmo ciclo: {ano_visto} vs {ano} ({url})")
        ano_visto = ano
        todos.extend(registros)
        print(f"  {casco} {fase}: {len(registros)} registros ({ano})", file=sys.stderr)

    assert ano_visto is not None
    return ano_visto, todos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()  # sem argumentos — só documenta --help (ver docstring do módulo)

    DIR_DADOS.mkdir(exist_ok=True)
    print("EFOMM — raspando CIAGA e CIABA...", file=sys.stderr)
    try:
        ano, registros = raspar()
    except requests.HTTPError as e:
        print(f"  falhou: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    if not registros:
        print("  0 registros — algo mudou no site, confira antes de importar", file=sys.stderr)
        raise SystemExit(1)

    destino = DIR_DADOS / f"efomm_{ano}.json"
    destino.write_text(
        json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  EFOMM {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
