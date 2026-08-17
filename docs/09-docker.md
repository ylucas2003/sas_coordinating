# 09 · Docker

Como o SAS roda em container — em dev e em produção.

## O que está dentro e o que ficou fora

| Peça | Container? | Motivo |
|------|-----------|--------|
| `api/` (FastAPI) | **sim** | É o serviço de runtime. Imagem multi-stage com alvos `dev` e `prod`. |
| `web/` (estático) | **sim** | nginx servindo os arquivos crus. Não há build step. |
| `db` (Postgres 16) | **sim** | Banco local. Volume nomeado `db-dados`. |
| `postgrest` | **sim** | Traduz HTTP→SQL. É o que o backend realmente consome — ver abaixo. |
| `scripts/migrate.py` | **sim**, one-shot | Reaproveita a imagem da API (precisa de `psycopg` e de `migrations/`). |
| `infra/` (AWS CDK) | **não** | É ferramenta de deploy, roda na sua máquina ou na CI — não é serviço. |
| `api/grading_prototype/` | **não** | Script ad-hoc, não serviço. Roda dentro do container da API quando precisar. |

### Por que `db` + `postgrest`, e não só um Postgres

O backend nunca escreve SQL. Ele monta requisições HTTP que o **PostgREST** converte em
SQL — os ~210 `cliente.table(...)` do projeto são chamadas de rede, não queries. O
Supabase hospeda um PostgREST; a stack local sobe outro. Por isso um `postgres:16`
sozinho não resolveria, mas o par resolve **sem tocar em nenhum call site**.

O que muda é só o ponto de entrada, em dois arquivos:

| | Supabase hospedado | Stack local |
|---|---|---|
| Dados | `supabase-py` → PostgREST da Supabase | `postgrest-py` → serviço `postgrest` |
| Storage | bucket do Supabase Storage | filesystem em `STORAGE_DIR` |
| Chave | `SUPABASE_SERVICE_KEY` | papel `sas_service` (sem JWT em dev) |

Ver [api/app/supabase_client.py](../api/app/supabase_client.py) e
[api/app/storage.py](../api/app/storage.py). O modo é escolhido por env: com
`POSTGREST_URL` preenchida vale a stack local; sem ela, o Supabase. O compose já injeta
as duas variáveis, então `docker compose up` é local por default.

## Dev

```sh
docker compose up
docker compose run --rm migrate up      # primeira vez: cria o schema
docker compose restart postgrest        # ver "cache de schema" abaixo
```

| Serviço | Onde | Observação |
|---------|------|------------|
| `api` | `http://localhost:8000` | `--reload` ligado, `./api` montado como volume |
| `web` | `http://localhost:8080` | `./web` montado read-only |
| `postgrest` | `http://localhost:3000` | loopback só; dá pra chamar no `curl` direto |
| `db` | `localhost:5432` | loopback só; user `postgres`, senha `postgres`, base `sas` |
| `migrate` | — | profile `tools`, não sobe com `up` |

As tasks do VS Code ([.vscode/tasks.json](../.vscode/tasks.json)) rodam via compose.
`SAS: rodar tudo` é a task de build default, então **Cmd+Shift+B** sobe a stack inteira.

O banco e o PostgREST ficam presos em `127.0.0.1` de propósito: o projeto não usa RLS
(nenhuma migration cria policy) e o papel `sas_service` tem acesso total ao schema, então
expor essas portas na rede seria expor o banco inteiro. Toda autorização real está no
FastAPI — o mesmo desenho que a service key do Supabase já tinha.

Segredos vêm de `api/.env` (`env_file` no compose). O compose sobrescreve:

- `APP_ENV=dev` — desliga o guard de boot do [api/app/main.py](../api/app/main.py).
- `CORS_ALLOW_ORIGINS` — inclui `http://localhost:8080`. Necessário porque o front é
  servido em `:8080` e o [http-client.js](../web/js/services/http-client.js) chama a API
  em `:8000`; portas diferentes são origens diferentes pro browser.
- `POSTGREST_URL`, `STORAGE_DIR`, `API_BASE_URL` — ligam o modo local.
- `SUPABASE_DB_URL` (só no `migrate`) — aponta o runner para o `db` local.

### Migrations

```sh
docker compose run --rm migrate status
docker compose run --rm migrate up
docker compose run --rm migrate down --to 0016
```

#### Cache de schema

O PostgREST lê o schema **uma vez, ao subir**. Depois de qualquer migration que crie ou
altere tabela/coluna/FK, recarregue:

```sh
docker compose restart postgrest
```

Sem isso a coluna nova volta `404 column does not exist` mesmo estando no banco. É o
sintoma mais comum de "mas eu acabei de rodar a migration".

Tabelas criadas depois já nascem com permissão para o `sas_service` graças ao
`ALTER DEFAULT PRIVILEGES` em
[infra/postgres/init/01-papeis.sh](../infra/postgres/init/01-papeis.sh). Esse script roda
uma única vez, na criação do volume — se precisar mexer nele, `docker compose down -v`.

### Storage local

Arquivos vão para `.dados/storage/` na raiz do repo (bind mount, gitignored) — dá pra
abrir os PDFs no Finder. As keys gravadas em `upload.caminho_storage` e
`simulado.arquivo_storage` são as mesmas dos dois backends, então trocar de modo não
invalida linha nenhuma; só muda de onde os bytes são lidos.

O download continua sendo link assinado de curta duração: no Supabase é a signed URL do
bucket, aqui é `GET /arquivos/download?token=<jwt>`
([api/app/routes/arquivos.py](../api/app/routes/arquivos.py)). Essa rota só é registrada
quando `STORAGE_DIR` está setada.

### Voltando para o Supabase hospedado

Remova `POSTGREST_URL` e `STORAGE_DIR` do serviço `api` no compose (ou rode a API fora
dele com um `.env` sem essas variáveis). Nenhuma alteração de código é necessária.

### Comandos avulsos dentro do container

```sh
docker compose exec api python -m scripts.recalcular_metricas
docker compose exec api sh
```

O protótipo de correção discursiva precisa de uma dep extra (`Pillow`), que
propositalmente não está na imagem:

```sh
docker compose exec api pip install -r grading_prototype/requirements.txt
```

## Produção

A imagem `prod` é imutável (código copiado, sem volume, sem `--reload`) e roda como
usuário não-root `sas` (uid 10001). Ela escuta em `$PORT` quando a plataforma injeta a
variável — que é o contrato de Render, Cloud Run e Fly.

```sh
docker build --target prod -t sas-api ./api
docker build -t sas-web ./web
```

`UVICORN_WORKERS` default é **1**, de propósito: o `canvas_sync` coordena por trava em
banco e o chat streama SSE. Aumentar só depois de validar esses dois caminhos com
concorrência real.

### Testando a imagem de produção localmente

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

Isso roda com `APP_ENV=production`, o que **ativa o guard de boot**: a API se recusa a
subir se `JWT_SECRET_KEY` ou `COORDENADOR_SENHA` estiverem nos defaults de dev. Hoje
nenhuma das duas está em `api/.env`, então esse comando falha até você adicioná-las.
Isso é o guard funcionando — e é exatamente a classe de erro que esse override existe
pra pegar antes do deploy.

### Deploy atual

O [render.yaml](../render.yaml) ainda usa `runtime: python`, não Docker. Trocar é opção,
não obrigação — bastaria `runtime: docker` + `dockerfilePath: ./api/Dockerfile` +
`dockerContext: ./api` no serviço `sas-api`. Deixado como está pra não mexer no deploy
que está de pé.
