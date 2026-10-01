-- Os módulos criados no Canvas ficam lá: apagar módulo de curso com alunos não
-- é coisa de migration.
ALTER TABLE curso_monitorado_gravacao
  DROP COLUMN IF EXISTS canvas_modulo_generico_id;
