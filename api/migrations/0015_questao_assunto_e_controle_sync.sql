-- Fase 2 do Canvas sync: sincronização de questões/respostas via Quiz Statistics.
-- questao.assunto é só o gancho da futura classificação por assunto (taxonomia
-- ainda não definida) — nenhum código grava nela ainda.
BEGIN;

ALTER TABLE questao ADD COLUMN assunto text;
COMMENT ON COLUMN questao.assunto IS
  'Assunto/tópico da questão. NULL até a taxonomia de assuntos ser definida — gancho sem classificador ainda.';

ALTER TABLE simulado ADD COLUMN questoes_sincronizadas_em timestamptz;
COMMENT ON COLUMN simulado.questoes_sincronizadas_em IS
  'Última sincronização bem-sucedida de questões/respostas via Quiz Statistics. NULL = pendente (gate do sync incremental).';

COMMIT;
