BEGIN;

ALTER TABLE questao DROP COLUMN assunto;
ALTER TABLE simulado DROP COLUMN questoes_sincronizadas_em;

COMMIT;
