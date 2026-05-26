-- ─────────────────────────────────────────────────────────────────────────
-- 0005 · limpar dados que violam as novas regras de ingestão
--
-- Regras confirmadas pelo usuário em 2026-05-25 e implementadas em
-- api/app/ingest/{header,pipeline}.py:
--
--   (a) Colunas "1 FASE ITA - ..." (formato órfão) viraram colunas ignoradas
--       → simulados existentes com `nome` começando por "1 FASE ITA -"
--         devem ser apagados (junto de suas notas/metricas).
--
--   (b) Simulados com nota_maxima = 0 (provas de treino) agora são descartados.
--
--   (c) Simulados sem nenhum aluno presente (n=0) não devem ser persistidos.
--
--   (d) Alunos cujas TODAS as notas são nulas/zero/ausentes não devem existir
--       no banco — limpamos junto.
--
-- Esta é uma migration de DADOS, não de schema. O `.down.sql` correspondente
-- é um no-op declarado: não dá pra "ressuscitar" simulados/alunos apagados.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

-- ── (1) Identifica simulados violadores ──
CREATE TEMP TABLE _simulados_violadores AS
SELECT s.id
FROM simulado s
WHERE
    -- (a) órfãs "1 FASE ITA - ..."
    s.nome ~* '^1[º°]?\s*FASE\s+ITA\b'
    OR
    -- (b) Points Possible = 0
    s.nota_maxima = 0
    OR
    -- (c) sem ninguém presente
    NOT EXISTS (
        SELECT 1 FROM nota n
        WHERE n.simulado_id = s.id AND n.presente = true
    );

-- ── (2) Apaga cache de métricas (FK sem CASCADE) ──
DELETE FROM metrica_simulado
    WHERE simulado_id IN (SELECT id FROM _simulados_violadores);

-- ── (3) Apaga notas dos simulados violadores ──
DELETE FROM nota
    WHERE simulado_id IN (SELECT id FROM _simulados_violadores);

-- ── (4) Apaga os simulados ──
DELETE FROM simulado
    WHERE id IN (SELECT id FROM _simulados_violadores);

DROP TABLE _simulados_violadores;


-- ── (5) Identifica alunos sem nenhuma nota presente ──
CREATE TEMP TABLE _alunos_sem_nota AS
SELECT a.id
FROM aluno a
WHERE NOT EXISTS (
    SELECT 1 FROM nota n
    WHERE n.aluno_id = a.id AND n.presente = true
);

-- ── (6) Apaga dependências do aluno ──
DELETE FROM classificacao_aluno
    WHERE aluno_id IN (SELECT id FROM _alunos_sem_nota);

DELETE FROM vestibular_alvo_aluno
    WHERE aluno_id IN (SELECT id FROM _alunos_sem_nota);

DELETE FROM matricula_turma
    WHERE aluno_id IN (SELECT id FROM _alunos_sem_nota);

DELETE FROM nota
    WHERE aluno_id IN (SELECT id FROM _alunos_sem_nota);

-- ── (7) Apaga os alunos ──
DELETE FROM aluno
    WHERE id IN (SELECT id FROM _alunos_sem_nota);

DROP TABLE _alunos_sem_nota;

COMMIT;
