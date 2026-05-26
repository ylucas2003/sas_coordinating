-- Reverte 0006: remove colunas avançadas e a tabela de cache de insights.

BEGIN;

DROP TABLE IF EXISTS insight_ciclo;

ALTER TABLE metrica_simulado
    DROP COLUMN IF EXISTS skewness,
    DROP COLUMN IF EXISTS curtose,
    DROP COLUMN IF EXISTS p10,
    DROP COLUMN IF EXISTS p90,
    DROP COLUMN IF EXISTS moda,
    DROP COLUMN IF EXISTS pct_aprovados,
    DROP COLUMN IF EXISTS pct_zona_critica,
    DROP COLUMN IF EXISTS pct_excelencia,
    DROP COLUMN IF EXISTS bimodal_flag;

COMMIT;
