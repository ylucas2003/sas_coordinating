-- Tabela de usuários da coordenação (docs/15 §Etapa 7, item 7.1).
--
-- Antes disto o login da coordenação era UMA credencial em variável de
-- ambiente, comparada em texto puro com hmac.compare_digest contra
-- COORDENADOR_EMAIL/COORDENADOR_SENHA. Consequências, todas reais:
--
--   * senha compartilhada entre todas as pessoas da coordenação;
--   * sem hash — quem lê o .env do servidor lê a senha;
--   * sem rastro: `sub` do token era a string fixa "coordenador", então
--     nenhuma ação no sistema tem autor;
--   * trocar de pessoa no cargo exigia redeploy.
--
-- O hash é o mesmo PBKDF2-SHA256 de 600k iterações que os alunos já usam
-- (app/auth.py:hash_senha) — não há formato novo aqui.

BEGIN;

CREATE TABLE IF NOT EXISTS usuario_coordenacao (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email           text NOT NULL,
    nome            text NOT NULL,
    senha_hash      text NOT NULL,
    ativo           boolean NOT NULL DEFAULT true,
    criado_em       timestamptz NOT NULL DEFAULT now(),
    ultimo_login_em timestamptz
);

-- Case-insensitive: ninguém deve conseguir criar Leo@ e leo@ como contas
-- diferentes, e o login normaliza para minúsculas antes de consultar.
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuario_coordenacao_email
    ON usuario_coordenacao (lower(email));

COMMENT ON TABLE  usuario_coordenacao          IS 'Usuários da coordenação. Substitui COORDENADOR_EMAIL/COORDENADOR_SENHA do .env.';
COMMENT ON COLUMN usuario_coordenacao.senha_hash IS 'pbkdf2_sha256$<iteracoes>$<salt>$<hash> — mesmo formato de aluno.senha_hash.';
COMMENT ON COLUMN usuario_coordenacao.ultimo_login_em IS 'Atualizado a cada login bem-sucedido. É o começo da trilha de auditoria que docs/14 §5 pede.';

COMMIT;
