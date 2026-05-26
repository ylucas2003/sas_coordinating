-- ─────────────────────────────────────────────────────────────────────────
-- 0001 · DOWNGRADE — derruba o schema inicial inteiro.
--
-- Drop em ordem inversa de dependências de FK. Como tudo do schema do SAS
-- partiu desta migration, descer 0001 esvazia o banco completamente.
-- ─────────────────────────────────────────────────────────────────────────

DROP INDEX IF EXISTS idx_matricula_ativa;
DROP INDEX IF EXISTS idx_alerta_pendente;
DROP INDEX IF EXISTS idx_simulado_externo;
DROP INDEX IF EXISTS idx_simulado_ciclo_data;
DROP INDEX IF EXISTS idx_nota_aluno_atualizado;
DROP INDEX IF EXISTS idx_nota_simulado_presente;

DROP TABLE IF EXISTS nota_corte_vestibular;
DROP TABLE IF EXISTS alerta;
DROP TABLE IF EXISTS metrica_simulado;
DROP TABLE IF EXISTS classificacao_aluno;
DROP TABLE IF EXISTS upload_evento;
DROP TABLE IF EXISTS upload;
DROP TABLE IF EXISTS nota;
DROP TABLE IF EXISTS simulado;
DROP TABLE IF EXISTS ciclo;
DROP TABLE IF EXISTS vestibular_alvo_aluno;
DROP TABLE IF EXISTS matricula_turma;
DROP TABLE IF EXISTS aluno;
DROP TABLE IF EXISTS materia;
DROP TABLE IF EXISTS turma;
DROP TABLE IF EXISTS ano_letivo;
DROP TABLE IF EXISTS sede;
