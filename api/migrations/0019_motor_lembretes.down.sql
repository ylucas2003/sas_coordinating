-- 0019 · down — desfaz o motor de lembretes (P2)
BEGIN;

DROP TABLE disparo;
DROP TABLE regra_lembrete;

COMMIT;
