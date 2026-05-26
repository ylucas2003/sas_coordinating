## SAS — Interface de coordenação ITM · Colégio Ari de Sá

Ferramenta web para a coordenação analisar o desempenho dos alunos das turmas ITM (turmas voltadas a vestibulares militares e altamente competitivos como ITA e IME) em simulados e ciclos de provas.

Substitui o cruzamento manual de planilhas que a coordenação faz hoje, e — mais importante — **sinaliza proativamente o que merece atenção**, em vez de obrigar o coordenador a saber o que procurar.

## Posicionamento

A interface deve parecer **ferramenta analítica e investigativa**, não ERP escolar, painel administrativo ou dashboard financeiro genérico. A ambição é de sistema de acompanhamento pedagógico e central de tomada de decisão.

## Estrutura do repositório

```
sas/
├── docs/   → toda a documentação (visão de produto, design system, telas, dados)
├── web/    → frontend — HTML + CSS + JavaScript puro (Vercel)
└── api/    → backend — Python + FastAPI + Supabase
```

## Documentação

Toda a documentação fica em [docs/](docs/). Comece pelo índice:

| Arquivo | Para quê serve | Para quem |
|---------|----------------|-----------|
| [00-tech-stack.md](docs/00-tech-stack.md) | Decisões de stack, estrutura de pastas, convenções | Desenvolvimento |
| [01-product-vision.md](docs/01-product-vision.md) | Visão de produto, princípios, usuários | Todos |
| [02-information-architecture.md](docs/02-information-architecture.md) | Navegação, hierarquia, decisões arquiteturais | Design, produto |
| [03-design-system.md](docs/03-design-system.md) | Paleta, tipografia, regras visuais, biblioteca de gráficos | Design, frontend |
| [04-screens.md](docs/04-screens.md) | Especificação detalhada de cada tela | Design, frontend |
| [05-data-and-stats.md](docs/05-data-and-stats.md) | Métricas, alertas, classificações de aluno | Backend, dados |
| [06-open-questions.md](docs/06-open-questions.md) | Decisões pendentes para validação | Produto |
| [07-glossary.md](docs/07-glossary.md) | Vocabulário do domínio | Todos |

## Por onde começar

- **Stakeholder de negócio:** README + [01-product-vision.md](docs/01-product-vision.md)
- **Designer:** [01](docs/01-product-vision.md) → [02](docs/02-information-architecture.md) → [03](docs/03-design-system.md) → [04](docs/04-screens.md)
- **Desenvolvedor frontend:** [00](docs/00-tech-stack.md) → [02](docs/02-information-architecture.md) → [03](docs/03-design-system.md) → [04](docs/04-screens.md) + ler `web/`
- **Desenvolvedor backend / dados:** [00](docs/00-tech-stack.md) → [01](docs/01-product-vision.md) → [05](docs/05-data-and-stats.md)
- **Recém-chegado:** tudo na ordem numérica

## Rodando localmente

**Frontend** (qualquer servidor estático):

```sh
cd web
python3 -m http.server 5173
```

Abre em `http://localhost:5173`. Os dados vêm de mocks em [web/js/services/mock-data.js](web/js/services/mock-data.js) enquanto o backend não existe.

**Backend** (opcional — só faz sentido depois do Supabase configurado):

```sh
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

OpenAPI em `http://localhost:8000/docs`.

## Deploy

- **Frontend** — Vercel, estático e grátis. `vercel.json` na raiz já aponta `outputDirectory: web`.
- **Backend** — fora do Vercel (limites do Python serverless não casam com upload de planilhas). Opções recomendadas no [docs/00-tech-stack.md](docs/00-tech-stack.md): Render, Fly.io ou Railway. Decisão final fica em aberto até a TI do colégio pesar on-premise vs. nuvem (questão 10).
- **Banco** — Supabase (free tier).

## Status

Documentação consolidada da fase de descoberta e design conceitual. Frontend navegável entre as 4 telas principais com dados mockados. Backend com scaffold das rotas, esperando definição do schema no Supabase. Antes de avançar para implementação real, validar os pontos abertos em [06-open-questions.md](docs/06-open-questions.md).
