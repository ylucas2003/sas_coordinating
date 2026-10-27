"""O schema do banco lido das migrations — para o fake recusar o que o PostgREST recusa.

O fake de tool (`FakeRico`, tests/test_chat_tools_coordenacao.py) devolvia
`None` para coluna que não existe, e com isso uma tool que pedia `simulado.fase`
— removida na 0003 — passou na suíte inteira enquanto falhava SEMPRE no banco
de verdade, com 42703 (revisão paralela de 25/10). Este leitor dá ao fake o
schema contra o qual conferir cada coluna pedida, e o tipo, para recusar o id
torto numa coluna uuid como o Postgres recusa (22P02).

Lê só o que as migrations deste repositório usam: CREATE TABLE, ALTER TABLE
(ADD/DROP/RENAME COLUMN, RENAME TO), DROP TABLE e o nome das views. Conferido
em 25/10 contra o OpenAPI do PostgREST de uma stack com as migrations até a do
`token_mcp` (hoje 0072; a stack não tinha a 0069 do horário de estudos, que veio
do `main` depois): as 59 tabelas batem coluna por coluna. As COLUNAS das views
não são lidas — o fake não confere o que não sabe, em vez de inventar.

⚠️ Uma migration que crie tabela dentro de um bloco `DO $$ … $$` passaria
despercebida: o corpo entre cifrões é descartado, porque é lá que moram as
funções, cujo texto não é schema.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

_COMENTARIO_DE_LINHA = re.compile(r"--[^\n]*")
_COMENTARIO_DE_BLOCO = re.compile(r"/\*.*?\*/", re.S)
_TEXTO = re.compile(r"'(?:[^']|'')*'")
_CORPO_ENTRE_CIFROES = re.compile(r"\$([A-Za-z_]*)\$.*?\$\1\$", re.S)
_NOME = r'"?([A-Za-z_][A-Za-z0-9_]*)"?'
_TABELA = rf"(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:ONLY\s+)?(?:public\.)?{_NOME}"
_TIPO = r"([A-Za-z_][A-Za-z0-9_]*(?:\[\])?)"
#: A primeira palavra de uma restrição de tabela, que não é coluna.
_RESTRICOES = frozenset({"constraint", "primary", "unique", "check", "foreign", "exclude", "like"})


@dataclass(frozen=True)
class Esquema:
    #: tabela → {coluna: tipo}, o tipo como a migration o escreveu, em minúsculas.
    tabelas: dict[str, dict[str, str]]
    views: frozenset[str]

    def colunas(self, nome: str) -> dict[str, str] | None:
        """As colunas da tabela; None para view (colunas não lidas) ou nome desconhecido."""
        return self.tabelas.get(nome)

    def existe(self, nome: str) -> bool:
        return nome in self.tabelas or nome in self.views


def _partes(corpo: str) -> list[str]:
    """Divide no nível de cima, respeitando parênteses."""
    partes, atual, profundidade = [], [], 0
    for c in corpo:
        profundidade += (c == "(") - (c == ")")
        if c == "," and profundidade == 0:
            partes.append("".join(atual).strip())
            atual = []
        else:
            atual.append(c)
    if "".join(atual).strip():
        partes.append("".join(atual).strip())
    return partes


def _fecho(texto: str, abre: int) -> int:
    profundidade = 0
    for i in range(abre, len(texto)):
        profundidade += (texto[i] == "(") - (texto[i] == ")")
        if profundidade == 0:
            return i
    return -1


def _tipo(bruto: str) -> str:
    return bruto.split("(")[0].lower()


def _comandos(arquivo: Path) -> list[str]:
    sql = arquivo.read_text(encoding="utf-8")
    sql = _COMENTARIO_DE_BLOCO.sub(" ", _COMENTARIO_DE_LINHA.sub(" ", sql))
    # Texto entre aspas some antes do corte por ';': COMMENT ON tem ponto e
    # vírgula e parêntese dentro do texto.
    sql = _CORPO_ENTRE_CIFROES.sub(" ", _TEXTO.sub("''", sql))
    return [" ".join(c.split()) for c in sql.split(";") if c.strip()]


def _aplicar(comando: str, tabelas: dict[str, dict[str, str]], views: set[str]) -> None:
    m = re.match(rf"CREATE\s+(?:UNLOGGED\s+)?TABLE\s+{_TABELA}\s*\(", comando, re.I)
    if m:
        abre = m.end() - 1
        fecho = _fecho(comando, abre)
        if fecho < 0:
            return
        colunas: dict[str, str] = {}
        for parte in _partes(comando[abre + 1 : fecho]):
            palavras = parte.split()
            if palavras[0].lower() in _RESTRICOES or len(palavras) < 2:
                continue
            colunas[palavras[0].strip('"')] = _tipo(palavras[1])
        tabelas[m.group(1)] = colunas
        return

    m = re.match(rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+{_TABELA}", comando, re.I)
    if m:
        views.add(m.group(1))
        return

    m = re.match(rf"DROP\s+(?:MATERIALIZED\s+)?VIEW\s+(?:IF\s+EXISTS\s+)?(?:public\.)?{_NOME}", comando, re.I)
    if m:
        views.discard(m.group(1))
        return

    m = re.match(rf"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:public\.)?{_NOME}", comando, re.I)
    if m:
        tabelas.pop(m.group(1), None)
        return

    m = re.match(rf"ALTER\s+TABLE\s+{_TABELA}\s+(.*)$", comando, re.I)
    if not m or m.group(1) not in tabelas:
        return
    tabela, acoes = m.group(1), m.group(2)
    r = re.match(rf"RENAME\s+TO\s+{_NOME}", acoes, re.I)
    if r:
        tabelas[r.group(1)] = tabelas.pop(tabela)
        return
    r = re.match(rf"RENAME\s+(?:COLUMN\s+)?{_NOME}\s+TO\s+{_NOME}", acoes, re.I)
    if r:
        tabelas[tabela][r.group(2)] = tabelas[tabela].pop(r.group(1), "")
        return
    for acao in _partes(acoes):
        a = re.match(rf"ADD\s+(?:COLUMN\s+)?(?:IF\s+NOT\s+EXISTS\s+)?{_NOME}\s+{_TIPO}", acao, re.I)
        if a and a.group(1).lower() not in _RESTRICOES:
            tabelas[tabela][a.group(1)] = _tipo(a.group(2))
            continue
        d = re.match(rf"DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?{_NOME}", acao, re.I)
        if d:
            tabelas[tabela].pop(d.group(1), None)


@functools.cache
def esquema() -> Esquema:
    """O schema depois de todas as migrations de subida, na ordem do nome."""
    tabelas: dict[str, dict[str, str]] = {}
    views: set[str] = set()
    for arquivo in sorted(MIGRATIONS.glob("*.sql")):
        if arquivo.name.endswith(".down.sql"):
            continue
        for comando in _comandos(arquivo):
            _aplicar(comando, tabelas, views)
    return Esquema(tabelas=tabelas, views=frozenset(views))
