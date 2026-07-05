BEGIN;

ALTER TABLE aluno DROP COLUMN email_verificado_em;

COMMENT ON COLUMN aluno.email IS
  'Populado só no backfill — muda raramente';

COMMIT;
