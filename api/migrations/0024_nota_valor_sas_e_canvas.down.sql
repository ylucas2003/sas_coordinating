-- Reverte a 0024. As edições do coordenador em `pontuacao_sas` se PERDEM —
-- `pontuacao` fica com o último valor em vigor, que as incluía.
BEGIN;
DROP TRIGGER IF EXISTS trg_nota_resolver_pontuacao ON nota;
DROP FUNCTION IF EXISTS nota_resolver_pontuacao();
ALTER TABLE nota
    DROP COLUMN IF EXISTS pontuacao_canvas,
    DROP COLUMN IF EXISTS pontuacao_sas,
    DROP COLUMN IF EXISTS editada_em,
    DROP COLUMN IF EXISTS editada_por;
ALTER TABLE ciclo
    DROP COLUMN IF EXISTS canvas_estado,
    DROP COLUMN IF EXISTS canvas_erro;
COMMIT;
