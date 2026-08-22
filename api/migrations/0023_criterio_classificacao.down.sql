-- Reverte a 0023. DESTRUTIVO: apaga também os critérios que a coordenação
-- tiver criado pela tela. Os embutidos (colégio, ITA, IME) continuam vivendo
-- em app/stats/criterios.py e voltam na reaplicação.
BEGIN;
DROP TABLE IF EXISTS predicado_criterio;
DROP TABLE IF EXISTS criterio_classificacao;
COMMIT;
