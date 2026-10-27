"""O cliente PostgREST do MCP: um NOVO a cada operação.

Por quê novo, e não o `get_supabase()` cacheado: o postgrest-py força HTTP/2,
todas as requisições de um cliente dividem uma conexão, e um GOAWAY numa
stream (statement timeout de uma tool pesada) derruba as outras
(app/supabase_client.py). No MCP as chamadas de clientes diferentes correm em
paralelo, cada uma numa thread — o mesmo caso das tools em paralelo do chat
(docs/43 §4.2).

O endereço vem de POSTGREST_URL, que no processo do MCP aponta para o
`postgrest_mcp` (papel anônimo `sas_mcp`). Não há código aqui que escolha o
papel: é o ambiente do processo que decide, e por isso TODO cliente do
processo — inclusive os que as tools criam por dentro — fica restrito. E como
o ambiente pode estar errado, o boot PERGUNTA ao PostgREST qual é o papel
(`exigir_papel_restrito`) antes de atender alguém.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from postgrest.exceptions import APIError

from ..supabase_client import criar_cliente_supabase

log = logging.getLogger("sas.mcp.dados")

CriarCliente = Callable[[], Any]

#: A tabela da sonda de privilégio. O sas_mcp não tem nada nela — a 0071
#: deixa a credencial de fora, de propósito —, e o sas_service da API tem
#: ALL. "Não consegue ler usuario_coordenacao" é o critério de pronto da
#: Fase 2 (docs/43 §7).
TABELA_DA_SONDA = "usuario_coordenacao"
_SEM_PRIVILEGIO = "42501"  # insufficient_privilege, o SQLSTATE que o PostgREST repassa


def fechar_cliente(cliente: Any) -> None:
    """Fecha a conexão do cliente, se ele tiver uma.

    `SyncPostgrestClient.aclose()` é SÍNCRONO apesar do nome (postgrest-py
    0.16). Sem fechar, cada chamada deixaria uma conexão aberta até o coletor
    de lixo passar.
    """
    fechar = getattr(cliente, "aclose", None)
    if not callable(fechar):
        return
    try:
        fechar()
    except Exception:
        log.debug("não consegui fechar o cliente PostgREST", exc_info=True)


@contextmanager
def cliente_novo(criar_cliente: CriarCliente = criar_cliente_supabase) -> Iterator[Any]:
    cliente = criar_cliente()
    try:
        yield cliente
    finally:
        fechar_cliente(cliente)


# ─── A sonda de privilégio do boot ───────────────────────────────────────


class SondaIndisponivel(Exception):
    """O PostgREST não respondeu à sonda (subindo ainda, banco fora): vale tentar de novo."""


def problema_de_privilegio(criar_cliente: CriarCliente = criar_cliente_supabase) -> str | None:
    """None quando o papel deste processo NÃO lê `usuario_coordenacao`; senão, o problema.

    O guard de configuracao.py só compara o NOME do host de POSTGREST_URL com
    `postgrest` — e `postgrest.`, `sas-postgrest-1` e o IP do container passam
    por ele (revisão de 24/10). Aqui quem responde é o próprio PostgREST: sob o
    sas_mcp, ler a tabela da sonda volta 42501; sob o sas_service, volta linha
    (ou lista vazia — que também é ler). Não dá para perguntar: `SondaIndisponivel`.
    """
    try:
        with cliente_novo(criar_cliente) as cliente:
            cliente.table(TABELA_DA_SONDA).select("id").limit(1).execute()
    except APIError as erro:
        # `code` é texto no corpo do PostgREST e int no erro genérico do
        # postgrest-py (resposta que nem é JSON).
        codigo = str(erro.code or "")
        if codigo == _SEM_PRIVILEGIO:
            return None
        if codigo.startswith("PGRST00"):
            # PGRST000–003: o PostgREST está de pé mas não alcança o banco.
            raise SondaIndisponivel(codigo) from None
        return (
            f"a sonda de privilégio em {TABELA_DA_SONDA} voltou o código {codigo or '?'} em vez "
            "de 42501 — POSTGREST_URL não parece ser o postgrest_mcp"
        )
    except Exception as erro:
        # O texto da exceção pode ter a URL; o nome do tipo basta para o log.
        raise SondaIndisponivel(type(erro).__name__) from None
    return (
        f"o PostgREST de POSTGREST_URL LÊ {TABELA_DA_SONDA}: o papel dele não é o sas_mcp "
        "(é o da API, sas_service, com acesso total?) — aponte para o postgrest_mcp"
    )


def exigir_papel_restrito(
    app_env: str,
    criar_cliente: CriarCliente = criar_cliente_supabase,
    *,
    tentativas: int = 10,
    espera_s: float = 2.0,
    dormir: Callable[[float], None] = time.sleep,
) -> None:
    """A sonda no boot. Fora de dev/test o MCP NÃO sobe sem ela passar.

    Com tentativas porque, no compose, o MCP pode subir antes de o
    postgrest_mcp atender (`depends_on` sem healthcheck). Esgotadas, recusa
    subir — sem a resposta não há como saber com que papel o processo fala.
    Em dev/test é uma tentativa e um aviso, como o guard de configuracao.py.
    """
    em_dev = app_env in ("dev", "test")
    problema: str | None = None
    for tentativa in range(1 if em_dev else max(1, tentativas)):
        if tentativa:
            dormir(espera_s)
        try:
            problema = problema_de_privilegio(criar_cliente)
            break
        except SondaIndisponivel as erro:
            problema = f"não consegui fazer a sonda de privilégio no PostgREST ({erro})"
    if problema is None:
        log.info("sonda de privilégio ok: o papel deste PostgREST não lê %s", TABELA_DA_SONDA)
        return
    if em_dev:
        log.warning("sonda de privilégio: %s — subindo assim mesmo porque APP_ENV=%s", problema, app_env)
        return
    raise RuntimeError(
        f"Configuração insegura do MCP para APP_ENV={app_env}:\n  - {problema}"
        "\n\nCorrija POSTGREST_URL, ou declare APP_ENV=dev se for ambiente local."
    )
