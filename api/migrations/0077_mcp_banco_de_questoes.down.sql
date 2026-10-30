-- Reverte a 0077: tira do sas_leitura o que ela deu, coluna por coluna, e só
-- isso. As colunas de `parametro_importancia` que a 0071 já dava (versao,
-- meia_vida_anos, janela_tendencia_anos, ativo) ficam: são as de
-- `recorrencia_no_banco`, e um REVOKE na tabela inteira levaria junto o índice
-- de importância do MCP para o valor de fábrica, sem erro nenhum
-- (importancia.carregar_parametro engole a falha).
--
-- Depois do down, `minhas_listas_do_banco` e `calibracao_da_importancia` voltam
-- 42501 no MCP: o código das tools tem de sair junto (ou sair do METADADOS).

BEGIN;

REVOKE SELECT (criado_em, criado_por) ON parametro_importancia FROM sas_leitura;
REVOKE SELECT (lista_id, questao_id, posicao) ON lista_questoes_item FROM sas_leitura;
REVOKE SELECT (id, titulo, dono_tipo, dono_id, criada_em, atualizada_em) ON lista_questoes FROM sas_leitura;

COMMIT;
