-- 0082 · Envio de push por evento: o registro, e a trava de "uma vez só" (docs/45 §16)
--
-- Uma linha por ENVIO de um evento, não por aparelho: "a missão de 19/11 saiu
-- para 312 aparelhos, 4 foram apagados". O que aconteceu com cada aparelho
-- continua em `inscricao_push` (`ultimo_status_http`, `ultimo_envio_ok_em`).
--
-- A 0081 deixou esta tabela de fora de propósito (docs/45 §5.2): para o botão de
-- teste ela seria uma tabela crescendo sem leitor. Ela entra com o primeiro
-- evento porque ele PRECISA dela — e não pelo log, pela idempotência:
--
--   o `UNIQUE (tipo, referencia)` é o que impede o mesmo evento de sair duas
--   vezes. A linha é reservada ANTES do primeiro POST (`app/push/registro.py`),
--   e um segundo disparo do mesmo dia — cron repetido, alguém rodando à mão,
--   deploy no meio — encontra a vaga ocupada. Aviso repetido para a turma
--   inteira é o que faz o aluno desligar os avisos, e desligar é para TODOS os
--   tipos de aviso, não só para aquele.
--
-- Cresce uma linha por dia por evento agendado: a missão do dia dá 365 por ano.
-- Não precisa de limpeza (armadilha 2 não se aplica a esse volume).
--
-- ⚠️ Depois de aplicar: o `migrate.py` já manda `NOTIFY pgrst, 'reload schema'`,
-- mas na dúvida `docker compose restart postgrest` (armadilha 1). Como a 0081,
-- nasce invisível ao `sas_leitura` do MCP, e está certo assim.

BEGIN;

CREATE TABLE envio_push (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- O mesmo slug de `Notificacao.tipo` (app/push/envio.py).
    tipo           text NOT NULL CHECK (tipo ~ '^[a-z0-9][a-z0-9-]{0,63}$'),
    -- O que torna o envio único dentro do tipo. Para a missão do dia é a data
    -- em America/Fortaleza ('2026-11-19'); um evento futuro por simulado usaria
    -- o id do simulado.
    referencia     text NOT NULL CHECK (length(referencia) BETWEEN 1 AND 128),
    CONSTRAINT envio_push_uma_vez UNIQUE (tipo, referencia),

    iniciado_em    timestamptz NOT NULL DEFAULT now(),
    -- NULL com `iniciado_em` antigo = o processo morreu no meio. O envio NÃO é
    -- refeito naquele dia: perder um aviso é barato, repetir para todos não é.
    concluido_em   timestamptz,

    -- Pessoas, não aparelhos: quem tinha aparelho ativo e entrou no envio, e
    -- quem tinha mas ficou de fora pela regra do evento (na missão: já mexeu
    -- no assunto de hoje).
    destinatarios  int CHECK (destinatarios >= 0),
    pulados        int CHECK (pulados >= 0),

    -- Aparelhos, como `ResultadoDoEnvio` (app/push/envio.py).
    tentadas       int CHECK (tentadas >= 0),
    entregues      int CHECK (entregues >= 0),
    removidas      int CHECK (removidas >= 0),
    falhas         int CHECK (falhas >= 0),

    -- Por que não houve envio ("sem_missao") ou por que ele parou no meio.
    -- Nunca leva endpoint, chave nem nome de aluno.
    observacao     text
);

COMMENT ON TABLE envio_push IS
    'Um envio de um evento de push (docs/45 §16): quando, para quantos, com que resultado. O UNIQUE (tipo, referencia) é a trava que impede o mesmo evento de sair duas vezes.';
COMMENT ON COLUMN envio_push.referencia IS
    'O que torna o envio único dentro do tipo. Missão do dia: a data em America/Fortaleza.';
COMMENT ON COLUMN envio_push.concluido_em IS
    'NULL com iniciado_em antigo = o processo morreu no meio do envio. Não se refaz: a vaga do dia já foi usada.';
COMMENT ON COLUMN envio_push.destinatarios IS
    'Pessoas com aparelho ativo que entraram no envio.';
COMMENT ON COLUMN envio_push.pulados IS
    'Pessoas com aparelho ativo que ficaram de fora pela regra do evento (missão do dia: já mexeram no assunto de hoje).';
COMMENT ON COLUMN envio_push.observacao IS
    'Motivo de não ter havido envio, ou erro que interrompeu. Sem dado de aluno nem de aparelho.';

COMMIT;
