"""Trilha de auditoria — quem fez o quê (docs/15 §Etapa 8, migration 0022).

Regra da casa: **nunca** grave senha, hash, token ou corpo de mensagem aqui.
A tabela existe para responder "quem" e "quando", não para reproduzir conteúdo.

Toda gravação é melhor-esforço e engole a própria exceção: auditoria que
derruba a operação auditada é pior que auditoria ausente — um login não pode
falhar porque o INSERT do registro falhou. Consequência para quem LÊ: a falta
de um evento não prova que a ação não aconteceu.

A leitura também mora aqui (`consultar`, `nomes_dos_atores`): nasceu em
`routes/auditoria.py` e desceu quando a tool do assistente que conta "quem
mudou o quê" (docs/43 §4.3) passou a precisar da mesma consulta.

Desde 30/10 a tool também vai ao MCP, e o MCP não lê `evento_auditoria` nem
`usuario_coordenacao`: lê as duas views que a 0074 escreveu para ele —
`trilha_de_alteracoes` (`consultar(..., so_alteracoes=True)`) e
`nome_da_coordenacao` (`nomes_da_coordenacao`). A tela continua nas tabelas.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Any

from .observabilidade import request_id_atual

log = logging.getLogger("sas.auditoria")

# Entrar no sistema não muda nada. A linha do tempo é "o que foi criado ou
# alterado" (coordenação, 22/08); login fica gravado para forense, mas só
# aparece se pedirem.
ACOES_DE_ACESSO = ("login_ok", "login_falhou", "primeiro_acesso_bloqueado")

# Ler pelo MCP também não muda nada, e é uma linha por chamada de tool
# (app/mcp/auditoria_mcp.py, docs/43 §5.3): uma conversa com a IA de fora são
# dezenas de leituras, que soterrariam as edições humanas na linha do tempo
# padrão (revisão paralela de 25/10). Fica gravada e sai junto dos logins, só
# se pedirem. ⚠️ ESPELHO de `auditoria_mcp.ACAO_CHAMADA`, que é quem grava —
# tests/test_dominio_auditoria.py reprova se os dois divergirem.
ACAO_LEITURA_DO_MCP = "mcp_ferramenta_chamada"

#: O que não cria nem altera nada — e por isso fica fora da linha do tempo
#: padrão. Emitir ou revogar uma conexão do MCP é alteração, e fica dentro.
ACOES_SEM_ALTERACAO = (*ACOES_DE_ACESSO, ACAO_LEITURA_DO_MCP)

# Sem paginação em lugar nenhum do projeto (CLAUDE.md, armadilha 2) — aqui
# ela existe porque a tabela só cresce e a tela mostra a cauda recente.
LIMITE_MAXIMO = 500

_COLUNAS = "id, ocorrido_em, acao, canal, ator_tipo, ator_id, recurso, ip, detalhe, request_id"

#: A trilha que as tools leem, no chat e no MCP (migration 0074): só os canais
#: de alteração (nota, simulado, ciclo, canvas, criterio), sem `ip` nem
#: `request_id`, e o detalhe só com as chaves que a tool mostra. GRANT por
#: coluna não corta LINHA, e a tabela tem o canal `acesso`, com o e-mail
#: digitado no login que falhou — por isso a view, e não a tabela.
VIEW_DAS_ALTERACOES = "trilha_de_alteracoes"
_COLUNAS_DAS_ALTERACOES = "id, ocorrido_em, acao, canal, ator_tipo, ator_id, recurso, detalhe"

#: O nome de cada conta da coordenação e só ele (0074): sem e-mail, hash nem
#: papel. `usuario_coordenacao` continua fora da lista branca do MCP — é a
#: sonda de privilégio do boot dele (app/mcp/dados.py).
VIEW_DOS_NOMES = "nome_da_coordenacao"


def registrar(
    cliente,
    acao: str,
    *,
    canal: str = "acesso",
    ator_tipo: str | None = None,
    ator_id: str | None = None,
    recurso: str | None = None,
    ip: str | None = None,
    detalhe: dict[str, Any] | None = None,
) -> None:
    evento = {
        "acao": acao,
        # Compartimento da linha do tempo (migration 0025): acesso, nota,
        # simulado, ciclo, canvas, criterio, cantina, captacao, mcp. É texto
        # livre — quem grava diz de que assunto é o evento.
        "canal": canal,
        "ator_tipo": ator_tipo,
        "ator_id": ator_id,
        "recurso": recurso,
        "ip": ip,
        "detalhe": detalhe,
        "request_id": request_id_atual(),
    }
    # No log também: se a escrita no banco falhar, o evento não se perde.
    log.info("auditoria: %s", acao, extra={"usuario": ator_id, "rota": recurso})
    try:
        cliente.table("evento_auditoria").insert(evento).execute()
    except Exception:
        log.warning("não consegui gravar evento de auditoria", exc_info=True)


# ─── Leitura ──────────────────────────────────────────────────────────────


def consultar(
    cliente,
    *,
    canais: Sequence[str] | None = None,
    acao: str | None = None,
    recurso_prefixos: Sequence[str] | None = None,
    ator_ids: Sequence[str] | None = None,
    desde: str | None = None,
    ate: str | None = None,
    limite: int = 100,
    antes_de_id: int | None = None,
    incluir_logins: bool = False,
    so_alteracoes: bool = False,
) -> list[dict[str, Any]]:
    """Eventos da trilha, do mais recente para o mais antigo (por `id`).

    Os filtros se somam (E). Dentro de uma lista, basta casar um item (OU):
    `canais=["nota", "simulado"]` traz os dois. Lista vazia ou None = sem
    filtro naquele eixo.

      * `recurso_prefixos` — prefixo de `recurso`, por LIKE: `nota/<aluno_id>`
        pega as notas do aluno em todos os simulados. ⚠️ `%` e `_` dentro do
        prefixo são curinga do LIKE: quem monta o prefixo a partir de texto de
        fora o valida antes (id, slug), senão a busca alarga.
      * `desde`/`ate` — ISO 8601, inclusivos, em `ocorrido_em`.
      * `antes_de_id` — cursor: só eventos com `id` menor. Com `limite`
        eventos de volta, há mais; o próximo cursor é o `id` do último.
      * `incluir_logins` — sem ele, as `ACOES_SEM_ALTERACAO` saem: os logins
        e as leituras do MCP. Vale até para `acao` e `canais`: pedir
        `acao="login_ok"`, ou o canal `mcp` atrás das leituras, sem
        `incluir_logins` não as traz. O nome ficou o da rota, que já o
        recebia antes de o MCP existir.
      * `limite` — preso entre 1 e `LIMITE_MAXIMO`.

    Um item só por eixo vira `eq`/`like`, e não `in`/`or`: é a mesma
    requisição que a rota sempre fez.

    O que sai é a linha crua — com `ip` e, em `login_falhou`, o e-mail
    DIGITADO em `ator_id` (routes/auth.py). A tela é da coordenação; quem leva
    isto a um modelo lê com `so_alteracoes`:

      * `so_alteracoes` — lê `VIEW_DAS_ALTERACOES` (0074) em vez da tabela: os
        cinco canais de alteração, sem `ip` nem `request_id`, e o detalhe só
        com as chaves revisadas. É o que a tool lê no chat e no MCP — e o
        único jeito de o MCP ler a trilha, que ele não lê como tabela. Os
        filtros são os mesmos; canal fora dos cinco simplesmente não vem.
    """
    limite = min(max(1, limite), LIMITE_MAXIMO)
    origem, colunas = (VIEW_DAS_ALTERACOES, _COLUNAS_DAS_ALTERACOES) if so_alteracoes else ("evento_auditoria", _COLUNAS)
    q = cliente.table(origem).select(colunas).order("id", desc=True).limit(limite)
    if not incluir_logins:
        q = q.not_.in_("acao", list(ACOES_SEM_ALTERACAO))
    canais = [c for c in canais or () if c]
    if len(canais) == 1:
        q = q.eq("canal", canais[0])
    elif canais:
        q = q.in_("canal", canais)
    if acao:
        q = q.eq("acao", acao)
    ator_ids = [a for a in ator_ids or () if a]
    if len(ator_ids) == 1:
        q = q.eq("ator_id", ator_ids[0])
    elif ator_ids:
        q = q.in_("ator_id", ator_ids)
    prefixos = [p for p in recurso_prefixos or () if p]
    if len(prefixos) == 1:
        q = q.like("recurso", f"{prefixos[0]}%")
    elif prefixos:
        q = q.or_(",".join(_recurso_comeca_com(p) for p in prefixos))
    if desde:
        q = q.gte("ocorrido_em", desde)
    if ate:
        q = q.lte("ocorrido_em", ate)
    if antes_de_id is not None:
        q = q.lt("id", antes_de_id)
    return q.execute().data or []


def _recurso_comeca_com(prefixo: str) -> str:
    """Um ramo do `or=(…)` do PostgREST: `recurso.like."<prefixo>%"`.

    Entre aspas porque vírgula, ponto, dois-pontos e parênteses são a sintaxe
    do próprio `or`, e um deles dentro do prefixo partiria o filtro ao meio.
    Aspas e barra invertida do prefixo vão escapadas, que é como o PostgREST
    lê o valor entre aspas.
    """
    escapado = prefixo.replace("\\", "\\\\").replace('"', '\\"')
    return f'recurso.like."{escapado}%"'


def nomes_dos_atores(
    cliente, ids: Iterable[tuple[str | None, str | None]]
) -> tuple[dict[str, str], dict[str, bool]]:
    """Nome e "tem foto?" de cada ator, para a tela não mostrar uuid.

    `ids` são pares `(ator_tipo, ator_id)`, como a trilha os grava — é o tipo
    que diz em que tabela procurar: `coordenador` em `usuario_coordenacao`,
    `aluno` em `aluno`. Qualquer outro tipo fica sem nome.

    Só id de 36 caracteres vai à consulta: em `login_falhou` o `ator_id` é o
    e-mail digitado, e e-mail num `in` de coluna uuid derrubaria a leitura
    inteira. Melhor-esforço: um ator que não existe mais simplesmente não
    aparece no dicionário, e quem desenha cai no id.

    Devolve `(nomes, tem_foto)`, os dois por `ator_id`. `tem_foto` é sinal
    barato (uma coluna a mais no mesmo select) para o front decidir se vale
    buscar a foto.
    """
    coord_ids: set[str] = set()
    aluno_ids: set[str] = set()
    for tipo, ator_id in ids:
        if not _e_id_de_conta(ator_id):
            continue
        if tipo == "coordenador":
            coord_ids.add(ator_id)
        elif tipo == "aluno":
            aluno_ids.add(ator_id)

    nomes: dict[str, str] = {}
    tem_foto: dict[str, bool] = {}
    for tabela, alvo in (("usuario_coordenacao", coord_ids), ("aluno", aluno_ids)):
        if not alvo:
            continue
        linhas = (
            cliente.table(tabela)
            .select("id, nome, foto_perfil_storage")
            .in_("id", sorted(alvo))
            .execute()
            .data
            or []
        )
        for linha in linhas:
            nomes[linha["id"]] = linha["nome"]
            tem_foto[linha["id"]] = linha.get("foto_perfil_storage") is not None
    return nomes, tem_foto


def _e_id_de_conta(ator_id: str | None) -> bool:
    """Só id de 36 caracteres vai à consulta: em `login_falhou` o `ator_id` é o
    e-mail digitado, e e-mail num `in` de coluna uuid derrubaria a leitura."""
    return bool(ator_id) and len(ator_id) == 36


def nomes_da_coordenacao(cliente, ids: Iterable[str | None]) -> dict[str, str]:
    """O nome de cada conta da coordenação, por id — o "quem fez" das tools.

    Lê `VIEW_DOS_NOMES` (0074), e não `usuario_coordenacao`: as tools que dizem
    quem mudou a nota ou criou a régua rodam também no MCP, que não lê a
    tabela da credencial. Sem foto, que é sinal de tela (`nomes_dos_atores`).
    A mesma regra de id da tela; a conta que não existe mais fica fora do
    dicionário, e quem desenha decide o que dizer no lugar.
    """
    alvo = sorted({i for i in ids if _e_id_de_conta(i)})
    if not alvo:
        return {}
    linhas = cliente.table(VIEW_DOS_NOMES).select("id, nome").in_("id", alvo).execute().data or []
    return {linha["id"]: linha["nome"] for linha in linhas}
