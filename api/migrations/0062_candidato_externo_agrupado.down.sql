-- Reverte a 0062: derruba a função de refresh e a view materializada (os
-- índices vão junto). GET /captacao/candidatos volta a precisar ler
-- v_candidato_externo direto (mudança de código, não só de banco — não
-- desfaz sozinho).
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

DROP FUNCTION IF EXISTS atualizar_v_candidato_externo_agrupado();
DROP MATERIALIZED VIEW IF EXISTS v_candidato_externo_agrupado;

COMMIT;
