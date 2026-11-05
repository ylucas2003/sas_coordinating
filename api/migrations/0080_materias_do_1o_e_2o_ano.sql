-- 0080 · Biologia, História e Geografia (docs/44 §1)
--
-- As AP6 e AG6 do 1º e do 2º ano são dessas três matérias, e a coordenação
-- decidiu que entram junto com as outras AP e AG em 05/11/2026. Sem a linha em
-- `materia`, o sync gravaria a prova sem matéria e ela sumiria das colunas.
--
-- O 3º não tem prova delas. Elas passam a aparecer no formulário de agendamento,
-- que lista `GET /materias` inteiro.

BEGIN;

INSERT INTO materia (codigo, nome) VALUES
    ('biologia', 'Biologia'),
    ('historia', 'História'),
    ('geografia', 'Geografia')
ON CONFLICT (codigo) DO NOTHING;

COMMIT;
