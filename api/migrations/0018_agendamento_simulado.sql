-- ─────────────────────────────────────────────────────────────────────────
-- 0018 · P1 — o simulado nasce no SAS
--
-- Inverte a fonte da verdade: o simulado passa a poder ser CRIADO no SAS
-- (fase pré-aplicação), e o SAS cria o Assignment correspondente no Canvas.
-- Ver docs/11-plano-p1-agendamento.md.
--
--   1. evento_agenda — âncora genérica do motor de lembretes (P2 pendura
--      regra_lembrete/disparo nela; aqui só nasce).
--   2. simulado ganha origem ('canvas'|'sas'), estado de sincronização com
--      o Canvas e external_id opcional (o id só existe após o POST).
--   3. ano_letivo/ciclo guardam ONDE criar no Canvas (course + assignment
--      group) — preenchidos pelo próprio sync, sem script de backfill.
-- ─────────────────────────────────────────────────────────────────────────
BEGIN;

-- ─── 1 · evento_agenda ────────────────────────────────────────────────────

CREATE TABLE evento_agenda (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo           text NOT NULL CHECK (tipo IN ('simulado')),
    titulo         text NOT NULL,
    data_evento    date NOT NULL,
    hora_evento    time NOT NULL DEFAULT '07:00',
    criado_por     text,
    cancelado_em   timestamptz,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  evento_agenda              IS 'Algo marcado numa data. Âncora do motor de lembretes (P2) — o motor não conhece o domínio; quem aponta pra cá é o domínio (simulado.evento_agenda_id).';
COMMENT ON COLUMN evento_agenda.tipo         IS 'Discriminador pra filtrar sem join. Por ora só ''simulado''.';
COMMENT ON COLUMN evento_agenda.criado_por   IS 'E-mail de quem criou. Texto (não FK) porque não existe tabela de usuário — o coordenador é credencial em config.py.';
COMMENT ON COLUMN evento_agenda.cancelado_em IS 'Timestamp (não boolean): P2 precisa saber QUANDO foi cancelado pra decidir o que fazer com disparos já materializados. É também o registro histórico de simulado desmarcado.';

CREATE INDEX idx_evento_agenda_data ON evento_agenda(data_evento);

-- ─── 2 · simulado — fase pré-aplicação ────────────────────────────────────

-- O id do Canvas só existe depois que o Assignment é criado lá. A UNIQUE
-- simples que já existe continua valendo: múltiplos NULL não conflitam.
-- (NÃO trocar por índice parcial — upsert_simulados_em_lote depende de
-- on_conflict="external_id", e o PostgREST não sabe repetir o WHERE do
-- índice parcial na cláusula ON CONFLICT.)
ALTER TABLE simulado ALTER COLUMN external_id DROP NOT NULL;

ALTER TABLE simulado ADD COLUMN evento_agenda_id uuid REFERENCES evento_agenda(id);
ALTER TABLE simulado ADD COLUMN origem text NOT NULL DEFAULT 'canvas'
    CHECK (origem IN ('canvas', 'sas'));
ALTER TABLE simulado ADD COLUMN canvas_estado text NOT NULL DEFAULT 'sincronizado'
    CHECK (canvas_estado IN ('sincronizado', 'pendente', 'falhou'));
ALTER TABLE simulado ADD COLUMN canvas_erro text;
ALTER TABLE simulado ADD COLUMN canvas_tentativas int NOT NULL DEFAULT 0;

COMMENT ON COLUMN simulado.external_id       IS 'ID do Assignment no Canvas. NULL só em simulado origem=''sas'' ainda não criado lá (canvas_estado pendente/falhou).';
COMMENT ON COLUMN simulado.evento_agenda_id  IS 'Evento de agenda do agendamento. NULL nos simulados que nasceram do sync (origem=''canvas'').';
COMMENT ON COLUMN simulado.origem            IS '''sas'' = criado pelo agendamento; campos de identidade (nome, rótulo, data, escala, tipo) são do SAS e o sync NÃO os sobrescreve. ''canvas'' = espelho do Canvas, comportamento original.';
COMMENT ON COLUMN simulado.canvas_estado     IS 'Sincronização SAS→Canvas. pendente = ainda não tentou/aguardando retry; falhou = última tentativa falhou (ver canvas_erro); sincronizado = Assignment existe e reflete o SAS.';
COMMENT ON COLUMN simulado.canvas_tentativas IS 'Tentativas de criação/atualização no Canvas. O reprocessamento do sync desiste a partir de 5 — resgate manual via botão na UI.';

-- Guarda contra duplo clique no agendamento. Não cobre materia_id NULL
-- (NULL <> NULL) — a checagem explícita na rota é a guarda de verdade;
-- este índice é a rede pro caso com matéria.
CREATE UNIQUE INDEX idx_simulado_sas_unico
    ON simulado (ciclo_id, rotulo_curto, materia_id) WHERE origem = 'sas';

-- ─── 3 · onde criar no Canvas ─────────────────────────────────────────────

-- No course em ano_letivo (não em ciclo): é um curso "{ano} 3o ITA/IME
-- Simulados" por ano (verificado na conta em 17/08/2026), e assim um ciclo
-- NOVO já sabe em que curso nascer antes de existir no Canvas.
ALTER TABLE ano_letivo ADD COLUMN canvas_course_id text;
ALTER TABLE ciclo      ADD COLUMN canvas_assignment_group_id text;

COMMENT ON COLUMN ano_letivo.canvas_course_id         IS 'ID do curso "{ano} 3o ITA/IME Simulados" no Canvas. Preenchido pelo sync; é onde o agendamento cria Assignments.';
COMMENT ON COLUMN ciclo.canvas_assignment_group_id    IS 'ID do Assignment Group ("N° CICLO - VEST") no Canvas. Preenchido pelo sync ou pela criação de ciclo no SAS. Sem ele o Assignment criado cairia no grupo default e o sync não o reconheceria.';

COMMIT;
