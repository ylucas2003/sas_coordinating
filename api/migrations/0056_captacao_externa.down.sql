-- Reverte a 0056.
--
-- DESTRUTIVO: apaga todo o catálogo de provas, candidatos e conquistas
-- raspadas. Não há de onde restaurar além de rodar os scrapers de novo — e
-- qualquer status_captacao/observação que a coordenação já tenha preenchido à
-- mão se perde.
--
-- Ordem dos DROPs é a das dependências: conquista_externa referencia as
-- outras duas; candidato_externo não referencia nada.

BEGIN;

DROP TABLE IF EXISTS conquista_externa;
DROP TABLE IF EXISTS candidato_externo;
DROP TABLE IF EXISTS prova_externa;

COMMIT;
