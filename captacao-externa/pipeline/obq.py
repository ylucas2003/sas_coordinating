"""Raspa os resultados da OBQ (Olimpíada Brasileira de Química) e da OBQ Jr
(Olimpíada Brasileira de Química Júnior) — duas provas distintas, do mesmo
programa (PNOQ/UFC+UFPI), com público-alvo diferente (OBQ é médio, OBQ Jr é
6º-9º fundamental) — e grava um JSON cru POR PROVA e por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/obq.py --anos 2018 2019 2020 2021 2022 2024 2025 --fonte obq
    ./.venv/bin/python pipeline/obq.py --anos 2018 2019 2020 2021 2022 2023 --fonte obqjr
    ./.venv/bin/python pipeline/obq.py --anos 2022 2023 2024 2025 --fonte ambas

Grava dados/obq_{ano}.json e dados/obqjr_{ano}.json — arquivos separados
porque são `prova_externa` separadas (docs/41 §6, item 2), mesmo os dois
saindo deste único script.

## Primeira fonte do projeto em PDF — e o gerador mudou QUATRO vezes

obquimica.org/olimpiada/... lista um PDF de resultado por ano, mas o gerador
do PDF mudou várias vezes na década — `_DOCUMENTOS_OBQ`/`_DOCUMENTOS_OBQ_JR`
curam qual PDF usa qual formato, ano a ano (mesma régua do IME/EFOMM/Escola
Naval: nada de adivinhar em tempo de execução). Quatro formatos:

- **"tabela"**: PDF gerado a partir de planilha, com bordas de célula reais
  que `pagina.find_tables()` do PyMuPDF lê direto — OBQ 2024/2025, OBQ Jr
  2022/2023. A medalha vem INLINE, uma célula própria em cada linha de
  dado (não um marcador de seção à parte).
- **"tabela_marcador"**: mesma extração por `find_tables()`, mas a medalha
  vem de uma linha-MARCADOR de seção (só uma célula preenchida — "OURO",
  "PRATA"...) que vale pras linhas seguintes até a próxima trocar — OBQ
  2021, OBQ Jr 2018/2020. Compartilha o gerador `_linhas_tabela_com_marcador`
  com o formato "tabela" da OBQ adulta (ver bug crítico abaixo).
- **"texto"**: PDF sem tabela detectável (`find_tables()` devolve zero, ou
  devolve algo mas inútil — ver achado 7) — OBQ 2020/2022, OBQ Jr
  2019/2021. Cada registro é um bloco curto de linhas consecutivas (nome,
  escola, estado/UF[, cidade], série, nota, escore); em vez de filtrar
  cabeçalho/rodapé linha por linha (frágil — o texto varia demais entre
  documentos), o parser ANCORA no campo ESTADO/UF: é o único campo com um
  conjunto FECHADO e conhecido de valores (27 unidades federativas), então
  uma linha que bate exatamente com uma delas (por extenso, sem se importar
  com acento — "Espirito Santo" aparece sem acento de verdade na fonte
  2022 — ou sigla de 2 letras) nunca é cabeçalho, título ou nome de aluno.
  Nome e escola ficam nas 1-2 linhas ANTES da âncora; cidade (quando existe)
  e nota/escore ficam DEPOIS, sem precisar ser lidos.

  ⚠️ **Nota/escore não são âncora confiável**: a primeira versão deste
  parser usava o par (nota, escore) — duas linhas seguidas só com número —
  como âncora, e isso PERDIA inteiras as faixas de "Menção Honrosa" e
  "Demais Classificados"/"Demais Participantes": essas faixas às vezes
  publicam só UMA nota (sem escore) ou nenhuma (só "NÃO INF." em vez de
  série), porque não competem mais por posição. Achado rodando contra a OBQ
  2022 (226 registros viravam só 138, zero Menção Honrosa) e a OBQ Jr 2021.
- **"texto2"**: mesmo princípio de âncora do "texto", mas a ORDEM das
  linhas ao redor muda — OBQ 2018/2019: nome, cidade, UF(sigla), e só
  DEPOIS escola (no "texto", escola vem ANTES da âncora).

## Anos confirmados, e por que os outros ficaram de fora

**OBQ**: 2018-2022, 2024, 2025 — só **2023 fica de fora**: a seção de
resultados desse ano só publica o PDF da Fase IV (laboratório, já filtrado
pros medalhistas de Ouro da Modalidade A), sem coluna de medalha nenhuma; o
PDF de Fase III (que teria Ouro/Prata/Bronze/Menção) não está publicado
nessa seção — confirmado abrindo a página, não suposição.

**OBQ Jr**: 2018-2023. **2024 e 2025 ficam de fora**: 2024
(`Estudantes X Notas`) só publica código do aluno + nome + classificação —
SEM escola nem UF, não serve pra identidade (mesma categoria do "Não
Aprovados" do IME, §6.2.1 do plano). 2025 publica seis PDFs fragmentados
por série (6ª-9ª) que são listas de CLASSIFICADOS pra fase seguinte — sem
medalha — mais dois PDFs de medalha só pra ESCOLA PÚBLICA por UF; não achei
o PDF de medalha geral (pública+privada) da OBQ Jr 2025.

## Achados que não davam pra prever sem abrir o PDF de verdade

1. **"OIRO"** — a OBQ 2025 Modalidade B (o PDF cujo NOME do arquivo é um
   hash sem relação com o conteúdo — a modalidade real só se confirma
   lendo "MODALIDADE B" no cabeçalho de cada página, nunca pelo nome do
   link) escreve a medalha de Ouro como "OIRO" — typo real da fonte, não
   erro de extração. Tratado como sinônimo de "OURO".
2. **"HONRA"** — no PDF combinado da OBQ 2024, o marcador de Menção
   Honrosa quebra exatamente na virada de página e só "HONRA" sobrevive na
   célula. Tratado como sinônimo de "Menção Honrosa".
3. **Marcador com uma letra por célula** — "O U R O", "P R A T A",
   "B R O N Z E" — na OBQ 2018/2020 e na OBQ Jr 2018/2020, efeito provável
   de uma fonte de cabeçalho com tracking largo no PDF de origem.
   `_medalha_secao`/`_normalizar_medalha` tiram TODO espaço antes de
   comparar (não só duplicado), sem criar ambiguidade nova.
4. **Estado vem ora como SIGLA, ora por EXTENSO** — OBQ Jr 2018/2020/2021/
   2022 dão UF de 2 letras; OBQ Jr 2019/2023 e a OBQ inteira dão o nome do
   estado por extenso, maiúsculo, sem padrão de acentuação confiável.
   `_uf()` aceita as duas formas.
5. **A OBQ (adulto) não publica cidade, só Estado** em nenhum dos anos
   raspados — achado real, mesma categoria de "a OBM não publica escola"
   (docs/41 §5.1): `cidade_informada` sai sempre `""` pra `prova_nome="OBQ"`.
   A OBQ Jr publica cidade/município em todos os anos raspados.
6. **A coluna "Série" da tabela da OBQ 2024 mistura texto de OUTRA
   modalidade** (`"OBQjr - MODALIDADE A"` em vez de uma série normal em
   algumas linhas) — por isso este scraper NUNCA lê nenhuma coluna de
   série/pontos/nota pra decidir nada; nome/escola/estado vêm sempre do
   CABEÇALHO da tabela (`_mapa_colunas`), nunca de posição fixa — a OBQ
   sozinha já publicou pelo menos três ordens de coluna diferentes em
   formato tabela.
7. **"Tabela" só de aparência, em dois anos por dois motivos diferentes** —
   a OBQ 2020 faz `find_tables()` devolver "1 tabela", mas o conteúdo sai
   em blocos de texto colados numa única célula (inútil); a OBQ 2021 faz
   `find_tables()` devolver só a linha de CABEÇALHO, nenhuma linha de dado
   (a grade real não é detectável pelo PyMuPDF nesse documento específico).
   As duas viraram formato "texto"/"texto2" — o texto puro (`get_text`) sai
   limpo nos dois casos, ao contrário da tabela "detectada".
8. **OBQ Jr 2020 tem uma coluna fantasma entre nome e escola** — o
   cabeçalho chega como `['Nome Do Aluno', 'do', 'Escola do Aluno', 'UF',
   ...]` (a palavra "do" de "Escola do Aluno" vira cabeçalho de coluna
   própria, artefato de como o PDF original foi gerado), e toda linha de
   dado tem um "A"/"a" solto ali — não parece modalidade (só um valor
   aparece no documento inteiro), mais um resíduo administrativo sem
   significado pro pipeline. `_mapa_colunas`, por procurar
   nome/escola/estado pelo TEXTO do cabeçalho (não por posição), ignora
   essa coluna sozinho.
9. ⚠️ **Bug crítico, achado em 23/09/2026, já tinha ido pra produção em
   22/09/2026**: `_parsear_obq_tabela` reiniciava a medalha (e a
   modalidade) vigente no topo de CADA PÁGINA — seguro só se o marcador de
   seção se repete em toda página, suposição nunca verificada linha a
   linha. A OBQ 2024 tem 34 páginas e só 2 têm marcador de medalha; as
   outras 32 perdiam TODAS as linhas de dado em silêncio. Uma segunda
   camada do MESMO bug sobreviveu à primeira correção: mesmo persistindo o
   estado entre páginas, o código reiniciava a medalha toda vez que o
   regex de modalidade CASAVA de novo — e "MODALIDADE A"/"MODALIDADE B" é
   cabeçalho CORRIDO, repete em toda página. A correção final só reinicia
   a medalha numa mudança de VALOR de modalidade, nunca numa re-ocorrência
   do mesmo valor. Resultado: OBQ 2024 foi de 195 pra 1.343
   `conquista_externa` (quase 7×) — detalhe completo em docs/41 §13.1.

   A OBI **não** tem esse bug — cada linha da tabela HTML dela já carrega
   a própria medalha (imagem ou "HM") na primeira célula, sem estado que
   precise sobreviver entre nada, e cada modalidade/nível é uma página HTML
   só, sem "virar de página" no meio de uma tabela.
10. **Menos de 2022/2024/2025 confirmam o ano DENTRO do PDF que os outros
    pipelines deste projeto** — a OBQ Jr 2023 não menciona "2023" em lugar
    nenhum do documento, e a 2022 só menciona o ano fora de ordem no meio
    da extração de tabela. `_ano_confere` faz um teste best-effort e AVISA
    quando não confirma, mas não bloqueia — bloquear pela ausência
    quebraria documentos inteiros por uma limitação da fonte, não um risco
    real de pegar o ano errado (a URL já foi curada por ano olhando o
    conteúdo).
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
    2018: [
        ("https://obquimica.org/storage/olympiads/result-files/Resultado OBQ2018 Mod A e B.pdf", "texto2"),
    ],
    2019: [
        (
            "https://obquimica.org/storage/olympiads/result-files/ResultadoOBQ2019 Mod. A e B para site.pdf",
            "texto2",
        ),
    ],
    2020: [
        ("https://obquimica.org/storage/olympiads/result-files/ResultadoOBQ2020 Fase III.pdf", "texto"),
    ],
    2021: [
        ("https://obquimica.org/storage/olympiads/result-files/Resultado_OBQ_2021_FASE III Site.pdf", "texto"),
    ],
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
    2018: [
        ("https://obquimica.org/storage/olympiads/result-files/Resultado OBQjr 2018.pdf", "tabela_marcador"),
    ],
    2019: [
        ("https://obquimica.org/storage/olympiads/result-files/ResultadoFinalOBQjunior.pdf", "texto"),
    ],
    2020: [
        (
            "https://obquimica.org/storage/olympiads/result-files/Resultado OBQjr 2020 Fase II site.pdf",
            "tabela_marcador",
        ),
    ],
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
    "MENCAOHONROSA": "Menção Honrosa",
    "HONRA": "Menção Honrosa",
    "DEMAISCLASSIFICADOS": "Demais Classificados",
    "DEMAISPARTICIPANTES": "Demais Classificados",
}


def _medalha_secao(linha: str) -> str | None:
    """Só reconhece uma linha que é INTEIRA E SÓ o nome de uma faixa —
    igualdade exata (tirando TODO espaço e acento), nunca substring.

    ⚠️ Achado rodando de verdade contra a OBQ Jr 2021: "Prata" e "Ouro" são
    sobrenome real de aluno de verdade ("Arthur Braga Prata", "Monica
    Vitoria de Carvalho Prata"), e "Lagoa da Prata"/"Ouro Fino" são cidade
    real (MG). Uma versão anterior deste parser casava por substring (útil
    pra célula de tabela isolada, onde a única coisa que aparece É a
    medalha) e, aplicada linha a linha sobre o texto inteiro, qualquer aluno
    com esse sobrenome ou cidade reiniciava a "medalha atual" pro resto do
    documento — inflou "Prata" de ~400 pra quase 4 mil registros antes de
    virar `resultado` errado em tudo que vinha depois, silenciosamente.

    ⚠️ Tira TODO espaço, não só duplicado — achado na OBQ/OBQ Jr de
    2018/2020: a fonte escreve a medalha com uma letra por célula/token
    ("O U R O", "P R A T A", "B R O N Z E"), provavelmente efeito de uma
    fonte de cabeçalho com tracking largo no PDF original. Colapsar espaço
    duplo pra um só não resolve isso; só remover todo espaço resolve, e não
    tem ambiguidade nova nisso (nenhuma medalha vira outra ao perder os
    espaços)."""
    t = re.sub(r"\s+", "", _sem_acento(linha).upper())
    return _MEDALHAS_CANONICAS.get(t)


def _normalizar_medalha(texto: str) -> str | None:
    """Pra célula de TABELA isolada (marcador de seção com 1 célula só
    preenchida, ou coluna "medalha" inline por linha) — aqui substring é
    seguro porque o valor da célula NUNCA é nome de aluno/cidade, só rótulo
    de faixa. Para texto livre linha a linha, use `_medalha_secao`. Mesmo
    cuidado de tirar TODO espaço (não só colapsar) — ver docstring de
    `_medalha_secao`."""
    t = re.sub(r"\s+", "", _sem_acento(texto).upper())
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


def _parsear_obq_texto2(conteudo: bytes, ano: int, url: str) -> list[Registro]:
    """Variante 2018/2019: mesmo princípio de âncora do `_parsear_obq_texto`
    (Estado/UF é o único campo de conjunto fechado), mas a ORDEM das linhas
    ao redor da âncora é outra — UF vem como SIGLA de 2 letras (não Estado
    por extenso), e a sequência é nome, cidade, UF, escola: a escola fica
    DEPOIS da âncora, não antes. Achado abrindo os dois PDFs de verdade —
    nenhuma suposição de que "o formato de 2022 vale pros anos anteriores"."""
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
    for i in range(2, len(linhas) - 1):
        if linhas[i] not in _UFS_VALIDAS:
            continue
        modalidade, medalha = estado_por_indice[i]
        if medalha is None:
            continue
        nome, cidade = linhas[i - 2], linhas[i - 1]
        escola = linhas[i + 1]
        if (
            not nome
            or not escola
            or not _parece_nome_de_pessoa(nome)
            or re.match(r"^[\d,]+$", escola)
        ):
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
                cidade_informada=cidade,
                uf_informada=linhas[i],
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


def _mapa_colunas(celulas: list[str]) -> dict[str, int]:
    """Índice de nome/escola/estado/cidade a partir do CABEÇALHO de verdade
    da tabela, não posição fixa — achado rodando contra 2020/2021/2024/2025:
    a OBQ sozinha já publicou pelo menos três ORDENS de coluna diferentes
    (`Estado, Nome, Série, Escola, Nota, Escore` em 2024/2025; `Nome, Escola,
    Estado, Escore` em 2021; `Nome, Escola, Estado, Pontuação, Escore` em
    2020) — fatiar por posição (`celulas[:6]`) supõe uma ordem só e quebra
    silenciosamente nas outras. `\\bESTADO\\b`/`\\bESCOLA\\b`/`\\bNOME\\b`
    usam fronteira de palavra de propósito: "Colégio ESTADUAL" contém
    "ESTADO" como substring solto, e pegaria a coluna errada sem a
    fronteira."""
    mapa: dict[str, int] = {}
    for idx, cel in enumerate(celulas):
        c = _sem_acento(cel or "").upper()
        if re.search(r"\bESTADO\b", c) or c.strip().rstrip("*") == "UF":
            mapa.setdefault("estado", idx)
        elif re.search(r"\bESCOLA\b", c):
            mapa.setdefault("escola", idx)
        elif re.search(r"\bCIDADE\b", c):
            mapa.setdefault("cidade", idx)
        elif re.search(r"\bNOME\b", c):
            mapa.setdefault("nome", idx)
    return mapa


def _linhas_tabela_com_marcador(doc: pymupdf.Document, ano: int, url: str):
    """Gera (modalidade_atual, medalha_atual, campos) pra cada linha de DADO
    de um PDF em tabela cuja medalha vem de uma linha-MARCADOR de seção (só
    uma célula preenchida) — o padrão da OBQ inteira e de parte da OBQ Jr
    (2018, 2020). `campos` é um dict com "nome"/"escola"/"uf" sempre, e
    "cidade" quando a própria tabela publica.

    ⚠️ Marcador de medalha e de modalidade PERSISTEM entre páginas — bug real
    corrigido aqui, já tinha ido pra produção: a versão anterior reiniciava
    `medalha_atual`/`modalidade` no topo de CADA página, e a OBQ 2024/2025
    só repete "MODALIDADE [AB]"/"OURO" na página em que a faixa COMEÇA, não
    em toda página em que ela continua (confirmado contando de verdade:
    2024 tem 34 páginas e só 2 delas têm uma linha-marcador) — as páginas
    "sem marcador" tinham TODAS as linhas de dado descartadas em silêncio
    (`if medalha_atual is None: continue`), porque o estado resetava pra
    `None` antes de qualquer linha ser lida. Persistir o estado corrige a
    subcontagem sem custo nenhum: nada muda pra um documento onde o
    marcador REALMENTE se repete a cada página."""
    modalidade: str | None = None
    medalha_atual: str | None = None
    mapa_colunas: dict[str, int] | None = None
    ano_confirmado = False

    for pagina in doc:
        texto_pagina = _texto_pagina(pagina)
        if _ano_confere(texto_pagina, ano):
            ano_confirmado = True

        m_mod = re.search(r"MODALIDADE\s*([AB])", texto_pagina, re.IGNORECASE)
        if m_mod:
            nova_modalidade = m_mod.group(1).upper()
            if nova_modalidade != modalidade:
                # só reinicia a medalha numa mudança de VERDADE — "MODALIDADE
                # A/B" é cabeçalho corrido, repete em toda página (achado
                # rodando: as 34 páginas da OBQ 2024 têm a MESMA modalidade
                # no topo da página inteira). Resetar em toda RE-ocorrência
                # (não só na troca) reproduzia o mesmo bug da página por
                # outro caminho — a medalha nunca sobrevivia de uma página
                # pra outra mesmo com o estado persistindo fora do loop.
                medalha_atual = None
            modalidade = nova_modalidade

        for celulas in _linhas_de_tabela(pagina):
            preenchidas = [c for c in celulas if c]
            if not preenchidas:
                continue
            if len(preenchidas) == 1:
                medalha = _normalizar_medalha(preenchidas[0])
                if medalha:
                    medalha_atual = medalha
                continue

            candidato_mapa = _mapa_colunas(celulas)
            if len(candidato_mapa) >= 3:
                mapa_colunas = candidato_mapa
                continue
            if mapa_colunas is None or medalha_atual is None:
                continue

            def campo(chave: str, celulas: list[str] = celulas, mapa: dict[str, int] = mapa_colunas) -> str:
                idx = mapa.get(chave)
                if idx is None or idx >= len(celulas):
                    return ""
                return celulas[idx] or ""

            uf = _uf(campo("estado"))
            if not uf:
                continue
            nome = campo("nome").strip()
            escola = campo("escola").strip()
            if not nome or not escola:
                continue
            yield modalidade, medalha_atual, {"nome": nome, "escola": escola, "uf": uf, "cidade": campo("cidade").strip()}

    if not ano_confirmado:
        print(f"    aviso: {url} não confirma {ano} em nenhuma página — seguindo pela curadoria mesmo assim", file=sys.stderr)


def _parsear_obq_tabela(conteudo: bytes, ano: int, url: str) -> list[Registro]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    registros: list[Registro] = []
    for modalidade, medalha, campos in _linhas_tabela_com_marcador(doc, ano, url):
        nivel_texto, serie_min, serie_max = _NIVEL_OBQ.get(modalidade or "", ("", None, None))
        registros.append(
            Registro(
                prova_nome="OBQ",
                ano=ano,
                nivel_texto=nivel_texto,
                serie_referencia_min=serie_min,
                serie_referencia_max=serie_max,
                resultado=medalha,
                nome_informado=campos["nome"],
                escola_informada=campos["escola"],
                cidade_informada=campos["cidade"],
                uf_informada=campos["uf"],
                fonte_url=url,
            )
        )
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


def _parsear_obqjr_tabela_marcador(conteudo: bytes, ano: int, url: str) -> list[Registro]:
    """Variante 2018/2020 da OBQ Jr: mesmo padrão de marcador-de-seção +
    cabeçalho dinâmico do `_parsear_obq_tabela` (reaproveita
    `_linhas_tabela_com_marcador`), não o inline-por-linha do
    `_parsear_obqjr_tabela` (2022/2023) — a OBQ Jr também já publicou as
    duas formas. Sem modalidade (a OBQ Jr não distingue A/B nesses anos, e
    quando distingue — 2020 tem uma coluna extra de "A"/"a" minúsculo entre
    nome e escola — o cabeçalho dinâmico já pula essa coluna sozinho, porque
    ela nunca bate `\\bESTADO\\b`/`\\bESCOLA\\b`/`\\bNOME\\b`/`\\bCIDADE\\b`)."""
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    registros: list[Registro] = []
    for _modalidade, medalha, campos in _linhas_tabela_com_marcador(doc, ano, url):
        registros.append(
            Registro(
                prova_nome="OBQ Jr",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=6,
                serie_referencia_max=9,
                resultado=medalha,
                nome_informado=campos["nome"],
                escola_informada=campos["escola"],
                cidade_informada=campos["cidade"],
                uf_informada=campos["uf"],
                fonte_url=url,
            )
        )
    return registros


_PARSERS = {
    ("OBQ", "texto"): _parsear_obq_texto,
    ("OBQ", "texto2"): _parsear_obq_texto2,
    ("OBQ", "tabela"): _parsear_obq_tabela,
    ("OBQ Jr", "texto"): _parsear_obqjr_texto,
    ("OBQ Jr", "tabela"): _parsear_obqjr_tabela,
    ("OBQ Jr", "tabela_marcador"): _parsear_obqjr_tabela_marcador,
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
