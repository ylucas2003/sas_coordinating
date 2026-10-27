-- Reverte a 0072: tira a tabela de tokens, a função de conferência, o
-- estreito de auditoria do sas_mcp e o gatilho que o confina à trilha do MCP.
--
-- ⚠️ Apaga todos os tokens do MCP. Quem estiver conectado perde o acesso na
-- hora — e, depois de um `up` de novo, precisa de token novo: o token em
-- claro nunca esteve no banco para ser restaurado.
--
-- Sem CASCADE no DROP TABLE: se a 0073 (OAuth) ainda tiver FK para cá, o
-- down tem de falhar alto, e não levar a constraint de outra migration junto.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`
-- (CLAUDE.md, armadilha 1).

BEGIN;

DROP TRIGGER IF EXISTS trg_evento_auditoria_so_do_mcp ON evento_auditoria;
DROP FUNCTION IF EXISTS evento_auditoria_so_do_mcp();

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sas_mcp') THEN
        -- REVOKE na tabela leva junto o INSERT por coluna.
        REVOKE INSERT ON evento_auditoria FROM sas_mcp;
        REVOKE USAGE ON SEQUENCE evento_auditoria_id_seq FROM sas_mcp;
    END IF;
END
$$;

DROP FUNCTION IF EXISTS mcp_conferir_token(text);
DROP TABLE IF EXISTS token_mcp;

COMMIT;
