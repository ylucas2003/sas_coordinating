-- Reverte 0007.

BEGIN;

ALTER TABLE insight_ciclo
    DROP CONSTRAINT insight_ciclo_chave_completa_key;

ALTER TABLE insight_ciclo
    ADD CONSTRAINT insight_ciclo_ciclo_id_fase_materia_codigo_hash_payload_key
    UNIQUE (ciclo_id, fase, materia_codigo, hash_payload);

ALTER TABLE insight_ciclo
    DROP CONSTRAINT insight_ciclo_fase_check;

ALTER TABLE insight_ciclo
    ADD CONSTRAINT insight_ciclo_fase_check
    CHECK (fase IN ('fase_1', 'fase_2'));

ALTER TABLE insight_ciclo
    DROP COLUMN tipo_insight;

COMMIT;
