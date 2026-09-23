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

## Nota de 2021/2023/2025 por CRUZAMENTO com um segundo documento

Pedido do usuário depois de olhar que só 2016/2018/2022/2024 tinham nota
(22/09/2026): pesquisa dirigida achou que a própria fonte oficial também
publica, à parte do Resultado Final (que só tem inscrição+nome+OREL, sem
nota), o resultado da fase de PROVAS OBJETIVAS — que TEM nota — pra esses
três anos. Mesma técnica do IME (docs/41 §11.3.1): junta as duas listas por
Nº DE INSCRIÇÃO, nunca por nome (grafia pode variar entre os dois PDFs).
Confirmado rodando de verdade: as inscrições do Resultado Final aparecem
100% na lista de Provas Objetivas nos três anos.

O formato da linha da Prova Objetiva é o MESMO já coberto por
`_PADRAO_LINHA`/`_DOCUMENTOS` — é só mais um documento com `rotulos_notas`
próprio, então vira só uma entrada de enriquecimento em `_DOCUMENTOS`
(campo `enriquecimento`), sem parser novo.

⚠️ **2021 só tem nota em PARES somados, não as 4 matérias abertas**: o
próprio PDF define "MI" = soma de Matemática+Inglês e "FP" = soma de
Física+Português — não dá pra separar Matemática de Inglês dentro do MI
(nem Física de Português dentro do FP) a partir desse documento. Os rótulos
`mi`/`fp` (em vez de `mat`/`ing`/`fis`/`por`) marcam essa diferença de
propósito, pra não passar a impressão de granularidade que a fonte não deu
— 2023 e 2025 têm as 4 matérias abertas de verdade (MAT/ING/FIS/POR), igual
2024.

Cobertura do cruzamento: 100% em 2023 e 2025 (100/100 e 68/68 inscrições do
Resultado Final acharam par na Prova Objetiva); 2021 ficou em 36/37 — a
única que faltou ("Esther Victoria Valério M. do Nascimento") tem o nome
quebrado em duas linhas físicas na Prova Objetiva de um jeito que gruda a
nota na linha ANTES da inscrição aparecer (`sort=True` do PyMuPDF reordena
assim, mesma categoria de achado já visto no EFOMM/IME/OBQ) — descartado
como aviso, não vale a pena um regex só pra 1 caso em 423.
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

# ano -> (id_file, descrição da fase, tem_secao_titular_reserva, rótulos das
# colunas de nota NA ORDEM em que aparecem (ou None quando o documento
# principal não publica nota nenhuma), enriquecimento) — pesquisa dirigida de
# 17/09/2026 (docstring do módulo), rótulos conferidos abrindo o PDF de cada
# ano (nunca supostos por analogia): 2016/2018 usam ME+Clas.; 2022 usa
# MO+RED; 2024 usa MAT/ING/FIS/POR/MO. `tem_secao_titular_reserva` distingue
# os dois formatos: Resultado Final separa titular/reserva em seções; "não
# eliminados" é uma lista só, sem essa distinção.
#
# `enriquecimento` = (id_file de um SEGUNDO documento, rótulos dele) — pra
# 2021/2023/2025, cujo Resultado Final não abre nota nenhuma; a nota vem de
# cruzar por Nº DE INSCRIÇÃO com o resultado da fase de Provas Objetivas
# daquele mesmo ano (achado de 23/09/2026, docstring do módulo).
_DOCUMENTOS: dict[int, tuple[int, str, bool, tuple[str, ...] | None, tuple[int, tuple[str, ...]] | None]] = {
    2016: (3354, "Resultado Final", True, ("media", "classificacao"), None),
    2018: (4296, "Resultado da Seleção Inicial", True, ("media", "classificacao"), None),
    2021: (6360, "Resultado Final da Seleção", True, None, (6093, ("mi", "fp", "mo", "re", "me"))),
    2022: (7000, "Não eliminado nas provas escritas (seleção inicial)", False, ("mo", "red"), None),
    2023: (7883, "Resultado Final", True, None, (7650, ("mat", "ing", "fis", "por", "mo"))),
    2024: (8335, "Não eliminado nas provas escritas (seleção inicial)", False, ("mat", "ing", "fis", "por", "mo"), None),
    2025: (9220, "Resultado Final da Seleção", True, None, (9050, ("mat", "ing", "fis", "por", "mo"))),
}

# Inscrição sempre no início (âncora inequívoca — nunca aparece em nome), o
# bloco de notas capturado inteiro num grupo só (`notas`, dígito e vírgula,
# formato brasileiro "84,58" — o rótulo de cada valor vem de `_DOCUMENTOS`,
# não de posição fixa aqui), e o código de OREL como ÚLTIMO token da linha
# (docstring do módulo).
_PADRAO_LINHA = re.compile(
    r"^\s*(?P<insc>\d{5,6}-\d)\s+(?P<nome>.+?)\s+(?P<notas>(?:[\d,]+\s+)*)(?P<orel>\S+)\s*$",
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
    notas_por_materia: dict[str, float] | None = None


def _numero(texto: str) -> float:
    return float(texto.replace(",", "."))


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


def _linhas_brutas(texto: str) -> list[tuple[str, str, list[float], int]]:
    """(inscrição, nome, notas ainda sem rótulo, posição da linha no texto) —
    bloco comum reaproveitado tanto por `parsear_pdf` (documento principal)
    quanto por `_notas_por_inscricao` (documento de enriquecimento, docstring
    do módulo). Descarta aqui, uma vez só, a linha sem nome reconhecível."""
    saida: list[tuple[str, str, list[float], int]] = []
    for m in _PADRAO_LINHA.finditer(texto):
        nome = re.sub(r"\s+", " ", m.group("nome")).strip()
        if not nome or len(nome.split()) < 2:
            print(f"  aviso: linha sem nome reconhecível, pulando: {m.group(0)!r}", file=sys.stderr)
            continue
        valores = [_numero(v) for v in m.group("notas").split()]
        saida.append((m.group("insc"), nome, valores, m.start()))
    return saida


def _notas_por_inscricao(texto: str, rotulos_notas: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """Nota por matéria indexada por Nº DE INSCRIÇÃO, extraída de um SEGUNDO
    documento (Provas Objetivas) — usado só pra enriquecer um ano cujo
    documento principal (`_DOCUMENTOS[ano]`) não abre nota nenhuma (docstring
    do módulo, "Nota de 2021/2023/2025 por CRUZAMENTO"). Por inscrição, não
    por nome: nome pode variar grafia entre os dois PDFs."""
    return {
        insc: dict(zip(rotulos_notas, valores, strict=True))
        for insc, _nome, valores, _pos in _linhas_brutas(texto)
        if len(valores) == len(rotulos_notas)
    }


def parsear_pdf(
    conteudo: bytes,
    ano: int,
    fase: str,
    tem_secoes: bool,
    rotulos_notas: tuple[str, ...] | None,
    fonte_url: str,
    notas_por_inscricao: dict[str, dict[str, float]] | None = None,
) -> list[Registro]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    texto = "\n".join(pagina.get_text("text", sort=True) for pagina in doc)

    m_inicio = _MARCA_INICIO_LISTAGEM.search(texto)
    inicio_real = m_inicio.start() if m_inicio else 0

    registros: list[Registro] = []
    for insc, nome, valores, pos in _linhas_brutas(texto):
        notas: dict[str, float] | None = None
        if rotulos_notas and len(valores) == len(rotulos_notas):
            notas = dict(zip(rotulos_notas, valores, strict=True))
        elif notas_por_inscricao is not None:
            notas = notas_por_inscricao.get(insc)

        registros.append(
            Registro(
                prova_nome="Escola Naval (CPAEN)",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                resultado=_resultado_da_posicao(texto, inicio_real, pos, fase, tem_secoes),
                nome_informado=nome,
                escola_informada="",
                # Nunca uma cidade: OREL é unidade administrativa, não local
                # de moradia — ver docstring do módulo ("OREL não é cidade").
                cidade_informada="",
                uf_informada="",
                fonte_url=fonte_url,
                notas_por_materia=notas,
            )
        )
    return registros


def _baixar(id_file: int) -> bytes:
    url = f"{BASE}/x.pdf?id_file={id_file}"
    resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.content


def raspar_ano(ano: int) -> list[Registro]:
    id_file, fase, tem_secoes, rotulos_notas, enriquecimento = _DOCUMENTOS[ano]
    url = f"{BASE}/x.pdf?id_file={id_file}"
    conteudo = _baixar(id_file)

    notas_extra = None
    if enriquecimento:
        id_file_po, rotulos_po = enriquecimento
        doc_po = pymupdf.open(stream=_baixar(id_file_po), filetype="pdf")
        texto_po = "\n".join(pagina.get_text("text", sort=True) for pagina in doc_po)
        notas_extra = _notas_por_inscricao(texto_po, rotulos_po)
        print(f"    enriquecimento: {len(notas_extra)} inscrições com nota (id_file={id_file_po})", file=sys.stderr)

    return parsear_pdf(conteudo, ano, fase, tem_secoes, rotulos_notas, url, notas_por_inscricao=notas_extra)


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
