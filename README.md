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
    ├── app/         → código da aplicação (routes, ingest, stats, chat)
    ├── migrations/  → schema versionado (0001…0008), pareadas com .down.sql
    └── scripts/     → migration runner + tasks de manutenção
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
- **Desenvolvedor frontend:** [00](docs/00-tech-stack.md) → [02](docs/02-information-architecture.md) → [03](docs/03-design-system.md) → [04](docs/04-screens.md) + ler [web/](web/)
- **Desenvolvedor backend / dados:** [00](docs/00-tech-stack.md) → [01](docs/01-product-vision.md) → [05](docs/05-data-and-stats.md) + ler [api/](api/)
- **Recém-chegado:** tudo na ordem numérica

## Rodando localmente

**Frontend** (qualquer servidor estático):

```sh
cd web
python3 -m http.server 5173
```

Abre em `http://localhost:5173`. Por padrão, [web/js/services/api.js](web/js/services/api.js) usa o `http-client` apontando para `http://localhost:8000` — suba o backend abaixo, ou troque pelo `mockClient` se quiser navegar só com dados sintéticos.

**Backend** (FastAPI + Supabase):

```sh
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencher SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_DB_URL, OPENAI_API_KEY

# aplicar migrations no banco (ver seção abaixo)
python -m scripts.migrate up

uvicorn app.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Detalhes específicos de cada camada em [api/README.md](api/README.md) e [web/README.md](web/README.md).

## Migrations

Schema versionado em [api/migrations/](api/migrations/). Cada migration tem um par `NNNN_descricao.sql` (UP) e `NNNN_descricao.down.sql` (DOWN). Runner próprio em [api/scripts/migrate.py](api/scripts/migrate.py), que rastreia o estado na tabela `_migracoes_aplicadas` e usa `SUPABASE_DB_URL` do `.env`.

| Versão | O que faz |
|--------|-----------|
| `0001_schema_inicial` | Tabelas-base: `sede`, `turma`, `aluno`, `simulado`, `nota`, `ciclo`, `alerta`, `upload`, cache de métricas e classificação. |
| `0002_views` | View `v_nota_dimensoes` (nota + turma + sede da matrícula ativa) usada pelo recálculo de métricas. |
| `0003_vestibular_e_fase` | `vestibular_alvo` no ciclo + `tipo` no simulado para distinguir Fase 1 (combinada) de Fase 2 (matérias separadas). |
| `0004_fix_metrica_recorte_null` | Conserta a PK de `metrica_simulado` para permitir `recorte_id NULL` no recorte `geral`. |
| `0005_limpar_violacoes_ingest` | Limpeza retroativa das regras de ingestão (colunas órfãs "1 FASE ITA - …" e afins). |
| `0006_metricas_avancadas_e_insights` | Estende `metrica_simulado` (skewness, curtose, P10/P90, moda, bimodalidade) + cria `insight_ciclo` (cache de insights LLM). |
| `0007_insights_tecnico_e_pratico` | Insights em duas linguagens (`pratico` e `tecnico`) + recorte `todas` por fase. |
| `0008_chat_agente` | `chat_thread`, `chat_mensagem`, `chat_artefato` para o chat coordenador ↔ LLM com tools. |

Comandos:

```sh
python -m scripts.migrate status         # lista aplicadas e pendentes
python -m scripts.migrate up             # aplica todas pendentes
python -m scripts.migrate up --to 0006   # aplica até a versão 0006 (inclusivo)
python -m scripts.migrate down           # reverte só a última
python -m scripts.migrate down --to 0005 # reverte tudo acima de 0005 (exclusivo)
python -m scripts.migrate bootstrap      # marca como aplicadas migrations já rodadas via dashboard
python -m scripts.migrate wipe-dados     # TRUNCATE nas tabelas de dados (mantém schema e seeds)
```

## Tasks de manutenção

Scripts pontuais em [api/scripts/](api/scripts/). Rodar sempre como módulo (`python -m scripts.<nome>`) a partir de `api/`, com o `.venv` ativo.

| Script | Quando rodar |
|--------|--------------|
| [scripts/recalcular_metricas.py](api/scripts/recalcular_metricas.py) | Depois de aplicar a `0006` (ou qualquer migration que mexa em `metrica_simulado`). Reprocessa todos os simulados — idempotente, faz upsert sobre `(simulado_id, recorte_tipo, recorte_id)`. |
| [scripts/limpar_zeros_provaveis_ausencias.py](api/scripts/limpar_zeros_provaveis_ausencias.py) | One-off: aplica retroativamente a regra "2+ zeros no mesmo dia = ausência" em dados ingeridos antes da regra existir. Tem `--aplicar` (sem ele é dry-run). Depois, rodar `recalcular_metricas`. |
| [scripts/limpar_dados_importados.sql](api/scripts/limpar_dados_importados.sql) | SQL usado por `migrate.py wipe-dados`. Esvazia dados de planilha mantendo schema + seed de matérias. |

## Deploy

- **Frontend** — Vercel, estático e grátis. `vercel.json` na raiz já aponta `outputDirectory: web`.
- **Backend** — fora do Vercel (limites do Python serverless não casam com upload de planilhas). Opções recomendadas em [docs/00-tech-stack.md](docs/00-tech-stack.md): Render, Fly.io ou Railway. Decisão final fica em aberto até a TI do colégio pesar on-premise vs. nuvem (questão 10).
- **Banco** — Supabase (free tier).

## Status

- **Backend** funcional: ingest de planilha do Canvas, stats engine (métricas + classificação + alertas), insights via OpenAI (gpt-4o-mini) em duas linguagens, chat com agente (tools curadas sobre o banco), uploads versionados.
- **Frontend** com as telas principais navegáveis (painel, alunos, ficha do aluno, simulados, ficha do simulado, ciclos, ficha do ciclo, importar) + chat embarcado, gráficos próprios (sparkline, histograma, heatmap, linha de evolução).
- **Schema** em 8 migrations aplicadas, todas reversíveis.
- Pontos abertos restantes em [06-open-questions.md](docs/06-open-questions.md).
