-- ─────────────────────────────────────────────────────────────────────────
-- 0008 · Chat com agente (coordenador ↔ LLM com tools curadas)
--
-- Modelo:
--   chat_thread     — uma "conversa" do coordenador. Título auto-gerado.
--   chat_mensagem   — turnos da conversa (user / assistant / tool / system).
--                     tool_calls e tool_results em jsonb (formato OpenAI).
--   chat_artefato   — gráficos/CSVs gerados pelo agente, ligados a uma msg.
--
-- Sem RLS: todos os coordenadores podem ver todas as threads do sistema?
-- NÃO — cada thread tem usuario_id e o backend filtra por ele. Não há RLS
-- porque tudo passa pela service key, e a autorização é no nível da rota.
--
-- Reversível via 0008_*.down.sql.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

-- ── Threads ────────────────────────────────────────────────────────────
CREATE TABLE chat_thread (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id      text NOT NULL,
    titulo          text NOT NULL DEFAULT 'Nova conversa',
    arquivada       boolean NOT NULL DEFAULT false,
    criada_em       timestamptz NOT NULL DEFAULT now(),
    ultima_msg_em   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  chat_thread             IS 'Uma conversa do coordenador com o agente. Threads são livres (sem escopo pré-fixado) — o LLM se vira com tools.';
COMMENT ON COLUMN chat_thread.usuario_id  IS 'Identificador do coordenador. No MVP é o email/handle passado pelo front; futuramente FK pra usuario.';
COMMENT ON COLUMN chat_thread.titulo      IS 'Título auto-gerado pelo LLM após a primeira resposta. Default "Nova conversa" enquanto a thread está vazia.';

CREATE INDEX idx_chat_thread_usuario_recente
    ON chat_thread (usuario_id, ultima_msg_em DESC)
    WHERE arquivada = false;


-- ── Mensagens ──────────────────────────────────────────────────────────
CREATE TABLE chat_mensagem (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id     uuid NOT NULL REFERENCES chat_thread(id) ON DELETE CASCADE,
    ordem         int  NOT NULL,
    papel         text NOT NULL CHECK (papel IN ('user', 'assistant', 'tool', 'system')),
    conteudo      text,
    tool_calls    jsonb,
    tool_call_id  text,
    nome_tool     text,
    tokens_in     int,
    tokens_out    int,
    modelo        text,
    criada_em     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (thread_id, ordem)
);

COMMENT ON COLUMN chat_mensagem.ordem        IS 'Posição na thread (0, 1, 2, ...). Define a ordem para o histórico enviado ao LLM.';
COMMENT ON COLUMN chat_mensagem.papel        IS 'Mapeia para o role do OpenAI: user/assistant/tool/system.';
COMMENT ON COLUMN chat_mensagem.tool_calls   IS 'Lista de tool_calls solicitadas pelo assistant (formato OpenAI). NULL em mensagens de user/tool.';
COMMENT ON COLUMN chat_mensagem.tool_call_id IS 'Em mensagens "tool", referencia o id da tool_call que retornou.';
COMMENT ON COLUMN chat_mensagem.nome_tool    IS 'Em mensagens "tool", o nome da função executada (redundância pra debugging).';

CREATE INDEX idx_chat_mensagem_thread
    ON chat_mensagem (thread_id, ordem);


-- ── Artefatos (gráficos, CSVs gerados pelo agente) ─────────────────────
CREATE TABLE chat_artefato (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mensagem_id    uuid NOT NULL REFERENCES chat_mensagem(id) ON DELETE CASCADE,
    tipo           text NOT NULL CHECK (tipo IN ('histograma', 'linha_temporal', 'tabela', 'csv')),
    titulo         text,
    payload        jsonb,
    url_export     text,
    criado_em      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  chat_artefato         IS 'Artefatos visuais ou exportáveis produzidos pelo agente (gráficos inline, CSVs).';
COMMENT ON COLUMN chat_artefato.payload IS 'Para tipos visuais: payload pronto pro componente do frontend (histograma.js, linha-temporal.js).';
COMMENT ON COLUMN chat_artefato.url_export IS 'Para CSV: URL no Supabase Storage. NULL para artefatos puramente visuais.';

CREATE INDEX idx_chat_artefato_mensagem
    ON chat_artefato (mensagem_id);


COMMIT;
