-- Trilha de auditoria (docs/15 §Etapa 8, item 8.3).
--
-- Não existia NADA: nem log de login, nem registro de quem editou nota, nem
-- de quem resetou o acesso de um aluno. Não havia como responder "quem entrou
-- de madrugada?" nem "quem mudou essa nota?" (docs/14 §5).
--
-- Vai para TABELA e não só para stdout de propósito: a retenção não pode
-- depender da política de um coletor de log que ainda não existe, e o art. 37
-- da LGPD pede registro das operações de tratamento — sobre dados de menores.

BEGIN;

CREATE TABLE IF NOT EXISTS evento_auditoria (
    id          bigserial PRIMARY KEY,
    ocorrido_em timestamptz NOT NULL DEFAULT now(),
    acao        text NOT NULL,
    ator_tipo   text,
    ator_id     text,
    recurso     text,
    ip          text,
    detalhe     jsonb,
    request_id  text
);

CREATE INDEX IF NOT EXISTS idx_evento_auditoria_recente
    ON evento_auditoria (ocorrido_em DESC);
CREATE INDEX IF NOT EXISTS idx_evento_auditoria_ator
    ON evento_auditoria (ator_id, ocorrido_em DESC);
CREATE INDEX IF NOT EXISTS idx_evento_auditoria_acao
    ON evento_auditoria (acao, ocorrido_em DESC);

COMMENT ON TABLE  evento_auditoria         IS 'Quem fez o quê, quando. Nunca guarda senha, hash nem corpo de mensagem.';
COMMENT ON COLUMN evento_auditoria.acao    IS 'login_ok, login_falhou, primeiro_acesso_bloqueado, nota_editada, acesso_resetado, …';
COMMENT ON COLUMN evento_auditoria.request_id IS 'Costura o evento às linhas de log da mesma requisição (X-Request-Id).';

COMMIT;
