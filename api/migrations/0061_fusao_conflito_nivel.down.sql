-- Reverte a 0061: volta v_fusao_candidata pra definição da 0059, sem
-- tem_conflito_nivel.
--
-- `CREATE OR REPLACE VIEW` não deixa apagar coluna de view já existente
-- (Postgres recusa com "cannot drop columns from view") — só permite ACRESCENTAR
-- no fim. Pra tirar `tem_conflito_nivel`, precisa dropar e recriar.
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

DROP VIEW IF EXISTS v_fusao_candidata;

CREATE VIEW v_fusao_candidata AS
SELECT
    c.nome_normalizado,
    count(*)::int AS candidatos,
    count(DISTINCT NULLIF(c.uf, '')) FILTER (WHERE c.uf IS NOT NULL)::int AS ufs_distintas
FROM candidato_externo c
WHERE NOT EXISTS (
    SELECT 1 FROM candidato_externo_fusao_decisao d
    WHERE d.nome_normalizado = c.nome_normalizado
)
GROUP BY c.nome_normalizado
HAVING count(*) > 1;

COMMENT ON VIEW v_fusao_candidata IS
    'Grupos de candidato_externo que COMPARTILHAM nome_normalizado e ainda não foram decididos — a fila da fusão de baixa confiança (docs/41 §8 item 1). ufs_distintas é o sinal de confiança rápido: 1 = todo mundo do grupo bate geograficamente, mais que 1 = pode ser gente diferente.';

COMMIT;
