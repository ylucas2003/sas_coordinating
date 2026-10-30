-- Reverte a 0074: o MCP volta a não ler régua (os nomes de quem a criou),
-- rotinas nem trilha. As sete tools voltam a dar 42501 pelo postgrest_mcp —
-- antes do down, devolva `expor_no_mcp` a False no METADADOS de
-- chat/tools/reguas.py, rotinas.py e trilha.py, senão o MCP as anuncia e
-- cada chamada falha.
--
-- REVOKE por coluna nas tabelas que a 0071 já concedia (simulado, ciclo,
-- nota): só as colunas DESTA migration saem, e as da 0071 ficam. Nas tabelas
-- que só a 0074 abriu, o REVOKE por coluna leva tudo o que ela deu. As views
-- saem com DROP, que leva o GRANT junto.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`
-- (CLAUDE.md, armadilha 1) — e as tools do CHAT também leem as três views:
-- reverter o banco sem reverter o código quebra `historico_de_alteracoes`,
-- `reguas_de_corte` (o detalhe de régua criada) e `estado_das_gravacoes` no
-- app.

BEGIN;

REVOKE SELECT (pontuacao_sas, pontuacao_canvas) ON nota FROM sas_leitura;
REVOKE SELECT (canvas_estado, canvas_erro) ON ciclo FROM sas_leitura;
REVOKE SELECT (origem, canvas_estado, canvas_tentativas, canvas_erro, evento_agenda_id) ON simulado FROM sas_leitura;
REVOKE SELECT (id, evento_agenda_id, destinatario_tipo, dias_antes, cancelada_em) ON regra_lembrete FROM sas_leitura;
REVOKE SELECT (id, titulo, data_evento, hora_evento, cancelado_em) ON evento_agenda FROM sas_leitura;
REVOKE SELECT (id, chave_idempotencia, estado, enviar_em, enviado_em, tentativas, atualizado_em) ON disparo FROM sas_leitura;
REVOKE SELECT (id, tipo, status, iniciado_em, finalizado_em, resumo, erro_mensagem) ON canvas_sync_execucao FROM sas_leitura;
REVOKE SELECT (curso_id, nome, ativo, publicar_no_canvas) ON curso_monitorado_gravacao FROM sas_leitura;

DROP VIEW IF EXISTS aula_gravacao_para_ia;
DROP VIEW IF EXISTS nome_da_coordenacao;
DROP VIEW IF EXISTS trilha_de_alteracoes;

COMMIT;
