-- ─────────────────────────────────────────────────────────────────────────
-- 0010 · DOWNGRADE — desfaz a expansão para sincronização com o Canvas.
-- Tabelas novas primeiro (filhas antes das mães), depois as colunas.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

DROP TABLE IF EXISTS canvas_sync_execucao;

DROP TABLE IF EXISTS aluno_modulo_progresso;
DROP TABLE IF EXISTS modulo;

DROP TABLE IF EXISTS questao_resposta_aluno;
DROP TABLE IF EXISTS questao_alternativa;
DROP TABLE IF EXISTS questao;

ALTER TABLE simulado DROP COLUMN IF EXISTS duracao_media_segundos;
ALTER TABLE simulado DROP COLUMN IF EXISTS lock_at;
ALTER TABLE simulado DROP COLUMN IF EXISTS unlock_at;
ALTER TABLE simulado DROP COLUMN IF EXISTS quiz_id;

ALTER TABLE nota DROP COLUMN IF EXISTS canvas_workflow_state;
ALTER TABLE nota DROP COLUMN IF EXISTS canvas_excused;
ALTER TABLE nota DROP COLUMN IF EXISTS canvas_missing;
ALTER TABLE nota DROP COLUMN IF EXISTS grader_canvas_user_id;
ALTER TABLE nota DROP COLUMN IF EXISTS graded_em;
ALTER TABLE nota DROP COLUMN IF EXISTS late;

ALTER TABLE matricula_turma DROP COLUMN IF EXISTS last_attended_at;
ALTER TABLE matricula_turma DROP COLUMN IF EXISTS last_activity_at;
ALTER TABLE matricula_turma DROP COLUMN IF EXISTS enrollment_state;
ALTER TABLE matricula_turma DROP COLUMN IF EXISTS canvas_section_id;
ALTER TABLE matricula_turma DROP COLUMN IF EXISTS canvas_enrollment_id;

DROP INDEX IF EXISTS idx_aluno_canvas_user_id;
ALTER TABLE aluno DROP COLUMN IF EXISTS canvas_criado_em;
ALTER TABLE aluno DROP COLUMN IF EXISTS canvas_user_id;
ALTER TABLE aluno DROP COLUMN IF EXISTS avatar_url;
ALTER TABLE aluno DROP COLUMN IF EXISTS email;

COMMIT;
