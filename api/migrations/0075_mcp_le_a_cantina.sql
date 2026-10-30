-- 0075 · O MCP passa a ler a cantina (docs/43 §5, decisão de 30/10/2026)
--
-- A decisão da coordenação de 30/10: TUDO o que ela lê na plataforma a IA dela lê
-- também, pelo MCP. Até aqui a cantina estava na lista do que fica de fora
-- (0071), e não havia tool nenhuma dela, nem no chat. As sete tools nasceram em
-- app/chat/tools/cantina.py, e a regra é a de app/cantina_leitura.py e
-- app/cantina_relatorio.py, que as rotas também chamam.
--
-- O GRANT segue a régua da 0071, por coluna e nada além do que as tools leem,
-- seguindo cada handler até o PostgREST: embed e filtro contam, porque o
-- Postgres exige SELECT em toda coluna citada no comando, não só nas devolvidas.
--
-- ⚠️ `select=*` numa tabela com GRANT por coluna dá 42501. Por isso o domínio
-- escreve as colunas por extenso nos selects que as tools alcançam
-- (cantina_leitura.COLUNAS_*): nenhum deles usa `*`. `_cantina_por_id`,
-- `_cardapio_da_cantina` e os demais `select("*")` que sobraram na rota são da
-- API, pelo sas_service, e as tools não passam por eles.
--
-- Sem restart do PostgREST: esta migration só dá GRANT e troca um COMMENT, e
-- GRANT vale na consulta seguinte (o Postgres confere privilégio a cada
-- comando). Provado num Postgres descartável em 30/10: aplicada com o
-- postgrest_mcp de pé, as tabelas e os embeds responderam 200 sem reiniciar. A
-- armadilha 1 do CLAUDE.md é de tabela e coluna NOVAS, e aqui não há nenhuma.
--
-- O QUE FICA DE FORA, de propósito:
--
--   * `usuario_cantina`: conta de acesso, com e-mail, último login e senha_hash.
--     Continua em TABELAS_PROIBIDAS, e é a única diferença entre o que
--     /cantina/acesso mostra e o que a tool `cantinas_e_regras` devolve;
--   * as duas VIEWS, `v_pedidos_por_cardapio` e `v_contagem_pedidos_por_opcao`:
--     nenhuma view do schema usa security_invoker, elas rodam com o privilégio
--     do dono, e um GRANT nelas exporia tudo o que leem (0071). O MCP faz a
--     MESMA conta a partir das tabelas de base (cantina_leitura.contar_pelos_pedidos
--     e contagem_por_opcao_pelos_itens), numa janela que a tool limita;
--   * o token do QR de retirada (`cantina_token.py`): é assinado na hora com o
--     segredo da API, que o MCP não tem, e não existe tabela de tokens;
--   * dado de pagamento: não existe no SAS. `valor_cobrado` é o preço de tabela
--     carimbado no pedido (0054), e o próprio COMMENT dele diz que não é cobrança.

BEGIN;

-- cantina · cantinas_e_regras (a regra da casa) e, por `cantina_leitura.cantinas`
-- e `ids_das_cantinas_ativas`, o recorte de calendario_da_cantina,
-- cardapio_da_cantina e pedidos_da_refeicao (`ativo`: filtro); custos_da_cantina
-- lê (id, nome). FORA: `criado_em`, que tela nenhuma lê.
GRANT SELECT (id, nome, ativo, prazo_padrao_dias_antes, prazo_padrao_hora,
              valor_almoco, valor_janta, aceita_pedido_almoco, aceita_pedido_janta,
              aceita_presencial_almoco, aceita_presencial_janta)
    ON cantina TO sas_leitura;

-- cardapio · calendario_da_cantina, cardapio_da_cantina, pedidos_da_refeicao e
-- custos_da_cantina (cantina_id e data: filtro). FORA: `criado_por`, o uuid da
-- CONTA da cantina que lançou — dela só o estabelecimento sai —, `criado_em` e
-- `atualizado_em`.
GRANT SELECT (id, cantina_id, data, refeicao, pedidos_ate, publicado_em, sem_refeicao,
              aceita_pedido, aceita_presencial)
    ON cardapio TO sas_leitura;

-- cardapio_bloco · cardapio_da_cantina e pedidos_da_refeicao (cardapio_id:
-- filtro). Todas as colunas: nada aqui é de pessoa.
GRANT SELECT (id, cardapio_id, nome, ordem, escolhas_minimas, escolhas_maximas, observacao)
    ON cardapio_bloco TO sas_leitura;

-- cardapio_opcao · as mesmas, pelo embed cardapio_opcao(...) a partir do bloco
-- (bloco_id: FK do embed). Todas as colunas.
GRANT SELECT (id, bloco_id, nome, ordem, disponivel)
    ON cardapio_opcao TO sas_leitura;

-- direito_refeicao_aluno · direitos_a_refeicao e restricoes_alimentares.
GRANT SELECT (aluno_id, refeicao)
    ON direito_refeicao_aluno TO sas_leitura;

-- pedido_refeicao · calendario_da_cantina (cardapio_id, modo: a contagem que as
-- rotas leem da view), pedidos_da_refeicao (a lista, com o embed aluno(...), e
-- retirado_em no placar do presencial), custos_da_cantina (valor_cobrado, data e
-- refeicao: a soma de cantina_relatorio._ler) e restricoes_alimentares (data e
-- refeicao: filtro de quem vai comer). FORA: `atualizado_em`, que nenhuma lê.
GRANT SELECT (id, cardapio_id, aluno_id, data, refeicao, modo, criado_em, retirado_em,
              valor_cobrado)
    ON pedido_refeicao TO sas_leitura;

-- pedido_refeicao_item · pedidos_da_refeicao: as escolhas de cada aluno e a
-- contagem por opção.
GRANT SELECT (pedido_id, opcao_id)
    ON pedido_refeicao_item TO sas_leitura;

-- aluno.restricao_alimentar · restricoes_alimentares, e SÓ ela.
--
-- ⚠️ DADO DE SAÚDE DE MENOR (LGPD art. 11, e art. 14). A 0071 a deixou fora por
-- decisão de 24/10; a decisão da coordenação de 30/10 a põe dentro, em GRANT
-- próprio e em tool própria, para poder sair sozinha. As outras tools da
-- cantina nem leem a coluna (`com_restricao=False`, o padrão do domínio).
--
-- Para desligar: `"expor_no_mcp": False` no METADADOS de chat/tools/cantina.py
-- tira a tool do catálogo, e o `REVOKE SELECT (restricao_alimentar) ON aluno FROM
-- sas_leitura` numa migration nova tira a leitura do papel. Só o METADADOS não
-- basta para dizer que o dado não sai: o GRANT continuaria valendo.
GRANT SELECT (restricao_alimentar)
    ON aluno TO sas_leitura;

-- O COMMENT da 0049 dizia "em lugar nenhum mais", e deixaria de ser verdade.
COMMENT ON COLUMN aluno.restricao_alimentar IS
    'Restrição alimentar em texto livre, preenchida pela COORDENAÇÃO. Dado de SAÚDE de menor (LGPD art. 11). Aparece para a cantina ao lado do pedido, na tela de direitos da coordenação sob clique e, desde a decisão de 30/10/2026, na tool restricoes_alimentares, e só nela (migration 0075). Não entra em ficha, painel nem dossiê (docs/38 §2.6).';

COMMIT;
