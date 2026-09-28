-- Corrige um bug de verdade em produção (achado 28/09/2026, tela branca ao
-- buscar em /administracao/captacao): `array_agg(x) FILTER (WHERE cond)` do
-- Postgres devolve NULL — não `{}` — quando NENHUMA linha do grupo passa no
-- filtro. `v_candidato_externo_por_nome` (migration 0063) usa exatamente esse
-- padrão pra escolas/cidades/ufs, e qualquer nome cujas conquistas nunca
-- tiveram esse campo preenchido vira `null` em vez de lista vazia.
--
-- 25.554 nomes com escolas NULL, 26.453 com cidades NULL, 17.984 com ufs
-- NULL — quase um quarto da base. `tipos/captacao.ts::CandidatoPorNome`
-- declara os três como `string[]` (nunca `| null`), e `Captacao.tsx::fmtLista`
-- faz `itens.length` sem guarda — qualquer busca que trouxesse um desses
-- nomes pra dentro da página (20 por vez) derrubava a tela inteira, sem
-- ErrorBoundary nenhum pra pegar (mesma classe de crash do
-- `recuperacaoDeChunk.ts`, causa diferente).
--
-- `status_captacao` NÃO tem esse bug: `candidato_externo.status_captacao` é
-- `NOT NULL DEFAULT 'novo'`, então o `array_agg` sem FILTER nunca fica sem
-- linha nenhuma pra agregar.

BEGIN;

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

COMMENT ON MATERIALIZED VIEW v_candidato_externo_por_nome IS
    'Uma linha por nome_normalizado, SEMPRE — sem "perfil representante" nem fila de fusão (simplificação de 25/09/2026). escolas/cidades/ufs são o CONJUNTO de conquista_externa.*_informada de todo mundo com este nome (arrays independentes, não pareados), NUNCA null — COALESCE pra array vazio (0065, bug de array_agg FILTER sem linha). Filtro por UF/status é .contains(), bate se QUALQUER perfil/conquista do nome casar. Fonte de GET /captacao/candidatos. MATERIALIZADA por custo (mesmo motivo da 0062) — atualizada via RPC em BackgroundTasks por toda escrita relevante.';

COMMIT;
