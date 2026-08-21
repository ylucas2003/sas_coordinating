BEGIN;

ALTER TABLE ciclo      DROP COLUMN canvas_assignment_group_id;
ALTER TABLE ano_letivo DROP COLUMN canvas_course_id;

DROP INDEX idx_simulado_sas_unico;

-- Simulados nascidos no SAS sem espelho no Canvas não sobrevivem ao NOT NULL
-- de external_id — removemos as linhas (e dependências) antes de restaurar.
DELETE FROM metrica_simulado WHERE simulado_id IN (SELECT id FROM simulado WHERE external_id IS NULL);
DELETE FROM nota             WHERE simulado_id IN (SELECT id FROM simulado WHERE external_id IS NULL);
DELETE FROM simulado         WHERE external_id IS NULL;

ALTER TABLE simulado DROP COLUMN canvas_tentativas;
ALTER TABLE simulado DROP COLUMN canvas_erro;
ALTER TABLE simulado DROP COLUMN canvas_estado;
ALTER TABLE simulado DROP COLUMN origem;
ALTER TABLE simulado DROP COLUMN evento_agenda_id;
ALTER TABLE simulado ALTER COLUMN external_id SET NOT NULL;

DROP TABLE evento_agenda;

COMMIT;
