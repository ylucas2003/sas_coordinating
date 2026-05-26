-- ─────────────────────────────────────────────────────────────────────────
-- SAS · views auxiliares para o stats engine
-- ─────────────────────────────────────────────────────────────────────────

-- Junta nota com turma e sede da matrícula ativa do aluno. Usada pelo
-- recálculo de métricas (geral, por turma, por sede). Evita 3-join em Python.
CREATE OR REPLACE VIEW v_nota_dimensoes AS
SELECT
    n.aluno_id,
    n.simulado_id,
    n.pontuacao,
    n.presente,
    mt.turma_id,
    t.sede_id
FROM nota n
JOIN matricula_turma mt
    ON mt.aluno_id = n.aluno_id
   AND mt.ativo_ate IS NULL
JOIN turma t
    ON t.id = mt.turma_id;

COMMENT ON VIEW v_nota_dimensoes IS
    'Notas com turma_id e sede_id da matrícula ativa do aluno. Recalcular métricas.';
