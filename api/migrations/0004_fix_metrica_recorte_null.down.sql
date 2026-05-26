-- ─────────────────────────────────────────────────────────────────────────
-- 0004 · DOWNGRADE — volta a PK estrita em metrica_simulado.
--
-- Cuidado: reaplicar 0004 → 0004-down → 0004 quebra se há linhas com
-- recorte_id IS NULL. O downgrade força recorte_id NOT NULL e recria a PK
-- original — qualquer linha 'geral' (recorte_id NULL) presente vai bloquear.
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE metrica_simulado
    DROP CONSTRAINT IF EXISTS metrica_simulado_chave_natural;

-- Pré-condição implícita: nenhuma linha com recorte_id NULL.
-- Se quiser forçar, apague-as antes:
--     DELETE FROM metrica_simulado WHERE recorte_id IS NULL;
ALTER TABLE metrica_simulado
    ALTER COLUMN recorte_id SET NOT NULL;

ALTER TABLE metrica_simulado
    ADD CONSTRAINT metrica_simulado_pkey
    PRIMARY KEY (simulado_id, recorte_tipo, recorte_id);
