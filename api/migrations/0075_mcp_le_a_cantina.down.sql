-- Reverte a 0075: a cantina volta a ficar fora do que o MCP lê, e a restrição
-- alimentar sai da lista branca.
--
-- REVOKE por coluna, tabela a tabela, e não `REVOKE ALL`: em `aluno` o papel
-- continua lendo as colunas da 0071, e as demais tabelas podem ter ganhado
-- GRANT de outra frente depois desta.
--
-- ⚠️ Antes de aplicar, tire as tools do catálogo (o METADADOS de
-- chat/tools/cantina.py), senão as sete passam a voltar 42501. O REVOKE vale na
-- consulta seguinte, sem restart do PostgREST.

BEGIN;

REVOKE SELECT (restricao_alimentar)
    ON aluno FROM sas_leitura;

REVOKE SELECT (pedido_id, opcao_id)
    ON pedido_refeicao_item FROM sas_leitura;

REVOKE SELECT (id, cardapio_id, aluno_id, data, refeicao, modo, criado_em, retirado_em,
               valor_cobrado)
    ON pedido_refeicao FROM sas_leitura;

REVOKE SELECT (aluno_id, refeicao)
    ON direito_refeicao_aluno FROM sas_leitura;

REVOKE SELECT (id, bloco_id, nome, ordem, disponivel)
    ON cardapio_opcao FROM sas_leitura;

REVOKE SELECT (id, cardapio_id, nome, ordem, escolhas_minimas, escolhas_maximas, observacao)
    ON cardapio_bloco FROM sas_leitura;

REVOKE SELECT (id, cantina_id, data, refeicao, pedidos_ate, publicado_em, sem_refeicao,
               aceita_pedido, aceita_presencial)
    ON cardapio FROM sas_leitura;

REVOKE SELECT (id, nome, ativo, prazo_padrao_dias_antes, prazo_padrao_hora,
               valor_almoco, valor_janta, aceita_pedido_almoco, aceita_pedido_janta,
               aceita_presencial_almoco, aceita_presencial_janta)
    ON cantina FROM sas_leitura;

-- O texto da 0049, como estava.
COMMENT ON COLUMN aluno.restricao_alimentar IS
    'Restrição alimentar em texto livre, preenchida pela COORDENAÇÃO. Aparece para a cantina ao lado do pedido, e em lugar nenhum mais — não entra em ficha, painel, dossiê nem chat (docs/38 §2.6).';

COMMIT;
