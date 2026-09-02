-- Devolve `questao_estudo_aluno` ao que a 0029 desenhou.
--
-- ⚠️ Apaga as respostas de treino gravadas. É perda de dado real, e não há
-- outro lugar de onde reconstruí-lo: a alternativa escolhida só existia no
-- `useState` da tela antes da 0042. Reverter em produção depois de a feature
-- estar no ar apaga o histórico de acerto por assunto de todo mundo.

BEGIN;

ALTER TABLE questao_estudo_aluno
    DROP CONSTRAINT IF EXISTS questao_estudo_aluno_acertou_exige_resposta;

ALTER TABLE questao_estudo_aluno
    DROP COLUMN IF EXISTS acertou,
    DROP COLUMN IF EXISTS alternativa_escolhida;

COMMIT;
