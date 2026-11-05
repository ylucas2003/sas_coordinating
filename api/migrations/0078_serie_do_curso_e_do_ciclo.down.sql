-- Reverte a 0078.
--
-- ⚠️ Se já existir ciclo de 1º ou 2º ano, a volta do UNIQUE (ano_letivo_id, ordem)
-- falha, e é de propósito: apagar ciclo em silêncio levaria as provas e as notas
-- junto. Tire esses ciclos à mão antes de reverter.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`.

BEGIN;

REVOKE SELECT (serie) ON ciclo FROM sas_leitura;

ALTER TABLE turma DROP COLUMN serie_do_curso;

ALTER TABLE ciclo DROP CONSTRAINT ciclo_ano_letivo_serie_ordem_key;
ALTER TABLE ciclo ADD CONSTRAINT ciclo_ano_letivo_id_ordem_key UNIQUE (ano_letivo_id, ordem);
ALTER TABLE ciclo DROP COLUMN serie;

DROP TABLE curso_canvas;

COMMIT;
