-- Reverte a 0082.
--
-- Some o registro dos envios e, com ele, a trava de "uma vez por dia": se o
-- código do evento ainda estiver no ar, a rota agendada passa a falhar (a
-- reserva não acha a tabela) em vez de mandar de novo. É o lado certo de errar.

BEGIN;

DROP TABLE IF EXISTS envio_push;

COMMIT;
