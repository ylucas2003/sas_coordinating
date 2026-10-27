-- Reverte a 0071: tira os papéis do MCP — o login do postgrest_mcp inclusive
-- — e devolve a função de captação a PUBLIC, como a 0063 a deixou.
--
-- A 0072 tem de sair ANTES (o runner reverte em ordem decrescente): ela dá
-- ao sas_mcp o INSERT na auditoria e o EXECUTE em mcp_conferir_token. Mesmo
-- se não tiver saído, o DROP OWNED BY abaixo revoga esses GRANT também.
--
-- Papel é global no cluster: cada passo confere se ele existe, para o down
-- não morrer num banco onde o up parou no meio. DROP ROLE leva junto os
-- pertencimentos do papel, nos dois sentidos — inclusive um `GRANT sas_mcp TO
-- authenticator` que a primeira versão da 0071 tenha deixado.
--
-- ⚠️ Depois de aplicar: `docker compose stop postgrest_mcp` e `docker compose
-- restart postgrest` (CLAUDE.md, armadilha 1). Sem o autenticador_mcp, o
-- postgrest_mcp não conecta mais — é o esperado. Um `up` de novo recria o
-- login SEM senha: ela tem de ser definida outra vez (docker-compose.yml).

BEGIN;

REVOKE EXECUTE ON FUNCTION atualizar_v_candidato_externo_por_nome() FROM sas_service;
GRANT  EXECUTE ON FUNCTION atualizar_v_candidato_externo_por_nome() TO PUBLIC;

DO $$
BEGIN
    -- O login primeiro: é membro do sas_mcp.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'autenticador_mcp') THEN
        REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM autenticador_mcp;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM autenticador_mcp;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM autenticador_mcp;
        REVOKE ALL ON SCHEMA public FROM autenticador_mcp;
        DROP OWNED BY autenticador_mcp;
        DROP ROLE autenticador_mcp;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sas_mcp') THEN
        REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM sas_mcp;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM sas_mcp;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM sas_mcp;
        -- Leva o que sobrar neste banco (GRANT dado por fora, objeto que ele
        -- possua) — sem isso o DROP ROLE recusa.
        DROP OWNED BY sas_mcp;
        DROP ROLE sas_mcp;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sas_leitura') THEN
        -- REVOKE na tabela leva junto os GRANT por coluna da lista branca.
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM sas_leitura;
        REVOKE ALL ON SCHEMA public FROM sas_leitura;
        DROP OWNED BY sas_leitura;
        DROP ROLE sas_leitura;
    END IF;
END
$$;

COMMIT;
