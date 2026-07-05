-- Reverte para o estado da migration 0009 (senha única demo em md5).
-- Atenção: senhas PBKDF2 criadas pelos alunos não são recuperáveis — o down
-- só faz sentido em desenvolvimento.
BEGIN;

UPDATE aluno
   SET senha_hash = md5('tioleo123')
 WHERE senha_hash IS NULL
    OR senha_hash LIKE 'pbkdf2_sha256$%';

COMMENT ON COLUMN aluno.senha_hash IS NULL;

COMMIT;
