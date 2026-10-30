#!/usr/bin/env python3
"""Confere, por HTTP, que o PostgREST do MCP deixa só o que as migrations dizem.

O MCP da coordenação lê o banco por um PostgREST PRÓPRIO, cujo papel anônimo é
o `sas_mcp` (migrations 0071 e 0072, docs/43 §5.2). A garantia de menor
privilégio está no Postgres, e não no código das tools — então a prova também
tem de ser contra o Postgres de verdade: o fake de PostgREST dos testes não
tem privilégio nenhum (tests/fake_postgrest.py). Este script é essa prova, e
roda depois de toda migration que mexer na lista branca.

A régua não é uma lista escrita aqui: é lida das próprias migrations, aplicando
em ordem todo `GRANT SELECT … TO sas_leitura` e todo `REVOKE` que o desfaça. O
que o script confere é o banco contra o arquivo — e o arquivo contra as formas
permitidas (`auditar_migrations`, que tests/test_migrations_do_mcp.py também
roda no CI).

O QUE ELE CONFERE
  0. as migrations: toda concessão que toca sas_leitura, sas_mcp, o login
     autenticador_mcp ou PUBLIC é de uma forma que esta régua entende — o que
     ela não entende é falha;
  0b. o PostgREST do MCP conecta: sem a senha do login definida, ele sai, e
     nada abaixo diria alguma coisa;
  1. o sas_mcp lê cada tabela da lista branca, com as colunas dela;
  2. e nada além: coluna fora da lista dá 42501, tabela fora dela não aparece
     para ele, e as proibidas (credencial, conversa, auditoria…) dão 42501;
  3. não escreve em tabela nenhuma da lista branca: INSERT e UPDATE coluna a
     coluna e DELETE dão 42501 (com --api, a mesma sonda passa no PostgREST
     da API — é o controle de que ela exercita o privilégio);
  4. a auditoria: INSERT em `evento_auditoria` passa com `Prefer:
     return=minimal` e falha sem ele — o postgrest-py manda
     return=representation por padrão, e `auditoria.registrar()` engole o
     erro (0072) —, e só passa evento do próprio MCP (o gatilho da 0072);
  5. a RPC `mcp_conferir_token` responde ao sas_mcp e a mais ninguém;
  6. nenhum JWT troca o papel: o PostgREST do MCP responde PGRST300 (servidor
     SEM segredo). Qualquer outro código é falha — quer dizer que ele tem um
     segredo, no env ou no banco, e um JWT assinado com ele troca o papel;
  7. com --api, o PostgREST da API continua lendo e escrevendo tudo;
  8. com --ferramentas, cada tool exposta roda pelo REGISTRO de verdade,
     contra o PostgREST do MCP: nenhuma pode dar 42501 nem devolver coluna
     sensível.

O que ele NÃO enxerga por HTTP: com que LOGIN o PostgREST do MCP conecta (o
`autenticador_mcp` da 0071, que não alcança o sas_service) e se ele lê a config
do banco (PGRST_DB_CONFIG) — isso o teste do compose confere, e a seção 0 que
nenhuma migration dá ao login mais do que o sas_mcp —, e UPDATE ou DELETE em
`evento_auditoria`, que sem SELECT nenhum filtro alcança — isso a seção 0.

USO (de api/)
  ./.venv/bin/python -m scripts.verificar_papeis_do_mcp --mcp http://127.0.0.1:3001
  ./.venv/bin/python -m scripts.verificar_papeis_do_mcp \\
      --mcp http://127.0.0.1:3001 --api http://127.0.0.1:3000 --ferramentas

  Na VPS o postgrest_mcp não publica porta: rode de dentro do container `api`,
  que enxerga os dois PostgREST pela rede default —
  `docker compose exec -T api python -m scripts.verificar_papeis_do_mcp
   --mcp http://postgrest_mcp:3000 --api http://postgrest:3000`.

Sai com código 1 se alguma conferência falhar. Aviso não muda o código: é o
que não é de privilégio (uma tool quebrada com QUALQUER papel, por exemplo) e
merece olho, mas não diz nada sobre os GRANT.

⚠️ ESCREVE duas linhas em `evento_auditoria` a cada execução (acao
'mcp_verificacao_papeis'): uma pelo PostgREST do MCP, que é a prova de que o
INSERT da trilha passa, e outra pelo da API (só com --api). Fora isso, só lê.
As tentativas de escrita não alcançam linha nenhuma — INSERT de lote vazio,
UPDATE e DELETE com filtro contraditório (`c is null AND c is not null`) —:
mesmo que o papel deixasse, nada mudaria.

Opcional: SAS_MCP_TOKEN no ambiente (o token em claro, nunca em argumento — ia
para o histórico do shell) confere que a RPC reconhece um token de verdade.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

DIR_MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
_PADRAO_UP = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")
_PADRAO_DOWN = re.compile(r"^\d{4}_[a-z0-9_]+\.down\.sql$")

#: O que o sas_mcp não lê de jeito nenhum: credencial (inclusive o OAuth e os
#: e-mails das contas de IA, 0073), conversa, contato, cantina, gravação e a
#: própria trilha (0071). Conferidas uma a uma, com ou sem --api. É também a
#: régua de tests/test_migrations_do_mcp.py. `alerta` saiu daqui em 26/10: com
#: o nome do aluno liberado no MCP (decisão do dono), `listar_alertas` é
#: exposta e a 0071 dá o GRANT por coluna. `prova_externa`, `candidato_externo`
#: e `conquista_externa` saíram em 30/10, quando a coordenação decidiu que a IA
#: lê o que o coordenador lê: a 0076 dá o GRANT por coluna, e o que continua
#: fechado da captação está em COLUNAS_PROIBIDAS_DA_CAPTACAO.
TABELAS_PROIBIDAS: tuple[str, ...] = (
    "usuario_coordenacao",
    "usuario_cantina",
    "token_mcp",
    "oauth_cliente_mcp",
    "oauth_pedido_mcp",
    "oauth_codigo_mcp",
    "oauth_refresh_mcp",
    "oauth_codigo_por_email_mcp",
    "email_conta_ia_mcp",
    "evento_auditoria",
    "chat_thread",
    "chat_mensagem",
    "chat_artefato",
    "disparo",
    "email_invalido",
    "upload",
    "upload_evento",
    "canvas_sync_execucao",
    "aula_gravacao",
    "cantina",
    "cardapio",
    "direito_refeicao_aluno",
    "pedido_refeicao",
    "pedido_refeicao_item",
    "questao_estudo_aluno",
)

#: Colunas de `aluno` que nunca entram no GRANT (0071): segredo, contato,
#: chave de entrada do Canvas, foto e dado de saúde.
COLUNAS_PROIBIDAS_DO_ALUNO: tuple[str, ...] = (
    "senha_hash",
    "email",
    "avatar_url",
    "canvas_user_id",
    "canvas_criado_em",
    "email_verificado_em",
    "foto_perfil_storage",
    "foto_perfil_atualizada_em",
    "restricao_alimentar",
)

#: Colunas da captação que nunca entram no GRANT (0076): o texto livre do funil,
#: onde um telefone anotado à mão apareceria (o SAS não tem coluna de contato),
#: e o bastidor da raspagem e do resolver, que a tela não mostra. São pessoas de
#: fora, muitas menores, que nunca se cadastraram: a régua é o que a tela mostra.
COLUNAS_PROIBIDAS_DA_CAPTACAO: dict[str, tuple[str, ...]] = {
    "candidato_externo": ("observacoes", "retrato_editado_a_mao"),
    "conquista_externa": ("nome_informado", "raspado_em"),
}

#: As únicas funções que o sas_mcp pode executar. `buscar_candidatos_por_conquista`
#: é SECURITY INVOKER (0068) e vem de PUBLIC: roda com o privilégio de quem
#: chama, então só alcança as colunas que a 0076 lhe deu — é uma das tools da
#: captação. Função nova que aparecer aqui é para olhar: se for SECURITY
#: DEFINER, roda como superusuário.
FUNCOES_EXECUTAVEIS: frozenset[str] = frozenset(
    {"mcp_conferir_token", "buscar_candidatos_por_conquista"}
)

#: Chave que, em qualquer profundidade do resultado de uma tool, é vazamento.
#: Comparadas sem `_` e sem caixa, para pegar `senha_hash` e `senhaHash`.
_CHAVES_SENSIVEIS: frozenset[str] = frozenset(
    {
        *(c.replace("_", "") for c in COLUNAS_PROIBIDAS_DO_ALUNO),
        *(c.replace("_", "") for colunas in COLUNAS_PROIBIDAS_DA_CAPTACAO.values() for c in colunas),
        "fotourl",
        "hashacesso",
        "ip",
    }
)

_PAPEL_DE_LEITURA = "sas_leitura"
#: Uma das DUAS ações que o gatilho da 0072 deixa o sas_mcp gravar — esta só
#: sem ator; a outra é a chamada de tool (`mcp_ferramenta_chamada`).
_ACAO_DE_VERIFICACAO = "mcp_verificacao_papeis"
#: Ações que só a API grava e que a linha do tempo padrão mostra: com o
#: prefixo `mcp_` liberado, o sas_mcp forjava "a administradora X revogou a
#: conexão Y" (revisão final de 26/10). O gatilho tem de recusar cada uma —
#: inclusive as do e-mail da conta de IA (routes/mcp_emails_ia.py), que dizem
#: quem pode aprovar conexão.
_ACOES_SO_DA_API = (
    "mcp_token_emitido", "mcp_token_revogado", "mcp_oauth_aprovado", "mcp_oauth_recusado",
    "mcp_email_ia_cadastrado", "mcp_email_ia_confirmado", "mcp_email_ia_removido",
)
#: Um ator que não existe, para a sonda da verificação atribuída a alguém.
_ATOR_QUE_NAO_EXISTE = "00000000-0000-4000-8000-00000000000a"
_SO_O_MINIMO = {"Prefer": "return=minimal"}


# ─── A lista branca, lida das migrations ─────────────────────────────────


@dataclass(frozen=True)
class Comando:
    """Um comando de um .sql, como o psql o separa."""

    #: Sem comentários e com o espaço normalizado; literal entre aspas
    #: simples vira `''`, identificador entre aspas duplas perde as aspas e
    #: cada corpo `$tag$…$tag$` vira `$$`.
    texto: str
    #: O conteúdo cru de cada corpo `$tag$`, na ordem: o plpgsql de um DO ou de
    #: uma função. É onde mora o SQL dinâmico (`EXECUTE '…'`), que o texto não
    #: mostra — e que a auditoria lê à parte.
    corpos: tuple[str, ...] = ()
    #: Cada literal '…' do comando, com as aspas, na ordem — o que o texto
    #: troca por `''`. A auditoria só olha valor onde ele decide alguma coisa
    #: (o teto de duração do login do MCP).
    literais: tuple[str, ...] = ()


_RE_ESPECIAL = re.compile(r"--|/\*|['\";$]")
_RE_TAG_DOLAR = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")


def _e_de_identificador(c: str) -> bool:
    return c.isalnum() or c in "_$"


def _fim_do_comentario_de_bloco(sql: str, i: int) -> int:
    """Onde termina o `/* … */` que começa em i (o Postgres aninha)."""
    profundidade, i = 1, i + 2
    while i < len(sql) and profundidade:
        if sql.startswith("/*", i):
            profundidade, i = profundidade + 1, i + 2
        elif sql.startswith("*/", i):
            profundidade, i = profundidade - 1, i + 2
        else:
            i += 1
    return i


def _fim_do_literal(sql: str, i: int) -> int:
    """Onde termina o literal '…' que começa em i (depois da aspa final).

    `''` é aspa escapada; num E'…', a barra invertida também escapa.
    """
    com_barra = i > 0 and sql[i - 1] in "eE" and (i < 2 or not _e_de_identificador(sql[i - 2]))
    i += 1
    while i < len(sql):
        if (com_barra and sql[i] == "\\") or sql.startswith("''", i):
            i += 2
        elif sql[i] == "'":
            return i + 1
        else:
            i += 1
    return i


def _tag_dolar(sql: str, i: int) -> str | None:
    """A tag `$…$` que abre um corpo em i, ou None (`$1`, `a$b`)."""
    if i > 0 and _e_de_identificador(sql[i - 1]):
        return None
    m = _RE_TAG_DOLAR.match(sql, i)
    return m.group() if m else None


def _separar(sql: str) -> list[Comando]:
    """Os comandos de um .sql: o `;` só separa fora de comentário, de literal,
    de identificador entre aspas e de corpo `$tag$`.

    Uma sequência de regex erra onde o psql acerta — um apóstrofo num
    comentário (`-- it's`) abria um literal falso que engolia o GRANT da linha
    de baixo, e o que o leitor não vê a auditoria não recusa.
    """
    comandos: list[Comando] = []
    texto: list[str] = []
    corpos: list[str] = []
    literais: list[str] = []

    def fechar() -> None:
        normalizado = " ".join("".join(texto).split())
        if normalizado:
            comandos.append(Comando(normalizado, tuple(corpos), tuple(literais)))
        texto.clear()
        corpos.clear()
        literais.clear()

    i, n = 0, len(sql)
    while i < n:
        m = _RE_ESPECIAL.search(sql, i)
        if m is None:
            texto.append(sql[i:])
            break
        texto.append(sql[i : m.start()])
        i, achado = m.start(), m.group()
        if achado == "--":
            fim = sql.find("\n", i)
            i = n if fim < 0 else fim
            texto.append(" ")
        elif achado == "/*":
            i = _fim_do_comentario_de_bloco(sql, i)
            texto.append(" ")
        elif achado == "'":
            fim = _fim_do_literal(sql, i)
            literais.append(sql[i:fim])
            i = fim
            texto.append("''")
        elif achado == '"':
            fim = i + 1
            while fim < n and (sql[fim] != '"' or sql.startswith('""', fim)):
                fim += 2 if sql.startswith('""', fim) else 1
            texto.append(sql[i + 1 : fim].replace('""', '"'))
            i = fim + 1
        elif achado == ";":
            fechar()
            i += 1
        elif tag := _tag_dolar(sql, i):
            fim = sql.find(tag, i + len(tag))
            corpos.append(sql[i + len(tag) : n if fim < 0 else fim])
            texto.append(" $$ ")
            i = n if fim < 0 else fim + len(tag)
        else:
            texto.append("$")
            i += 1
    fechar()
    return comandos


def _sem_comentarios(sql: str) -> str:
    """O texto sem comentários e com os literais INTEIROS — no corpo de um DO
    ou de uma função, é dentro do literal que mora o SQL dinâmico."""
    saida: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        m = _RE_ESPECIAL.search(sql, i)
        if m is None:
            saida.append(sql[i:])
            break
        saida.append(sql[i : m.start()])
        i, achado = m.start(), m.group()
        if achado == "--":
            fim = sql.find("\n", i)
            i = n if fim < 0 else fim
            saida.append(" ")
        elif achado == "/*":
            i = _fim_do_comentario_de_bloco(sql, i)
            saida.append(" ")
        elif achado == "'":
            fim = _fim_do_literal(sql, i)
            saida.append(sql[i:fim])
            i = fim
        elif (tag := _tag_dolar(sql, i)) and (fim := sql.find(tag, i + len(tag))) >= 0:
            saida.append(sql[i : fim + len(tag)])
            i = fim + len(tag)
        else:
            saida.append(achado)
            i += 1
    return "".join(saida)


def _comandos(sql: str) -> Iterator[str]:
    """Os textos dos comandos de `_separar`, um por vez."""
    for comando in _separar(sql):
        yield comando.texto


def _papeis(texto: str) -> set[str]:
    return {p.strip().lower() for p in texto.split(",")}


def _colunas(texto: str | None) -> set[str]:
    return {c.strip().lower() for c in (texto or "").split(",") if c.strip()}


_RE_GRANT_SELECT = re.compile(
    r"GRANT SELECT(?: ?\((?P<colunas>[^)]*)\))? ON (?:TABLE )?(?P<tabela>[\w.]+) TO (?P<papeis>.+)",
    re.IGNORECASE,
)
_RE_REVOKE_TUDO = re.compile(
    r"REVOKE .+ ON ALL TABLES IN SCHEMA public FROM (?P<papeis>.+)", re.IGNORECASE
)
_RE_REVOKE = re.compile(
    r"REVOKE (?:GRANT OPTION FOR )?(?P<privilegio>SELECT|ALL(?: PRIVILEGES)?)"
    r"(?: ?\((?P<colunas>[^)]*)\))? ON (?:TABLE )?(?P<tabela>[\w.]+) FROM (?P<papeis>.+)",
    re.IGNORECASE,
)
_RE_DROP = re.compile(
    r"DROP (?:MATERIALIZED VIEW|VIEW|TABLE) (?:IF EXISTS )?(?P<nomes>[\w., ]+?)(?: CASCADE| RESTRICT)?",
    re.IGNORECASE,
)


def lista_branca(
    dir_migrations: Path = DIR_MIGRATIONS, papel: str = _PAPEL_DE_LEITURA
) -> dict[str, frozenset[str] | None]:
    """{tabela: colunas} que `papel` pode ler, aplicando as migrations em ordem.

    `None` no lugar das colunas = GRANT na tabela inteira. Só os .sql de UP:
    é o estado de um banco com tudo aplicado.
    """
    estado: dict[str, set[str] | None] = {}
    arquivos = sorted(p for p in dir_migrations.iterdir() if _PADRAO_UP.match(p.name))
    for caminho in arquivos:
        for comando in _comandos(caminho.read_text(encoding="utf-8")):
            _aplicar(estado, comando, papel.lower())
    return {t: (None if c is None else frozenset(c)) for t, c in estado.items()}


def _aplicar(estado: dict[str, set[str] | None], comando: str, papel: str) -> None:
    # O GRANT morre com o objeto: a view materializada recriada volta sem ele (foi
    # o que a 0065 e a 0068 fizeram, antes de ela estar na lista). Sem isto o
    # leitor continuaria dizendo que o MCP a lê, e a tool só cairia no 42501.
    if m := _RE_DROP.fullmatch(comando):
        for nome in m["nomes"].split(","):
            estado.pop(nome.strip().lower().removeprefix("public."), None)
        return
    if m := _RE_GRANT_SELECT.fullmatch(comando):
        if papel not in _papeis(m["papeis"]):
            return
        tabela = m["tabela"].lower().removeprefix("public.")
        colunas = _colunas(m["colunas"])
        if not colunas:
            estado[tabela] = None
        elif estado.get(tabela, set()) is not None:
            estado.setdefault(tabela, set()).update(colunas)  # type: ignore[union-attr]
        return
    if m := _RE_REVOKE_TUDO.fullmatch(comando):
        if papel in _papeis(m["papeis"]):
            estado.clear()
        return
    if m := _RE_REVOKE.fullmatch(comando):
        if papel not in _papeis(m["papeis"]):
            return
        tabela = m["tabela"].lower().removeprefix("public.")
        colunas = _colunas(m["colunas"])
        atual = estado.get(tabela)
        if not colunas or atual is None:
            estado.pop(tabela, None)
        else:
            atual.difference_update(colunas)
            if not atual:
                estado.pop(tabela, None)


# ─── A auditoria das migrations ──────────────────────────────────────────
#
# O leitor da lista branca é estreito de propósito: só entende `GRANT SELECT
# (colunas) ON tabela TO sas_leitura`. Estreito só é seguro se o que ele NÃO
# entende falhar em vez de passar calado — na revisão de 24/10, 14 de 17
# concessões perigosas (UPDATE ao sas_leitura, `GRANT sas_service TO
# sas_leitura`, SELECT a PUBLIC, ALTER FUNCTION … SECURITY DEFINER) passavam
# por todos os testes. Daqui para baixo, todo comando que concede, revoga ou
# altera algo dos papéis do MCP — ou de PUBLIC, de quem o sas_mcp herda tudo —
# tem de ser uma das formas abaixo, ou vira problema.

#: O login do postgrest_mcp (0071). Não recebe privilégio de objeto nenhum: é
#: NOINHERIT, membro só do sas_mcp, e toda a força dele está em NÃO alcançar o
#: sas_service — um pertencimento a mais aqui desfaria o login próprio.
LOGIN_DO_MCP = "autenticador_mcp"
#: Os papéis que o PostgREST do MCP é ou pode virar: o que se lê, o efetivo e o
#: login. Toda regra de concessão vale para os três.
PAPEIS_DO_MCP: tuple[str, ...] = ("sas_leitura", "sas_mcp", LOGIN_DO_MCP)
_VIGIADOS: frozenset[str] = frozenset({*PAPEIS_DO_MCP, "public"})
_MIGRATIONS_DO_MCP: tuple[str, ...] = ("0071_", "0072_", "0076_")
DIR_INIT = Path(__file__).resolve().parent.parent.parent / "infra" / "postgres" / "init"

#: Prefixos de tabela que nunca entram na lista branca, além das nomeadas em
#: TABELAS_PROIBIDAS: conversa, credencial, token, OAuth (0073), cantina,
#: captação, disparo e e-mail (o das contas de IA inclusive) — e `v_`, porque
#: view comum roda com o privilégio do dono (0071).
PREFIXOS_PROIBIDOS: tuple[str, ...] = (
    "chat_", "usuario_", "token_", "oauth_", "cantina", "cardapio", "pedido_", "direito_",
    "candidato_", "conquista_", "prova_externa", "disparo", "email_", "v_",
)

#: As views que a lista branca pode ter, pelo nome (0076). A trava do prefixo
#: `v_` continua para todas as outras, e a destas tem de sobreviver à auditoria
#: estrutural (`_views`): não podem rodar com o privilégio do dono, ou seja, são
#: materializadas (ler não roda a consulta de baixo: o GRANT por coluna vale como
#: numa tabela) ou têm `security_invoker` (leem com o privilégio de quem chama).
VIEWS_DA_LISTA_BRANCA: frozenset[str] = frozenset({"v_candidato_externo_por_nome", "v_prova_externa_resumo"})

#: O que entra PELO NOME apesar do prefixo. As três tabelas da captação, e só as
#: três (0076): uma tabela de contato do candidato, amanhã, nasce proibida e pede
#: uma decisão, em vez de herdar a liberação destas.
LIBERADAS_PELO_NOME: frozenset[str] = frozenset(
    {"prova_externa", "candidato_externo", "conquista_externa", *VIEWS_DA_LISTA_BRANCA}
)


def tabela_proibida(tabela: str) -> bool:
    """A tabela nunca entra na lista branca: a régua nominal e a dos prefixos."""
    if tabela in TABELAS_PROIBIDAS:
        return True
    return tabela not in LIBERADAS_PELO_NOME and tabela.startswith(PREFIXOS_PROIBIDOS)

#: As colunas que o sas_mcp insere na trilha (0072): nem `id` nem `ocorrido_em`.
COLUNAS_DA_TRILHA: frozenset[str] = frozenset(
    {"acao", "canal", "ator_tipo", "ator_id", "recurso", "ip", "detalhe", "request_id"}
)

#: Os únicos pertencimentos que tocam os papéis do MCP, como (papel, membro) —
#: e a opção que cada um leva. O login TROCA para o sas_mcp e não herda dele:
#: `WITH INHERIT FALSE` é exigido, porque no Postgres 16 a herança é do
#: pertencimento. O `authenticator` da API, membro do sas_service, fica de fora
#: de propósito: foi o login do MCP na primeira versão da 0071.
PERTENCIMENTOS_PERMITIDOS: dict[tuple[str, str], str | None] = {
    ("sas_leitura", "sas_mcp"): None,
    ("sas_mcp", LOGIN_DO_MCP): "with inherit false",
}

#: O que um ALTER ROLE pode pôr em sas_leitura e sas_mcp: todos tiram poder.
_ATRIBUTOS_QUE_TIRAM_PODER: frozenset[str] = frozenset(
    {"nologin", "nosuperuser", "nocreatedb", "nocreaterole", "noreplication", "nobypassrls", "inherit", "noinherit"}
)
#: E no login: entra (LOGIN), mas sem herdar nem poder de cluster, e sem senha
#: no arquivo — `PASSWORD NULL` é a única forma; a senha de verdade a operação
#: define fora do git (0071). INHERIT, que no sas_mcp é exigido, aqui é proibido.
_ATRIBUTOS_DO_LOGIN: frozenset[str] = frozenset(
    {"login", "noinherit", "nosuperuser", "nocreatedb", "nocreaterole", "noreplication", "nobypassrls"}
)
#: O teto de conexões do login: positivo e pequeno. `-1` (sem teto) tiraria a
#: proteção do max_connections que a API divide.
_TETO_DE_CONEXOES_DO_LOGIN = 20
#: E o de duração de comando: positivo, em segundos, até o prazo das tools.
_TETO_DE_DURACAO_DO_LOGIN_S = 90

#: A única SECURITY DEFINER que o MCP executa. Lê credencial como dono — por
#: isso é só dele, e de mais ninguém (0072).
_DEFINER_DO_MCP = "mcp_conferir_token"

_RE_PAPEL_DO_MCP = re.compile(r"\b(?:sas_leitura|sas_mcp|autenticador_mcp)\b", re.IGNORECASE)
_RE_ON = re.compile(r"\s+ON\s+", re.IGNORECASE)
_RE_GRANT = re.compile(
    r"GRANT (?P<o_que>.+?) TO (?P<quem>.+?)"
    r"(?P<opcao> WITH (?:GRANT|ADMIN|INHERIT|SET) (?:OPTION|TRUE|FALSE))?(?: GRANTED BY [\w$]+)?",
    re.IGNORECASE,
)
_RE_REVOKE_GERAL = re.compile(
    r"REVOKE (?:(?:GRANT|ADMIN|INHERIT|SET) OPTION FOR )?(?P<o_que>.+?) FROM (?P<quem>.+?)"
    r"(?: GRANTED BY [\w$]+)?(?: (?:CASCADE|RESTRICT))?",
    re.IGNORECASE,
)


def _menciona_papel_do_mcp(texto: str) -> bool:
    return _RE_PAPEL_DO_MCP.search(texto) is not None


def _alcanca_vigiado(texto: str) -> bool:
    """Cita papel do MCP ou a palavra `public` (papel OU schema: na dúvida, conta)."""
    return _menciona_papel_do_mcp(texto) or re.search(r"\bpublic\b", texto, re.IGNORECASE) is not None


def _destinatarios(texto: str) -> set[str]:
    """Os papéis de uma lista como `a, GROUP b, PUBLIC`, em minúsculas."""
    return {p.strip().lower().removeprefix("group ").strip() for p in texto.split(",") if p.strip()}


def auditar_migrations(
    dir_migrations: Path = DIR_MIGRATIONS, dir_init: Path | None = DIR_INIT
) -> list[str]:
    """O que nas migrations (e no init dos papéis) foge das formas permitidas.

    Vazia = toda concessão que toca os papéis do MCP, ou PUBLIC, é uma das que
    a lista branca, o verificador e os testes entendem. Cada problema diz o
    arquivo, o porquê e o começo do comando. Ups e downs: um .down que
    concedesse algo valeria enquanto a migration dele estivesse revertida.
    """
    lidos = [
        (caminho, _separar(caminho.read_text(encoding="utf-8")))
        for caminho in sorted(dir_migrations.iterdir())
        if _PADRAO_UP.match(caminho.name) or _PADRAO_DOWN.match(caminho.name)
    ]
    ups = [c for caminho, comandos in lidos if _PADRAO_UP.match(caminho.name) for c in comandos]
    views = _views(ups)
    problemas: list[str] = []
    for caminho, comandos in lidos:
        down = _PADRAO_DOWN.match(caminho.name) is not None
        do_mcp = caminho.name.startswith(_MIGRATIONS_DO_MCP)
        for comando in comandos:
            for motivo in _auditar_comando(comando, down=down, do_mcp=do_mcp, views=views):
                problemas.append(f"{caminho.name}: {motivo} — {comando.texto[:160]}")
    problemas += [f"funções: {motivo}" for motivo in auditar_funcoes(ups)]
    if dir_init is not None and dir_init.is_dir():
        problemas += _auditar_init(dir_init)
    return problemas


_RE_VIEW_CRIADA = re.compile(
    r"CREATE (?:OR REPLACE )?(?P<materializada>MATERIALIZED )?VIEW (?:IF NOT EXISTS )?(?:public\.)?"
    r"(?P<nome>\w+)(?P<resto>.*)",
    re.IGNORECASE,
)
_RE_VIEW_OPCOES = re.compile(
    r"ALTER (?:VIEW|TABLE) (?:IF EXISTS )?(?:public\.)?(?P<nome>\w+) (?P<verbo>SET|RESET) \((?P<opcoes>[^()]*)\)",
    re.IGNORECASE,
)
_RE_VIEW_RENOMEADA = re.compile(
    r"ALTER (?:MATERIALIZED )?VIEW (?:IF EXISTS )?(?:public\.)?(?P<nome>\w+) RENAME TO (?P<novo>\w+)",
    re.IGNORECASE,
)
_RE_VIEW_DERRUBADA = re.compile(
    r"DROP (?:MATERIALIZED )?VIEW (?:IF EXISTS )?(?P<nomes>[\w., ]+?)(?: CASCADE| RESTRICT)?", re.IGNORECASE
)
#: `security_invoker` ligado. Sem valor também liga; valor entre aspas (o texto
#: normalizado o troca por `''`) não casa e fica como dono: na dúvida, fecha.
_RE_INVOKER_LIGADO = re.compile(r"\bsecurity_invoker\b(?:\s*=\s*(?:true|on|yes|1)\b|\s*(?=,|$))", re.IGNORECASE)


def _invoker_ligado(opcoes: str) -> bool:
    return any(_RE_INVOKER_LIGADO.search(opcao.strip()) for opcao in opcoes.split(","))


def _views(comandos: Iterable[Comando]) -> frozenset[str]:
    """As views que rodam com o privilégio do DONO depois de todas as migrations.

    É o que torna um GRANT perigoso: elas expõem o que leem, mesmo sem GRANT nas
    tabelas de baixo (0071). Não entram as materializadas (ler não roda a consulta
    de baixo) nem as de `security_invoker` ligado. Vale o ÚLTIMO comando de cada
    view: `CREATE OR REPLACE VIEW` sem o `WITH` DESLIGA a opção — provado num
    Postgres 16 descartável em 30/10 —, e por isso quem recria a view do rodapé da
    captação sem repetir a opção reprova aqui, no GRANT da 0076.
    """
    do_dono: dict[str, bool] = {}
    for comando in comandos:
        texto = comando.texto
        if m := _RE_VIEW_CRIADA.match(texto):
            cabecalho = re.split(r"\sAS\s", m["resto"], maxsplit=1, flags=re.IGNORECASE)[0]
            opcoes = re.search(r"\bWITH \((?P<opcoes>[^()]*)\)", cabecalho, re.IGNORECASE)
            invoker = opcoes is not None and _invoker_ligado(opcoes["opcoes"])
            do_dono[m["nome"].lower()] = not m["materializada"] and not invoker
        elif m := _RE_VIEW_OPCOES.fullmatch(texto):
            nome = m["nome"].lower()
            if nome in do_dono and "security_invoker" in m["opcoes"].lower():
                do_dono[nome] = m["verbo"].upper() == "RESET" or not _invoker_ligado(m["opcoes"])
        elif m := _RE_VIEW_RENOMEADA.fullmatch(texto):
            if m["nome"].lower() in do_dono:
                do_dono[m["novo"].lower()] = do_dono.pop(m["nome"].lower())
        elif m := _RE_VIEW_DERRUBADA.fullmatch(texto):
            for nome in m["nomes"].split(","):
                do_dono.pop(nome.strip().lower().removeprefix("public."), None)
    return frozenset(nome for nome, dono in do_dono.items() if dono)


def _auditar_init(dir_init: Path) -> list[str]:
    """O init roda uma vez, antes das migrations: papel do MCP não mora nele, e
    nada ali concede a PUBLIC — de quem o sas_mcp herda."""
    problemas: list[str] = []
    for caminho in sorted(p for p in dir_init.iterdir() if p.is_file()):
        # Texto cru, e não o separador de SQL: é shell, e um `psql -c '…'`
        # esconderia o comando dentro de um "literal". Só a linha de
        # comentário de shell sai; o resto conta, comentário de SQL inclusive.
        texto = re.sub(r"(?m)^\s*#.*$", "", caminho.read_text(encoding="utf-8"))
        if _menciona_papel_do_mcp(texto):
            problemas.append(f"{caminho.name}: o init cita papel do MCP")
        for m in re.finditer(r"\bTO\s+(?:[\w$\"]+\s*,\s*)*PUBLIC\b", texto, re.IGNORECASE):
            trecho = " ".join(texto[max(0, m.start() - 80) : m.end()].split())
            problemas.append(f"{caminho.name}: concessão a PUBLIC no init — …{trecho}")
    return problemas


def _auditar_comando(c: Comando, *, down: bool, do_mcp: bool, views: frozenset[str]) -> list[str]:
    motivos = [m for corpo in c.corpos for m in _auditar_corpo(corpo, do_mcp=do_mcp)]
    texto, baixo = c.texto, c.texto.lower()
    if baixo.startswith("comment on "):
        return motivos
    if re.match(r"(?:create (?:or replace )?|alter )function ", baixo) and re.search(
        r"\bset\s+(?:role|session_authorization)\b", baixo
    ):
        # `SET role = …` no cabeçalho troca o papel enquanto a função roda. O
        # login próprio do MCP (0071) não alcança o sas_service, mas função
        # nenhuma do schema precisa disto, e numa SECURITY DEFINER o papel que
        # vale é o do dono: é a porta que o login próprio fechou, reaberta.
        motivos.append("função que troca de papel (SET role no cabeçalho)")
    if baixo.startswith("grant "):
        motivos += _auditar_grant(texto, down=down, views=views)
    elif baixo.startswith("revoke "):
        motivos += _auditar_revoke(texto)
    elif baixo.startswith("alter default privileges"):
        motivos += _auditar_default_privileges(baixo)
    elif m := re.match(r"(alter|create|drop) (?:role|user|group) (?:if exists )?([\w$]+)(.*)", baixo):
        motivos += _auditar_papel(m[1], m[2], m[3].strip(), down=down, literais=c.literais)
    elif down and re.fullmatch(
        r"drop owned by (?:sas_leitura|sas_mcp|autenticador_mcp)(?: cascade| restrict)?", baixo
    ):
        pass
    elif _menciona_papel_do_mcp(baixo):
        # ALTER TABLE … OWNER TO sas_mcp, CREATE POLICY … TO sas_mcp, SET ROLE…
        motivos.append("cita papel do MCP fora das formas permitidas")
    return motivos


def _auditar_grant(texto: str, *, down: bool, views: frozenset[str]) -> list[str]:
    m = _RE_GRANT.fullmatch(texto)
    if m is None:
        return ["GRANT que a auditoria não entende"] if _alcanca_vigiado(texto) else []
    quem = _destinatarios(m["quem"])
    partes = _RE_ON.split(m["o_que"], maxsplit=1)
    if len(partes) == 1:
        opcao = " ".join(m["opcao"].split()).lower() if m["opcao"] else None
        return _auditar_pertencimento(_destinatarios(partes[0]), quem, opcao=opcao)
    if not quem & _VIGIADOS:
        return []
    if len(quem) > 1:
        return ["GRANT a papel do MCP ou a PUBLIC vai a UM papel por comando"]
    if m["opcao"]:
        return ["WITH GRANT OPTION a papel do MCP ou a PUBLIC"]
    return _forma_permitida(partes[0], partes[1], next(iter(quem)), down=down, views=views)


def _auditar_pertencimento(papeis: set[str], membros: set[str], *, opcao: str | None) -> list[str]:
    """`GRANT papel TO membro`: só os pares da 0071, cada um com a opção dele.

    Conta o par que TOCA um papel do MCP de qualquer lado — o papel do MCP
    dentro de outro (herdaria o outro) ou outro papel dentro do do MCP (o
    `authenticator` da API dentro do sas_mcp foi a primeira versão da 0071). E
    PUBLIC como membro, de quem o sas_mcp herda tudo.
    """
    pares = {
        (p, q) for p in papeis for q in membros if p in PAPEIS_DO_MCP or q in _VIGIADOS
    }
    motivos = []
    for p, q in sorted(pares):
        if (p, q) not in PERTENCIMENTOS_PERMITIDOS:
            motivos.append(f"pertencimento fora do permitido: {q} passaria a ser membro de {p}")
        elif opcao != PERTENCIMENTOS_PERMITIDOS[(p, q)]:
            esperada = PERTENCIMENTOS_PERMITIDOS[(p, q)] or "nenhuma"
            motivos.append(f"pertencimento {q} ∈ {p} com opção {opcao or 'nenhuma'}; a da 0071 é {esperada}")
    return motivos


def _forma_permitida(
    privilegios: str, objeto: str, papel: str, *, down: bool, views: frozenset[str]
) -> list[str]:
    priv, obj = " ".join(privilegios.split()), " ".join(objeto.split())
    if papel == _PAPEL_DE_LEITURA:
        if m := re.fullmatch(r"SELECT ?\((?P<colunas>[^()]+)\)", priv, re.IGNORECASE):
            t = re.fullmatch(r"(?:TABLE )?(?:public\.)?(?P<tabela>\w+)", obj, re.IGNORECASE)
            if t is None:
                return ["GRANT SELECT ao sas_leitura é numa tabela por comando"]
            tabela, colunas = t["tabela"].lower(), _colunas(m["colunas"])
            motivos = []
            if tabela_proibida(tabela):
                motivos.append(f"{tabela} nunca entra na lista branca")
            if tabela in views:
                motivos.append(f"{tabela} é view: roda com o privilégio do dono e expõe o que lê (0071)")
            if tabela == "aluno" and (proibidas := colunas & set(COLUNAS_PROIBIDAS_DO_ALUNO)):
                motivos.append(f"coluna proibida de aluno: {', '.join(sorted(proibidas))}")
            if proibidas := colunas & set(COLUNAS_PROIBIDAS_DA_CAPTACAO.get(tabela, ())):
                motivos.append(f"coluna proibida da captação: {', '.join(sorted(proibidas))}")
            return motivos
        if priv.upper() == "SELECT":
            return ["GRANT SELECT ao sas_leitura é por coluna: coluna nova nasce invisível (0071)"]
        if priv.upper() == "USAGE" and obj.lower() == "schema public":
            return []
    elif papel == "sas_mcp":
        m = re.fullmatch(r"INSERT ?\((?P<colunas>[^()]+)\)", priv, re.IGNORECASE)
        if m and re.fullmatch(r"(?:TABLE )?(?:public\.)?evento_auditoria", obj, re.IGNORECASE):
            fora = _colunas(m["colunas"]) - COLUNAS_DA_TRILHA
            return [f"INSERT do sas_mcp na trilha fora das colunas da 0072: {', '.join(sorted(fora))}"] if fora else []
        if priv.upper() == "USAGE" and re.fullmatch(
            r"SEQUENCE (?:public\.)?evento_auditoria_id_seq", obj, re.IGNORECASE
        ):
            return []
        if priv.upper() == "EXECUTE" and re.fullmatch(
            rf"FUNCTION (?:public\.)?{_DEFINER_DO_MCP} ?\(text\)", obj, re.IGNORECASE
        ):
            return []
    elif papel == "public" and down:
        # O .down devolve a função ao ACL de fábrica do Postgres.
        if priv.upper() == "EXECUTE" and re.fullmatch(r"FUNCTION (?:public\.)?\w+ ?\([^()]*\)", obj, re.IGNORECASE):
            return []
    return [f"concessão a {papel} fora das formas permitidas"]


def _auditar_revoke(texto: str) -> list[str]:
    """REVOKE só tira — mas o que o leitor da lista branca não modela faria a
    régua dele divergir do banco, sem erro nenhum."""
    m = _RE_REVOKE_GERAL.fullmatch(texto)
    if m is None:
        return ["REVOKE que a auditoria não entende"] if _alcanca_vigiado(texto) else []
    partes = _RE_ON.split(m["o_que"], maxsplit=1)
    if len(partes) == 1 or not _destinatarios(m["quem"]) & _VIGIADOS:
        return []
    priv, obj = " ".join(partes[0].split()).lower(), " ".join(partes[1].split())
    toca_select = re.search(r"\b(?:select|all)\b", priv) is not None
    sozinho = re.fullmatch(r"all(?: privileges)?|select(?: ?\([^()]*\))?", priv) is not None
    if toca_select and not sozinho:
        return ["REVOKE que mistura SELECT com outro privilégio: o leitor da lista branca não o modela"]
    formas = (
        r"ALL (?:TABLES|SEQUENCES|FUNCTIONS|ROUTINES) IN SCHEMA public",
        r"(?:TABLE |SEQUENCE )?(?:public\.)?\w+",
        r"SCHEMA public",
        r"(?:FUNCTION|ROUTINE) (?:public\.)?\w+ ?\([^()]*\)",
    )
    if any(re.fullmatch(f, obj, re.IGNORECASE) for f in formas):
        return []
    return ["REVOKE de papel do MCP ou de PUBLIC numa forma que o leitor não modela (um objeto por comando)"]


def _auditar_default_privileges(baixo: str) -> list[str]:
    if _menciona_papel_do_mcp(baixo):
        return ["ALTER DEFAULT PRIVILEGES cita papel do MCP: tabela nova nasce invisível ao MCP (0071)"]
    m = re.search(r"\bgrant\b.*?\bto\b(?P<quem>.*)$", baixo)
    if m and "public" in _destinatarios(m["quem"].replace("with grant option", "")):
        return ["ALTER DEFAULT PRIVILEGES … TO PUBLIC: o sas_mcp herda de PUBLIC"]
    return []


def _auditar_papel(
    verbo: str, nome: str, resto: str, *, down: bool, literais: tuple[str, ...] = ()
) -> list[str]:
    if nome not in PAPEIS_DO_MCP:
        # `CREATE ROLE x ROLE sas_mcp` põe o sas_mcp DENTRO de x, herdando
        # tudo de x; `ALTER GROUP x ADD USER sas_mcp`, idem.
        return ["papel alheio ganha relação com papel do MCP"] if _menciona_papel_do_mcp(resto) else []
    if verbo == "drop":
        return [] if down else ["DROP de papel do MCP fora de um .down"]
    if verbo == "create":
        # O login também: nasce NOLOGIN, e o LOGIN vem num ALTER à vista.
        return [] if resto == "nologin" else ["papel do MCP nasce NOLOGIN e nada mais"]
    if resto == "reset all":
        return []
    if nome == LOGIN_DO_MCP:
        return _auditar_alter_do_login(resto, literais)
    if resto and set(resto.split()) <= _ATRIBUTOS_QUE_TIRAM_PODER:
        return []
    return ["ALTER ROLE em papel do MCP só tira poder (NOLOGIN, NOSUPERUSER, …) ou faz RESET ALL"]


_RE_DURACAO = re.compile(r"'\s*(\d+)\s*(ms|s|min)?\s*'")
_EM_SEGUNDOS = {"ms": 0.001, "s": 1.0, "min": 60.0, None: 0.001}


def _auditar_alter_do_login(resto: str, literais: tuple[str, ...]) -> list[str]:
    """O ALTER ROLE do login do MCP: os atributos da 0071, ou o teto de duração.

    Fora disso, nada — e é aqui que mora o que o login próprio fecha: `SET role
    = …`, `SET pgrst.db_anon_role = …` ou `SET pgrst.jwt_secret = …` no papel de
    login (o PostgREST lê `pgrst.*` dali com PGRST_DB_CONFIG ligado), senha
    escrita no arquivo, INHERIT, poder de cluster.
    """
    if re.fullmatch(r"set statement_timeout (?:=|to) ''", resto):
        valor = _RE_DURACAO.fullmatch(literais[0]) if len(literais) == 1 else None
        segundos = int(valor[1]) * _EM_SEGUNDOS[valor[2]] if valor else 0.0
        if 0 < segundos <= _TETO_DE_DURACAO_DO_LOGIN_S:
            return []
        return [
            f"statement_timeout do login do MCP: positivo e até {_TETO_DE_DURACAO_DO_LOGIN_S} s, "
            "o prazo das tools — zero o desligaria"
        ]
    motivos: list[str] = []
    sobra = re.sub(r"\bpassword null\b", " ", resto)
    if teto := re.search(r"\bconnection limit (-?\d+)\b", sobra):
        if not 0 < int(teto[1]) <= _TETO_DE_CONEXOES_DO_LOGIN:
            motivos.append(
                f"CONNECTION LIMIT do login do MCP: de 1 a {_TETO_DE_CONEXOES_DO_LOGIN} — sem teto, um "
                "postgrest_mcp comprometido esgotaria as conexões que a API divide"
            )
        sobra = sobra.replace(teto[0], " ")
    if not set(sobra.split()) <= _ATRIBUTOS_DO_LOGIN:
        motivos.append(
            "ALTER ROLE no login do MCP: só LOGIN NOINHERIT sem poder de cluster, CONNECTION LIMIT, "
            "PASSWORD NULL (a senha a operação define fora do git), RESET ALL ou SET statement_timeout"
        )
    return motivos


def _auditar_corpo(corpo: str, *, do_mcp: bool) -> list[str]:
    """O corpo de um DO ou de uma função, com os literais — onde vai o SQL
    dinâmico. Concessão ali escaparia de toda a leitura acima, então não pode."""
    codigo = _sem_comentarios(corpo).lower()
    motivos: list[str] = []
    if _menciona_papel_do_mcp(codigo) and not do_mcp:
        motivos.append("corpo $$ cita papel do MCP fora da 0071/0072")
    if re.search(r"\bgrant\b", codigo):
        motivos.append("GRANT dentro de corpo $$ (DO, função, SQL dinâmico) escapa da auditoria: escreva-o como comando")
    if re.search(r"\balter\s+default\s+privileges\b", codigo):
        motivos.append("ALTER DEFAULT PRIVILEGES dentro de corpo $$")
    if re.search(r"\b(?:set|reset)\s+(?:local\s+|session\s+)?role\b|\bsession\s+authorization\b|\bset_config\s*\(\s*'role'", codigo):
        motivos.append(
            "troca de papel em corpo $$: é o SET ROLE de dentro de uma requisição que o login próprio do "
            "MCP fecha (0071) — numa função, ele volta com o papel de quem a chamar"
        )
    for m in re.finditer(r"\b(alter|create)\s+(?:role|user|group)\b(?P<resto>[^;]*)", codigo):
        if m[1] == "alter" and not re.search(r"\breset\s+all\b", m["resto"]):
            motivos.append("ALTER ROLE em corpo $$ que não é RESET ALL")
        if m[1] == "create" and not re.fullmatch(r"\s+[\w$]+\s+nologin\s*", m["resto"]):
            motivos.append("CREATE ROLE em corpo $$ que não é só NOLOGIN")
    # SQL dinâmico só com o comando INTEIRO à vista: `EXECUTE 'GR' || 'ANT …'`
    # ou `format('%s …', 'GRANT …')` não têm a palavra GRANT para a regra de
    # cima pegar. Vale um literal só (puro ou como molde do format), sem %s —
    # %I e %L citam identificador e valor, não montam comando.
    for m in re.finditer(r"\bexecute\b(?!\s+(?:function|procedure)\b)", codigo):
        resto = codigo[m.end() :]
        molde = re.match(r"\s*format\s*\(\s*'((?:[^']|'')*)'\s*[,)]", resto)
        puro = re.match(r"\s*'((?:[^']|'')*)'\s*(?:;|using\b|into\b|$)", resto)
        if molde is None and puro is None:
            motivos.append("SQL dinâmico que a auditoria não lê: EXECUTE só de literal inteiro ou format('…')")
        elif molde is not None and re.search(r"%(?:\d+\$)?-?\d*s", molde[1]):
            motivos.append("SQL dinâmico com %s no molde: o comando vem de fora do literal — use %I/%L")
    return motivos


@dataclass
class _Funcao:
    definer: bool
    gatilho: bool
    dinamica: bool
    #: PUBLIC executa — o padrão do Postgres para toda função nova.
    publica: bool = True
    #: Executável por GRANT direto a sas_leitura ou sas_mcp.
    do_mcp: bool = False


def _nomes_de_funcao(texto: str) -> list[str | None]:
    """Os nomes de `f(a, b), public.g()` — None no que não for nome simples."""
    partes, profundidade, atual = [], 0, []
    for ch in texto:
        profundidade += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and profundidade == 0:
            partes.append("".join(atual))
            atual = []
        else:
            atual.append(ch)
    partes.append("".join(atual))
    nomes = []
    for parte in partes:
        m = re.fullmatch(r"\s*(?:public\.)?(\w+)\s*(?:\([^()]*\))?\s*(?:cascade|restrict)?\s*", parte, re.IGNORECASE)
        nomes.append(m[1].lower() if m else None)
    return nomes


def auditar_funcoes(comandos: Iterable[Comando]) -> list[str]:
    """Aplica as migrations em ordem e devolve o que o sas_mcp alcançaria.

    O Postgres dá EXECUTE a PUBLIC — e portanto ao sas_mcp — em toda função
    nova; CREATE OR REPLACE mantém o ACL, DROP + CREATE o devolve a PUBLIC, e
    ALTER FUNCTION … SECURITY DEFINER muda a função sem recriá-la. No fim, é
    problema toda função que o sas_mcp executa e que: é SECURITY DEFINER (roda
    como o dono, o superusuário das migrations) sem ser a mcp_conferir_token;
    ou tem SQL dinâmico — uma injeção ali é SQL arbitrário dentro de uma
    requisição do MCP. O login próprio (0071) limita o estrago ao que o sas_mcp
    alcança, mas é a única camada que sobraria: com o `authenticator` da API
    como login, como na primeira versão da 0071, era `SET ROLE sas_service`.
    Função de gatilho fica de fora: não é chamável por RPC.
    """
    funcoes: dict[str, _Funcao] = {}
    motivos: list[str] = []
    for c in comandos:
        baixo = c.texto.lower()
        if m := re.match(r"create (or replace )?function (?:public\.)?(\w+)\s*\(", baixo):
            antiga = funcoes.get(m[2]) if m[1] else None
            funcoes[m[2]] = _Funcao(
                definer=re.search(r"\bsecurity definer\b", baixo) is not None,
                gatilho=re.search(r"\breturns (?:trigger|event_trigger)\b", baixo) is not None,
                dinamica=any(re.search(r"\bexecute\b", _sem_comentarios(x).lower()) for x in c.corpos),
                publica=antiga.publica if antiga else True,
                do_mcp=antiga.do_mcp if antiga else False,
            )
        elif baixo.startswith(("create function ", "create or replace function ")):
            motivos.append(f"CREATE FUNCTION de nome que a auditoria não entende: {c.texto[:120]}")
        elif m := re.match(r"drop function (?:if exists )?(.+)$", baixo):
            for nome in _nomes_de_funcao(m[1]):
                if nome is None:
                    motivos.append(f"DROP FUNCTION que a auditoria não entende: {c.texto[:120]}")
                else:
                    funcoes.pop(nome, None)
        elif m := re.match(r"alter function (?:public\.)?(\w+)\s*(?:\([^()]*\))?\s*(.*)$", baixo):
            if m[1] not in funcoes:
                motivos.append(f"ALTER FUNCTION de função que a auditoria não viu criar: {c.texto[:120]}")
                continue
            if re.search(r"\bsecurity definer\b", m[2]):
                funcoes[m[1]].definer = True
            if re.search(r"\bsecurity invoker\b", m[2]):
                funcoes[m[1]].definer = False
            if novo := re.search(r"\brename to (\w+)", m[2]):
                funcoes[novo[1]] = funcoes.pop(m[1])
        elif baixo.startswith("alter function "):
            motivos.append(f"ALTER FUNCTION que a auditoria não entende: {c.texto[:120]}")
        elif m := re.match(
            r"(grant|revoke) .+? on (?:(?:function|routine) (?P<alvos>.+?)|all (?:functions|routines) in schema public)"
            r" (?:to|from) (?P<quem>.+?)(?: with grant option)?(?: granted by [\w$]+)?(?: cascade| restrict)?$",
            baixo,
        ):
            quem = _destinatarios(m["quem"])
            nomes = list(funcoes) if m["alvos"] is None else _nomes_de_funcao(m["alvos"])
            for nome in nomes:
                if nome not in funcoes:
                    continue
                if "public" in quem:
                    funcoes[nome].publica = m[1] == "grant"
                if quem & set(PAPEIS_DO_MCP):
                    funcoes[nome].do_mcp = m[1] == "grant"
    for nome, f in sorted(funcoes.items()):
        if f.gatilho or not (f.publica or f.do_mcp):
            continue
        quem_executa = "PUBLIC" if f.publica else "o sas_mcp, por GRANT"
        if f.definer and nome != _DEFINER_DO_MCP:
            motivos.append(f"{nome}: SECURITY DEFINER que {quem_executa} executa — revogue de PUBLIC na migration que a cria")
        if nome == _DEFINER_DO_MCP and f.publica:
            motivos.append(f"{nome}: PUBLIC ainda executa — a 0072 revoga")
        if f.dinamica:
            motivos.append(f"{nome}: SQL dinâmico (EXECUTE) numa função que {quem_executa} executa")
    return motivos


# ─── O relatório ─────────────────────────────────────────────────────────


@dataclass
class Relatorio:
    conferidas: int = 0
    falhas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def secao(self, titulo: str) -> None:
        print(f"\n── {titulo} ──")

    def ok(self, texto: str) -> None:
        self.conferidas += 1
        print(f"  ok     {texto}")

    def falha(self, texto: str) -> None:
        self.conferidas += 1
        self.falhas.append(texto)
        print(f"  FALHA  {texto}")

    def aviso(self, texto: str) -> None:
        self.avisos.append(texto)
        print(f"  aviso  {texto}")

    def conferir(self, condicao: bool, texto: str, detalhe: str = "") -> None:
        if condicao:
            self.ok(texto)
        else:
            self.falha(f"{texto}{f' — {detalhe}' if detalhe else ''}")


# ─── HTTP ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Resposta:
    status: int
    #: O `code` do corpo de erro do PostgREST: SQLSTATE do Postgres (42501 =
    #: permissão negada) ou PGRSTnnn do próprio PostgREST.
    codigo: str | None
    mensagem: str
    corpo: Any

    def resumo(self) -> str:
        return f"HTTP {self.status}" + (f" {self.codigo}: {self.mensagem}" if self.codigo else "")

    @property
    def negada(self) -> bool:
        return self.codigo == "42501"


class PostgREST:
    def __init__(self, url: str, http: httpx.Client) -> None:
        self.url = url.rstrip("/")
        self._http = http

    def pedir(
        self,
        metodo: str,
        caminho: str,
        *,
        params: dict[str, str] | None = None,
        corpo: Any = None,
        cabecalhos: dict[str, str] | None = None,
    ) -> Resposta:
        r = self._http.request(
            metodo,
            f"{self.url}/{caminho.lstrip('/')}",
            params=params,
            json=corpo,
            headers={"Accept": "application/json", **(cabecalhos or {})},
        )
        try:
            dados = r.json() if r.content else None
        except ValueError:
            dados = r.text
        codigo = mensagem = None
        if r.status_code >= 400 and isinstance(dados, dict):
            codigo = str(dados.get("code")) if dados.get("code") is not None else None
            mensagem = str(dados.get("message") or "")
        return Resposta(r.status_code, codigo, mensagem or "", dados)

    def ler(self, tabela: str, colunas: Iterable[str]) -> Resposta:
        return self.pedir("GET", tabela, params={"select": ",".join(colunas), "limit": "1"})

    def superficie(self) -> tuple[dict[str, set[str]], set[str]] | None:
        """({tabela: colunas}, {função}) que o OpenAPI deste PostgREST mostra.

        O OpenAPI do PostgREST segue o privilégio do papel na TABELA (lista a
        tabela se o papel tem qualquer privilégio nela), mas mostra todas as
        colunas — é o que permite saber quais colunas ficaram de fora. None se
        o OpenAPI estiver desligado.
        """
        r = self.pedir("GET", "/")
        if r.status != 200 or not isinstance(r.corpo, dict) or "paths" not in r.corpo:
            return None
        tabelas: dict[str, set[str]] = {}
        funcoes: set[str] = set()
        definicoes = r.corpo.get("definitions") or {}
        for caminho in r.corpo["paths"]:
            nome = caminho.strip("/")
            if not nome:
                continue
            if nome.startswith("rpc/"):
                funcoes.add(nome.removeprefix("rpc/"))
            else:
                tabelas[nome] = set((definicoes.get(nome) or {}).get("properties") or {})
        return tabelas, funcoes


def _jwt_forjado(papel: str) -> str:
    """HS256 com chave aleatória: o que um MCP comprometido tentaria mandar."""

    def b64(dados: bytes) -> str:
        return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()

    cabeca = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    carga = b64(json.dumps({"role": papel}).encode())
    assinatura = hmac.new(secrets.token_bytes(32), f"{cabeca}.{carga}".encode(), hashlib.sha256)
    return f"{cabeca}.{carga}.{b64(assinatura.digest())}"


def _evento(papel: str, *, ator_tipo: str = "coordenador") -> dict[str, Any]:
    """O evento que o verificador grava: a forma de evento do MCP (gatilho da
    0072), com uma ação que ninguém confunde com chamada de verdade."""
    return {
        "acao": _ACAO_DE_VERIFICACAO,
        "canal": "mcp",
        "ator_tipo": ator_tipo,
        "recurso": "scripts/verificar_papeis_do_mcp",
        "detalhe": {"papel": papel},
    }


def _contraditorio(coluna: str) -> dict[str, str]:
    """`coluna IS NULL AND coluna IS NOT NULL`: filtro de qualquer tipo que não
    alcança linha nenhuma. A coluna tem de ter SELECT — senão o 42501 seria do
    filtro, e não do UPDATE ou do DELETE que se quer sondar."""
    return {"and": f"({coluna}.is.null,{coluna}.not.is.null)"}


# ─── As conferências ─────────────────────────────────────────────────────


def conferir_migrations(rel: Relatorio) -> None:
    rel.secao("0 · As migrations: só concessão de forma conhecida aos papéis do MCP e a PUBLIC")
    problemas = auditar_migrations()
    for problema in problemas:
        rel.falha(problema)
    if not problemas:
        rel.ok("auditar_migrations: nada fora das formas permitidas")


def conferir_conexao(rel: Relatorio, mcp: PostgREST) -> bool:
    """O PostgREST do MCP fala com o banco? Sem isso, nada abaixo diz nada.

    O caso comum é a senha do autenticador_mcp: a 0071 cria o login SEM senha,
    e quem a define é a operação (docker-compose.yml) — até lá, e depois de um
    down + up da 0071, o login é recusado. O PostgREST 12.2.3 não fica
    respondendo 503 nesse caso: ele SAI (código 1, "password authentication
    failed" no log), e a porta recusa a conexão (provado num Postgres
    descartável em 25/10).
    """
    rel.secao("0b · O PostgREST do MCP conecta no banco, com o login dele")
    dica = (
        "a senha do autenticador_mcp foi definida (ALTER ROLE … PASSWORD, docker-compose.yml), é a mesma "
        "do POSTGREST_MCP_PASSWORD do postgrest_mcp, e ele foi reiniciado depois? Sem senha ele sai"
    )
    try:
        r = mcp.pedir("GET", "/")
    except httpx.TransportError as erro:
        rel.falha(f"o PostgREST do MCP não responde ({type(erro).__name__}) — {dica}")
        return False
    conecta = r.status != 503
    rel.conferir(conecta, "conecta (o login do postgrest_mcp entra no Postgres)", f"{r.resumo()} — {dica}")
    return conecta


def conferir_lista_branca(
    rel: Relatorio, mcp: PostgREST, branca: dict[str, frozenset[str] | None]
) -> None:
    rel.secao(f"1 · O sas_mcp lê a lista branca ({len(branca)} tabelas, das migrations)")
    if not branca:
        rel.falha("nenhum GRANT SELECT ao sas_leitura nas migrations — a 0071 foi aplicada?")
    for tabela, colunas in sorted(branca.items()):
        if colunas is None:
            r = mcp.pedir("GET", tabela, params={"limit": "1"})
            rel.conferir(r.status == 200, f"{tabela} (tabela inteira)", r.resumo())
            continue
        r = mcp.ler(tabela, sorted(colunas))
        rel.conferir(r.status == 200, f"{tabela} ({len(colunas)} colunas)", r.resumo())


def conferir_nada_alem(
    rel: Relatorio,
    mcp: PostgREST,
    branca: dict[str, frozenset[str] | None],
    superficie: tuple[dict[str, set[str]], set[str]] | None,
    superficie_da_api: tuple[dict[str, set[str]], set[str]] | None,
) -> None:
    rel.secao("2 · E nada além dela")
    if superficie is None:
        rel.aviso("o OpenAPI do PostgREST do MCP não respondeu: a superfície não foi conferida")
    else:
        tabelas_visiveis, funcoes = superficie
        # evento_auditoria aparece porque o sas_mcp tem INSERT nela (0072);
        # que ele não a LÊ, a conferência das proibidas abaixo prova.
        permitidas = set(branca) | {"evento_auditoria"}
        sobra = sorted(set(tabelas_visiveis) - permitidas)
        rel.conferir(
            not sobra,
            f"o sas_mcp enxerga {len(tabelas_visiveis)} tabelas, todas da lista branca",
            f"fora dela: {', '.join(sobra)}",
        )
        estranhas = sorted(funcoes - FUNCOES_EXECUTAVEIS)
        rel.conferir(
            not estranhas,
            f"executa só {', '.join(sorted(funcoes & FUNCOES_EXECUTAVEIS)) or 'nada'}",
            f"funções a mais: {', '.join(estranhas)} — se for SECURITY DEFINER, "
            "revogue de PUBLIC; se for INVOKER, acrescente a FUNCOES_EXECUTAVEIS",
        )

    # Coluna por coluna: o que a tabela tem e a lista branca não concede. As
    # colunas vêm do OpenAPI da API (enxerga tudo) ou, sem ela, do do MCP —
    # que lista as colunas todas das tabelas que ele enxerga.
    origem = superficie_da_api or superficie
    todas_as_colunas = origem[0] if origem else {}
    if not todas_as_colunas:
        rel.aviso("sem OpenAPI, as colunas de fora da lista branca não foram conferidas")
    for tabela, colunas in sorted(branca.items()):
        if colunas is None:
            continue
        fora = sorted(todas_as_colunas.get(tabela, set()) - colunas)
        abertas = [c for c in fora if not mcp.ler(tabela, [c]).negada]
        rel.conferir(
            not abertas,
            f"{tabela}: colunas fora da lista dão 42501 ({len(fora)})",
            f"lidas sem GRANT: {', '.join(abertas)}",
        )

    for coluna in COLUNAS_PROIBIDAS_DO_ALUNO:
        r = mcp.ler("aluno", [coluna])
        rel.conferir(r.negada, f"aluno.{coluna} → 42501", r.resumo())
    r = mcp.pedir("GET", "aluno", params={"select": "*", "limit": "1"})
    rel.conferir(r.negada, "aluno?select=* → 42501 (GRANT por coluna)", r.resumo())

    proibidas = set(TABELAS_PROIBIDAS)
    if superficie_da_api is not None:
        # Com a API, toda tabela que existe e não está na lista também entra.
        proibidas |= set(superficie_da_api[0]) - set(branca)
    for tabela in sorted(proibidas):
        colunas_da_tabela = (superficie_da_api[0] if superficie_da_api else {}).get(tabela)
        coluna = sorted(colunas_da_tabela)[0] if colunas_da_tabela else "*"
        r = mcp.ler(tabela, [coluna])
        if r.codigo == "PGRST205":
            rel.aviso(f"{tabela}: não existe neste banco (nada a vazar; confira o nome)")
            continue
        rel.conferir(r.negada, f"{tabela} → 42501", r.resumo())


#: Recusa que não é 42501 mas também prova que não há escrita: coluna gerada
#: só aceita DEFAULT (o Postgres recusa antes de conferir o privilégio).
_SO_DEFAULT = "428C9"
#: Idem para view que agrega, que não é atualizável: o Postgres recusa no
#: reescritor, antes de olhar privilégio. Só vale para as VIEWS_DA_LISTA_BRANCA
#: (a 0076 deixou a do rodapé da captação com security_invoker): numa tabela,
#: este código seria uma sonda que não exercitou privilégio nenhum.
_VIEW_NAO_ATUALIZAVEL = "55000"


def conferir_sem_escrita(
    rel: Relatorio,
    mcp: PostgREST,
    branca: dict[str, frozenset[str] | None],
    colunas_de: dict[str, set[str]],
    api: PostgREST | None,
) -> None:
    """Escrita em TODA tabela que o sas_mcp enxerga, coluna por coluna.

    INSERT e UPDATE têm GRANT por coluna, então uma sonda numa coluna só não
    prova nada da vizinha: com UPDATE concedido em classificacao_aluno, o
    PATCH do MCP dava 204 e a versão anterior desta seção (que só olhava
    nota, aluno e a trilha) saía com 0 falhas (revisão de 24/10). Nenhuma
    sonda alcança linha: INSERT de lote vazio (`?columns=c` com `[]` — o
    comando roda, o privilégio é conferido, nada é gravado) e UPDATE/DELETE com
    filtro contraditório. Tabela fora da lista branca não precisa disto: com
    qualquer privilégio nela, ela aparece no OpenAPI, e a seção 2 já falha.
    """
    rel.secao("3 · O sas_mcp não escreve em tabela nenhuma")
    if api is not None:
        controle = [
            api.pedir("POST", "nota", params={"columns": "pontuacao"}, corpo=[], cabecalhos=_SO_O_MINIMO),
            api.pedir("PATCH", "nota", params=_contraditorio("aluno_id"), corpo={"pontuacao": None}, cabecalhos=_SO_O_MINIMO),
            api.pedir("DELETE", "nota", params=_contraditorio("aluno_id"), cabecalhos=_SO_O_MINIMO),
        ]
        # O 42501 do MCP só prova falta de privilégio se a mesma sonda PASSA
        # onde há privilégio — senão seria o PostgREST nem montando o comando.
        rel.conferir(
            all(r.status in (201, 204) for r in controle),
            "controle: a mesma sonda passa no PostgREST da API (sas_service) sem tocar linha",
            "; ".join(r.resumo() for r in controle),
        )
    if not colunas_de:
        rel.aviso("sem OpenAPI, a sonda de escrita só cobre as colunas da lista branca")
    trilha_inteira = set(COLUNAS_DA_TRILHA) | {"id", "ocorrido_em"}
    for tabela in sorted(set(branca) | {"evento_auditoria"}):
        recusas = {_SO_DEFAULT} | ({_VIEW_NAO_ATUALIZAVEL} if tabela in VIEWS_DA_LISTA_BRANCA else set())
        legiveis = sorted(branca.get(tabela) or ())
        reserva = trilha_inteira if tabela == "evento_auditoria" else set(legiveis)
        todas = sorted(colunas_de.get(tabela) or reserva)
        abertas: list[str] = []
        for coluna in todas:
            r = mcp.pedir("POST", tabela, params={"columns": coluna}, corpo=[], cabecalhos=_SO_O_MINIMO)
            if tabela == "evento_auditoria" and coluna in COLUNAS_DA_TRILHA:
                if r.status != 201:
                    abertas.append(f"INSERT ({coluna}) é da 0072 e deu {r.resumo()}")
            elif not (r.negada or r.codigo in recusas):
                abertas.append(f"INSERT ({coluna}): {r.resumo()}")
        if legiveis:
            filtro = _contraditorio(legiveis[0])
            for coluna in todas:
                r = mcp.pedir("PATCH", tabela, params=filtro, corpo={coluna: None}, cabecalhos=_SO_O_MINIMO)
                if not (r.negada or r.codigo in recusas):
                    abertas.append(f"UPDATE ({coluna}): {r.resumo()}")
            r = mcp.pedir("DELETE", tabela, params=filtro, cabecalhos=_SO_O_MINIMO)
            if not (r.negada or r.codigo in recusas - {_SO_DEFAULT}):
                abertas.append(f"DELETE: {r.resumo()}")
            alcance = f"INSERT e UPDATE nas {len(todas)} colunas, DELETE"
        else:
            # Sem SELECT, todo filtro já volta 42501 e não existe sonda segura
            # de UPDATE/DELETE (sem filtro, ela apagaria a trilha). Quem prova
            # que não há GRANT de UPDATE/DELETE aqui é a seção 0.
            for metodo, corpo in (("PATCH", {"acao": "x"}), ("DELETE", None)):
                r = mcp.pedir(metodo, tabela, params={"id": "eq.-1"}, corpo=corpo, cabecalhos=_SO_O_MINIMO)
                if not r.negada:
                    abertas.append(f"{metodo}: {r.resumo()}")
            alcance = f"INSERT só nas {len(COLUNAS_DA_TRILHA)} colunas da 0072, de {len(todas)}; PATCH e DELETE"
        rel.conferir(not abertas, f"{tabela}: nenhuma escrita além da prevista ({alcance})", "; ".join(abertas))


def conferir_auditoria(rel: Relatorio, mcp: PostgREST) -> None:
    rel.secao("4 · A trilha: INSERT só com return=minimal, e só de evento do MCP")
    r = mcp.pedir("POST", "evento_auditoria", corpo=_evento("sas_mcp"), cabecalhos=_SO_O_MINIMO)
    rel.conferir(r.status == 201, "INSERT com Prefer: return=minimal → 201", r.resumo())
    r = mcp.pedir(
        "POST", "evento_auditoria", corpo=_evento("sas_mcp"), cabecalhos={"Prefer": "return=representation"}
    )
    rel.conferir(
        r.negada,
        "INSERT com return=representation (o padrão do postgrest-py) → 42501",
        r.resumo(),
    )
    datado = {**_evento("sas_mcp"), "ocorrido_em": "2000-01-01T00:00:00Z"}
    r = mcp.pedir("POST", "evento_auditoria", corpo=datado, cabecalhos=_SO_O_MINIMO)
    rel.conferir(r.negada, "INSERT com ocorrido_em (datar no passado) → 42501", r.resumo())
    # Cada sonda muda UMA coisa do evento válido e mantém o recurso do
    # verificador: se o gatilho faltar e ela passar, o que fica na trilha é
    # um evento que se lê como teste, nunca um login ou uma nota forjada. As
    # de ação da API vão sem ator e dizendo no detalhe que são sonda — uma
    # "revogação" que passasse não seria de conta nenhuma.
    sonda = {"papel": "sas_mcp", "sonda": "evento que o gatilho da 0072 tinha de recusar"}
    forjados = (
        ("canal fora do mcp (acesso)", {**_evento("sas_mcp"), "canal": "acesso"}),
        ("ação sem o prefixo mcp_", {**_evento("sas_mcp"), "acao": "verificacao_papeis_mcp"}),
        *(
            (f"ação que só a API grava ({acao})", {**_evento("sas_mcp"), "acao": acao, "detalhe": sonda})
            for acao in _ACOES_SO_DA_API
        ),
        ("verificação atribuída a uma conta", {**_evento("sas_mcp"), "ator_id": _ATOR_QUE_NAO_EXISTE}),
        ("ator_tipo que não é coordenador", _evento("sas_mcp", ator_tipo="sistema")),
        ("detalhe de 8 KB", {**_evento("sas_mcp"), "detalhe": {"x": "A" * 8192}}),
    )
    for rotulo, evento in forjados:
        r = mcp.pedir("POST", "evento_auditoria", corpo=evento, cabecalhos=_SO_O_MINIMO)
        rel.conferir(r.negada, f"o gatilho da 0072 recusa {rotulo} → 42501", r.resumo())


def conferir_token(rel: Relatorio, mcp: PostgREST, api: PostgREST | None) -> None:
    rel.secao("5 · mcp_conferir_token")
    r = mcp.pedir("POST", "rpc/mcp_conferir_token", corpo={"p_hash": secrets.token_hex(32)})
    rel.conferir(
        r.status == 200 and r.corpo == [],
        "o sas_mcp executa; hash desconhecido → conjunto vazio",
        r.resumo() if r.status != 200 else f"devolveu {r.corpo!r}",
    )
    token = os.environ.get("SAS_MCP_TOKEN", "").strip()
    if token:
        r = mcp.pedir(
            "POST",
            "rpc/mcp_conferir_token",
            corpo={"p_hash": hashlib.sha256(token.encode()).hexdigest()},
        )
        linhas = r.corpo if isinstance(r.corpo, list) else []
        rel.conferir(
            r.status == 200 and len(linhas) == 1,
            "SAS_MCP_TOKEN é reconhecido (uma linha)",
            r.resumo() if r.status != 200 else f"{len(linhas)} linhas",
        )
    if api is not None:
        r = api.pedir("POST", "rpc/mcp_conferir_token", corpo={"p_hash": secrets.token_hex(32)})
        rel.conferir(r.negada, "o sas_service (API) NÃO executa → 42501", r.resumo())


def conferir_jwt(rel: Relatorio, mcp: PostgREST) -> None:
    rel.secao("6 · Nenhum JWT troca o papel")
    r = mcp.pedir(
        "GET",
        "usuario_coordenacao",
        params={"select": "id", "limit": "1"},
        cabecalhos={"Authorization": f"Bearer {_jwt_forjado('sas_service')}"},
    )
    # Só PGRST300 ("Server lacks JWT secret") prova que não há segredo. Um
    # PGRST301 (assinatura inválida) também recusa ESTE token — mas diz que o
    # servidor tem um segredo, no env ou no banco (pgrst.jwt_secret com
    # PGRST_DB_CONFIG ligado), e um JWT assinado com ele troca o papel. Era
    # um aviso; com o segredo no banco, o verificador saía com 0 (revisão de
    # 24/10).
    rel.conferir(
        r.codigo == "PGRST300",
        "JWT forjado com role=sas_service → PGRST300: o PostgREST do MCP não tem segredo de JWT",
        f"{r.resumo()} — o servidor tem segredo de JWT (PGRST_JWT_SECRET, ou pgrst.jwt_secret no banco "
        "com PGRST_DB_CONFIG ligado): um JWT assinado com ele sai do sas_mcp",
    )


def conferir_api(rel: Relatorio, api: PostgREST) -> None:
    rel.secao("7 · O PostgREST da API continua igual")
    for tabela in ("ciclo", "usuario_coordenacao", "token_mcp", "evento_auditoria"):
        r = api.ler(tabela, ["id"])
        rel.conferir(r.status == 200, f"sas_service lê {tabela}", r.resumo())
    # ator_tipo 'sistema', que o gatilho da 0072 recusaria vindo do sas_mcp:
    # é a prova de que ele só confina o MCP, e não a API.
    r = api.pedir(
        "POST",
        "evento_auditoria",
        corpo=_evento("sas_service", ator_tipo="sistema"),
        cabecalhos={"Prefer": "return=representation"},
    )
    escreveu = r.status == 201 and isinstance(r.corpo, list) and bool(r.corpo)
    rel.conferir(
        escreveu,
        "sas_service escreve e lê de volta (INSERT com RETURNING), sem o gatilho do MCP no caminho",
        r.resumo(),
    )


# ─── As tools, pelo registro de verdade ──────────────────────────────────


class _Captura(logging.Handler):
    """Guarda os WARNING+ de qualquer logger durante uma chamada de tool.

    O registro devolve ao modelo uma mensagem genérica e manda a exceção para
    o log (docs/43 §3.2, invariante 6); dois leitores do domínio engolem a
    falha com um warning. É no log que o 42501 aparece.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.registros: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.registros.append(record)


def _descobrir_valores(cliente: Any) -> dict[str, Any]:
    """Ids de verdade para preencher argumentos, lidos pelo próprio sas_mcp."""

    def linhas(tabela: str, select: str, **opcoes: Any) -> list[dict[str, Any]]:
        consulta = cliente.table(tabela).select(select)
        for coluna, valor in (opcoes.get("eq") or {}).items():
            consulta = consulta.eq(coluna, valor)
        if "ordem" in opcoes:
            consulta = consulta.order(opcoes["ordem"], desc=True)
        return consulta.limit(opcoes.get("limite", 1)).execute().data or []

    v: dict[str, Any] = {"busca": "a"}
    ciclos = linhas("ciclo", "id", ordem="ordem", limite=2)
    if ciclos:
        v["ciclo_id"] = v["ciclo_id_a"] = ciclos[0]["id"]
        v["ciclo_id_b"] = ciclos[-1]["id"]
    simulados = linhas("simulado", "id, quiz_id", ordem="data_aplicacao", limite=20)
    if simulados:
        com_quiz = [s for s in simulados if s.get("quiz_id")]
        v["simulado_id"] = (com_quiz or simulados)[0]["id"]
        if len(simulados) >= 2:
            v["simulado_ids"] = [s["id"] for s in simulados[:2]]
    classificados = linhas("classificacao_aluno", "aluno_id", limite=2)
    if classificados:
        v["aluno_id"] = classificados[0]["aluno_id"]
        if len(classificados) >= 2:
            v["aluno_ids"] = [c["aluno_id"] for c in classificados]
        alunos = linhas("aluno", "matricula, nome", eq={"id": v["aluno_id"]})
        if alunos:
            v["matricula"] = alunos[0]["matricula"]
            # `buscar_aluno_por_nome` (exposta desde 26/10): a primeira palavra
            # de um nome de verdade, que acha pelo menos este aluno — o handler
            # recusa trecho com menos de duas letras.
            palavras = (alunos[0].get("nome") or "").split()
            if palavras and len(palavras[0]) >= 2:
                v["nome"] = palavras[0]
    turmas = linhas("turma", "id, sede_id")
    if turmas:
        v["turma_id"], v["sede_id"] = turmas[0]["id"], turmas[0]["sede_id"]
    reguas = linhas("criterio_classificacao", "slug", eq={"embutido": False, "ativo": True})
    if reguas:
        v["criterio"] = reguas[0]["slug"]
    ligacoes = linhas("questao_vestibular_topico", "questao_id, materia, topico_codigo")
    if ligacoes:
        v["questao_id"] = ligacoes[0]["questao_id"]
        v["materia"] = ligacoes[0]["materia"]
        v["topico"] = ligacoes[0]["topico_codigo"]
        questoes = linhas("questao_vestibular", "ano", eq={"id": v["questao_id"]})
        if questoes:
            v["ano_desde"] = v["ano_ate"] = questoes[0]["ano"]
    # A captação (0076): cada leitura aqui já é o sas_mcp lendo o que a lista
    # branca lhe deu. Sem linha, a tool sai com o vazio, e o verificador diz.
    nomes = linhas("v_candidato_externo_por_nome", "nome_normalizado, ufs", ordem="conquistas_total")
    if nomes:
        v["nome_normalizado"] = nomes[0]["nome_normalizado"]
        if nomes[0].get("ufs"):
            v["uf"] = nomes[0]["ufs"][0]
        perfis = linhas("candidato_externo", "id", eq={"nome_normalizado": v["nome_normalizado"]})
        conquistas = (
            linhas("conquista_externa", "ano, prova_id", eq={"candidato_id": perfis[0]["id"]}, ordem="ano")
            if perfis
            else []
        )
        if perfis:
            v["candidato_id"] = perfis[0]["id"]
        if conquistas:
            v["ano"] = v["ano_min"] = v["ano_max"] = conquistas[0]["ano"]
            provas = linhas("prova_externa", "nome", eq={"id": conquistas[0]["prova_id"]})
            if provas:
                v["prova"] = provas[0]["nome"]
                v["provas"] = [provas[0]["nome"]]
    v["faixas"], v["publicos"], v["conquistas_min"] = ["ouro"], ["medio"], 1
    return v


def _valor_para(nome: str, esquema: dict[str, Any], valores: dict[str, Any]) -> Any:
    if nome in valores:
        return valores[nome]
    if esquema.get("enum"):
        return esquema["enum"][0]
    if esquema.get("type") == "boolean":
        # O contrário do padrão: é o outro ramo do handler que falta exercitar.
        return not bool(esquema.get("default", False))
    return None


def _chamadas(ferramenta: Any, valores: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any] | None]]:
    """Os argumentos de cada chamada: só os obrigatórios, cada opcional
    sozinho (cada filtro é um ramo do handler) e todos juntos."""
    from app.chat.ferramentas import parametros_do_handler

    aceitos, obrigatorios = parametros_do_handler(ferramenta.handler)
    props = ferramenta.propriedades
    minimos: dict[str, Any] = {}
    for nome in sorted(obrigatorios):
        valor = _valor_para(nome, props.get(nome) or {}, valores)
        if valor is None:
            yield f"sem valor para '{nome}'", None
            return
        minimos[nome] = valor
    vistos: list[dict[str, Any]] = []
    candidatas = [("obrigatórios", minimos)]
    opcionais = {
        nome: valor
        for nome in sorted(aceitos - obrigatorios)
        if (valor := _valor_para(nome, props.get(nome) or {}, valores)) is not None
    }
    candidatas += [(f"+{nome}", {**minimos, nome: valor}) for nome, valor in opcionais.items()]
    candidatas.append(("todos", {**minimos, **opcionais}))
    for rotulo, args in candidatas:
        if args not in vistos:
            vistos.append(args)
            yield rotulo, args


def _chaves_sensiveis(valor: Any, caminho: str = "") -> list[str]:
    achadas: list[str] = []
    if isinstance(valor, dict):
        for chave, filho in valor.items():
            onde = f"{caminho}.{chave}" if caminho else str(chave)
            if str(chave).replace("_", "").lower() in _CHAVES_SENSIVEIS:
                achadas.append(onde)
            achadas += _chaves_sensiveis(filho, onde)
    elif isinstance(valor, list):
        for i, filho in enumerate(valor):
            achadas += _chaves_sensiveis(filho, f"{caminho}[{i}]")
    return achadas


def _textos(valor: Any) -> Iterator[str]:
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for filho in valor.values():
            yield from _textos(filho)
    elif isinstance(valor, list):
        for filho in valor:
            yield from _textos(filho)


def conferir_ferramentas(
    rel: Relatorio, url_mcp: str, nomes: list[str] | None, proibidos: list[str]
) -> None:
    # Importados aqui: as conferências por HTTP não dependem do app.
    from postgrest import SyncPostgrestClient

    from app.chat.ferramentas import REGISTRO, Sessao

    rel.secao("8 · As tools expostas, pelo REGISTRO, contra o PostgREST do MCP")
    catalogo = {f.nome: f for f in REGISTRO.catalogo("coordenacao")}
    if nomes:
        alvo = []
        for nome in nomes:
            if nome in catalogo:
                alvo.append(catalogo[nome])
            else:
                rel.aviso(f"{nome}: não existe no registro da coordenação (ainda?)")
    else:
        alvo = [f for f in catalogo.values() if f.expor_no_mcp]
        if not alvo:
            rel.aviso("nenhuma tool com expor_no_mcp=True; passe os nomes com --so")

    cliente = SyncPostgrestClient(
        url_mcp.rstrip("/"),
        schema="public",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    valores = _descobrir_valores(cliente)
    sessao = Sessao(
        tipo="coordenador", usuario="coord:verificacao-mcp", papel="coordenador", nome="Verificação"
    )
    captura = _Captura()
    raiz = logging.getLogger()
    raiz.addHandler(captura)
    try:
        for ferramenta in alvo:
            for rotulo, args in _chamadas(ferramenta, valores):
                titulo = f"{ferramenta.nome} [{rotulo}]"
                if args is None:
                    rel.aviso(f"{titulo}: não sei preencher o argumento obrigatório")
                    continue
                captura.registros.clear()
                resultado = REGISTRO.despachar(sessao, ferramenta.nome, cliente, args)
                _julgar(rel, titulo, resultado, captura.registros, proibidos)
    finally:
        raiz.removeHandler(captura)


def _julgar(
    rel: Relatorio,
    titulo: str,
    resultado: dict[str, Any],
    registros: list[logging.LogRecord],
    proibidos: list[str],
) -> None:
    negadas, outras = [], []
    for registro in registros:
        erro = registro.exc_info[1] if registro.exc_info else None
        codigo = str(getattr(erro, "code", "") or "")
        texto = getattr(erro, "message", None) or (str(erro) if erro else registro.getMessage())
        (negadas if codigo == "42501" else outras).append(f"{codigo or type(erro).__name__}: {texto}")
    if negadas:
        rel.falha(f"{titulo}: permissão negada — {'; '.join(negadas)}")
        return
    sensiveis = _chaves_sensiveis(resultado)
    if sensiveis:
        rel.falha(f"{titulo}: devolveu coluna sensível em {', '.join(sensiveis)}")
        return
    vazados = sorted({p for p in proibidos for t in _textos(resultado) if p in t})
    if vazados:
        rel.falha(f"{titulo}: devolveu valor proibido ({', '.join(vazados)})")
        return
    if outras:
        rel.aviso(f"{titulo}: falhou, mas não por privilégio — {'; '.join(outras)}")
        return
    if "erro" in resultado:
        rel.ok(f"{titulo} (a tool respondeu erro de domínio: {str(resultado['erro'])[:90]})")
    else:
        # Quantos itens de lista voltaram, em qualquer profundidade: lista
        # vazia num banco com dados é sinal de que o caminho com embed nem
        # rodou. Resposta só de campos (obter_simulado) conta 0.
        rel.ok(f"{titulo} · {_itens(resultado)} itens")


def _itens(valor: Any) -> int:
    if isinstance(valor, list):
        return len(valor) + sum(_itens(v) for v in valor)
    if isinstance(valor, dict):
        return sum(_itens(v) for v in valor.values())
    return 0


# ─── Entrada ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--mcp", required=True, help="URL do PostgREST do MCP (papel sas_mcp)")
    p.add_argument("--api", help="URL do PostgREST da API (papel sas_service), opcional")
    p.add_argument("--ferramentas", action="store_true", help="roda as tools expostas pelo registro")
    p.add_argument("--so", help="nomes de tools, separados por vírgula (padrão: expor_no_mcp=True)")
    p.add_argument(
        "--valor-proibido",
        action="append",
        default=[],
        help="texto que nenhuma tool pode devolver (ex.: o e-mail plantado num aluno de teste)",
    )
    args = p.parse_args(argv)

    branca = lista_branca()
    rel = Relatorio()
    print(f"PostgREST do MCP: {args.mcp}" + (f" · da API: {args.api}" if args.api else ""))
    conferir_migrations(rel)
    with httpx.Client(timeout=60) as http:
        mcp = PostgREST(args.mcp, http)
        api = PostgREST(args.api, http) if args.api else None
        if not conferir_conexao(rel, mcp):
            print(f"\n{rel.conferidas} conferências · {len(rel.falhas)} falhas · {len(rel.avisos)} avisos")
            return 1
        superficie = mcp.superficie()
        superficie_da_api = api.superficie() if api else None
        if api is not None and superficie_da_api is None:
            rel.aviso("o OpenAPI do PostgREST da API não respondeu: tabelas fora da lista viram só as proibidas")
        # As colunas de cada tabela: do OpenAPI da API (enxerga tudo) ou, sem
        # ela, do do MCP — que lista as colunas todas das tabelas que enxerga.
        origem = superficie_da_api or superficie
        colunas_de = origem[0] if origem else {}
        conferir_lista_branca(rel, mcp, branca)
        conferir_nada_alem(rel, mcp, branca, superficie, superficie_da_api)
        conferir_sem_escrita(rel, mcp, branca, colunas_de, api)
        conferir_auditoria(rel, mcp)
        conferir_token(rel, mcp, api)
        conferir_jwt(rel, mcp)
        if api is not None:
            conferir_api(rel, api)
    if args.ferramentas:
        nomes = [n.strip() for n in args.so.split(",") if n.strip()] if args.so else None
        conferir_ferramentas(rel, args.mcp, nomes, args.valor_proibido)

    print(
        f"\n{rel.conferidas} conferências · {len(rel.falhas)} falhas · {len(rel.avisos)} avisos"
    )
    for falha in rel.falhas:
        print(f"  FALHA  {falha}")
    return 1 if rel.falhas else 0


if __name__ == "__main__":
    sys.exit(main())
