-- 0081 · Inscrição de push: um aparelho que aceitou receber aviso do SAS (docs/45 §5.2)
--
-- Cada linha é uma `PushSubscription` do navegador — o endereço no serviço de push
-- do fabricante (FCM, APNs, Mozilla, WNS) mais as duas chaves com que o servidor
-- cifra o conteúdo para AQUELE aparelho (RFC 8291). Nenhum evento manda push ainda:
-- esta migration é só a capacidade.
--
-- O dono é exatamente um, e são DUAS FKs de verdade, não (tipo, id) solto:
--   - o ON DELETE CASCADE dá de graça a parte de push do caminho de eliminação da
--     LGPD (docs/19 bloco G) — apagar o aluno apaga os aparelhos dele;
--   - um id de coordenação nunca pode ser lido como id de aluno.
-- A cantina fica de fora até um evento pedir (docs/45 §5.3): entrar depois custa
-- uma coluna e alargar o CHECK.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest` (armadilha 1). O MCP
-- não lê esta tabela, e não deve: a lista branca do `sas_leitura` é por coluna, e
-- tabela nova nasce invisível a ele — que é o certo para endereço de aparelho.

BEGIN;

CREATE TABLE inscricao_push (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id                uuid REFERENCES aluno(id) ON DELETE CASCADE,
    usuario_coordenacao_id  uuid REFERENCES usuario_coordenacao(id) ON DELETE CASCADE,
    CONSTRAINT inscricao_push_um_dono
        CHECK (num_nonnulls(aluno_id, usuario_coordenacao_id) = 1),

    -- O mesmo navegador devolve o mesmo endpoint a quem se inscrever nele. Com
    -- UNIQUE, a inscrição MUDA DE DONO num computador compartilhado em vez de
    -- existirem duas — e o aviso do aluno que saiu não aparece na tela do próximo.
    endpoint                text NOT NULL UNIQUE,
    chave_p256dh            text NOT NULL,
    chave_auth              text NOT NULL,

    plataforma              text NOT NULL
        CHECK (plataforma IN ('ios', 'android', 'desktop', 'outra')),
    descricao_aparelho      text,

    criada_em               timestamptz NOT NULL DEFAULT now(),
    vista_em                timestamptz NOT NULL DEFAULT now(),
    ultimo_envio_ok_em      timestamptz,
    falhas_seguidas         int NOT NULL DEFAULT 0 CHECK (falhas_seguidas >= 0),
    ultimo_status_http      int,
    ultimo_erro             text
);

CREATE INDEX inscricao_push_aluno
    ON inscricao_push (aluno_id) WHERE aluno_id IS NOT NULL;
CREATE INDEX inscricao_push_coordenacao
    ON inscricao_push (usuario_coordenacao_id) WHERE usuario_coordenacao_id IS NOT NULL;

COMMENT ON TABLE inscricao_push IS
    'Aparelho que aceitou receber notificação push do SAS (Web Push, RFC 8030/8291/8292). Um dono: aluno OU coordenação. Docs/45.';
COMMENT ON COLUMN inscricao_push.endpoint IS
    'URL do serviço de push do fabricante para esta inscrição. Só hosts da lista fechada de app/push/endpoints.py entram: o servidor faz POST nela (SSRF).';
COMMENT ON COLUMN inscricao_push.chave_p256dh IS
    'Chave pública ECDH (P-256, ponto não comprimido, base64url) do aparelho. Com a chave_auth, é o que cifra o conteúdo de ponta a ponta.';
COMMENT ON COLUMN inscricao_push.chave_auth IS
    'Segredo de autenticação de 16 bytes (base64url) gerado pelo navegador.';
COMMENT ON COLUMN inscricao_push.plataforma IS
    'De onde veio a inscrição, para a lista "seus aparelhos" e para medir a adesão por plataforma (docs/45 §8).';
COMMENT ON COLUMN inscricao_push.descricao_aparelho IS
    'Texto curto que o próprio front monta ("iPhone · app instalado"). Só exibição.';
COMMENT ON COLUMN inscricao_push.vista_em IS
    'Última vez que o navegador confirmou a inscrição ao abrir o SAS (reconciliação, docs/45 §6.1).';
COMMENT ON COLUMN inscricao_push.falhas_seguidas IS
    'Falhas TRANSITÓRIAS seguidas (429, 5xx, rede). Erro nosso (400/403/413) não conta: chave errada nossa não pode apagar o aparelho de ninguém.';
COMMENT ON COLUMN inscricao_push.ultimo_status_http IS
    'Status da última resposta do serviço de push. Diagnóstico de "o aviso chegou?".';

COMMIT;
