-- Desfaz a 0043. As colunas são derivadas: o que se perde é a conclusão do
-- SAS, não o fato do Canvas — `presente` e `pontuacao` nunca foram tocados,
-- e o avaliador recalcula tudo numa passada.

BEGIN;

-- A view volta ao formato da 0002 ANTES de as colunas sumirem: um DROP COLUMN
-- de coluna que a view referencia falha, e falharia no meio do down.
--
-- DROP + CREATE, e não CREATE OR REPLACE: replace não sabe REMOVER coluna.
DROP VIEW IF EXISTS v_nota_dimensoes;

CREATE VIEW v_nota_dimensoes AS
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

ALTER TABLE simulado
    DROP COLUMN IF EXISTS motivo_nota_nao_confiavel,
    DROP COLUMN IF EXISTS nota_confiavel;

ALTER TABLE questao_resposta_aluno
    DROP COLUMN IF EXISTS balde_sem_alternativa;

ALTER TABLE nota
    DROP COLUMN IF EXISTS motivo_nao_computavel,
    DROP COLUMN IF EXISTS computavel;

COMMIT;
