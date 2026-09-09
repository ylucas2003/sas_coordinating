-- Reverte a 0053. A coluna é puramente informativa e ninguém depende dela para
-- decidir nada, então descer não muda comportamento — só apaga o texto que a
-- cantina tiver escrito, que é irrecuperável.
--
-- ⚠️ A API volta para a versão anterior à 0053 ANTES deste down: o editor manda
-- `observacao` no corpo do PUT, e coluna ausente no PostgREST é 400, não campo
-- ignorado. É a mesma advertência dos downs da 0051 e da 0052.

BEGIN;

ALTER TABLE cardapio_bloco DROP COLUMN IF EXISTS observacao;

COMMIT;
