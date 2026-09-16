-- Reverte a 0059: derruba a tabela de decisões de fusão.
--
-- Não desfaz fusão nenhuma já confirmada (os candidato_externo já
-- combinados continuam combinados — reverter isso exigiria saber quem
-- eram os candidatos originais, que a 0059 nunca guardou de propósito).
-- Só apaga a TRILHA de decisão; sem ela, nomes já revisados voltam a
-- aparecer na fila da próxima vez que alguém abrir a tela.
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

DROP VIEW IF EXISTS v_fusao_candidata;
DROP TABLE IF EXISTS candidato_externo_fusao_decisao;

COMMIT;
