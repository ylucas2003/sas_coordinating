-- Simplificação radical da captação externa (docs/41, 25/09/2026): tira toda
-- "inteligência" de agrupamento automático e de alerta de confiança.
-- candidato_externo_fusao_decisao marcava um nome como "já decidido" e o
-- excluía PRA SEMPRE da fila de revisão — 4.395 desses nomes (de 17.427,
-- todos decididos por confirmar_fusoes_alta_confianca.py, NUNCA por um
-- humano) já tinham ganhado conquista nova depois da decisão e ficaram
-- invisíveis pra sempre (achado em produção: "Yan Lucas Freitas de Araújo"
-- tinha 12 candidato_externo, nenhum visível em lugar nenhum).
--
-- Dali pra frente, agrupar é só manual (arrastar em CaptacaoPerfil.tsx —
-- routes/captacao.py::mover_conquista). resolver_candidatos_externos.py já
-- foi reescrito pra nunca mais agrupar por (nome, escola); toda conquista
-- nasce com o PRÓPRIO candidato_externo.
--
-- ⚠️ Rodar api/scripts/separar_candidatos_externos.py ANTES desta migration
-- (--simular primeiro) — ele só mexe em candidato_externo/conquista_externa
-- crus, não depende de view nenhuma. Rodar depois também funciona (a view
-- só reflete o estado atual da tabela), mas deixa a lista mostrando, por um
-- tempo, nomes cujo agrupamento automático antigo ainda não foi desfeito.
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

-- ── 1. Fila de fusão e a view materializada antiga saem de cena ──────────
DROP FUNCTION IF EXISTS atualizar_v_candidato_externo_agrupado();
DROP MATERIALIZED VIEW IF EXISTS v_candidato_externo_agrupado;
DROP VIEW IF EXISTS v_fusao_candidata;
DROP TABLE IF EXISTS candidato_externo_fusao_decisao;

-- ── 2. View nova: um nome_normalizado, sempre UMA linha ──────────────────
--
-- Sem HAVING count(*) > 1 nenhum — ao contrário das duas views antigas,
-- aqui TODO nome vira linha, mesmo quem tem 1 candidato_externo e 1
-- conquista (o caso mais comum agora que nada agrupa sozinho).
--
-- escolas/cidades/ufs vêm de conquista_externa.*_informada — NÃO do
-- "retrato" de candidato_externo — porque um nome pode ter N perfis ainda
-- não arrumados à mão, e o retrato de cada perfil só reflete a conquista
-- mais recente DAQUELE perfil, não o conjunto inteiro do nome.
--
-- ⚠️ cidades/ufs são arrays INDEPENDENTES (array_agg DISTINCT cada um) — NÃO
-- pareados por índice entre si. Duas conquistas podem repetir a mesma
-- cidade com UF diferente por erro de digitação da fonte — nunca zipar
-- cidades[i]+ufs[i] no front; mostrar como duas listas soltas.
--
-- (array_agg(c.nome ORDER BY c.atualizado_em DESC))[1]: nome de EXIBIÇÃO
-- (com acento/maiúscula certos) vem do perfil tocado mais recentemente —
-- mesma convenção "mais recente vence" que _serie_dominante já usa em
-- routes/captacao.py; aqui é só rótulo, nada mais lê esse valor de volta.
CREATE MATERIALIZED VIEW v_candidato_externo_por_nome AS
SELECT
    c.nome_normalizado,
    (array_agg(c.nome ORDER BY c.atualizado_em DESC))[1]     AS nome,
    -- NULLIF(..., '') antes do FILTER, não só IS NOT NULL: a fonte raspada
    -- às vezes grava string vazia em vez de omitir a coluna (achado ao
    -- aplicar, 28/09/2026 — "" aparecia misturado com valor de verdade nos
    -- três arrays). Mesmo truque de v_fusao_candidata (0059) pra uf.
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

-- Único índice ÚNICO obrigatório pra REFRESH ... CONCURRENTLY — de graça
-- aqui: nome_normalizado JÁ é a chave natural da linha (o GROUP BY), ao
-- contrário da view antiga, que precisava do id de um "representante"
-- escolhido por DISTINCT ON.
CREATE UNIQUE INDEX v_candext_por_nome_nome_idx
    ON v_candidato_externo_por_nome (nome_normalizado);

-- Cobre a ordenação padrão de listar_candidatos. Sem 3º critério de
-- desempate — nome_normalizado já é único por linha.
CREATE INDEX v_candext_por_nome_ordem_idx
    ON v_candidato_externo_por_nome (conquistas_total DESC, nome_normalizado);

-- GIN, não btree — só GIN sabe usar índice pro operador @> que .contains()
-- do postgrest-py gera. Só nas DUAS colunas que a rota de fato filtra
-- (UF e status); escolas/cidades são só exibição hoje.
CREATE INDEX v_candext_por_nome_ufs_gin_idx
    ON v_candidato_externo_por_nome USING GIN (ufs);
CREATE INDEX v_candext_por_nome_status_gin_idx
    ON v_candidato_externo_por_nome USING GIN (status_captacao);

-- SECURITY DEFINER: REFRESH exige ser DONO da view materializada (mesmo
-- motivo da 0062 — quem chama via RPC, sas_service, não é dono).
CREATE OR REPLACE FUNCTION atualizar_v_candidato_externo_por_nome()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY v_candidato_externo_por_nome;
END;
$$;

-- ── 3. Resumo por prova, pro rodapé "quais fontes alimentam a lista" ─────
--
-- 10 linhas hoje (uma por prova_externa — o nome JÁ é o rótulo: "ITA",
-- "IME", "OBMEP"...), junção barata (conquista_externa.prova_id é indexado,
-- 0056). VIEW comum, não materializada: 10 linhas não justificam refresh em
-- background.
CREATE VIEW v_prova_externa_resumo AS
SELECT
    p.nome, p.categoria,
    min(ce.ano)::int AS ano_min, max(ce.ano)::int AS ano_max,
    count(ce.id)::int AS conquistas_total
FROM prova_externa p
LEFT JOIN conquista_externa ce ON ce.prova_id = p.id
GROUP BY p.nome, p.categoria;

COMMENT ON MATERIALIZED VIEW v_candidato_externo_por_nome IS
    'Uma linha por nome_normalizado, SEMPRE — sem "perfil representante" nem fila de fusão (simplificação de 25/09/2026). escolas/cidades/ufs são o CONJUNTO de conquista_externa.*_informada de todo mundo com este nome (arrays independentes, não pareados). Filtro por UF/status é .contains() (cs.{...}), bate se QUALQUER perfil/conquista do nome casar. perfis_no_grupo é sempre >= 1. Fonte de GET /captacao/candidatos; GET /captacao/perfis/{nome} continua lendo v_candidato_externo direto (0058), porque ali é sempre sobre UM perfil por vez. MATERIALIZADA por custo (mesmo motivo da 0062) — atualizar_v_candidato_externo_por_nome() é chamada via RPC do PostgREST em BackgroundTasks por toda escrita relevante em routes/captacao.py.';
COMMENT ON FUNCTION atualizar_v_candidato_externo_por_nome() IS
    'REFRESH CONCURRENTLY de v_candidato_externo_por_nome (0063). SECURITY DEFINER pelo mesmo motivo da 0062: quem chama via RPC (sas_service) não é dono da matview.';
COMMENT ON VIEW v_prova_externa_resumo IS
    'Uma linha por prova_externa, com o intervalo de anos carregado (min/max de conquista_externa.ano) — alimenta o rodapé "quais fontes alimentam a lista" de GET /captacao/provas.';

COMMIT;
