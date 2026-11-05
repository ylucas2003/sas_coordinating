-- Reverte a 0080.
--
-- ⚠️ Falha de propósito se algum simulado já usa uma delas: apagar a matéria em
-- silêncio levaria a prova junto. Tire esses simulados à mão antes de reverter.

BEGIN;

DELETE FROM materia WHERE codigo IN ('biologia', 'historia', 'geografia');

COMMIT;
