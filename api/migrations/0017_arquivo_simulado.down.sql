BEGIN;

ALTER TABLE simulado DROP COLUMN arquivo_storage_path;
ALTER TABLE simulado DROP COLUMN arquivo_canvas_file_id;
ALTER TABLE simulado DROP COLUMN arquivo_sincronizado_em;

COMMIT;
