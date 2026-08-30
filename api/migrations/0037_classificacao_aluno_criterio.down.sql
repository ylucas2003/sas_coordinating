BEGIN;

ALTER TABLE classificacao_aluno
    DROP COLUMN IF EXISTS criterio_slug,
    DROP COLUMN IF EXISTS criterio_versao;

COMMENT ON COLUMN classificacao_aluno.zona IS NULL;

COMMIT;
