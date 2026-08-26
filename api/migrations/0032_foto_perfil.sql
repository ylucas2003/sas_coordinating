-- Foto de perfil de aluno e de coordenação (docs/sprints.html · SPRINT FOTO).
--
-- Não é `aluno.avatar_url`. Aquele campo é do Canvas (migration 0010), o sync
-- o sobrescreve a cada rodada, e 818 dos 877 alunos têm ali só o boneco
-- padrão do Canvas (avatar-50.png) — não uma foto. O que nasce aqui é dado do
-- SAS: enviado pela própria pessoa, e o sync do Canvas nunca escreve nestas
-- colunas (a mesma regra da Sprint 1 · P1 para `evento_agenda`).
--
-- `_storage` guarda a KEY do Storage (local ou bucket), não os bytes — o
-- mesmo desenho de `upload.caminho_storage` e `simulado.arquivo_storage`
-- (app/storage.py). `_atualizada_em` existe para o coordenador ver há quanto
-- tempo a foto está no ar, e não é usada para nada além de exibição.

BEGIN;

ALTER TABLE aluno ADD COLUMN foto_perfil_storage text;
ALTER TABLE aluno ADD COLUMN foto_perfil_atualizada_em timestamptz;

ALTER TABLE usuario_coordenacao ADD COLUMN foto_perfil_storage text;
ALTER TABLE usuario_coordenacao ADD COLUMN foto_perfil_atualizada_em timestamptz;

COMMENT ON COLUMN aluno.foto_perfil_storage IS
  'Key no Storage (app/storage.py). NULL = sem foto. Não confundir com avatar_url (Canvas, sobrescrito a cada sync).';
COMMENT ON COLUMN aluno.foto_perfil_atualizada_em IS
  'Quando a foto foi definida/trocada pela última vez. Só para exibição.';
COMMENT ON COLUMN usuario_coordenacao.foto_perfil_storage IS
  'Key no Storage (app/storage.py). NULL = sem foto.';
COMMENT ON COLUMN usuario_coordenacao.foto_perfil_atualizada_em IS
  'Quando a foto foi definida/trocada pela última vez. Só para exibição.';

COMMIT;
