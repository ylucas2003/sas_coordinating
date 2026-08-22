-- Reverte a 0025. Os eventos continuam; só perdem o canal.
BEGIN;
DROP INDEX IF EXISTS idx_evento_auditoria_canal;
ALTER TABLE evento_auditoria DROP COLUMN IF EXISTS canal;
COMMIT;
