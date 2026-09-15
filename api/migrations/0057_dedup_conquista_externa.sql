-- Chave de deduplicação pra conquista_externa (par da 0056).
--
-- Sem isto, rodar o mesmo scraper duas vezes (ex.: reprocessar uma edição
-- porque a fonte corrigiu um nome) duplicaria toda linha, porque
-- api/scripts/importar_captacao_externa.py faz upsert e upsert via PostgREST
-- PRECISA de uma constraint de unicidade real pra ter o que ser "on conflict".
--
-- A chave é o que identifica um registro CRU da fonte, não a pessoa (isso é
-- candidato_externo): mesma prova, mesmo ano, mesmo nível, mesmo nome/escola
-- informados, mesmo resultado. Duas pessoas homônimas na mesma escola no
-- mesmo nível/ano/resultado colidiriam aqui — extremamente raro, e o pior caso
-- é perder uma linha, não misturar duas pessoas (isso só acontece na
-- resolução de identidade, em candidato_externo).

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS conquista_externa_dedup
    ON conquista_externa (prova_id, ano, nivel_texto, nome_informado, escola_informada, resultado);

COMMENT ON INDEX conquista_externa_dedup IS
    'Permite upsert idempotente do scraper (mesma edição raspada de novo não duplica). Não é identidade de pessoa — é identidade de LINHA da fonte.';

COMMIT;
