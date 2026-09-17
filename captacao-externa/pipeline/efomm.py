r"""Raspa a Classificação Inicial (1ª fase) e a Classificação Final
(titulares + reservas) do processo seletivo da EFOMM — CIAGA (Rio de
Janeiro) e CIABA (Belém) — e grava um JSON cru por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/efomm.py
    ./.venv/bin/python pipeline/efomm.py --anos 2023 2024 2025

## De "só o ciclo corrente" pra multi-ano curado (17/09/2026)

Até aqui este scraper só pegava o ciclo CORRENTE: os PDFs oficiais em
`assets.marinha.mil.br/ciaga/.../files/...` não têm ano no NOME do arquivo
— são sobrescritos a cada ciclo, e não havia snapshot nenhum no Wayback
Machine pra esse caminho. Um usuário mandou mirror de cursinho pro IME que
provou dar pra recuperar ano antigo por fora da fonte oficial — pesquisa
dirigida a partir disso achou que a EFOMM tem o MESMO tipo de mirror: sites
de cursinho militar (Estratégia Militares/Vestibulares) e até um jornal dos
próprios alunos da EFOMM (Jornal Pelicano, Belém) hospedam cópia dos PDFs
oficiais, com o ano no CAMINHO do arquivo — o que a fonte oficial nunca
teve. `_DOCUMENTOS` é o resultado curado: 6 anos (2017, 2022-2026), cada um
confirmado baixando e lendo o PDF de verdade.

⚠️ Achados de 2016 e 2021 no Scribd (paywall) foram DESCARTADOS — só deu pra
confirmar pelo preview renderizado, nunca baixando o arquivo de verdade, e a
régua deste pipeline é nunca confiar em conteúdo que não foi lido de
verdade (mesmo cuidado que já pegou falso positivo na Escola Naval —
`CP-CEM`/`CP-PMS` disfarçados de `CPAEN` só pelo nome do arquivo). Faltam
2018, 2019 e 2020 — não achados em nenhum domínio pesquisado.

## Dois hosts oficiais com comportamento diferente — use SEMPRE `assets.`

`www.marinha.mil.br/ciaga/*` (páginas institucionais Drupal) está atrás de
Cloudflare managed challenge (403 pra requisição simples). Os PDFs de
resultado, hospedados no espelho de assets estático
(`assets.marinha.mil.br/ciaga/sites/www.marinha.mil.br.ciaga/files/...`),
**não** passam por esse desafio — servidor estático plano, sem bloqueio.
Isso só vale pro ciclo 2026 (oficial); os anos anteriores vêm de mirror de
cursinho, sem esse problema.

## Reservas: CIAGA tem lista única, CIABA nem sempre (achado, não preguiça)

CIAGA costuma publicar "Candidatos na condição de RESERVAS" como documento
único e estável, igual titulares — 2023 e 2026 confirmados assim. CIABA às
vezes não — em 2026 a convocação de reserva de lá sai como boletim numerado
incremental ("10 CONVOCAÇÃO DOS RESERVAS-CIABA.pdf", que vira "11...",
"12..." a cada substituição), sem nome de arquivo fixo pra apontar; por
isso fica de fora quando não achado. 2017/2022/2024/2025 não tiveram reserva
de nenhum casco confirmada na pesquisa — só titular e classificação inicial.

## 2017 tem uma fase a mais: "2ª Convocação" de pós-classificados

Achado só nesse ano: depois da Classificação Inicial, uma SEGUNDA leva de
pós-classificados foi publicada em documento separado (2_convocacao_CIAGA...
pdf) — mesma categoria (ainda fase 1, ainda pós-classificado), só que
chamada explicitamente à parte. Vira `fase="fase1_conv2"`: sempre
Pós-classificado, sem precisar do marcador de seção (o documento inteiro já
É a segunda convocação).

## Nome pode quebrar em 3 linhas no `pdftotext -layout` — nome muito comprido

Um nome com 6+ palavras não cabe na largura da coluna e o extrator devolve a
PRIMEIRA parte na linha ACIMA da linha de dado, e a ÚLTIMA palavra (o
sobrenome final) na linha ABAIXO — a linha de dado em si fica com um "buraco"
onde o nome deveria estar (só rank + inscrição + notas + cidade + data).
Com `sort=True` do PyMuPDF, as três partes acabam intercaladas numa linha
SÓ (início do nome ANTES do rank, sobrenome final DEPOIS da data) — ver
`prefixo`/`sufixo` em `_PADRAO_LINHA`.

## Ordem de Nome/Inscrição muda entre fase 1 e fase 4 — mesmo problema da OBM

Fase 1: `Clas. | Insc. | Nome | ... | Dt_Nasc`. Fase 4 (titulares/reservas):
`Clas. | Nome | Insc. | ... | Data_Nasc` — **nome e inscrição trocam de
lugar**. `_PADRAO_LINHA` não fixa a ordem: captura o trecho inteiro entre o
rank e o bloco de notas como `meio`, acha a inscrição por regex DENTRO dele
(`\d{5,6}-\d`, formato que nunca aparece no nome) e trata o resto de `meio`
como nome — funciona nas duas ordens sem precisar saber qual é qual.
Confirmado que o MESMO padrão casa sem alteração em 2017 e 2022-2025, apesar
de vir de domínios/geradores diferentes.

## Sem escola — cidade é onde fez a prova (ODE), não onde mora

Mesma ressalva de ITA/IME: o candidato faz prova na banca mais perto, não na
própria cidade. `_UF_DA_CIDADE` traduz os nomes de cidade-sede vistos pra UF
— não é lista genérica de capital, é conferida contra todo valor de ODE
observado (inclui Corumbá/MS, Paranaguá/PR, Parnaíba/PI e Santarém/PA, que
não são capital).

## `assets.marinha.mil.br` também não manda a cadeia intermediária

Mesmo achado do IME (`inscricoes.ime.eb.br`, ver pipeline/ime.py): `curl`
valida normal (completa a cadeia com o que já tem por perto), o verificador
de certificado do Python não (`unable to get local issuer certificate`). Só
esse host específico precisa de `verify=False` — os mirrors de cursinho e o
Jornal Pelicano têm certificado normal.
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

_HOST_CERT_QUEBRADO = "assets.marinha.mil.br"
_BASE_OFICIAL = "https://assets.marinha.mil.br/ciaga/sites/www.marinha.mil.br.ciaga/files"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# ano -> [(casco, url, fase)] — pesquisa dirigida de 17/09/2026 (docstring do
# módulo). `fase` em {"fase1", "fase1_conv2", "titular", "reserva"}.
_DOCUMENTOS: dict[int, list[tuple[str, str, str]]] = {
    2017: [
        ("CIAGA", "http://static.jornalpelicano.com.br/2016/09/CLAS-e-POS_CLASSIFICADOS_CIAGA.pdf", "fase1"),
        (
            "CIAGA",
            "http://static.jornalpelicano.com.br/2016/11/2_convocacao_CIAGA_POS_CLASSIFICADOS_SITE.pdf",
            "fase1_conv2",
        ),
        ("CIAGA", "http://static.jornalpelicano.com.br/2016/12/SITE_CLASSIFICACAO-FINAL_CIAGA_TITULARES.pdf", "titular"),
        ("CIABA", "http://static.jornalpelicano.com.br/2016/12/SITE_CLASSIFICACAO-FINAL_CIABA_TITULARES.pdf", "titular"),
    ],
    2022: [
        (
            "CIAGA",
            "https://cdn.blog.estrategiavestibulares.com.br/vestibulares/wp-content/uploads/2021/09/Lista-EFOMM-2022-CIAGA.pdf",
            "fase1",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2021/09/Lista-EFOMM-2022-CIABA.pdf",
            "fase1",
        ),
        (
            "CIAGA",
            "https://cdn.blog.estrategiavestibulares.com.br/vestibulares/wp-content/uploads/2021/12/Candidatos-TITULARES-convocados-para-o-CIAGA.pdf",
            "titular",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2021/12/Candidatos-TITULARES-convocados-para-o-CIABA.pdf",
            "titular",
        ),
    ],
    2023: [
        (
            "CIAGA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2022/09/CANDIDATOS-CLASSIFICADOS-E-POS-CLASSIFCADOS-CIAGA.pdf",
            "fase1",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2022/09/CANDIDATOS-CLASSIFICADOS-E-POS-CLASSIFICADOS-CIABA.pdf",
            "fase1",
        ),
        (
            "CIAGA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2022/12/Candidatos-TITULARES-convocados-para-o-CIAGA.pdf",
            "titular",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2022/12/Candidatos-TITULARES-convocados-para-o-CIABA_0.pdf",
            "titular",
        ),
        (
            "CIAGA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2022/12/Candidatos-na-condicao-de-RESERVAS-CIAGA_2.pdf",
            "reserva",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2022/12/Candidatos-na-condicao-de-RESERVAS-CIABA_1.pdf",
            "reserva",
        ),
    ],
    2024: [
        (
            "CIAGA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2023/09/CANDIDATOS-CLASSIFICADOS-E-POS-CLASSIFCADOS_CIAGA.pdf",
            "fase1",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2023/09/CANDIDATOS-CLASSIFICADOS-E-POS-CLASSIFICADOS_CIABA_1.pdf",
            "fase1",
        ),
        (
            "CIAGA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2023/12/Candidatos-TITULARES-convocados-para-o-CIAGA.pdf",
            "titular",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2023/12/Candidatos-TITULARES-convocados-para-o-CIABA_0.pdf",
            "titular",
        ),
    ],
    2025: [
        (
            "CIAGA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2024/09/CANDIDATOS-CLASSIFICADOS-E-POS-CLASSIFCADOS_CIAGA.pdf",
            "fase1",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2024/09/CANDIDATOS-CLASSIFICADOS-E-POS-CLASSIFICADOS_CIABA_1.pdf",
            "fase1",
        ),
        (
            "CIAGA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2024/12/Candidatos-TITULARES-convocados-para-o-CIAGA.pdf",
            "titular",
        ),
        (
            "CIABA",
            "https://militares.estrategia.com/portal/wp-content/uploads/2024/12/Candidatos-TITULARES-convocados-para-o-CIABA_1.pdf",
            "titular",
        ),
    ],
    2026: [
        (
            "CIAGA",
            f"{_BASE_OFICIAL}/Processos%20Seletivos/CANDIDATOS%20CLASSIFICADOS%20E%20P%C3%93S-CLASSIFCADOS_CIAGA_0.pdf",
            "fase1",
        ),
        (
            "CIABA",
            f"{_BASE_OFICIAL}/Processos%20Seletivos/CANDIDATOS%20CLASSIFICADOS%20E%20P%C3%93S-CLASSIFICADOS_CIABA.pdf",
            "fase1",
        ),
        (
            "CIAGA",
            f"{_BASE_OFICIAL}/Processo%20Seletivo/Candidatos%20TITULARES%20-%20convocados%20para%20o%20CIAGA_0.pdf",
            "titular",
        ),
        (
            "CIABA",
            f"{_BASE_OFICIAL}/Processo%20Seletivo/Candidatos%20TITULARES%20-%20convocados%20para%20o%20CIABA_0.pdf",
            "titular",
        ),
        (
            "CIAGA",
            f"{_BASE_OFICIAL}/Processo%20Seletivo/Candidatos%20na%20condi%C3%A7%C3%A3o%20de%20RESERVAS%20-%20CIAGA%20-%20Retificada_0.pdf",
            "reserva",
        ),
    ],
}

_UF_DA_CIDADE: dict[str, str] = {
    "AMAPA": "AP",
    "BELEM": "PA",
    "BELO HORIZONTE": "MG",
    "BRASILIA": "DF",
    "CORUMBA": "MS",
    "CUIABA": "MT",
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
    "SAO LUIZ": "MA",  # grafia com Z aparece de verdade na fonte (2023) — não é erro de raspagem
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
    r"(?P<notas>(?:\d{1,3}\s+){3,6}\d{1,3})\s+"
    r"(?P<cidade>[A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ '\-]*?)\s+"
    r"(?P<data>\d{2}/\d{2}/\d{4})"
    r"\s*(?P<sufixo>[A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÜÇ'\-]*)?\s*$",
    re.MULTILINE,
)
_INSCRICAO = re.compile(r"\d{5,6}-\d")
# Ordem de coluna real do relatório (docs/41 §11.1) — "total" é a GI/GF que a
# EFOMM soma na própria tabela. Só um dos dois bate o nº de valores achados
# em `notas`; o outro fica de fora, nunca inventado por posição errada.
_MATERIAS_POR_QTD = {
    5: ("ing", "por", "mat", "fis", "total"),  # 1ª fase (Classificação Inicial)
    6: ("ing", "por", "red", "mat", "fis", "total"),  # final (titular/reserva)
}
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
    notas_por_materia: dict[str, float] | None = None


def _notas_por_materia(bloco: str) -> dict[str, float] | None:
    valores = [int(v) for v in bloco.split()]
    materias = _MATERIAS_POR_QTD.get(len(valores))
    if materias is None:
        # Quantidade fora do esperado (5 ou 6) — não arrisca casar número com
        # matéria errada só por posição; melhor não ter a granularidade do
        # que ter errada.
        return None
    return dict(zip(materias, valores, strict=True))


def parsear_pdf(conteudo: bytes, casco: str, fase: str, fonte_url: str) -> tuple[int | None, list[Registro]]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    # `sort=True` aproxima a ordem visual (coluna por coluna) — sem isso a
    # extração vem token a token, uma linha por número/palavra, impossível
    # de casar por regex de linha inteira.
    texto = "\n".join(pagina.get_text("text", sort=True) for pagina in doc)

    m_ano = _PADRAO_ANO.search(texto)
    if not m_ano:
        return None, []
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
        elif fase == "fase1_conv2":
            resultado = f"{casco} — Pós-classificado (2ª convocação, 1ª fase)"
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
                notas_por_materia=_notas_por_materia(m.group("notas")),
            )
        )
    return ano, registros


def _get(url: str) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=30, verify=_HOST_CERT_QUEBRADO not in url)
    resp.raise_for_status()
    return resp


def raspar_ano(ano: int) -> list[Registro]:
    registros: list[Registro] = []
    for casco, url, fase in _DOCUMENTOS[ano]:
        resp = _get(url)
        ano_no_pdf, novos = parsear_pdf(resp.content, casco, fase, url)
        if ano_no_pdf is None:
            print(f"  aviso: não achei 'EFOMM AAAA' em {url} — layout mudou?", file=sys.stderr)
            continue
        if ano_no_pdf != ano:
            print(
                f"  aviso: esperava {ano}, o PDF diz {ano_no_pdf} — pulando, a fonte deve ter mudado ({url})",
                file=sys.stderr,
            )
            continue
        registros.extend(novos)
        print(f"  {casco} {fase}: {len(novos)} registros", file=sys.stderr)
    return registros


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
            print(f"  {ano}: sem documento curado, pulando (ver _DOCUMENTOS)", file=sys.stderr)
            continue

        print(f"EFOMM {ano} — raspando...", file=sys.stderr)
        try:
            registros = raspar_ano(ano)
        except requests.HTTPError as e:
            print(f"  falhou: {e}", file=sys.stderr)
            continue

        if not registros:
            print("  0 registros — algo mudou na fonte, confira antes de importar", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"efomm_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  EFOMM {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
