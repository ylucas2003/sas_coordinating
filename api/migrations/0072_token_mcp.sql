-- 0072 · O token do MCP da coordenação (docs/43 §5.3, Fases 2 e 3)
--
-- Quem conecta uma IA ao MCP é uma pessoa da coordenação, e cada conexão tem
-- um token próprio: revogável sozinho, com nome ("Claude Code do Leo"), e
-- ligado a UMA conta — é a conta que aparece na auditoria de cada chamada.
--
-- O token é OPACO ('sas_mcp_' + secrets.token_urlsafe(32)), nunca JWT, e só o
-- sha256 dele fica aqui. Dois efeitos, os dois de propósito:
--   * o MCP não precisa de JWT_SECRET_KEY nem de segredo nenhum para validar
--     — ele calcula o sha256 do que recebeu e pergunta ao banco;
--   * `get_current_user` recusa o token do MCP por construção (não é JWT), e
--     um JWT de sessão nunca abre o MCP (não está nesta tabela). É a mesma
--     separação que fechou o token de download (test_auth_chat.py).
-- O token em claro sai UMA vez, na emissão, e não é recuperável: quem perder
-- emite outro e revoga o velho.
--
-- QUEM LÊ E ESCREVE
--   * a API (sas_service) emite, lista e revoga. Ela tem ALL nesta tabela pelo
--     ALTER DEFAULT PRIVILEGES de infra/postgres/init/01-papeis.sh — nenhum
--     GRANT aqui. Emitem e aprovam conexão OAuth o administrador E o
--     coordenador, cada um em nome da própria conta (decisão do dono em
--     26/10; até ali, só o administrador). MCP_EMISSAO_SO_ADMINISTRADOR=true
--     volta ao "só o administrador" — é opção, não o padrão. O administrador
--     vê e revoga todas; o coordenador, só as dele.
--   * o MCP (sas_mcp) NÃO lê esta tabela. Ele só chama mcp_conferir_token(),
--     que devolve a linha do hash pedido e nada mais: nem a lista de tokens,
--     nem hash, nem o de outra pessoa.
--
-- E o estreito de auditoria do MCP: toda chamada de tool vira evento (docs/43
-- §5.3), mas o sas_mcp não tem SELECT em evento_auditoria — ela guarda IP e,
-- em login_falhou, o e-mail digitado. INSERT sem SELECT só funciona com
-- `Prefer: return=minimal` (postgrest-py: returning=ReturnMethod.minimal): o
-- padrão do postgrest-py é return=representation, que faz RETURNING e exige
-- SELECT — e como auditoria.registrar() engole a exceção, o evento sumiria
-- sem erro nenhum, só com um warning no log.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`
-- (CLAUDE.md, armadilha 1) — tabela e função novas só entram no cache de
-- schema no restart; antes dele a RPC volta 404.

BEGIN;

-- ─── 1. A tabela ──────────────────────────────────────────────────────────

CREATE TABLE token_mcp (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_coordenacao_id  uuid NOT NULL REFERENCES usuario_coordenacao(id),
    nome                    text NOT NULL
        CONSTRAINT token_mcp_nome_valido
        CHECK (btrim(nome) <> '' AND char_length(nome) <= 80),
    origem                  text NOT NULL
        CONSTRAINT token_mcp_origem_valida
        CHECK (origem IN ('pessoal', 'oauth')),
    oauth_cliente_id        text,
    -- O CHECK de formato é a última barreira contra gravar o token em claro
    -- por engano: 'sas_mcp_…' não é hex de 64 caracteres.
    hash_acesso             text NOT NULL UNIQUE
        CONSTRAINT token_mcp_hash_e_sha256_hex
        CHECK (hash_acesso ~ '^[0-9a-f]{64}$'),
    prefixo                 text NOT NULL
        CONSTRAINT token_mcp_prefixo_curto
        CHECK (char_length(prefixo) BETWEEN 1 AND 20),
    criado_em               timestamptz NOT NULL DEFAULT now(),
    expira_em               timestamptz,
    ultimo_uso_em           timestamptz,
    revogado_em             timestamptz,
    revogado_por            uuid REFERENCES usuario_coordenacao(id),

    -- Token pessoal não tem cliente OAuth. O contrário (oauth sem cliente)
    -- fica permitido de propósito: a tabela de clientes nasce na 0073, e uma
    -- FK ON DELETE SET NULL de lá não pode esbarrar aqui.
    CONSTRAINT token_mcp_pessoal_sem_cliente
        CHECK (origem = 'oauth' OR oauth_cliente_id IS NULL),
    CONSTRAINT token_mcp_expira_depois_de_criado
        CHECK (expira_em IS NULL OR expira_em > criado_em),
    -- Quem revogou só existe se houve revogação. O contrário vale: revogação
    -- automática (conta desativada, cliente OAuth removido) não tem autor.
    CONSTRAINT token_mcp_revogacao_coerente
        CHECK (revogado_por IS NULL OR revogado_em IS NOT NULL)
);

-- A tela lista os tokens de uma conta; a conferência vai pelo UNIQUE do hash.
CREATE INDEX idx_token_mcp_usuario ON token_mcp (usuario_coordenacao_id);

COMMENT ON TABLE  token_mcp IS
    'Token de acesso ao MCP da coordenação (docs/43 §5.3). Guardado só como sha256. A API emite e revoga; o MCP só confere, por mcp_conferir_token().';
COMMENT ON COLUMN token_mcp.usuario_coordenacao_id IS
    'A conta dona do token — é ela que aparece na auditoria de cada chamada do MCP.';
COMMENT ON COLUMN token_mcp.nome IS
    'Nome que a pessoa dá à conexão ("Claude Code do Leo"), para reconhecer na tela. 1 a 80 caracteres.';
COMMENT ON COLUMN token_mcp.origem IS
    'pessoal = emitido pela tela de administração (Fase 2); oauth = emitido pelo authorization server da API para um conector (Fase 3).';
COMMENT ON COLUMN token_mcp.oauth_cliente_id IS
    'client_id do cadastro dinâmico (RFC 7591) quando origem = oauth. Sem FK aqui: a tabela de clientes nasce na 0073.';
COMMENT ON COLUMN token_mcp.hash_acesso IS
    'sha256 do token em claro, em hex minúsculo (hashlib.sha256(token.encode()).hexdigest()). O token em claro nunca é gravado.';
COMMENT ON COLUMN token_mcp.prefixo IS
    'Começo do token em claro (ex.: sas_mcp_AbCd), só para reconhecer na tela. Até 20 caracteres: o resto do token fica secreto.';
COMMENT ON COLUMN token_mcp.expira_em IS
    'NULL = não expira. Vencido, mcp_conferir_token() não o devolve mais.';
COMMENT ON COLUMN token_mcp.ultimo_uso_em IS
    'Gravado por mcp_conferir_token() no máximo uma vez por minuto. É sinal de uso para a tela, não trilha — a trilha é evento_auditoria.';
COMMENT ON COLUMN token_mcp.revogado_em IS
    'Preenchido = token morto. Não se apaga a linha: a auditoria aponta para ela.';
COMMENT ON COLUMN token_mcp.revogado_por IS
    'Quem revogou. NULL com revogado_em preenchido = revogação automática, sem autor.';

-- Nada nesta tabela é do MCP. O REVOKE não faz nada num banco montado pelas
-- migrations, e é por isso que ele está aqui: se alguém tiver criado DEFAULT
-- PRIVILEGES por fora, a tabela ainda nasce fechada para quem não é a API.
REVOKE ALL ON token_mcp FROM PUBLIC, sas_leitura, sas_mcp;


-- ─── 2. A conferência ─────────────────────────────────────────────────────
--
-- SECURITY DEFINER porque o sas_mcp não lê token_mcp nem usuario_coordenacao:
-- a função roda como o dono (o papel das migrations) e devolve só a linha do
-- hash pedido. `search_path` fixo, com pg_temp por último, fecha o sequestro
-- clássico de função SECURITY DEFINER por objeto temporário de mesmo nome.
--
-- Devolve a linha se, e só se: o token não foi revogado, não venceu e a conta
-- está ativa. Desativar a conta derruba todos os tokens dela na hora, sem
-- precisar revogar um por um. Fora disso, devolve conjunto vazio — o mesmo
-- para hash inexistente, revogado e vencido, para não contar a quem tenta
-- qual é o caso.
--
-- `nome` é o nome da PESSOA (usuario_coordenacao.nome), para a Sessao do
-- registro de ferramentas — não o nome do token.
--
-- ultimo_uso_em é gravado no máximo uma vez por minuto: um UPDATE por chamada
-- faria cada tools/call escrever no banco. O WHERE repete a condição para que
-- duas chamadas simultâneas não gravem duas vezes.
--
-- VOLATILE (o padrão) porque escreve. Chame por POST — é o que o `.rpc()` do
-- postgrest-py faz: por GET o PostgREST abre transação só-leitura, e a
-- conferência que precisa gravar ultimo_uso_em falha com 25006 (provado num
-- Postgres descartável em 24/10).

CREATE FUNCTION mcp_conferir_token(p_hash text)
RETURNS TABLE (token_id uuid, coordenador_id uuid, nome text, papel text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_token_id        uuid;
    v_coordenador_id  uuid;
    v_nome            text;
    v_papel           text;
    v_ultimo_uso_em   timestamptz;
BEGIN
    -- Toda coluna qualificada: `nome` e `papel` também são nomes das colunas
    -- de saída, e o plpgsql recusaria a referência ambígua.
    SELECT t.id, t.usuario_coordenacao_id, u.nome, u.papel, t.ultimo_uso_em
      INTO v_token_id, v_coordenador_id, v_nome, v_papel, v_ultimo_uso_em
      FROM token_mcp AS t
      JOIN usuario_coordenacao AS u ON u.id = t.usuario_coordenacao_id
     WHERE t.hash_acesso = p_hash
       AND t.revogado_em IS NULL
       AND (t.expira_em IS NULL OR t.expira_em > now())
       AND u.ativo;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    IF v_ultimo_uso_em IS NULL OR v_ultimo_uso_em < now() - interval '1 minute' THEN
        UPDATE token_mcp AS t
           SET ultimo_uso_em = now()
         WHERE t.id = v_token_id
           AND (t.ultimo_uso_em IS NULL OR t.ultimo_uso_em < now() - interval '1 minute');
    END IF;

    token_id       := v_token_id;
    coordenador_id := v_coordenador_id;
    nome           := v_nome;
    papel          := v_papel;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION mcp_conferir_token(text) IS
    'Confere um token do MCP pelo sha256 (hex): devolve (token_id, coordenador_id, nome da pessoa, papel) se o token não foi revogado, não venceu e a conta está ativa; senão, nada. Grava ultimo_uso_em no máximo uma vez por minuto. Só o sas_mcp executa (0072, docs/43 §5.3).';

-- O Postgres dá EXECUTE a PUBLIC em toda função nova. Esta lê credencial
-- como superusuário: só o sas_mcp a chama. Nem a API — ela não confere token
-- do MCP, só emite e revoga, e faz isso direto na tabela.
REVOKE ALL ON FUNCTION mcp_conferir_token(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION mcp_conferir_token(text) TO sas_mcp;


-- ─── 3. O estreito de auditoria ───────────────────────────────────────────
--
-- INSERT sim; SELECT, UPDATE e DELETE não: o MCP registra o que fez e não
-- consegue ler a trilha de ninguém, nem apagar a própria.
--
-- Por coluna, sem `id` e sem `ocorrido_em`: os dois saem do default (a
-- sequência e now()), e o MCP não consegue datar um evento no passado. As
-- colunas são as que auditoria.registrar() já grava.
GRANT INSERT (acao, canal, ator_tipo, ator_id, recurso, ip, detalhe, request_id)
    ON evento_auditoria TO sas_mcp;

-- O `id` é bigserial (0022): o default chama nextval(), que exige USAGE.
GRANT USAGE ON SEQUENCE evento_auditoria_id_seq TO sas_mcp;


-- ─── 4. O que o sas_mcp pode escrever na trilha ───────────────────────────
--
-- O GRANT por coluna fecha `id` e `ocorrido_em`, mas deixava o sas_mcp gravar
-- QUALQUER `acao`, `canal` e `ator_tipo` — e o modelo de ameaça da 0071 é um
-- MCP comprometido. Um MCP assim forjava `login_ok` no canal `acesso`, ou
-- `nota_editada`, em nome de qualquer coordenador, e a tela de auditoria os
-- lia iguais aos reais; um `detalhe` de 2 MB também passava (revisão de 24/10,
-- num Postgres descartável).
--
-- Daqui em diante, o que o sas_mcp grava é SEMPRE evento do MCP: canal `mcp`,
-- ator `coordenador`, e uma de DUAS ações — `mcp_ferramenta_chamada`, a única
-- que app/mcp/auditoria_mcp.registrar_chamada manda, e `mcp_verificacao_papeis`
-- SEM ator, a prova que scripts/verificar_papeis_do_mcp.py grava por aqui.
-- tests/test_migrations_do_mcp confere os dois lados. Tamanho com teto, coluna
-- a coluna: o evento real tem uns 200 bytes. `ip` e `request_id` vêm de FORA
-- (X-Forwarded-For, X-Request-Id), e o app os corta ANTES do INSERT
-- (auditoria_mcp.ip_da_trilha, observabilidade.request_id_aceito): passado um
-- teto, o gatilho recusa a linha inteira, e a chamada sairia sem rastro
-- (revisão final de 26/10).
--
-- Ação exata, e não o prefixo `mcp_` da primeira versão: com o prefixo, o
-- sas_mcp gravava também as ações que SÓ A API grava e que contam a história
-- do acesso — mcp_token_emitido, mcp_token_revogado, mcp_oauth_aprovado,
-- mcp_oauth_recusado. Ao contrário das leituras do MCP, elas aparecem na linha
-- do tempo PADRÃO da auditoria, iguais às reais: um MCP comprometido forjava "a
-- administradora X revogou a conexão Y" em nome de qualquer conta, com a
-- conexão viva (revisão final de 26/10, num Postgres descartável). E a
-- verificação sem ator: com ator, ela seria "a conta X verificou os papéis".
--
-- O que NÃO fecha: o `ator_id` da chamada de tool. Quem sabe de quem é o
-- token é o MCP; um MCP comprometido ainda atribui chamada a outra conta — e
-- essas ficam fora da linha do tempo padrão (auditoria.ACOES_SEM_ALTERACAO). E
-- o volume: o teto é por linha, não por minuto — o limite por minuto mora no
-- processo do MCP (servidor.LimitePorMinuto).
--
-- SECURITY INVOKER (o padrão): `current_user` é o papel de quem insere — o
-- sas_mcp, depois do SET ROLE do PostgREST. Para a API (sas_service) e para
-- as migrations, o gatilho não faz nada. EXECUTE em função de gatilho só é
-- conferido no CREATE TRIGGER, então revogar de PUBLIC não a desliga.

CREATE FUNCTION evento_auditoria_so_do_mcp()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF current_user <> 'sas_mcp' THEN
        RETURN NEW;
    END IF;
    IF NEW.canal IS DISTINCT FROM 'mcp'
       OR (NEW.acao IS DISTINCT FROM 'mcp_ferramenta_chamada'
           AND (NEW.acao IS DISTINCT FROM 'mcp_verificacao_papeis' OR NEW.ator_id IS NOT NULL))
       OR NEW.ator_tipo IS DISTINCT FROM 'coordenador'
       OR char_length(coalesce(NEW.ator_id, '')) > 64
       OR char_length(coalesce(NEW.recurso, '')) > 200
       OR char_length(coalesce(NEW.ip, '')) > 64
       OR char_length(coalesce(NEW.request_id, '')) > 128
       OR octet_length(coalesce(NEW.detalhe::text, '')) > 4096
    THEN
        RAISE EXCEPTION 'o sas_mcp só grava na trilha evento do próprio MCP (0072)'
            USING ERRCODE = 'insufficient_privilege',
                  HINT = 'canal mcp, acao mcp_ferramenta_chamada (ou mcp_verificacao_papeis sem ator), ator_tipo coordenador, detalhe até 4 KB';
    END IF;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION evento_auditoria_so_do_mcp() IS
    'Gatilho de evento_auditoria: o que o sas_mcp insere tem de ser evento do MCP (canal mcp, acao mcp_ferramenta_chamada ou mcp_verificacao_papeis sem ator, ator_tipo coordenador, com teto de tamanho). Não faz nada para outro papel (0072).';

CREATE TRIGGER trg_evento_auditoria_so_do_mcp
    BEFORE INSERT ON evento_auditoria
    FOR EACH ROW EXECUTE FUNCTION evento_auditoria_so_do_mcp();

REVOKE ALL ON FUNCTION evento_auditoria_so_do_mcp() FROM PUBLIC;

COMMIT;
