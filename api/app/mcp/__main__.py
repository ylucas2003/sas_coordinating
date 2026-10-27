"""Entrada do MCP da coordenação: `python -m app.mcp` (docs/43 §5.1).

    python -m app.mcp                 # HTTP em 0.0.0.0:${PORT:-8000}, /mcp e /health
    python -m app.mcp --stdio         # stdio — SÓ em dev/test

O uvicorn sobe PROGRAMÁTICO e com o app como objeto, de propósito: assim ele
não tem como subir worker nenhum. O MCP é um processo só — o limite por
minuto por token mora na memória dele (`servidor.LimitePorMinuto`), e com dois
processos cada um teria a sua contagem e o limite dobraria calado.

Antes de atender, o boot pergunta ao PostgREST com que papel fala
(`dados.exigir_papel_restrito`): fora de dev/test, um PostgREST que lê
`usuario_coordenacao` impede o processo de subir.

O stdio é de desenvolvimento: nele o processo roda na máquina de quem chama, e
o pseudônimo, o teto e o limite seriam lidos do ambiente DESSA pessoa — o guard
o recusa fora de dev/test. O Claude Desktop de verdade conecta pelo
`mcp-remote` sobre o HTTP (docs/43 §5.3). No stdio o token vem de SAS_MCP_TOKEN
(nunca de argumento, que fica no `ps` e no histórico do shell) e é reconferido
a cada chamada; o stdout é o canal do protocolo, então todo log vai para o
stderr.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import anyio

from ..config import get_settings
from ..observabilidade import configurar_logging
from .configuracao import (
    ConfiguracaoMcp,
    get_configuracao_mcp,
    registrar_no_log,
    validar_configuracao_do_mcp,
)
from .dados import exigir_papel_restrito

log = logging.getLogger("sas.mcp")

VARIAVEL_DO_TOKEN = "SAS_MCP_TOKEN"  # noqa: S105 — nome da variável, não o token


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m app.mcp", description="MCP da coordenação do SAS.")
    p.add_argument(
        "--stdio", action="store_true",
        help=f"fala MCP por stdio, só em dev/test; o token vem de {VARIAVEL_DO_TOKEN}",
    )
    # 0.0.0.0 é o certo DENTRO do container (o compose publica só no
    # loopback, e em produção o serviço nem tem `ports:`); fora dele, a
    # proteção de Host do transporte recusa quem chegar por outro endereço.
    p.add_argument("--host", default=os.environ.get("MCP_ESCUTAR_EM", "0.0.0.0"))  # noqa: S104
    p.add_argument("--porta", type=int, default=int(os.environ.get("PORT", "8000")))
    return p.parse_args(argv)


def _rodar_http(config: ConfiguracaoMcp, host: str, porta: int) -> int:
    import uvicorn

    from .app import montar_app

    servidor_http = uvicorn.Config(
        montar_app(config=config),
        host=host,
        port=porta,
        # O log é o da casa (JSON com request id, `main`); o dictConfig do
        # uvicorn poria um formato próprio por cima. Sem access log: o
        # middleware de request id já grava uma linha por requisição.
        log_config=None,
        access_log=False,
        proxy_headers=True,
        # Só o nginx alcança o MCP em produção, como a API (infra/vps); sem
        # isto, a auditoria grava o IP do nginx em vez do de quem chamou.
        forwarded_allow_ips=config.ips_do_proxy,
        server_header=False,
    )
    uvicorn.Server(servidor_http).run()
    return 0


async def _rodar_stdio(config: ConfiguracaoMcp) -> int:
    from mcp.server.stdio import stdio_server

    from .servidor import IdentidadePeloToken, conferir_em_thread, montar_servidor

    token = os.environ.get(VARIAVEL_DO_TOKEN, "").strip()
    if not token:
        sys.stderr.write(f"Defina {VARIAVEL_DO_TOKEN} com o token da conexão (Administração → Conexões de IA).\n")
        return 2
    try:
        identidade = await conferir_em_thread(token)
    except Exception:
        log.exception("não consegui conferir o token na subida")
        sys.stderr.write("Não consegui falar com o PostgREST do MCP (POSTGREST_URL).\n")
        return 2
    if identidade is None:
        sys.stderr.write("Token inválido, revogado ou vencido.\n")
        return 2

    servidor = montar_servidor(config=config, identificar=IdentidadePeloToken(token))
    async with stdio_server() as (leitura, escrita):
        await servidor.run(leitura, escrita, servidor.create_initialization_options())
    return 0


def _log_no_stderr() -> None:
    # No stdio, uma linha de log no stdout corromperia o JSON-RPC.
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setStream(sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    configurar_logging()
    if args.stdio:
        _log_no_stderr()

    settings = get_settings()
    config = get_configuracao_mcp()
    validar_configuracao_do_mcp(config, settings, "stdio" if args.stdio else "http")
    # O par da linha que a API escreve ao subir (app/main.py): os dois leem
    # MCP_* cada um do seu ambiente, e só o log mostra se divergem.
    registrar_no_log(config, "mcp")
    if not config.habilitado:
        # Só chega aqui em dev/test: fora deles o guard já recusou.
        log.warning("MCP_HABILITADO=false: subindo assim mesmo porque APP_ENV=%s", settings.app_env)
    # Depois do guard (que já exige POSTGREST_URL) e antes de atender alguém.
    exigir_papel_restrito(settings.app_env)

    if args.stdio:
        return anyio.run(_rodar_stdio, config)
    return _rodar_http(config, args.host, args.porta)


if __name__ == "__main__":
    sys.exit(main())
