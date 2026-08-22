-- "Sempre o Canvas + alterações do SAS" (docs/18 §2.4).
--
-- Até aqui uma nota editada pelo coordenador só sobrevivia se fosse gravada
-- no Canvas primeiro — senão o sync de 5 min trazia o valor do Canvas por
-- cima e a edição evaporava (cabeçalho de routes/notas.py). A coordenação
-- decidiu que a edição NÃO sobe ao Canvas automaticamente, então o banco
-- precisa guardar os dois valores e saber qual exibir.
--
--   pontuacao_canvas  ← o que o Canvas diz. O sync escreve SEMPRE.
--   pontuacao_sas     ← a edição do coordenador. NULL se ninguém editou.
--   pontuacao         ← o que o SAS exibe e usa em toda estatística:
--                       COALESCE(pontuacao_sas, pontuacao_canvas).
--
-- Por que `pontuacao` continua existindo como coluna, e não vira view: há
-- 273 leituras de `nota.pontuacao` no backend. Mantê-la como "o valor em
-- vigor" faz todas continuarem certas sem tocar em nenhuma. O trigger abaixo
-- é o único lugar que precisa saber da regra — e é o único que vê todo
-- write, venha ele do sync, da edição ou de um script.
--
-- A divergência é DERIVADA (pontuacao_sas IS NOT NULL AND pontuacao_sas IS
-- DISTINCT FROM pontuacao_canvas), não um estado a manter em dia.

BEGIN;

ALTER TABLE nota
    ADD COLUMN IF NOT EXISTS pontuacao_canvas numeric(6, 2),
    ADD COLUMN IF NOT EXISTS pontuacao_sas    numeric(6, 2),
    ADD COLUMN IF NOT EXISTS editada_em       timestamptz,
    ADD COLUMN IF NOT EXISTS editada_por      text;

COMMENT ON COLUMN nota.pontuacao        IS 'O valor EM VIGOR: COALESCE(pontuacao_sas, pontuacao_canvas). Mantido pelo trigger; não escrever direto.';
COMMENT ON COLUMN nota.pontuacao_canvas IS 'O que o Canvas diz. O sync escreve sempre, mesmo depois de uma edição no SAS.';
COMMENT ON COLUMN nota.pontuacao_sas    IS 'Edição do coordenador. NULL = nunca editada. Prevalece sobre o Canvas na exibição.';
COMMENT ON COLUMN nota.editada_por      IS 'id de usuario_coordenacao. Quem editou, para a trilha de auditoria.';

-- Backfill: tudo que existe veio do Canvas (ou da planilha do Canvas).
UPDATE nota SET pontuacao_canvas = pontuacao WHERE pontuacao_canvas IS NULL;

-- O trigger decide `pontuacao` a partir das duas fontes. Quem escreve só
-- diz de ONDE veio o valor; nunca precisa calcular o que fica em vigor.
CREATE OR REPLACE FUNCTION nota_resolver_pontuacao() RETURNS trigger AS $$
BEGIN
    -- Compatibilidade: um write antigo que só mande `pontuacao` (sem dizer a
    -- origem) é tratado como vindo do Canvas — é o que o sync e o ingest da
    -- planilha sempre foram.
    IF TG_OP = 'INSERT' AND NEW.pontuacao_canvas IS NULL AND NEW.pontuacao_sas IS NULL THEN
        NEW.pontuacao_canvas := NEW.pontuacao;
    ELSIF TG_OP = 'UPDATE'
          AND NEW.pontuacao IS DISTINCT FROM OLD.pontuacao
          AND NEW.pontuacao_canvas IS NOT DISTINCT FROM OLD.pontuacao_canvas
          AND NEW.pontuacao_sas    IS NOT DISTINCT FROM OLD.pontuacao_sas THEN
        NEW.pontuacao_canvas := NEW.pontuacao;
    END IF;

    NEW.pontuacao := COALESCE(NEW.pontuacao_sas, NEW.pontuacao_canvas);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_nota_resolver_pontuacao ON nota;
CREATE TRIGGER trg_nota_resolver_pontuacao
    BEFORE INSERT OR UPDATE ON nota
    FOR EACH ROW EXECUTE FUNCTION nota_resolver_pontuacao();

-- ─── ciclo: estado de sincronização, como simulado já tem ───────────────
-- 'divergente' é o valor novo: o coordenador ESCOLHEU não mandar. O retry
-- automático (agendamento.reprocessar_canvas_pendentes) ignora esse estado
-- por definição — docs/18 §2.5.

ALTER TABLE ciclo
    ADD COLUMN IF NOT EXISTS canvas_estado text
        CHECK (canvas_estado IN ('pendente', 'falhou', 'sincronizado', 'divergente')),
    ADD COLUMN IF NOT EXISTS canvas_erro text;

UPDATE ciclo SET canvas_estado = 'sincronizado'
 WHERE canvas_estado IS NULL AND canvas_assignment_group_id IS NOT NULL;

COMMENT ON COLUMN ciclo.canvas_estado IS 'NULL = veio do Canvas. divergente = coordenador escolheu não criar o grupo lá; o retry nunca reenvia sozinho.';

-- simulado já tinha canvas_estado (0018) sem CHECK; o valor novo precisa ser
-- aceito onde houver um. Só documenta.
COMMENT ON COLUMN simulado.canvas_estado IS 'pendente | falhou | sincronizado | divergente. divergente = coordenador escolheu não mandar; o retry automático ignora.';

COMMIT;
