-- O CHECK de simulado.canvas_estado (0018) aceita pendente | sincronizado |
-- falhou. A 0024 assumiu que não havia CHECK e só documentou o valor novo —
-- e o primeiro agendamento "só no site" caiu com 23514. Achado no teste de
-- escrita real no Canvas, 22/08/2026.
--
-- 'divergente' = o coordenador escolheu não mandar (docs/18 §2.5).

BEGIN;

ALTER TABLE simulado DROP CONSTRAINT IF EXISTS simulado_canvas_estado_check;
ALTER TABLE simulado ADD CONSTRAINT simulado_canvas_estado_check
    CHECK (canvas_estado IN ('pendente', 'sincronizado', 'falhou', 'divergente'));

COMMIT;
