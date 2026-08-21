-- Reverte a 0022. DESTRUTIVO: apaga a trilha de auditoria inteira.
BEGIN;
DROP TABLE IF EXISTS evento_auditoria;
COMMIT;
