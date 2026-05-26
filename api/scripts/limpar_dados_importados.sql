-- ─────────────────────────────────────────────────────────────────────────
-- USO PONTUAL · zerar todos os dados que vieram de upload de planilha.
--
-- Quando rodar:
--   1) após aplicar uma migration que mudou o schema de dados importados
--   2) quando quiser refazer a ingestão do zero
--
-- Não toca em:
--   - materia          (seed estática das 6 matérias)
--   - (schema das tabelas — só esvazia o conteúdo)
--
-- TRUNCATE ... CASCADE garante que linhas dependentes (FK) também sejam
-- removidas, mesmo as que não estão listadas explicitamente. RESTART IDENTITY
-- reinicia sequências (não temos nenhuma hoje, mas é defensivo).
-- ─────────────────────────────────────────────────────────────────────────

TRUNCATE TABLE
    alerta,
    classificacao_aluno,
    metrica_simulado,
    upload_evento,
    upload,
    nota,
    vestibular_alvo_aluno,
    nota_corte_vestibular,
    matricula_turma,
    simulado,
    ciclo,
    aluno,
    turma,
    ano_letivo,
    sede
RESTART IDENTITY CASCADE;
