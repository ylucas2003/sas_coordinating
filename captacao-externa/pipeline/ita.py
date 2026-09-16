"""Raspa os convocados do vestibular do ITA — 2ª fase (quem passou na 1ª,
objetiva) E 3ª fase (inspeção de saúde, o último crivo antes da matrícula) —
e grava um JSON cru por ano em dados/.

Uso:
    ./.venv/bin/python pipeline/ita.py --anos 2024 2025

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

## Só 2024 e 2025 confirmados

`{ano}_convocados_3f.htm` funciona pra esses dois; 2023 pra trás devolve 404
nesse padrão de nome (o "Dossiê de Provas", arquivo 09, já registrava isso
como não confirmado). Não investigado se existe outro nome de arquivo pros
anos anteriores — mesmo tipo de lacuna que a OBMEP tinha antes de virar
`SEGMENTO_POR_ANO` (pipeline/obmep.py); fica pra quando fizer sentido gastar
o tempo de achar.

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
    "SAO JOSE DOS CAMPOS": ("São José dos Campos", "SP"),
    "SAO LUIS": ("São Luís", "MA"),
    "SAO PAULO": ("São Paulo", "SP"),
    "TERESINA": ("Teresina", "PI"),
    "VITORIA": ("Vitória", "ES"),
}


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


def _titulo_da_secao(texto: str, fim_do_bloco: int) -> str:
    """O rótulo "Convocados – X" mais próximo ANTES do bloco `<pre>` — vira o
    `resultado` sem tradução (docstring do módulo)."""
    trecho = texto[:fim_do_bloco]
    m = list(re.finditer(r"Convocados\s*(?:&#8211;|–|-)?\s*([^<]*)", trecho))
    if not m:
        return "Convocado — 3ª fase"
    rotulo = html.unescape(re.sub(r"\s+", " ", m[-1].group(1)).strip())
    return rotulo or "Convocado — 3ª fase"


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


def raspar_ano(ano: int) -> list[Registro]:
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
    parser.add_argument("--anos", type=int, nargs="+", required=True, help="Anos a raspar — só 2024 e 2025 confirmados (ver docstring)")
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
