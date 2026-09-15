-- Reverte a 0057.

BEGIN;

DROP INDEX IF EXISTS conquista_externa_dedup;

COMMIT;
