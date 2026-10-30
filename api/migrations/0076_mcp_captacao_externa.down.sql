-- Reverte a 0076: a captação externa sai da lista branca do MCP, e a view do
-- rodapé volta a rodar com o privilégio do dono, como a 0063 a deixou.
--
-- Coluna por coluna, o espelho exato do up: tira só o que a 0076 deu, sem
-- tocar no resto do que o sas_leitura lê. A ordem é a inversa da do up: o GRANT
-- na view sai antes de ela voltar a rodar com o privilégio do dono.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`
-- (CLAUDE.md, armadilha 1). Com as tools da captação ainda no código e
-- `expor_no_mcp=True`, elas passam a voltar 42501 pelo MCP — reverter a
-- migration é reverter também `app/chat/tools/captacao.py`.

BEGIN;

REVOKE SELECT (nome, categoria, ano_min, ano_max, conquistas_total)
    ON v_prova_externa_resumo FROM sas_leitura;

REVOKE SELECT (nome_normalizado, nome, escolas, cidades, ufs, status_captacao,
               conquistas_total, provas_distintas, participacoes, perfis_no_grupo,
               ano_mais_recente, criado_em, atualizado_em)
    ON v_candidato_externo_por_nome FROM sas_leitura;

REVOKE SELECT (id, candidato_id, prova_id, ano, nivel_texto, resultado, faixa,
               escola_informada, cidade_informada, uf_informada, notas_por_materia,
               fonte_url, ano_conclusao_min, ano_conclusao_max)
    ON conquista_externa FROM sas_leitura;

REVOKE SELECT (id, nome, nome_normalizado, escola, cidade, uf, serie_referencia_min,
               serie_referencia_max, ano_referencia_serie, status_captacao, criado_em)
    ON candidato_externo FROM sas_leitura;

REVOKE SELECT (id, nome, categoria)
    ON prova_externa FROM sas_leitura;

ALTER VIEW v_prova_externa_resumo RESET (security_invoker);

COMMIT;
