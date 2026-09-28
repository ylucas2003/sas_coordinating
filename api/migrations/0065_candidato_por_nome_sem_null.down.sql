BEGIN;

DROP MATERIALIZED VIEW v_candidato_externo_por_nome;

-- Restaura o formato da 0063 — inclusive o bug do array_agg FILTER sem
-- linha virando NULL. Down restaura schema, não conserta bug.
CREATE MATERIALIZED VIEW v_candidato_externo_por_nome AS
SELECT
    c.nome_normalizado,
    (array_agg(c.nome ORDER BY c.atualizado_em DESC))[1]     AS nome,
    array_agg(DISTINCT NULLIF(ce.escola_informada, ''))
        FILTER (WHERE NULLIF(ce.escola_informada, '') IS NOT NULL) AS escolas,
    array_agg(DISTINCT NULLIF(ce.cidade_informada, ''))
        FILTER (WHERE NULLIF(ce.cidade_informada, '') IS NOT NULL) AS cidades,
    array_agg(DISTINCT NULLIF(ce.uf_informada, ''))
        FILTER (WHERE NULLIF(ce.uf_informada, '') IS NOT NULL)     AS ufs,
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

COMMENT ON MATERIALIZED VIEW v_candidato_externo_por_nome IS
    'Uma linha por nome_normalizado, SEMPRE — sem "perfil representante" nem fila de fusão (simplificação de 25/09/2026). escolas/cidades/ufs são o CONJUNTO de conquista_externa.*_informada de todo mundo com este nome (arrays independentes, não pareados). Filtro por UF/status é .contains(), bate se QUALQUER perfil/conquista do nome casar. Fonte de GET /captacao/candidatos. MATERIALIZADA por custo (mesmo motivo da 0062) — atualizada via RPC em BackgroundTasks por toda escrita relevante.';

COMMIT;
