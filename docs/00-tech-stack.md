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
| Linguagem | **HTML + CSS + JavaScript puro (ES modules)** | Sem bundler, sem transpilador, sem `node_modules`. Deploy estático no Vercel sai grátis e instantâneo. Toda a stack roda direto no navegador. |
| Tipagem | **JSDoc opcional** | Sem TypeScript. Tipos críticos (entidades do domínio) documentados via JSDoc no `services/api.js`. |
| Roteamento | **Hash router próprio** ([js/router.js](../web/js/router.js)) | ~30 linhas, suficiente para o app. Hash routing dispensa rewrite no Vercel. |
| Estilização | **CSS vanilla + CSS variables** | Tokens semânticos (`--color-navy`, `--color-amber`…) batem com o princípio "cor é linguagem". Três arquivos: [tokens.css](../web/styles/tokens.css), [base.css](../web/styles/base.css), [layout.css](../web/styles/layout.css). |
| Tipografia | **Plus Jakarta Sans** via Google Fonts | Já em uso nos mockups e no design system. |
| Gráficos | **SVG primitives escritos à mão** | Sparkline já está em [components/ui/sparkline.js](../web/js/components/ui/sparkline.js). Histograma, heatmap, etc. seguem a mesma abordagem (~50 linhas cada). Sem libs de gráfico. |
| Camada de dados | **`ApiClient` interface** ([services/api.js](../web/js/services/api.js)) | Hoje aponta para `mockClient`; quando o backend estiver pronto, trocar para `httpClient`. As telas não mudam. |

### Estrutura

```
web/
├── index.html              entry point
├── styles/                 tokens, reset, layout
└── js/
    ├── main.js             bootstrap (router + render)
    ├── router.js           hash router
    ├── dom.js              helpers (el, clear, fmtNota)
    ├── services/
    │   ├── api.js          contrato — getApiClient() escolhe mock vs HTTP
    │   ├── mock-client.js
    │   ├── mock-data.js
    │   └── http-client.js  placeholder do client real
    ├── components/
    │   ├── topbar.js
    │   ├── filter-strip.js
    │   ├── sidebar.js
    │   └── ui/             alert-card, sparkline, …
    └── screens/            painel, alunos, aluno-ficha, simulados, …
```

### Convenções

- **ES modules** com extensão `.js` nas importações (`import { x } from './x.js'`) — navegadores exigem.
- **Sem build step.** Editar e recarregar.
- **`async/await` em toda I/O.** O contrato com o backend já é assíncrono (`Promise`).
- **`document.createElement`** via helper `el()` em vez de `innerHTML` — protege contra XSS por default.
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
