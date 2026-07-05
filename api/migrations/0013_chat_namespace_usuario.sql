-- As rotas de chat passaram a exigir JWT e a separar threads por namespace:
-- 'coord:<sub>' para coordenação e 'aluno:<aluno_id>' para alunos.
-- Migra as threads existentes (todas viviam no fallback 'coordenador').
BEGIN;

UPDATE chat_thread
   SET usuario_id = 'coord:coordenador'
 WHERE usuario_id = 'coordenador';

COMMENT ON COLUMN chat_thread.usuario_id IS
  'Namespace do dono: coord:<sub> (coordenação) ou aluno:<aluno_id>.';

COMMIT;
