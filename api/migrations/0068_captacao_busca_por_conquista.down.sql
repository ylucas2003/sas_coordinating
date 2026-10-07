-- Par da 0068: volta a lista geral pra forma da 0065 (participação conta
-- como conquista), tira a busca por conquista e as colunas novas.

BEGIN;

DROP FUNCTION IF EXISTS buscar_candidatos_por_conquista;

DROP MATERIALIZED VIEW v_candidato_externo_por_nome;

CREATE MATERIALIZED VIEW v_candidato_externo_por_nome AS
SELECT
    c.nome_normalizado,
    (array_agg(c.nome ORDER BY c.atualizado_em DESC))[1]     AS nome,
    COALESCE(
        array_agg(DISTINCT NULLIF(ce.escola_informada, ''))
            FILTER (WHERE NULLIF(ce.escola_informada, '') IS NOT NULL),
        ARRAY[]::text[]
    )                                                         AS escolas,
    COALESCE(
        array_agg(DISTINCT NULLIF(ce.cidade_informada, ''))
            FILTER (WHERE NULLIF(ce.cidade_informada, '') IS NOT NULL),
        ARRAY[]::text[]
    )                                                         AS cidades,
    COALESCE(
        array_agg(DISTINCT NULLIF(ce.uf_informada, ''))
            FILTER (WHERE NULLIF(ce.uf_informada, '') IS NOT NULL),
        ARRAY[]::text[]
    )                                                         AS ufs,
    array_agg(DISTINCT c.status_captacao)                    AS status_captacao,
    count(ce.id)::int                                        AS conquistas_total,
    count(DISTINCT ce.prova_id)::int                         AS provas_distintas,
    count(DISTINCT c.id)::int                                AS perfis_no_grupo,
    max(ce.ano)                                              AS ano_mais_recente,
    min(c.criado_em)                                         AS criado_em,
    max(c.atualizado_em)                                     AS atualizado_em
FROM candidato_externo c
LEFT JOIN conquista_externa ce ON ce.candidato_id = c.id
GROUP BY c.nome_normalizado
WITH DATA;

CREATE UNIQUE INDEX v_candext_por_nome_nome_idx
    ON v_candidato_externo_por_nome (nome_normalizado);
CREATE INDEX v_candext_por_nome_ordem_idx
    ON v_candidato_externo_por_nome (conquistas_total DESC, nome_normalizado);
CREATE INDEX v_candext_por_nome_ufs_gin_idx
    ON v_candidato_externo_por_nome USING GIN (ufs);
CREATE INDEX v_candext_por_nome_status_gin_idx
    ON v_candidato_externo_por_nome USING GIN (status_captacao);

DROP INDEX IF EXISTS idx_conquista_externa_faixa;
ALTER TABLE conquista_externa
    DROP COLUMN IF EXISTS ano_conclusao_max,
    DROP COLUMN IF EXISTS ano_conclusao_min,
    DROP COLUMN IF EXISTS faixa;

COMMIT;
