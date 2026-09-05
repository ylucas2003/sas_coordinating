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
| `routes/` | 18 routers aqui, mais `chat/`, `canvas_sync/` e `gravacoes_aula/` (22 `include_router` no total). `main.py` registra `arquivos` só com Storage local e `email_eventos` só com `SES_WEBHOOK_TOKEN` preenchido |
| `stats/` | Métricas por simulado em 3 recortes (geral/turma/sede), classificação de aluno, alertas, insights via LLM. **`criterios.py` é a única definição de "quem passou"** — as cinco réguas como dado, avaliador **puro** (sem I/O, testável sem container); `criterios_repo.py` é a metade que toca o banco, para as réguas que a coordenação cria. `thresholds.py` ficou só com **calibração** (janela, percentis, limiares de alerta): se o número tem artigo de edital é regra e mora em `criterios.py`; se fomos nós que escolhemos olhando dados, é calibração |
| `chat/` | Loop de agente com tools. `perfis.py` parametriza por usuário: coordenador tem **30 tools** staff; aluno tem 6 restritas com `aluno_id` injetado do JWT. `navegacao.py` carrega o contexto da tela nos dois sentidos — o preâmbulo do turno (página → chat) e a rota do `navegar_para` (chat → página) |
| `canvas_sync/` | Sincronização com o Canvas LMS — fonte de verdade das notas. `mapeador.py` compõe **e** parseia os nomes de assignment; as duas gramáticas precisam casar |
| `ingest/` | Pipeline de planilha (CSV/XLSX), idempotente por construção |
| `lembretes/` | Motor de e-mail via SES. Disparo é materializado na criação da regra e revalidado antes do envio |
| `banco/` | Banco de questões ITA·IME (docs/22): consultas filtradas, recorrência por tópico, progresso do aluno e listas com dono. **É a única rota que pagina** — e o motivo está escrito em `schemas/banco.py`. As tabelas são a **fonte da verdade**: os JSONs não são versionados, e `scripts/exportar_banco_questoes.py` é a saída (docs/22 §13) |
| `gravacoes_aula/` | Publica a aula gravada do Canvas no YouTube: baixa os dois componentes do BigBlueButton, compõe com o template da marca (ffmpeg), guarda no S3, publica como **não listado** (LGPD — são menores) e pendura a página da aula no módulo certo do Canvas (`0035`, `0036`); a coordenação acompanha em `/integracoes/aulas`. A gravação some do Canvas em ~7 dias, então o cron roda de hora em hora. Estados `publicado`/`publicado_sem_confirmacao` são TERMINAIS: reprocessar geraria segunda cópia no canal |
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

49 em [migrations/](migrations/), cada uma com par `.down.sql`. Runner próprio,
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
./.venv/bin/python -m pytest tests/ -q   # 530 testes (+15 pulados)
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
