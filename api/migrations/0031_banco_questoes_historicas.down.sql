-- Desfaz a 0030. As colunas saem inteiras, e com elas a distinção entre gabarito
-- da banca e gabarito deduzido — então descer esta migration com acervo histórico
-- já importado deixaria letras sugeridas indistinguíveis das oficiais na tela.
-- Antes de rodar, confira que não há linha com gabarito_origem = 'sugerido':
--
--   SELECT count(*) FROM questao_vestibular WHERE gabarito_origem = 'sugerido';
--
-- Se houver, apague essas questões antes — ou mantenha a migration.

BEGIN;

DROP INDEX IF EXISTS idx_questao_vestibular_sugerido;

ALTER TABLE questao_vestibular
    DROP CONSTRAINT IF EXISTS questao_vestibular_gabarito_origem_check,
    DROP CONSTRAINT IF EXISTS questao_vestibular_gabarito_origem_presente,
    DROP CONSTRAINT IF EXISTS questao_vestibular_gabarito_confianca_check,
    DROP CONSTRAINT IF EXISTS questao_vestibular_confianca_so_em_sugerido,
    DROP CONSTRAINT IF EXISTS questao_vestibular_resolucao_origem_check,
    DROP CONSTRAINT IF EXISTS questao_vestibular_resolucao_coerente,
    DROP CONSTRAINT IF EXISTS questao_vestibular_extraido_por_check;

ALTER TABLE questao_vestibular
    DROP COLUMN IF EXISTS gabarito_origem,
    DROP COLUMN IF EXISTS gabarito_confianca,
    DROP COLUMN IF EXISTS resolucao_md,
    DROP COLUMN IF EXISTS resolucao_origem,
    DROP COLUMN IF EXISTS extraido_por;

COMMIT;
