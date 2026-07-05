-- ─────────────────────────────────────────────────────────────────────────
-- 0011 · canvas_user_id deixa de ser único
--
-- O backfill histórico revelou que o mesmo usuário do Canvas aparece com
-- sis_user_id (= aluno.matricula) DIFERENTE em cursos de anos diferentes —
-- matrículas re-emitidas, contas antigas com e-mail no lugar do número.
-- A identidade do domínio é e continua sendo `matricula`; canvas_user_id é
-- referência auxiliar, não chave. Índice vira não-único.
--
-- Reversível via 0011_*.down.sql.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

DROP INDEX IF EXISTS idx_aluno_canvas_user_id;
CREATE INDEX idx_aluno_canvas_user_id ON aluno(canvas_user_id) WHERE canvas_user_id IS NOT NULL;

COMMIT;
