# 41 — Captação externa · achar potenciais alunos cruzando resultados de provas públicas

> Parte **já rodou de verdade** (schema aplicado, um pipeline completo,
> 33 mil linhas cruas e 26 mil pessoas resolvidas — §5). A tela em
> Administração e as rotas de API que a alimentam **ainda não existem** — é
> desenho, não código (§7). Este documento é o registro das duas coisas
> juntas, pra quem entrar depois saber exatamente onde a linha entre "feito"
> e "planejado" está.
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

Edições raspadas: **17ª a 20ª = 2022 a 2025** (`captacao-externa/pipeline/obmep.py`).
**2019, 2020 e 2021 não estão nesta rodada** — `premiacao.obmep.org.br`
devolve 404 pra edições anteriores à 17ª; o Dossiê de Provas já havia notado
que a página-índice também não lista 2020. Onde esses três anos moram (se é
que estão publicados em algum lugar) não foi investigado ainda — é a próxima
lacuna a fechar nesta fonte antes de considerá-la "completa" pra janela de
5-7 anos decidida no §2.

Números depois de raspar, importar e resolver (ambiente local,
15/09/2026):

| Métrica | Valor |
|---|---|
| `conquista_externa` (linhas cruas) | 33.066 |
| `candidato_externo` (pessoas resolvidas) | 26.521 |
| candidatos com 2+ conquistas (repetiram medalha) | 5.096 |
| — dos quais, com 3 | 1.093 |
| — dos quais, com **4** (medalha nos 4 anos seguidos) | **178** |

Dois exemplos reais de candidato com 4 conquistas — o tipo de perfil que essa
funcionalidade existe pra achar:

```
JOAO PEDRO DE MELO RIOS — Colégio Militar de Fortaleza (CE)
  2022  Nível 1  Prata
  2023  Nível 2  Ouro
  2024  Nível 2  Ouro
  2025  Nível 3  Prata

JOAO SANTOS PEREIRA — Colégio Militar de Belo Horizonte (MG)
  2022  Nível 1  Ouro
  2023  Nível 2  Ouro
  2024  Nível 2  Ouro
  2025  Nível 3  Prata
```

Reprodutível com:

```sh
cd captacao-externa && ./.venv/bin/python pipeline/obmep.py --edicoes 17 18 19 20

cd ../api
POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/importar_captacao_externa.py \
  ../captacao-externa/dados/obmep_202*.json \
  --prova-categoria olimpiada --prova-abrangencia nacional \
  --prova-fonte https://www.obmep.org.br/premiados.htm

POSTGREST_URL=http://localhost:3000 ./.venv/bin/python scripts/resolver_candidatos_externos.py
```

(`POSTGREST_URL` explícito porque `api/.env` local não tem essa variável —
sem ela, `criar_cliente_supabase()` cairia no branch de Supabase hospedado, ver
[app/supabase_client.py](../api/app/supabase_client.py); dentro do container
`api` do compose já vem setada.)

## 6 · Próximas fontes, em ordem

Critério de ordenação: fonte publica escola/cidade/UF por premiado (senão o
match do §4.1 não tem o que comparar) **e** já tem arquivo público
multi-ano confirmado no Dossiê de Provas. Nessa ordem:

1. **OBM** — [Dossiê 01](../Dossie%20de%20Provas/01-nacionais-matematica-e-quimica.md) confirma
   `obm.org.br/quem-somos/premiados-da-obm/`, 1979-2025 numa página só.
2. **OBA** — [Dossiê 02](../Dossie%20de%20Provas/02-nacionais-biologia-astronomia-informatica-ciencias-historia.md),
   `novo.oba.org.br/medalhas` (SPA — precisa investigar se dá pra raspar sem
   navegador headless, diferente da OBMEP que é HTML estático).
3. **OBI** — mesmo arquivo do Dossiê, `olimpiada.ic.unicamp.br/passadas/`,
   1999-2025 confirmado, HTML estático.
4. **OBQ / OBQ Jr** — mesmo arquivo, `obquimica.org`, PDFs por ano (precisa de
   extração de PDF, não só HTML — primeira fonte que vai exigir isso).
5. **OPEMAT (PE) e OMEG (GO)** — [Dossiê 05](../Dossie%20de%20Provas/05-estaduais.md),
   as duas estaduais com melhor cobertura confirmada.

**Vestibular fica pra depois, e como enriquecimento, não descoberta**: listas
de aprovado de vestibular (ITA, IME, FUVEST...) normalmente só têm nome +
número de inscrição, sem escola/cidade — não dá pra criar um
`candidato_externo` novo só com isso, mas dá pra **anexar** uma conquista de
vestibular a um candidato que uma olimpíada já identificou, se o nome bater.
Isso é uma variação do resolver que ainda não foi escrita.

## 7 · O que falta: backend + tela em Administração

Desenho, não código — nada disto foi escrito ainda.

### 7.1 · Rotas (novas, em `api/app/routes/captacao.py`)

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

**Vai precisar de paginação de verdade desde o primeiro dia** — 26 mil
candidatos e crescendo a cada fonte nova. É diferente do resto do sistema
(CLAUDE.md, armadilha nº 2: "não existe paginação em lugar nenhum, de
propósito") porque aqui o volume não é dos ~900 alunos — é de gente de fora,
sem teto natural. Vale a pena olhar como `banco/` pagina hoje (é a única rota
que pagina no sistema inteiro,
[api/app/schemas/banco.py](../api/app/schemas/banco.py) explica o porquê) antes
de desenhar esta.

### 7.2 · Frontend

Card novo no [`HubAdministracao.tsx`](../web/src/telas/Administracao/HubAdministracao.tsx)
(mesmo padrão de `CartaoDeCampo` que `Contas` e `Cantina` já usam — resumo
vivo tipo "26.521 candidatos · 178 com 4 conquistas"), abrindo:

```
/administracao/captacao        lista de candidatos (filtro por UF, status, nº de conquistas)
/administracao/captacao/:id    ficha — conquistas cruzadas + status_captacao + observações
```

Rotas declaradas em [`AppCoordenacao.tsx`](../web/src/cascos/AppCoordenacao.tsx),
mesmo arquivo que já tem `/administracao` e `/administracao/contas`. O par
lista→ficha tem precedente direto pra copiar de estrutura: `/alunos` →
[`Alunos.tsx`](../web/src/telas/Alunos/Alunos.tsx) e `/alunos/:id` →
[`AlunoFicha.tsx`](../web/src/telas/AlunoFicha/AlunoFicha.tsx) — mesma forma
(lista filtrável, ficha com seções), conteúdo completamente diferente (aqui
não tem nota, tem conquista externa).

## 8 · Em aberto

1. **Fila de revisão pra match de confiança média.** Hoje só existe o match de
   alta confiança (§4.1). Um segundo nível — nome + cidade/UF, sem escola
   batendo — encontraria mais cruzamentos, mas precisa de alguém confirmando
   antes de mesclar; não faz sentido escrever isso antes de a tela do §7
   existir pra alguém revisar.
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
5. **As três edições que faltam da OBMEP (2019-2021)** — §5 já registra que
   `premiacao.obmep.org.br` não tem essas edições no padrão de URL usado;
   precisa achar onde (se é que) estão publicadas antes de considerar a fonte
   completa pra janela de 5-7 anos.
6. **Vestibular como enriquecimento** (§6, último parágrafo) — variação do
   resolver que ainda não foi desenhada em detalhe, só apontada como direção.
