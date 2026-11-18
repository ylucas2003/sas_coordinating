-- Reverte a 0081.
--
-- Apaga todas as inscrições: cada aparelho que tinha ativado os avisos para de
-- receber, e só volta se a pessoa ativar de novo depois de um novo `up`. O
-- navegador continua com a inscrição dele, mas ninguém mais a usa.

BEGIN;

DROP TABLE IF EXISTS inscricao_push;

COMMIT;
