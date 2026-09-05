-- Reverte a 0049.
--
-- DESTRUTIVO em dois níveis, e o segundo é o que costuma surpreender:
--
--   * apaga os pedidos já feitos — o histórico do que cada aluno comeu;
--   * apaga QUEM TEM DIREITO. Refazer é trabalho de administrador, aluno a
--     aluno, e a lista não existe em outro lugar. `evento_auditoria` guarda as
--     concessões, então dá para reconstruir lendo a trilha — mas é
--     arqueologia, não restauração.
--
-- `aluno.restricao_alimentar` também some, e com ela a informação de saúde que
-- a coordenação digitou. É o único dado deste conjunto que ninguém consegue
-- reconstruir a partir de outra fonte.
--
-- A ordem é a das dependências: a view primeiro, depois os itens, depois os
-- pedidos.

BEGIN;

DROP VIEW  IF EXISTS v_pedidos_por_cardapio;
DROP VIEW  IF EXISTS v_contagem_pedidos_por_opcao;
DROP TABLE IF EXISTS pedido_refeicao_item;
DROP TABLE IF EXISTS pedido_refeicao;
ALTER TABLE aluno DROP COLUMN IF EXISTS restricao_alimentar;
DROP TABLE IF EXISTS direito_refeicao_aluno;

COMMIT;
