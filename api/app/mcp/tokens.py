"""O token do MCP: opaco, guardado só como sha256 (migration 0072, docs/43 §5.3).

Nunca JWT, de propósito. Um JWT pediria a JWT_SECRET_KEY no processo do MCP —
e com ela ele assinaria sessão de coordenação na API. Opaco, o MCP não guarda
segredo nenhum: calcula o sha256 do que recebeu e pergunta ao banco pela RPC
`mcp_conferir_token`. E as duas portas ficam separadas por construção:
`get_current_user` recusa o token do MCP (não decodifica como JWT), e um JWT
de sessão nunca abre o MCP (não está em `token_mcp`).

Usado pelos DOIS processos — a API emite (`gerar`) e o MCP confere
(`conferir`) —, por isso nada aqui importa o SDK do MCP.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from typing import Any

from ..auth import PAPEIS_DE_COORDENACAO

#: O começo de todo token. Público de propósito: é o que deixa um scanner de
#: segredo (o do GitHub, por exemplo) reconhecer um token vazado num commit, e
#: o que deixa esta conferência descartar lixo sem ir ao banco.
PREFIXO_DO_TOKEN = "sas_mcp_"  # noqa: S105 — formato público, não segredo

#: `secrets.token_urlsafe(32)`: 32 bytes aleatórios em base64url, 43 caracteres.
_BYTES_ALEATORIOS = 32
_FORMATO = re.compile(r"sas_mcp_[A-Za-z0-9_-]{43}")

#: O que a tela mostra para reconhecer o token: "sas_mcp_AbCd". Quatro
#: caracteres do segredo ficam à vista (24 dos 256 bits); o CHECK da 0072
#: aceita até 20.
TAMANHO_DO_PREFIXO_VISIVEL = len(PREFIXO_DO_TOKEN) + 4


@dataclass(frozen=True)
class Identidade:
    """Quem está do outro lado do MCP: a conta da coordenação dona do token."""

    token_id: str
    coordenador_id: str
    #: Nome da PESSOA (usuario_coordenacao.nome), não o da conexão.
    nome: str
    papel: str


def gerar() -> tuple[str, str, str]:
    """(token em claro, sha256 hex, prefixo visível). O token sai daqui e não volta."""
    token = PREFIXO_DO_TOKEN + secrets.token_urlsafe(_BYTES_ALEATORIOS)
    return token, hash_do_token(token), token[:TAMANHO_DO_PREFIXO_VISIVEL]


def hash_do_token(token: str) -> str:
    """O que a 0072 guarda em `token_mcp.hash_acesso`: sha256 em hex minúsculo.

    sha256 puro, sem sal nem PBKDF2: o token tem 256 bits aleatórios, então
    não há dicionário a atacar — e a conferência roda a cada requisição, onde
    um hash lento seria custo sem ganho.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def formato_valido(token: str | None) -> bool:
    return isinstance(token, str) and _FORMATO.fullmatch(token) is not None


def conferir(cliente: Any, token: str | None) -> Identidade | None:
    """A identidade dona do token, ou None. Síncrono: quem está num event loop
    chama numa thread (`servidor.conferir_em_thread`).

    Token fora do formato nem vai ao banco: um JWT de sessão, um token de
    download ou lixo de scanner custariam uma ida ao PostgREST cada um.

    Revogado, vencido, de conta desativada e inexistente voltam todos como
    None — é a RPC que decide, e ela não conta qual dos casos foi. Erro de
    banco SOBE: quem chama decide se isso é 401 ou 503.
    """
    if not isinstance(token, str) or not formato_valido(token):
        return None
    linhas = cliente.rpc("mcp_conferir_token", {"p_hash": hash_do_token(token)}).execute().data or []
    if not linhas:
        return None
    linha = linhas[0]
    token_id, coordenador_id = linha.get("token_id"), linha.get("coordenador_id")
    if not token_id or not coordenador_id:
        return None
    papel = linha.get("papel")
    return Identidade(
        token_id=str(token_id),
        coordenador_id=str(coordenador_id),
        nome=(linha.get("nome") or "").strip(),
        # Papel que não se reconhece vale o MENOS poderoso, como em
        # `auth.papel_da_sessao`: um valor torto não vira administrador.
        papel=papel if papel in PAPEIS_DE_COORDENACAO else "coordenador",
    )
