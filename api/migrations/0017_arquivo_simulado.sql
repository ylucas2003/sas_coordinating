-- Fase 3 do Canvas sync: arquivo (PDF) original da prova, guardado no
-- Supabase Storage. O arquivo não é anexo de Assignment/Quiz — é um Course
-- File do curso "Simulados", casado por parsing de nome (ciclo + Pn +
-- matéria) contra o simulado já existente no banco.
BEGIN;

ALTER TABLE simulado ADD COLUMN arquivo_storage_path text;
COMMENT ON COLUMN simulado.arquivo_storage_path IS
  'Path do PDF da prova no bucket do Supabase Storage. NULL = ainda não sincronizado.';

ALTER TABLE simulado ADD COLUMN arquivo_canvas_file_id text;
COMMENT ON COLUMN simulado.arquivo_canvas_file_id IS
  'Id do Canvas File de origem do PDF — rastreabilidade/debug do casamento por nome.';

ALTER TABLE simulado ADD COLUMN arquivo_sincronizado_em timestamptz;
COMMENT ON COLUMN simulado.arquivo_sincronizado_em IS
  'Última sincronização bem-sucedida do arquivo da prova. NULL = pendente (gate do sync incremental).';

COMMIT;
