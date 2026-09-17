-- Nota por matéria da conquista externa (docs/41), quando a fonte publica —
-- só IME e EFOMM têm essa granularidade (Mat/Fis/Qui/Port/Ing...); olimpíada
-- (OBMEP/OBM/OBF) e Escola Naval só têm medalha/situação, sem nota aberta
-- por matéria, então a coluna fica NULL pra elas de propósito.

BEGIN;

ALTER TABLE conquista_externa
    ADD COLUMN IF NOT EXISTS notas_por_materia jsonb;

COMMENT ON COLUMN conquista_externa.notas_por_materia IS
    'Nota por matéria, quando a fonte publica (ex. {"mat": 8.3, "fis": 8.2, "qui": 9.6, "port": 7.6, "ing": 6.0}) — chave livre por prova, cada fonte usa o próprio vocabulário de matéria. NULL quando a fonte só publica medalha/situação agregada, sem abrir por matéria (toda olimpíada, Escola Naval, e a lista de habilitados pra 2ª fase do IME).';

COMMIT;
