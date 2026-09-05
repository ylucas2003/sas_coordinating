"""Clientes de dados.

Dois modos, escolhidos por env — o resto do código não sabe qual está ativo,
porque os dois expõem o mesmo `.table(...)`:

  - **Supabase hospedado** (default): `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`.
  - **PostgREST local** (docker compose): `POSTGREST_URL`.

O truque é que o `supabase-py` não é um driver de banco — ele é um wrapper
HTTP em cima do `postgrest-py`, que é exatamente o mesmo cliente usado aqui no
modo local. O Supabase hospeda um PostgREST; o compose sobe outro. Por isso os
~210 `cliente.table(...)` espalhados pelo projeto funcionam nos dois modos sem
alteração. As anotações `from supabase import Client` continuam pelo código
como documentação do formato — no modo local o objeto é um
`SyncPostgrestClient`, que responde à mesma chamada.

O que NÃO existe no modo local é `.storage` — quem cuida disso é app/storage.py,
que tem seu próprio backend de filesystem.

Duas funções porque o postgrest-py força HTTP/2: todas as requisições do
mesmo client compartilham uma conexão TCP única e ficam multiplexadas em
streams. Se duas operações pesadas usam o mesmo client (ex.: pipeline de
ingestão correndo em background + polling do frontend), e o servidor manda
GOAWAY em uma stream (ex.: statement timeout), o cliente **aborta todas as
streams da conexão** — sintoma: "Server disconnected".

Para evitar isso:
  - `get_supabase()`         → cliente cacheado para handlers normais (rápido)
  - `criar_cliente_supabase()` → cliente novo, para background tasks isoladas

Tanto a service key do Supabase quanto o papel `sas_service` do PostgREST local
dão acesso total (sem RLS) — toda lógica de autorização fica neste backend.
"""

from functools import lru_cache

from postgrest import SyncPostgrestClient
from supabase import Client, create_client

from .config import get_settings

# O que os módulos recebem. Anotado como `Client` na maior parte do código.
ClienteDados = Client | SyncPostgrestClient


def _criar_cliente_postgrest_local(url: str, token: str) -> SyncPostgrestClient:
    """Cliente apontando direto para um PostgREST próprio.

    Sem `Authorization`, o PostgREST usa o papel de `PGRST_DB_ANON_ROLE` — que
    no compose é o `sas_service`, com acesso total. Isso só é aceitável porque
    a porta está presa no loopback. Num PostgREST exposto, configure
    `PGRST_JWT_SECRET` no servidor e `POSTGREST_TOKEN` aqui.
    """
    cabecalhos = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    return SyncPostgrestClient(url.rstrip("/"), schema="public", headers=cabecalhos)


def criar_cliente_supabase() -> ClienteDados:
    """Cria um client novo (sem cache). Use em workers/background que rodam em
    paralelo a outras chamadas, para garantir conexão TCP independente."""
    settings = get_settings()

    if settings.postgrest_url:
        return _criar_cliente_postgrest_local(
            settings.postgrest_url, settings.postgrest_token
        )

    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError(
            "Nenhum backend de dados configurado. Defina POSTGREST_URL (stack local, "
            "ver docker-compose.yml) ou SUPABASE_URL + SUPABASE_SERVICE_KEY no .env "
            "(ver api/.env.example)."
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)


@lru_cache
def get_supabase() -> ClienteDados:
    """Client cacheado para handlers HTTP normais (curtos, sequenciais)."""
    return criar_cliente_supabase()
