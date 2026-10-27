-- Reverte a 0073: tira as tabelas do OAuth do MCP e a FK que ela pôs em
-- token_mcp.
--
-- ⚠️ Derruba toda conexão OAuth. As linhas de token_mcp de origem 'oauth'
-- FICAM (a auditoria aponta para elas, e a 0072 manda nunca apagar), mas são
-- REVOGADAS aqui: sem as tabelas, o refresh já não teria onde ser conferido,
-- e o access de até uma hora que sobrasse seria acesso sem dono no OAuth. Quem
-- usa o conector aprova de novo depois de um `up`.
--
-- E perdem o `oauth_cliente_id`: o cliente some com a tabela, e um id que
-- aponta para o nada impediria o `up` seguinte de recriar a FK (visto num
-- Postgres descartável em 25/10). O nome do app continua em `nome`.
--
-- Pedidos, códigos, refresh e os e-mails das contas de IA somem com as
-- tabelas — inclusive o registro de quem aprovou o quê, e por qual e-mail. A
-- trilha disso continua em evento_auditoria (canal mcp), com o e-mail
-- mascarado. Depois de um `up`, cada coordenador cadastra o e-mail de novo.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`
-- (CLAUDE.md, armadilha 1).

BEGIN;

UPDATE token_mcp
   SET revogado_em      = coalesce(revogado_em, now()),
       oauth_cliente_id = NULL
 WHERE origem = 'oauth';

ALTER TABLE token_mcp DROP CONSTRAINT IF EXISTS token_mcp_oauth_cliente_fk;

-- Na ordem das FKs, sem CASCADE: se algo de fora ainda depender destas
-- tabelas, o down tem de falhar alto em vez de levar junto. O código por
-- e-mail aponta para o pedido e para o e-mail; o e-mail, só para a conta.
DROP TABLE IF EXISTS oauth_codigo_por_email_mcp;
DROP TABLE IF EXISTS oauth_refresh_mcp;
DROP TABLE IF EXISTS oauth_codigo_mcp;
DROP TABLE IF EXISTS oauth_pedido_mcp;
DROP TABLE IF EXISTS oauth_cliente_mcp;
DROP TABLE IF EXISTS email_conta_ia_mcp;

COMMIT;
