# captacao-externa — achar potencial aluno cruzando resultado de prova pública

Pipeline que raspa lista pública de premiado/aprovado de olimpíada, vestibular
ou concurso, e alimenta `conquista_externa`/`candidato_externo` no SAS — pra
achar gente de fora do colégio que já provou que é boa antes de a coordenação
nunca ter ouvido falar dela.

**O plano — por que isto existe, o modelo de dados, a régua de match, o
estado atual com números reais e o que ainda falta (backend + tela) — está
em [docs/41-plano-captacao-externa.md](../docs/41-plano-captacao-externa.md).
Este README é só o operacional: como rodar o que já existe.**

⚠️ **As conquistas não moram aqui.** `dados/*.json` existe em disco e **não é
versionado** — é onde o scraper escreve e de onde o importador lê, mesmo
raciocínio do `questoes_json/` do `banco-questoes/`. Quem guarda de verdade é
o Postgres (`conquista_externa`, `candidato_externo`).

## Por que isto não mora em `api/`

Mesmo motivo do `banco-questoes/`: o pipeline não roda em requisição nenhuma
— ele baixa página externa e faz parsing de HTML, com `requests`/`bs4`/`lxml`
num venv próprio. O que roda a partir de `api/` é só a importação e a
resolução de identidade (`api/scripts/importar_captacao_externa.py` e
`api/scripts/resolver_candidatos_externos.py`), que falam com o banco via
PostgREST — nunca SQL direto, mesma regra do resto do backend.

## O que tem aqui

```
captacao-externa/
├── requirements.txt         requests, beautifulsoup4, lxml
├── pipeline/
│   └── obmep.py              1º scraper — Ouro/Prata/Bronze nacional, 2022-2025
└── dados/                    JSON cru por edição — NÃO VERSIONADO
    └── obmep_2025.json
```

## Setup

```sh
cd captacao-externa
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## O fluxo de "acrescentar uma prova" (4 passos, sempre nesta ordem)

Detalhado em [docs/41 §4](../docs/41-plano-captacao-externa.md#4--o-fluxo-que-se-repete-a-cada-prova-nova).
Pra OBMEP, hoje:

```sh
# 1. raspar — grava captacao-externa/dados/obmep_{ano}.json
cd captacao-externa
./.venv/bin/python pipeline/obmep.py --edicoes 17 18 19 20

# 2. importar — cria a linha de prova_externa na 1ª vez, upsert em conquista_externa
cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/obmep_202*.json \
    --prova-categoria olimpiada --prova-abrangencia nacional \
    --prova-fonte https://www.obmep.org.br/premiados.htm

# 3. resolver — cruza conquista_externa em candidato_externo (relê tudo, idempotente)
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py

# 4. validar — antes de ir pra próxima fonte, conferir uma amostra
curl -s "http://localhost:3000/conquista_externa?uf_informada=eq.CE&limit=5" | python3 -m json.tool
```

`POSTGREST_URL=http://localhost:3000` é porque `api/.env` local não define
essa variável — sem ela, `criar_cliente_supabase()` cairia no branch de
Supabase hospedado (ver [api/app/supabase_client.py](../api/app/supabase_client.py)).
Dentro do container `api` do compose já vem setada; rodando os scripts direto
no host (como acima), precisa passar na mão.

Depois de qualquer migration nova em `api/migrations/`:
`docker compose run --rm migrate up` + `docker compose restart postgrest`
(armadilha nº 1 do [CLAUDE.md raiz](../CLAUDE.md)).

## Escrever um scraper novo

Um arquivo por fonte em `pipeline/`, gerando JSON no formato que o importador
espera — ver o topo de [`pipeline/obmep.py`](pipeline/obmep.py) pro formato
exato (`prova_nome`, `ano`, `nivel_texto`, `serie_referencia_min/max`,
`resultado`, `nome_informado`, `escola_informada`, `cidade_informada`,
`uf_informada`, `fonte_url`).

**Critério de prioridade pra próxima fonte** (docs/41 §6): só vale a pena se
a fonte publica escola + cidade/UF por premiado — é o que o resolver usa pra
desambiguar nome, e é raro fora de lista de olimpíada científica. Vestibular
(ITA, IME...) geralmente só tem nome + inscrição — não dá pra criar
candidato novo com isso, só enriquecer um que uma olimpíada já achou.

## Estado atual

Só OBMEP, edições 17ª-20ª (2022-2025) — 2019/2020/2021 ainda não têm fonte
localizada (docs/41 §5 e §8, item 5). Números da última rodada e o resto da
fila de fontes: docs/41 §5 e §6.
