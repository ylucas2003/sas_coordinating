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
-- ⚠️ O GRANT é por coluna, NÃO POR LINHA. `lista_questoes` guarda as listas
-- dos dois lados (dono_tipo 'aluno' e 'coordenacao', CHECK da 0029), e o
-- sas_mcp passa a poder ler as dos alunos também. Nenhuma tool as lê: o lado é
-- fixo na tool ('coordenacao') e a pessoa vem da SESSÃO — o registro injeta o
-- `coordenador_id` (chat/ferramentas.py, `_IDENTIDADE_DA_COORDENACAO`), que
-- nenhum schema declara e o modelo não escolhe. A trava por linha seria RLS, e
-- ela fica fora de propósito: ligaria a segurança por linha também para o
-- sas_service da API, que não é dono da tabela, e a política teria de citar o
-- papel do MCP — forma que a auditoria das migrations recusa
-- (scripts/verificar_papeis_do_mcp.py). O que fica ao alcance do PAPEL numa
-- lista de aluno é o título, o `dono_id` (que cruza com `aluno`, também na
-- lista branca) e quais questões ele separou; anotação e resposta moram em
-- `questao_estudo_aluno`, que continua proibida. Medido num Postgres
-- descartável em 30/10: o `SET ROLE sas_mcp` lê a linha, e a tool responde o
-- mesmo "não existe" de uma lista inexistente. A camada que segura isto é a do
-- código, não a do papel, ao contrário do resto da lista branca: é decisão a
-- rever se um dia o MCP ganhar outra porta além das tools do registro.
--
-- ⚠️ Depois de aplicar: nada a reiniciar. GRANT vale na hora — o Postgres
-- confere privilégio a cada consulta —, e as três tabelas já existiam (0029,
-- 0044), então o cache de schema do postgrest_mcp já as conhece. Rodar
-- `scripts/verificar_papeis_do_mcp.py --ferramentas` contra o postgrest_mcp.

BEGIN;

-- lista_questoes · minhas_listas_do_banco (listas.listar e
-- listas._linha_da_lista: _COLUNAS_LISTA; dono_tipo e dono_id são filtro,
-- atualizada_em é ordem). dono_id é o uuid da conta da coordenação — o `sub`,
-- não e-mail —, e a tool não o devolve. São todas as colunas da tabela; vão
-- por coluna pela regra da 0071 (coluna nova nasce invisível).
GRANT SELECT (id, titulo, dono_tipo, dono_id, criada_em, atualizada_em)
    ON lista_questoes TO sas_leitura;

-- lista_questoes_item · minhas_listas_do_banco (listas.listar conta os itens
-- por lista_id; listas._ordem_dos_itens lê questao_id e posicao, com lista_id
-- de filtro e posicao de ordem). As questões da lista vêm depois de
-- questao_vestibular, pela 0071.
GRANT SELECT (lista_id, questao_id, posicao)
    ON lista_questoes_item TO sas_leitura;

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
