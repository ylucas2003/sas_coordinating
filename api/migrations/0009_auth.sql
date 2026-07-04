-- Adiciona hash de senha para autenticação de alunos.
-- Senha padrão demo: md5('tioleo123') — alterar em produção.
ALTER TABLE aluno ADD COLUMN IF NOT EXISTS senha_hash text;
UPDATE aluno SET senha_hash = md5('tioleo123') WHERE senha_hash IS NULL;
