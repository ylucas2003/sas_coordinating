-- 0020 · down — desfaz o lembrete de aluno (P3)
--
-- A volta do CHECK só é possível se não houver regra de aluno viva: é o
-- comportamento correto (o down avisa em vez de apagar dado).
BEGIN;

DROP TABLE email_invalido;

DROP INDEX idx_disparo_enviado_em;
DROP INDEX idx_disparo_chave;
ALTER TABLE disparo DROP COLUMN chave_idempotencia;
ALTER TABLE disparo DROP COLUMN contexto;

DELETE FROM disparo WHERE regra_lembrete_id IN (
    SELECT id FROM regra_lembrete WHERE destinatario_tipo = 'aluno'
);
DELETE FROM regra_lembrete WHERE destinatario_tipo = 'aluno';

DO $$
DECLARE nome text;
BEGIN
    SELECT conname INTO nome
      FROM pg_constraint
     WHERE conrelid = 'regra_lembrete'::regclass
       AND contype  = 'c'
       AND pg_get_constraintdef(oid) ILIKE '%destinatario_tipo%';
    IF nome IS NOT NULL THEN
        EXECUTE format('ALTER TABLE regra_lembrete DROP CONSTRAINT %I', nome);
    END IF;
END $$;

ALTER TABLE regra_lembrete ADD CONSTRAINT regra_lembrete_destinatario_tipo_check
    CHECK (destinatario_tipo IN ('coordenador'));

COMMIT;
