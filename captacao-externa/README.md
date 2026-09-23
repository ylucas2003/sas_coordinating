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
├── requirements.txt         requests, beautifulsoup4, lxml, pymupdf (PDF: IME, EFOMM, OBQ/OBQ Jr)
├── pipeline/
│   ├── obmep.py              1º scraper — Ouro/Prata/Bronze, 2016-2025 exceto 2020 (não existe)
│   ├── obm.py                2º scraper — Ouro/Prata/Bronze/Menção Honrosa, 2016-2025 completo
│   ├── ita.py                3º scraper — convocados 2ª e 3ª fase do ITA, 2024-2025 (validação, não descoberta — docs/41 §6.1)
│   ├── ime.py                4º scraper — CACFG/IME, 9 de 11 anos entre 2016-2025, 2 fases por ano (URL curada — docs/41 §6.2, §11.3)
│   ├── obf.py                5º scraper — Ouro/Prata/Bronze/Menção Honrosa da OBF, 2023-2025 (publica escola — docs/41 §5.2)
│   ├── efomm.py              6º scraper — CIAGA/CIABA, 6 anos (2017, 2022-2026), 1ª fase + final (URL curada — docs/41 §11.1)
│   ├── escola_naval.py       7º scraper — CPAEN, 7 de 11 anos entre 2016-2025 (`id_file` curado à mão — docs/41 §11.2)
│   ├── obi.py                8º scraper — Quadro de Medalhas da OBI, 2005-2025 exceto 2018 (publica escola — docs/41 §12)
│   └── obq.py                9º e 10º scraper (OBQ + OBQ Jr, duas prova_externa) — primeira fonte em PDF do
│                             projeto, QUATRO formatos de PDF curados por ano (docs/41 §13, §13.1)
└── dados/                    JSON cru por ano — NÃO VERSIONADO
    └── obmep_2025.json, obm_2025.json, ita_2025.json, ime_2025.json, obf_2025.json, efomm_2026.json,
        escola_naval_2025.json, obi_2025.json, obq_2025.json, obqjr_2023.json...
```

⚠️ **OBA foi pesquisada e NÃO virou scraper** — a ferramenta pública de
consulta (nas duas telas que o site tem, a nova em Next.js e a antiga em
PHP) é um verificador POR PESSOA, não um quadro de medalhas: devolve o
cadastro inteiro de participantes que batem UF+ano (238 mil só no Ceará em
2024) e só diz se cada um ganhou medalha abrindo o detalhe individual —
inviável em escala. Decisão e investigação completa em docs/41 §14.

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

E pra OBF (docs/41 §5.2) — publica escola, então FUNDE de verdade com
candidato que a OBMEP já resolveu:

```sh
cd captacao-externa
./.venv/bin/python pipeline/obf.py --anos 2023 2024 2025

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/obf_*.json \
    --prova-categoria olimpiada --prova-abrangencia nacional \
    --prova-fonte "https://www1.fisica.org.br/olimpiada/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

E pra ITA (docs/41 §6.1) — é **validação, não captação**: quem está nessa
lista já passou no vestibular-alvo, não é lead pra convidar. O valor é
cruzar por nome com OBMEP/OBM depois de resolver. Ao vivo só existem 2024 e
2025 (`convocados_2f`/`_3f`, só quem passou de fase); 2021-2023 voltam pelo
Wayback Machine via outro padrão de URL (`notas_Xf_completo`, achado em
22/09/2026) — esse é **melhor** que o ao vivo, não só mais velho: lista TODO
MUNDO que fez a prova, aprovado ou não (docstring do módulo tem os quirks de
HTML que essa recuperação exigiu). 2019/2020/2024/2025/2026 também existem
nesse formato no Wayback; 2020 foi trazido e depois apagado a pedido do
usuário (só quer ITA a partir de 2021 no banco — `_DOCUMENTOS_HISTORICOS`
continua com 2020 pra quem passar `--anos 2020` explicitamente, só não é o
padrão de ninguém rodar sem querer):

```sh
cd captacao-externa
./.venv/bin/python pipeline/ita.py --anos 2024 2025
./.venv/bin/python pipeline/ita.py --anos 2021 2022 2023

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/ita_*.json \
    --prova-categoria vestibular --prova-abrangencia nacional \
    --prova-fonte "https://vestibular.ita.br/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

E pra IME (docs/41 §6.2, §11.3) — mesma categoria da ITA (validação, sem
escola), mas ao contrário do que a versão anterior deste README dizia,
**dá sim pra escolher o ano** (`--anos`, default = todo ano curado em
`_DOCUMENTOS`): a fonte oficial sobrescreve a URL a cada ciclo, mas domínio
irmão (`www.ime.eb.mil.br`), Wayback Machine e mirror de cursinho militar
recuperam 9 dos últimos 10 anos, cada um com até duas fases (Habilitados
2ª fase + Resultado Final):

```sh
cd captacao-externa
./.venv/bin/python pipeline/ime.py
# ou só alguns anos: ./.venv/bin/python pipeline/ime.py --anos 2023 2024 2025

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/ime_*.json \
    --prova-categoria vestibular --prova-abrangencia nacional \
    --prova-fonte "https://inscricoes.ime.eb.br/cfg/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

E pra EFOMM (docs/41 §11.1) — CIAGA + CIABA, mesma categoria de ITA/IME
(validação, sem escola). Mesma correção do IME: **dá pra escolher o ano**,
mirror de cursinho militar (e até um jornal dos próprios alunos da EFOMM)
recuperam 6 anos (2017, 2022-2026):

```sh
cd captacao-externa
./.venv/bin/python pipeline/efomm.py
# ou só alguns anos: ./.venv/bin/python pipeline/efomm.py --anos 2023 2024 2025

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/efomm_*.json \
    --prova-categoria vestibular --prova-abrangencia nacional \
    --prova-fonte "https://www.marinha.mil.br/ciaga/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

E pra Escola Naval/CPAEN (docs/41 §11.2) — ao contrário de EFOMM/IME, aqui
**dá pra escolher o ano** (`--anos`, default = todo ano curado em
`_DOCUMENTOS`), porque cada ano tem um `id_file` fixo e imutável. Sem
escola nem cidade (OREL é unidade administrativa, não lugar — a primeira
fonte deste pipeline sem sinal geográfico nenhum):

```sh
cd captacao-externa
./.venv/bin/python pipeline/escola_naval.py
# ou só alguns anos: ./.venv/bin/python pipeline/escola_naval.py --anos 2023 2024 2025

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/escola_naval_*.json \
    --prova-categoria vestibular --prova-abrangencia nacional \
    --prova-fonte "https://www.marinha.mil.br/sspm/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

E pra OBI (docs/41 §12) — publica escola, funde de verdade com OBMEP/OBF
como a OBI mesma. A descoberta de modalidade é dinâmica (lida da própria
página-índice do ano), então **não tem lista fixa de níveis** — só o ano:

```sh
cd captacao-externa
./.venv/bin/python pipeline/obi.py --anos 2005 2008 2010 2015 2016 2017 2019 2020 2021 2022 2023 2024 2025
# 2018 não existe (404 real, confirmado abrindo a URL — não é bug do scraper)

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/obi_*.json \
    --prova-categoria olimpiada --prova-abrangencia nacional \
    --prova-fonte "https://olimpiada.ic.unicamp.br/passadas/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

E pra OBQ/OBQ Jr (docs/41 §13, §13.1) — duas `prova_externa`, o mesmo script,
primeira fonte do projeto em PDF, com QUATRO formatos de PDF curados por ano
(`_DOCUMENTOS_OBQ`/`_DOCUMENTOS_OBQ_JR`). `--fonte` escolhe qual das duas
raspar (`obq`, `obqjr` ou `ambas`, default):

```sh
cd captacao-externa
./.venv/bin/python pipeline/obq.py --anos 2018 2019 2020 2021 2022 2024 2025 --fonte obq
./.venv/bin/python pipeline/obq.py --anos 2018 2019 2020 2021 2022 2023 --fonte obqjr

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/obq_*.json \
    --prova-categoria olimpiada --prova-abrangencia nacional \
    --prova-fonte "https://obquimica.org/olimpiada/olimpiada-brasileira-de-quimica"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/obqjr_*.json \
    --prova-categoria olimpiada --prova-abrangencia nacional \
    --prova-fonte "https://obquimica.org/olimpiada/olimpiada-brasileira-de-quimica-junior"

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
OBF (2023-2025), ITA (2024-2025 ao vivo — convocados 2ª e 3ª fase — mais
2021-2023 via Wayback Machine — lista completa de 1ª e 2ª fase, §6.1.2),
IME (9 de 11 anos entre 2016-2025, 2 fases por ano — inclusive nota de quem
NÃO passou na 2ª fase de 2022-2025, §11.3.1), EFOMM (6 anos: 2017, 2022-2026,
CIAGA/CIABA), Escola Naval (7 de 11 anos entre 2016-2025, CPAEN), OBI (2005,
2008, 2010, 2015-2025 exceto 2018, que não existe — §12) e OBQ/OBQ Jr
(OBQ: 2018-2022, 2024, 2025 — só falta 2023; OBQ Jr: 2018-2023 — primeira
fonte em PDF, §13/§13.1, com um bug de subcontagem real corrigido depois de
já ter ido pra produção) — quatro delas (ITA/IME/EFOMM/Escola Naval) são
validação, não captação — **137.861** `candidato_externo` / **166.034**
`conquista_externa` resolvidos neste ambiente (números de 23/09/2026, depois
do lote de fusão em massa do §10, da expansão de IME/EFOMM via mirror de
cursinho e Wayback Machine, do ITA 2021-2023, da nota de não aprovados do
IME, da OBI e da expansão+correção de OBQ/OBQ Jr). AFA pesquisada e deixada
de fora (bloqueio de Cloudflare, docs/41 §11); OBA pesquisada e deixada de
fora (ferramenta pública é verificador individual, não quadro de medalhas,
docs/41 §14). Números da última rodada e o resto da fila de fontes: docs/41
§5, §5.1, §5.2, §6.1, §6.1.2, §6.2, §6.2.1, §10, §11, §11.1, §11.2, §11.3,
§12, §13, §13.1 e §14.
