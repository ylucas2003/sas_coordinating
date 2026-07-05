-- Reverte o namespace das threads da coordenação para o fallback antigo.
BEGIN;

UPDATE chat_thread
   SET usuario_id = 'coordenador'
 WHERE usuario_id = 'coord:coordenador';

COMMENT ON COLUMN chat_thread.usuario_id IS NULL;

COMMIT;
