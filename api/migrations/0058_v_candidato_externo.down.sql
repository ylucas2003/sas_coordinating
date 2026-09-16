-- Reverte a 0058: derruba a view de resumo da captação externa.
--
-- Sem `DROP VIEW` de `candidato_externo`/`conquista_externa` nem de suas
-- linhas: a view é só leitura derivada, apagá-la não perde nenhum dado
-- raspado nem resolvido (isso é a 0056/0057, revertidas à parte).
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

DROP VIEW IF EXISTS v_candidato_externo;

COMMIT;
