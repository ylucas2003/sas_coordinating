-- Reverte a 0054.
--
-- ⚠️ O carimbo é IRRECUPERÁVEL: descer aqui apaga o preço histórico de cada
-- pedido, e o backfill da subida só sabe reconstruir o valor de HOJE. Se o
-- preço tiver mudado entre a subida e a descida, subir de novo produz números
-- diferentes dos que os relatórios já mostraram.
--
-- A API volta para a versão anterior à 0054 ANTES deste down.

BEGIN;

ALTER TABLE pedido_refeicao DROP COLUMN IF EXISTS valor_cobrado;

COMMIT;
