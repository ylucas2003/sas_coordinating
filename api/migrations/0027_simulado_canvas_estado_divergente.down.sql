-- Reverte a 0027. Linhas em 'divergente' impediriam o CHECK antigo: viram
-- 'falhou' (o retry passa a tentá-las — é o comportamento de antes da 0024).
BEGIN;
UPDATE simulado SET canvas_estado = 'falhou' WHERE canvas_estado = 'divergente';
ALTER TABLE simulado DROP CONSTRAINT IF EXISTS simulado_canvas_estado_check;
ALTER TABLE simulado ADD CONSTRAINT simulado_canvas_estado_check
    CHECK (canvas_estado IN ('pendente', 'sincronizado', 'falhou'));
COMMIT;
