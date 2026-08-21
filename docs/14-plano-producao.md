# 14 · Plano de produção — hospedar a stack na infra do colégio

Plano de implementação para tirar o SAS da infra provisória (Supabase + Render +
Vercel + AWS) e colocá-lo em produção na infraestrutura do Colégio Ari de Sá.

Companheiro de [`perguntas-infra-producao.pdf`](../perguntas-infra-producao.pdf), que é
a pauta da conversa com o time de plataforma. **Este documento corrige quatro
afirmações daquela pauta** — ver §7.

Base factual: varredura completa do código em 20/08/2026 (8 camadas mapeadas,
bloqueadores verificados adversarialmente). Referências são `arquivo:linha` do
estado atual do repo.

---

## 1. Onde estamos, sem eufemismo

**Não existe produção hoje.** O Supabase caiu em 13/08/2026 (NXDOMAIN) e levou o
ambiente junto. A fonte de verdade atual é o volume Docker `db-dados` e o bind
mount `.dados/storage` (22 MB, 25 PDFs) — ambos na máquina de um desenvolvedor,
ambos fora do git.

Isso tem um lado bom que vale registrar: **não há cutover a coordenar**. Não
existe dataset vivo, janela de dual-write nem downtime a negociar. O caminho de
subida é `migrate up` + `canvas_backfill` + `recalcular_metricas` contra o
Postgres que o colégio provisionar, porque o Canvas é a fonte de verdade de
aluno, turma, simulado e nota.

O que **não** volta do Canvas e precisa de export explícito: senhas que os alunos
criaram no primeiro acesso, threads de chat, alertas resolvidos, insights
gerados, agendamentos (P1), regras de lembrete (P2/P3) e o histórico de
`upload_evento`.

O sistema já é containerizável — imagem multi-stage com alvo `prod`, não-root,
healthcheck, config por env. O trabalho pesado não é "subir": é **fechar o que
hoje só é seguro porque está preso em `127.0.0.1`**.

---

## 2. A decisão que destrava todas as outras: topologia

Antes de qualquer código, uma pergunta ao time de plataforma:
**a API fica em host próprio ou sob subcaminho do mesmo domínio do frontend?**

### Recomendação: um domínio, mesma origem

```
https://sas.aridesa.com.br
    /              →  nginx  (web/ estático)
    /api/*         →  proxy_pass → FastAPI
                                      │
                        rede interna  ├→ PostgREST  (NUNCA roteável de fora)
                                      └→ Postgres
```

Três problemas morrem de uma vez com esse arranjo:

| Problema hoje | Como a mesma origem resolve |
|---|---|
| `BASE_URL` hardcoded para `sas-coordinating.onrender.com` ([http-client.js:10-12](../web/js/services/http-client.js#L10-L12)) | `BASE_URL = ''` — caminho relativo, sem build step |
| CORS por whitelist de string exata ([main.py:52](../api/app/main.py#L52), [config.py:32](../api/app/config.py#L32)) | Não há cross-origin. O middleware fica inerte |
| PostgREST com papel anônimo de acesso total | Fica em rede interna, sem rota de entrada |

**Custo se o colégio recusar:** três correções voltam à mesa — `BASE_URL`
injetável em runtime (arquivo `config.js` gerado no deploy ou `<meta>` no
`index.html`), `CORS_ALLOW_ORIGINS` com os domínios definitivos, e `root_path`
no FastAPI. É meio dia de trabalho, mas precisa ser decidido **antes**, não
descoberto no dia do deploy.

> ⚠️ **A API não tem `root_path` hoje.** [main.py:44-48](../api/app/main.py#L44-L48)
> constrói o `FastAPI()` sem ele e o CMD do Dockerfile não passa `--root-path`.
> Publicar sob `/api` sem isso quebra `/docs`, o `openapi.json` e todo redirect.

---

## 3. O contrato de infraestrutura — o que precisa existir

Oito papéis. A coluna do meio é o que importa; a da esquerda é só o que usamos hoje.

| Hoje | Papel que precisa existir | Requisitos não-negociáveis |
|---|---|---|
| Render | Rodar o container da API | 1 réplica, 1 worker (ver §6.1). Injeta `PORT`. Volume persistente se o storage for filesystem |
| Vercel | Servir o frontend estático | Sem rewrite/fallback SPA — roteamento é por hash, 404 tem que ser 404 |
| Supabase (Postgres) | Banco relacional | **Postgres ≥ 15** (ver §5.1). Collation definida explicitamente. TLS exigido |
| PostgREST (embutido) | Traduzir HTTP → SQL | Container próprio, **rede interna apenas**. É a questão 3 da pauta |
| Supabase Storage | Guardar PDFs de simulado | Volume persistente com owner uid 10001, ou bucket S3-compatível |
| AWS EventBridge | 4 jobs → POST HTTPS autenticado | CronJob genérico resolve. Fuso declarado explicitamente |
| AWS SSM | Cofre de segredos | ~20 variáveis, 8 delas segredos (§5.3) |
| OpenAI | LLM de insights e chat | Saída para `api.openai.com` ou gateway compatível |
| — | Registry + pipeline de deploy | Recebe a imagem `--target prod` |
| — | Log, métrica e alerta | A API escreve em stdout (depois da Fase 4) |

**Saída para a internet** (item 6 da pauta) — hoje **não há suporte a proxy de
saída nem a CA corporativa** em nenhum dos três clientes HTTP. Se a rede do
colégio exigir proxy explícito ou fizer inspeção TLS, tudo falha no primeiro
request e não há variável para consertar. Destinos a liberar:

- `<canvas>.instructure.com` (ou host do Canvas do colégio) — 443
- `api.openai.com` — 443
- `email.<regiao>.amazonaws.com` e `sns.<regiao>.amazonaws.com` — 443 (enquanto for SES)

---

## 4. Fase 0 — Parar o que pode causar dano

**Antes de qualquer deploy. Não depende de resposta nenhuma do colégio. ~3 dias.**

Estes cinco itens não são "melhorias de produção": são coisas que já estão erradas
no código de hoje e cujo raio de dano cresce no momento em que o sistema sair do
laptop.

### 4.1 O guard de boot falha aberto — `minutos`

[config.py:11](../api/app/config.py#L11) tem `app_env: str = "dev"`, e
[main.py:33](../api/app/main.py#L33) envolve **toda** a validação de segredos em
`if settings.app_env not in ("dev", "test")`. Os únicos arquivos que setavam
`APP_ENV=production` são `render.yaml` e `docker-compose.prod.yml` — exatamente
os que deixam de valer na migração.

Um deploy que esqueça `APP_ENV` sobe com `JWT_SECRET_KEY =
"dev-secret-change-in-production"` (valor público neste repositório) e
`COORDENADOR_SENHA = "tioleo123"`. Com o segredo público, qualquer pessoa forja
`{"tipo":"coordenador"}` e lê a base inteira de menores de idade. Não há RLS como
segunda linha ([09-docker.md:55-58](09-docker.md)).

E o estado é publicamente sondável: `/health` devolve `{"env": "dev"}`
([main.py:77](../api/app/main.py#L77)) sem autenticação.

**Correção:** tirar os defaults. `jwt_secret_key: str` e `coordenador_senha: str`
sem valor fazem o pydantic-settings recusar o boot em qualquer ambiente, sem
depender de `APP_ENV`. Estender a validação para `SCHEDULER_SECRET`,
`API_BASE_URL` (quando `STORAGE_DIR` estiver setado), `CORS_ALLOW_ORIGINS` (não
pode conter localhost), `POSTGREST_TOKEN` (quando `POSTGREST_URL` estiver setado)
e `EMAIL_DESTINATARIO_TESTE` (tem que estar **vazia** em produção). Remover `env`
do `/health`.

> A comparação atual é por igualdade literal, então `COORDENADOR_SENHA=` (vazio)
> **passa** no guard — e [auth.py:68](../api/app/routes/auth.py#L68) autentica com
> senha vazia. `JWT_SECRET_KEY=` vazio idem, assinando HS256 com chave conhecida.

### 4.2 SSRF no webhook do SNS — `horas`

[email_eventos.py:39](../api/app/routes/email_eventos.py#L39):

```python
if arn_esperado and payload.get("TopicArn") not in (None, arn_esperado):
```

Um payload **sem** o campo `TopicArn` faz `.get()` devolver `None`, que está na
tupla — a guarda não dispara. E logo abaixo, linhas 46-51, a API faz
`await http.get(url)` na `SubscribeURL` que vier no corpo, **sem validar host nem
esquema**.

Quem conhecer o `SES_WEBHOOK_TOKEN` (que viaja no *path* da URL, portanto está no
access log do ingress, no console do SNS e no histórico de quem configurou) faz a
API emitir GET para qualquer endereço alcançável de dentro da rede do colégio —
incluindo o PostgREST interno e endpoints de metadados de nuvem. E pode injetar
bounces falsos para apagar qualquer aluno da audiência, silenciosamente.

**Correção:** trocar por `payload.get("TopicArn") != arn_esperado` (rejeitando
ausência); validar `SubscribeURL` contra allowlist
(`^https://sns\.[a-z0-9-]+\.amazonaws\.com/`); implementar a verificação de
assinatura do SNS, hoje declarada fora de escopo em
[13-plano-p3-lembrete-aluno.md:378](13-plano-p3-lembrete-aluno.md).

### 4.3 Race no motor de alertas — `horas`

[alertas.py:449-451](../api/app/stats/alertas.py#L449-L451) mantém estado mutável
de módulo (`_cache_historico`, `_historico_carregado`). `avaliar_tudo()` começa
com `limpar_caches()`, que faz `.clear()`; as sete regras iteram o mesmo
dicionário.

Dois chamadores não coordenados: o ingest roda em `background_tasks.add_task`
([uploads.py:115](../api/app/routes/uploads.py#L115)) num thread do threadpool, e
o sync de 5 min ([canvas_sync/rotas.py:53](../api/app/canvas_sync/rotas.py#L53))
em outro. A trava `_trava_execucao` só coordena sync ↔ reconcile, **nunca o
ingest**.

Coordenador sobe planilha às 10:00 e o sync dispara no mesmo minuto: um thread
limpa o dicionário enquanto o outro itera → `RuntimeError: dictionary changed
size during iteration`, ou — pior, porque é silencioso — alertas calculados sobre
histórico pela metade e gravados na tabela `alerta`, que a coordenação lê como
verdade.

**Isso já acontece hoje, com 1 worker.**

**Correção:** tirar o estado do módulo. O histórico vira dicionário local criado
dentro de `avaliar_tudo` e passado às regras como parâmetro. ~30 linhas, resolve
1 worker e N réplicas ao mesmo tempo.

### 4.4 O teto de e-mail é menor que a audiência — `horas`

[config.py:78](../api/app/config.py#L78): `email_teto_diario: int = 150`. A
audiência do P3 é **873 alunos**, e todos os disparos nascem com o mesmo
`enviar_em` (18:00 BRT da véspera).

No tick: `if enviados_24h >= teto: break`. Na primeira noite com P3 ligada, 150
alunos recebem e 723 não. Nos dias seguintes a fila drena — e como `preparar()`
recompõe o texto `f"Amanhã, {data_br}"` a partir do evento, alunos recebem
**"Amanhã, 21/08/2026 você tem:" no dia 23**. E-mail em massa, para menores, com
informação factualmente errada.

**Correção:** (1) dimensionar o teto para a audiência real e travar o boot se
`email_teto_diario` < audiência quando `LEMBRETE_ALUNO_ATIVO=true`; (2) dar
validade ao disparo — `preparar()` devolve `None` quando o dia já passou,
cancelando em vez de enviar.

### 4.5 Dependências — `minutos`

- **`python-multipart==0.0.9`** ([requirements.txt:10](../api/requirements.txt#L10))
  — CVE-2024-53981, DoS no parser multipart, corrigido em 0.0.18. A única rota
  multipart é `POST /uploads`, que já lê o arquivo inteiro na RAM sem limite de
  tamanho. O parsing acontece **antes** do handler, então nem precisa de token
  válido para travar o worker.
- **`python-jose==3.3.0`** ([requirements.txt:7](../api/requirements.txt#L7)) —
  versão de 2021 com CVE-2024-33663/33664. A exposição real é limitada (o código
  fixa `algorithms=["HS256"]`), mas qualquer scan de imagem do time de plataforma
  barra isso. O ambiente local já roda 3.5.0 — o pin e o venv não descrevem o
  mesmo sistema.
- **`postgrest` não está declarado.** [supabase_client.py:38](../api/app/supabase_client.py#L38)
  importa `SyncPostgrestClient` direto — a biblioteca dos ~210 call sites de dados
  entra de carona no `supabase==2.7.4`. Um bump menor do supabase-py que troque
  essa dependência quebra a camada de dados inteira num build que passou sem erro.

**Correção:** subir os dois pins, declarar `postgrest==0.16.11`, e congelar tudo
num `requirements.lock` com hashes usado pelo Dockerfile. Sem lock, a promessa de
"imagem imutável" que a pauta faz ao colégio não é verdadeira.

---

## 5. Fase 1 a 4 — o caminho até o go-live

### Fase 1 — Topologia e fechamento de rede (~4 dias)

| # | Item | Onde |
|---|---|---|
| 1.1 | `location /api { proxy_pass }` no nginx + `BASE_URL = ''` | [nginx.conf](../web/nginx.conf), [http-client.js:10](../web/js/services/http-client.js#L10) |
| 1.2 | `ROOT_PATH` em Settings → `FastAPI(root_path=…)`; `--proxy-headers --forwarded-allow-ips` no CMD | [main.py:44](../api/app/main.py#L44), [Dockerfile:62](../api/Dockerfile#L62) |
| 1.3 | **Fechar o PostgREST**: papel anônimo sem privilégio + `PGRST_JWT_SECRET` + `POSTGREST_TOKEN` | [01-papeis.sh](../infra/postgres/init/01-papeis.sh), [supabase_client.py:56](../api/app/supabase_client.py#L56) |
| 1.4 | `/docs`, `/redoc`, `/openapi.json` fechados fora de dev | [main.py:44-48](../api/app/main.py#L44-L48) |
| 1.5 | Imagem web para `nginx-unprivileged` + headers de segurança (CSP, nosniff, frame-ancestors, Referrer-Policy) | [web/Dockerfile](../web/Dockerfile), [nginx.conf](../web/nginx.conf) |
| 1.6 | Google Fonts local (`@font-face` em `web/assets/fonts/`) — hoje é a única saída externa do frontend e vaza IP de aluno para o Google | [index.html:8-13](../web/index.html#L8-L13) |
| 1.7 | `/health` (liveness) separado de `/health/ready` (checa PostgREST) | [main.py:76](../api/app/main.py#L76) |
| 1.8 | Botão de sair na coordenação — hoje não existe, e o computador da secretaria é compartilhado | [topbar.js](../web/js/components/topbar.js) |

> **1.3 é a questão mais importante da pauta.** Hoje `PGRST_DB_ANON_ROLE:
> sas_service` + `GRANT ALL ON ALL TABLES`: requisição sem token tem
> SELECT/INSERT/UPDATE/DELETE em todas as 31 tabelas. `curl -X DELETE
> http://postgrest:3000/nota` apaga as 44 mil notas; `GET
> /aluno?select=nome,email,senha_hash` vaza 873 menores. A única coisa que
> protege isso hoje é o bind em `127.0.0.1` do compose de dev — **e em Kubernetes
> não existe equivalente disso**: um Service é cluster-wide por definição.
>
> Metade do conserto já está no código: `supabase_client.py:56-57` anexa o Bearer
> quando `POSTGREST_TOKEN` existe. Falta o outro lado.

### Fase 2 — Banco e dados (~4 dias)

#### 5.1 Requisitos do Postgres

**Postgres ≥ 15**, por exatamente uma linha:
[0004:23-25](../api/migrations/0004_fix_metrica_recorte_null.sql) usa `UNIQUE
NULLS NOT DISTINCT`. Em PG 13/14 o `migrate up` morre na quarta migration e o
banco fica pela metade.

O workaround óbvio (dois índices únicos parciais) **não funciona**:
[metricas.py:312-315](../api/app/stats/metricas.py#L312-L315) faz
`upsert(on_conflict="simulado_id,recorte_tipo,recorte_id")`, que o PostgREST
traduz sem index predicate — o Postgres não infere índice parcial, e todo
recálculo passa a devolver `42P10`. Como o backend nunca escreve SQL, não há onde
injetar o predicate. Se o colégio impuser PG 14, o custo é mexer no modelo de
dados, não numa migration.

**Collation** nunca foi especificada. Dev roda `postgres:16-alpine` (musl → locale
C, ordenação por byte). Num Postgres com `pt_BR.UTF-8`, a lista de alunos ordena
diferente ("Ávila" sai do fim e vai para junto dos A) — e, pior, restaurar dump
entre clusters de collation diferente invalida índices de texto e faz busca por
índice devolver menos linhas do que existem.

**TLS**: zero ocorrências de `sslmode` no repo. `psycopg.connect` fica no default
`prefer`, que aceita texto claro e nunca verifica certificado. Exigir
`sslmode=require` (ou `verify-full` com a CA do colégio).

#### 5.2 Migrations e papéis

| # | Item |
|---|---|
| 2.1 | Papéis viram `0000_papeis.sql` idempotente. Hoje só existem via `docker-entrypoint-initdb.d`, que **não existe em Postgres gerenciado** — o PostgREST não sobe com `FATAL: role "authenticator" does not exist` |
| 2.2 | O runner emite `GRANT ALL ON ALL TABLES ... TO sas_service` ao fim de todo `up`. Hoje depende de `ALTER DEFAULT PRIVILEGES` amarrado ao papel `postgres` — se as migrations rodarem como outro usuário (o normal em RDS/Cloud SQL), **toda tabela nova nasce invisível** e o PostgREST devolve 404 |
| 2.3 | `pg_advisory_lock` no `cmd_up`/`cmd_down` — duas réplicas rodando o job de migration aplicam a mesma migration duas vezes |
| 2.4 | Tirar `BEGIN;`/`COMMIT;` dos 22 arquivos que os trazem — hoje a atomicidade prometida no docstring é falsa e um kill no meio trava o deploy com `relation already exists` |
| 2.5 | `wipe-dados` exige `--confirmo=<nome_do_banco>` e recusa fora de dev. Hoje é `TRUNCATE CASCADE` em 15 tabelas, sem confirmação, na mesma imagem que roda em produção — e com atalho de um clique em `.vscode/tasks.json` |
| 2.6 | Completar os detectores de `bootstrap` (hoje só reconhecem 0001-0004) ou exigir `_migracoes_aplicadas` no dump |
| 2.7 | Marcar 0005/0012/0018 como não-reversíveis: os `.down.sql` apagam linhas. `down --to 0017` perde todo simulado agendado e transforma as senhas dos alunos na senha demo |

#### 5.3 Migração dos dados — **não existe ferramenta hoje**

> **Decisão de 21/08/2026:** backup contínuo **não** é bloqueador de go-live. O Canvas
> guarda todo o histórico e restauração lenta (~3.300 chamadas em série, horas) é
> aceitável. O que segue abaixo continua valendo como ferramenta de **migração**, não
> de backup.

`grep -rni 'pg_dump|pg_restore|backup|restore'` no repo inteiro: zero. O
`migrate.py` sabe criar, reverter e esvaziar schema — não sabe extrair nem
carregar dados.

**Escrever `scripts/exportar.py` e `scripts/importar.py`** (`pg_dump --data-only`
na ordem das FKs + cópia dos objetos de storage com checksum), rodar um ensaio
completo contra um Postgres limpo, e registrar no repo o inventário do que
precisa viajar: tabelas com contagem de linhas + quantidade e tamanho dos
arquivos. Três coisas não têm origem no Canvas e só existem no banco do SAS:
`aluno.senha_hash` (perder = 873 alunos refazendo o primeiro acesso),
`email_invalido` (a lista de supressão de bounces) e `evento_agenda` (o vínculo
entre o simulado agendado e a regra de lembrete). Nenhuma justifica backup
contínuo, mas as três devem viajar no export da migração.

#### 5.4 Exclusão de dado pessoal — **não existe caminho**

Nenhuma rota apaga aluno. Só 5 das ~40 FKs são `ON DELETE CASCADE`, então
`DELETE FROM aluno` falha. Os dados pessoais estão espalhados por `chat_mensagem.conteudo`
(transcrição inteira), `disparo.destinatario`/`corpo`, planilhas brutas no
storage, PDFs, e `aluno.email` vindo do Canvas.

Um pedido de eliminação (LGPD art. 18, V) não tem como ser atendido pelo produto.
O DPO vai pedir esse fluxo antes de aprovar — é a mesma conversa que trava o uso
da LLM. Implementar como operação única: rota autenticada de coordenação ou
função no banco chamada via `/rpc/` do PostgREST.

### Fase 3 — Jobs e e-mail (~3 dias)

Os quatro schedules reais (o `infra/README.md` está desatualizado e lista o path
deprecado `/cobranca/verificar`):

| Rota | Frequência | Header |
|---|---|---|
| `POST /canvas-sync/run` | 5 min | `X-Scheduler-Secret` |
| `POST /alertas/verificar` | 1 h | `X-Scheduler-Secret` |
| `POST /disparos/processar` | 1 h | `X-Scheduler-Secret` |
| `POST /canvas-sync/reconciliar` | diário | `X-Scheduler-Secret` |

| # | Item |
|---|---|
| 3.1 | **Travas em banco.** `canvas_sync/rotas.py:32` e `disparos.py:29` são `threading.Lock()` — travas **de processo**, não de banco. Trocar por advisory lock |
| 3.2 | **Fuso explícito.** Nenhum container define `TZ` → roda UTC. Sete call sites de `date.today()` no caminho de leitura das estatísticas: das 21h à meia-noite BRT, prova de amanhã entra nas médias. E `FUSO_BRASIL` é offset fixo `-3`, não `ZoneInfo` — se o horário de verão voltar, o lembrete das 18:00 sai às 17:00 |
| 3.3 | Contagem de envio do SES é **por processo** (`enviados_24h` lido uma vez e incrementado em memória). Duas réplicas mandam o dobro, ao dobro da taxa — é assim que a conta é suspensa |
| 3.4 | Backoff nos retries: hoje a cadência de retry é a mesma do cron (5 min) e sem espaçamento, então 25 min de Canvas fora queimam as 5 tentativas de todo simulado agendado |
| 3.5 | Segredo do scheduler com rotação sem downtime (aceitar `SCHEDULER_SECRET` + `SCHEDULER_SECRET_ANTERIOR`) |
| 3.6 | Deletar `routes/cobranca.py` e corrigir `infra/README.md` ao desligar a stack CDK |
| 3.7 | Sair do sandbox do SES **ou** trocar por relay do colégio (o que também elimina a transferência internacional de dado pessoal) |

### Fase 4 — Observabilidade e operação (~3 dias)

Hoje: zero `exception_handler`, zero log em `sincronizar.py` (684 linhas),
`despachante.py` (159 linhas), `routes/notas.py` (224 linhas) e em todo o
`auth.py`. Nenhum Sentry, OTel, Prometheus ou `/metrics`.

| # | Item |
|---|---|
| 4.1 | Logging JSON configurado em `create_app()`, nível por env, com request id |
| 4.2 | Exception handler global — hoje o traceback sai órfão, sem rota, sem usuário, e não há ponto único onde contar erro |
| 4.3 | Log de autenticação e trilha de auditoria em tabela (`evento_auditoria`): login ok/falho, primeiro acesso, reset feito pela coordenação, edição de nota. É o art. 37 da LGPD e a resposta para "quem editou essa nota?" |
| 4.4 | **Alerta de "agendador parado"** — o modo de falha mais provável de toda a migração. Se o cron não disparar, a API responde 200 em tudo, `/health` diz ok, e os dados congelam em silêncio. Fazer `/health/ready` degradar sem sync bem-sucedido em 30 min |
| 4.5 | `criar_acesso.py` para de imprimir senha e PII em stdout — num cluster isso vira log retido |
| 4.6 | Métrica no padrão que o colégio já operar (só decidir depois de saber qual é) |

---

## 6. As dez decisões do colégio — e o que cada resposta custa

### 6.1 Quantas réplicas? → **hoje a resposta obrigatória é 1**

Três coisas são estado de processo e quebram com N réplicas:

1. Travas do sync e do despachante (`threading.Lock`) — §3.1
2. Rate limit de login em dict de memória ([auth.py:36-57](../api/app/routes/auth.py#L36-L57)) — vira 5×N tentativas, e zera a cada restart
3. Teto e ritmo de envio do SES — §3.3

Depois da Fase 3 isso deixa de ser verdade. **Antes dela, "1 réplica, 1 worker"
precisa estar dito por escrito ao time de plataforma.**

### 6.2 PostgREST é aceitável? → é a pergunta que decide o escopo

Se a resposta for "não, só entregamos Postgres gerenciado", o custo é **reescrever
a camada de dados**: ~210 call sites de `cliente.table(...)`. É decisão de escopo
de projeto, não de configuração. Vale insistir no arranjo sidecar (PostgREST no
mesmo pod da API, sem Service) antes de aceitar a reescrita.

### 6.3 SSO corporativo? → se sim, entra no escopo agora

Hoje a coordenação é **uma credencial única em variável de ambiente**, sem hash,
sem MFA, sem rastro de quem entrou, e o `/auth/login` **não tem rate limit** (o
limitador só cobre `/auth/primeiro-acesso`). Isso não passa em revisão de
segurança nem em avaliação de LGPD.

Pior: `settings.coordenador_email` também vira **dado** — é gravado em
`evento_agenda.criado_por` e usado como Reply-To de todo e-mail a aluno. Trocar
depois não corrige o histórico.

Mesmo sem SSO, o mínimo é tabela de usuários de coordenação com PBKDF2 (o código
de hash já existe em `auth.py:32-59`).

### 6.4 LLM externa aprovada pelo DPO? → o inventário de dados é maior do que parece

Não sai só "nota". Saem **enunciados completos e gabaritos** das provas do colégio
(propriedade intelectual, e provas que podem ser reaplicadas) e as **respostas
individuais do aluno**, ligadas ao nome dele que já está no system prompt.

Se o DPO exigir provedor nacional: **Azure OpenAI é quase de graça** — falta só
`base_url` configurável (meia hora). Qualquer coisa que não fale o dialeto da
OpenAI (Bedrock nativo, Gemini) exige reescrever o loop de tool-calling e o
formato já persistido em `chat_mensagem.tool_calls`.

Também não há rate limit nem teto de custo no chat: 873 alunos e nada entre um
script e a fatura.

### 6.5 API pública ou só rede interna?

Se ficar atrás de VPN, o agendador externo não alcança e os 4 jobs viram cron
interno. **Mas há uma exceção que não dá para esconder:** o webhook do SNS
(`POST /email/eventos-ses/{token}`) precisa ser alcançável pela AWS. É o único
endpoint que não dá para proteger por header custom nem por VPN — e é o mesmo
com o SSRF da §4.2. Se o e-mail migrar para relay do colégio, o problema some.

### 6.6 Demais

| Pergunta | O que muda |
|---|---|
| Nuvem-mãe / caminho pavimentado | Define registry, pipeline e formato do CronJob |
| Migrations em produção | Precisa de janela e credencial de dono do schema; **e restart do PostgREST depois de cada uma** (§ abaixo) |
| Backup e restore | Baixa prioridade: o Canvas é arquivo completo e restauração lenta é aceitável (decidido 21/08). Ver §5.3 |
| Conta de serviço do Canvas | Token hoje é pessoal e já tem poder de escrita e de nota. Pedir conta de serviço com escopo mínimo + ambiente de homologação |
| WhatsApp (fora de escopo, mas na fila) | Z-API é não-oficial e pendura o serviço num celular físico com risco de banimento. Provavelmente inaceitável — a alternativa é WhatsApp Business API via BSP |

> **Schema cache do PostgREST.** Ele lê o schema uma vez, no boot. O runner já
> emite `NOTIFY pgrst`, mas isso só funciona se o PostgREST mantiver um `LISTEN`
> em conexão persistente — **se houver PgBouncer em transaction mode no caminho,
> o LISTEN é descartado** e o reload nunca chega. O passo pós-migration no runbook
> tem que ser NOTIFY **e** restart (o restart é idempotente e cobre os dois casos).

---

## 7. Correções na pauta antes da reunião

A seção "o que já vai pronto do nosso lado" do
[`perguntas-infra-producao.pdf`](../perguntas-infra-producao.pdf) faz quatro
afirmações que o código contradiz. Levá-las como estão custa credibilidade com o
time de plataforma na primeira pergunta técnica.

| Pauta diz | Código diz |
|---|---|
| "o sync já coordena por trava em banco, então disparo duplicado não corrompe nada" | `_trava_execucao = threading.Lock()` ([rotas.py:32](../api/app/canvas_sync/rotas.py#L32)) — trava **de processo**. Duas réplicas ou 2 workers e a coordenação some |
| "imagem de produção… rodando como usuário não-root" *(com o comentário do Dockerfile: "a API só escreve em storage remoto, nunca em disco local")* | Ao sair do Supabase Storage, o modo filesystem passa a ser o caminho principal. Sem volume com owner uid 10001, ou o upload falha, ou os PDFs somem no primeiro restart |
| "guard de boot que recusa subir com segredo default" | Só roda se `APP_ENV` for explicitamente ≠ dev/test, e o default é `dev` (§4.1). Falha aberto |
| "configuração 100% por variável de ambiente" | A URL da API está hardcoded no JavaScript ([http-client.js:10-12](../web/js/services/http-client.js#L10-L12)). Sem build step, não há mecanismo de injeção |

Sugestão: corrigir as quatro na pauta e transformá-las em compromissos da Fase 0/1
("vai estar pronto até o deploy"), o que é verdade e é mais forte do que uma
afirmação que não se sustenta.

---

## 8. Sequenciamento e esforço

| Fase | Conteúdo | Esforço | Depende do colégio? |
|---|---|---|---|
| **0** | Guard de boot, SSRF, race de alertas, teto de e-mail, CVEs | ~3 dias | Não |
| **1** | Mesma origem, PostgREST fechado, headers, fontes locais | ~4 dias | Topologia (§2) |
| **2** | Papéis, grants, lock, export/import, ensaio de restore | ~4 dias | Versão e collation do PG |
| **3** | Travas em banco, fuso, cron, SES | ~3 dias | Agendador e provedor de e-mail |
| **4** | Log, auditoria, alerta de agendador parado | ~3 dias | Stack de observabilidade deles |
| **5** | Ensaio de ponta a ponta + go-live | ~3 dias | Janela |

**~4 semanas de trabalho de código.** A Fase 0 e boa parte da 2 (export/import)
não dependem de resposta nenhuma e devem começar já. As demais destravam conforme
as respostas chegarem.

> A imagem `--target prod` **nunca foi exercitada num deploy real** — o Render
> rodava `runtime: python`, um terceiro caminho. E o único ensaio de produção do
> repo (`docker-compose.prod.yml`) **não sobe hoje**, porque o `.env` não tem
> `JWT_SECRET_KEY` nem `COORDENADOR_SENHA`. Consertar isso é o primeiro passo da
> Fase 5, não o último.

---

## 9. Checklist de go-live

**Pré-requisitos de plataforma**
- [ ] Postgres ≥ 15, collation definida, `sslmode=require`
- [ ] PostgREST em rede interna, com JWT, papel anônimo sem privilégio
- [ ] Volume persistente para PDFs com owner uid 10001 (ou bucket)
- [ ] Domínio + TLS; decisão de mesma origem vs. hosts separados
- [ ] `client_max_body_size` ≥ 25 MB e `proxy_read_timeout` ≥ 300 s na rota de chat (SSE)
- [ ] Faixa de IP do ingress para `--forwarded-allow-ips`
- [ ] Allowlist de saída: Canvas, OpenAI, SES/SNS
- [ ] 4 CronJobs com fuso declarado

**Pré-requisitos de código**
- [ ] Fase 0 inteira aplicada
- [ ] `requirements.lock` com hashes; imagem escaneada sem CVE crítica
- [ ] Smoke test da imagem `prod` passando (inclusive upload e download de PDF por browser real)
- [ ] Ensaio de export → import contra Postgres limpo, com contagem de linhas conferida
- [ ] Teste de SSE atravessando o proxy real (`curl -N`)

**Segredos a gerar e guardar no cofre do colégio** (nunca reaproveitar os do `.env` do dev)
- [ ] `JWT_SECRET_KEY` · `COORDENADOR_SENHA` · `SCHEDULER_SECRET` · `POSTGREST_TOKEN` + `PGRST_JWT_SECRET`
- [ ] `CANVAS_API_TOKEN` (conta de serviço nova) · `OPENAI_API_KEY` · credencial de e-mail
- [ ] `SES_WEBHOOK_TOKEN` · `LEMBRETE_TOKEN_SECRET`
- [ ] `EMAIL_DESTINATARIO_TESTE` **vazia** · `EMAIL_REMETENTE` institucional (não gmail pessoal)

**Rollback**: é **restore de dump**, não `migrate down`. Registrar isso no runbook —
`down --to 0017` apaga agendamentos e reseta senhas de alunos.

---

## 10. Dívida que fica, conscientemente

Itens reais que **não** bloqueiam o go-live, mas devem ser ditos em voz alta para
não virarem surpresa:

- **Sem paginação em lugar nenhum.** O teto de 1000 linhas era configuração do
  Supabase, não do PostgREST. Num PostgREST próprio, leituras que hoje truncam
  passam a devolver tudo — fixar `PGRST_DB_MAX_ROWS` explicitamente e paginar
  `nota`, `v_nota_dimensoes` e `questao_resposta_aluno`.
- **Escritas multi-tabela sem transação** — custo estrutural de o backend nunca
  escrever SQL. Um `evento_agenda` órfão não é mostrado por nenhuma tela nem
  limpo por nenhum job.
- **`ciclo` tem `UNIQUE (ano_letivo_id, ordem)`** e não comporta "3º Ciclo ITA" e
  "3º Ciclo IME" no mesmo ano — o upsert **sobrescreve** em vez de duplicar.
  Corrupção silenciosa. Corrigir agora, com 148 simulados, é infinitamente mais
  barato do que depois.
- **Sem revogação de sessão**: trocar senha ou desativar aluno não derruba tokens
  já emitidos (valem 8 h).
- **"Primeiro acesso" é também "esqueci a senha"** e reseta com matrícula +
  e-mail, sem prova de posse. Matrícula é o SIS User ID, que circula em lista de
  chamada.
- **Sem cache busting** nos `.js`/`.css` e sem tratamento global de erro no
  frontend: um deploy parcial deixa a coordenadora em "Carregando…" para sempre,
  sem nada registrado em lugar nenhum.
- **Limiares de alerta nunca calibrados** com dado real ([06-open-questions.md §5](06-open-questions.md)).
- **Sem testes** de auth, storage, ingest ou integrações; sem CI. Numa entrega
  para um time que não escreveu o código, é o que garante que as correções não
  sejam desfeitas.
- **`docs/00-tech-stack.md` e o README descrevem um sistema que não existe mais**
  (Vercel, Supabase, 8 migrations). São os dois primeiros arquivos que um time
  novo abre — reescrever antes do handover.
