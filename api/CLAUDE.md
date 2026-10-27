# api — contexto para o Claude Code

Backend FastAPI. Contexto geral e armadilhas do repositório em
[../CLAUDE.md](../CLAUDE.md) — leia aquele primeiro.

> [README.md](README.md) está desatualizado: diz "scaffold inicial, rotas
> devolvem listas vazias". Não é o caso desde 2025 — o backend está completo e
> em produção.

## A camada de dados

`get_supabase()` devolve um cliente **PostgREST**, não um driver SQL. Regras
que decorrem disso:

- Escreva `cliente.table("nota").select(...).eq(...)`, nunca SQL. A única
  exceção é [scripts/migrate.py](scripts/migrate.py), que usa `psycopg`.
- **`get_supabase()` para handler normal** (cliente cacheado) e
  **`criar_cliente_supabase()` para background task**. O motivo está em
  [app/supabase_client.py](app/supabase_client.py): o postgrest-py força
  HTTP/2, todas as requisições de um cliente dividem uma conexão TCP, e um
  GOAWAY numa stream (statement timeout, por exemplo) **aborta todas as
  outras** — sintoma "Server disconnected" num lugar que não tem nada a ver
  com o problema.
- Sem RLS. O papel `sas_service` tem acesso total, então **toda** autorização é
  explícita aqui no backend.

## Mapa dos módulos

| Módulo | O que faz |
|---|---|
| `routes/` | 25 módulos aqui (28 `include_router`: a cantina registra três routers e o `oauth_mcp` dois), mais `chat/`, `canvas_sync/` e `gravacoes_aula/` — 32 `include_router` no total. `main.py` registra `arquivos` só com Storage local e `email_eventos` só com `SES_WEBHOOK_TOKEN` preenchido. Os do MCP: `mcp_tokens.py` (Conexões de IA: emitir, listar e revogar o token), `mcp_emails_ia.py` (os e-mails das contas de IA) e `oauth_mcp.py` (o authorization server do OAuth e o consentimento, que é PÚBLICO — aprovar pede o código do e-mail, não a sessão) |
| `stats/` | Métricas por simulado em 3 recortes (geral/turma/sede), classificação de aluno, alertas, insights via LLM. **`criterios.py` é a única definição de "quem passou"** — as cinco réguas como dado, avaliador **puro** (sem I/O, testável sem container); `criterios_repo.py` é a metade que toca o banco, para as réguas que a coordenação cria. `thresholds.py` ficou só com **calibração** (janela, percentis, limiares de alerta): se o número tem artigo de edital é regra e mora em `criterios.py`; se fomos nós que escolhemos olhando dados, é calibração |
| `chat/` | Loop de agente com tools. **`ferramentas.py` é o registro único** (docs/43 §3): as 42 tools da coordenação e as 17 do aluno passam por um despacho só, que aplica escopo, `aluno_id` do JWT, validação de argumento, prazo, erro sem texto cru e compactação do resultado — e é o mesmo despacho que o MCP usa. Tool nova entra no `TOOLS` do módulo dela e o registro a recolhe; **não escreva outro despachante**. Os `METADADOS` do módulo dão `prazo_s` e `expor_no_mcp`; tool da coordenação sem decisão de exposição reprova em `tests/test_chat_exposicao_no_mcp.py`. O catálogo de cartões é FECHADO (`TIPOS_DE_ARTEFATO`, espelhado em `web/src/dominio/chatStream.ts`; tipo novo pede migration no CHECK de `chat_artefato`, como a 0070). `perfis.py` só amarra uma `Sessao` ao registro, ao prompt e ao modelo; `contexto_do_turno.py` monta, antes de cada pergunta, a data de hoje (os dois escopos) e, no aluno, alvos, régua, próximo simulado e sequência — tudo a partir do JWT, nunca do browser; os roteiros (`roteiros/<escopo>/*.md`) carregam sob demanda. `navegacao.py` carrega o contexto da tela nos dois sentidos — o preâmbulo do turno (página → chat) e a rota do `navegar_para` (chat → página) |
| `mcp/` | **Outro processo**, na mesma imagem: o MCP da coordenação (`python -m app.mcp`, docs/43 §5), fora de produção. Expõe as tools do registro com `expor_no_mcp` (31; 29 com o pseudônimo, que desde 26/10 é opção), e é UM processo só de propósito, porque os tetos por minuto moram na memória dele. Não importa `app.main` nem router — o guard de boot de lá exigiria os segredos que este processo não pode ter —, e a API não importa o SDK do MCP (`test_a_api_nao_importa_o_sdk_do_mcp`). O authorization server do OAuth NÃO mora aqui: é a API (`routes/oauth_mcp.py`, em FastAPI, sem o `mcp.server.auth` do SDK). `emails_ia.py` mora aqui por ser do MCP, mas é a parte pura do código por e-mail e só a API a usa |
| `canvas_sync/` | Sincronização com o Canvas LMS — fonte de verdade das notas. `mapeador.py` compõe **e** parseia os nomes de assignment; as duas gramáticas precisam casar |
| `ingest/` | Pipeline de planilha (CSV/XLSX), idempotente por construção |
| `lembretes/` | Motor de e-mail via SES. Disparo é materializado na criação da regra e revalidado antes do envio. `email.py` é também por onde sai o código que aprova a conexão OAuth do MCP (`routes/oauth_mcp.py::_enviar_codigo`), com a mesma rede de `EMAIL_DESTINATARIO_TESTE` — preenchido, o código vai para a caixa de teste |
| `banco/` | Banco de questões ITA·IME (docs/22): consultas filtradas, recorrência por tópico, progresso do aluno e listas com dono. **É a única rota que pagina** — e o motivo está escrito em `schemas/banco.py`. As tabelas são a **fonte da verdade**: os JSONs não são versionados, e `scripts/exportar_banco_questoes.py` é a saída (docs/22 §13) |
| `gravacoes_aula/` | Publica a aula gravada do Canvas no YouTube: baixa os dois componentes do BigBlueButton, compõe com o template da marca (ffmpeg), guarda no S3, publica como **não listado** (LGPD — são menores) e pendura a página da aula no módulo certo do Canvas (`0035`, `0036`). A ordem é assunto → módulo padrão → "Outras aulas gravadas", um módulo genérico publicado que o código cria por curso na primeira vez que faz falta (`0067`). Página publicada e fora de módulo é repassada a cada rodada; a coordenação acompanha em `/integracoes/aulas`. A gravação some do Canvas em ~7 dias, então o cron roda de hora em hora. Estados `publicado`/`publicado_sem_confirmacao` são TERMINAIS: reprocessar geraria segunda cópia no canal. Uma queda do S3 esgota as 3 tentativas de quem estava na fila; `scripts/reabrir_aulas_com_erro.py` (ou `infra/vps/reabrir-aulas.sh`) as devolve, depois de conferir que o S3 voltou e que a gravação ainda está no Canvas |
| `auditoria.py` | Quem fez o quê. **Nunca** grave senha, hash, token ou corpo de mensagem |

### ⚠️ `questao` e `questao_vestibular` são coisas diferentes

O erro de leitura mais provável do schema hoje:

| Tabela | O que é | Chave |
|---|---|---|
| `questao` | Questão de um **simulado-Quiz do Canvas**. Só existe para simulado com `quiz_id`. Migration 0010 | `simulado_id` NOT NULL |
| `questao_vestibular` | Questão de **prova passada de ITA/IME**, do banco por assunto. Nenhum simulado envolvido. Migration 0028 | `id` texto: `ita_2019_fase1_q01` |

As duas vão se encontrar num sprint futuro: a taxonomia da 0028 é a que preenche
o gancho `questao.assunto`, vazio desde a 0015.

## Autenticação

Quatro tipos de credencial, um JWT (HS256, 8h) — [app/auth.py](app/auth.py).
E, à parte, o token do MCP da coordenação, que de propósito NÃO é JWT (o
último item da lista).

⚠️ **`tipo` diz que tipo de SESSÃO é; `papel` diz o que uma sessão de
coordenação pode a mais.** Confundir os dois derruba acesso — o docstring de
`app/auth.py` explica por que o administrador é `tipo: "coordenador"` +
`papel: "administrador"`, e não um `tipo` próprio.

⚠️ **`get_current_administrador` é o único guard que vai ao BANCO.** Ele
reconfere `papel` e `ativo` em `usuario_coordenacao`, porque o papel viaja num
token de 8 h e rebaixar (ou desativar) alguém precisa valer na hora — senão o
rebaixado cria outra conta de administrador dentro da janela e desfaz a
própria queda. São 5 rotas; `get_current_coordenador` continua decidindo só
pelo token, de propósito.

- **Aluno**: SÓ pelo Canvas (`routes/auth_canvas.py`). A senha de aluno saiu em
  04/09 (docs/35 §11.5) e `aluno.senha_hash` virou fóssil — nenhuma rota
  autentica por ela. O caminho de acesso do aluno é o `canvas_user_id`.
- **Coordenador**: e-mail + senha na tabela `usuario_coordenacao` (0021). A
  credencial de env não é mais lida pelo login; contas nascem pelo painel
  `/administracao` ou por `scripts/criar_coordenador.py`.
- **Canvas (aluno e coordenador)**: OAuth2 por redirect, `routes/auth_canvas.py`.
  O Canvas diz *quem é*; o banco decide *quem entra* — identidade sem linha em
  `aluno`/`usuario_coordenacao` é recusada. Precisa de `CANVAS_CLIENT_ID` /
  `CANVAS_CLIENT_SECRET` (Developer Key, OUTRA credencial que não o token).
- **Cantina**: e-mail + senha em `usuario_cantina` (0047), pela MESMA
  `/auth/login` com `tipo: "cantina"`. É o terceiro tipo de SESSÃO, não um
  papel de coordenação — um papel novo em `usuario_coordenacao` passaria por
  `get_current_coordenador`, que aceita todo papel de propósito, e abriria as
  39 rotas de coordenação para quem trabalha na copa (docs/38 §1).

  ⚠️ **Acrescentar um `tipo` a `TIPOS_DE_SESSAO` nunca é uma linha.** Todo
  lugar que dividia o mundo em "aluno" e "todo o resto" passa a estar errado no
  instante em que existe um terceiro — e o "resto" costuma ser o ramo de
  COORDENAÇÃO. Quando a cantina entrou foram três lugares, verificados um a um
  (docs/38 §1.1); `routes/foto_perfil.py` daria a ela `UPDATE` em
  `usuario_coordenacao`. `tests/test_cantina.py` tranca os cinco guards.
- **Scheduler** (EventBridge): segredo compartilhado no header
  `X-Scheduler-Secret`, não JWT.
- **MCP da coordenação** (outro processo, fora de produção — docs/43 §5.3):
  token **OPACO** `sas_mcp_…`, **nunca JWT**. Só o sha256 fica em
  `token_mcp` (0072), e o MCP o confere A CADA requisição pela RPC
  `mcp_conferir_token`, sem cache: revogar ou desativar a conta vale na
  próxima. `get_current_user` recusa o token do MCP e o MCP recusa o JWT de
  sessão, por construção — não "unifique" os dois, nem dê ao MCP a
  `JWT_SECRET_KEY` (o guard dele recusa subir com ela). Dois caminhos:
  - **token pessoal** (Claude Code, Claude Desktop): emitido pelo coordenador
    LOGADO, em Conexões de IA (`routes/mcp_tokens.py`) ou por
    `scripts/criar_token_mcp.py`; mostrado uma vez, vence em 90 dias;
  - **OAuth** (claude.ai, ChatGPT): o authorization server é a API
    (`routes/oauth_mcp.py`), e ⚠️ **a aprovação NÃO é a sessão**: é o código
    de 6 dígitos enviado ao e-mail da conta de IA que o coordenador cadastrou
    (`routes/mcp_emails_ia.py`; decisão do dono de 26/10). O consentimento é
    público; o `/codigo` responde 202 igual para e-mail cadastrado ou não
    (o que depende do e-mail roda depois da resposta), e o código só existe
    como HMAC com chave derivada da `JWT_SECRET_KEY`. A conexão nasce em nome
    do coordenador dono do e-mail. Só aprova e-mail ativo E confirmado: o
    cadastro nasce aguardando e manda um código de confirmação (`POST
    /mcp/emails-ia/{id}/confirmar`, `…/reenviar`), e `_cadastro_que_aprova`
    exige `confirmado_em` (docs/43 §5.6). Erro do SES se loga com o e-mail
    mascarado e o TIPO da exceção, nunca a mensagem — a do `MessageRejected`
    traz o endereço.

  Quem conecta: administrador e coordenador (`MCP_EMISSAO_SO_ADMINISTRADOR`
  com padrão `false` desde 26/10). Ligada, a regra vale para emitir, aprovar e
  USAR, e precisa do MESMO valor na API e no `mcp`, senão a tela emite o que o
  MCP recusa.

O autosserviço de primeiro acesso (`PRIMEIRO_ACESSO_AUTOSSERVICO`) está
**desligado** e o motivo está comentado em [app/config.py](app/config.py):
valida só matrícula + e-mail, ambos deriváveis — quem souber os dois toma a
conta. Não religue sem código de uso único por e-mail.

## Custo de LLM

Há teto por usuário porque já houve o susto: sem limite, o pior caso medido foi
**US$ 379 numa hora**. `CHAT_LIMITE_MENSAGENS_HORA` e
`CHAT_LIMITE_TOKENS_DIA` em [app/config.py](app/config.py). Modelo default é
`gpt-4o-mini` nos dois perfis, cada um com a sua chave explícita
(`OPENAI_MODELO_COORDENADOR` e `OPENAI_MODELO_ALUNO`) — o fallback invertido
que ligava o gpt-4o (16x mais caro) ao configurar o modelo barato já foi
consertado; não reintroduza inferência de modelo a partir de substring do
nome. O processo do MCP não tem chave da OpenAI (o guard dele recusa subir
com ela, `mcp/configuracao.py`): ali, quem paga o modelo é a IA de quem
conectou.

## Migrations

72 em [migrations/](migrations/) (de 0001 a 0073; a 0030 não existe), cada
uma com par `.down.sql`. Runner próprio, estado em `_migracoes_aplicadas`.

⚠️ **O runner guarda só a VERSÃO (os quatro dígitos), não o nome.** Duas
migrations com o mesmo número: a segunda aparece como aplicada e é pulada SEM
ERRO. Quase aconteceu em 26/10 — a `0069` do horário de estudos já estava em
produção quando o branch das ferramentas trazia outra `0069`, e as dele viraram
0070 a 0073 (docs/43 §9). Antes de criar uma, confira o último número no `main`.

```sh
docker compose run --rm migrate status
docker compose run --rm migrate up
docker compose restart postgrest     # OBRIGATÓRIO depois de mexer em tabela
docker compose restart postgrest_mcp # e este também, se o MCP lê o que mudou
```

As migrations do MCP (0071 a 0073) têm regras próprias: a lista branca do
`sas_leitura` é `GRANT` **por coluna**, sem `DEFAULT PRIVILEGES` — tabela e
coluna novas nascem invisíveis ao MCP, e tool exposta que passar a ler coluna
nova leva 42501 até ganhar migration —, e a senha do `autenticador_mcp` NUNCA
entra no arquivo: a 0071 o cria com `PASSWORD NULL` (e devolve a NULL um papel
que já existia), e a operação a define depois do `up` que a aplica e de novo a
cada `down` + `up` dela. O comando está no `docker-compose.yml` da raiz; em
produção, quando o MCP entrar, o `deploy.sh` a redefine em todo deploy
(docs/43 §10).

Depois de qualquer migration que toque `metrica_simulado`, rode
`python -m scripts.recalcular_metricas` (idempotente).

`aluno_serie_recente` (0066) guarda a sparkline e o vetor do kNN por aluno, e
é regravada junto com `classificacao_aluno`. Se suspeitar que envelheceu:
`python -m app.stats.serie_recente` (o deploy roda com `--se-vazia`).

## Ferramentas

```sh
./.venv/bin/python -m pytest tests/ -q   # 2623 testes (+31 pulados); 3 de test_canvas_publicacao.py falham também no main
./.venv/bin/ruff check .                 # lint — configurado em pyproject.toml
./.venv/bin/ruff check . --fix
./.venv/bin/mypy app                     # sob demanda, fora do gate

# MCP da coordenação (docs/43 §5) — com o postgrest_mcp do compose de pé
./.venv/bin/python -m scripts.verificar_papeis_do_mcp \
    --mcp http://127.0.0.1:3001 --api http://127.0.0.1:3000 --ferramentas
./.venv/bin/python -m scripts.criar_token_mcp --email <conta> --nome "<conexão>"
./.venv/bin/python -m scripts.criar_token_mcp --listar          # e --revogar <id>
```

Sem `api/.env` (num worktree, por exemplo), o `pytest` precisa de
`APP_ENV=dev` na frente — o default é `production` (armadilha 3 do
CLAUDE.md da raiz). Os 3 testes de `tests/test_canvas_publicacao.py` falham
também no `main` (26/10). O verificador de papéis é a prova de privilégio
contra o PostgREST DE VERDADE — os testes rodam contra um fake, e o fake não
sabe o que o Postgres recusa; cada rodada grava duas linhas na trilha. O
`criar_token_mcp` grava o token num arquivo 0600 (`SAS_SAIDA_TOKEN` muda o
diretório), nunca no stdout. O processo do MCP sobe pelo compose (`mcp`, em
`127.0.0.1:8001`); `python -m app.mcp --stdio` existe só para dev/test e nunca
foi verificado (docs/43 §8).

Dependências de desenvolvimento em [requirements-dev.txt](requirements-dev.txt)
(não entram na imagem de produção).

O ruff está calibrado para pegar **bug**, não estilo: `E501` (linha longa) está
desligado porque o projeto usa comentário longo explicativo de propósito, e
`RUF001/002/003` porque marcariam todo "ç" e "ã" como caractere ambíguo. O que
ficou ligado inclui `ASYNC` (chamada bloqueante dentro de `async def`), `DTZ`
(datetime sem fuso), `S` (bandit) e `B` (bugbear).

**mypy está fora do gate de propósito.** Dos 109 erros do primeiro run, 72 são
a mesma coisa: `get_supabase()` devolve `ClienteDados`
(`Client | SyncPostgrestClient`) e as funções anotam o parâmetro como `Client`
— decisão consciente, documentada em `supabase_client.py`, não bug. Trocar
essas anotações por `ClienteDados` derruba os 72 de uma vez; aí vale promover
o mypy a gate.

## Convenções

- **`def`, e não `async def`, no endpoint que só faz I/O síncrono** — e quase
  todos fazem: o cliente PostgREST é síncrono. Um `async def` que chama
  `.execute()` roda NO event loop (`UVICORN_WORKERS=1`), então as 8–10
  requisições que uma tela dispara em paralelo são atendidas uma por vez, e uma
  lenta congela o processo para todo mundo. `def` vai para o threadpool do
  FastAPI. Só é `async def` quem tem `await` de verdade (escrita no Canvas,
  streaming). Foi por isso que `alunos.py`, `ciclos.py` e `simulados.py`
  mudaram em 29/09/2026 — e um teste que chamava o handler com `asyncio.run`
  passa a chamá-lo direto.
- Type hints em todas as funções.
- Nomes em português, inclusive colunas de banco.
- Comentário explica o porquê e cita a fonte (`docs/14 §4.1`).
- Erro em caminho de auditoria ou telemetria é engolido; erro em caminho de
  dado, não.
