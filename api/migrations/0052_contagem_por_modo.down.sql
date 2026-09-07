-- Reverte a 0052: a view volta a ter só `cardapio_id` e `quantos`.
--
-- ⚠️ DROP + CREATE, e não `CREATE OR REPLACE`: o REPLACE acrescenta coluna no
-- fim, mas não REMOVE nenhuma — descer com ele daria
-- "cannot drop columns from view". Como a view é derrubada e recriada no mesmo
-- BEGIN, nenhuma leitura enxerga o buraco.
--
-- ⚠️ Ordem obrigatória em relação à API: `_calendario` (routes/cantina.py) pede
-- `com_pedido, presenciais` no select, e coluna ausente no PostgREST é 400, não
-- nulo — vira 500 no calendário das duas telas. A API volta para a versão
-- anterior à 0052 ANTES deste down. É a mesma advertência do down da 0051.
--
-- ⚠️ Reverter a 0049 sem passar por aqui antes deixa o banco SEM a view: o
-- `DROP VIEW` da 0049 leva esta definição junto, e o calendário passa a devolver
-- erro do PostgREST em vez de lista vazia.
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

DROP VIEW IF EXISTS v_pedidos_por_cardapio;

CREATE VIEW v_pedidos_por_cardapio AS
SELECT
    c.id                    AS cardapio_id,
    count(p.id)::int        AS quantos
FROM cardapio c
LEFT JOIN pedido_refeicao p ON p.cardapio_id = c.id
GROUP BY c.id;

COMMENT ON VIEW v_pedidos_por_cardapio IS
    'Quantos alunos pediram em cada cardápio. LEFT JOIN para o dia sem pedido aparecer com 0 em vez de sumir do calendário.';

COMMIT;
