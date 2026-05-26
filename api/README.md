## SAS · api

Backend da interface de coordenação ITM. **FastAPI + Supabase**.

> **Status:** scaffold inicial. As rotas existem com schemas Pydantic corretos, mas todas devolvem listas vazias / 404 — as queries no Supabase serão implementadas quando o banco for criado. Ver decisões pendentes 2, 3, 9, 10 e 11 em [../docs/06-open-questions.md](../docs/06-open-questions.md).

## Rodar localmente

```sh
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencher com credenciais reais quando existir Supabase

uvicorn app.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- OpenAPI / Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Estrutura

```
api/
├── requirements.txt
├── .env.example
└── app/
    ├── main.py             cria FastAPI, registra routers, CORS
    ├── config.py           carrega .env via pydantic-settings
    ├── supabase_client.py  singleton lazy do client Supabase
    ├── schemas/
    │   └── domain.py       modelos Pydantic — espelham os tipos do frontend
    └── routes/
        ├── alertas.py
        ├── alunos.py
        ├── simulados.py
        ├── ciclos.py
        └── dimensoes.py    sedes e turmas
```

## Por que FastAPI

- Tipagem com Pydantic — bate com o estilo do projeto (frontend também tipado via JSDoc).
- OpenAPI gerado automaticamente — o frontend pode regerar o `http-client.js` a partir do schema quando começarmos a implementar de verdade.
- Performance assíncrona — relevante quando o pipeline de upload de planilhas crescer.

## Como o Supabase entra

O cliente é singleton lazy ([app/supabase_client.py](app/supabase_client.py)). Cada rota faz `client = get_supabase()` e executa queries via `client.table("alunos").select(...)`.

**Regra crítica de segurança:** a `SUPABASE_SERVICE_KEY` dá bypass de Row Level Security e nunca pode ser exposta no frontend. Toda leitura/escrita acontece neste backend, que aplica autorização explícita. Ver decisão pendente #10 em [../docs/06-open-questions.md](../docs/06-open-questions.md).

## Storage (Supabase Storage / S3)

Default: **Supabase Storage** (S3-compatível, vem junto do projeto). Upload de planilhas vai para o bucket configurado em `STORAGE_BUCKET`.

Se for necessário usar AWS S3 mesmo, descomentar as variáveis `AWS_*` no `.env` e implementar um adapter — a interface de upload fica isolada num módulo `app/storage.py` quando virar uma necessidade.

## Deploy

Não fica no Vercel. Opções recomendadas (todas com tier gratuito):

- **Render** — `render.yaml` com `python -m uvicorn app.main:app`, free tier hiberna após 15min de ociosidade
- **Fly.io** — `fly.toml` + Dockerfile, sem hibernação
- **Railway** — detecta `requirements.txt` automaticamente, free tier de 500h/mês

A decisão final fica em aberto até saber se a TI do Ari de Sá prefere on-premise (questão 10).
