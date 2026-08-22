-- Reverte a 0026. A coordenação volta a entrar só por e-mail + senha.
BEGIN;
DROP INDEX IF EXISTS idx_usuario_coordenacao_canvas_user_id;
ALTER TABLE usuario_coordenacao DROP COLUMN IF EXISTS canvas_user_id;
COMMIT;
