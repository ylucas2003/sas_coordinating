-- Guarda, por aluno, as duas séries que a coordenação lia varrendo TODAS as
-- ~78 mil notas a cada clique (medido em 29/09/2026 no banco local):
--
--   sparkline         as últimas notas do aluno em 0–10 (o mini-gráfico)
--   vetor_similares   o vetor de features do kNN de `/alunos/{id}/similares`
--
-- `GET /alunos/{id}` gastava 1,04 s para devolver 1 KB, dos quais 1,01 s eram a
-- sparkline de TODOS os alunos (78 páginas de 1.000 linhas, em sequência) só
-- para descartar tudo menos uma. Ambas as séries só mudam quando entra nota —
-- exatamente quando `classificacao_aluno` já é recalculada —, então passam a
-- ser gravadas no mesmo momento e lidas como leitura de tabela.
--
-- ⚠️ TABELA PRÓPRIA, e não colunas em `classificacao_aluno`: aquela tabela só
-- tem linha de quem tem >= 2 notas na janela (`_classificar_e_salvar` pula os
-- demais) e `perfil`/`tendencia`/`zona` são NOT NULL. O aluno com uma nota só
-- tinha sparkline de um ponto e vetor; em colunas ele perderia os dois.
--
-- Depois de aplicar, rodar o backfill (a tabela nasce vazia):
--     python -m app.stats.serie_recente

BEGIN;

CREATE TABLE aluno_serie_recente (
    aluno_id         uuid PRIMARY KEY REFERENCES aluno(id) ON DELETE CASCADE,
    sparkline        jsonb NOT NULL DEFAULT '[]'::jsonb,
    vetor_similares  jsonb,
    calculado_em     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  aluno_serie_recente                 IS 'Cache de leitura: séries derivadas das notas, regravadas junto com classificacao_aluno.';
COMMENT ON COLUMN aluno_serie_recente.sparkline       IS 'Últimas notas do aluno em escala 0–10, da mais antiga à mais recente (janela = JANELA_CLASSIFICACAO).';
COMMENT ON COLUMN aluno_serie_recente.vetor_similares IS '[média por matéria em ordem alfabética do nome..., desvio geral, coef_tendencia]; null onde não há dado.';

COMMIT;
