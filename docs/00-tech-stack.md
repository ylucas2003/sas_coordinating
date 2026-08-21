## 00 — Stack técnico

Decisões técnicas fechadas para começar a implementação. Atualizar este documento sempre que uma escolha for revisitada.

## Visão geral

```
sas/
├── docs/   → documentação (este arquivo e os demais .md)
├── web/    → frontend — HTML + CSS + JavaScript puro (Vercel)
└── api/    → backend — Python + FastAPI + Supabase
```

Monorepo simples baseado em pastas, sem ferramenta de workspaces. Frontend e backend evoluem independentes; o contrato entre eles é a API REST descrita pelo OpenAPI gerado pelo FastAPI.

## Frontend (`/web`)

| Camada | Escolha | Por quê |
|--------|---------|---------|
| Framework | **React 19** | As telas grandes (painel, chat) reimplementavam à mão reconciliação de DOM, estado derivado e cache — as três coisas que o React já resolve. |
| Build | **Vite** | Dev server com HMR e build com assets hasheados, que é o que permite cachear o front (antes nada tinha hash, então nada podia ser cacheado). |
| Linguagem | **TypeScript** | O contrato com a API vive em [src/tipos/dominio.ts](../web/src/tipos/dominio.ts) e espelha os schemas Pydantic. Erro de campo (`turmaId` vs `turma_id`) passa a aparecer no build, não em runtime. |
| Roteamento | **React Router**, caminhos reais | `/alunos/A023`, não `#/alunos/A023`. Exige `try_files` com fallback no nginx — seguro porque todo asset real mora sob `/assets/`. |
| Dados | **TanStack Query** | Substitui o cache manual de GETs do cliente HTTP e o cache de DOM por rota que existia no bootstrap. |
| Estilização | **CSS Modules + CSS variables** | Tokens semânticos (`--color-navy`, `--color-amber`…) continuam globais em [tokens.css](../web/styles/tokens.css); o CSS de cada tela vira módulo conforme ela migra. |
| Tipografia | **Plus Jakarta Sans**, servida localmente | Saiu do Google Fonts: mandava o IP de aluno menor de idade para o Google, e a CSS de produção a bloqueia. Ver [fontes.css](../web/styles/fontes.css). |
| Gráficos | **SVG escrito à mão** | Sparkline, histograma, heatmap, linha de evolução, anel e barra de comparação — sem lib de gráfico. São funções puras `dados → SVG`, que em JSX ficam mais curtas que no DOM. |
| Testes | **Vitest** sobre `src/dominio/` | Cobre a lógica de domínio (esquemas ITA/IME, médias, filtros, ranking, streaming), não markup. |
| Camada de dados | **`servicos/api.ts`** | Operações tipadas sobre [servicos/http.ts](../web/src/servicos/http.ts) (fetch + auth + SSE + upload com progresso). |

### Estrutura

```
web/
├── index.html              entrada única (o login é rota do SPA)
├── vite.config.ts  tsconfig.json  package.json
├── assets/                 fontes e logos
├── styles/                 CSS global (tokens, base, layout e por tela)
└── src/
    ├── main.tsx            bootstrap: QueryClient + Router + CSS global
    ├── App.tsx             rotas, guard de sessão, chat
    ├── rotas.ts            que sidebar cada rota mostra
    ├── tipos/              dominio.ts (espelha api/app/schemas/domain.py), aluno.ts, chat.ts
    ├── dominio/            regras puras e testadas: painel, simulados, ciclos, chatStream…
    ├── servicos/           http.ts · api.ts · sessao.ts
    ├── hooks/              consultas.ts (leitura) · mutacoes.ts (escrita) · aluno.ts
    ├── componentes/        layout/ · ui/ · filtros/ · dialogos/ · simulados/ · chat/ · aluno/
    ├── telas/              uma pasta por tela
    └── exportacao/         geradores de PDF/PNG/CSV — DOM cru, de propósito (ver LEIA-ME)
```

### Onde ficam as regras de negócio

`src/dominio/` é a parte do frontend que **não** desenha nada: esquema de
colunas do painel por vestibular, fórmulas de média ITA/IME, cross-filtering,
corte por matéria, reducer do streaming do chat. Está separada porque é o que
tem regra de domínio de verdade — e é o que os testes cobrem (`npm test`).

### Convenções

- **Nomes em português**, como no resto do projeto (`telas/`, `servicos/`, `consultas.ts`).
- **Nada de `fetch` em componente.** Leitura passa por um hook de `hooks/consultas.ts`.
- **Classes compartilhadas ficam globais** (`.card`, `.tone-*`, `.nota-badge`, `.btn`); só o CSS de prefixo próprio da tela vira módulo.
- **`async/await` em toda I/O.**
- **Sentence case em UI**, regra do design system (ver [03](03-design-system.md)).

## Backend (`/api`)

| Camada | Escolha | Por quê |
|--------|---------|---------|
| Linguagem | **Python 3.11+** | Pedido do usuário. |
| Framework | **FastAPI 0.115+** | Padrão atual para APIs Python: tipagem com Pydantic, OpenAPI nativo, async. |
| ASGI server | **uvicorn** | Funciona em dev (`--reload`) e em produção. |
| Validação | **Pydantic v2** | Schemas dos endpoints em [api/app/schemas/domain.py](../api/app/schemas/domain.py) — espelham as entidades do frontend e a especificação de [05-data-and-stats.md](05-data-and-stats.md). |
| Banco | **Supabase** (Postgres gerenciado) | Pedido do usuário. Vem com auth, storage e RLS prontos. |
| Cliente Supabase | **`supabase-py` v2** | Acesso ao Postgres + Storage a partir do FastAPI. |
| Armazenamento de arquivos | **Supabase Storage** (default) | Já incluído no Supabase, S3-compatível. Para upload de planilhas. Trocar pelo AWS S3 real é um adapter (`app/storage.py`) caso o usuário queira. |
| Config | **pydantic-settings + .env** | Variáveis em `api/.env`, exemplo em `api/.env.example`. |

### Estrutura

```
api/
├── requirements.txt
├── .env.example
└── app/
    ├── main.py             cria FastAPI, registra routers, CORS
    ├── config.py           carrega .env
    ├── supabase_client.py  singleton lazy
    ├── schemas/domain.py   modelos Pydantic
    └── routes/
        ├── alertas.py
        ├── alunos.py
        ├── simulados.py
        ├── ciclos.py
        └── dimensoes.py    sedes, turmas
```

### Regra de segurança não-negociável

A `SUPABASE_SERVICE_KEY` faz bypass de Row Level Security e **nunca** pode ser exposta no frontend. Toda leitura/escrita passa pelo FastAPI, que aplica autorização explícita e auditoria. Por se tratar de dados de menores de idade (LGPD), o frontend nem deve ter um client direto do Supabase.

Ver decisão pendente #10 em [06-open-questions.md](06-open-questions.md).

### Convenções

- **`async def`** em todos os endpoints.
- **Type hints** em todas as funções.
- **TODOs explícitos** marcando onde a query no Supabase ainda precisa ser escrita (`# TODO(supabase): ...`).
- **Sem ORM por enquanto.** O `supabase-py` já oferece query builder; SQLAlchemy entra se queries muito complexas justificarem.

## Deploy

### Frontend — Vercel (grátis)

O `vercel.json` na raiz aponta `outputDirectory` para `web/`. Não há build — o Vercel serve `web/` como estático. Conectar o repo no painel do Vercel funciona out-of-the-box.

### Backend — fora do Vercel

Vercel suporta funções Python serverless, mas com limites (10s timeout, frio entre requisições) que não combinam com upload de planilhas e cálculo de alertas. Opções gratuitas:

| Plataforma | Notas |
|------------|-------|
| **Render** | `render.yaml` simples; free tier hiberna após 15min de ociosidade |
| **Fly.io** | Sem hibernação; precisa Dockerfile |
| **Railway** | Detecta `requirements.txt`; 500h/mês grátis |

A decisão fica em aberto até a TI do Ari de Sá pesar on-premise vs. nuvem (ver questão 10 em [06](06-open-questions.md)).

### Banco — Supabase (free tier)

Free tier do Supabase: 500 MB Postgres, 1 GB Storage, 2 GB transferência. Suficiente para o piloto.

## Reavaliações conhecidas

- **Bundler / framework no frontend** entra se o JS começar a sofrer com duplicação de lógica entre telas. Sinal: 5+ componentes precisando de mesma helper de estado.
- **TypeScript** entra junto se bundler for adicionado.
- **ORM (SQLAlchemy)** entra se queries via supabase-py ficarem ilegíveis.
- **Celery / RQ** para tarefas assíncronas entra quando a ingestão de planilhas precisar processar arquivo > 1 minuto.
- **Testes** (pytest no back, mocha/playwright no front) entram quando houver lógica não trivial.

Cada uma dessas adições deve atualizar este documento.
