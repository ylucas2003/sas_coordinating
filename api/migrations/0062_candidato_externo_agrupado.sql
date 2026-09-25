-- View agrupada pra lista geral de captação (GET /captacao/candidatos) não
-- expor a fragmentação interna do resolver.
--
-- O resolver (scripts/resolver_candidatos_externos.py) funde só por
-- nome+escola EXATOS — fontes sem escola (OBM, ITA, IME, Escola Naval) nunca
-- se juntam sozinhas a quem OBMEP/OBF/OBI já resolveram, mesmo sendo a mesma
-- pessoa. Isso é correto pro resolver (evita fusão errada por engano), mas
-- vaza pra quem só está caçando lead na lista geral: um nome ambíguo com 3
-- candidato_externo aparecia 3× numa busca. A fila de fusão (0059/0061) é
-- pra QUEM RESOLVE a duplicidade; esta view é pra QUEM BUSCA lead e não
-- precisa (nem deve) ver a fragmentação — só precisa saber que ela existe
-- ("3 perfis") e ir pra fila se quiser resolver.
--
-- Colapsa em UMA linha só enquanto o nome estiver PENDENTE (presente em
-- v_fusao_candidata, 0061). Nome já decidido como "pessoas diferentes"
-- (rejeitada em candidato_externo_fusao_decisao) ou nome único continua
-- linha-a-linha — nesses dois casos não é fragmentação, é gente diferente de
-- verdade, e esconder seria perder um lead.
--
-- ⚠️ É MATERIALIZED VIEW, não VIEW comum — de propósito, medido, não chutado.
-- A primeira versão (VIEW simples) levava ~1,3s por página contra 110ms da
-- v_candidato_externo de hoje (12×): o JOIN candidato_externo×conquista_externa
-- é recalculado DUAS vezes (direto + dentro do CTE de agrupamento) e o
-- `DISTINCT ON` força ordenar as ~116 mil linhas inteiras antes do `LIMIT`
-- poder cortar qualquer coisa — e o PostgREST ainda soma OUTRA passada igual
-- pra calcular `count=exact` na paginação. `docker compose exec db psql` com
-- `EXPLAIN (ANALYZE, BUFFERS)` confirmou (24/09/2026). Materializar resolve:
-- leitura vira índice, não recomputo. O preço é ficar atrasada entre uma
-- escrita e o próximo refresh — `atualizar_v_candidato_externo_agrupado()`
-- abaixo é chamada em BACKGROUND (depois da resposta já ter saído) por toda
-- rota de `routes/captacao.py` que escreve em candidato_externo/
-- conquista_externa, e o cron do resolver é o backstop pra quem não passou
-- por essas rotas (o próprio resolver, os scripts de fusão em lote).
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

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

-- Índice ÚNICO obrigatório pra `REFRESH ... CONCURRENTLY` (senão o refresh
-- bloqueia leitor — o motivo inteiro de materializar). `id` é único no
-- resultado por construção: o `DISTINCT ON` escolhe exatamente UMA linha por
-- grupo, e quem não é a escolhida simplesmente não aparece.
CREATE UNIQUE INDEX v_candext_agrupado_id_idx ON v_candidato_externo_agrupado (id);

-- Cobre a ordenação padrão de `listar_candidatos` (mais conquista primeiro,
-- desempate por nome e id) sem precisar reordenar tudo a cada página.
CREATE INDEX v_candext_agrupado_ordem_idx
    ON v_candidato_externo_agrupado (conquistas_total DESC, nome, id);
CREATE INDEX v_candext_agrupado_uf_idx ON v_candidato_externo_agrupado (uf);
CREATE INDEX v_candext_agrupado_status_idx ON v_candidato_externo_agrupado (status_captacao);

-- SECURITY DEFINER: REFRESH exige ser DONO da view materializada — quem cria
-- é o papel de migration (superusuário), quem chama via RPC é `sas_service`
-- (PGRST_DB_ANON_ROLE local), que não é dono. Sem isso o RPC volta 401/42501
-- "must be owner of materialized view" (confirmado ao vivo, 24/09/2026).
-- `SET search_path = public` fecha o vetor clássico de sequestro de search_path
-- em função SECURITY DEFINER — a função não referencia nada fora do schema
-- public, mas fixar o caminho custa zero e é a prática padrão.
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

COMMENT ON MATERIALIZED VIEW v_candidato_externo_agrupado IS
    'Mesma linha de v_candidato_externo, mas com os grupos AINDA PENDENTES na fila de fusão (v_fusao_candidata) colapsados num representante só — perfis_no_grupo diz quantos existem de verdade, conquistas_total já vem somado do grupo inteiro. Nome decidido como pessoas diferentes, ou nome único, passa reto (1 linha = 1 pessoa). Fonte de GET /captacao/candidatos; GET /captacao/candidatos/{id} continua lendo v_candidato_externo direto, porque a ficha é sempre sobre UM perfil específico. MATERIALIZADA por custo (ver comentário da migration 0062) — pode ficar segundos atrasada em relação à escrita mais recente; atualizar_v_candidato_externo_agrupado() é chamada via RPC do PostgREST por toda escrita relevante em routes/captacao.py.';
COMMENT ON FUNCTION atualizar_v_candidato_externo_agrupado() IS
    'REFRESH CONCURRENTLY da view agrupada de captação (0062). Chamada via POST /rpc/atualizar_v_candidato_externo_agrupado — é assim que routes/captacao.py atualiza a view sem escrever SQL na rota (CLAUDE.md raiz, "get_supabase() não fala com Supabase"): RPC é a própria API do PostgREST, não uma exceção à regra. Chamada em BACKGROUND (depois da resposta já ter saído) — o refresh sozinho já levou ~1,3s medido, ninguém deveria esperar por ele numa requisição síncrona.';

COMMIT;
