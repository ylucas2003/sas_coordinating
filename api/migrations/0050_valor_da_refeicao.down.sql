-- Reverte a 0050.
--
-- Apaga os preços informados pela coordenação. Não há de onde restaurar — eles
-- não vêm de nenhuma outra fonte, e a soma de custo das telas volta a não
-- existir. As contas e os cardápios não são afetados.

BEGIN;

ALTER TABLE cantina
    DROP COLUMN IF EXISTS valor_almoco,
    DROP COLUMN IF EXISTS valor_janta;

COMMIT;
