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
├── requirements.txt         requests, beautifulsoup4, lxml, pymupdf (só pro IME, é PDF)
├── pipeline/
│   ├── obmep.py              1º scraper — Ouro/Prata/Bronze, 2016-2025 exceto 2020 (não existe)
│   ├── obm.py                2º scraper — Ouro/Prata/Bronze/Menção Honrosa, 2016-2025 completo
│   ├── ita.py                3º scraper — convocados 2ª e 3ª fase do ITA, 2024-2025 (validação, não descoberta — docs/41 §6.1)
│   └── ime.py                4º scraper — aprovados do CACFG/IME, só o ciclo corrente (validação — docs/41 §6.2)
└── dados/                    JSON cru por ano — NÃO VERSIONADO
    └── obmep_2025.json, obm_2025.json, ita_2025.json, ime_2025.json...
```

## Setup

```sh
cd captacao-externa
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## O fluxo de "acrescentar uma prova" (4 passos, sempre nesta ordem)

Detalhado em [docs/41 §4](../docs/41-plano-captacao-externa.md#4--o-fluxo-que-se-repete-a-cada-prova-nova).
Pra OBMEP:

```sh
# 1. raspar — grava captacao-externa/dados/obmep_{ano}.json
cd captacao-externa
./.venv/bin/python pipeline/obmep.py --anos 2016 2017 2018 2019 2021 2022 2023 2024 2025

# 2. importar — cria a linha de prova_externa na 1ª vez, upsert em conquista_externa
cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/obmep_*.json \
    --prova-categoria olimpiada --prova-abrangencia nacional \
    --prova-fonte https://www.obmep.org.br/premiados.htm

# 3. resolver — cruza conquista_externa em candidato_externo (relê tudo, idempotente)
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py

# 4. validar — antes de ir pra próxima fonte, conferir uma amostra
curl -s "http://localhost:3000/conquista_externa?uf_informada=eq.CE&limit=5" | python3 -m json.tool
```

E pra OBM (mesmos passos 2-4, só troca o scraper e o `--prova-fonte`):

```sh
cd captacao-externa
./.venv/bin/python pipeline/obm.py --anos 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/obm_*.json \
    --prova-categoria olimpiada --prova-abrangencia nacional \
    --prova-fonte "https://www.obm.org.br/quem-somos/premiados-da-obm/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

⚠️ **A OBM não publica escola** (docs/41 §5.1) — cada conquista dela vira
candidato PRÓPRIO no passo 3, nunca se funde com o que a OBMEP já resolveu
pra mesma pessoa. Não é bug do resolver: é a régua de match do §4.1 (nome +
escola, sem fallback pra nome+cidade) fazendo o que foi desenhada pra fazer.

E pra ITA (docs/41 §6.1) — é **validação, não captação**: quem está nessa
lista já passou no vestibular-alvo, não é lead pra convidar. O valor é
cruzar por nome com OBMEP/OBM depois de resolver:

```sh
cd captacao-externa
./.venv/bin/python pipeline/ita.py --anos 2024 2025

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/ita_*.json \
    --prova-categoria vestibular --prova-abrangencia nacional \
    --prova-fonte "https://vestibular.ita.br/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

E pra IME (docs/41 §6.2) — mesma categoria da ITA, **sem `--anos`**: a URL
não tem ano nenhum, é sempre o ciclo corrente (o ano do registro vem de
dentro do PDF). Rodar de novo daqui a um ano traz outro concurso:

```sh
cd captacao-externa
./.venv/bin/python pipeline/ime.py

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/ime_*.json \
    --prova-categoria vestibular --prova-abrangencia nacional \
    --prova-fonte "https://inscricoes.ime.eb.br/cfg/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
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

**Critério de prioridade pra próxima fonte** (docs/41 §6): só vale a pena
pra DESCOBERTA de candidato novo se a fonte publica escola + cidade/UF por
premiado — é o que o resolver usa pra desambiguar nome. **Confira abrindo o
HTML de verdade, não só o que o Dossiê de Provas resume**: a OBM parecia
servir e não publica escola nenhuma (docs/41 §5.1) — só se descobriu abrindo
a página. Sem escola, a fonte só serve pra fila de enriquecimento (§8, item
1), não pra criar candidato novo.

## Estado atual

OBMEP (2016-2025, exceto 2020, que não existe), OBM (2016-2025 completo),
ITA (2024-2025, convocados 2ª e 3ª fase) e IME (2025, aprovados CACFG) — as duas
últimas são validação, não captação — 57.103 `candidato_externo` resolvidos.
Números da última rodada e o resto da fila de fontes: docs/41 §5, §5.1, §6.1
e §6.2.
