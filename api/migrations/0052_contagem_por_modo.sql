-- O calendário passa a dizer de que porta veio cada pessoa (docs/40 §1, §10.1).
--
-- A 0051 abriu o segundo jeito de comer sem abrir tabela nova: a retirada
-- presencial é uma linha de `pedido_refeicao` com `modo = 'presencial'` e
-- NENHUM item em `pedido_refeicao_item`. Só que `v_pedidos_por_cardapio` conta
-- linhas de `pedido_refeicao` — então o número do calendário passou a incluir
-- presenciais, enquanto a contagem por opção (`v_contagem_pedidos_por_opcao`,
-- que nasce dos itens) não inclui e nunca vai incluir.
--
-- Os dois números continuam CERTOS, cada um respondendo a sua pergunta. O
-- problema é que parecem responder à mesma: "47 no dia" e "39 pratos" viram
-- chamado de bug toda vez que alguém soma o segundo e não chega no primeiro.
-- O conserto não é mudar contagem nenhuma — é dar à tela a quebra que falta,
-- para o 47 poder se explicar sozinho.
--
-- ⚠️ `quantos` NÃO muda de significado: continua sendo "quantos vão comer", as
-- duas portas somadas. `com_pedido` e `presenciais` são acréscimo. Renomear ou
-- reapontar `quantos` seria trocar o sentido de um campo que várias telas já
-- leem, o que é pior que o problema que esta migration resolve.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md,
-- armadilha 1). Sem o restart as colunas novas voltam 404, e o 404 parece bug
-- de código.

BEGIN;

-- `CREATE OR REPLACE VIEW` só aceita coluna NOVA e só NO FIM — não renomeia,
-- não reordena, não remove. Por isso `com_pedido` e `presenciais` entram
-- depois de `quantos`, e por isso o `.down.sql` precisa de DROP + CREATE.
--
-- `count(...) FILTER` e não `sum(CASE ...)`: o LEFT JOIN garante uma linha por
-- cardápio mesmo sem pedido algum, com `p.*` nulo, e `count` ignora nulo —
-- devolve 0 onde o `sum` devolveria NULL, e NULL no calendário viraria dia sem
-- número. O LEFT JOIN segue obrigatório pelo motivo da 0049: dia sem pedido
-- tem de aparecer com 0 em vez de sumir do mês.
CREATE OR REPLACE VIEW v_pedidos_por_cardapio AS
SELECT
    c.id                                                    AS cardapio_id,
    count(p.id)::int                                        AS quantos,
    (count(p.id) FILTER (WHERE p.modo = 'pedido'))::int     AS com_pedido,
    (count(p.id) FILTER (WHERE p.modo = 'presencial'))::int AS presenciais
FROM cardapio c
LEFT JOIN pedido_refeicao p ON p.cardapio_id = c.id
GROUP BY c.id;

COMMENT ON VIEW v_pedidos_por_cardapio IS
    'Quantos vão comer em cada cardápio, e por qual das duas portas. quantos = o total (é o número do calendário); com_pedido = escolheu prato com antecedência; presenciais = declarou presença pelo QR, pendentes e já retiradas juntas (docs/40 §10.1). quantos = com_pedido + presenciais sempre, porque modo é NOT NULL com CHECK de dois valores (0051). LEFT JOIN para o dia sem pedido aparecer com 0 em vez de sumir do calendário.';

COMMIT;
