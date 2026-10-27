-- 0071 · Os papéis do MCP da coordenação (docs/43 §5.2, Fase 2)
--
-- O MCP liga a IA de FORA da escola (Claude, ChatGPT) aos dados do SAS. Ele
-- não pode herdar o acesso da API: o papel anônimo do PostgREST da API é o
-- `sas_service`, com ALL em tudo (infra/postgres/init/01-papeis.sh). A
-- decisão de 24/10 é dar ao MCP um PostgREST PRÓPRIO (`postgrest_mcp` no
-- compose) cujo papel anônimo é o `sas_mcp` daqui, SEM `PGRST_JWT_SECRET`.
-- Sem segredo, o PostgREST recusa todo Bearer (PGRST300) e nenhum token troca
-- o papel.
--
-- E com LOGIN PRÓPRIO (revisão de 24/10). Na primeira versão o postgrest_mcp
-- entrava com o mesmo `authenticator` da API, que é membro do `sas_service`:
--   * a config do PostgREST guardada no banco (`pgrst.*` no papel de login,
--     lida por padrão e POR CIMA do env) valia para os DOIS — um
--     `ALTER ROLE authenticator SET pgrst.db_anon_role = 'sas_service'` dava
--     ao MCP a senha_hash da coordenação sem token nenhum, e um
--     `pgrst.jwt_secret` ali deixava passar um JWT com role=sas_service
--     (provado num Postgres descartável);
--   * SQL arbitrário numa requisição do MCP — injeção no PostgREST, função com
--     SQL dinâmico — podia fazer `SET ROLE sas_service`: o Postgres confere o
--     SET ROLE contra o papel da SESSÃO, e a sessão era do authenticator.
-- Com o `autenticador_mcp`, membro SÓ do sas_mcp, as duas portas fecham no
-- Postgres e não numa opção do PostgREST: ele não alcança o sas_service por
-- cadeia nenhuma, e a config no banco dele só pode apontar para papel que ele
-- já alcança. Provado num Postgres descartável em 25/10: SET ROLE e
-- set_config('role') por RPC, `pgrst.db_anon_role` e `pgrst.jwt_secret` no
-- papel de login com a config do PostgREST LIGADA — "permission denied to set
-- role" em todos, onde o login antigo lia as contas da coordenação. O compose
-- ainda liga `PGRST_DB_CONFIG=false`: é a segunda camada, não a única.
--
-- A SENHA do autenticador_mcp não mora aqui: o arquivo vai para o git. A
-- migration o cria com `PASSWORD NULL` — ninguém entra até alguém definir — e
-- quem define é a operação, com o valor de POSTGREST_MCP_PASSWORD, o mesmo
-- que o PGRST_DB_URI do postgrest_mcp lê (o comando está no docker-compose.yml
-- da raiz). Um papel que já existia volta a NULL: senha de origem desconhecida
-- não vale.
--
-- Três papéis:
--
--   sas_leitura       NOLOGIN. SELECT na lista branca abaixo, e nada mais. É o
--                     "ler sem escrever" reaproveitável por qualquer leitor
--                     externo futuro.
--   sas_mcp           NOLOGIN. O papel efetivo do MCP: membro de sas_leitura,
--                     mais o estreito que só o MCP precisa e que vem na 0072 —
--                     INSERT na auditoria e EXECUTE em mcp_conferir_token.
--   autenticador_mcp  O LOGIN do postgrest_mcp, como o `authenticator` é o do
--                     PostgREST da API: NOINHERIT, sem privilégio nenhum por si
--                     só, membro de sas_mcp só para o SET ROLE de cada
--                     requisição. Com teto de conexões e de duração de comando
--                     (abaixo).
--
-- A LISTA BRANCA é exatamente o que as 31 tools expostas no MCP leem — as 24
-- marcadas 'expor' ou 'expor_com_pseudonimo' no levantamento de LGPD de
-- 24/10, mais `relatorio_ciclo` e as quatro da Fase 2:
-- `buscar_aluno_por_matricula` e as três do banco de questões
-- (`topicos_do_edital`, `buscar_questoes_do_banco`, `recorrencia_no_banco`,
-- que leem por banco/consultas.py e banco/estatisticas.py), e as duas que
-- entraram em 26/10, quando o dono decidiu que o MCP mostra o NOME do aluno
-- (app/mcp/configuracao.py): `buscar_aluno_por_nome` e `listar_alertas` —
-- seguindo cada handler até o PostgREST, domínio, embed e filtro incluídos. Embed e filtro
-- contam: o PostgREST monta o join com a FK da tabela de fora e a PK da de
-- dentro, e o Postgres exige SELECT em toda coluna citada no comando, não só
-- nas devolvidas.
--
-- O GRANT é POR COLUNA em TODAS as tabelas, não só em `aluno`. Três motivos:
--   * "nem mais": as tabelas de negócio carregam coluna que nenhuma tool lê e
--     que não tem por que sair do SAS — quem corrigiu a nota
--     (nota.grader_canvas_user_id, nota.editada_por), o último acesso do aluno
--     ao Canvas (matricula_turma.last_activity_at), a alternativa que cada um
--     marcou (questao_resposta_aluno.alternativa_id), texto livre e erro de
--     integração (simulado.motivo_zero_e_ausencia, simulado.canvas_erro);
--   * coluna nova nasce invisível ao MCP, como tabela nova (falha fechada):
--     uma `observacao` acrescentada amanhã a `aluno` não vaza sozinha;
--   * a régua fica uma só — "o que o MCP lê está escrito aqui, coluna por
--     coluna" — e scripts/verificar_papeis_do_mcp.py confere o banco contra
--     ESTE arquivo.
-- O custo é conhecido: tool exposta que passar a ler coluna nova precisa de
-- GRANT numa migration nova, senão a chamada volta 42501 (o registro a
-- devolve ao modelo como falha genérica — docs/43 §3.2, invariante 6). O
-- `verificar_papeis_do_mcp.py --ferramentas` roda as expostas e pega isso.
-- Pior que o 42501 são os dois leitores que ENGOLEM a falha e seguem com o
-- valor de fábrica — criterios_repo._linhas_ativas e
-- importancia.carregar_parametro: lá, GRANT faltando não dá erro, dá número
-- calculado com a régua ou a meia-vida erradas. O verificador lê as duas
-- tabelas direto e, nas tools, conta como falha o warning que traz 42501.
--
-- ⚠️ `select=*` numa tabela com GRANT por coluna dá 42501. Nenhuma das 31
-- usa, nem o domínio que elas chamam (conferido em 24/10 e, para as duas de
-- 26/10, nesse dia); tool nova no MCP lista as colunas.
--
-- O QUE FICA DE FORA, de propósito: credencial (usuario_coordenacao,
-- usuario_cantina, token_mcp, e o OAuth e os e-mails das contas de IA da
-- 0073), conversa (chat_*), trilha (evento_auditoria — o MCP só GRAVA nela,
-- 0072), disparo de e-mail, cantina, captação, upload, sync do Canvas,
-- gravações e toda VIEW. Nenhuma view do schema usa security_invoker: elas
-- rodam com o privilégio do dono, então GRANT numa view expõe tudo o que ela
-- lê, mesmo sem GRANT nas tabelas de baixo. Nenhuma das 31 lê view.
--
-- SEM `ALTER DEFAULT PRIVILEGES` para estes papéis: tabela nova nasce
-- invisível ao MCP. A regra para quem vier depois: tabela de negócio que uma
-- tool exposta lê ganha o GRANT (por coluna) na própria migration — e view
-- materializada derrubada e recriada perde o GRANT a cada recriação (foi o
-- caso de v_candidato_externo_por_nome na 0065 e na 0068).
--
-- FUNÇÃO é o caminho inverso: o Postgres dá EXECUTE a PUBLIC — e portanto ao
-- sas_mcp — em toda função criada. Função SECURITY DEFINER nova revoga de
-- PUBLIC na própria migration (a §3 abaixo faz isso com a da captação), e
-- DROP + CREATE devolve o EXECUTE a PUBLIC, ao contrário de CREATE OR
-- REPLACE. tests/test_migrations_do_mcp.py confere as duas coisas.
--
-- ⚠️ Depois de aplicar: definir a senha do autenticador_mcp (acima) e
-- `docker compose restart postgrest postgrest_mcp` (CLAUDE.md, armadilha 1).
-- GRANT e REVOKE valem na hora — o Postgres confere privilégio a cada
-- consulta —, mas a 0072 cria tabela e função, que o cache de schema só vê
-- depois do restart.

BEGIN;

-- ─── 1. Os papéis ─────────────────────────────────────────────────────────
--
-- Papel é GLOBAL no cluster, não do banco: o IF NOT EXISTS evita o erro num
-- cluster onde ele já exista (outro banco, um `down` que parou no meio). Os
-- três nascem NOLOGIN; o login do autenticador_mcp vem no ALTER logo abaixo,
-- à vista da auditoria das migrations, e não dentro do corpo $$.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sas_leitura') THEN
        CREATE ROLE sas_leitura NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sas_mcp') THEN
        CREATE ROLE sas_mcp NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'autenticador_mcp') THEN
        CREATE ROLE autenticador_mcp NOLOGIN;
    END IF;
END
$$;

-- E se já existiam, passam a ser o que este arquivo diz. Num banco novo nada
-- daqui até a lista branca faz efeito; num papel que já existia, desfaz o que
-- foi dado por fora — por ordem de estrago:
--
--   * atributo: um papel herdado com LOGIN, ou com poder de cluster, desfaria
--     a premissa inteira. INHERIT no sas_mcp é o que o faz receber os SELECT
--     do sas_leitura; NOINHERIT no autenticador_mcp, o que o deixa sem
--     privilégio próprio (ele só troca de papel). CONNECTION LIMIT: um
--     postgrest_mcp comprometido, que tem a senha, não esgota o
--     max_connections do Postgres que a API divide — o pool é de 3, mais a
--     conexão do LISTEN (docker-compose.yml);
ALTER ROLE sas_leitura      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE sas_mcp          NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT;
ALTER ROLE autenticador_mcp LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
                            CONNECTION LIMIT 10 PASSWORD NULL;

--   * config do papel (`ALTER ROLE … SET`), em todo banco do cluster — no
--     autenticador_mcp, é onde o PostgREST procuraria `pgrst.*`;
ALTER ROLE sas_leitura      RESET ALL;
ALTER ROLE sas_mcp          RESET ALL;
ALTER ROLE autenticador_mcp RESET ALL;

--   * PERTENCIMENTO: o REVOKE de objeto abaixo não tira papel de dentro de
--     papel, e um sas_mcp que já fosse membro do sas_service (ou do
--     pg_read_all_data) seguiria lendo e escrevendo tudo — a migration
--     aplicava "ok" e o MCP lia usuario_coordenacao.senha_hash (provado em
--     24/10). Sai todo pertencimento que toque os três, nos dois sentidos — de
--     que eles são membros e quem é membro deles (o `GRANT sas_mcp TO
--     authenticator` da primeira versão da 0071 sai por aqui) —, e os dois
--     certos voltam logo abaixo. Fica o de quem roda a migration: num Postgres
--     gerenciado ela não é superusuária, ganha ADMIN no papel que cria, e sem
--     ele os GRANT de baixo falhariam. GRANTED BY porque, no Postgres 16, o
--     REVOKE só tira o que foi concedido pelo papel nomeado ali;
DO $$
DECLARE
    v_linha record;
BEGIN
    FOR v_linha IN
        SELECT papel.rolname AS papel, membro.rolname AS membro, concedente.rolname AS concedente
          FROM pg_auth_members AS a
          JOIN pg_roles AS papel      ON papel.oid = a.roleid
          JOIN pg_roles AS membro     ON membro.oid = a.member
          JOIN pg_roles AS concedente ON concedente.oid = a.grantor
         WHERE (membro.rolname IN ('sas_leitura', 'sas_mcp', 'autenticador_mcp')
                OR papel.rolname IN ('sas_leitura', 'sas_mcp', 'autenticador_mcp'))
           AND membro.rolname <> current_user
    LOOP
        EXECUTE format('REVOKE %I FROM %I GRANTED BY %I CASCADE',
                       v_linha.papel, v_linha.membro, v_linha.concedente);
    END LOOP;

    FOR v_linha IN
        SELECT papel.rolname AS papel, banco.datname AS banco
          FROM pg_db_role_setting AS s
          JOIN pg_roles    AS papel ON papel.oid = s.setrole
          JOIN pg_database AS banco ON banco.oid = s.setdatabase
         WHERE papel.rolname IN ('sas_leitura', 'sas_mcp', 'autenticador_mcp')
    LOOP
        EXECUTE format('ALTER ROLE %I IN DATABASE %I RESET ALL', v_linha.papel, v_linha.banco);
    END LOOP;
END
$$;

--   * e privilégio de objeto: a lista abaixo passa a ser a lista INTEIRA.
--     REVOKE na tabela leva junto os GRANT por coluna.
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM sas_leitura, sas_mcp, autenticador_mcp;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM sas_leitura, sas_mcp, autenticador_mcp;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM sas_leitura, sas_mcp, autenticador_mcp;
REVOKE ALL ON SCHEMA public FROM sas_leitura, sas_mcp, autenticador_mcp;

GRANT USAGE ON SCHEMA public TO sas_leitura;

-- O sas_mcp é sas_leitura e mais o estreito da 0072.
GRANT sas_leitura TO sas_mcp;

-- O autenticador_mcp só TROCA para o sas_mcp: sem isto o postgrest_mcp
-- responde "permission denied to set role" a tudo. INHERIT FALSE explícito, e
-- não só deduzido do NOINHERIT do papel: no Postgres 16 a herança é do
-- pertencimento, fixada aqui, e um `ALTER ROLE … INHERIT` depois não a muda.
GRANT sas_mcp TO autenticador_mcp WITH INHERIT FALSE;

-- O teto de duração de comando vale para a SESSÃO do login, que o Postgres
-- aplica ao conectar — e não depende do PostgREST, que com PGRST_DB_CONFIG
-- desligado nem lê config de papel. Abaixo do prazo de 90 s das tools
-- (chat/ferramentas.PRAZO_PADRAO_S): quando o prazo abandona a thread de uma
-- tool, a consulta dela segue no Postgres, que é o mesmo da API; o teto a mata
-- lá. As consultas das tools expostas levam menos de 1 s com os ~900 alunos.
ALTER ROLE autenticador_mcp SET statement_timeout = '30s';

COMMENT ON ROLE sas_leitura IS
    'SELECT só na lista branca da 0071, por coluna. Sem DEFAULT PRIVILEGES: tabela e coluna novas nascem invisíveis (docs/43 §5.2).';
COMMENT ON ROLE sas_mcp IS
    'Papel anônimo do postgrest_mcp: sas_leitura + INSERT na auditoria + EXECUTE em mcp_conferir_token (0072). Nunca recebe JWT: o postgrest_mcp não tem PGRST_JWT_SECRET (docs/43 §5.2).';
COMMENT ON ROLE autenticador_mcp IS
    'Login do postgrest_mcp (0071): NOINHERIT, membro só do sas_mcp, para o SET ROLE de cada requisição. Nunca membro do sas_service. A senha vem de POSTGREST_MCP_PASSWORD e é definida pela operação, nunca numa migration (docs/43 §5.2).';


-- ─── 2. A lista branca ────────────────────────────────────────────────────
--
-- Uma tabela por GRANT, com quem a lê. "Filtro" e "embed" marcam coluna que
-- a tool não devolve mas que o comando cita.

-- alerta · listar_alertas (resolvido, severidade e categoria: filtro;
-- disparado_em: ordem). Entrou em 26/10 com o nome do aluno liberado no MCP: o
-- título é texto livre com o nome interpolado. FORA: `dados_brutos` (o
-- payload da sparkline da tela), `hash_dedup` (bastidor do recálculo) e
-- `resolvido_em` — nenhuma tool os lê.
GRANT SELECT (id, categoria, severidade, entidade_tipo, entidade_id, titulo,
              subtitulo, disparado_em, resolvido)
    ON alerta TO sas_leitura;

-- aluno · obter_aluno, relatorio_aluno, historico_aluno, relatorio_ciclo,
-- notas_simulado (embed aluno(id, nome)), alunos_similares, comparar_alunos,
-- alunos_em_risco, alunos_destaque, listar_alunos (embed aluno:aluno_id),
-- buscar_aluno_por_matricula, buscar_aluno_por_nome (26/10; `nome` é filtro
-- ilike e ordem) — e o pseudonimizador do MCP, quando ligado, que lê (id,
-- matricula, nome) para trocar nome por matrícula. `ativo` também é filtro
-- (stats/classificacao). NUNCA: senha_hash, email, avatar_url, canvas_user_id,
-- canvas_criado_em, email_verificado_em, foto_perfil_*, restricao_alimentar
-- (dado de saúde; o COMMENT da 0049 já diz que não entra em chat).
GRANT SELECT (id, matricula, nome, ativo)
    ON aluno TO sas_leitura;

-- ano_letivo · listar_ciclos, relatorio_aluno, historico_aluno e
-- relatorio_ciclo, pelo embed ano_letivo(ano) a partir de ciclo.
GRANT SELECT (id, ano)
    ON ano_letivo TO sas_leitura;

-- ciclo · listar_ciclos, relatorio_aluno, historico_aluno, relatorio_ciclo e,
-- por stats/ciclo_estatisticas.calcular, estatisticas_ciclo e
-- comparar_ciclos (ano_letivo_id: filtro do ciclo anterior e FK do embed).
GRANT SELECT (id, ano_letivo_id, ordem, nome, vestibular_alvo, periodo_inicio, periodo_fim)
    ON ciclo TO sas_leitura;

-- classificacao_aluno · obter_aluno, tendencia_aluno, relatorio_aluno,
-- alunos_em_risco, alunos_destaque, listar_alunos, relatorio_ciclo e, por
-- stats/classificacao.mapa_classificacao, alunos_similares e comparar_alunos.
GRANT SELECT (aluno_id, perfil, tendencia, zona, media_recente, desvio_recente,
              coef_tendencia, p_valor_tendencia, janela_simulados)
    ON classificacao_aluno TO sas_leitura;

-- criterio_classificacao · estatisticas_ciclo com régua criada pela
-- coordenação (stats/criterios_repo._linhas_ativas; as cinco embutidas vêm do
-- arquivo e não tocam o banco). criado_por é o `sub` (uuid) da conta que
-- criou a régua (routes/criterios.py:_ator), não e-mail: vai porque o select
-- do domínio o pede, não por ser útil ao MCP. ⚠️ _linhas_ativas engole a
-- falha: sem este GRANT a régua criada some em silêncio e a tool responde
-- "critério não existe".
GRANT SELECT (id, slug, versao, nome, descricao, combinador, fase, desempate,
              embutido, ativo, criado_em, criado_por)
    ON criterio_classificacao TO sas_leitura;

-- predicado_criterio · estatisticas_ciclo, pelo embed
-- predicado_criterio(...) (criterio_id: FK do embed).
GRANT SELECT (criterio_id, posicao, materia, operador, valor_nota, valor_acertos,
              valor_de, eliminatorio, entra_na_media, peso, fonte)
    ON predicado_criterio TO sas_leitura;

-- insight_ciclo · insights_do_ciclo (ciclo_id: filtro).
GRANT SELECT (ciclo_id, fase, materia_codigo, tipo_insight, bullets, gerado_em)
    ON insight_ciclo TO sas_leitura;

-- materia · listar_materias, listar_simulados, obter_simulado,
-- trajetoria_aluno, comparar_alunos, comparar_simulados, alunos_similares,
-- materias_problematicas, relatorio_aluno, historico_aluno, relatorio_ciclo,
-- estatisticas_ciclo e comparar_ciclos.
GRANT SELECT (id, codigo, nome)
    ON materia TO sas_leitura;

-- matricula_turma · obter_aluno e relatorio_aluno (a turma ativa, pelo embed
-- turma(...)) e listar_alunos (filtro por turma ou sede). FORA: os campos
-- brutos do Canvas, inclusive o último acesso do aluno ao curso.
GRANT SELECT (aluno_id, turma_id, ativo_desde, ativo_ate)
    ON matricula_turma TO sas_leitura;

-- metrica_simulado · obter_simulado, histograma_simulado, comparar_simulados
-- e relatorio_ciclo (recorte_tipo e recorte_id: filtro do recorte 'geral').
GRANT SELECT (simulado_id, recorte_tipo, recorte_id, media, mediana, desvio_padrao,
              minimo, maximo, quartil_1, quartil_3, n_presentes, n_ausentes,
              histograma, pct_aprovados, pct_zona_critica, pct_excelencia)
    ON metrica_simulado TO sas_leitura;

-- nota · trajetoria_aluno, notas_simulado, alunos_similares, comparar_alunos,
-- materias_problematicas, relatorio_aluno, historico_aluno, relatorio_ciclo,
-- estatisticas_ciclo e comparar_ciclos (computavel: filtro de
-- stats/utils.filtro_nota_valida; simulado_id e aluno_id: FK dos embeds).
-- FORA: as duas origens da pontuação, quem a lançou e quem a editou.
GRANT SELECT (aluno_id, simulado_id, pontuacao, presente, computavel)
    ON nota TO sas_leitura;

-- questao · questoes_do_simulado (simulado_id: filtro).
GRANT SELECT (id, simulado_id, posicao, texto, assunto)
    ON questao TO sas_leitura;

-- questao_resposta_aluno · questoes_do_simulado, que só conta acerto por
-- questão. FORA: de quem é a resposta e qual alternativa a pessoa marcou.
GRANT SELECT (questao_id, correta)
    ON questao_resposta_aluno TO sas_leitura;

-- sede · listar_sedes, e os embeds sede(nome) de listar_turmas, obter_aluno
-- e relatorio_aluno.
GRANT SELECT (id, codigo, nome, modalidade)
    ON sede TO sas_leitura;

-- simulado · listar_simulados, obter_simulado, notas_simulado,
-- comparar_simulados, questoes_do_simulado (quiz_id), materias_problematicas,
-- relatorio_ciclo, estatisticas_ciclo, comparar_ciclos, e os embeds
-- simulado(...) de trajetoria_aluno (nota_confiavel), relatorio_aluno,
-- historico_aluno, alunos_similares e comparar_alunos. FORA: arquivo da
-- prova, estado e erro do Canvas, e os motivos escritos à mão.
-- ⚠️ materias_problematicas pede também `fase` (tools/heuristicas.py:130),
-- coluna que a 0003 removeu: a tool falha nos DOIS PostgREST, com 42703 —
-- não é GRANT que falta, e não há coluna a conceder (24/10).
GRANT SELECT (id, ciclo_id, materia_id, nome, rotulo_curto, tipo, data_aplicacao,
              nota_maxima, e_agregado, anulado, nota_confiavel, quiz_id)
    ON simulado TO sas_leitura;

-- turma · listar_turmas, listar_alunos (filtro por sede) e o embed turma(...)
-- de obter_aluno e relatorio_aluno (sede_id: FK do embed sede).
GRANT SELECT (id, sede_id, serie, trilha, section_original)
    ON turma TO sas_leitura;

-- vestibular_alvo_aluno · obter_aluno.
GRANT SELECT (aluno_id, vestibular)
    ON vestibular_alvo_aluno TO sas_leitura;

-- ── O banco de questões (prova passada de ITA/IME) ──
--
-- Nada aqui é dado pessoal: são as provas, os tópicos do edital e o
-- parâmetro do índice. Vai por coluna mesmo assim, pela regra do arquivo. As
-- três tools leem PELO DOMÍNIO — o que pedem ao PostgREST é o que
-- banco/consultas.py e banco/estatisticas.py pedem, e é isso que está aqui.

-- questao_vestibular · buscar_questoes_do_banco (consultas.listar_questoes e
-- obter_questao: _COLUNAS_QUESTAO, o count=exact da página; materia,
-- vestibular, ano, fase, extraido_por e enunciado_md também são filtro, e ano
-- e numero, ordem), topicos_do_edital (consultas.listar_taxonomia: id,
-- materia, ano, fase, vestibular) e recorrencia_no_banco
-- (estatisticas._carregar_questoes). imagem_url e resolucao_url vão porque o
-- select do domínio as pede, não porque a tool as devolva. FORA: a
-- proveniência (fonte_pdf, fonte_pagina, arquivo_origem, importado_em), quem
-- classificou e o bastidor da extração.
GRANT SELECT (id, vestibular, ano, fase, materia, numero, dissertativa, enunciado_md,
              gabarito, gabarito_origem, gabarito_confianca, imagem_url,
              usa_imagem_no_render, resolucao_url, resolucao_md, resolucao_origem,
              extraido_por, revisado)
    ON questao_vestibular TO sas_leitura;

-- questao_vestibular_alternativa · buscar_questoes_do_banco, pelo embed
-- questao_vestibular_alternativa(letra, texto) (questao_id: FK do embed).
GRANT SELECT (questao_id, letra, texto)
    ON questao_vestibular_alternativa TO sas_leitura;

-- questao_vestibular_topico · as três: a ligação questão↔tópico
-- (consultas._COLUNAS_LIGACAO em buscar_questoes_do_banco; questao_id,
-- materia e topico_codigo nas contagens e no filtro por tópico).
-- `observacao` é a nota do classificador sobre o tópico, não de pessoa.
GRANT SELECT (questao_id, materia, topico_codigo, confianca, observacao)
    ON questao_vestibular_topico TO sas_leitura;

-- topico_taxonomia · as três (consultas._COLUNAS_TAXONOMIA e
-- estatisticas._carregar_topicos; materia é filtro, ordem é a do edital).
GRANT SELECT (materia, codigo, nome, bloco_codigo, bloco_nome, ordem)
    ON topico_taxonomia TO sas_leitura;

-- topico_taxonomia_assunto · topicos_do_edital e buscar_questoes_do_banco,
-- pelo embed topico_taxonomia_assunto(ordem, texto) (materia e
-- topico_codigo: a FK composta do embed).
GRANT SELECT (materia, topico_codigo, ordem, texto)
    ON topico_taxonomia_assunto TO sas_leitura;

-- parametro_importancia · recorrencia_no_banco (importancia.carregar_parametro;
-- ativo: filtro). FORA: criado_por, que é o NOME de quem girou o botão
-- (routes/banco.py). ⚠️ carregar_parametro nunca levanta: sem este GRANT o
-- índice sai com a meia-vida de fábrica, sem erro nenhum.
GRANT SELECT (versao, meia_vida_anos, janela_tendencia_anos, ativo)
    ON parametro_importancia TO sas_leitura;


-- ─── 3. A função SECURITY DEFINER que qualquer papel executava ────────────
--
-- `atualizar_v_candidato_externo_por_nome()` (0063) roda como o DONO — o
-- superusuário das migrations — e o Postgres dá EXECUTE a PUBLIC em toda
-- função nova. Hoje isso não pesava, porque só o sas_service chegava ao
-- PostgREST; com um segundo papel no ar, qualquer um dispararia o REFRESH de
-- ~1,3 s da captação por RPC. Fica só com quem a chama de fato: a API e os
-- scripts de captação, todos pelo PostgREST da API (routes/captacao.py,
-- scripts/importar_captacao_externa.py e outros).
--
-- `buscar_candidatos_por_conquista()` (0068) continua de PUBLIC, e pode: é
-- SECURITY INVOKER, roda com o privilégio de quem chama, e o sas_mcp não tem
-- SELECT em tabela nenhuma da captação — chamada por ele volta 42501.
REVOKE EXECUTE ON FUNCTION atualizar_v_candidato_externo_por_nome() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION atualizar_v_candidato_externo_por_nome() TO sas_service;

COMMIT;
