BEGIN;

ALTER TABLE conquista_externa
    DROP COLUMN IF EXISTS notas_por_materia;

COMMIT;
