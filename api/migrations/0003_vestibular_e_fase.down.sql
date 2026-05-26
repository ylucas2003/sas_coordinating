-- ─────────────────────────────────────────────────────────────────────────
-- 0003 · DOWNGRADE — desfaz vestibular_alvo + tipo (volta pra fase '1a'/'2a').
-- ─────────────────────────────────────────────────────────────────────────

DROP INDEX IF EXISTS idx_simulado_tipo;
ALTER TABLE simulado DROP CONSTRAINT IF EXISTS simulado_tipo_check;
ALTER TABLE simulado DROP COLUMN IF EXISTS tipo;
ALTER TABLE simulado ADD COLUMN fase text CHECK (fase IN ('1a', '2a'));

DROP INDEX IF EXISTS idx_ciclo_vestibular;
ALTER TABLE ciclo DROP CONSTRAINT IF EXISTS ciclo_vestibular_alvo_check;
ALTER TABLE ciclo DROP COLUMN IF EXISTS vestibular_alvo;
