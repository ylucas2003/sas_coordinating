-- ─────────────────────────────────────────────────────────────────────────
-- 0019 · P2 — motor de lembretes (regra + disparo)
--
-- O motor genérico de disparos do bloco A (docs/12-plano-p2-motor-lembretes.md).
-- Pendura em evento_agenda (0018) e não conhece o domínio: o despachante lê
-- disparo → regra_lembrete → evento_agenda e para aí.
--
--   regra_lembrete — a intenção ("me lembre X dias antes"). Em P2 é um tiro
--                    só; P4 estende a MATERIALIZAÇÃO (1 regra → N disparos),
--                    não o despachante.
--   disparo        — a mensagem concreta, com estado. É o histórico exigido
--                    pelo motor: pra quem foi, quando, com que resultado.
-- ─────────────────────────────────────────────────────────────────────────
BEGIN;

-- ─── 1 · regra_lembrete ───────────────────────────────────────────────────

-- Os CHECKs de um valor só são deliberados — mesmo padrão de
-- evento_agenda.tipo IN ('simulado'): documentam a intenção e P3/P4/P5
-- alargam ('aluno', 'professor'; 'whatsapp') sem reestruturar.
CREATE TABLE regra_lembrete (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evento_agenda_id   uuid NOT NULL REFERENCES evento_agenda(id),
    destinatario_tipo  text NOT NULL CHECK (destinatario_tipo IN ('coordenador')),
    canal              text NOT NULL CHECK (canal IN ('email')),
    dias_antes         int  NOT NULL CHECK (dias_antes >= 0),
    criado_em          timestamptz NOT NULL DEFAULT now(),
    cancelada_em       timestamptz
);

COMMENT ON TABLE  regra_lembrete              IS 'Intenção de lembrete pendurada num evento_agenda ("me lembre X dias antes"). Quem cria é a aplicação (rota de agendamento); o motor só materializa e despacha.';
COMMENT ON COLUMN regra_lembrete.dias_antes   IS '0 = no dia, na hora do evento. O horário do envio é a hora_evento do evento, X dias antes.';
COMMENT ON COLUMN regra_lembrete.cancelada_em IS 'Preenchido quando o evento é cancelado. Regra cancelada não regera disparos e a guarda do despachante não envia nada dela.';

CREATE INDEX idx_regra_lembrete_evento ON regra_lembrete(evento_agenda_id);

-- ─── 2 · disparo ──────────────────────────────────────────────────────────

CREATE TABLE disparo (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    regra_lembrete_id  uuid NOT NULL REFERENCES regra_lembrete(id),
    destinatario       text NOT NULL,
    canal              text NOT NULL CHECK (canal IN ('email')),
    enviar_em          timestamptz NOT NULL,
    estado             text NOT NULL DEFAULT 'agendado'
        CHECK (estado IN ('agendado', 'enviando', 'enviado', 'falhou', 'cancelado')),
    tentativas         int NOT NULL DEFAULT 0,
    erro               text,
    assunto            text,
    corpo              text,
    enviado_em         timestamptz,
    criado_em          timestamptz NOT NULL DEFAULT now(),
    atualizado_em      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  disparo               IS 'Uma mensagem concreta do motor de lembretes. Materializado na criação da regra (decisão A7) e decidido de novo no instante do envio — a guarda do despachante reverifica o estado do mundo antes de sair qualquer coisa.';
COMMENT ON COLUMN disparo.destinatario  IS 'E-mail concreto, resolvido na materialização. Fica gravado mesmo que a config mude depois — é histórico.';
COMMENT ON COLUMN disparo.estado        IS 'agendado → enviando (claim) → enviado | falhou (retry no tick seguinte, teto de tentativas) | cancelado. enviado e cancelado são terminais.';
COMMENT ON COLUMN disparo.tentativas    IS 'O despachante desiste a partir de 5 — o disparo fica em falhou e sai da fila.';
COMMENT ON COLUMN disparo.assunto       IS 'Preenchido no ENVIO com o que saiu de fato (conteúdo é composto na hora, do dado fresco do evento). NULL = nunca saiu.';
COMMENT ON COLUMN disparo.atualizado_em IS 'Mantido pela aplicação a cada transição. É o que permite resgatar claim órfão (enviando parado há >30 min = processo morreu no meio).';

CREATE INDEX idx_disparo_fila ON disparo(enviar_em)
    WHERE estado IN ('agendado', 'falhou');

COMMIT;
