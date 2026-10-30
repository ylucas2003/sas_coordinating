-- Reverte a 0077: derruba as duas views e tira do sas_leitura o que ela deu em
-- `parametro_importancia`, coluna por coluna. As colunas de lá que a 0071 já dava
-- (versao, meia_vida_anos, janela_tendencia_anos, ativo) ficam: são as de
-- `recorrencia_no_banco`, e um REVOKE na tabela inteira levaria o índice de
-- importância do MCP para o valor de fábrica, sem erro nenhum
-- (importancia.carregar_parametro engole a falha). O GRANT das views morre com
-- elas.
--
-- ⚠️ O CÓDIGO VOLTA PRIMEIRO. `banco/listas.py` lê o lado da coordenação por estas
-- views, na tool E NA ROTA: com o código novo no ar, o down quebra a aba Minha
-- lista da coordenação, além de `minhas_listas_do_banco` e
-- `calibracao_da_importancia` no MCP. Depois de aplicar: `docker compose restart
-- postgrest postgrest_mcp` (CLAUDE.md, armadilha 1).

BEGIN;

REVOKE SELECT (criado_em, criado_por) ON parametro_importancia FROM sas_leitura;
DROP VIEW IF EXISTS lista_questoes_item_da_coordenacao;
DROP VIEW IF EXISTS lista_questoes_da_coordenacao;

COMMIT;
