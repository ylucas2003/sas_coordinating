"""Uma linha em `evento_auditoria` por chamada de tool do MCP (docs/43 §5.3).

Por que não `app.auditoria.registrar`: ele grava com o padrão do postgrest-py,
`return=representation`, que faz RETURNING e por isso exige SELECT na
tabela. O `sas_mcp` não tem — a trilha guarda IP e, em `login_falhou`, o
e-mail digitado (0072). E como o `registrar` engole a exceção, o evento do MCP
sumiria sem erro nenhum, só com um warning no log. Aqui o INSERT vai com
`returning=minimal`, que é o que o GRANT por coluna da 0072 permite.

O que vai: quem (a conta dona do token), por qual conexão (`mcp_token/<id>`),
qual ferramenta, o desfecho, a duração e quantas linhas saíram. O que NUNCA
vai: argumento de texto livre e resultado — a regra da casa em auditoria.py
("quem e quando, não conteúdo"), e aqui com mais razão: o resultado é dado de
menor que já saiu para um provedor de fora.

Melhor-esforço, como o `registrar`: auditoria que derruba a consulta é pior
que auditoria ausente. A mesma linha vai para o log antes do INSERT, para o
evento não se perder se o banco falhar — e o INSERT que falha é ERROR com
"[AÇÃO NECESSÁRIA]", porque é o controle do §5.3 falhando.

Por isso nada que vem de FORA chega cru ao INSERT: o gatilho da 0072 recusa
(42501) a linha inteira quando uma coluna passa do teto, e com o erro engolido
quem escolhesse o tamanho de um header lia a escola sem rastro na tela de
auditoria (revisão final de 26/10). Os dois campos de fora são o request id
(o X-Request-Id do cliente) e o IP (o X-Forwarded-For, atrás do proxy).
"""

from __future__ import annotations

import logging
from typing import Any

from postgrest.types import ReturnMethod

from ..observabilidade import request_id_aceito, request_id_atual
from .tokens import Identidade

log = logging.getLogger("sas.auditoria")

ACAO_CHAMADA = "mcp_ferramenta_chamada"
#: As duas da API (routes/mcp_tokens.py) e do script de operação.
ACAO_CONEXAO_EMITIDA = "mcp_token_emitido"
ACAO_CONEXAO_REVOGADA = "mcp_token_revogado"
#: Canal da linha do tempo (0025). Sem CHECK no banco: canal novo não pede
#: migration — mas precisa entrar em `routes/auditoria.CANAIS` para aparecer
#: no filtro da tela.
CANAL = "mcp"

#: O teto do gatilho da 0072 (`evento_auditoria_so_do_mcp`) para `ip`.
#: tests/test_migrations_do_mcp confere o número contra o SQL.
TETO_DO_IP = 64


def recurso_do_token(token_id: str) -> str:
    return f"mcp_token/{token_id}"


def ip_da_trilha(ip: str | None) -> str | None:
    """O IP como a trilha o aceita: só caracteres visíveis, até `TETO_DO_IP`.

    Atrás do proxy, o IP é o X-Forwarded-For que o uvicorn aceitou
    (MCP_IPS_DO_PROXY). Uma location do nginx sem `proxy_set_header
    X-Forwarded-For` deixa passar o que o cliente escreveu, e com `*` o uvicorn
    usa a entrada mais à esquerda: texto livre, sem teto. Cortar, e não
    descartar: um "IP" que não é IP na trilha é o sinal de que o proxy está
    errado.
    """
    visivel = "".join(c for c in ip or "" if "!" <= c <= "~")
    return visivel[:TETO_DO_IP] or None


def request_id_da_trilha(request_id: str | None) -> str:
    """O id que vai para a trilha: o recebido, se tem a forma aceita
    (`observabilidade.request_id_aceito`), senão o da requisição.

    O da requisição já passou pela mesma régua no middleware — ou é dele, ou
    é o "-" de fora de requisição (stdio) —, e é ele que costura o evento à
    linha de log.
    """
    return request_id_aceito(request_id) or request_id_atual()


def contar_linhas(resultado: Any) -> int:
    """Quantos registros saíram: cada dict DENTRO de uma lista conta um.

    Lista de número (as contagens de um histograma, os bullets de um insight)
    não conta — não é registro de ninguém. Sem lista de registros, o
    resultado inteiro é um registro só (`obter_aluno`, `tendencia_aluno`).
    """
    total = 0
    pilha = [resultado]
    while pilha:
        no = pilha.pop()
        if isinstance(no, list):
            total += sum(1 for item in no if isinstance(item, dict))
            pilha.extend(item for item in no if isinstance(item, (dict, list)))
        elif isinstance(no, dict):
            pilha.extend(v for v in no.values() if isinstance(v, (dict, list)))
    return total or 1


def registrar_chamada(
    cliente: Any,
    *,
    identidade: Identidade,
    ferramenta: str | None,
    desfecho: str,
    duracao_ms: int,
    linhas: int,
    ip: str | None = None,
    request_id: str | None = None,
) -> None:
    """Grava a chamada. Síncrono — quem está no event loop chama numa thread.

    `ferramenta` é None quando o nome pedido não está no catálogo: o nome é
    texto que o cliente escolheu, e texto livre não entra na trilha.
    """
    evento = {
        "acao": ACAO_CHAMADA,
        "canal": CANAL,
        # `coordenador` + o uuid da conta: é o par que a tela de auditoria
        # resolve em nome (routes/auditoria.py). O MCP se distingue pelo canal.
        "ator_tipo": "coordenador",
        "ator_id": identidade.coordenador_id,
        "recurso": recurso_do_token(identidade.token_id),
        "ip": ip_da_trilha(ip),
        "detalhe": {
            "ferramenta": ferramenta,
            "desfecho": desfecho,
            "duracaoMs": duracao_ms,
            "linhas": linhas,
        },
        "request_id": request_id_da_trilha(request_id),
    }
    extra = {
        "usuario": identidade.coordenador_id,
        "rota": evento["recurso"],
        "ferramenta": ferramenta,
        "desfecho": desfecho,
        "duracao_ms": duracao_ms,
    }
    log.info("auditoria: %s", ACAO_CHAMADA, extra=extra)
    try:
        cliente.table("evento_auditoria").insert(evento, returning=ReturnMethod.minimal).execute()
    except Exception:
        # ERROR, e não WARNING: a IA de fora leu e a tela de auditoria não vai
        # mostrar (docs/43 §5.3). A linha de cima, no log, é a única que ficou.
        log.error(
            "[AÇÃO NECESSÁRIA] não consegui gravar evento de auditoria do MCP: a chamada ficou só no log",
            exc_info=True,
            extra=extra,
        )
