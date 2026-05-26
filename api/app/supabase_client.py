"""Clientes Supabase.

Duas funções porque o postgrest-py força HTTP/2: todas as requisições do
mesmo `Client` compartilham uma conexão TCP única e ficam multiplexadas em
streams. Se duas operações pesadas usam o mesmo client (ex.: pipeline de
ingestão correndo em background + polling do frontend), e o servidor manda
GOAWAY em uma stream (ex.: statement timeout do Supabase), o cliente
**aborta todas as streams da conexão** — sintoma: "Server disconnected".

Para evitar isso:
  - `get_supabase()`         → cliente cacheado para handlers normais (rápido)
  - `criar_cliente_supabase()` → cliente novo, para background tasks isoladas

A service key dá acesso total (bypass de RLS) — toda lógica de autorização
fica neste backend, nunca expor a service key para o frontend.
"""

from functools import lru_cache

from supabase import Client, create_client

from .config import get_settings


def criar_cliente_supabase() -> Client:
    """Cria um Client novo (sem cache). Use em workers/background que rodam em
    paralelo a outras chamadas, para garantir conexão TCP independente."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError(
            "Supabase não configurado. Defina SUPABASE_URL e SUPABASE_SERVICE_KEY no .env "
            "(ver api/.env.example)."
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)


@lru_cache
def get_supabase() -> Client:
    """Cliente cacheado para handlers HTTP normais (curtos, sequenciais)."""
    return criar_cliente_supabase()
