-- View de leitura para a tela de captação externa (docs/41 §7.1).
--
-- `GET /captacao/candidatos` precisa filtrar por Nº MÍNIMO de conquistas
-- ("candidatos com 4 conquistas" é o próprio exemplo do docs/41 §5) e paginar
-- de verdade — 26 mil linhas e crescendo a cada fonte nova. Nenhuma das duas
-- coisas dá para fazer só com `.table("candidato_externo")...`: o número de
-- conquistas é um COUNT sobre `conquista_externa`, e o backend nunca escreve
-- SQL nas rotas (CLAUDE.md raiz, §"get_supabase() não fala com Supabase").
--
-- A view é o mesmo truque de `v_pedidos_por_cardapio` (0052): a conta pesada
-- mora no banco, uma vez, e a rota só faz `.table("v_candidato_externo")
-- .gte("conquistas_total", N)...` — filtro comum do PostgREST, sem HAVING
-- escondido em lugar nenhum.
--
-- LEFT JOIN, não INNER: um candidato sem conquista_externa nenhuma (não deve
-- acontecer — candidato_externo só nasce do resolver a partir de conquistas —,
-- mas a view não deve escondê-lo se acontecer) aparece com 0 em vez de sumir
-- da lista.
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

CREATE OR REPLACE VIEW v_candidato_externo AS
SELECT
    c.id, c.nome, c.nome_normalizado, c.escola, c.cidade, c.uf,
    c.serie_referencia_min, c.serie_referencia_max, c.ano_referencia_serie,
    c.status_captacao, c.observacoes, c.criado_em, c.atualizado_em,
    count(ce.id)::int             AS conquistas_total,
    count(DISTINCT ce.prova_id)::int AS provas_distintas,
    max(ce.ano)                   AS ano_mais_recente
FROM candidato_externo c
LEFT JOIN conquista_externa ce ON ce.candidato_id = c.id
GROUP BY c.id;

COMMENT ON VIEW v_candidato_externo IS
    'Um candidato por linha, com o resumo que a lista de captação precisa pra filtrar e ordenar: conquistas_total (pra "nº mínimo de conquistas"), provas_distintas e ano_mais_recente. Só leitura — status_captacao e observacoes continuam escritos em candidato_externo direto (PATCH /captacao/candidatos/{id}), nunca por aqui.';

COMMIT;
