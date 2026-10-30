-- 0077 · O banco de questões inteiro no MCP da coordenação (docs/43 §5.2)
--
-- A decisão da coordenação de 30/10: tudo o que ela lê na plataforma a IA
-- conectada ao MCP lê também. Para o banco de questões, isso é a aba Banco da
-- coordenação (`web/src/telas/Banco/`: questões, estatísticas e Minha lista)
-- e a tela de Calibração, que viraram quatro tools novas em
-- `app/chat/tools/banco_questoes.py`, todas só de leitura:
--
--   abrir_questao_do_banco     o cartão inteiro — consultas.obter_questao
--   panorama_do_banco          o acervo por matéria × vestibular × ano —
--                              estatisticas.panorama
--   calibracao_da_importancia  a meia-vida em vigor e o histórico —
--                              importancia.calibracao_em_vigor
--   minhas_listas_do_banco     as listas da conta conectada —
--                              listas.listar e listas.obter
--
-- Fica de fora o que é do ALUNO: o estudo (`questao_estudo_aluno`, que está em
-- TABELAS_PROIBIDAS do verificador), o progresso e a aba Mensagem, que nem
-- dado tem.
--
-- O QUE A 0071 JÁ COBRIA, e por isso não se repete aqui: as duas primeiras
-- tools leem só o que as três do banco já liam. O cartão é `_COLUNAS_QUESTAO`
-- inteiro — a resolução (resolucao_url, resolucao_md, resolucao_origem), o
-- endereço da figura (imagem_url, usa_imagem_no_render, extraido_por), a
-- confiança do gabarito e a do classificador (questao_vestibular_topico.
-- confianca e observacao) — e a 0071 já dava tudo isso, porque o select do
-- domínio era o mesmo; até 30/10 a tool só não os DEVOLVIA. O panorama lê um
-- subconjunto dessas colunas e a ligação (questao_id, materia).
--
-- O QUE ENTRA, a mesma regra da 0071 — POR COLUNA, uma tabela por GRANT, com
-- quem a lê; "filtro" e "ordem" marcam coluna que a tool não devolve mas que o
-- comando cita (o Postgres exige SELECT em toda coluna citada).
--
-- AS LISTAS ENTRAM POR VIEW, E NÃO POR TABELA (decisão de 30/10). `lista_questoes`
-- guarda os dois lados (dono_tipo 'aluno' e 'coordenacao', CHECK da 0029), e
-- GRANT é por coluna, nunca por linha: dado na tabela, ele punha ao alcance do
-- papel o título e as questões de cada lista de aluno, que nenhuma tool lê. As
-- duas views daqui só têm o lado da coordenação, e as duas tabelas de baixo
-- continuam dando 42501 ao sas_mcp (estão em TABELAS_PROIBIDAS do verificador).
-- Quem segura a linha passa a ser o PAPEL, como no resto da lista branca. RLS
-- ficou de fora: ligaria a segurança por linha também para o sas_service, e a
-- política teria de citar papel do MCP, forma que a auditoria recusa.
--
-- Três coisas, nas duas views, que não são detalhe:
--
--   * NÃO são `security_invoker`, de propósito: rodam com o privilégio do DONO
--     (o `postgres`, que aplica as migrations), porque o sas_mcp não tem acesso
--     às tabelas. É o caso que a 0071 proíbe para toda outra view — a que roda
--     como dono expõe o que lê —, e por isso estas entram por nome
--     (VIEWS_DO_MCP) e o corpo delas é travado por teste: elas expõem só o que
--     o WHERE deixa.
--   * SÃO `security_barrier`. Sem a barreira, o planejador pode rodar um filtro
--     vindo de fora ANTES do WHERE da view, e uma função que vaze o argumento vê
--     a linha do aluno. Medido num Postgres descartável em 30/10: com a tabela
--     cheia de listas da coordenação, o plano sai assim sozinho. O sas_mcp não
--     cria função, então é a segunda camada, e sai barata: uuid e texto têm
--     igualdade `leakproof`, e o `dono_id = …` da tool segue usando o índice.
--   * ⚠️ `CREATE OR REPLACE VIEW` sem o `WITH` ZERA as opções, e a barreira sai
--     em silêncio, com o GRANT intacto (provado no mesmo Postgres). Quem recriar
--     uma delas repete o `WITH`; a auditoria recusa a que nascer sem ele
--     (`_auditar_view`), e ALTER nenhum as toca.
--
-- O `sas_service` lê as duas sem GRANT aqui: a API também lê por elas (ver
-- abaixo), e o ALTER DEFAULT PRIVILEGES do init lhe dá ALL em toda tabela e view
-- que o `postgres` criar, como em tudo desde a 0001. Conferido em 30/10.
--
-- A ROTA DA TELA LÊ PELAS MESMAS VIEWS: `banco/listas.py` é uma função só para a
-- rota e para a tool, e o lado da coordenação lê sempre pela view (o do aluno
-- segue na tabela, e a escrita dos dois também). Consequência para o deploy: com
-- o código novo, a aba Minha lista da coordenação DEPENDE desta migration.
--
-- Depois de aplicar, o restart de sempre (CLAUDE.md, armadilha 1), que o deploy.sh
-- já faz nos dois PostgREST. Medido em 30/10 no v12.2.3: a view só entra no cache
-- de schema (a OpenAPI) com o restart, mas o SELECT sem embed, que é o que
-- `listas.py` faz, não depende dele: a tool e as rotas responderam com o cache
-- velho. O que protege a tela é a ORDEM: sem a view, a leitura dá 404 (42P01), e o
-- deploy aplica a migration antes do `up -d`. O verificador lê a OpenAPI: rode
-- `scripts/verificar_papeis_do_mcp.py --ferramentas` só depois do restart.

BEGIN;

-- Sem `dono_tipo = 'aluno'`, por construção. A coluna fica porque o domínio é um
-- só para os dois lados: `_COLUNAS_LISTA` a seleciona e todo filtro de dono a cita.
CREATE VIEW lista_questoes_da_coordenacao WITH (security_barrier = true) AS
SELECT l.id, l.titulo, l.dono_tipo, l.dono_id, l.criada_em, l.atualizada_em
  FROM lista_questoes AS l
 WHERE l.dono_tipo = 'coordenacao';

-- Semi-join, e não JOIN: a view continua atualizável, e a escrita do sas_mcp é
-- recusada pelo privilégio (42501), que é o que o verificador confere. Com JOIN o
-- Postgres recusaria antes, na reescrita, com 55000.
CREATE VIEW lista_questoes_item_da_coordenacao WITH (security_barrier = true) AS
SELECT i.lista_id, i.questao_id, i.posicao
  FROM lista_questoes_item AS i
 WHERE i.lista_id IN (SELECT l.id FROM lista_questoes AS l WHERE l.dono_tipo = 'coordenacao');

COMMENT ON VIEW lista_questoes_da_coordenacao IS
    'As listas do banco de questões, só o lado da coordenação (0077). Roda como o dono, de propósito: é por ela que o MCP as lê, sem acesso à tabela. A API também lê por ela. Recriar com CREATE OR REPLACE exige repetir o WITH.';
COMMENT ON VIEW lista_questoes_item_da_coordenacao IS
    'Os itens das listas da coordenação (0077): a mesma fronteira de lista_questoes_da_coordenacao. Recriar com CREATE OR REPLACE exige repetir o WITH.';

-- lista_questoes_da_coordenacao · minhas_listas_do_banco (listas.listar e
-- listas._linha_da_lista: _COLUNAS_LISTA; dono_tipo e dono_id são filtro,
-- atualizada_em é ordem). dono_id é o uuid da conta da coordenação — o `sub`,
-- não e-mail —, e a tool não o devolve.
GRANT SELECT (id, titulo, dono_tipo, dono_id, criada_em, atualizada_em)
    ON lista_questoes_da_coordenacao TO sas_leitura;

-- lista_questoes_item_da_coordenacao · minhas_listas_do_banco (listas.listar
-- conta os itens por lista_id; listas._ordem_dos_itens lê questao_id e posicao,
-- com lista_id de filtro e posicao de ordem). As questões da lista vêm depois de
-- questao_vestibular, pela 0071.
GRANT SELECT (lista_id, questao_id, posicao)
    ON lista_questoes_item_da_coordenacao TO sas_leitura;

-- parametro_importancia · calibracao_da_importancia (importancia.historico).
-- A 0071 deixou de fora `criado_por`, o NOME de quem da coordenação girou o
-- botão (routes/banco.py grava coordenador["nome"]), porque nenhuma tool o
-- lia. Agora uma lê: é a coluna "Quem" da tela de Calibração, que todo
-- coordenador vê (`/calibracao`, sem `SoAdministrador`). Nome de pessoa da
-- coordenação, não de aluno, e não e-mail. `criado_em` é a coluna "Quando".
-- FORA: `id`, que ninguém lê.
GRANT SELECT (criado_em, criado_por)
    ON parametro_importancia TO sas_leitura;

COMMIT;
