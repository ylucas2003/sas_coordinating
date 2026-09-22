"""Raspa os convocados do vestibular do ITA — 2ª fase (quem passou na 1ª,
objetiva) E 3ª fase (inspeção de saúde, o último crivo antes da matrícula) —
e grava um JSON cru por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/ita.py --anos 2024 2025
    ./.venv/bin/python pipeline/ita.py --anos 2020 2021 2022 2023   # via Wayback Machine

## Duas fases, não só a 3ª — "todos os alunos", não só os aprovados finais

Até 16/09/2026 este scraper só trazia a 3ª fase (~180-330 pessoas por ano).
Pedido explícito: "salvar o resultado de TODOS os alunos, não só dos
aprovados" — e a 1ª fase (objetiva) não tem lista nomeada nenhuma
(`{ano}_convocados_1f.htm` nunca existiu; é natural, ninguém foi filtrado
ainda), mas a **2ª fase tem**, e é MUITO maior: 773-777 pessoas por ano contra
~180-330 na 3ª. Continua sendo "quem passou uma etapa", nunca a base de
TODOS os inscritos — a ITA não publica nome de quem não avançou nenhuma fase,
em lugar nenhum. "Convocado pra 2ª fase" é o teto real do que dá pra
capturar com nome.

Cada pessoa costuma render DUAS linhas de `conquista_externa` no ano em que
chega à 3ª fase — uma da 2ª fase, uma da 3ª — porque são dois EVENTOS
distintos de classificação, não a mesma informação duas vezes; é o mesmo
raciocínio de OBMEP guardar Ouro E o nível como campos separados.

## Isto é validação, não descoberta — ao contrário de OBMEP/OBM

As outras duas fontes (docs/41 §5, §5.1) acham gente que AINDA vai prestar
vestibular — um lead de captação de verdade. O ITA é o inverso: quem está
nesta lista **já passou** no vestibular que o colégio existe pra preparar.
Não tem série de referência pra calcular (a lista não diz se é treineiro
ou formando, então `serie_referencia_min/max` sai `None` sempre — inventar um
valor aqui seria pior que não ter nenhum) e a maioria já deve estar de saída
do ensino médio, não precisando de convite nenhum.

O valor real é **cruzar por nome com quem a OBMEP/OBM já achou**: confirma
que o sinal de captação (medalha de olimpíada) realmente correlaciona com
aprovação no vestibular-alvo — é dado de prova da tese, não fila de convite.
Ver a conversa de 16/09/2026 que cruzou OBMEP×OBM por nome; ITA é a
terceira ponta do mesmo triângulo.

## `BANCA` é a CIDADE DA PROVA, não a cidade do candidato

Diferença real de significado em relação a `cidade_informada` da OBMEP/OBM
(que é o município do ALUNO): aqui é onde ele *aplicou* a prova — um
candidato de uma cidade pequena vai pra "banca" mais perto, não pra sua
própria cidade. `_CIDADE_DA_BANCA` traduz o nome em CAIXA ALTA do relatório
pra Cidade/UF, usando a lista real de locais de prova do próprio site
(`vestibular.ita.br/principal.htm`) — não é chute, é a lista de cidades que o
ITA de fato usa, contra a qual todo valor de `BANCA` visto em 2024/2025 bateu.

## Ao vivo, só 2024 e 2025 — 2020-2023 voltaram pelo Wayback Machine

`{ano}_convocados_2f.htm`/`_3f.htm` funciona pra 2024/2025; 2023 pra trás
devolve 404 nesse padrão de nome (o "Dossiê de Provas", arquivo 09, já
registrava isso como não confirmado).

O que existia era outro padrão de URL — `notas/{ano}_notas_1f_completo.htm`
e `_2f_completo.htm` —, que o site já não serve mais ao vivo, mas o Wayback
Machine tem congelado pra 2019-2026. É uma fonte MELHOR que a "convocados"
atual, não só mais velha: **lista TODO MUNDO que fez a prova**, aprovado ou
não (inclusive "AUSENTE"), com nota aberta — a "convocados" só mostra quem
passou de fase. `_DOCUMENTOS_HISTORICOS` curou 2020-2023 (pesquisa dirigida
de 22/09/2026); 2019/2024/2025/2026 também existem no Wayback pra quando
fizer sentido gastar o tempo de trazer.

⚠️ O `<pre>` do "1f_completo" não FECHA no HTML original (a página nunca foi
bem-formada, nem antes do Wayback capturar) — `parsear_1f_completo` lê tudo
depois da abertura até o fim do documento, em vez de procurar `</pre>`. E o
separador decimal varia ano a ano: 2022 usa ponto ("3.3333"), 2023 usa
vírgula ("7,5000") — `_numero` já tolera os dois (só troca vírgula por
ponto, e ponto sem vírgula não muda).

Três achados a mais, só vistos rodando de verdade contra os quatro anos
(22/09/2026), que custaram registro em silêncio antes de virarem código:

- **O banner "VESTIBULAR AAAA" não existe em toda página** — 2020/2021 têm,
  2022/2023 pulam direto pro título da tabela. `_confere_ano_historico` só
  recusa o ano quando o banner EXISTE e diz outra coisa; ausência não é
  motivo pra descartar (era o bug original: tratava as duas situações igual e
  jogava fora 2022 inteiro e todo o 2023).
- **2021 usa `<br>` como separador de linha DENTRO do `<pre>` da 1ª fase**
  (7223 ocorrências, contra 8-11 incidentais nos outros anos) — sem
  normalizar pra `\n` antes de repartir, `.split("\n")` via quase tudo como
  uma linha só. `_linhas_do_pre_sem_fechar` cuida disso pra 1ª fase;
  `parsear_2f_completo` normaliza pelo mesmo motivo, de graça, mesmo não
  tendo achado o problema lá ainda.
- **2023 (só a 2ª fase) vem em DOIS `<pre>`** — "Candidatos Optantes pela
  Carreira Militar" e "Não Optantes", cada um com seu próprio cabeçalho.
  `re.search` (um match só) pegava só o primeiro bloco (185 de 729
  candidatos) e nunca avisava que faltava o resto — silêncio idêntico ao
  do banner ausente. `parsear_2f_completo` agora itera `re.finditer` sobre
  todos os blocos.

## Sem escola, e por quê `escola_informada` sai `""` e não `None`

O relatório não publica escola (só Nome, notas, classificação e banca) —
mesma ausência da OBM (pipeline/obm.py), e pelo mesmo motivo o campo sai `""`:
o índice único de dedup (migration 0057) trata NULL como sempre-diferente-de-
NULL, e duas raspagens do mesmo ano duplicariam a linha inteira em vez de
fazer upsert.

## RESERVA continua sinal, só que mais fraco — não é filtrado

Anos com concorrência maior (2024) separam ATIVA de RESERVA (lista de espera,
chamada se alguém da ativa desistir) dentro de cada cota; 2025 não fez essa
separação. O rótulo da seção vira `resultado` como o site escreveu — nenhuma
tradução, mesma regra do `resultado` da OBMEP/OBM (migration 0056: "cada
prova tem seu próprio vocabulário").
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

BASE = "https://vestibular.ita.br"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Cidade da prova (CAIXA ALTA, como o relatório escreve) → (Cidade bonita, UF).
# Extraído dos locais de exame reais em vestibular.ita.br/principal.htm —
# conferido contra TODO valor de BANCA visto em 2024 e 2025 (ver docstring).
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
    "SAO JOSE DO RIO PRETO": ("São José do Rio Preto", "SP"),
    "SAO JOSE RIO PRETO": ("São José do Rio Preto", "SP"),
    "SAO JOSE DO RIO PRET": ("São José do Rio Preto", "SP"),
    "SAO JOSE DOS CAMPOS": ("São José dos Campos", "SP"),
    "SAO LUIS": ("São Luís", "MA"),
    "SAO PAULO": ("São Paulo", "SP"),
    "TERESINA": ("Teresina", "PI"),
    "VITORIA": ("Vitória", "ES"),
}

# ano -> (url 1ª fase completa, url 2ª fase completa), via Wayback Machine —
# pesquisa dirigida de 22/09/2026 (docstring do módulo). Timestamp escolhido
# é o snapshot mais completo achado na API CDX pra cada URL.
_DOCUMENTOS_HISTORICOS: dict[int, tuple[str, str]] = {
    2020: (
        "http://web.archive.org/web/20210116182131/http://www.vestibular.ita.br/notas/2020_notas_1f_completo.htm",
        "http://web.archive.org/web/20210116171959/http://www.vestibular.ita.br/notas/2020_notas_2f_completo.htm",
    ),
    2021: (
        "http://web.archive.org/web/20210116175631/http://www.vestibular.ita.br/notas/2021_notas_1f_completo.htm",
        "http://web.archive.org/web/20210116170147/http://www.vestibular.ita.br/notas/2021_notas_2f_completo.htm",
    ),
    2022: (
        "http://web.archive.org/web/20211125170650/http://www.vestibular.ita.br/notas/2022_notas_1f_completo.htm",
        "http://web.archive.org/web/20220120161253/http://www.vestibular.ita.br/notas/2022_notas_2f_completo.htm",
    ),
    2023: (
        "http://web.archive.org/web/20221104162847/https://www.vestibular.ita.br/notas/2023_notas_1f_completo.htm",
        "http://web.archive.org/web/20221214142824/https://www.vestibular.ita.br/notas/2023_notas_2f_completo.htm",
    ),
}
_PADRAO_ANO_HISTORICO = re.compile(r"VESTIBULAR (\d{4})")


@dataclass
class Registro:
    prova_nome: str
    ano: int
    # "" e não None, mesmo raciocínio de `escola_informada`: o índice único de
    # dedup (0057) trata NULL como sempre-diferente-de-NULL, e reimportar o
    # mesmo ano duplicaria a linha inteira. Descoberto rodando de verdade:
    # a primeira leva de import ficou 660 em vez de 330 (2x) até este fix.
    nivel_texto: str
    serie_referencia_min: int | None
    serie_referencia_max: int | None
    resultado: str
    nome_informado: str
    escola_informada: str
    cidade_informada: str
    uf_informada: str
    fonte_url: str
    # Só a 3ª fase publica nota — a 2ª fase é só convocação (nome/banca/sala,
    # sem prova ainda feita) e sai sempre `None` (docstring da 2ª fase).
    notas_por_materia: dict[str, float] | None = None


def _titulo_da_secao(texto: str, fim_do_bloco: int) -> str:
    """O rótulo "Convocados – X" mais próximo ANTES do bloco `<pre>` — vira o
    `resultado` sem tradução (docstring do módulo)."""
    trecho = texto[:fim_do_bloco]
    m = list(re.finditer(r"Convocados\s*(?:&#8211;|–|-)?\s*([^<]*)", trecho))
    if not m:
        return "Convocado — 3ª fase"
    rotulo = html.unescape(re.sub(r"\s+", " ", m[-1].group(1)).strip())
    return rotulo or "Convocado — 3ª fase"


def _numero(texto: str) -> float:
    return float(texto.replace(",", "."))


def _rotulos_das_materias(linhas: list[str]) -> list[str] | None:
    """Lê a linha de CABEÇALHO do bloco (a única com "NOME") pra saber quais
    matérias a 2ª fase cobrou NAQUELE ciclo — acha real, não suposição: 2024
    testou Redação no lugar de Português onde 2025 testou Português, mesma
    posição da tabela (docstring do módulo, "o meio varia de largura"). Sem
    ler o cabeçalho de cada bloco, "REDACAO" de um ano viraria "port" errado
    no outro."""
    cabecalho = next((l for l in linhas if l.startswith("|") and "NOME" in l), None)
    if cabecalho is None:
        return None
    campos = [c.strip() for c in cabecalho.strip("|").split("|")]
    if len(campos) != 5:
        return None
    return [r.rstrip(".").lower() for r in campos[2].split()]


def _confere_ano_historico(texto: str, ano_esperado: int, fonte_url: str) -> bool:
    """O banner "VESTIBULAR AAAA" só existe em ALGUNS anos (achado rodando de
    verdade: 2020/2021 têm, 2022/2023 não — a página pula direto pro título
    da tabela). Sem banner, confia no ano do próprio `_DOCUMENTOS_HISTORICOS`
    (a URL já tem o ano no nome do arquivo); só recusa se o banner EXISTIR e
    disser um ano DIFERENTE — aí sim é sinal real de conteúdo trocado."""
    m_ano = _PADRAO_ANO_HISTORICO.search(texto)
    if m_ano and int(m_ano.group(1)) != ano_esperado:
        print(
            f"  aviso: banner diz {m_ano.group(1)}, esperava {ano_esperado} — pulando ({fonte_url})",
            file=sys.stderr,
        )
        return False
    return True


def _linhas_do_pre_sem_fechar(texto: str) -> list[str] | None:
    """Lê tudo depois de `<pre>` até o fim do documento — achado real: o
    `<pre>` desta página nunca fecha no HTML original (nem antes do Wayback
    capturar), então procurar `</pre>` devolveria vazio. Também troca `<br>`
    por quebra de linha de verdade: 2021 usa `<br>` como separador de linha
    dentro do PRÓPRIO `<pre>` (nenhum outro ano faz isso, achado comparando
    os quatro)."""
    idx = texto.find("<pre>")
    if idx < 0:
        return None
    bruto = texto[idx + len("<pre>") :]
    bruto = re.sub(r"<br\s*/?>", "\n", bruto, flags=re.IGNORECASE)
    return bruto.split("\n")


def parsear_1f_completo(texto: str, ano_esperado: int, fonte_url: str) -> list[Registro]:
    """"Notas da 1ª Fase" completa — TODO CANDIDATO que fez a prova, aprovado
    ou não (inclusive AUSENTE), formato `| final do CPF | NOME | <matérias> |
    OBS |`."""
    if not _confere_ano_historico(texto, ano_esperado, fonte_url):
        return []

    linhas = _linhas_do_pre_sem_fechar(texto)
    if linhas is None:
        print(f"  aviso: sem <pre> em {fonte_url} — layout mudou?", file=sys.stderr)
        return []

    cabecalho = next((l for l in linhas if l.strip().startswith("|") and "NOME" in l.upper()), None)
    rotulos = [r.rstrip(".").lower() for r in cabecalho.strip().strip("|").split("|")[2].split()] if cabecalho else None

    registros: list[Registro] = []
    for linha in linhas:
        campos = [c.strip() for c in linha.rstrip("\r").strip().strip("|").split("|")]
        # Âncora inequívoca: "final do CPF" no formato NNN-NN — nunca aparece
        # na linha de cabeçalho nem nos separadores `+---+`.
        if len(campos) < 4 or not re.match(r"^\d{3}-\d{2}$", campos[0]):
            continue
        nome = campos[1]
        if not nome:
            continue
        obs = campos[-1].strip().upper()
        valores = campos[2:-1]
        notas: dict[str, float] | None = None
        if rotulos and len(rotulos) == len(valores):
            notas = {r: _numero(v) for r, v in zip(rotulos, valores, strict=True)}

        registros.append(
            Registro(
                prova_nome="ITA",
                ano=ano_esperado,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                resultado="Ausente — 1ª fase" if obs == "AUSENTE" else "Realizou a 1ª fase",
                nome_informado=nome,
                escola_informada="",
                # Sem BANCA nesta página — só a prova objetiva, sem local.
                cidade_informada="",
                uf_informada="",
                fonte_url=fonte_url,
                notas_por_materia=notas,
            )
        )
    return registros


def parsear_2f_completo(texto: str, ano_esperado: int, fonte_url: str) -> list[Registro]:
    """"Notas da 2ª Fase" completa — TODO CANDIDATO que fez a prova
    discursiva, classificado pra 3ª fase ou não (CLASS. sai "----" pra quem
    não classificou). Mesmo formato de `parsear_pagina_do_ano`
    (NOME | média 1ª fase | matérias da 2ª fase | classificação | banca).

    Achado real em 2023: a página vem em DOIS `<pre>`, um pra "Candidatos
    Optantes pela Carreira Militar" e outro pra "Não Optantes" — não é
    "Convocados" por cota (isso só existe na 3ª fase), mas ainda assim quebra
    ao vivo em duas tabelas. `re.search` (um só match) pegava só a primeira e
    descartava 544 dos 729 candidatos em silêncio; por isso agora é
    `re.finditer` sobre TODOS os blocos, cada um com seu próprio cabeçalho
    (2020-2022 têm só um bloco, e continuam funcionando do mesmo jeito)."""
    if not _confere_ano_historico(texto, ano_esperado, fonte_url):
        return []

    blocos = list(re.finditer(r"<pre>(.*?)</pre>", texto, re.DOTALL))
    if not blocos:
        print(f"  aviso: sem <pre>...</pre> em {fonte_url} — layout mudou?", file=sys.stderr)
        return []

    registros: list[Registro] = []
    for bloco in blocos:
        # `<br>` no lugar de `\n` só apareceu na 1ª fase de 2021 (achado real,
        # ver `_linhas_do_pre_sem_fechar`), mas normalizar aqui também é de
        # graça e blinda contra o mesmo problema aparecer nesta página nalgum
        # ano futuro.
        linhas = re.sub(r"<br\s*/?>", "\n", bloco.group(1), flags=re.IGNORECASE).split("\n")

        cabecalho = next((l for l in linhas if l.strip().startswith("|") and "NOME" in l.upper()), None)
        rotulos = [r.rstrip(".").lower() for r in cabecalho.strip().strip("|").split("|")[2].split()] if cabecalho else None

        for linha in linhas:
            campos = [c.strip() for c in linha.rstrip("\r").strip().strip("|").split("|")]
            if len(campos) != 5 or campos[0].upper() == "NOME" or not campos[0]:
                continue
            nome = campos[0]
            banca = campos[-1].strip().upper()
            classe = campos[-2].strip()
            cidade, uf = _CIDADE_DA_BANCA.get(banca, (banca.title(), ""))
            if banca not in _CIDADE_DA_BANCA:
                print(f"  aviso: banca desconhecida {banca!r} — sem UF", file=sys.stderr)

            notas: dict[str, float] | None = None
            valores_materias = campos[2].split()
            if rotulos and len(rotulos) == len(valores_materias):
                notas = {
                    (f"{r}_2fase" if r == "media" else r): _numero(v)
                    for r, v in zip(rotulos, valores_materias, strict=True)
                }
                notas["media_1fase"] = _numero(campos[1])
                if classe not in ("", "----"):
                    notas["classificacao"] = _numero(classe)

            resultado = f"Classificado — 2ª fase (nº {int(classe)})" if classe not in ("", "----") else "Não classificado — 2ª fase"

            registros.append(
                Registro(
                    prova_nome="ITA",
                    ano=ano_esperado,
                    nivel_texto="",
                    serie_referencia_min=None,
                    serie_referencia_max=None,
                    resultado=resultado,
                    nome_informado=nome,
                    escola_informada="",
                    cidade_informada=cidade,
                    uf_informada=uf,
                    fonte_url=fonte_url,
                    notas_por_materia=notas,
                )
            )
    return registros


def parsear_pagina_do_ano(html: str, ano: int, fonte_url: str) -> list[Registro]:
    registros: list[Registro] = []

    for bloco in re.finditer(r"<pre>(.*?)</pre>", html, re.DOTALL):
        conteudo, fim_do_bloco = bloco.group(1), bloco.start()
        linhas = [l.rstrip("\r") for l in conteudo.split("\n")]
        dados = [
            l for l in linhas
            if l.startswith("|") and "NOME" not in l and set(l.strip()) != {"-", "+"}
        ]
        if not dados:
            continue

        resultado = _titulo_da_secao(html, fim_do_bloco)
        rotulos_materias = _rotulos_das_materias(linhas)

        for linha in dados:
            campos = [c.strip() for c in linha.strip("|").split("|")]
            # NOME é sempre o primeiro campo e BANCA o último — o meio (as
            # notas por fase) varia de largura entre anos (docstring), mas as
            # duas pontas nunca mudaram de lugar nos anos conferidos.
            if len(campos) < 3:
                continue
            nome, banca = campos[0], campos[-1].strip().upper()
            if not nome:
                continue
            cidade, uf = _CIDADE_DA_BANCA.get(banca, (banca.title(), ""))
            if banca not in _CIDADE_DA_BANCA:
                print(f"  aviso: banca desconhecida {banca!r} — sem UF", file=sys.stderr)

            # 5 campos (nome, média 1ª fase, bloco de matérias, classificação,
            # banca) é o formato confirmado em 2024/2025 — fora disso, melhor
            # não ter granularidade do que casar número com matéria errada.
            notas: dict[str, float] | None = None
            if len(campos) == 5:
                valores_materias = campos[2].split()
                if rotulos_materias and len(rotulos_materias) == len(valores_materias):
                    notas = {
                        (f"{r}_2fase" if r == "media" else r): _numero(v)
                        for r, v in zip(rotulos_materias, valores_materias, strict=True)
                    }
                    notas["media_1fase"] = _numero(campos[1])
                    notas["classificacao"] = _numero(campos[3])

            registros.append(
                Registro(
                    prova_nome="ITA",
                    ano=ano,
                    nivel_texto="",
                    serie_referencia_min=None,
                    serie_referencia_max=None,
                    resultado=resultado,
                    nome_informado=nome,
                    escola_informada="",
                    cidade_informada=cidade,
                    uf_informada=uf,
                    notas_por_materia=notas,
                    fonte_url=fonte_url,
                )
            )
    return registros


def _linha_e_separador(linha: str) -> bool:
    """`------ -------- ---- ----` — a régua de traços que delimita as
    colunas da 2ª fase, sem NOME nenhum atrás. Sobra uma no fim do relatório
    inteiro, sem dado depois — por isso não basta olhar só a PRIMEIRA."""
    sem_espaco = linha.replace(" ", "")
    return bool(sem_espaco) and set(sem_espaco) <= {"-"}


def parsear_convocados_2f(texto: str, ano: int, fonte_url: str) -> list[Registro]:
    """"Convocados pra 2ª fase" é texto de LARGURA FIXA, não `|`-delimitado
    como a 3ª fase — sem cabeçalho repetido por seção, um `<pre>` só de
    cabeçalho e outro só de dado. A largura de cada coluna muda de ano pra
    ano (a do relatório de 2025 é mais larga que a de 2024, porque
    "SAO JOSE DO RIO PRETO" — 21 caracteres — só apareceu em 2025): por isso
    as posições vêm da régua de traços do PRÓPRIO ano, nunca de um número
    cravado aqui. Duas colunas (NOME cabe em 1 espaço de sobra, não 2+) já
    bastam pra split-por-espaço dar linha errada — largura fixa não erra.
    """
    blocos = re.findall(r"<pre>(.*?)</pre>", texto, re.DOTALL)
    if len(blocos) < 2:
        return []
    cabecalho, corpo = blocos[0], blocos[1]

    linha_regua = next(
        (l.rstrip("\r") for l in cabecalho.split("\n") if _linha_e_separador(l.rstrip("\r"))),
        None,
    )
    if linha_regua is None:
        print("  aviso: 2ª fase sem régua de colunas reconhecida — pulando", file=sys.stderr)
        return []
    colunas = [(m.start(), m.end()) for m in re.finditer(r"-+", linha_regua)]
    if len(colunas) != 4:
        print(f"  aviso: 2ª fase com {len(colunas)} colunas, esperava 4 — pulando", file=sys.stderr)
        return []
    col_nome, col_banca = colunas[1], colunas[2]

    registros: list[Registro] = []
    for linha in corpo.split("\n"):
        linha = linha.rstrip("\r")
        if not linha.strip() or _linha_e_separador(linha):
            continue
        nome = linha[col_nome[0] : col_nome[1]].strip()
        banca = linha[col_banca[0] : col_banca[1]].strip().upper()
        if not nome:
            continue
        cidade, uf = _CIDADE_DA_BANCA.get(banca, (banca.title(), ""))
        if banca not in _CIDADE_DA_BANCA:
            print(f"  aviso: banca desconhecida {banca!r} — sem UF", file=sys.stderr)

        registros.append(
            Registro(
                prova_nome="ITA",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                resultado="Convocado — 2ª fase",
                nome_informado=nome,
                escola_informada="",
                cidade_informada=cidade,
                uf_informada=uf,
                fonte_url=fonte_url,
            )
        )
    return registros


def _raspar_ano_historico(ano: int) -> list[Registro]:
    """2020-2023: página ao vivo não existe mais — vem do Wayback Machine,
    formato "completo" (todo candidato, não só convocado — docstring)."""
    url_1f, url_2f = _DOCUMENTOS_HISTORICOS[ano]
    registros: list[Registro] = []

    resp = requests.get(url_1f, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    registros.extend(parsear_1f_completo(resp.text, ano, url_1f))

    resp = requests.get(url_2f, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    registros.extend(parsear_2f_completo(resp.text, ano, url_2f))

    return registros


def raspar_ano(ano: int) -> list[Registro]:
    if ano in _DOCUMENTOS_HISTORICOS:
        return _raspar_ano_historico(ano)

    registros: list[Registro] = []

    url_2f = f"{BASE}/{ano}_convocados_2f.htm"
    resp = requests.get(url_2f, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    registros.extend(parsear_convocados_2f(resp.text, ano, url_2f))

    url_3f = f"{BASE}/{ano}_convocados_3f.htm"
    resp = requests.get(url_3f, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    registros.extend(parsear_pagina_do_ano(resp.text, ano, url_3f))

    return registros


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--anos",
        type=int,
        nargs="+",
        required=True,
        help=f"Anos a raspar — 2024/2025 ao vivo, ou {sorted(_DOCUMENTOS_HISTORICOS)} via Wayback Machine (ver docstring)",
    )
    args = parser.parse_args()

    DIR_DADOS.mkdir(exist_ok=True)

    for ano in args.anos:
        print(f"ITA {ano} — raspando...", file=sys.stderr)
        try:
            registros = raspar_ano(ano)
        except requests.HTTPError as e:
            print(f"  falhou: {e}", file=sys.stderr)
            continue

        if not registros:
            print("  0 registros — algo mudou no site, confira antes de importar", file=sys.stderr)
            continue

        destino = DIR_DADOS / f"ita_{ano}.json"
        destino.write_text(
            json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  ITA {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
