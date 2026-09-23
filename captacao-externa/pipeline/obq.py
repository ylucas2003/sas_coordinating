"""Raspa os resultados da OBQ (Olimpíada Brasileira de Química) e da OBQ Jr
(Olimpíada Brasileira de Química Júnior) — duas provas distintas, do mesmo
programa (PNOQ/UFC+UFPI), com público-alvo diferente (OBQ é médio, OBQ Jr é
6º-9º fundamental) — e grava um JSON cru POR PROVA e por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/obq.py --anos 2022 2024 2025 --fonte obq
    ./.venv/bin/python pipeline/obq.py --anos 2021 2022 2023 --fonte obqjr
    ./.venv/bin/python pipeline/obq.py --anos 2022 2023 2024 2025 --fonte ambas

Grava dados/obq_{ano}.json e dados/obqjr_{ano}.json — arquivos separados
porque são `prova_externa` separadas (docs/41 §6, item 2), mesmo os dois
saindo deste único script.

## Primeira fonte do projeto em PDF que também exige DUAS formas de parsing

obquimica.org/olimpiada/... lista um PDF de resultado por ano, mas o GERADOR
do PDF mudou pelo menos duas vezes na década — não dá pra usar um parser só:

- **"tabela"**: PDF gerado a partir de planilha, com bordas de célula reais.
  `pagina.find_tables()` do PyMuPDF lê direto — usado por OBQ 2024/2025 e por
  OBQ Jr 2022/2023.
- **"texto"**: PDF mais antigo, sem tabela detectável (`find_tables()` devolve
  zero) — usado por OBQ 2022 e OBQ Jr 2021. Cada registro é um bloco curto de
  linhas consecutivas (nome, escola, estado/UF[, cidade], série, nota,
  escore); em vez de filtrar cabeçalho/rodapé linha por linha (frágil — o
  texto varia demais entre os dois documentos), o parser ANCORA no campo
  ESTADO/UF: é o único campo com um conjunto FECHADO e conhecido de valores
  (27 unidades federativas), então uma linha que bate exatamente com uma
  delas (por extenso, sem se importar com acento — "Espirito Santo" aparece
  sem acento de verdade na fonte 2022 — ou sigla de 2 letras) nunca é
  cabeçalho, título ou nome de aluno. Nome e escola ficam nas 1-2 linhas
  ANTES da âncora; cidade (quando existe) e nota/escore ficam nas linhas
  DEPOIS, sem precisar ser lidos.

  ⚠️ **Nota/escore não são âncora confiável**: a primeira versão deste parser
  usava o par (nota, escore) — duas linhas seguidas só com número — como
  âncora, e isso PERDIA inteiras as faixas de "Menção Honrosa" e "Demais
  Classificados"/"Demais Participantes": essas faixas às vezes publicam só
  UMA nota (sem escore) ou nenhuma nota (só "NÃO INF." em vez de série),
  porque não estão mais competindo por posição. Achado rodando de verdade
  contra a OBQ 2022 (226 registros viravam só 138, sem nenhuma Menção
  Honrosa) e a OBQ Jr 2021. O campo Estado/UF é o único que as cinco faixas
  sempre publicam.

`_DOCUMENTOS_OBQ`/`_DOCUMENTOS_OBQ_JR` curam qual PDF é qual formato, ano a
ano — a mesma régua do IME/EFOMM/Escola Naval: nada de adivinhar o formato
em tempo de execução, cada entrada foi baixada e lida de verdade antes de
entrar aqui.

## Anos confirmados, e por que os outros ficaram de fora

**OBQ**: 2022, 2024, 2025. **2023 não entrou** — a seção "Resultados de 2023"
da página só tem o PDF da Fase IV (laboratório, só medalhistas de Ouro da
Modalidade A já filtrados, sem coluna de medalha nenhuma); o PDF da Fase III
(que teria Ouro/Prata/Bronze/Menção) não está publicado nessa seção pra esse
ano — confirmado abrindo a página de verdade, não suposição. 2019-2021
citados como "não confirmados" numa versão anterior deste plano na verdade
têm PDF listado (2019, 2020, 2021 aparecem em "Resultados de..."), mas não
foram abertos ainda; ficam como próximo passo, não como esta rodada.

**OBQ Jr**: 2021, 2022, 2023. **2024 e 2025 ficaram de fora**: o PDF de 2024
(`Estudantes X Notas`) só publica código do aluno + nome + classificação —
SEM escola nem UF, então não serve pra identidade (mesma categoria de
ausência do "Não Aprovados" do IME, §6.2.1 do plano). 2025 publica seis PDFs
fragmentados por série (6ª-9ª) que são listas de CLASSIFICADOS pra fase
seguinte — sem medalha nenhuma — mais dois PDFs de medalha só pra ESCOLA
PÚBLICA por UF; não achei, nesta rodada, o PDF de medalha da OBQ Jr 2025 que
cubra rede pública E privada juntas. Documentado aqui como lacuna real, não
escondida.

## Achados que não davam pra prever sem abrir o PDF de verdade

1. **"OIRO"** — a OBQ 2025 Modalidade B (o PDF cujo NOME do arquivo é um hash
   sem relação com o conteúdo — `01KN25Y5....pdf` — a modalidade real só se
   confirma abrindo e lendo "MODALIDADE B" no cabeçalho de cada página, nunca
   pelo nome do link) escreve a medalha de Ouro como "OIRO" — typo real da
   fonte, não erro de extração (confirmado que a célula da tabela já vem
   assim). `_normalizar_medalha` trata como sinônimo de "OURO".
2. **"HONRA"** — no PDF combinado da OBQ 2024 (as duas modalidades no MESMO
   arquivo, separadas por cabeçalho de página "MODALIDADE A"/"MODALIDADE B"),
   o marcador de Menção Honrosa quebra exatamente na virada de página e só
   "HONRA" sobrevive na célula (a extração de tabela por página perde a
   palavra "MENÇÃO", que ficou na página anterior). Tratado como sinônimo.
3. **Estado vem ora como SIGLA, ora por EXTENSO** — OBQ Jr 2021/2022 dão UF
   de 2 letras; OBQ Jr 2023 e a OBQ inteira (2022/2024/2025) dão o nome do
   estado por extenso, maiúsculo, sem padrão de acentuação confiável. `_uf()`
   aceita as duas formas.
4. **A OBQ (adulto) não publica cidade, só Estado** — achado real, mesma
   categoria de "a OBM não publica escola" (docs/41 §5.1): `cidade_informada`
   sai sempre `""` pra `prova_nome="OBQ"`. A OBQ Jr publica cidade/município
   nos três anos raspados.
5. **A coluna "Série" da tabela da OBQ 2024 mistura texto de OUTRA
   modalidade** (`"OBQjr - MODALIDADE A"` aparece em vez de uma série normal
   em algumas linhas) — por isso este scraper NUNCA lê série pra decidir
   nível: a Modalidade (A/B) vem do cabeçalho de PÁGINA
   ("MODALIDADE [AB]", repetido em toda página, inclusive dentro do PDF
   combinado de 2024), nunca da coluna.
6. **Menos de 2022/2024/2025 confirmam o ano DENTRO do PDF que os outros
   pipelines deste projeto** — a OBQ Jr 2023 não menciona "2023" em lugar
   nenhum do documento (nem no cabeçalho, nem no rodapé), e a 2022 só
   menciona o ano numa linha de título que aparece MEIO da extração da
   tabela, fora de ordem. `_ano_confere` faz um teste best-effort (a string
   do ano aparece em algum lugar do texto?) e AVISA quando não confirma, mas
   não bloqueia — bloquear pela ausência quebraria a OBQ Jr 2023 inteira por
   uma limitação da fonte, não um risco real de pegar o ano errado (a URL
   já foi curada por ano, olhando o conteúdo, em `_DOCUMENTOS_OBQ_JR`).
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

DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# ano -> [(url, formato)], formato em {"texto", "tabela"} — curado olhando
# cada PDF de verdade (docstring do módulo, seção "Anos confirmados").
_DOCUMENTOS_OBQ: dict[int, list[tuple[str, str]]] = {
    2022: [
        ("https://obquimica.org/storage/olympiads/result-files/Resultado_OBQ_2022_Fase_III.pdf", "texto"),
    ],
    2024: [
        (
            "https://obquimica.org/storage/olympiads/result-files/Resultado OBQ 2024 v11 RESULTADO FINAL.pdf",
            "tabela",
        ),
    ],
    2025: [
        ("https://obquimica.org/storage/olympiads/result-files/01KN25Y5ETSD2MSX5DADSKP3QG.pdf", "tabela"),
        ("https://obquimica.org/storage/olympiads/result-files/01KN25YR6NS2SPZM3X7FJ6S5B8.pdf", "tabela"),
    ],
}

_DOCUMENTOS_OBQ_JR: dict[int, list[tuple[str, str]]] = {
    2021: [
        ("https://obquimica.org/storage/olympiads/result-files/Resultado_OBQjr2021_Site.pdf", "texto"),
    ],
    2022: [
        ("https://obquimica.org/storage/olympiads/result-files/Resultado da OBQJr 2022.pdf", "tabela"),
    ],
    2023: [
        ("https://obquimica.org/storage/olympiads/result-files/OBQJr 2023 Lista de Medalhistas (1).pdf", "tabela"),
    ],
}

# Modalidade A: 1º/2º ano EM (série 10-11). Modalidade B: 3º ano EM + 4º ano
# técnico — este último não tem número de série no padrão EF/EM do projeto,
# então a faixa cobre só a parte que dá pra descrever sem inventar precisão
# (mesmo cuidado do docs/41 §3): 12-12.
_NIVEL_OBQ: dict[str, tuple[str, int, int]] = {
    "A": ("Modalidade A", 10, 11),
    "B": ("Modalidade B", 12, 12),
}

_NOME_ESTADO_PARA_UF: dict[str, str] = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM", "BAHIA": "BA",
    "CEARA": "CE", "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES", "GOIAS": "GO",
    "MARANHAO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR",
    "PERNAMBUCO": "PE", "PIAUI": "PI", "RIO DE JANEIRO": "RJ",
    "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO",
    "RORAIMA": "RR", "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}

_UFS_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def _uf(texto: str) -> str:
    """Aceita sigla de 2 letras OU nome do estado por extenso (docstring do
    módulo, achado 3) — nunca None: string vazia quando não reconhece. Só
    aceita sigla que é UF de verdade (contra `_UFS_VALIDAS`), não qualquer
    par de letras — mesmo cuidado do achado abaixo em `_medalha_secao`."""
    t = texto.strip().upper()
    if t in _UFS_VALIDAS:
        return t
    return _NOME_ESTADO_PARA_UF.get(_sem_acento(t), "")


_PADRAO_NAO_NOME = re.compile(
    r"\b(Centro|Col[eé]gio|Colegio|Col\.|Escola|Esc\.?|Emef|Emei|Ceei|Cei|Educand[aá]rio|"
    r"Instituto|Curso|Ensino|Funda[cç][aã]o|Universit[aá]rio|Educacional|Ano|Anbeas|"
    r"Faculdade|Sociedade|Unid(ade)?)\b",
    re.IGNORECASE,
)


def _parece_nome_de_pessoa(texto: str) -> bool:
    """Filtro defensivo pro formato "texto" (docstring do módulo, seção
    "achados"): quando a ESCOLA de um registro tem nome comprido e quebra em
    duas linhas físicas no PDF, a âncora (que sempre lê nome/escola pelas 2
    linhas imediatamente antes do Estado/UF) desliza uma posição e
    "nome_informado" vira a SEGUNDA metade do nome da escola, não uma pessoa
    — achado rodando de verdade contra a OBQ 2022 e a OBQ Jr 2021 ("Centro de
    Atividades Jones dos" virando nome, "Santos Neves" virando escola). Sem
    um nome de aluno de verdade não tem quem contatar, então o registro é
    descartado — melhor perder a linha do que gravar identidade errada
    (mesma régua do `notas_por_materia` em efomm.py: granularidade a menos é
    melhor que granularidade errada).

    Não é exaustivo — nome de instituição tem variedade grande demais de
    abreviação (achado rodando: "Col. Militar Corpo de Bombeiro -" e outras
    formas abreviadas escapam da lista de palavras) — por isso os dois
    últimos testes (termina em hífen/aspas, começa com conectivo minúsculo)
    pegam a FORMA do fragmento cortado, não o vocabulário."""
    partes = texto.split()
    if len(partes) < 2:
        return False
    if texto.rstrip().endswith(("-", '"')):
        return False
    if partes[0][0].islower():
        return False
    return not _PADRAO_NAO_NOME.search(texto)


_MEDALHAS_CANONICAS: dict[str, str] = {
    "OURO": "Ouro",
    "OIRO": "Ouro",
    "PRATA": "Prata",
    "BRONZE": "Bronze",
    "MENCAO HONROSA": "Menção Honrosa",
    "HONRA": "Menção Honrosa",
    "DEMAIS CLASSIFICADOS": "Demais Classificados",
    "DEMAIS PARTICIPANTES": "Demais Classificados",
}


def _medalha_secao(linha: str) -> str | None:
    """Só reconhece uma linha que é INTEIRA E SÓ o nome de uma faixa —
    igualdade exata (tolerando espaço duplo e acento), nunca substring.

    ⚠️ Achado rodando de verdade contra a OBQ Jr 2021: "Prata" e "Ouro" são
    sobrenome real de aluno de verdade ("Arthur Braga Prata", "Monica
    Vitoria de Carvalho Prata"), e "Lagoa da Prata"/"Ouro Fino" são cidade
    real (MG). Uma versão anterior deste parser casava por substring (útil
    pra célula de tabela isolada, onde a única coisa que aparece É a
    medalha) e, aplicada linha a linha sobre o texto inteiro, qualquer aluno
    com esse sobrenome ou cidade reiniciava a "medalha atual" pro resto do
    documento — inflou "Prata" de ~400 pra quase 4 mil registros antes de
    virar `resultado` errado em tudo que vinha depois, silenciosamente."""
    t = re.sub(r"\s+", " ", _sem_acento(linha).upper().strip())
    return _MEDALHAS_CANONICAS.get(t)


def _normalizar_medalha(texto: str) -> str | None:
    """Pra célula de TABELA isolada (marcador de seção com 1 célula só
    preenchida, ou coluna "medalha" inline por linha) — aqui substring é
    seguro porque o valor da célula NUNCA é nome de aluno/cidade, só rótulo
    de faixa. Para texto livre linha a linha, use `_medalha_secao`."""
    t = _sem_acento(texto).upper().strip()
    if not t:
        return None
    if t in ("OURO", "OIRO"):
        return "Ouro"
    if "PRATA" in t:
        return "Prata"
    if "BRONZE" in t:
        return "Bronze"
    if "MENCAO" in t or "HONRA" in t:
        return "Menção Honrosa"
    if "DEMAIS" in t:
        return "Demais Classificados"
    return None


def _ano_confere(texto: str, ano: int) -> bool:
    return str(ano) in texto


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


def _texto_pagina(pagina: pymupdf.Page) -> str:
    """`get_text` puro, mas trocando `\\x00` por "é" — achado real na OBQ Jr
    2021: a fonte embutida do PDF não mapeia o glifo de "é"/"É" pra um
    caractere de verdade, e o PyMuPDF devolve NUL byte no lugar ("Mois\\x00s"
    em vez de "Moisés", "\\x00rica" em vez de "Érica", em dezenas de nomes).
    NUL byte também é um problema à parte: nem chega a virar linha no banco —
    o Postgres/PostgREST recusa qualquer texto com `\\u0000` embutido
    ("unsupported Unicode escape sequence"), e o processo de importação
    inteiro falhava por causa de UM nome. "é" é a letra que falta em
    praticamente todo caso observado (nunca dá pra saber com certeza se era
    maiúscula ou minúscula a partir do NUL sozinho); fica documentado aqui
    como aproximação, não certeza."""
    return pagina.get_text("text").replace("\x00", "é")


def _baixar(url: str) -> bytes:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.content


def _parsear_obq_texto(conteudo: bytes, ano: int, url: str) -> list[Registro]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    linhas: list[str] = []
    for pagina in doc:
        linhas.extend(l.strip() for l in _texto_pagina(pagina).split("\n") if l.strip())

    if not _ano_confere("\n".join(linhas), ano):
        print(f"    aviso: {url} não confirma {ano} no texto — seguindo pela curadoria mesmo assim", file=sys.stderr)

    modalidade_atual: str | None = None
    medalha_atual: str | None = None
    estado_por_indice: list[tuple[str | None, str | None]] = []
    for linha in linhas:
        m_mod = re.search(r"Modalidade\s+([AB])\b", linha, re.IGNORECASE)
        if m_mod:
            modalidade_atual = m_mod.group(1).upper()
            medalha_atual = None
        nova_medalha = _medalha_secao(linha)
        if nova_medalha:
            medalha_atual = nova_medalha
        estado_por_indice.append((modalidade_atual, medalha_atual))

    registros: list[Registro] = []
    for i in range(2, len(linhas)):
        uf = _uf(linhas[i])
        if not uf:
            continue
        modalidade, medalha = estado_por_indice[i]
        if medalha is None:
            continue
        escola, nome = linhas[i - 1], linhas[i - 2]
        if not nome or not escola or not _parece_nome_de_pessoa(nome):
            continue
        nivel_texto, serie_min, serie_max = _NIVEL_OBQ.get(modalidade or "", ("", None, None))
        registros.append(
            Registro(
                prova_nome="OBQ",
                ano=ano,
                nivel_texto=nivel_texto,
                serie_referencia_min=serie_min,
                serie_referencia_max=serie_max,
                resultado=medalha,
                nome_informado=nome,
                escola_informada=escola,
                cidade_informada="",
                uf_informada=uf,
                fonte_url=url,
            )
        )
    return registros


def _linhas_de_tabela(pagina: pymupdf.Page) -> list[list[str]]:
    saida: list[list[str]] = []
    for tabela in pagina.find_tables().tables:
        for linha in tabela.extract():
            saida.append([(c or "").strip() for c in linha])
    return saida


def _parsear_obq_tabela(conteudo: bytes, ano: int, url: str) -> list[Registro]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    registros: list[Registro] = []
    ano_confirmado_em_alguma_pagina = False

    for pagina in doc:
        texto_pagina = _texto_pagina(pagina)
        if _ano_confere(texto_pagina, ano):
            ano_confirmado_em_alguma_pagina = True

        m_mod = re.search(r"MODALIDADE\s*([AB])", texto_pagina, re.IGNORECASE)
        modalidade = m_mod.group(1).upper() if m_mod else None
        nivel_texto, serie_min, serie_max = _NIVEL_OBQ.get(modalidade or "", ("", None, None))

        medalha_atual: str | None = None
        for celulas in _linhas_de_tabela(pagina):
            preenchidas = [c for c in celulas if c]
            if not preenchidas:
                continue
            if len(preenchidas) == 1:
                medalha = _normalizar_medalha(preenchidas[0])
                if medalha:
                    medalha_atual = medalha
                continue
            if celulas[0].rstrip("*") == "Estado" or len(celulas) < 6:
                continue
            if medalha_atual is None:
                continue
            estado, nome, _serie, escola, _nota, _escore = celulas[:6]
            if not nome or not escola:
                continue
            registros.append(
                Registro(
                    prova_nome="OBQ",
                    ano=ano,
                    nivel_texto=nivel_texto,
                    serie_referencia_min=serie_min,
                    serie_referencia_max=serie_max,
                    resultado=medalha_atual,
                    nome_informado=nome,
                    escola_informada=escola,
                    cidade_informada="",
                    uf_informada=_uf(estado),
                    fonte_url=url,
                )
            )

    if not ano_confirmado_em_alguma_pagina:
        print(f"    aviso: {url} não confirma {ano} em nenhuma página — seguindo pela curadoria mesmo assim", file=sys.stderr)
    return registros


def _parsear_obqjr_texto(conteudo: bytes, ano: int, url: str) -> list[Registro]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    linhas: list[str] = []
    for pagina in doc:
        linhas.extend(l.strip() for l in _texto_pagina(pagina).split("\n") if l.strip())

    if not _ano_confere("\n".join(linhas), ano):
        print(f"    aviso: {url} não confirma {ano} no texto — seguindo pela curadoria mesmo assim", file=sys.stderr)

    medalha_atual: str | None = None
    medalha_por_indice: list[str | None] = []
    for linha in linhas:
        nova = _medalha_secao(linha)
        if nova:
            medalha_atual = nova
        medalha_por_indice.append(medalha_atual)

    registros: list[Registro] = []
    for i in range(2, len(linhas) - 1):
        if linhas[i] not in _UFS_VALIDAS:
            continue
        medalha = medalha_por_indice[i]
        if medalha is None:
            continue
        escola, nome = linhas[i - 1], linhas[i - 2]
        cidade = linhas[i + 1]
        if not nome or not escola or not _parece_nome_de_pessoa(nome):
            continue
        registros.append(
            Registro(
                prova_nome="OBQ Jr",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=6,
                serie_referencia_max=9,
                resultado=medalha,
                nome_informado=nome,
                escola_informada=escola,
                cidade_informada=cidade,
                uf_informada=linhas[i],
                fonte_url=url,
            )
        )
    return registros


def _parsear_obqjr_tabela(conteudo: bytes, ano: int, url: str) -> list[Registro]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    registros: list[Registro] = []
    ano_confirmado_em_alguma_pagina = False

    for pagina in doc:
        if _ano_confere(_texto_pagina(pagina), ano):
            ano_confirmado_em_alguma_pagina = True

        for celulas in _linhas_de_tabela(pagina):
            if not celulas:
                continue
            medalha = _normalizar_medalha(celulas[0])
            if medalha is None:
                continue  # cabeçalho ("MEDALHA"/"PREMIAÇÃO") ou linha não reconhecida
            if len(celulas) == 5:
                _, nome, uf, cidade, escola = celulas
            elif len(celulas) == 6:
                _, nome, _serie, escola, uf, cidade = celulas
            else:
                print(f"    aviso: linha com {len(celulas)} colunas, formato inesperado: {celulas!r}", file=sys.stderr)
                continue
            if not nome or not escola:
                continue
            registros.append(
                Registro(
                    prova_nome="OBQ Jr",
                    ano=ano,
                    nivel_texto="",
                    serie_referencia_min=6,
                    serie_referencia_max=9,
                    resultado=medalha,
                    nome_informado=nome,
                    escola_informada=escola,
                    cidade_informada=cidade,
                    uf_informada=_uf(uf),
                    fonte_url=url,
                )
            )

    if not ano_confirmado_em_alguma_pagina:
        print(f"    aviso: {url} não confirma {ano} em nenhuma página — seguindo pela curadoria mesmo assim", file=sys.stderr)
    return registros


_PARSERS = {
    ("OBQ", "texto"): _parsear_obq_texto,
    ("OBQ", "tabela"): _parsear_obq_tabela,
    ("OBQ Jr", "texto"): _parsear_obqjr_texto,
    ("OBQ Jr", "tabela"): _parsear_obqjr_tabela,
}


def raspar_ano(prova_nome: str, ano: int, documentos: dict[int, list[tuple[str, str]]]) -> list[Registro]:
    itens = documentos.get(ano)
    if not itens:
        print(f"  {prova_nome} {ano}: sem documento curado (ver _DOCUMENTOS_{'OBQ_JR' if prova_nome == 'OBQ Jr' else 'OBQ'})", file=sys.stderr)
        return []

    registros: list[Registro] = []
    for url, formato in itens:
        try:
            conteudo = _baixar(url)
        except requests.HTTPError as e:
            print(f"    falhou: {url}: {e}", file=sys.stderr)
            continue
        parser = _PARSERS[(prova_nome, formato)]
        novos = parser(conteudo, ano, url)
        registros.extend(novos)
        print(f"    {url.rsplit('/', 1)[-1]}: {len(novos)} registros", file=sys.stderr)
    return registros


def _sem_duplicata_de_chave(registros: list[Registro]) -> list[Registro]:
    """Deduplica pela MESMA chave do índice único da 0057
    (prova, ano, nivel_texto, nome, escola, resultado) — achado real, não
    hipotético: a OBQ 2022 repete "Gustavo Zanete Alencar / Colegio Harmonia"
    inteiro, com o mesmo resultado, 21 linhas adiante no PDF de origem (texto
    duplicado na fonte, conferido abrindo o PDF de verdade). Sem isso o
    importador quebra com "ON CONFLICT DO UPDATE cannot affect row a second
    time" — o mesmo upsert em lote não tolera duas linhas iguais no msmo
    lote."""
    vistos: set[tuple] = set()
    saida = []
    for r in registros:
        chave = (r.ano, r.nivel_texto, r.nome_informado, r.escola_informada, r.resultado)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(r)
    return saida


def _gravar(prova_arquivo: str, ano: int, registros: list[Registro]) -> None:
    registros = _sem_duplicata_de_chave(registros)
    if not registros:
        print("  0 registros — algo mudou na fonte, confira antes de importar", file=sys.stderr)
        return
    destino = DIR_DADOS / f"{prova_arquivo}_{ano}.json"
    destino.write_text(
        json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  {prova_arquivo} {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--anos", type=int, nargs="+", required=True, help="Anos a raspar")
    parser.add_argument(
        "--fonte", choices=["obq", "obqjr", "ambas"], default="ambas",
        help="obq = só OBQ, obqjr = só OBQ Jr, ambas (default)",
    )
    args = parser.parse_args()

    DIR_DADOS.mkdir(exist_ok=True)

    for ano in args.anos:
        if args.fonte in ("obq", "ambas"):
            print(f"OBQ {ano} — raspando...", file=sys.stderr)
            _gravar("obq", ano, raspar_ano("OBQ", ano, _DOCUMENTOS_OBQ))
        if args.fonte in ("obqjr", "ambas"):
            print(f"OBQ Jr {ano} — raspando...", file=sys.stderr)
            _gravar("obqjr", ano, raspar_ano("OBQ Jr", ano, _DOCUMENTOS_OBQ_JR))


if __name__ == "__main__":
    main()
