-- Canvas como provedor de identidade também para a coordenação (docs/18 §4.2).
--
-- `aluno.canvas_user_id` já existe (0010) e está preenchido em 100% dos
-- ativos. A coordenação não tinha a coluna porque até aqui entrava por
-- e-mail + senha. Com o SSO, o callback precisa achar o coordenador pelo id
-- que o Canvas devolve — e é este campo que o painel de administrador vai
-- preencher ao criar a conta.

BEGIN;

ALTER TABLE usuario_coordenacao
    ADD COLUMN IF NOT EXISTS canvas_user_id text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_usuario_coordenacao_canvas_user_id
    ON usuario_coordenacao (canvas_user_id) WHERE canvas_user_id IS NOT NULL;

COMMENT ON COLUMN usuario_coordenacao.canvas_user_id IS 'id do usuário no Canvas. NULL = só entra por e-mail + senha.';

COMMIT;
