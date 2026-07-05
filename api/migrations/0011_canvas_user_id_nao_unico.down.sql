-- ─────────────────────────────────────────────────────────────────────────
-- 0011 · DOWNGRADE — volta canvas_user_id a índice único.
-- Só é seguro se não houver canvas_user_id duplicado no banco.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

DROP INDEX IF EXISTS idx_aluno_canvas_user_id;
CREATE UNIQUE INDEX idx_aluno_canvas_user_id ON aluno(canvas_user_id) WHERE canvas_user_id IS NOT NULL;

COMMIT;
