-- ─────────────────────────────────────────────────────────────────────────
-- 0007 · insights LLM em duas linguagens (técnica + prática) + recorte "todas"
--
-- (A) Adiciona `tipo_insight` em `insight_ciclo` pra suportar dois textos
--     por recorte: 'pratico' (linguagem de coordenador, visível por padrão)
--     e 'tecnico' (com jargão estatístico, vive na seção avançada).
--
-- (B) Relaxa o CHECK de `fase` pra aceitar 'todas' — usado nos insights da
--     análise conjunta (ciclo todo agregado, sem separar F1 e F2).
--
-- (C) Reconstrói o UNIQUE incluindo o tipo, pra os dois insights do mesmo
--     recorte conviverem.
--
-- Reversível via 0007_*.down.sql.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

-- ── (A) Coluna tipo_insight ──
ALTER TABLE insight_ciclo
    ADD COLUMN tipo_insight text NOT NULL DEFAULT 'pratico'
        CHECK (tipo_insight IN ('pratico', 'tecnico'));

COMMENT ON COLUMN insight_ciclo.tipo_insight IS
    'pratico = leitura para coordenador (linguagem acessível, visível por default na UI); '
    'tecnico = leitura com jargão estatístico (skewness, curtose, etc.), aparece só na seção avançada.';

-- ── (B) Relaxa CHECK de fase pra incluir 'todas' ──
ALTER TABLE insight_ciclo
    DROP CONSTRAINT insight_ciclo_fase_check;

ALTER TABLE insight_ciclo
    ADD CONSTRAINT insight_ciclo_fase_check
    CHECK (fase IN ('fase_1', 'fase_2', 'todas'));

COMMENT ON COLUMN insight_ciclo.fase IS
    'fase_1 / fase_2 = recorte daquela fase específica; '
    'todas = análise conjunta (média ponderada do aluno no ciclo todo, F1+F2 juntos).';

-- ── (C) Recria UNIQUE incluindo tipo_insight ──
ALTER TABLE insight_ciclo
    DROP CONSTRAINT insight_ciclo_ciclo_id_fase_materia_codigo_hash_payload_key;

ALTER TABLE insight_ciclo
    ADD CONSTRAINT insight_ciclo_chave_completa_key
    UNIQUE (ciclo_id, fase, materia_codigo, tipo_insight, hash_payload);

COMMIT;
