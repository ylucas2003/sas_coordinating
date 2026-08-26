-- Reverte 0033. Só é seguro se nenhuma linha usa extraido_por = 'pagina' ou
-- tem enunciado_md NULL — senão o CHECK/NOT NULL antigos rejeitam dado já
-- gravado e o `migrate down` falha no meio, com a mesma transação revertida.

BEGIN;

ALTER TABLE questao_vestibular
    DROP CONSTRAINT questao_vestibular_enunciado_presente;

ALTER TABLE questao_vestibular
    ALTER COLUMN enunciado_md SET NOT NULL;

ALTER TABLE questao_vestibular
    DROP CONSTRAINT questao_vestibular_extraido_por_check;

ALTER TABLE questao_vestibular
    ADD CONSTRAINT questao_vestibular_extraido_por_check
        CHECK (extraido_por IN ('pipeline', 'visao'));

COMMENT ON COLUMN questao_vestibular.extraido_por IS
  '''pipeline'' = PDF nativo, texto extraído direto; ''visao'' = página '
  'escaneada lida como imagem, porque o OCR não dá conta de prova '
  'datilografada. É por onde se acha o lote a reconferir.';
COMMENT ON COLUMN questao_vestibular.enunciado_md IS NULL;

COMMIT;
