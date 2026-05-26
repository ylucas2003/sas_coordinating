-- ─────────────────────────────────────────────────────────────────────────
-- 0006 · métricas estatísticas avançadas + cache de insights LLM
--
-- (A) Estende `metrica_simulado` com indicadores que o coordenador pediu pra
--     ler nas fichas de ciclo: forma da distribuição (skewness, curtose),
--     percentis extremos (P10, P90), moda, taxas por corte e flag de
--     bimodalidade.
--
-- (B) Cria `insight_ciclo` — cache dos textos gerados por LLM a partir das
--     estatísticas. Chaveado por (ciclo_id, fase, materia_codigo) + um hash
--     do payload de stats que alimentou o modelo. Se o hash mudar (nota
--     nova chegou), o cache expira por construção.
--
-- Reversível via 0006_*.down.sql.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

-- ── (A) métrica_simulado: novas colunas ──

ALTER TABLE metrica_simulado
    ADD COLUMN skewness            numeric(7, 3),
    ADD COLUMN curtose             numeric(7, 3),
    ADD COLUMN p10                 numeric(6, 2),
    ADD COLUMN p90                 numeric(6, 2),
    ADD COLUMN moda                numeric(6, 2),
    ADD COLUMN pct_aprovados       numeric(5, 2),
    ADD COLUMN pct_zona_critica    numeric(5, 2),
    ADD COLUMN pct_excelencia      numeric(5, 2),
    ADD COLUMN bimodal_flag        boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN metrica_simulado.skewness         IS 'Assimetria (3º momento padronizado). Positiva = cauda à direita.';
COMMENT ON COLUMN metrica_simulado.curtose          IS 'Excesso de curtose (4º momento − 3). Positiva = caudas pesadas.';
COMMENT ON COLUMN metrica_simulado.p10              IS 'Percentil 10 — limite inferior da turma típica.';
COMMENT ON COLUMN metrica_simulado.p90              IS 'Percentil 90 — limite superior da turma típica.';
COMMENT ON COLUMN metrica_simulado.moda             IS 'Centro do bin mais alto do histograma. Estimativa rápida da moda.';
COMMENT ON COLUMN metrica_simulado.pct_aprovados    IS '% de presentes com nota ≥ corte aplicável (4,0 geral / 5,0 Inglês ITA F1).';
COMMENT ON COLUMN metrica_simulado.pct_zona_critica IS '% com nota em [corte−1, corte).';
COMMENT ON COLUMN metrica_simulado.pct_excelencia   IS '% com nota ≥ 7,0.';
COMMENT ON COLUMN metrica_simulado.bimodal_flag     IS 'true se detectados ≥ 2 picos significativos no histograma.';


-- ── (B) insight_ciclo: cache dos textos do LLM ──

CREATE TABLE insight_ciclo (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ciclo_id        uuid NOT NULL REFERENCES ciclo(id),
    fase            text NOT NULL CHECK (fase IN ('fase_1', 'fase_2')),
    materia_codigo  text,
    hash_payload    text NOT NULL,
    bullets         jsonb NOT NULL,
    modelo          text NOT NULL,
    gerado_em       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ciclo_id, fase, materia_codigo, hash_payload)
);

CREATE INDEX idx_insight_ciclo_lookup
    ON insight_ciclo (ciclo_id, fase, materia_codigo);

COMMENT ON TABLE  insight_ciclo                IS 'Cache dos bullets gerados por LLM a partir das estatísticas de um recorte de ciclo.';
COMMENT ON COLUMN insight_ciclo.materia_codigo IS 'NULL para o recorte "geral" (nota agregada do aluno). Slug da matéria nos recortes por matéria.';
COMMENT ON COLUMN insight_ciclo.hash_payload   IS 'sha256 truncado das estatísticas que alimentaram o LLM. Mudou = regerar.';
COMMENT ON COLUMN insight_ciclo.bullets        IS 'Lista de strings (3–5 itens curtos).';
COMMENT ON COLUMN insight_ciclo.modelo         IS 'Identificador do modelo (ex.: claude-sonnet-4-6) — útil pra auditar regerações.';

COMMIT;
