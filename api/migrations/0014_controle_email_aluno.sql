-- Controle de descoberta de e-mail no sync incremental: o fallback por
-- Communication Channels é 1 chamada por aluno, então cada aluno é tentado
-- uma única vez e a tentativa fica registrada aqui.
BEGIN;

ALTER TABLE aluno ADD COLUMN email_verificado_em timestamptz;

COMMENT ON COLUMN aluno.email_verificado_em IS
  'Última tentativa de descobrir e-mail via Canvas (Communication Channels). Evita re-tentativas infinitas no sync incremental.';
COMMENT ON COLUMN aluno.email IS
  'E-mail do Canvas. Populado no backfill e no sync incremental (users?include[]=email + fallback Communication Channels). Valida o primeiro acesso do aluno.';

COMMIT;
