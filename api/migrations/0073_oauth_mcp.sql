-- 0073 · OAuth dos conectores do MCP (docs/43 §5.3, Fase 3)
--
-- O claude.ai e o ChatGPT não aceitam colar um token: o conector se CADASTRA
-- sozinho (RFC 7591), manda a coordenadora aprovar no SAS e troca o código por
-- um access token (RFC 6749 §4.1, com PKCE S256 — RFC 7636). Quem fala o
-- protocolo é a API (app/routes/oauth_mcp.py); estas são as tabelas dela.
--
-- O ACCESS TOKEN NÃO TEM TABELA AQUI: é uma linha de `token_mcp` (0072) com
-- origem 'oauth' e `oauth_cliente_id`. O MCP já o confere pela mesma RPC
-- (`mcp_conferir_token`), sem saber que veio do OAuth, e a tela de Conexões de
-- IA já o lista e revoga. A linha de `token_mcp` é a CONEXÃO: cada refresh
-- troca o hash DELA (o access antigo morre na hora) em vez de criar outra —
-- senão a lista ganharia uma linha por hora, e revogar a linha da tela não
-- cortaria nada, porque o app pegaria um access novo com o refresh.
--
-- O caminho, tabela por tabela:
--   oauth_cliente_mcp           o cadastro dinâmico: quem pode pedir, e para
--                               onde volta
--   oauth_pedido_mcp            o /oauth/authorize guardado até alguém decidir
--                               na tela /conectar-ia (10 min)
--   email_conta_ia_mcp          o e-mail da conta de IA de cada coordenador:
--                               quem pode aprovar, e em nome de quem — só
--                               depois de CONFIRMADO, com o código que chegou
--                               a ele no cadastro
--   oauth_codigo_por_email_mcp  o código de 6 dígitos que aprova o pedido,
--                               enviado àquele e-mail: só o HMAC, 5 tentativas,
--                               USO ÚNICO, 10 min
--   oauth_codigo_mcp            o código da aprovação (o do RFC): só o hash,
--                               USO ÚNICO, 10 min
--   oauth_refresh_mcp           o refresh: só o hash, gira a cada uso, e o novo
--                               herda o prazo do velho (a conexão vale N dias
--                               da aprovação)
--
-- QUEM APROVA (decisão do dono em 26/10). O claude.ai e o ChatGPT não dizem ao
-- SAS qual é a conta de quem conecta, e a tela de consentimento abre no browser
-- em que a IA está — sem sessão do SAS, muitas vezes. A aprovação deixou de ser
-- a sessão da coordenação e passou a ser a POSSE do e-mail da conta de IA: o
-- coordenador cadastra esse e-mail no card "Conexões de IA" (pode não ser o do
-- SAS, pode ser mais de um), a tela pede um código enviado a ele, e quem
-- digita o código aprova — a conexão nasce em nome do coordenador DONO do
-- e-mail. A tela não exige login; o que ela exige é o código.
--
-- E O CADASTRO TAMBÉM PROVA A POSSE (revisão de segurança de 26/10). Sem
-- isso, quem lesse a caixa de um e-mail digitado errado ("gmial.com", um
-- catch-all) ou compartilhado aprovava conexões com o acesso da conta — nome
-- de aluno menor de idade incluído. O e-mail nasce AGUARDANDO, com um código
-- enviado a ele; só vale depois que quem o cadastrou, logado no card, digita
-- esse código (routes/mcp_emails_ia.py, regra 0).
--
-- Nada é guardado em claro que valha como credencial: segredo de cliente,
-- código e refresh ficam como sha256 em hex — os três têm 256 bits aleatórios,
-- então não há dicionário a atacar (o mesmo raciocínio de token_mcp, 0072). O
-- código de 6 dígitos é a exceção que confirma: com um milhão de valores, um
-- sha256 cairia num segundo para quem lesse o banco, e por isso ele fica como
-- HMAC com uma chave que mora no ambiente da API, não aqui
-- (app/mcp/emails_ia.chave_dos_hashes). O id do pedido fica em claro: ele só
-- ABRE a tela de consentimento, que mostra o app e permite RECUSAR; aprovar
-- pede o código que chegou ao e-mail cadastrado, e o código do RFC vai para a
-- redirect_uri de quem criou o pedido — quem lê o id não ganha acesso.
--
-- QUEM LÊ E ESCREVE
--   * a API (sas_service), com ALL pelos DEFAULT PRIVILEGES de
--     infra/postgres/init/01-papeis.sh — nenhum GRANT aqui.
--   * o MCP (sas_mcp) NADA: nenhuma destas tabelas entra na lista branca da
--     0071, e o REVOKE abaixo fecha cada uma mesmo que alguém tenha criado
--     DEFAULT PRIVILEGES por fora. Ele confere o access pela RPC da 0072 e
--     não precisa saber que OAuth existe.
--
-- Nunca se apaga: pedido decidido, código usado, refresh revogado e e-mail
-- removido são o que responde, depois, "quem aprovou que app, quando, e por
-- qual e-mail" — por isso as FKs não têm CASCADE: apagar um cliente com
-- história falha alto. A exceção é o pedido que VENCE SEM DECISÃO: ele não
-- responde nada (a tela o trata como inexistente, e nenhum código do RFC saiu
-- dele), e o /oauth/authorize, que é anônimo e grava uma linha por pedido,
-- apaga os vencidos (`FaxinaDosPedidos`) e limita os abertos
-- (MCP_OAUTH_PEDIDOS_ABERTOS_*). Sem os dois, um IP sozinho gravava ~375 MB
-- por dia aqui, no banco dos alunos (revisão de segurança de 25/10). Os
-- códigos por e-mail de um pedido assim vão junto (o único CASCADE daqui):
-- eram a tentativa de aprovar algo que ninguém aprovou.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`
-- (CLAUDE.md, armadilha 1) — antes do restart as tabelas novas voltam 404.

BEGIN;

-- ─── 1. O cadastro dinâmico (RFC 7591) ────────────────────────────────────

CREATE TABLE oauth_cliente_mcp (
    -- uuid4 em texto, gerado pela API. Texto e não uuid: o client_id chega do
    -- cliente em todo pedido, e um valor torto num filtro de coluna uuid
    -- derrubaria a consulta com 400 em vez de dar "cliente desconhecido".
    client_id                   text PRIMARY KEY
        CONSTRAINT oauth_cliente_mcp_client_id_curto
        CHECK (char_length(client_id) BETWEEN 1 AND 64),
    -- Só o cliente CONFIDENCIAL tem segredo, e só o sha256 dele fica aqui; o
    -- segredo em claro sai uma vez, na resposta do cadastro.
    client_secret_hash          text
        CONSTRAINT oauth_cliente_mcp_segredo_e_sha256_hex
        CHECK (client_secret_hash IS NULL OR client_secret_hash ~ '^[0-9a-f]{64}$'),
    -- O nome que o PRÓPRIO app declarou. Não prova nada — qualquer um se
    -- cadastra como "Claude"; a tela mostra o host de volta ao lado dele.
    client_name                 text
        CONSTRAINT oauth_cliente_mcp_nome_curto
        CHECK (client_name IS NULL OR char_length(client_name) BETWEEN 1 AND 100),
    -- https, ou http de loopback para app nativo (RFC 8252 §7.3) — quem
    -- confere o formato é a API; aqui, o teto e a ausência de NULL.
    redirect_uris               text[] NOT NULL
        CONSTRAINT oauth_cliente_mcp_redirect_uris_validas
        CHECK (cardinality(redirect_uris) BETWEEN 1 AND 10
               AND array_position(redirect_uris, NULL) IS NULL),
    token_endpoint_auth_method  text NOT NULL
        CONSTRAINT oauth_cliente_mcp_metodo_valido
        CHECK (token_endpoint_auth_method IN ('none', 'client_secret_basic', 'client_secret_post')),
    grant_types                 text[] NOT NULL
        CONSTRAINT oauth_cliente_mcp_grants_validos
        CHECK (grant_types <@ ARRAY['authorization_code', 'refresh_token']::text[]
               AND 'authorization_code' = ANY (grant_types)),
    criado_em                   timestamptz NOT NULL DEFAULT now(),

    -- Público ("none") não tem segredo; confidencial tem. Sem isto, um
    -- confidencial sem hash autenticaria com qualquer segredo — ou nenhum.
    CONSTRAINT oauth_cliente_mcp_segredo_coerente
        CHECK ((token_endpoint_auth_method = 'none') = (client_secret_hash IS NULL))
);

COMMENT ON TABLE oauth_cliente_mcp IS
    'Clientes OAuth do MCP cadastrados pelo registro dinâmico (RFC 7591, docs/43 §5.3). O segredo do confidencial fica só como sha256.';
COMMENT ON COLUMN oauth_cliente_mcp.client_name IS
    'Nome que o próprio app declarou no cadastro. Não é conferido: a tela de consentimento mostra o host de volta junto.';
COMMENT ON COLUMN oauth_cliente_mcp.redirect_uris IS
    'Endereços de volta aceitos. O /oauth/authorize compara o pedido com eles por texto exato; só no http de loopback a porta pode variar (RFC 8252 §7.3).';

-- O token do MCP de origem 'oauth' aponta para o cliente que o recebeu. A
-- 0072 deixou a coluna sem FK porque esta tabela ainda não existia; sem
-- CASCADE nem SET NULL, como o resto: cliente com conexão não se apaga.
ALTER TABLE token_mcp
    ADD CONSTRAINT token_mcp_oauth_cliente_fk
    FOREIGN KEY (oauth_cliente_id) REFERENCES oauth_cliente_mcp (client_id);

REVOKE ALL ON oauth_cliente_mcp FROM PUBLIC, sas_leitura, sas_mcp;


-- ─── 2. O pedido de autorização, até a coordenadora decidir ──────────────

CREATE TABLE oauth_pedido_mcp (
    -- secrets.token_urlsafe(32): vai na URL da tela, /conectar-ia?pedido=<id>.
    id                      text PRIMARY KEY
        CONSTRAINT oauth_pedido_mcp_id_opaco
        CHECK (id ~ '^[A-Za-z0-9_-]{43}$'),
    client_id               text NOT NULL REFERENCES oauth_cliente_mcp (client_id),
    -- A redirect_uri DESTE pedido (com a porta que o app nativo escolheu), e
    -- se ela veio no pedido: o /oauth/token só a dispensa se não veio
    -- (RFC 6749 §4.1.3).
    redirect_uri            text NOT NULL
        CONSTRAINT oauth_pedido_mcp_redirect_uri_curta
        CHECK (char_length(redirect_uri) BETWEEN 1 AND 2000),
    redirect_uri_explicita  boolean NOT NULL DEFAULT true,
    code_challenge          text NOT NULL
        CONSTRAINT oauth_pedido_mcp_desafio_pkce
        CHECK (code_challenge ~ '^[A-Za-z0-9._~-]{43,128}$'),
    -- Só S256: "plain" mandaria o verificador em claro pelo browser.
    code_challenge_method   text NOT NULL DEFAULT 'S256'
        CONSTRAINT oauth_pedido_mcp_so_s256
        CHECK (code_challenge_method = 'S256'),
    state                   text
        CONSTRAINT oauth_pedido_mcp_state_curto
        CHECK (state IS NULL OR char_length(state) <= 2048),
    scope                   text NOT NULL,
    -- O `resource` do RFC 8707, quando o app mandou: a URL do MCP.
    resource                text,
    criado_em               timestamptz NOT NULL DEFAULT now(),
    expira_em               timestamptz NOT NULL,
    decidido_em             timestamptz,
    decidido_por            uuid REFERENCES usuario_coordenacao (id),
    aprovado                boolean,

    CONSTRAINT oauth_pedido_mcp_expira_depois_de_criado
        CHECK (expira_em > criado_em),
    -- Decidido é decidido, com uma resposta — ou nada disso. A APROVAÇÃO tem
    -- autor: o coordenador dono do e-mail que recebeu o código, em nome de
    -- quem a conexão nasce. A RECUSA não tem: desde 26/10 a tela não pede
    -- sessão do SAS, e recusar só pede o link do pedido.
    CONSTRAINT oauth_pedido_mcp_decisao_coerente
        CHECK ((decidido_em IS NULL) = (aprovado IS NULL)
               AND (decidido_por IS NOT NULL) = (aprovado IS TRUE))
);

-- Os pedidos sem decisão: é por eles que o /oauth/authorize conta os abertos
-- (o teto) e apaga os vencidos (a faxina). Parcial porque o decidido fica
-- para sempre e não entra em nenhuma das duas contas.
CREATE INDEX idx_oauth_pedido_mcp_sem_decisao ON oauth_pedido_mcp (expira_em)
    WHERE decidido_em IS NULL;

COMMENT ON TABLE oauth_pedido_mcp IS
    'Pedido do /oauth/authorize esperando aprovação (com o código enviado ao e-mail da conta de IA) ou recusa na tela /conectar-ia (docs/43 §5.3). Vale 10 minutos; decidido, não volta. Vencido sem decisão, o próprio /authorize apaga.';
COMMENT ON COLUMN oauth_pedido_mcp.decidido_por IS
    'Na aprovação, o coordenador dono do e-mail que recebeu o código — a conexão nasce em nome dele. Na recusa, NULL: recusar não pede sessão nem código.';

REVOKE ALL ON oauth_pedido_mcp FROM PUBLIC, sas_leitura, sas_mcp;


-- ─── 2b. O e-mail da conta de IA: quem aprova, e em nome de quem ──────────

CREATE TABLE email_conta_ia_mcp (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- O coordenador em nome de quem a conexão aprovada por este e-mail nasce.
    usuario_coordenacao_id  uuid NOT NULL REFERENCES usuario_coordenacao (id),
    -- Em minúsculas e sem espaço nas pontas: é por este texto que o /codigo
    -- procura, e "Ana@Gmail.com" e "ana@gmail.com" são a mesma caixa. A forma
    -- inteira (o "valid e-mail address" do HTML, com ponto no domínio) quem
    -- confere é a API (app/mcp/emails_ia.email_valido); aqui, o mínimo.
    email                   text NOT NULL
        CONSTRAINT email_conta_ia_mcp_email_normalizado
        CHECK (email = lower(btrim(email))
               AND char_length(email) BETWEEN 3 AND 254
               AND email ~ '^[^@[:space:]]+@[^@[:space:]]+$'),
    criado_em               timestamptz NOT NULL DEFAULT now(),
    -- A PROVA DE POSSE: preenchido quando quem cadastrou digita, logado no
    -- card, o código que chegou a este e-mail. NULL = aguardando — e o
    -- aguardando não recebe código de aprovar nem aprova nada (o /codigo e o
    -- /aprovar só procuram o confirmado).
    confirmado_em           timestamptz,
    -- O código de confirmação em aberto: só o HMAC, preso a ESTE cadastro e ao
    -- e-mail (app/mcp/emails_ia.hash_da_confirmacao), com a chave que mora no
    -- ambiente da API — o mesmo raciocínio do código de aprovar, logo abaixo.
    -- Pedir outro troca o hash e zera as tentativas; confirmado, ele sai.
    hash_codigo_de_confirmacao text
        CONSTRAINT email_conta_ia_mcp_hash_da_confirmacao_hex
        CHECK (hash_codigo_de_confirmacao IS NULL OR hash_codigo_de_confirmacao ~ '^[0-9a-f]{64}$'),
    confirmacao_expira_em   timestamptz,
    -- Cada conferência gasta uma ANTES de comparar, como no código de aprovar.
    -- O 5 é o de app/mcp/emails_ia.TENTATIVAS_POR_CODIGO (um teste confere).
    tentativas_de_confirmacao smallint NOT NULL DEFAULT 0
        CONSTRAINT email_conta_ia_mcp_tentativas_de_confirmacao
        CHECK (tentativas_de_confirmacao BETWEEN 0 AND 5),
    -- A última aprovação feita com ele: o que o card mostra.
    ultimo_uso_em           timestamptz,
    -- Remover é preencher isto, nunca apagar a linha (a regra de token_mcp,
    -- 0072): a removida responde depois "quem podia aprovar conexão, e até
    -- quando", e o código que ela recebeu aponta para ela.
    removido_em             timestamptz,

    CONSTRAINT email_conta_ia_mcp_removido_depois_de_criado
        CHECK (removido_em IS NULL OR removido_em >= criado_em),
    CONSTRAINT email_conta_ia_mcp_confirmado_depois_de_criado
        CHECK (confirmado_em IS NULL OR confirmado_em >= criado_em),
    -- Aguardando tem código (com prazo) a conferir; confirmado, não tem mais.
    CONSTRAINT email_conta_ia_mcp_codigo_so_enquanto_aguarda
        CHECK ((confirmado_em IS NULL) = (hash_codigo_de_confirmacao IS NOT NULL)
               AND (hash_codigo_de_confirmacao IS NULL) = (confirmacao_expira_em IS NULL)),
    -- Só o confirmado aprova, então só ele tem "último uso".
    CONSTRAINT email_conta_ia_mcp_uso_so_depois_de_confirmado
        CHECK (ultimo_uso_em IS NULL OR confirmado_em IS NOT NULL)
);

-- Um e-mail aprova em nome de UMA conta só: com dois donos, a conexão nasceria
-- em nome de quem? Único entre os CONFIRMADOS ativos — o removido pode voltar,
-- por quem o removeu ou por outra conta, e o que só AGUARDA não tranca
-- ninguém: ele não aprova nada, e quem digitou o e-mail de outra pessoa não
-- pode impedir o dono da caixa de cadastrá-lo e confirmá-lo na conta dele. A
-- API recusa antes (409); o índice é o que vale quando duas confirmações
-- chegam juntas.
CREATE UNIQUE INDEX uq_email_conta_ia_mcp_confirmado ON email_conta_ia_mcp (email)
    WHERE removido_em IS NULL AND confirmado_em IS NOT NULL;
-- Na MESMA conta, um ativo por e-mail, aguardando ou confirmado: o segundo
-- cadastro do mesmo endereço é 409 (o card já mostra o primeiro, com o código).
CREATE UNIQUE INDEX uq_email_conta_ia_mcp_na_conta ON email_conta_ia_mcp (usuario_coordenacao_id, email)
    WHERE removido_em IS NULL;
CREATE INDEX idx_email_conta_ia_mcp_usuario ON email_conta_ia_mcp (usuario_coordenacao_id);

COMMENT ON TABLE email_conta_ia_mcp IS
    'E-mail da conta de IA (claude.ai, ChatGPT) de cada coordenador, cadastrado no card Conexões de IA (decisão de 26/10). Nasce aguardando: só depois de confirmado, com o código que chegou a ele, recebe o código que aprova a conexão OAuth — e a conexão nasce em nome do dono. Removido não se apaga.';
COMMENT ON COLUMN email_conta_ia_mcp.confirmado_em IS
    'Quando quem cadastrou provou a posse da caixa, digitando no card o código enviado a ela. NULL = aguardando: não recebe código de aprovar nem aprova (revisão de segurança de 26/10).';

-- Credencial de aprovação: nem o sas_mcp nem o leitor genérico o enxergam.
REVOKE ALL ON email_conta_ia_mcp FROM PUBLIC, sas_leitura, sas_mcp;


-- ─── 2c. O código enviado ao e-mail, que aprova o pedido ─────────────────

CREATE TABLE oauth_codigo_por_email_mcp (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- O único CASCADE da 0073: o pedido que vence sem decisão é apagado pela
    -- faxina do /authorize, e o código de quem tentou aprová-lo vai junto.
    pedido_id               text NOT NULL REFERENCES oauth_pedido_mcp (id) ON DELETE CASCADE,
    -- O e-mail DIGITADO, como HMAC. O /codigo grava uma linha para QUALQUER
    -- e-mail, cadastrado ou não: é isso que deixa a resposta dele e a do
    -- /aprovar iguais nos dois casos — senão o banco a mais ou a menos contaria
    -- quais e-mails estão cadastrados. E o que alguém digitou não fica em claro.
    hash_email              text NOT NULL
        CONSTRAINT oauth_codigo_por_email_mcp_hash_email_hex
        CHECK (hash_email ~ '^[0-9a-f]{64}$'),
    -- O cadastro que RECEBEU o código. NULL = e-mail sem cadastro ativo e
    -- confirmado, ou de conta que não pode conectar: nenhum e-mail saiu, e o
    -- código desta linha, que ninguém viu, não aprova nada.
    email_conta_ia_id       uuid REFERENCES email_conta_ia_mcp (id),
    -- O código de 6 dígitos, só como HMAC preso ao pedido E ao e-mail.
    hash_codigo             text NOT NULL
        CONSTRAINT oauth_codigo_por_email_mcp_hash_codigo_hex
        CHECK (hash_codigo ~ '^[0-9a-f]{64}$'),
    criado_em               timestamptz NOT NULL DEFAULT now(),
    expira_em               timestamptz NOT NULL,
    -- Cada conferência gasta uma ANTES de comparar, num UPDATE condicional:
    -- dez tentativas ao mesmo tempo não viram dez comparações. O 5 é o de
    -- app/mcp/emails_ia.TENTATIVAS_POR_CODIGO (um teste confere os dois).
    tentativas              smallint NOT NULL DEFAULT 0
        CONSTRAINT oauth_codigo_por_email_mcp_tentativas
        CHECK (tentativas BETWEEN 0 AND 5),
    -- Uso único: preenchido quando o código certo é apresentado.
    usado_em                timestamptz,

    CONSTRAINT oauth_codigo_por_email_mcp_expira_depois_de_criado
        CHECK (expira_em > criado_em)
);

-- O /aprovar procura o código mais recente de (pedido, e-mail digitado).
CREATE INDEX idx_oauth_codigo_por_email_mcp_pedido
    ON oauth_codigo_por_email_mcp (pedido_id, hash_email, criado_em DESC);

COMMENT ON TABLE oauth_codigo_por_email_mcp IS
    'Código de 6 dígitos enviado ao e-mail da conta de IA para aprovar um pedido do OAuth do MCP (decisão de 26/10): só o HMAC, 10 minutos, 5 tentativas, uso único, preso ao pedido e ao e-mail. Há linha também para e-mail não cadastrado (sem envio), para a resposta não contar quem está cadastrado.';

REVOKE ALL ON oauth_codigo_por_email_mcp FROM PUBLIC, sas_leitura, sas_mcp;


-- ─── 3. O código da aprovação: uso único ─────────────────────────────────

CREATE TABLE oauth_codigo_mcp (
    hash_codigo             text PRIMARY KEY
        CONSTRAINT oauth_codigo_mcp_hash_e_sha256_hex
        CHECK (hash_codigo ~ '^[0-9a-f]{64}$'),
    -- Um código por pedido: aprovar de novo não gera outro.
    pedido_id               text NOT NULL UNIQUE REFERENCES oauth_pedido_mcp (id),
    -- Quem aprovou: é em nome desta conta que a conexão nasce.
    usuario_coordenacao_id  uuid NOT NULL REFERENCES usuario_coordenacao (id),
    criado_em               timestamptz NOT NULL DEFAULT now(),
    expira_em               timestamptz NOT NULL,
    -- Preenchido na troca, num UPDATE condicional (usado_em IS NULL): duas
    -- trocas simultâneas, só uma ganha. Reapresentado depois, o código não
    -- vale e a conexão que ele gerou cai (RFC 6749 §4.1.2).
    usado_em                timestamptz,
    -- A conexão que a troca criou — é ela que cai quando o código volta.
    token_mcp_id            uuid REFERENCES token_mcp (id),

    CONSTRAINT oauth_codigo_mcp_expira_depois_de_criado
        CHECK (expira_em > criado_em),
    CONSTRAINT oauth_codigo_mcp_conexao_so_depois_de_usado
        CHECK (token_mcp_id IS NULL OR usado_em IS NOT NULL)
);

COMMENT ON TABLE oauth_codigo_mcp IS
    'Código de autorização do OAuth do MCP: só o sha256, uso único, 10 minutos (RFC 6749 §4.1.2). Reapresentado, derruba a conexão que gerou.';

REVOKE ALL ON oauth_codigo_mcp FROM PUBLIC, sas_leitura, sas_mcp;


-- ─── 4. O refresh token: gira a cada uso ─────────────────────────────────

CREATE TABLE oauth_refresh_mcp (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    hash_refresh            text NOT NULL UNIQUE
        CONSTRAINT oauth_refresh_mcp_hash_e_sha256_hex
        CHECK (hash_refresh ~ '^[0-9a-f]{64}$'),
    client_id               text NOT NULL REFERENCES oauth_cliente_mcp (client_id),
    usuario_coordenacao_id  uuid NOT NULL REFERENCES usuario_coordenacao (id),
    -- A CONEXÃO (a linha de token_mcp cujo hash cada giro troca). Todos os
    -- refresh de uma aprovação apontam para a mesma: é a "família" que cai
    -- inteira quando um refresh já girado é reapresentado (RFC 9700 §4.14.2).
    token_mcp_id            uuid NOT NULL REFERENCES token_mcp (id),
    pedido_id               text REFERENCES oauth_pedido_mcp (id),
    scope                   text NOT NULL,
    resource                text,
    criado_em               timestamptz NOT NULL DEFAULT now(),
    -- O prazo da CONEXÃO, contado da aprovação: o refresh novo herda o do
    -- velho, então usar não estica (MCP_VALIDADE_DO_REFRESH_OAUTH_DIAS).
    expira_em               timestamptz NOT NULL,
    revogado_em             timestamptz,
    substituido_por         uuid REFERENCES oauth_refresh_mcp (id),

    CONSTRAINT oauth_refresh_mcp_expira_depois_de_criado
        CHECK (expira_em > criado_em),
    -- Girado é revogado: o velho morre no giro.
    CONSTRAINT oauth_refresh_mcp_substituido_e_revogado
        CHECK (substituido_por IS NULL OR revogado_em IS NOT NULL)
);

-- Derrubar a conexão revoga todo refresh dela de uma vez.
CREATE INDEX idx_oauth_refresh_mcp_conexao ON oauth_refresh_mcp (token_mcp_id);

COMMENT ON TABLE oauth_refresh_mcp IS
    'Refresh token do OAuth do MCP: só o sha256. Gira a cada uso (o velho é revogado e aponta para o novo) e herda o prazo da conexão. Reapresentar um girado derruba a conexão inteira (RFC 9700 §4.14.2).';

REVOKE ALL ON oauth_refresh_mcp FROM PUBLIC, sas_leitura, sas_mcp;

COMMIT;
