-- ─────────────────────────────────────────────────────────────────────────
-- 0003 · vestibular_alvo no ciclo + tipo no simulado
--
-- Captura a estrutura real dos vestibulares-alvo (ITA e IME) e a regra que
-- distingue Fase 1 (uma prova combinada) de Fase 2 (matérias separadas).
-- Ciclos que não têm vestibular_alvo ITA/IME são descartados na ingestão.
-- ─────────────────────────────────────────────────────────────────────────

-- ─── Ciclo ganha vestibular_alvo ──────────────────────────────────────────

ALTER TABLE ciclo
    ADD COLUMN vestibular_alvo text;

ALTER TABLE ciclo
    ADD CONSTRAINT ciclo_vestibular_alvo_check
    CHECK (vestibular_alvo IS NULL OR vestibular_alvo IN ('ITA', 'IME'));

COMMENT ON COLUMN ciclo.vestibular_alvo IS
    'Vestibular ao qual este ciclo se dedica (ITA ou IME). Extraído pela '
    'ingestão das colunas "N° CICLO - VESTIBULAR Final Score" da planilha. '
    'Ciclos sem vestibular ITA/IME identificável (ENEM, SAS) não são '
    'persistidos.';

CREATE INDEX idx_ciclo_vestibular ON ciclo(vestibular_alvo);


-- ─── Simulado: troca `fase` por `tipo` mais expressivo ────────────────────

-- A coluna `fase` (valores '1a' / '2a') nunca foi populada pelo pipeline e
-- não distinguia Fase 1 combinada de Fase 2 individual. Substituímos por
-- `tipo` que tem valores semânticos: 'fase_1' | 'fase_2'.

ALTER TABLE simulado
    DROP COLUMN fase;

ALTER TABLE simulado
    ADD COLUMN tipo text;

ALTER TABLE simulado
    ADD CONSTRAINT simulado_tipo_check
    CHECK (tipo IS NULL OR tipo IN ('fase_1', 'fase_2'));

COMMENT ON COLUMN simulado.tipo IS
    'Categoria do simulado segundo a estrutura do vestibular-alvo do ciclo: '
    'fase_1 (uma prova combinada cobrindo várias matérias — ex.: P1 com '
    'Mat+Fis+Quim para IME, ou Mat+Fis+Quim+Inglês para ITA); fase_2 (uma '
    'prova por matéria, com Pn distintas — ex.: P2 Mat, P3 Fis, P4 Quim). '
    'O parser infere o tipo agrupando simulados pela rótulo Pn dentro do '
    'mesmo ciclo: 2+ matérias core (Mat/Fis/Quim) compartilhando Pn = fase_1.';

CREATE INDEX idx_simulado_tipo ON simulado(tipo);
