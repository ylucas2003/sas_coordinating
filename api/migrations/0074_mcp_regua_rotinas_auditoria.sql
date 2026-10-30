-- 0074 · O MCP passa a ler a régua, as rotinas e a trilha (docs/43 §5.2 e §6)
--
-- Até 30/10 sete tools da coordenação ficavam FORA do MCP por uma decisão de
-- 24/10 ("decisão aberta", docs/43 §6): `reguas_de_corte` e
-- `cortados_pela_regua` (chat/tools/reguas.py); `estado_do_sync_canvas`,
-- `pendencias_canvas_do_ciclo`, `estado_das_gravacoes` e `lembretes_agendados`
-- (chat/tools/rotinas.py); e `historico_de_alteracoes` (chat/tools/trilha.py).
-- Em 30/10 a coordenação reverteu: TUDO o que o coordenador lê na plataforma
-- passa a ser lido também pela IA no MCP. Esta migration é a parte do banco
-- dessa decisão — o que as sete leem, seguido handler por handler até o
-- PostgREST, domínio, embed e filtro incluídos, como a 0071 fez com as 31.
--
-- As regras da 0071 valem todas: SELECT POR COLUNA, só ao sas_leitura, sem
-- DEFAULT PRIVILEGES, e coluna nova nasce invisível. Só leitura: nenhuma das
-- sete escreve, e nada aqui concede escrita.
--
-- TRÊS VIEWS, e por que view desta vez. A 0071 deixou toda view de fora porque
-- nenhuma view do schema usa security_invoker: ela roda com o privilégio do
-- dono e expõe o que lê. Aqui é esse mesmo comportamento que se quer — mas
-- numa view escrita PARA o MCP, que só lê o que pode sair:
--
--   trilha_de_alteracoes  GRANT por coluna não corta LINHA, e `evento_auditoria`
--                         tem as linhas do canal `acesso`: em `login_falhou` o
--                         `ator_id` é o e-mail DIGITADO (e há quem digite a
--                         senha no campo errado), em `coordenador_criado` o
--                         detalhe leva e-mail e nome, e toda linha tem `ip`
--                         (routes/auth.py, routes/administracao.py). A view
--                         entrega só os canais que a tool lê, sem `ip`
--                         nem `request_id`, e o detalhe só com as chaves que a
--                         tool mostra;
--   nome_da_coordenacao   `historico_de_alteracoes` e `reguas_de_corte` dizem
--                         QUEM fez pelo nome, e o nome mora em
--                         `usuario_coordenacao` — a tabela da credencial, que
--                         não entra na lista branca (é a sonda do boot do MCP,
--                         app/mcp/dados.py). A view entrega o par (id, nome) e
--                         mais nada: nem e-mail, nem hash, nem papel;
--   aula_gravacao_para_ia o S3 é onde o vídeo de aula com aluno menor mora, e
--                         não é lido. Mas o texto de erro da aula pode citá-lo:
--                         o `Failing row contains (…)` do Postgres despeja a
--                         linha inteira, e o erro da API do YouTube traz a URL
--                         com `id=`. GRANT por coluna em `erro_detalhe`
--                         entregaria isso cru; a view entrega o erro sem o id do
--                         vídeo e sem a linha despejada. O LINK entra como
--                         coluna, por decisão da coordenação em 30/10: a IA o
--                         recebe como a tela o mostra (`youtube_video_id`,
--                         `youtube_titulo`, `canvas_pagina_url`), embora ele seja
--                         o acesso a um vídeo NÃO LISTADO.
--
-- As três são `security_barrier`: filtro vindo de fora (o PostgREST monta o
-- WHERE com o que a requisição pedir) não roda antes do WHERE da view, e
-- função que vaza argumento não vê a linha que a view esconde. São dela, e
-- de mais ninguém, as regras de auditoria que deixam GRANT numa view
-- (scripts/verificar_papeis_do_mcp.VIEWS_DO_MCP): criada numa migration do
-- MCP, com security_barrier, e nunca recriada fora delas.
--
-- Por que `usuario_coordenacao` continua fora mesmo com o nome saindo: o
-- GRANT (id, nome) na tabela abriria a sonda do boot — `select=id` voltaria
-- linha em vez de 42501 e o MCP recusaria subir (app/mcp/dados.py) —, e a
-- régua "a credencial não entra" deixaria de ser verdade por construção.
--
-- O QUE CONTINUA FORA, de propósito:
--   * `evento_auditoria`, `aula_gravacao` e `usuario_coordenacao` como
--     tabela: só pelas views acima;
--   * de `disparo`: o destinatário (e-mail), assunto, corpo (com o primeiro
--     nome do aluno e o link de descadastro, que é o token de quem recebe),
--     contexto (com o nome) e o erro do SES. A tool só CONTA disparos
--     (chat/tools/rotinas.py, docstring);
--   * de `evento_agenda`: `criado_por`, o e-mail de quem agendou (0018);
--   * de `curso_monitorado_gravacao`: `professor_padrao` (nome de professor)
--     e os ids de módulo do Canvas — a tool não os lê;
--   * de `simulado`: o arquivo da prova e os motivos escritos à mão, como na
--     0071; de `nota`, quem a lançou e quem a editou;
--   * a cantina, a captação e o banco de questões: cada um na sua frente
--     (0075 a 0077).
--
-- O texto de erro de integração (`simulado.canvas_erro`, `ciclo.canvas_erro`,
-- `canvas_sync_execucao.erro_mensagem`) entra CRU: é o `str(exc)` do httpx, com
-- a URL do Canvas ou do PostgREST, e as tools o limpam (`texto_seguro`, docs/43
-- §3.2, invariante 6) antes de devolvê-lo. O token do Canvas vai no cabeçalho
-- (canvas_sync/cliente.py), não na URL; o que um MCP comprometido leria a mais
-- que a tool é o endereço, que a tela da coordenação também mostra.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`
-- (CLAUDE.md, armadilha 1). As views são relação nova: sem o restart, as duas
-- APIs respondem 404 nelas — e a API também lê as três, pelas tools do chat.
-- O sas_service as lê pelo DEFAULT PRIVILEGES do init (infra/postgres/init),
-- que vale para view como para tabela.

BEGIN;

-- ─── 1. As views ──────────────────────────────────────────────────────────

-- O que `historico_de_alteracoes` lê da trilha. Os canais são
-- `trilha.CANAIS_DA_TRILHA` e as chaves do detalhe são a UNIÃO de
-- `trilha.DETALHE_POR_ACAO` — tests/test_migrations_do_mcp.py reprova se os
-- dois lados divergirem. A tool ainda corta o detalhe por AÇÃO; aqui é o
-- teto, para que uma chave nova gravada amanhã num destes canais não saia
-- sem alguém revisar. Detalhe que não é objeto vira NULL, como a tool o lê.
-- As leituras do MCP (`mcp_ferramenta_chamada`) nem chegam aqui: são do canal
-- `mcp`. Os logins, sim, precisam do `acao`: o canal `cantina` também os grava
-- (routes/auth.py), e em `login_falhou` o `ator_id` é o que a pessoa digitou —
-- o motivo desta view existir. A prova integrada de 30/10 mostrou esse buraco
-- ao abrir o canal. `restricao_alimentar_editada` fica fora pela regra do dado
-- de saúde: ele sai por uma tool só (`restricoes_alimentares`), e com o id do
-- aluno a trilha diria quem tem restrição mesmo com essa tool desligada.
CREATE VIEW trilha_de_alteracoes WITH (security_barrier = true) AS
SELECT e.id,
       e.ocorrido_em,
       e.acao,
       e.canal,
       e.ator_tipo,
       e.ator_id,
       e.recurso,
       CASE WHEN jsonb_typeof(e.detalhe) = 'object' THEN (
           SELECT coalesce(jsonb_object_agg(d.chave, d.valor), '{}'::jsonb)
             FROM jsonb_each(e.detalhe) AS d (chave, valor)
            WHERE d.chave IN ('aluno', 'valor_antes', 'valor_depois', 'valor_canvas', 'presente',
                              'sincronizar_canvas', 'canvas_ok', 'canvas_erro', 'nome',
                              'data_aplicacao', 'canvas_estado', 'campos', 'origem',
                              'apagado_no_canvas', 'ok', 'erro', 'enviados', 'falhas', 'total',
                              'versao', 'requisitos', 'de', 'para', 'data', 'refeicao',
                              'blocos', 'aluno_id', 'cardapio_id', 'alunos', 'conquista_id')
       ) END AS detalhe
  FROM evento_auditoria AS e
 WHERE e.canal IN ('nota', 'simulado', 'ciclo', 'canvas', 'criterio', 'cantina', 'captacao')
   AND e.acao NOT IN ('login_ok', 'login_falhou', 'primeiro_acesso_bloqueado',
                      'restricao_alimentar_editada');

COMMENT ON VIEW trilha_de_alteracoes IS
    'A trilha que as tools leem (0074): só os canais nota, simulado, ciclo, canvas, criterio, cantina e captacao, sem ip nem request_id, e o detalhe só com as chaves que historico_de_alteracoes mostra. É por ela, e nunca pela tabela, que o MCP lê evento_auditoria (docs/43 §5.2).';

-- Quem fez, pelo nome. `auditoria.nomes_da_coordenacao` e a busca por nome de
-- `historico_de_alteracoes` leem daqui.
CREATE VIEW nome_da_coordenacao WITH (security_barrier = true) AS
SELECT u.id, u.nome
  FROM usuario_coordenacao AS u;

COMMENT ON VIEW nome_da_coordenacao IS
    'O nome de cada conta da coordenação, e só ele (0074): é como as tools dizem quem criou uma régua ou mudou uma nota. Nada de e-mail, hash, papel ou foto — e a tabela usuario_coordenacao continua fora da lista branca do MCP (docs/43 §5.2).';

-- O que `estado_das_gravacoes` lê das aulas (`consulta.painel(para_ia=True)`).
-- O id do vídeo sai do erro ANTES de a linha despejada sair: o `replace` só
-- acha o id que está gravado, e o corte do `Failing row contains (` leva o
-- resto — o S3 e o vídeo de quando o id não ficou gravado. O mesmo corte que
-- a tool já faz (chat/tools/rotinas._LINHA_DESPEJADA): lá ele limpa o que
-- sai; aqui, o que o MCP consegue ler. Do rótulo até o FIM do texto: o
-- Postgres escreve os valores sem aspas, e parêntese no título engana
-- qualquer pareamento (revisão paralela de 26/10). No Postgres, `.` casa a
-- quebra de linha por padrão.
CREATE VIEW aula_gravacao_para_ia WITH (security_barrier = true) AS
SELECT a.id,
       a.curso_id,
       a.titulo,
       a.iniciada_em,
       a.status,
       a.tentativas,
       regexp_replace(
           CASE WHEN coalesce(a.youtube_video_id, '') = '' THEN a.erro_detalhe
                ELSE replace(a.erro_detalhe, a.youtube_video_id, '[vídeo]') END,
           'Failing row contains \(.*$', 'Failing row contains (…)'
       ) AS erro_detalhe,
       a.canvas_estado,
       a.canvas_modulo_nome,
       a.youtube_video_id,
       a.youtube_titulo,
       a.canvas_pagina_url,
       regexp_replace(
           CASE WHEN coalesce(a.youtube_video_id, '') = '' THEN a.canvas_erro
                ELSE replace(a.canvas_erro, a.youtube_video_id, '[vídeo]') END,
           'Failing row contains \(.*$', 'Failing row contains (…)'
       ) AS canvas_erro,
       a.atualizado_em
  FROM aula_gravacao AS a;

COMMENT ON VIEW aula_gravacao_para_ia IS
    'As aulas gravadas como a tela as mostra, com o link do YouTube e a página do Canvas (decisão da coordenação, 30/10), sem as colunas do S3, e com o erro sem o id do vídeo e sem a linha que o Postgres despeja (a tool ainda limpa URL e credencial do texto). É por ela que estado_das_gravacoes lê, no chat e no MCP (docs/43 §5.2).';


-- ─── 2. A lista branca cresce ─────────────────────────────────────────────
--
-- Uma relação por GRANT, com quem a lê, como na 0071. "Filtro" e "embed"
-- marcam coluna que a tool não devolve mas que o comando cita.

-- trilha_de_alteracoes · historico_de_alteracoes (auditoria.consultar com
-- so_alteracoes: canal, acao, ator_id, recurso e ocorrido_em também são
-- filtro, id é a ordem).
GRANT SELECT (id, ocorrido_em, acao, canal, ator_tipo, ator_id, recurso, detalhe)
    ON trilha_de_alteracoes TO sas_leitura;

-- nome_da_coordenacao · historico_de_alteracoes (quem fez, e o filtro por
-- trecho do nome: `nome` é ilike) e reguas_de_corte (quem criou cada versão
-- de uma régua criada), por auditoria.nomes_da_coordenacao.
GRANT SELECT (id, nome)
    ON nome_da_coordenacao TO sas_leitura;

-- aula_gravacao_para_ia · estado_das_gravacoes (iniciada_em: ordem).
GRANT SELECT (id, curso_id, titulo, iniciada_em, status, tentativas, erro_detalhe,
              canvas_estado, canvas_modulo_nome, canvas_erro, atualizado_em,
              youtube_video_id, youtube_titulo, canvas_pagina_url)
    ON aula_gravacao_para_ia TO sas_leitura;

-- curso_monitorado_gravacao · estado_das_gravacoes (o nome do curso e se a
-- página da aula é publicada nele; nome é a ordem). FORA: professor_padrao e
-- os ids de módulo do Canvas.
GRANT SELECT (curso_id, nome, ativo, publicar_no_canvas)
    ON curso_monitorado_gravacao TO sas_leitura;

-- canvas_sync_execucao · estado_do_sync_canvas (canvas_sync/estado.ultimo_sync
-- e as rodadas recentes; status e iniciado_em são filtro, id é o que a
-- contagem pede). Uma linha por rodada de 5 min, sem dado de pessoa: o
-- `resumo` são contagens e avisos de section e assignment; o erro, o str(exc)
-- da rodada — os dois saem limpos pela tool.
GRANT SELECT (id, tipo, status, iniciado_em, finalizado_em, resumo, erro_mensagem)
    ON canvas_sync_execucao TO sas_leitura;

-- disparo · lembretes_agendados, que só CONTA (`count=exact` com `select=id`):
-- chave_idempotencia, estado, enviar_em, enviado_em, tentativas e
-- atualizado_em são filtro (lembretes/despachante.enviados_nas_ultimas_24h e
-- a fila). A chave dos lembretes de aluno é `aluno-dia:<dia>:<aluno_id>`
-- (aluno_simulado.chave_idempotencia) — um id, não um nome. FORA: destinatario, assunto, corpo, contexto, erro,
-- regra_lembrete_id, canal e criado_em.
GRANT SELECT (id, chave_idempotencia, estado, enviar_em, enviado_em, tentativas, atualizado_em)
    ON disparo TO sas_leitura;

-- evento_agenda · lembretes_agendados (data_evento: filtro e ordem;
-- hora_evento: ordem). FORA: criado_por, que é o e-mail de quem agendou.
GRANT SELECT (id, titulo, data_evento, hora_evento, cancelado_em)
    ON evento_agenda TO sas_leitura;

-- regra_lembrete · lembretes_agendados (evento_agenda_id: filtro).
GRANT SELECT (id, evento_agenda_id, destinatario_tipo, dias_antes, cancelada_em)
    ON regra_lembrete TO sas_leitura;

-- simulado · estado_do_sync_canvas e pendencias_canvas_do_ciclo (a escrita SAS
-- → Canvas: origem e canvas_estado também são filtro) e lembretes_agendados
-- (evento_agenda_id: filtro). Somam-se às colunas da 0071.
GRANT SELECT (origem, canvas_estado, canvas_tentativas, canvas_erro, evento_agenda_id)
    ON simulado TO sas_leitura;

-- ciclo · estado_do_sync_canvas e pendencias_canvas_do_ciclo (canvas_estado
-- também é filtro: o grupo do ciclo que falhou ou divergiu no Canvas).
GRANT SELECT (canvas_estado, canvas_erro)
    ON ciclo TO sas_leitura;

-- nota · pendencias_canvas_do_ciclo: a nota editada no SAS que o Canvas ainda
-- não tem é `pontuacao_sas` diferente de `pontuacao_canvas` (docs/18 §2.4;
-- pontuacao_sas também é filtro). A 0071 as deixava fora por nenhuma tool
-- exposta as ler. Quem lançou e quem editou continuam fora.
GRANT SELECT (pontuacao_sas, pontuacao_canvas)
    ON nota TO sas_leitura;

COMMIT;
