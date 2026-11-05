-- Reverte a 0079.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`.

BEGIN;

ALTER TABLE alerta DROP COLUMN serie;

COMMIT;
