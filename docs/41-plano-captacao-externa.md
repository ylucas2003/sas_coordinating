# 41 — Captação externa · achar potenciais alunos cruzando resultados de provas públicas

> **Feito de ponta a ponta pra OBMEP**: schema aplicado, pipeline completo,
> quase 70 mil linhas cruas e 53 mil pessoas resolvidas (§5) — **e agora
> também as rotas de API e a tela em Administração** (§7), que na primeira
> versão deste documento ainda eram só desenho. Este documento é o registro
> do que existe, pra quem entrar depois saber exatamente onde a linha entre
> "feito" e "planejado" está.
>
> Nasceu de uma conversa (15/09/2026) que começou pedindo uma tela de
> "conquistas dos alunos" e só na segunda volta ficou claro que não é sobre
> os ~900 alunos que já estão no [aluno](../api/migrations/0001_schema_inicial.sql) —
> é sobre gente de fora, pra achar quem convidar pro colégio.

## 0 · O que foi pedido, em uma frase

Uma aba em Administração, só pra coordenador, com uma lista de nomes de
**candidatos externos** — gente que nunca estudou aqui, mas que apareceu numa
lista pública de premiados/aprovados de olimpíada, vestibular ou concurso — e,
ao clicar, a ficha mostra **todas** as conquistas daquela pessoa cruzadas de
várias fontes diferentes. É captação: achar quem já provou que é bom antes de
a coordenação nunca ter ouvido falar dela.

## 1 · Por que isto não é o mesmo problema que o resto do sistema resolve

Todo o resto do SAS parte de `aluno.matricula` — um identificador estável,
emitido pelo Canvas, que atravessa anos letivos (`matricula_turma`). Aqui não
existe nada parecido: cada "pessoa" nasce inteiramente do que uma fonte
externa escreveu numa lista de resultado, e a mesma pessoa pode aparecer em
várias listas diferentes, escritas por instituições diferentes, sem chave
comum nenhuma entre elas.

O núcleo do problema, então, não é a tela — é **resolução de identidade**:
decidir que duas linhas raspadas de fontes (ou anos) diferentes são a mesma
pessoa. Fazer isso só pelo nome dá colisão toda hora (nome comum + país
inteiro = muito homônimo); o que ajuda é **escola + cidade/UF**, que listas de
olimpíada científica quase sempre publicam junto do nome — e é exatamente por
isso que o plano de fontes (§6) prioriza olimpíada sobre vestibular.

O catálogo de provas candidatas a fonte, com o que cada uma publica e por
quanto tempo, já estava levantado antes desta conversa — é a pasta
[`Dossiê de Provas`](../Dossie%20de%20Provas/README.md) na raiz do repo (13
arquivos, ~70 provas pesquisadas). Este documento não repete aquele
levantamento; usa ele como insumo.

## 2 · Escopo decidido

Duas perguntas que mudam o volume de dado inteiro, decididas em conversa
antes de qualquer linha de código:

- **Geográfico: nacional**, não só Fortaleza/Ceará. Custo: sem filtro
  geográfico, uma fonte grande como a OBMEP tem dezenas de milhares de
  registros por ano — o pipeline precisa aguentar volume desde o primeiro dia,
  não só quando "crescer".
- **Temporal: últimos 5-7 anos**, não só 2-3. Custo: resultado antigo é lead
  frio (quem ganhou em 2019 já deve ter saído da educação básica) — por isso
  `candidato_externo.serie_referencia_min/max` + `ano_referencia_serie`
  existem: pra calcular, na leitura, se a pessoa ainda deve estar
  cursando fundamental/médio, em vez de descartar o dado antigo de cara.
  ⚠️ A OBMEP especificamente foi pedida com **10 anos** (2016-2025, §5) —
  é mais janela do que o piso de 5-7 decidido aqui, não uma revisão da regra
  geral. Prova nova em §6 volta ao piso de 5-7 salvo decisão em contrário.

## 3 · Modelo de dados — aplicado (migrations 0056 e 0057)

Três tabelas, porque a resolução de identidade é um passo **à parte**,
revisável, não um efeito colateral do INSERT do scraper:

```
prova_externa       catálogo (OBMEP, OBM, ITA...) — alimentado aos poucos, §4
conquista_externa   1 linha por registro raspado, CRU — nome/escola/cidade/UF
                     exatamente como a fonte informou
candidato_externo   identidade RESOLVIDA — agrupa N conquista_externa da
                     mesma pessoa
```

[`0056_captacao_externa.sql`](../api/migrations/0056_captacao_externa.sql) cria as
três; [`0057_dedup_conquista_externa.sql`](../api/migrations/0057_dedup_conquista_externa.sql)
acrescenta o índice único que faz o importador (§4) ser idempotente:

```sql
CREATE UNIQUE INDEX conquista_externa_dedup
    ON conquista_externa (prova_id, ano, nivel_texto, nome_informado, escola_informada, resultado);
```

Pontos que não são óbvios lendo só o `CREATE TABLE`:

- **`conquista_externa.candidato_id` nasce `NULL`.** Só o script de resolução
  (§4, passo 3) preenche. O scraper e o importador nunca escrevem nele.
- **`candidato_externo.serie_referencia_min/max` é uma FAIXA, não um número.**
  Prova costuma anunciar por **nível**, que cobre 2-3 séries (ex. Nível 2 da
  OBMEP = 8º-9º ano) — guardar um número só inventaria precisão que a fonte
  não deu.
- **`status_captacao`** (`novo` → `contatado` → `interessado` → `matriculado`,
  ou `descartado` a qualquer momento) é o único campo que código nenhum
  escreve sozinho — é o funil manual da coordenação, mexido só pela tela do §7.
- Ambas as migrations têm `.down.sql` par, aplicadas e testadas neste ambiente
  (`docker compose run --rm migrate up` + `docker compose restart postgrest`,
  a armadilha nº 1 do [CLAUDE.md raiz](../CLAUDE.md)).

## 4 · O fluxo que se repete a cada prova nova

Este é o padrão — "acrescentar uma prova no banco e depois cruzar, e ir
fazendo isso sucessivamente", como foi combinado na conversa. Quatro passos,
sempre nesta ordem:

1. **Scraper** — um arquivo novo em
   [`captacao-externa/pipeline/`](../captacao-externa/pipeline/) (venv próprio
   da pasta, fora da API — mesma escolha do `banco-questoes/`, nada disso roda
   em requisição). Baixa a fonte, faz o parsing, grava um JSON cru em
   `captacao-externa/dados/`. Não toca no banco.
2. **Importar** —
   [`api/scripts/importar_captacao_externa.py`](../api/scripts/importar_captacao_externa.py)
   lê o(s) JSON(s), cria a linha de `prova_externa` na primeira vez (passa
   `--prova-categoria`/`--prova-abrangencia`/`--prova-fonte`), e faz upsert em
   `conquista_externa` em lotes de 200. Idempotente: rodar o mesmo JSON de
   novo não duplica (é pra isso que serve o índice da 0057).
3. **Resolver** —
   [`api/scripts/resolver_candidatos_externos.py`](../api/scripts/resolver_candidatos_externos.py)
   relê **toda** `conquista_externa` (não só o que chegou agora) e refaz o
   agrupamento do zero. É assim que uma conquista nova de uma prova nova gruda
   num `candidato_externo` que já existia de uma prova antiga — e é por isso
   que o passo tem que reler tudo, não só o incremento: a mesma pessoa pode ter
   uma conquista de 2022 já resolvida e uma de uma fonte nova entrando agora,
   e as duas precisam acabar apontando pro mesmo `candidato_externo`.
4. **Validar** — antes de passar pra próxima fonte, olhar uma amostra (query
   direta, como em §5) pra confirmar que os campos vieram certos e que o
   cruzamento fez sentido. Nenhuma prova está "pronta" só porque o script
   rodou sem erro.

### 4.1 · A régua de match (e por que ela erra pra um lado só de propósito)

Chave usada: **nome normalizado (maiúsculas, sem acento) + escola informada,
exatos**. Nada de fuzzy matching, nada de "nome parecido". Consequência
assumida: a mesma pessoa que trocar de escola entre duas conquistas vira **dois**
`candidato_externo` — um falso NEGATIVO. A alternativa (relaxar pra nome +
cidade, por exemplo) traria falso POSITIVO — duas pessoas diferentes
viradas uma só — que é o erro caro aqui: uma ficha de captação errada é pior
que duas fichas certas separadas. Errar pro lado do falso negativo é a escolha
segura enquanto não existe fila de revisão humana (§8, primeiro item).

## 5 · Estado atual — o que já rodou, com número de verdade

Primeira fonte: **OBMEP** (Olimpíada Brasileira de Matemática das Escolas
Públicas), nacional, ouro/prata/bronze, públicas e privadas — sem Menção
Honrosa de propósito (ela só existe por UF, 27 estados × 3 níveis ×
pública/privada = 162 requisições por edição, e é sinal mais fraco pra
captação; fica pra quando o resto já estiver validado).

**Anos raspados: 2016 a 2025, exceto 2020 (que não existe — a pandemia
suspendeu aquela edição, e não há edição nenhuma publicada com esse ano em
lugar nenhum do site).** É a janela de 10 anos do §2, fechada. A versão
anterior deste documento cobria só 2022-2025 e registrava 2019/2020/2021 como
lacuna "não investigada" (§8, item 5, embaixo) — a lacuna real era de três
tipos:

1. **A numeração de edição não é linear.** `premiacao.obmep.org.br/{N}obmep/`
   só existe a partir da 17ª (2022); antes disso o site usa outras duas
   convenções de URL, achadas seguindo os links reais de
   [`obmep.org.br/premiados.htm`](https://www.obmep.org.br/premiados.htm) (o
   Dossiê de Provas já apontava essa página, só não tinha aberto os links) —
   `16aobmep/` pra 2021 (o "a" é peculiaridade do próprio site, não fórmula) e
   `{ano}/` pra 2016-2019. Por isso `pipeline/obmep.py` trocou de parâmetro:
   era `--edicoes` (número de edição, aritmética frágil), agora é `--anos`
   (a chave real), com `SEGMENTO_POR_ANO` documentando as três convenções
   ano a ano.
2. **2016 usa um HTML mais antigo**, sem as âncoras `<a name="nivelN">` que
   amarram cada tabela ao nível e sem a coluna de posição na linha (6 células
   por linha, não 7). O parser passou a ler o nível de dentro do cabeçalho da
   própria tabela e a cortar as células pelo FIM (`celulas[-6:]`), que
   funciona nos dois formatos.
3. **2016 não publica lista de rede privada** pro Ouro/Prata/Bronze
   (`.privada.do.htm` 404 só nesse ano) — os únicos "Tipo" de escola que
   aparecem na lista pública daquele ano são F/E/M (federal/estadual/
   municipal, todas públicas). Tratado como ausência esperada, não erro.

Números depois de raspar, importar e resolver (ambiente local, 15/09/2026),
só OBMEP:

| Métrica | Valor |
|---|---|
| `conquista_externa` (linhas cruas) | 69.653 |
| `candidato_externo` (pessoas resolvidas) | 53.813 |
| candidatos com 2+ conquistas (repetiram medalha) | 11.569 |
| — dos quais, com 3 | 3.279 |
| — dos quais, com 4 | 785 |
| — dos quais, com 5 | 164 |
| — dos quais, com **6** (o máximo achado nesta janela) | **43** |

Reprodutível com:

```sh
cd captacao-externa && ./.venv/bin/python pipeline/obmep.py \
  --anos 2016 2017 2018 2019 2021 2022 2023 2024 2025

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
  ../captacao-externa/dados/obmep_*.json \
  --prova-categoria olimpiada --prova-abrangencia nacional \
  --prova-fonte https://www.obmep.org.br/premiados.htm

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

(`POSTGREST_URL` explícito porque `api/.env` local não tem essa variável —
sem ela, `criar_cliente_supabase()` cairia no branch de Supabase hospedado, ver
[app/supabase_client.py](../api/app/supabase_client.py); dentro do container
`api` do compose já vem setada.)

### 5.1 · Segunda fonte: OBM

[`pipeline/obm.py`](../captacao-externa/pipeline/obm.py), 2016-2025 completo
(nem falta 2020, ao contrário da OBMEP — a OBM nunca parou). Uma requisição
por ano (`obm.org.br/premiados-obm-{ano}/`), ~300 linhas cada.

⚠️ **Achado real, não suposição do §1: a OBM não publica escola.** A tabela só
tem Nome, Cidade–Estado, Pontos e Prêmio — o §1 deste documento assumia que
"olimpíada científica quase sempre publica [escola]", e isso vale pra OBMEP,
não pra OBM. Consequência, pelo próprio desenho do §4.1 (nome+escola, sem
fallback pra nome+cidade): **toda conquista de OBM vira um `candidato_externo`
PRÓPRIO**, nunca se funde com um candidato que a OBMEP já resolveu — mesmo
quando é literalmente a mesma pessoa. Anexar por nome (+ cidade/UF de
confiança extra) ao candidato certo é a "variação do resolver ainda não
escrita" que o §6 original apontava pra vestibular; a OBM entra na mesma fila
(§8, item 1).

Por não ter escola, `escola_informada` sai `""` (nunca `null`) do scraper —
o índice único da 0057 trata NULL como sempre-diferente-de-NULL, e duas
raspagens do mesmo ano duplicariam a linha inteira em vez de fazer upsert;
string vazia participa do índice normalmente. Testado: reimportar o mesmo
lote duas vezes manteve `conquista_externa` no mesmo total.

Diferença deliberada da régua da OBMEP: **Menção Honrosa ENTRA** aqui (ao
contrário da OBMEP, onde ela foi excluída por custar 162 requisições por
edição — docs/41 §5). Na OBM ela já vem de graça na mesma página por ano, sem
requisição extra nenhuma — mais sinal, custo zero.

Números depois de raspar/importar/resolver (15/09/2026): 2.419
`conquista_externa` novas, todas viraram candidato novo (nenhuma tinha escola
pra cruzar com as 53.813 já resolvidas) — total geral agora **56.232**
`candidato_externo`.

⚠️ **A OBM também expôs um bug real no resolver**, consertado em
[`scripts/resolver_candidatos_externos.py`](../api/scripts/resolver_candidatos_externos.py)
(16/09/2026): ao criar candidato novo em lote, o código casava cada
conquista com a linha recém-inserida por `(nome, escola)` — um dicionário
Python. Com escola sempre vazia (só acontece na OBM), DUAS PESSOAS
DIFERENTES com o mesmo nome no mesmo lote de 200 colidiam na mesma chave, e
ambas ficavam apontando pro MESMO `candidato_externo` — o falso POSITIVO que
o §4.1 chama de erro caro, entrando pela porta dos fundos. A correção troca o
dicionário por `zip` posicional (o Postgres preserva a ordem do `INSERT
... VALUES (...), (...) RETURNING` de um único statement). 20 grupos da OBM
foram afetados; corrigidos à mão neste ambiente (grupo dividido de volta em
dois candidatos, um por ano) porque não havia rodada de produção ainda pra se
preocupar em migrar.

### 5.2 · Terceira olimpíada: OBF — a primeira que cruza de verdade com a OBMEP

[`pipeline/obf.py`](../captacao-externa/pipeline/obf.py) — Olimpíada
Brasileira de Física (SBF; não confundir com a OBFEP, prova irmã só de
escola pública). 2023-2025 confirmado; 2019/2021/2022 existem segundo o
Dossiê de Provas, mas a busca interna do site não os indexa (achado
rodando: 403/404 nas tentativas automatizadas) — lacuna registrada, não
perseguida, mesmo padrão da OBMEP antes de virar `SEGMENTO_POR_ANO`.

**Publica ESCOLA** — ao contrário da OBM/ITA/IME, e é a primeira fonte
depois da OBMEP com essa qualidade de dado. Efeito prático, visto rodando de
verdade: **conquistas de OBF já se fundem automaticamente com candidatos que
a OBMEP resolveu antes**, pela régua de match do §4.1 (nome+escola exatos) —
sem precisar da fila de enriquecimento do §8 item 1, que só existe pra
fontes SEM escola. "Arthur Reiser de Paula" (Alpha Lumen Instituto) chegou a
8 conquistas cruzando as duas fontes.

Mesma régua de escopo da OBM: Menção Honrosa entra (as 4 categorias — Ouro/
Prata/Bronze/Menção — vêm juntas na MESMA página por série, sem custo de
requisição extra, mesmo raciocínio que já valia pra OBM). Sem cidade — só
UF, direto da coluna do relatório, sem tradução por dicionário nenhum
(ao contrário da ITA/IME, aqui não tem "banca", o dado já vem certo).

**Achado real: o ID de página do Joomla muda a cada publicação**, e não tem
padrão de URL fixo (o Dossiê de Provas já registrava isso). A saída foi usar
a BUSCA interna do próprio site (`component/search/?searchword=premiados`)
pra descobrir os 7 links (6º ao 9º ano, 1ª à 3ª série) de cada ano — e o
termo de busca tem que ser a palavra solta "premiados", não o slug inteiro
"premiados-obf-2025": o buscador do Joomla indexa palavra, não string
composta, e buscar pelo slug direto sempre voltava zero resultado até eu
perceber isso rodando de verdade. O resultado de um ano pode estar
hospedado no site do ano SEGUINTE (a OBF publica resultado final em fev/mar
do ano seguinte) — a busca tenta os dois sites e junta o que achar.

Números depois de raspar/importar/resolver (16/09/2026): 4.767
`conquista_externa` novas (2023: 1.898 · 2024: 1.373 · 2025: 1.496), das
quais 827 se fundiram em candidato já existente (a maior parte, olimpíadas
anteriores da própria OBF entre si; algumas com a OBMEP) — **3.940**
candidatos novos, total geral agora **62.593**.

## 6 · Próximas fontes, em ordem

Critério de ordenação: fonte publica escola/cidade/UF por premiado (senão o
match do §4.1 não tem o que comparar, como se descobriu tarde demais com a
OBM — §5.1) **e** já tem arquivo público multi-ano confirmado no Dossiê de
Provas. Nessa ordem:

1. **OBA** — [Dossiê 02](../Dossie%20de%20Provas/02-nacionais-biologia-astronomia-informatica-ciencias-historia.md),
   `novo.oba.org.br/medalhas` (SPA — precisa investigar se dá pra raspar sem
   navegador headless, diferente da OBMEP que é HTML estático).
2. **OBI** — mesmo arquivo do Dossiê, `olimpiada.ic.unicamp.br/passadas/`,
   1999-2025 confirmado, HTML estático.
3. **OBQ / OBQ Jr** — mesmo arquivo, `obquimica.org`, PDFs por ano (precisa de
   extração de PDF, não só HTML — primeira fonte que vai exigir isso).
4. **OPEMAT (PE) e OMEG (GO)** — [Dossiê 05](../Dossie%20de%20Provas/05-estaduais.md),
   as duas estaduais com melhor cobertura confirmada.

   ⚠️ Antes de raspar qualquer uma: **confira se ela publica escola** (a OBM
   não publicava, e só se descobriu abrindo o HTML de verdade — o Dossiê de
   Provas registra o que cada prova PUBLICA em geral, não coluna por coluna).
   Sem escola, a fonte só serve pra fila de enriquecimento do item 1 do §8,
   não pra descoberta de candidato novo.

### 6.1 · Terceira fonte, fora da ordem: ITA — validação, não descoberta

[`pipeline/ita.py`](../captacao-externa/pipeline/ita.py), 2024-2025 (só esses
dois anos: `{ano}_convocados_3f.htm` 404 pra 2023 pra trás — o Dossiê de
Provas já registrava isso como não confirmado, e não investiguei mais fundo
porque o valor desta fonte não é histórico longo).

**Não é olimpíada, é o próprio vestibular-alvo** — e por isso não segue o
critério de ordenação do §6: entrou fora da fila porque a pergunta que
motivou não foi "quem descobrimos de novo", foi "o sinal que a gente já capta
(medalha de olimpíada) realmente correlaciona com passar no ITA?". Quem está
na lista de convocados pra 3ª fase **já passou** — não é lead pra convidar,
é prova de que a tese funciona. Por isso `serie_referencia_min/max` sai
sempre `None`: a lista não diz se é treineiro ou formando, e não tem escola
(mesma ausência da OBM, mesmo motivo do `escola_informada` sair `""`).

`cidade_informada`/`uf_informada` vêm da **cidade da PROVA** ("BANCA" no
relatório), não da cidade do candidato — quem mora numa cidade pequena faz a
prova na banca mais perto, não na própria cidade. Traduzido pela lista real
de locais de exame do próprio site (`vestibular.ita.br/principal.htm`),
conferida contra todo valor de banca visto nos dois anos.

**O resultado, cruzando por nome com OBMEP e OBM** (15-16/09/2026, mesma
ressalva de sempre: só nome, sem escola/cidade de confirmação):

| Só apareceu em | Pessoas |
|---|---|
| OBMEP | 48.347 |
| OBM + OBMEP | 1.132 |
| OBM | 230 |
| **ITA** | 221 |
| **ITA + OBMEP** | 82 |
| **ITA + OBM + OBMEP** | **25** |
| ITA + OBM | 2 |

Dos 330 convocados pra 3ª fase do ITA em 2024-2025, **109 (33%) já tinham
aparecido em OBMEP ou OBM** — quase um terço de quem entra no ITA já tinha
sido achado pelo sinal de captação, incluindo 25 pessoas com as três. Exemplo
real de uma delas:

```
Ahmed Ehab Fahmy El Tabey
  2017-2023  OBMEP, quase todo ano (Ouro/Prata/Bronze, pública e depois privada)
  2018-2023  OBM, todo ano (Menção Honrosa)
  2025       ITA — Ampla Concorrência
```

#### 6.1.1 · Addendum (16/09/2026): 2ª fase entrou — "todos os alunos", não só os aprovados finais

Pedido explícito: salvar o resultado de TODOS os alunos das provas de
vestibular, não só dos aprovados. A 1ª fase (objetiva) não tem lista nomeada
— ninguém foi filtrado ainda —, mas achei `{ano}_convocados_2f.htm`: quem
passou a 1ª fase e foi chamado pra 2ª (discursiva). É MUITO maior que a 3ª
fase (777/773 pessoas por ano contra 150/180) e continua sendo o teto real
do que a ITA publica com nome — ela nunca lista quem não passou fase
nenhuma.

Formato diferente da 3ª fase: texto de LARGURA FIXA (não `|`-delimitado), e
a largura de cada coluna muda de ano pra ano — a régua de traços do próprio
relatório dá as posições exatas; um split por 2+ espaços quebrava quando o
nome da banca ("SAO JOSE DOS CAMPOS", sem folga de sobra) grudava direto na
coluna seguinte.

Cada pessoa que chega à 3ª fase agora tem DUAS conquistas naquele ano — uma
de cada fase —, porque são dois eventos de classificação distintos, não a
mesma informação duas vezes.

**Números depois da expansão**: 330 → **1.205 pessoas distintas da ITA**;
cruzando as quatro fontes de novo:

| Cruzamento (subconjunto) | Pessoas |
|---|---|
| ITA sozinho | 702 |
| ITA + OBMEP | 230 |
| IME + ITA (sem olimpíada) | 152 |
| ITA + OBM + OBMEP | 53 |
| IME + ITA + OBMEP | 41 |
| **IME + ITA + OBM + OBMEP** | **24** (era 1 antes da expansão) |
| IME + OBM + OBMEP | 16 |

Cerca de 29% dos 1.205 (351 pessoas) já tinham medalhado em OBMEP ou OBM —
perto do 33% que a amostra menor (só 3ª fase) já mostrava, o que sugere que
o número não era um acaso de amostra pequena. E o grupo "nas quatro fontes"
saltou de 1 pessoa pra 24, porque agora capturamos gente que passou da 1ª
fase da ITA sem necessariamente chegar à 3ª — mais gente real, mais
cruzamento real.
```

Idem: **achado real, não suposição.** A primeira importação ficou em dobro
(660 em vez de 330 `conquista_externa`) porque `nivel_texto` saiu `None` do
scraper — mesmo problema de NULL-no-índice-de-dedup que a OBM já tinha
exposto pra `escola_informada` (0057), agora em outra coluna. Corrigido pra
`""`; o frontend também trocou `??` por `||` na célula de Nível
(`CaptacaoFicha.tsx`) pra tratar vazio e ausente como a mesma coisa, igual já
fazia pra Escola informada.

#### 6.1.2 · Addendum (22/09/2026): 2020-2023 via Wayback Machine — lista COMPLETA, não só quem passou de fase

O §6.1.1 trouxe "convocados 2ª fase", mas isso ainda é "quem passou uma
etapa" — o usuário pesquisou por conta própria e achou um padrão de URL
melhor: `vestibular.ita.br/notas/{ano}_notas_1f_completo.htm` e
`_2f_completo.htm`. O site já não serve isso ao vivo (só `convocados_2f`/`_3f`
funcionam, pra 2024/2025), mas o Wayback Machine tem os dois arquivos
congelados pra 2019-2026. É uma fonte estritamente melhor onde existe: lista
**TODO CANDIDATO que fez a prova**, aprovado ou não (inclusive "AUSENTE"),
com a nota de cada matéria aberta — não só quem avançou de fase.

Curou-se 2020-2023 (os quatro anos que o usuário pediu); 2019/2024/2025/2026
também existem nesse formato no Wayback, não trazidos ainda por não terem
sido pedidos.

Quatro achados de HTML, todos avessos a "assumir que o formato é igual todo
ano" — nenhum foi visível sem baixar o arquivo de verdade e ler:

1. **O banner "VESTIBULAR AAAA" não existe em toda página** — 2020/2021 têm,
   2022/2023 pulam direto pro título da tabela. A validação original tratava
   "banner ausente" igual a "banner contradiz o ano esperado" e descartava os
   dois casos — silenciosamente jogou fora 2022 (1ª fase) e o ano de 2023
   inteiro (as duas fases) antes de virar erro visível.
2. **2021 usa `<br>` como separador de linha DENTRO do `<pre>` da 1ª fase**
   (7223 ocorrências, contra 8-11 incidentais em cada um dos outros três
   anos) — sem trocar por `\n` antes de repartir, a 1ª fase de 2021 virava 1
   registro em vez de ~7200.
3. **A 2ª fase de 2023 vem em DOIS `<pre>`** — "Candidatos Optantes pela
   Carreira Militar" (185 pessoas) e "Não Optantes" (544), cada um com seu
   próprio cabeçalho. Pegar só o primeiro bloco (era o comportamento
   original, `re.search`) descartava 544 dos 729 candidatos sem aviso nenhum
   — mesma classe de erro do item 1, silêncio em vez de exceção.
4. **A 1ª fase PUBLICA nota por matéria, e o parser jogava tudo fora**
   (achado revisando um resultado real com o usuário, 22/09/2026 à tarde —
   ele perguntou "não salvou as notas de 1ª fase?"). O cabeçalho da 1ª fase
   dá cada matéria em SEU PRÓPRIO campo entre `|` (`| MAT. | FIS. | QUIM. |
   PORT. | INGL. | MEDIA |`), diferente da 2ª fase, que junta as matérias
   NUM campo só separado por espaço. O código lia os dois formatos do mesmo
   jeito — pegava só o primeiro rótulo ("mat"), a contagem nunca batia com
   os 6 valores da linha, e `notas_por_materia` saía `None` pra TODA a 1ª
   fase, sem aviso nenhum (mesma classe de silêncio dos itens 1 e 3: contagem
   não bate, função devolve vazio/None em vez de erro). E, só na 1ª fase de
   2022, a coluna de Inglês tem "10.0000" com um espaço solto no meio
   (`"1 0.0000"`, 437 ocorrências) — `_numero` agora também remove espaço
   interno antes de converter.

Números depois de corrigir os quatro (`captacao-externa/pipeline/ita.py`,
`_confere_ano_historico`, `_linhas_do_pre_sem_fechar`, `parsear_2f_completo`
com `re.finditer` sobre todos os blocos, `parsear_1f_completo` com rótulo por
campo em vez de rótulo por palavra):

| Ano | 1ª fase | 2ª fase | Total | Com nota por matéria |
|---|---|---|---|---|
| 2020 | 7.355 | 665 | 8.020 | 8.020 (100%) |
| 2021 | 7.201 | 749 | 7.950 | 7.950 (100%) |
| 2022 | 7.988 | 750 | 8.738 | 8.738 (100%) |
| 2023 | 9.364 | 727 | 10.091 | 10.091 (100%) |

A 1ª fase publica mat/fís/quím/port/inglês + média (inclusive pra quem
constou AUSENTE, com zero em tudo — mesmo raciocínio de "zero é dado, não
ausência de dado" que já valia pra `nota.computavel`); a 2ª fase publica
mat/fís/quím/redação + médias das duas fases (e classificação pra quem
passou), igual ao que a ITA já publicava para 2024/2025.

### 6.2 · Quarta fonte, mesma categoria da ITA: IME — a outra ponta do alvo

[`pipeline/ime.py`](../captacao-externa/pipeline/ime.py) raspa o "Resultado
Preliminar do Exame de Escolaridade" do concurso de admissão do IME — CACFG
(Curso de Formação e Graduação, o vestibular civil; não confundir com o
"CP/IME" de pós-graduação pra oficiais já formados, achado por engano na
primeira tentativa e descartado). Mesma categoria da ITA (§6.1): validação,
não descoberta — quem está aprovado já passou no vestibular-alvo.

**Só um ciclo, e sem jeito de escolher outro.** Ao contrário das outras três
fontes, `inscricoes.ime.eb.br/documentos/ATIVA.pdf` e `.../RESERVA.pdf` NÃO
têm ano na URL — são os nomes fixos do ciclo CORRENTE, sobrescritos a cada
concurso novo. Não existe arquivo por ano pra voltar atrás (o Dossiê de
Provas já registrava "não há padrão de URL único e estável confirmado" pro
IME, depois de duas tentativas travarem em erro de certificado). Por isso
`pipeline/ime.py` não tem `--anos`: o ano do registro vem de dentro do
próprio PDF ("CACFG 2025/2026" no cabeçalho — usamos 2025, o ano da prova
escrita), e rodar o script de novo daqui a um ano traz OUTRO concurso, não
este.

Dois achados reais no caminho, os dois já esperados pela essa altura:

1. **O certificado TLS do site é quebrado de verdade** (não é firewall nem
   User-Agent) — falta a cadeia intermediária, e `requests` recusa por
   padrão onde o `curl` que investigou a fonte tolerava. `verify=False` é a
   única forma de falar com esse servidor específico; documentado no
   scraper, não é escolha de segurança feita a esmo.
2. **Mesma pegadinha do NULL-no-índice-de-dedup da OBM/ITA, evitada desta
   vez ANTES de rodar**: `escola_informada` e `nivel_texto` já nasceram `""`
   no primeiro commit, não precisou de uma importação em dobro pra
   descobrir.

**Duas relações por PDF** — Aprovados (com nome) e Não Aprovados (só número
de inscrição, sem nome, pra não expor quem não passou); o parser só casa o
formato da primeira, então a segunda nunca precisa ser filtrada à mão.
ATIVA/RESERVA (a mesma distinção de carreira militar da OBM) e a situação —
ampla concorrência, Lei 12.990 (cota racial) ou excedente (passou da nota de
corte mas além do nº de vagas) — viram `resultado` sem tradução.

**O resultado, cruzando as quatro fontes por nome** (16/09/2026):

| Só apareceu em | Pessoas |
|---|---|
| OBMEP | 48.218 |
| OBM + OBMEP | 1.093 |
| **IME** | 370 |
| OBM | 228 |
| ITA | 221 |
| **IME + OBMEP** | 129 |
| ITA + OBMEP | 82 |
| **IME + OBM + OBMEP** | 39 |
| ITA + OBM + OBMEP | 24 |
| ITA + OBM | 2 |
| IME + OBM | 2 |
| **IME + ITA + OBM + OBMEP** | **1** |

Dos 541 aprovados do IME (ATIVA+RESERVA, 2025), **171 (32%) já tinham
aparecido em OBMEP ou OBM** — quase o mesmo terço da ITA (33%), o que por si
só é um sinal de que a validação é consistente entre os dois vestibulares, e
não coincidência de uma fonte só. E existe **uma pessoa nas quatro fontes**:

```
Paulo Vinícius Rodrigues de Azevedo
  2023  OBMEP Ouro — rede privada
  2025  OBM Menção Honrosa
  2025  ITA — Ampla Concorrência
  2025  IME (ATIVA) — Ampla Concorrência
```

Passou nos dois vestibulares mais concorridos do país no mesmo ano, depois
de anos de medalha de olimpíada — é o retrato mais completo do que a
captação por olimpíada tenta prever, e a prova está nas quatro fontes agora
cruzadas, não numa suposição.

#### 6.2.1 · Addendum (16/09/2026): o IME já é "todos os alunos" — não tem como ampliar

⚠️ **SUPERSEDIDO em 17/09/2026 — ver §11.3.** A conclusão abaixo estava
errada: existe sim uma fase intermediária nomeada ("Relação dos habilitados
para a 2ª fase"), só que a busca desta seção não a tinha encontrado. Fica
registrado por transparência — é o tipo de erro que vale mostrar, não
esconder.

O mesmo pedido que ampliou a ITA (§6.1.1, "todos os alunos, não só os
aprovados") foi conferido pro IME, e a resposta é diferente: **não tem
o que ampliar**. O CACFG só tem UMA fase escrita (a "Inspeção de Saúde" que
vem depois não reclassifica ninguém por nota), e o próprio PDF de resultado
já publica as duas relações — Aprovados (nome, a que já raspamos) e **Não
Aprovados**. A segunda existe, mas não tem NOME nenhum, só número de
inscrição — proteção de quem não passou. Sem nome não dá pra criar
`conquista_externa` (a coluna é `NOT NULL`), e mesmo que desse, não haveria
com quem cruzar. `escola_informada`/`nivel_texto` seguem sendo o único
motivo de a ITA e a OBM terem esse mesmo problema, mas aqui é o próprio nome
que falta — categoria de ausência diferente, sem solução por raspagem
nenhuma.

**Vestibular fica pra depois, e como enriquecimento, não descoberta**: listas
de aprovado de vestibular (ITA, IME, FUVEST...) normalmente só têm nome +
número de inscrição, sem escola/cidade — não dá pra criar um
`candidato_externo` novo só com isso, mas dá pra **anexar** uma conquista de
vestibular a um candidato que uma olimpíada já identificou, se o nome bater.
Isso é uma variação do resolver que ainda não foi escrita.

## 7 · Backend + tela em Administração — implementado (15/09/2026)

### 7.1 · Rotas, em [`api/app/routes/captacao.py`](../api/app/routes/captacao.py)

Seguindo o padrão de autorização existente
([api/app/auth.py](../api/app/auth.py)): `get_current_coordenador` (aceita
`coordenador` e `administrador`) — não há motivo pra restringir a
`administrador` só, é informação de leitura/triagem, não de acesso a conta.

```
GET   /captacao/candidatos           lista — filtros: uf, status_captacao,
                                      nº mínimo de conquistas, prova
GET   /captacao/candidatos/{id}      ficha — candidato + todas as
                                      conquista_externa dele, ordenadas por ano
PATCH /captacao/candidatos/{id}      só status_captacao e observacoes —
                                      os outros campos são derivados,
                                      só o resolver escreve neles
```

**Pagina de verdade desde o primeiro dia** — 53 mil candidatos e crescendo a
cada fonte nova. É diferente do resto do sistema (CLAUDE.md, armadilha nº 2:
"não existe paginação em lugar nenhum, de propósito") porque aqui o volume não
é dos ~900 alunos — é de gente de fora, sem teto natural. A paginação e o
filtro por Nº MÍNIMO DE CONQUISTAS moram no banco, não em Python: a migration
[`0058_v_candidato_externo.sql`](../api/migrations/0058_v_candidato_externo.sql)
cria a view `v_candidato_externo` (candidato + `conquistas_total`,
`provas_distintas`, `ano_mais_recente` agregados por `count`/`LEFT JOIN`,
mesmo desenho de `v_pedidos_por_cardapio` da 0052), e a rota só faz
`.gte("conquistas_total", N)` em cima dela — sem HAVING escondido em lugar
nenhum, sem SQL na rota. Filtro por prova é uma pré-consulta em
`conquista_externa` seguida de `.in_("id", ...)` na view, o mesmo desenho de
`_ids_por_topico` em `banco/consultas.py` (a view não tem `prova_id`: um
candidato cruza N provas).

### 7.2 · Frontend

Card no [`HubAdministracao.tsx`](../web/src/telas/Administracao/HubAdministracao.tsx)
(mesmo padrão de `CartaoDeCampo` que `Contas` e `Cantina` já usam — resumo
vivo "53.813 candidatos · 785 com 4+ conquistas", de duas chamadas
`por_pagina: 1` que só leem o `count="exact"` do PostgREST, sem baixar
candidato nenhum), abrindo:

```
/administracao/captacao        lista de candidatos (filtro por UF, status, nº de conquistas)
/administracao/captacao/:id    ficha — conquistas cruzadas + status_captacao + observações
```

em [`Captacao.tsx`](../web/src/telas/Administracao/Captacao.tsx) e
[`CaptacaoFicha.tsx`](../web/src/telas/Administracao/CaptacaoFicha.tsx). Rotas
declaradas em [`AppCoordenacao.tsx`](../web/src/cascos/AppCoordenacao.tsx),
mesmo arquivo que já tem `/administracao` e `/administracao/contas`. O par
lista→ficha segue a forma de `/alunos` →
[`Alunos.tsx`](../web/src/telas/Alunos/Alunos.tsx) e `/alunos/:id` →
[`AlunoFicha.tsx`](../web/src/telas/AlunoFicha/AlunoFicha.tsx) — lista
filtrável, ficha com seções —, mas a PAGINAÇÃO da lista (`ListaQuestoes.tsx`
do banco é o modelo, não `Alunos.tsx`, que rola os ~900 inteiros de propósito)
e a "série estimada hoje" da ficha (`dominio/captacao.ts`, com teste ao lado —
desloca a faixa de referência da conquista mais recente pelos anos
decorridos, e avisa quando a pessoa já deve ter saído da educação básica, em
vez de inventar uma "13ª série") são as duas coisas que este par NÃO copia de
lá.

## 8 · Em aberto

1. ~~Enriquecimento por nome (+ cidade/UF) pra fonte sem escola~~ —
   **fechado em 16/09/2026, ver §9.**
2. **PDF como fonte.** OBQ/OBQ Jr (§6, item 4) vai ser a primeira fonte que
   não é HTML estático — precisa decidir a biblioteca (o projeto já usa
   `pymupdf` em `banco-questoes/`, é candidato natural a reaproveitar).
3. **Página em JavaScript (SPA) como fonte.** A OBA (§6, item 2) parece ser
   SPA — `requests` sozinho não deve dar conta; pode precisar do Chrome MCP
   ou de achar um endpoint de API por trás da tela.
4. **Agendamento do scraper.** Hoje é rodado à mão. Quando tiver mais de 2-3
   fontes, faz sentido `infra/vps/crontab-sas` rodar isso periodicamente —
   mas só depois de validar cada fonte manualmente pelo menos uma vez (§4,
   passo 4).
5. ~~As três edições que faltam da OBMEP (2019-2021)~~ — **fechado em
   15/09/2026** (§5): eram três convenções de URL diferentes, não dado
   ausente. A janela de 10 anos (2016-2025, exceto 2020, que não existe) está
   raspada, importada e resolvida.
6. ~~Vestibular como enriquecimento~~ (§6, último parágrafo) — **fechado em
   16/09/2026 pela MESMA fila do item 1** (§9): a fila de fusão não distingue
   olimpíada de vestibular, agrupa por nome_normalizado não importa a fonte
   — ITA e IME (§6.1, §6.2) já entram nela do mesmo jeito que a OBM.
7. **AFA.** Bloqueada por Cloudflare Managed Challenge em `fab.mil.br`
   inteiro, PDF incluso (§11). Não vamos contornar bloqueio de bot
   deliberadamente. Única saída parcial achada: Diário Oficial (`in.gov.br`,
   sem bloqueio) publica só a lista final de habilitados — vale revisitar se
   um dia fizer sentido só essa fase.
8. ~~Escola Naval~~ — **fechado em 17/09/2026, ver §11.2**: `pipeline/escola_naval.py`
   construído com `id_file` curado à mão (7 de 11 anos, 2015/2017/2019
   não achados, 2020 é só retificação de edital). Cobertura desigual entre
   anos, mas real.

## 9 · Fila de fusão de baixa confiança — implementada (16/09/2026)

Fecha os itens 1 e 6 do §8: um segundo nível de match, ABAIXO do §4.1
(nome+escola exatos), pra sugerir — nunca fundir sozinho — candidatos que
compartilham só o nome. Pedido explícito depois de uma pergunta direta:
"já estamos cruzando no sentido de dizer que determinado aluno conquistou
X OBMEP, Y OBF, Z ITA, W IME?" — a resposta até aqui era "só quando a
escola bate por acaso (OBMEP↔OBF, §5.2); pra OBM/ITA/IME (sem escola) é só
análise que eu rodei fora do produto, nunca uma tela." Esta seção é a tela.

**Schema** (migration 0059): `candidato_externo_fusao_decisao` (nome_normalizado
PK, status confirmada/rejeitada, quem decidiu, quando) — só guarda a
DECISÃO humana, nunca a lista de candidatos do grupo (isso é recalculado na
leitura, igual o resolver relê tudo a cada rodada em vez de guardar
estado). A view `v_fusao_candidata` agrupa `candidato_externo` por
`nome_normalizado`, com `NOT EXISTS` contra a tabela de decisão embutido na
própria view — 6.560 grupos pendentes (15/09/2026) é gente demais pra
excluir com uma lista de nomes já decididos numa query string.

`ufs_distintas` é o sinal de confiança: 1 UF só entre todos os candidatos
do grupo é forte indício de mesma pessoa; mais de uma é o alerta — o caso
real que motivou a régua ser "sugestão", não "fusão automática", foi achado
nesta mesma conversa (Antonio Eduardo Rossano: Fortaleza/CE numa conquista
de 2019, Santa Fé do Sul/SP noutra de 2016 — pode ser mudança de cidade,
pode ser gente diferente).

**Rotas** (`routes/captacao.py`): `GET /captacao/fusoes` (fila paginada,
filtro `uf_incerta`), `GET /captacao/fusoes/{nome}` (o grupo inteiro, cada
candidato com as próprias conquistas), `POST /captacao/fusoes/confirmar` e
`.../rejeitar`. Confirmar de verdade COMBINA os `candidato_externo`: o
sobrevivente é quem já tem mais conquistas (empate → o mais antigo), as
conquistas dos outros são repassadas pra ele, o retrato (nome/escola/
cidade/UF/série) é recalculado pela conquista mais recente entre TODAS —
mesma regra que o resolver já usa (`dados_candidato`) —, e os outros
`candidato_externo` são apagados. Rejeitar só grava a decisão; nenhum dado
de captação é tocado.

**Testado com um caso real, não hipotético**: "Alan Mesquita Rios" tinha 11
`candidato_externo` (4 variações de nome de escola da OBMEP, 4 da OBM, 3 da
ITA, todos Fortaleza/CE — `ufs_distintas: 1`). Confirmando a fusão, virou UM
candidato com 12 conquistas em 3 provas (OBMEP, OBM, ITA), 2017-2025 — é
exatamente a pergunta "quais provas esse aluno já conquistou" respondida
pela tela, não mais só por SQL direto.

**Frontend**: `telas/Administracao/CaptacaoFusoes.tsx` (a fila, com o mesmo
padrão de paginação/filtro do resto da captação) e
`CaptacaoFusaoDetalhe.tsx` (o grupo lado a lado, com os dois botões — "São a
mesma pessoa" e "Não são"). Um elo quieto na lista principal
(`Captacao.tsx`) mostra quantos nomes estão esperando revisão.

## 10 · Fila de alta confiança confirmada em lote, e um alerta novo (17/09/2026)

Dos 6.560 grupos abertos pela §9, **5.864 tinham UF única** (o sinal de alta
confiança) — revisar um por um não escala, e a régua já tinha sido validada
contra um caso real (Aline Lima de Oliveira, OBMEP 2018: duas alunas
diferentes, UFs diferentes — corretamente do lado de FORA deste lote, porque
cai no grupo de UF divergente). `api/scripts/confirmar_fusoes_alta_confianca.py`
roda a MESMA lógica de `POST /captacao/fusoes/confirmar` (sobrevivente = mais
conquistas, empate pelo mais antigo) em lote, só pra `ufs_distintas <= 1`.
Rodado em produção: **5.864 grupos fundidos**, fila caiu pra **696** — só o
que precisa de olho humano.

⚠️ **Rodar o resolver DEPOIS de uma fusão em massa expõe um bug que só
aparece em escala**: uma fusão junta conquista de ESCOLAS diferentes debaixo
de um `candidato_id` só (ela funde por nome, ignora escola de propósito), mas
`resolver_candidatos_externos.py` ainda agrupava por `(nome, escola)` — dois
grupos de escola diferente emitindo patch pro MESMO `candidato_id` já
fundido, e o upsert em lote falhava com `ON CONFLICT DO UPDATE cannot affect
row a second time`. Afetava **5.479 candidatos** (achado rodando de novo o
resolver, 17/09/2026, depois do lote de fusão acima). Corrigido: o resolver
agora agrupa os patches por `candidato_id` DE VERDADE antes do upsert, não
por `(nome, escola)` — um retrato só por candidato, da conquista mais
recente entre TODAS as escolas que apontam pra ele.

**Sinalização de conflito de nível** (`api/scripts/sinalizar_fusoes_conflito_de_nivel.py`):
o mesmo teste que desqualificou a Aline — nível de ensino DIFERENTE no mesmo
ano entre candidatos do mesmo nome, fisicamente impossível — rodado contra a
fila inteira. Achou **17 grupos** (quase todos com sobrenome comum: da
Silva, dos Santos, de Oliveira), incluindo um caso com TRÊS níveis
diferentes no mesmo ano (Pedro Henrique dos Santos — provavelmente 3+
pessoas coladas, não 2). Cuidado necessário: a OBF relata série/ano (6º
ano...3ª série) enquanto OBMEP/OBM relatam "Nível N" — é a MESMA faixa em
vocabulário diferente, e comparar os dois sem traduzir gerava 34 falsos
positivos antes do ajuste. Não funde nem rejeita nada — só grava um aviso em
`observacoes`, exibido na ficha de fusão (`CaptacaoFusaoDetalhe.tsx`) antes
de alguém confirmar por engano.

## 11 · Sexta fonte: EFOMM — e por que AFA ficou de fora por enquanto (17/09/2026)

Pedido: AFA, EFOMM e Escola Naval, as três de uma vez. Pesquisadas em
paralelo antes de escrever qualquer scraper (mesma régua do §6: confira
abrindo a fonte de verdade, não confie no que parece óbvio).

**AFA — bloqueada, ficou de fora.** `fab.mil.br` inteiro devolve 403 por
Cloudflare Managed Challenge, inclusive pedindo o PDF direto (não é
certificado quebrado como o IME, é bloqueio de bot deliberado na borda).
Decisão: não contornar — driblar fingerprint de navegador automatizado pra
passar por desafio anti-bot não é caminho que este projeto vai tomar, mesmo
o dado sendo público por lei. Única saída parcial encontrada: o Diário
Oficial (`in.gov.br`, sem bloqueio) publica a lista final de habilitados à
matrícula, mas não as fases intermediárias — fica registrado como pendência
(§8), não perseguido agora.

**Escola Naval — pesquisada e construída, ver §11.2.** Os PDFs de resultado
(`inscricao.marinha.mil.br/marinha/*.pdf?id_file=N`) são abertos e com texto
extraível desde pelo menos 2016, mas a página que LISTA esses arquivos por
ano está atrás de Cloudflare — o `id_file` de cada ano foi descoberto por
busca (indexação por motor de busca), não navegação direta, e curado à mão
em `_DOCUMENTOS` do scraper.

### 11.1 · EFOMM — de "só o ciclo corrente" a 6 anos, com a mesma técnica que salvou o IME

[`pipeline/efomm.py`](../captacao-externa/pipeline/efomm.py) raspa a
Classificação Inicial (1ª fase, classificados + pós-classificados) e a
Classificação Final (titulares + reservas) do processo seletivo da EFOMM —
CIAGA (Rio de Janeiro) e CIABA (Belém), os dois centros que o mesmo concurso
alimenta.

⚠️ **Esta seção descrevia até 17/09/2026 uma limitação que não é mais real.**
A primeira versão dizia "os PDFs não têm ano no nome, a cobertura histórica
não é recuperável" — verdade só pra fonte OFICIAL. A mesma pesquisa dirigida
que expandiu o IME (§11.3) achou que sites de cursinho militar (Estratégia
Militares/Vestibulares) e até o jornal dos próprios alunos da EFOMM (Jornal
Pelicano, Belém) espelham os PDFs oficiais com o ano no CAMINHO do arquivo
— o que a fonte oficial nunca teve. `_DOCUMENTOS` virou um dicionário
curado por ano (mesmo desenho do IME/Escola Naval): **6 anos** (2017,
2022-2026), cada um confirmado baixando e lendo o PDF de verdade. Faltam
2018, 2019 e 2020 — não achados em nenhum domínio pesquisado. Dois achados
do Scribd (2016, 2021) foram DESCARTADOS por não terem sido baixados de
verdade (só preview renderizado, atrás de paywall) — a régua deste pipeline
é nunca confiar em conteúdo que não foi lido de verdade.

Achados novos no caminho:

1. **Dois hosts, comportamento oposto**: `www.marinha.mil.br/ciaga/*`
   (páginas institucionais) está atrás de Cloudflare; os PDFs de resultado,
   hospedados no espelho estático `assets.marinha.mil.br/ciaga/...`, não
   estão — mesmo domínio-mãe, zona diferente. O scraper usa sempre
   `assets.`, nunca `www.`.
2. **Mesmo certificado incompleto do IME**: `assets.marinha.mil.br` também
   não manda a cadeia intermediária — `curl` tolera, `requests` não sem
   `verify=False`.
3. **Ordem de Nome/Inscrição muda entre fase 1 e fase 4** — mesma categoria
   de armadilha da OBM (colunas fora de ordem), mas trocando a posição de
   duas colunas inteiras, não só a ordem de exibição. O parser acha a
   inscrição por regex (`\d{5,6}-\d`, formato que nunca aparece em nome) e
   trata o resto como nome, não importa a ordem.
4. **Nome comprido demais quebra a extração do PyMuPDF de um jeito que o
   IME nunca expôs**: com `sort=True`, um nome de 6+ palavras não cabe na
   coluna e o extrator devolve o INÍCIO do nome ANTES do número da
   classificação e o SOBRENOME FINAL DEPOIS da data de nascimento, na MESMA
   linha (`"MIGUEL CLAUDIO FERRO DE SÁ FERREIRA 90    102823-2 ... 30/10/2006
   VASCONCELOS"`). Sem tratar isso, 8 de 2.364 registros perdiam o nome
   inteiro, em silêncio. `_PADRAO_LINHA` ganhou grupos `prefixo`/`sufixo`
   opcionais nas duas pontas da linha — sem eles casarem, o comportamento
   pra linha normal não muda em nada.
5. **Reservas: CIAGA tem lista única e estável, CIABA não.** CIABA convoca
   reserva por boletim numerado incremental ("10 CONVOCAÇÃO DOS
   RESERVAS-CIABA.pdf", que vira "11...", "12..." a cada substituição) —
   sem nome de arquivo fixo pra apontar. Reserva do CIABA fica de fora por
   isso (mesma régua de "não dá pra confiar em URL sem padrão" do IME/AFA);
   CIAGA entra porque publica um documento único e estável, igual titular.
6. **Marcador de "pós-classificado" precisa ser específico**: a palavra
   solta "PÓS-CLASSIFICADOS" aparece primeiro no parágrafo de ABERTURA do
   PDF, antes de qualquer linha de dado — usar só ela marcava os 800/800
   candidatos da 1ª fase como pós-classificados (deviam ser 59
   classificados + 741 pós). Corrigido ancorando no título de verdade da
   seção ("Relação dos candidatos PÓS-CLASSIFICADOS").
7. **Sem escola** — mesma categoria de ITA/IME/OBM: cidade vem do "ODE"
   (onde fez a prova, não onde mora), cidades-sede traduzidas pra UF à mão
   contra o dado real (inclui Corumbá/MS, Paranaguá/PR, Parnaíba/PI e
   Santarém/PA, que não são capital).
8. **2017 tem uma fase a mais**: depois da Classificação Inicial, uma
   SEGUNDA leva de pós-classificados saiu em documento separado ("2ª
   Convocação") — mesma categoria (ainda fase 1, ainda pós-classificado),
   só publicada à parte naquele ano específico.

Números depois de raspar/importar/resolver (17/09/2026, com os 6 anos):
**8.833** `conquista_externa` (541 → 2.364 só do ciclo 2026 → 8.833 com
2017+2022-2025 somados), **5.888** pessoas distintas — todas viraram
candidato próprio (sem escola, nada funde automático). **1.692 (29%)** já
tinham aparecido em pelo menos outra fonte — quase o dobro da taxa (25%) de
quando só existia o ciclo 2026.

Reprodutível com:

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

### 11.2 · Sétima fonte: Escola Naval (CPAEN) — `id_file` curado à mão, não descoberto por padrão

[`pipeline/escola_naval.py`](../captacao-externa/pipeline/escola_naval.py)
raspa o CPAEN (Concurso Público de Admissão à Escola Naval). Diferente de
EFOMM/IME, aqui **dá pra escolher o ano** (`--anos`), porque a fonte não é
"o ciclo corrente sobrescrito" — é o oposto: cada ano tem um `id_file`
diferente e imutável, só que **descobrir esse número não tem atalho
nenhum**.

Os PDFs ficam em `www.inscricao.marinha.mil.br/marinha/<nome-livre>.pdf?
id_file=<N>` — o nome na URL é cosmético, só o `id_file` importa, e ele é um
contador SEQUENCIAL GLOBAL compartilhado por TODO concurso da Marinha
(CPAEN, CPACN/Colégio Naval, CPAEAM, QC...). A página que LISTA esses
arquivos por ano está atrás de Cloudflare managed challenge — não dá pra
navegar até o link certo. Pesquisado por busca dirigida (17/09/2026,
confirmando cada candidato baixando e lendo o PDF de verdade, nunca só o
nome do arquivo): **7 de 11 anos entre 2016 e 2025** — faltam 2015, 2017 e
2019 (não achados); 2020 existe mas é só uma retificação de EDITAL, sem nome
de candidato nenhum, por isso fora da lista. Dois "quase acertos" que a
pesquisa descartou por engano de fonte: um PDF que parecia 2015 era
CP-CEM/2014, e um que parecia 2017 era CP-PMS/2017 — outros concursos da
mesma casa, achados só depois de baixar e ler o texto, não pelo nome do
arquivo (que mentia os dois).

Cobertura desigual de propósito: cada ano trouxe o documento de MAIOR
classificação que a busca conseguiu confirmar — Resultado Final
(titular+reserva) pra 2016/2018/2021/2023/2025, "não eliminados nas provas
escritas" (única fase com nome publicado naqueles ciclos) pra 2022/2024. Não
é "todas as fases, todo ano" como o resto do §2 pede — é o que a fonte
permitiu confirmar sem inventar.

**Achado real, não suposição, no parser**: o parágrafo de ABERTURA de todo
PDF já diz "relação dos candidatos titulares e dos candidatos reservas" —
um marcador de seção que não distinguisse isso de um cabeçalho de verdade
vira a ÚLTIMA marca antes de QUALQUER linha de dado, e o documento inteiro
sai "Reserva". Aconteceu na primeira versão: 2023 e 2025 saíram 100/100 e
68/68 reserva. Corrigido restringindo a busca de marcador pra DEPOIS da
primeira menção de "Aspirante Masculino/Feminino" (que nunca aparece na
abertura) — e revelou um segundo problema no caminho: a seção feminina de
2016 usa "candidatAS titulares" (concordância de gênero), não "candidatOS
titulares", e o marcador antigo (que exigia a palavra "candidatos" antes)
nunca teria casado esse cabeçalho de jeito nenhum — o número certo de
titulares (24 masculino + 12 feminino = 36) só apareceu depois de tirar essa
exigência e casar só a palavra "titulares"/"reservas" sozinha.

**OREL não é cidade, e a maioria nem é lugar nenhum** — ao contrário de
ITA/IME (`BANCA`) e EFOMM (`ODE`), que são sempre nome de cidade, o "OREL" da
Marinha é uma unidade ADMINISTRATIVA: `SSPM`/`DEnsM` é o órgão central no
Rio, não um lugar; `Com7ºDN` é um Distrito Naval inteiro, que cobre vários
estados; só uma fração (`EAMCE`, `EAMPE`, `EAMSC`...) tem estado óbvio no
próprio nome. Inventar UF pra `CFPA`/`CPMA`/`CN`/`SNNF` sem confirmação seria
pior que não ter nenhuma — `cidade_informada`/`uf_informada` saem sempre
vazias aqui, a primeira fonte deste pipeline sem NENHUM sinal geográfico.

Números depois de raspar/importar/resolver (17/09/2026): **919**
`conquista_externa` novas, **895** pessoas distintas — 392 (44%, a maior
taxa de cruzamento de qualquer fonte sem escola até aqui) já apareciam em
outra fonte. Exemplo real, nível subindo sem conflito ano a ano e cinco
fontes diferentes desde 2019:

```
Henry Vieira Bidinotto
  2019  OBMEP Prata — rede pública (Nível 1)
  2021  OBMEP Prata — rede pública (Nível 2)
  2022  OBMEP Bronze — rede pública (Nível 3)
  2023  OBF Prata (2ª série)
  2024  Escola Naval — não eliminado nas provas escritas
  2024  OBF Prata (3ª série)
  2024  OBMEP Bronze — rede privada
  2025  IME ATIVA — ampla concorrência
  2025  ITA Convocado — 2ª fase
  2026  EFOMM (CIABA) — Classificado (1ª fase)
```

(Há uma pessoa nas SETE fontes — "João Paulo Pereira da Silva" — mas "da
Silva" é sobrenome comum demais pra confiar sem revisar: pelo menos parte
dessas sete conquistas provavelmente são pessoas diferentes com o mesmo
nome, exatamente o risco que a fila de fusão do §9 existe pra pegar.)

Reprodutível com:

```sh
cd captacao-externa
./.venv/bin/python pipeline/escola_naval.py

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
    ../captacao-externa/dados/escola_naval_*.json \
    --prova-categoria vestibular --prova-abrangencia nacional \
    --prova-fonte "https://www.marinha.mil.br/sspm/"

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

### 11.3 · IME revisitado: o §6.2.1 estava errado — tem sim uma 2ª fase (17/09/2026)

Um usuário mandou um link de mirror de cursinho pro IME
(`cdn.blog.estrategiavestibulares.com.br/.../Resultado_Final-IME.pdf`,
CACFG 2023/2024) como prova de conceito de que dava pra recuperar ano
antigo por fora da fonte oficial. A partir disso, pesquisa dirigida (em
duas rodadas) achou muito mais do que só "mais um ano de resultado final":

**Achado que invalida o §6.2.1**: o §6.2.1 (16/09/2026) dizia "o IME só tem
UMA fase escrita, não tem o que ampliar". Errado — a fonte tem sim uma fase
intermediária nomeada, **"Relação dos habilitados para a 2ª fase"**: quem
passou na prova escrita, ANTES da inspeção de saúde/documental que gera o
Resultado Final. A conclusão anterior só era verdade pro que a busca de
16/09 tinha encontrado, não pro que existe de fato — mesmo tipo de erro que
"a EFOMM não tem histórico" (§11.1) acabou de cometer.

**Três domínios/técnicas novas pra recuperar ano sobrescrito**, generalizáveis
pra qualquer fonte `.mil.br`/`.eb.br` futura:

1. **Domínio IRMÃO que não é sobrescrito.** `www.ime.eb.mil.br` (site
   institucional) mantém arquivo de resultado de anos passados
   (`/arquivos/Admissao/.../Resultados/2016-2017/...`,
   `/images/arquivos/admissao/cfg/...2020...`) que `inscricoes.ime.eb.br`
   (o site de inscrição, esse sim sobrescrito a cada ciclo) já não tem.
2. **Wayback Machine sobre o próprio caminho sobrescrito.** Como
   `inscricoes.ime.eb.br/documentos/{ATIVA,RESERVA,Resultado}.pdf` é
   reescrito a cada concurso, cada snapshot ANTIGO do Wayback congela um
   ciclo diferente por baixo da MESMA URL — a API CDX
   (`web.archive.org/cdx/search/cdx?url=...&matchType=prefix`) lista todo
   nome de arquivo já visto naquele domínio, inclusive os já sobrescritos.
   Foi assim que 2018, 2019 e 2024 apareceram.
3. **Mirror de cursinho militar publica a 2ª fase por conta própria.**
   Estratégia Militares e o mirror de vestibular da UOL (Brasil Escola/Mundo
   Educação) republicam a "Relação dos habilitados" todo outubro, com o ano
   no CAMINHO — o que a fonte oficial nunca teve.

**Também descartei coisa rodando de verdade, não só achei**: um "Resultado
Final" de 2019 (`vestibulandoweb.com.br/.../resultado-final-ime-2020.pdf`)
foi baixado e a tabela **não tinha coluna de nome nenhuma** — alguém cortou
a coluna ao reformatar pro blog. Sem nome não tem lead; esse ano só entra
pela peça de 2ª fase. Um "Resultado Final" de 2021 (via print do Diário
Oficial da União) tinha layout de tabela bem mais frágil e sem coluna de
cidade — fora desta rodada por custo/benefício, documentado no código, não
é lacuna escondida.

**Três formatos de tabela pro Resultado Final, não um só** — o layout do
PDF mudou pelo menos duas vezes na década (`pipeline/ime.py`):
`_parsear_final_padrao` (2020, 2022-2025, o formato original deste
scraper), `_parsear_final_2016` (inscrição+sigilo na MESMA linha, duas
colunas a mais de inglês quebrado, sem coluna de situação) e
`_parsear_fase2` (ord, inscrição, candidato, local, carreira — precisa de
`sort=True` do PyMuPDF, mesmo achado do EFOMM). Cada parser confere o ANO
extraído de DENTRO do PDF contra o ano esperado do dicionário, e descarta
com aviso se não bater — proteção contra a mesma fonte um dia trocar de
conteúdo por baixo do pé (já aconteceu nesta sessão: `inscricoes.ime.eb.br`
mudou de "Resultado.pdf" pra outro conteúdo entre duas pesquisas).

**Estado final, 9 de 11 anos entre 2016 e 2025**:

| Ano | Fases |
|---|---|
| 2016 | Resultado Final ATIVA+RESERVA |
| 2017 | ❌ nada achado |
| 2018 | Habilitados 2ª fase |
| 2019 | Habilitados 2ª fase (Final descartado — sem nome) |
| 2020 | Resultado Final ATIVA+RESERVA |
| 2021 | Habilitados 2ª fase (Final descartado — formato frágil) |
| 2022 | **as duas peças** |
| 2023 | **as duas peças** |
| 2024 | **as duas peças** |
| 2025 | **as duas peças** + RESERVA (oficial, ciclo corrente) |

**O cruzamento que só as duas peças juntas permitem** — quem passou na
prova escrita (2ª fase) mas não apareceu no Resultado Final, só possível
nos 4 anos com as duas peças:

| Ano | Habilitados 2ª fase | Também no Final | Sumiu do Final |
|---|---|---|---|
| 2022 | 1.044 | 532 | 512 (49%) |
| 2023 | 897 | 540 | 357 (40%) |
| 2024 | 749 | 545 | 204 (27%) |
| 2025 | 1.101 | 537 | 564 (51%) |

Entre 27% e 51% de quem passa na prova escrita do IME não aparece no
resultado final, TODO ano com as duas peças — não é ruído de amostra
pequena, é estrutural (reprova depois na inspeção de saúde/documental, ou
fica de fora do corte de vaga).

Números depois de raspar/importar/resolver (17/09/2026): **9.173**
`conquista_externa` (541 → 9.173, alta de 17x), candidato geral do pipeline
inteiro agora em **75.078** `candidato_externo` / **97.644**
`conquista_externa`. Exemplo real — passou pela 2ª fase do IME duas vezes
antes de aprovar, e está em SEIS das sete fontes:

```
Arthur Rampazio Siqueira
  2017-2023  OBMEP quase todo ano (Bronze→Ouro→Prata→Ouro→Prata→Ouro, Nível 1→2→3)
  2020,2023  OBM (Bronze, Menção Honrosa)
  2023       OBF Prata · IME Habilitado 2ª fase (não aprovou este ano)
  2024       EFOMM Classificado · Escola Naval não eliminado
  2024       IME Habilitado 2ª fase DE NOVO → ATIVA — ampla concorrência (aprovou!)
  2024-2025  ITA Convocado 2ª fase, depois Ampla Concorrência
```

Reprodutível com:

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
