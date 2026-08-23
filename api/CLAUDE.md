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
| `routes/` | 13 routers aqui, mais `chat/` e `canvas_sync/` (15 `include_router` no total). `main.py` registra `arquivos` só com Storage local e `email_eventos` só com `SES_WEBHOOK_TOKEN` preenchido |
| `stats/` | Métricas por simulado em 3 recortes (geral/turma/sede), classificação de aluno, alertas, thresholds, insights via LLM. **`criterios.py` é a única definição de "quem passou"** — réguas do colégio, ITA e IME como dado, avaliador puro; o front não reimplementa |
| `chat/` | Loop de agente com tools. `perfis.py` parametriza por usuário: coordenador tem 26 tools staff; aluno tem tools restritas com `aluno_id` injetado do JWT |
| `canvas_sync/` | Sincronização com o Canvas LMS — fonte de verdade das notas. `mapeador.py` compõe **e** parseia os nomes de assignment; as duas gramáticas precisam casar |
| `ingest/` | Pipeline de planilha (CSV/XLSX), idempotente por construção |
| `lembretes/` | Motor de e-mail via SES. Disparo é materializado na criação da regra e revalidado antes do envio |
| `banco/` | Banco de questões ITA·IME (docs/22): consultas filtradas, recorrência por tópico e listas com dono. **É a única rota que pagina** — e o motivo está escrito em `schemas/banco.py`. As tabelas são a **fonte da verdade**: os JSONs não são versionados, e `scripts/exportar_banco_questoes.py` é a saída (docs/22 §13) |
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

Três tipos de credencial, um JWT (HS256, 8h) — [app/auth.py](app/auth.py):

- **Aluno**: matrícula + senha PBKDF2-HMAC-SHA256 (formato versionado).
- **Coordenador**: e-mail + senha na tabela `usuario_coordenacao` (0021). A
  credencial de env não é mais lida pelo login; contas nascem pelo painel
  `/administracao` ou por `scripts/criar_coordenador.py`.
- **Canvas (aluno e coordenador)**: OAuth2 por redirect, `routes/auth_canvas.py`.
  O Canvas diz *quem é*; o banco decide *quem entra* — identidade sem linha em
  `aluno`/`usuario_coordenacao` é recusada. Precisa de `CANVAS_CLIENT_ID` /
  `CANVAS_CLIENT_SECRET` (Developer Key, OUTRA credencial que não o token).
- **Scheduler** (EventBridge): segredo compartilhado no header
  `X-Scheduler-Secret`, não JWT.

O autosserviço de primeiro acesso (`PRIMEIRO_ACESSO_AUTOSSERVICO`) está
**desligado** e o motivo está comentado em [app/config.py](app/config.py):
valida só matrícula + e-mail, ambos deriváveis — quem souber os dois toma a
conta. Não religue sem código de uso único por e-mail.

## Custo de LLM

Há teto por usuário porque já houve o susto: sem limite, o pior caso medido foi
**US$ 379 numa hora**. `CHAT_LIMITE_MENSAGENS_HORA` e
`CHAT_LIMITE_TOKENS_DIA` em [app/config.py](app/config.py). Modelo default é
`gpt-4o-mini` nos dois perfis — o fallback invertido que ligava o gpt-4o (16x
mais caro) ao configurar o modelo barato já foi consertado; não reintroduza
inferência de modelo a partir de substring do nome.

## Migrations

27 em [migrations/](migrations/), cada uma com par `.down.sql`. Runner próprio,
estado em `_migracoes_aplicadas`.

```sh
docker compose run --rm migrate status
docker compose run --rm migrate up
docker compose restart postgrest     # OBRIGATÓRIO depois de mexer em tabela
```

Depois de qualquer migration que toque `metrica_simulado`, rode
`python -m scripts.recalcular_metricas` (idempotente).

## Ferramentas

```sh
./.venv/bin/python -m pytest tests/ -q   # 120 testes
./.venv/bin/ruff check .                 # lint — configurado em pyproject.toml
./.venv/bin/ruff check . --fix
./.venv/bin/mypy app                     # sob demanda, fora do gate
```

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

- `async def` em todos os endpoints, type hints em todas as funções.
- Nomes em português, inclusive colunas de banco.
- Comentário explica o porquê e cita a fonte (`docs/14 §4.1`).
- Erro em caminho de auditoria ou telemetria é engolido; erro em caminho de
  dado, não.
