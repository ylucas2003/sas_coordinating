-- Reverte a 0032. Destrutivo: os bytes já removidos do Storage por
-- `storage.remover_foto_perfil` não voltam — só a referência às colunas some.
BEGIN;
ALTER TABLE aluno DROP COLUMN IF EXISTS foto_perfil_storage;
ALTER TABLE aluno DROP COLUMN IF EXISTS foto_perfil_atualizada_em;
ALTER TABLE usuario_coordenacao DROP COLUMN IF EXISTS foto_perfil_storage;
ALTER TABLE usuario_coordenacao DROP COLUMN IF EXISTS foto_perfil_atualizada_em;
COMMIT;
