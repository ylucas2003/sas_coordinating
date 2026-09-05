-- Reverte a 0048.
--
-- DESTRUTIVO: apaga todo cardápio já lançado. Não há de onde restaurar — a
-- planilha da cantina é a origem do conteúdo, não um backup do schema.
--
-- ⚠️ A 0049 depende desta: `pedido_refeicao` referencia `cardapio` e
-- `pedido_refeicao_item` referencia `cardapio_opcao`. Desça a 0049 ANTES, ou
-- o DROP falha por dependência — e falhar aqui é o comportamento certo, não
-- um obstáculo a contornar com CASCADE.
--
-- A ordem dos DROPs é a das dependências, de baixo para cima.

BEGIN;

DROP TABLE IF EXISTS cardapio_opcao;
DROP TABLE IF EXISTS cardapio_bloco;
DROP TABLE IF EXISTS cardapio;

COMMIT;
