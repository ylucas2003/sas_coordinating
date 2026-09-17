r"""Raspa o resultado do concurso de admissão do IME — CACFG (Curso de
Formação e Graduação, o vestibular civil de ensino médio; não confundir com
o "CP/IME" de pós-graduação de oficiais já formados, achado por engano na
primeira tentativa e descartado) — e grava um JSON por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/ime.py
    ./.venv/bin/python pipeline/ime.py --anos 2023 2024 2025

## De "só o ciclo corrente" pra multi-ano curado (17/09/2026)

Até aqui este scraper só pegava o ciclo CORRENTE: `inscricoes.ime.eb.br/
documentos/ATIVA.pdf`/`RESERVA.pdf` não têm ano na URL, são sobrescritos a
cada concurso, e não existia arquivo oficial por ano pra voltar atrás. Um
usuário mandou um link de mirror de cursinho (`cdn.blog.estrategiavestibulares.
com.br/.../Resultado_Final-IME.pdf`, CACFG 2023/2024) provando que dava pra
recuperar ano antigo por fora da fonte oficial — pesquisa dirigida a partir
disso achou mais: um domínio IRMÃO do oficial que NÃO é sobrescrito
(`www.ime.eb.mil.br`, com arquivos de 2016 e 2020 ainda vivos), o Wayback
Machine congelando snapshots do próprio `inscricoes.ime.eb.br` de anos
anteriores por baixo da mesma URL sobrescrita, e mirrors de cursinho militar
(Estratégia Militares) publicando a lista de 2ª fase por conta própria todo
outubro. `_DOCUMENTOS` é o resultado curado dessa busca em duas rodadas — 9
anos (2016, 2018-2025), cada um com o que foi possível confirmar baixando e
lendo o PDF de verdade (nunca confiando só no nome do arquivo ou no snippet
de busca). Só 2017 e a 2ª fase de 2020 continuam sem achar.

⚠️ Um "achado" de 2019 (`vestibulandoweb.com.br/.../resultado-final-ime-2020.pdf`)
foi DESCARTADO depois de baixado: a tabela não tem coluna de NOME nenhuma —
alguém cortou a coluna ao reformatar pro blog. Sem nome não tem lead, então
esse ano só entra pela peça de 2ª fase (que tem nome, veio do Wayback Machine
do site oficial). Outro achado (Resultado Final ATIVA/RESERVA de 2021 via
print do Diário Oficial da União) tem um layout de tabela mais frágil e sem
coluna de cidade — fora desta rodada por custo/benefício, não é bug.

## Duas fases por ano — a mesma "todos os alunos" que já valeu pro ITA

Descoberto rodando de verdade, com um mirror mandado por usuário: o IME
TAMBÉM publica uma "Relação dos habilitados para a 2ª fase" — quem passou na
prova escrita, ANTES da inspeção de saúde/documental que gera o Resultado
Final. É uma lista bem maior que a final (ex.: 2022/2023 teve 1.044
habilitados contra ~530 aprovados finais) — cruzando as duas por número de
inscrição, mais de 40% dos habilitados na 2ª fase não aparecem no resultado
final (reprovaram depois, ou ficaram de fora do corte de vaga). Isso
CONTRADIZ o que este módulo dizia até 16/09/2026 ("só tem UMA fase escrita,
não tem o que ampliar" — docs/41 §6.2.1): a fonte tem sim uma fase
intermediária nomeada, só não estava na busca de então.

## Três formatos de tabela, não um só

O layout do PDF mudou pelo menos duas vezes na década:

- **`_parsear_final_padrao`** (2020, 2022-2025): rank°, inscrição, sigilo,
  NOME, média, mat, fis, qui, port, ing, local, (situação) — o formato
  original deste scraper, um campo por linha na extração padrão do PyMuPDF.
- **`_parsear_final_2016`**: inscrição e sigilo saem na MESMA linha
  (`"115343 000821"`), tem duas colunas a mais (Ing Obj/Ing Disc, o inglês
  quebrado em objetiva/discursiva) e não tem coluna de situação nenhuma.
- **`_parsear_fase2`**: ord, inscrição, candidato, local, carreira — mais
  simples, mas só sai direito com `sort=True` do PyMuPDF (o padrão espalha
  os campos em ordem errada pra este layout específico, mesmo achado do
  `pipeline/efomm.py`).

Cada parser devolve o ANO extraído de dentro do próprio PDF — nunca assumido
pelo ano do dicionário — e `raspar_ano` descarta com aviso se não bater (ex.:
se um domínio ainda vivo um dia trocar de conteúdo, como já aconteceu com o
`inscricoes.ime.eb.br` entre uma pesquisa e outra desta mesma sessão).

## `verify=False` só onde precisa

`inscricoes.ime.eb.br` tem cadeia de certificado incompleta (`curl` tolera,
`requests` não) — mesmo achado de sempre. Os outros domínios (mirror de
cursinho, `www.ime.eb.mil.br`, Wayback Machine) têm certificado normal;
desligar verificação pra eles também seria frouxidão sem necessidade.

## Sem escola, sem série de referência — mesma ausência de sempre

Vestibular de verdade, não olimpíada: não diz se é treineiro ou formando
(`serie_referencia_min/max` fica `None`) nem escola (`escola_informada`
fica `""`, nunca `None` — o índice único de dedup trata NULL como
sempre-diferente-de-NULL).

## "Local de Exame" é a cidade da PROVA, não do candidato

Mesma ressalva da ITA: quem mora longe faz a prova no local mais perto, não
na própria cidade. `_CIDADE_DA_BANCA` é a mesma lista usada desde a versão
anterior deste scraper.
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

# inscricoes.ime.eb.br não manda a cadeia intermediária — curl tolera
# (completa com o que já tem por perto), requests não sem verify=False.
# Achado rodando de verdade: o domínio irmão `www.ime.eb.mil.br` tem o MESMO
# problema (mesma infra do Exército) — não é só um host, é sistêmico nesses
# domínios .eb.br/.mil.br (a Marinha também tem, ver pipeline/efomm.py e
# pipeline/escola_naval.py). Os mirrors de cursinho e o Wayback Machine têm
# certificado normal; a exceção fica só pra quem precisa dela (ver `_get`).
_HOSTS_CERT_QUEBRADO = ("inscricoes.ime.eb.br", "www.ime.eb.mil.br")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# ano -> [(url, formato, modalidade)] — pesquisa dirigida de 17/09/2026
# (docstring do módulo). `formato` seleciona o parser; `modalidade` é
# "ATIVA"/"RESERVA" pros formatos finais, "" pra fase2 (que já traz a
# carreira embutida em cada linha, na coluna "Carreira").
_BASE_OFICIAL = "https://inscricoes.ime.eb.br/documentos"
_DOCUMENTOS: dict[int, list[tuple[str, str, str]]] = {
    2016: [
        (
            "https://www.ime.eb.mil.br/arquivos/Admissao/Vestibular_CFG/Resultados/2016-2017/Resultado_final_CACFG_2016-17_ATIVA.pdf",
            "final_2016",
            "ATIVA",
        ),
        (
            "https://www.ime.eb.mil.br/arquivos/Admissao/Vestibular_CFG/Resultados/2016-2017/Resultado_final_CACFG_2016-17_RESERVA.pdf",
            "final_2016",
            "RESERVA",
        ),
    ],
    2018: [
        (
            "https://web.archive.org/web/20190116110532/http://inscricoes.ime.eb.br/vestibular/documentos/Candidatos_aprovados_para_a_2%C2%AA_FASE_-_Rela%C3%A7%C3%A3o.pdf",
            "fase2",
            "",
        ),
    ],
    2019: [
        (
            "https://web.archive.org/web/20210921151353/http://inscricoes.ime.eb.br/documentos/Candidatos_aprovados_para_a_2%C2%AA_FASE_-_Rela%C3%A7%C3%A3o.pdf",
            "fase2",
            "",
        ),
    ],
    2020: [
        (
            "https://www.ime.eb.mil.br/images/arquivos/admissao/cfg/RelatorioResultadoFinal_ATIVA_CFG2020.pdf",
            "final_padrao",
            "ATIVA",
        ),
        (
            "https://www.ime.eb.mil.br/images/arquivos/admissao/cfg/RelatorioResultadoFinal_RESERVA_CFG2020.pdf",
            "final_padrao",
            "RESERVA",
        ),
    ],
    2021: [
        (
            "https://s4.static.brasilescola.uol.com.br/vestibular/2021/10/classificados-ime-para-2-fase-2021-2022.pdf",
            "fase2",
            "",
        ),
    ],
    2022: [
        (
            "https://cdn.blog.estrategiavestibulares.com.br/vestibulares/wp-content/uploads/2022/12/Resultado_Final-IME-2023.pdf",
            "final_padrao",
            "ATIVA",
        ),
        (
            "https://s5.static.brasilescola.uol.com.br/vestibular/2022/10/resultado-1-fase-vestibular-2023-ime.pdf",
            "fase2",
            "",
        ),
    ],
    2023: [
        (
            "https://cdn.blog.estrategiavestibulares.com.br/vestibulares/wp-content/uploads/2023/12/Resultado_Final-IME.pdf",
            "final_padrao",
            "ATIVA",
        ),
        (
            "https://militares.estrategia.com/portal/wp-content/uploads/2023/10/aprovados-na-primeira-fase-IME-2024.pdf",
            "fase2",
            "",
        ),
    ],
    2024: [
        (
            "https://web.archive.org/web/20250105061519/https://inscricoes.ime.eb.br/documentos/Resultado.pdf",
            "final_padrao",
            "ATIVA",
        ),
        ("https://militares.estrategia.com/portal/wp-content/uploads/2024/10/Relacao.pdf", "fase2", ""),
    ],
    2025: [
        (f"{_BASE_OFICIAL}/ATIVA.pdf", "final_padrao", "ATIVA"),
        (f"{_BASE_OFICIAL}/RESERVA.pdf", "final_padrao", "RESERVA"),
        ("https://militares.estrategia.com/portal/wp-content/uploads/2025/10/Relacao.pdf", "fase2", ""),
    ],
}

_CIDADE_DA_BANCA: dict[str, tuple[str, str]] = {
    "BELEM": ("Belém", "PA"),
    "BELO HORIZONTE": ("Belo Horizonte", "MG"),
    "BRASILIA": ("Brasília", "DF"),
    "CAMPINAS": ("Campinas", "SP"),
    "CAMPO GRANDE": ("Campo Grande", "MS"),
    "CUIABA": ("Cuiabá", "MT"),
    "CURITIBA": ("Curitiba", "PR"),
    "FLORIANOPOLIS": ("Florianópolis", "SC"),
    "FORTALEZA": ("Fortaleza", "CE"),
    "GOIANIA": ("Goiânia", "GO"),
    "JUIZ DE FORA": ("Juiz de Fora", "MG"),
    "LONDRINA": ("Londrina", "PR"),
    "MANAUS": ("Manaus", "AM"),
    "NATAL": ("Natal", "RN"),
    "PORTO ALEGRE": ("Porto Alegre", "RS"),
    "RECIFE": ("Recife", "PE"),
    "RIBEIRAO PRETO": ("Ribeirão Preto", "SP"),
    "RIO DE JANEIRO": ("Rio de Janeiro", "RJ"),
    "SALVADOR": ("Salvador", "BA"),
    "SANTA MARIA": ("Santa Maria", "RS"),
    "SAO JOSE DO RIO PRETO": ("São José do Rio Preto", "SP"),
    "SAO JOSE DOS CAMPOS": ("São José dos Campos", "SP"),
    "SAO LUIS": ("São Luís", "MA"),
    "SAO PAULO": ("São Paulo", "SP"),
    "TERESINA": ("Teresina", "PI"),
    "VITORIA": ("Vitória", "ES"),
    "VILA VELHA": ("Vila Velha", "ES"),
}

_SITUACAO = {
    "1": "ampla concorrência",
    "2": "Lei 12.990 (cota racial)",
    "3": "excedente",
}

# rank, inscrição, sigilo, NOME, média, mat, fis, qui, port, ing, local, situação
# — sempre nessa ordem numa linha de candidato APROVADO. A relação de NÃO
# aprovados não tem NOME nenhum, então nunca casa aqui.
_PADRAO_FINAL = re.compile(
    r"(\d+)°\n(\d+)\n(\d+)\n(.+?)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n([^\n]+)\n\((\d)\)"
)

# 2016: inscrição+sigilo na MESMA linha, 8 números entre o nome e o local
# (média + mat/fis/qui/port/ing/ing-obj/ing-disc), sem situação.
_PADRAO_FINAL_2016 = re.compile(r"(\d+)°\n(\d+) (\d+)\n(.+?)\n(?:[\d,]+\n){8}([^\n]+?)\n")

# ord, inscrição, candidato, local, carreira — precisa de `sort=True` na
# extração (docstring do módulo). NOME é sempre CAIXA ALTA neste layout e
# LOCAL é sempre Título (city "São José dos Campos"), então o nome casa
# greedy só em maiúscula+apóstrofo/hífen (sobrenome como "DAL'EVEDOVE" ou
# "SANT'ANNA" quebraria um charset sem eles — achado rodando de verdade) até
# a primeira letra minúscula, que só pode ser do local.
_PADRAO_FASE2 = re.compile(
    r"^\s*\d+\s+(\d{6})\s+([A-ZÀ-Ü][A-ZÀ-Ü'\- ]*[A-ZÀ-Ü])\s+(.+?)\s+(ATIVA|RESERVA)\s*$",
    re.MULTILINE,
)


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def _cidade_e_uf(local_bruto: str) -> tuple[str, str]:
    local_normalizado = _sem_acento(local_bruto.strip()).upper()
    cidade, uf = _CIDADE_DA_BANCA.get(local_normalizado, (local_bruto.strip(), ""))
    if local_normalizado not in _CIDADE_DA_BANCA:
        print(f"  aviso: local de exame desconhecido {local_bruto!r} — sem UF", file=sys.stderr)
    return cidade, uf


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


def _parsear_final_padrao(conteudo: bytes, modalidade: str, fonte_url: str) -> tuple[int | None, list[Registro]]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    texto = "".join(pagina.get_text() for pagina in doc)

    m_ano = re.search(r"CACFG (\d{4})/\d{4}", texto)
    if not m_ano:
        return None, []
    ano = int(m_ano.group(1))

    registros: list[Registro] = []
    for _classif, _insc, _sigilo, nome, _media, _mat, _fis, _qui, _port, _ing, local, situacao in _PADRAO_FINAL.findall(texto):
        nome = nome.strip()
        if not nome:
            continue
        cidade, uf = _cidade_e_uf(local)
        registros.append(
            Registro(
                prova_nome="IME",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                resultado=f"{modalidade} — {_SITUACAO.get(situacao, f'situação {situacao}')}",
                nome_informado=nome,
                escola_informada="",
                cidade_informada=cidade,
                uf_informada=uf,
                fonte_url=fonte_url,
            )
        )
    return ano, registros


def _parsear_final_2016(conteudo: bytes, modalidade: str, fonte_url: str) -> tuple[int | None, list[Registro]]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    texto = "".join(pagina.get_text() for pagina in doc)

    m_ano = re.search(r"Exame de Escolaridade (\d{4})/\d{4}", texto)
    if not m_ano:
        return None, []
    ano = int(m_ano.group(1))

    registros: list[Registro] = []
    for _rank, _insc, _sigilo, nome, local in _PADRAO_FINAL_2016.findall(texto):
        nome = nome.strip()
        if not nome:
            continue
        cidade, uf = _cidade_e_uf(local)
        registros.append(
            Registro(
                prova_nome="IME",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                # Sem coluna de situação neste layout (docstring do módulo)
                # — não dá pra inventar ampla-concorrência/cota/excedente.
                resultado=modalidade,
                nome_informado=nome,
                escola_informada="",
                cidade_informada=cidade,
                uf_informada=uf,
                fonte_url=fonte_url,
            )
        )
    return ano, registros


def _parsear_fase2(conteudo: bytes, fonte_url: str) -> tuple[int | None, list[Registro]]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    texto = "\n".join(pagina.get_text("text", sort=True) for pagina in doc)

    m_ano = re.search(r"CA/CFG (\d{4})/\d{4}", texto)
    if not m_ano:
        return None, []
    ano = int(m_ano.group(1))

    registros: list[Registro] = []
    for _insc, nome, local, carreira in _PADRAO_FASE2.findall(texto):
        nome = re.sub(r"\s+", " ", nome).strip()
        if not nome:
            continue
        cidade, uf = _cidade_e_uf(local)
        registros.append(
            Registro(
                prova_nome="IME",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                resultado=f"Habilitado — 2ª fase ({carreira.upper()})",
                nome_informado=nome,
                escola_informada="",
                cidade_informada=cidade,
                uf_informada=uf,
                fonte_url=fonte_url,
            )
        )
    return ano, registros


_PARSERS = {
    "final_padrao": lambda conteudo, modalidade, fonte_url: _parsear_final_padrao(conteudo, modalidade, fonte_url),
    "final_2016": lambda conteudo, modalidade, fonte_url: _parsear_final_2016(conteudo, modalidade, fonte_url),
    "fase2": lambda conteudo, _modalidade, fonte_url: _parsear_fase2(conteudo, fonte_url),
}


def _get(url: str) -> requests.Response:
    verificar = not any(host in url for host in _HOSTS_CERT_QUEBRADO)
    resp = requests.get(url, headers=HEADERS, timeout=30, verify=verificar)
    resp.raise_for_status()
    return resp


def raspar_ano(ano: int) -> list[Registro]:
    registros: list[Registro] = []
    for url, formato, modalidade in _DOCUMENTOS[ano]:
        resp = _get(url)
        ano_no_pdf, novos = _PARSERS[formato](resp.content, modalidade, url)
        if ano_no_pdf is None:
            print(f"  aviso: não achei o ano dentro do PDF ({url}) — layout mudou?", file=sys.stderr)
            continue
        if ano_no_pdf != ano:
            print(
                f"  aviso: esperava {ano}, o PDF diz {ano_no_pdf} — pulando, a fonte deve ter mudado ({url})",
                file=sys.stderr,
            )
            continue
        registros.extend(novos)
        print(f"  {formato} {modalidade or ''}: {len(novos)} registros", file=sys.stderr)
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

        print(f"IME (CACFG) {ano} — raspando...", file=sys.stderr)
        try:
            registros = raspar_ano(ano)
        except requests.HTTPError as e:
            print(f"  falhou: {e}", file=sys.stderr)
            continue

        if not registros:
            print("  0 registros — algo mudou na fonte, confira antes de importar", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"ime_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  IME {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
