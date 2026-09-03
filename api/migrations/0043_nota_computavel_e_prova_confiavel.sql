-- Zero × ausência: separar "não entra na conta" de "tirou zero" (docs/32 §1).
--
-- A medição contra produção em 30/08/2026 (api/scripts/medir_zeros_b3.sql)
-- achou 2.756 notas com `pontuacao = 0` e `presente = true` — 6,17% das notas
-- presentes. E mostrou que elas não são UMA população, são duas, com causas
-- diferentes e remédios diferentes:
--
--   A) 122 células onde o aluno abriu a prova e NÃO MARCOU NENHUMA
--      alternativa. Evidência direta, por aluno, em questao_resposta_aluno.
--      É ausência escrita como nota. → `nota.computavel`
--
--   B) ~1.959 células em OITO provas de 2023 (71% de todos os zeros do
--      sistema) onde o professor lançou 0 para quem faltou. A evidência é por
--      PROVA, não por aluno: pico de 325 zeros com vale de 3 alunos entre 0 e
--      1, nenhuma delas é quiz, e a prova irmã do mesmo dia foi corrigida para
--      um terço da gente. → `simulado.nota_confiavel`
--
-- Os dois níveis vêm na MESMA migration porque são a mesma ideia — o SAS
-- concluindo algo sobre um dado que o Canvas afirma — e porque não vale duas
-- paradas do PostgREST (armadilha 1 do CLAUDE.md).
--
-- ⚠️ PRINCÍPIO: não destruir o fato do Canvas. O que o Canvas diz (`presente`,
-- `pontuacao`) fica intacto; o que o SAS conclui vira coluna própria, derivada
-- e reversível. É a mesma escolha da 0024, e pelo mesmo motivo — a regra
-- anterior, que APAGAVA `pontuacao` de quem tinha 2+ zeros no mesmo dia,
-- errava 14% dos casos verificáveis e operava às cegas em 79% deles.

BEGIN;

-- ── A · a nota que não entra na conta ──────────────────────────────────

ALTER TABLE nota
    ADD COLUMN IF NOT EXISTS computavel            boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS motivo_nao_computavel text;

COMMENT ON COLUMN nota.computavel IS
    'Esta nota entra nas estatísticas? Derivada pelo SAS (stats/computavel.py), nunca vinda do Canvas. false = há evidência de que o número não representa desempenho.';
COMMENT ON COLUMN nota.motivo_nao_computavel IS
    'Por que saiu da conta. Hoje só "todas_em_branco". A coluna é texto para a próxima regra não precisar de migration.';

-- ── A · a evidência, sem a conflação que ela tinha ─────────────────────
--
-- O Quiz Statistics tem dois baldes sintéticos: "none" (deixou em branco) e
-- "other" (marcou fora das alternativas, ex.: questão alterada depois da
-- aplicação). Os dois viravam `alternativa_id IS NULL`, então a regra "não
-- marcou nada" ficaria apoiada numa conflação. Guardar qual balde era desfaz
-- isso — e só então a regra é sobre "em branco" de fato.
ALTER TABLE questao_resposta_aluno
    ADD COLUMN IF NOT EXISTS balde_sem_alternativa text;

COMMENT ON COLUMN questao_resposta_aluno.balde_sem_alternativa IS
    'Qual balde sintético do Canvas gerou esta linha sem alternativa: "none" (em branco), "other" (fora das alternativas) ou NULL (alternativa real).';

-- ── B · a prova cujo zero é prática de lançamento ──────────────────────

ALTER TABLE simulado
    ADD COLUMN IF NOT EXISTS nota_confiavel            boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS motivo_nota_nao_confiavel text;

COMMENT ON COLUMN simulado.nota_confiavel IS
    'As notas desta prova representam desempenho? false exclui a prova das estatísticas AGREGADAS (média, desvio, histograma, alertas de calibração) e mantém as notas individuais visíveis com ressalva.';
COMMENT ON COLUMN simulado.motivo_nota_nao_confiavel IS
    'Por que a prova saiu dos agregados. Escrito à mão, com lista na mão — não há detector automático, de propósito (docs/32 §1.5, item 5).';

-- ── A view precisa saber das duas, senão dois pontos de leitura não filtram ──
--
-- `metricas.py` (média por turma/sede) e a regra DIFERENCA_ENTRE_SEDES de
-- `alertas.py` leem de v_nota_dimensoes, não de `nota`. Sem as colunas aqui,
-- eles continuariam somando o que o resto do sistema já parou de somar — e a
-- divergência apareceria como número diferente na mesma tela, sem erro.
-- ⚠️ As colunas novas entram NO FIM, e não onde ficariam bonitas: um
-- `CREATE OR REPLACE VIEW` só aceita acrescentar ao final da lista. Trocar a
-- ordem exigiria DROP + CREATE, e o DROP falha enquanto houver dependente.
CREATE OR REPLACE VIEW v_nota_dimensoes AS
SELECT
    n.aluno_id,
    n.simulado_id,
    n.pontuacao,
    n.presente,
    mt.turma_id,
    t.sede_id,
    n.computavel,
    s.nota_confiavel
FROM nota n
JOIN matricula_turma mt
    ON mt.aluno_id = n.aluno_id
   AND mt.ativo_ate IS NULL
JOIN turma t
    ON t.id = mt.turma_id
JOIN simulado s
    ON s.id = n.simulado_id;

COMMENT ON VIEW v_nota_dimensoes IS
    'Notas com turma_id e sede_id da matrícula ativa do aluno, mais os dois veredictos do SAS (nota.computavel, simulado.nota_confiavel). Recalcular métricas.';

COMMIT;
