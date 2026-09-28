-- Reverte a 0063: derruba a view nova, recria a fila de fusão (0059/0061) e
-- a view materializada antiga (0062) exatamente como estavam.
--
-- ⚠️ NÃO desfaz api/scripts/separar_candidatos_externos.py — os
-- candidato_externo que ele separou continuam separados; down restaura
-- SCHEMA, nunca dado apagado (mesma régua da 0059.down.sql).
-- candidato_externo_fusao_decisao volta VAZIA: as 17.427 decisões que
-- existiam antes desta migration foram apagadas pelo DROP TABLE da subida.
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

DROP VIEW IF EXISTS v_prova_externa_resumo;
DROP FUNCTION IF EXISTS atualizar_v_candidato_externo_por_nome();
DROP MATERIALIZED VIEW IF EXISTS v_candidato_externo_por_nome;

CREATE TABLE IF NOT EXISTS candidato_externo_fusao_decisao (
    nome_normalizado text PRIMARY KEY,
    status           text NOT NULL
        CONSTRAINT fusao_decisao_status_valido
        CHECK (status IN ('confirmada', 'rejeitada')),
    decidido_por     text,
    decidido_em      timestamptz NOT NULL DEFAULT now()
);

CREATE VIEW v_fusao_candidata AS
SELECT
    c.nome_normalizado,
    count(*)::int AS candidatos,
    count(DISTINCT NULLIF(c.uf, '')) FILTER (WHERE c.uf IS NOT NULL)::int AS ufs_distintas,
    COALESCE(bool_or(c.observacoes ILIKE '%Possível engano: nível de ensino conflitante%'), false) AS tem_conflito_nivel
FROM candidato_externo c
WHERE NOT EXISTS (
    SELECT 1 FROM candidato_externo_fusao_decisao d
    WHERE d.nome_normalizado = c.nome_normalizado
)
GROUP BY c.nome_normalizado
HAVING count(*) > 1;

CREATE MATERIALIZED VIEW v_candidato_externo_agrupado AS
WITH grupo AS (
    SELECT
        c.nome_normalizado,
        count(*)::int AS perfis_no_grupo,
        sum(c.conquistas_total)::int AS conquistas_total_grupo,
        max(c.ano_mais_recente) AS ano_mais_recente_grupo,
        bool_or(c.observacoes ILIKE '%Possível engano: nível de ensino conflitante%') AS tem_conflito_nivel
    FROM v_candidato_externo c
    WHERE NOT EXISTS (
        SELECT 1 FROM candidato_externo_fusao_decisao d
        WHERE d.nome_normalizado = c.nome_normalizado
    )
    GROUP BY c.nome_normalizado
    HAVING count(*) > 1
)
SELECT DISTINCT ON (COALESCE(g.nome_normalizado, c.id::text))
    c.id, c.nome, c.nome_normalizado, c.escola, c.cidade, c.uf,
    c.serie_referencia_min, c.serie_referencia_max, c.ano_referencia_serie,
    c.status_captacao, c.observacoes, c.criado_em, c.atualizado_em,
    c.provas_distintas,
    COALESCE(g.conquistas_total_grupo, c.conquistas_total) AS conquistas_total,
    COALESCE(g.ano_mais_recente_grupo, c.ano_mais_recente) AS ano_mais_recente,
    COALESCE(g.perfis_no_grupo, 1) AS perfis_no_grupo,
    COALESCE(g.tem_conflito_nivel, false) AS tem_conflito_nivel
FROM v_candidato_externo c
LEFT JOIN grupo g ON g.nome_normalizado = c.nome_normalizado
ORDER BY COALESCE(g.nome_normalizado, c.id::text), c.conquistas_total DESC, c.criado_em ASC
WITH DATA;

CREATE UNIQUE INDEX v_candext_agrupado_id_idx ON v_candidato_externo_agrupado (id);
CREATE INDEX v_candext_agrupado_ordem_idx
    ON v_candidato_externo_agrupado (conquistas_total DESC, nome, id);
CREATE INDEX v_candext_agrupado_uf_idx ON v_candidato_externo_agrupado (uf);
CREATE INDEX v_candext_agrupado_status_idx ON v_candidato_externo_agrupado (status_captacao);

CREATE OR REPLACE FUNCTION atualizar_v_candidato_externo_agrupado()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY v_candidato_externo_agrupado;
END;
$$;

COMMIT;
