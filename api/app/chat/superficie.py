"""De onde veio a chamada de tool: do chat do app ou do MCP (docs/43 §5).

Quase toda tool responde igual nas duas superfícies, porque lê o banco, e o
banco é o mesmo. A exceção é o que mora no AMBIENTE do processo. O processo do
MCP sobe só com `APP_ENV`, `POSTGREST_URL` e `MCP_*`, de propósito: sem
`env_file`, sem as chaves da AWS, sem nada da API (configuracao.py). Quem lê
`get_settings()` lá dentro recebe o valor de FÁBRICA, e não o da API que manda
os e-mails — `lembretes_agendados` diria "e-mail não configurado" com o SES
ligado, e a IA repetiria (decisão de 30/10, tool nova no MCP).

É uma ContextVar, e não um parâmetro do handler, porque a tool que precisa
disso é a exceção: o contrato `(cliente, **args)` continua o de todas. O
`despachar_async` roda a tool com `asyncio.to_thread`, que copia o contexto, e
por isso o valor chega à thread dela.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_PELO_MCP: ContextVar[bool] = ContextVar("chamada_pelo_mcp", default=False)


def pelo_mcp() -> bool:
    return _PELO_MCP.get()


@contextmanager
def chamada_pelo_mcp() -> Iterator[None]:
    marca = _PELO_MCP.set(True)
    try:
        yield
    finally:
        _PELO_MCP.reset(marca)
