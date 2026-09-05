-- Reverte a 0046.
--
-- As notas marcadas `computavel = false` por causa desta regra NÃO voltam
-- sozinhas: quem as marcou foi `stats/computavel.py`, e sem a coluna ele deixa
-- de enxergar o motivo. Rode `scripts/backfill_computavel.py --aplicar` depois
-- do down para que os vereditos sejam recalculados sem esta evidência — o
-- avaliador é idempotente e reversível nos dois sentidos, então as notas
-- voltam a computáveis por conta própria.

BEGIN;

ALTER TABLE simulado
    DROP COLUMN IF EXISTS zero_e_ausencia,
    DROP COLUMN IF EXISTS motivo_zero_e_ausencia;

COMMIT;
