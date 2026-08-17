#!/bin/bash
# Papéis do Postgres usados pelo PostgREST local (ver docker-compose.yml).
#
# Este script roda UMA ÚNICA VEZ, quando o volume do Postgres é criado. Se
# precisar mudar algo aqui, recrie o volume: `docker compose down -v`.
#
#   authenticator → papel de LOGIN do PostgREST. NOINHERIT de propósito: ele
#                   não tem permissão nenhuma por si só, apenas troca (SET
#                   ROLE) para o papel que a requisição pedir.
#   sas_service   → papel efetivo das requisições. É o equivalente local da
#                   service key do Supabase: acesso total ao schema public.
#                   Como o projeto não usa RLS (nenhuma migration cria
#                   policy), "acesso total" aqui é só GRANT de tabela.
#
# Toda autorização de verdade continua no backend FastAPI, igual ao que o
# comentário de app/supabase_client.py já dizia sobre a service key.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE sas_service NOLOGIN;
    GRANT USAGE ON SCHEMA public TO sas_service;
    GRANT ALL ON ALL TABLES IN SCHEMA public TO sas_service;
    GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO sas_service;

    -- Neste ponto o schema está vazio: quem cria as tabelas é o scripts/migrate.py,
    -- que roda depois e como $POSTGRES_USER. Sem o DEFAULT PRIVILEGES abaixo, cada
    -- tabela nova nasceria invisível para o PostgREST e voltaria 401/404.
    ALTER DEFAULT PRIVILEGES FOR ROLE $POSTGRES_USER IN SCHEMA public
        GRANT ALL ON TABLES TO sas_service;
    ALTER DEFAULT PRIVILEGES FOR ROLE $POSTGRES_USER IN SCHEMA public
        GRANT ALL ON SEQUENCES TO sas_service;

    CREATE ROLE authenticator LOGIN NOINHERIT PASSWORD '$POSTGREST_PASSWORD';
    GRANT sas_service TO authenticator;
EOSQL
