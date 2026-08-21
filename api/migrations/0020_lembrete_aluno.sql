-- ─────────────────────────────────────────────────────────────────────────
-- 0020 · P3 — lembrete de aluno
--
-- Nenhuma tabela nova para o motor: o desenho de 0019 (regra + disparo) já
-- servia. O que entra aqui é o alargamento previsto e o que o VOLUME exige.
-- Ver docs/13-plano-p3-lembrete-aluno.md §3.
--
--   1. destinatario_tipo ganha 'aluno' (alargamento anunciado em 0019).
--   2. disparo ganha contexto (opaco pro motor, significativo pra aplicação)
--      e chave_idempotencia — sem ela a varredura da véspera, que roda a
--      cada tick, duplicaria os 873 disparos do dia.
--   3. email_invalido — endereço que não recebe mais nada. Pré-requisito de
--      qualquer envio em volume: bounce acumulado suspende a conta do SES.
-- ─────────────────────────────────────────────────────────────────────────
BEGIN;

-- ─── 1 · destinatário aluno ───────────────────────────────────────────────

-- Dropa pelo CATÁLOGO, não pelo nome literal: o CHECK de 0019 foi declarado
-- inline na coluna, e o nome automático do Postgres é convenção, não
-- contrato. Migration que falha por causa disso falha no pior momento.
DO $$
DECLARE nome text;
BEGIN
    SELECT conname INTO nome
      FROM pg_constraint
     WHERE conrelid = 'regra_lembrete'::regclass
       AND contype  = 'c'
       AND pg_get_constraintdef(oid) ILIKE '%destinatario_tipo%';
    IF nome IS NOT NULL THEN
        EXECUTE format('ALTER TABLE regra_lembrete DROP CONSTRAINT %I', nome);
    END IF;
END $$;

ALTER TABLE regra_lembrete ADD CONSTRAINT regra_lembrete_destinatario_tipo_check
    CHECK (destinatario_tipo IN ('coordenador', 'aluno'));

COMMENT ON COLUMN regra_lembrete.destinatario_tipo IS 'Quem recebe — e QUAL aplicação decide o texto e a guarda do envio (app/lembretes/aplicacoes/). ''coordenador'': materializado no agendamento, 1 disparo. ''aluno'': materializado na véspera pela varredura, 1 disparo por aluno da audiência. P4 alarga pra ''professor''.';

-- ─── 2 · contexto e idempotência do disparo ───────────────────────────────

ALTER TABLE disparo ADD COLUMN contexto jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE disparo ADD COLUMN chave_idempotencia text;

COMMENT ON COLUMN disparo.contexto IS 'Dado opaco para o motor e significativo para a aplicação do destinatario_tipo. Lembrete de aluno guarda {dia, aluno_id}; P4 guardará o requerimento. O despachante nunca lê este campo — só repassa.';
COMMENT ON COLUMN disparo.chave_idempotencia IS 'Identidade natural do disparo, definida pela aplicação (ex.: ''aluno-dia:2026-08-21:<aluno_id>''). NULL nos disparos de coordenador, que nascem um a um no agendamento.';

-- O índice ignora 'cancelado' DE PROPÓSITO: disparo cancelado libera a chave,
-- e é isso que permite a varredura recriar o que um remarque desfez (e o
-- sistema se curar sozinho de um cancelamento indevido no meio do tick).
CREATE UNIQUE INDEX idx_disparo_chave ON disparo(chave_idempotencia)
    WHERE chave_idempotencia IS NOT NULL AND estado <> 'cancelado';

-- Contagem do teto diário de envio (guarda contra o corte de 200/24h do
-- sandbox do SES) — roda uma vez por tick.
CREATE INDEX idx_disparo_enviado_em ON disparo(enviado_em) WHERE estado = 'enviado';

-- ─── 3 · endereços queimados ──────────────────────────────────────────────

CREATE TABLE email_invalido (
    endereco   text PRIMARY KEY,
    motivo     text NOT NULL CHECK (motivo IN ('bounce', 'complaint', 'descadastro')),
    detalhe    text,
    criado_em  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  email_invalido         IS 'Endereços que não recebem mais nada: bounce permanente e complaint vindos do SNS do SES, e descadastro pedido pelo próprio destinatário. Deliberadamente NÃO é coluna em aluno — professor (P4) cai na mesma lista.';
COMMENT ON COLUMN email_invalido.motivo  IS '''bounce'' = endereço não existe (permanente; transiente não entra aqui, quem re-tenta é o disparo). ''complaint'' = marcou como spam. ''descadastro'' = clicou no link do rodapé.';
COMMENT ON COLUMN email_invalido.detalhe IS 'Subtipo do SES (ex.: ''General'', ''NoEmail'') ou origem do descadastro. Diagnóstico, não regra.';

COMMIT;
