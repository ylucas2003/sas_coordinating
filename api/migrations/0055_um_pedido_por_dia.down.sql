-- Reverte a 0055: volta a trava de um pedido por CARDÁPIO, e com ela a
-- possibilidade de o mesmo aluno pedir nas duas cantinas no mesmo dia.
--
-- ⚠️ A API volta para a versão anterior à 0055 ANTES deste down. O servidor
-- passou a escrever `data` e `refeicao` no INSERT, e coluna ausente no
-- PostgREST é 400 — o aluno perderia a capacidade de pedir, não um campo.

BEGIN;

DROP INDEX IF EXISTS pedido_refeicao_um_por_dia;

ALTER TABLE pedido_refeicao
    DROP COLUMN IF EXISTS data,
    DROP COLUMN IF EXISTS refeicao;

COMMIT;
