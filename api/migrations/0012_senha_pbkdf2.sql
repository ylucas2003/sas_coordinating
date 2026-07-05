-- Migra o armazenamento de senha de md5 para PBKDF2-HMAC-SHA256 versionado.
-- Hashes md5 legados (senha única demo da migration 0009) são zerados:
-- cada aluno cria a própria senha pelo fluxo "Primeiro acesso" (RA + email).
BEGIN;

UPDATE aluno
   SET senha_hash = NULL
 WHERE senha_hash IS NOT NULL
   AND senha_hash NOT LIKE 'pbkdf2_sha256$%';

COMMENT ON COLUMN aluno.senha_hash IS
  'Formato pbkdf2_sha256$<iteracoes>$<salt_hex>$<hash_hex>. NULL = aluno ainda não fez o primeiro acesso.';

COMMIT;
