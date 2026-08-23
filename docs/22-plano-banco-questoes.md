# 22 — Banco de questões ITA · IME: uma aba dentro do SAS

> **Origem:** decisão de 22/08/2026 de trazer o projeto `ita-por-assunto` para
> dentro do SAS, como aba na área do aluno e na da coordenação. O projeto existe
> desde 19/04/2026 como site estático próprio, hospedado à parte.
>
> **Escopo:** 934 questões de ITA e IME (2018–2025, Física, Química e
> Matemática), classificadas por tópico do edital, com filtros, estatísticas de
> recorrência e montagem de lista. Entra como **dado no Postgres** e **telas em
> React**, não como HTML colado.
>
> **Pronto quando:** o aluno abre a aba **Banco**, filtra por matéria e tópico,
> lê a questão no celular sem zoom, marca o que resolveu e monta a própria lista
> de estudo; o coordenador abre a mesma aba, vê a recorrência de um tópico ao
> longo dos anos e exporta uma lista em PDF ou DOCX. Nada disso depende de um
> HTML de 2,2 MB nem de um login de mentira.

---

## 1 · O ponto de partida — o que se importa e o que se joga fora

O projeto vive hoje em [ita-por-assunto/](../ita-por-assunto/), como **repositório
git aninhado dentro do SAS** — 215 MB de histórico de outro produto, não
rastreado pelo `git` do SAS. Não é um diretório do projeto; é outro projeto
morando dentro dele por acidente de pasta.

### 1.1 O que entra

| O quê | Tamanho | Por quê |
|---|---|---|
| `questoes_json/` — 934 JSONs | 5,0 MB | **A fonte da verdade.** Uma questão por arquivo, com enunciado, alternativas, gabarito, classificação e proveniência |
| `config/taxonomia*.json` — 3 arquivos | 20 KB | As taxonomias dos editais de Física, Matemática e Química |
| `pipeline/` — 12 scripts Python | 132 KB | Como uma prova nova vira JSON. Sem isso o banco congela em 2025 |
| `site/assets/banco.css` | 1.622 linhas | **Referência visual**, não código a colar (ver [§7.4](#74-o-css-não-vem-colado)) |
| `site/assets/banco.js`, `lista.js` | 1.353 linhas | **Referência de comportamento** para o port em React |

### 1.2 O que fica de fora — e por quê fica

| O quê | Tamanho | Por quê sai |
|---|---|---|
| `.git` aninhado | **215 MB** | Histórico de outro produto. Poluiria o `git log` do SAS com "ajuste2" |
| `site/banco_unificado.html` | 2,2 MB | O banco inteiro embutido inline num arquivo. É exatamente o que a API substitui |
| `output/banco_unificado.html` | 2,2 MB | Cópia gerada do anterior |
| **`site/assets/allowed-ras.json`** | 13 KB | **817 RAs de aluno servidos ao browser.** Ver [§1.3](#13-o-item-que-não-pode-entrar-nem-no-histórico) |
| `site/index.html` + `login.css` + `login.js` | 22 KB | Login cosmético. O SAS tem autenticação de verdade desde a Sprint 2 |
| `vercel.json` | — | A Vercel saiu do projeto em 13/08 ([docs/00](00-tech-stack.md)) |
| `PROMPT_CLAUDE_CODE.md`, `PROMPT_CURTO.md` | 9 KB | Andaime de quando o projeto foi escrito |
| `.vscode/tasks.json`, `.claude/settings.json` | 8 KB | Configuração de outro repo; o SAS tem a sua |
| `_relatorio.json` (84), `_classificacao_patch.json` (81) | — | Subprodutos do pipeline. Os patches já foram aplicados nos `q*.json`; o pipeline regenera |
| 3 × `.DS_Store` | 22 KB | — |

**Some 4,4 MB de HTML gerado e 215 MB de histórico.** O que entra de verdade são
os 5 MB de JSON, as taxonomias e o pipeline.

### 1.3 O item que não pode entrar nem no histórico

[`site/assets/allowed-ras.json`](../ita-por-assunto/projeto/site/assets/allowed-ras.json)
é uma lista de **817 matrículas de aluno** que o `login.js` baixa no browser e
compara em JavaScript. Isso significa que, hoje, qualquer pessoa que abra o site
baixa a lista inteira de matrículas do colégio.

Não é só "não trazer o arquivo": **ele não pode aparecer em nenhum commit do
SAS**, nem num commit que depois o remova — o objeto fica no histórico e o
`git log -p` o devolve. Como a importação vai ser um commit inicial novo
([§0.1](#01-desfazer-o-repositório-aninhado)), basta não incluí-lo. Fica
registrado aqui porque é o tipo de coisa que alguém "traz pra não perder".

O SAS já resolve esse problema de outro jeito, e melhor: `matricula` é a chave de
primeiro acesso, validada no servidor contra o e-mail do Canvas.

---

## 2 · Divisão em 6 partes

**É uma corrente até a P3, e um leque depois.** Sem dado no banco não há API; sem
API não há tela; com a tela em pé, estatística, lista e estudo são independentes.

```
P1  dado ──▶ P2  API ──▶ P3  a aba ──┬──▶ P4  estatísticas
                                     ├──▶ P5  listas
                                     └──▶ P6  estudo do aluno
                                              (corta se faltar tempo)
```

| Parte | O quê | Demonstrável quando |
|---|---|---|
| **P1** | [O dado entra no SAS](#p1--o-dado-entra-no-sas) | `select count(*) from questao_vestibular` devolve 934 |
| **P2** | [A API](#p2--a-api) | `GET /banco/questoes?materia=Física&topico=7.2` devolve a página certa |
| **P3** | [A aba, nos dois cascos](#p3--a-aba-nos-dois-cascos) | aluno e coordenador abrem `/banco` e leem uma questão a 360px |
| **P4** | [Estatísticas sem Chart.js](#p4--estatísticas-sem-chartjs) | a recorrência de um tópico por ano, em SVG à mão |
| **P5** | [Listas](#p5--listas-montar-ordenar-exportar) | montar lista, reordenar, exportar PDF e DOCX |
| **P6** | [Estudo do aluno](#p6--estudo-do-aluno-corta-se-faltar-tempo) | marcar resolvida e anotar, e o estado sobrevive à troca de aparelho |

> ⚠️ **O corte natural é o fim da P5.** P1→P5 entregam a promessa inteira para os
> dois perfis. A P6 é conforto de quem estuda; se cair, cai inteira, e o aluno
> continua com um banco filtrável e uma lista.

---

## 0 · Pré-voo — não é parte, mas trava

### 0.1 Desfazer o repositório aninhado

Hoje `ita-por-assunto/.git` existe e o `git status` do SAS mostra a pasta inteira
como um untracked só. **Decisão: o histórico não vem.** São 16 commits de outro
produto, com mensagens como `ajuste2`, e nenhum deles ajuda a entender o SAS. O
material entra como um commit inicial descrito, e este documento passa a ser a
memória de onde veio.

```sh
# fora do SAS, para não perder o original
mv ita-por-assunto ~/Documents/ita-por-assunto-original

# volta só o que a §1.1 lista, já no lugar novo
mkdir -p banco-questoes
cp -R ~/Documents/ita-por-assunto-original/projeto/questoes_json banco-questoes/
cp -R ~/Documents/ita-por-assunto-original/projeto/pipeline      banco-questoes/
cp -R ~/Documents/ita-por-assunto-original/projeto/config        banco-questoes/
find banco-questoes -name '.DS_Store' -delete
find banco-questoes -name '_relatorio.json' -o -name '_classificacao_patch.json' | xargs rm -f
```

O original fica fora do repositório, intacto, até a P1 fechar. **Não apagar antes
disso** — é a única cópia dos PDFs processados.

### 0.2 Conferir que o bucket responde

As 871 imagens de questão continuam no S3 (decisão de 22/08 — é conta própria, a
mesma que já roda SES e EventBridge, então não entra parte nova na cadeia). Mas
**não existe cópia delas em lugar nenhum**: `imagens/` está no `.gitignore` do
projeto original e a pasta não existe localmente.

Antes de prometer que o banco abre, um laço que faz `HEAD` nas 871 URLs e conta
os que não devolvem 200. Cinco minutos. Se algum falhar, é melhor saber agora do
que na primeira aula.

> ⬜ **Registrado como dívida consciente:** sem cópia local, o banco depende de o
> bucket continuar existindo com `public-read`. Regerar as imagens exigiria
> reprocessar os PDFs originais, que também não estão no repositório. Um
> `sincronizar_imagens.py` resolveria em meia hora — ficou fora deste sprint por
> decisão de 22/08.

### 0.3 Decidir o rótulo da aba

`banco` (como no site hoje), `Questões` ou `ITA · IME`. Muda uma string em dois
arquivos, mas muda o que 900 pessoas leem. Este plano escreve **Banco**.

---

## P1 · O dado entra no SAS

### 1.1 Por quê o Postgres, e não os JSONs servidos direto

Serviria: são 5 MB de arquivo estático. Mas três coisas que a aba precisa não
saem de arquivo solto sem reimplementar meio banco em JavaScript:

- **Filtrar por tópico, ano, fase, vestibular e matéria ao mesmo tempo** — é um
  `WHERE` composto, e hoje o site resolve isso baixando os 2,1 MB e filtrando em
  memória.
- **Recorrência por tópico** — `GROUP BY` de uma linha, contra varrer 934 objetos.
- **Lista de questões por aluno** — precisa de dono, e dono precisa de tabela.

E há o motivo estrutural: o SAS inteiro lê por PostgREST (`cliente.table(...)`,
[CLAUDE.md](../CLAUDE.md)). Um segundo caminho de leitura seria uma exceção que
todo mundo teria que lembrar.

### 1.2 As tabelas — migration `0028`

`questao` **já existe** e é outra coisa: questão de um simulado-Quiz do Canvas,
com `simulado_id NOT NULL` ([0010](../api/migrations/0010_expansao_canvas.sql)).
A do banco é questão de prova pública, sem simulado. Nome diferente, de propósito:

```sql
CREATE TABLE questao_vestibular (
    id           text PRIMARY KEY,          -- 'ita_2019_fase1_q01'
    vestibular   text NOT NULL,             -- 'ITA' | 'IME'
    ano          int  NOT NULL,
    fase         int  NOT NULL,
    materia      text NOT NULL,             -- 'Física' | 'Química' | 'Matemática'
    numero       int  NOT NULL,
    dissertativa boolean NOT NULL DEFAULT false,
    enunciado_md text NOT NULL,
    alternativas jsonb,                     -- NULL quando dissertativa
    gabarito     text,                      -- NULL quando dissertativa
    imagem_url   text,
    usa_imagem_no_render boolean NOT NULL DEFAULT false,
    resolucao_url text,
    arquivo_origem text NOT NULL,           -- 'banco-questoes/questoes_json/ita_2019_fase1/q01.json'
    UNIQUE (vestibular, ano, fase, materia, numero)
);
```

**`id` é texto legível, não uuid.** `ita_2019_fase1_q01` já é único, já é a chave
do arquivo e do nome da imagem no S3, e é o que se digita ao investigar um
problema. Trocar por uuid custaria uma tabela de-para para nada.

**`arquivo_origem` não é enfeite** — é o que responde "de onde veio esse
enunciado errado" numa consulta só. Ver [§7.5](#75-rastreabilidade-do-erro-até-o-arquivo).

```sql
CREATE TABLE topico_taxonomia (
    materia     text NOT NULL,
    codigo      text NOT NULL,              -- '7.2'
    nome        text NOT NULL,              -- 'Ondas e Acústica'
    bloco_codigo text NOT NULL,             -- '7'
    bloco_nome  text NOT NULL,              -- 'Oscilações e Ondas Mecânicas'
    assuntos    jsonb NOT NULL,             -- a lista de tópicos do edital
    ordem       int NOT NULL,
    PRIMARY KEY (materia, codigo)
);
```

> ⚠️ **A chave é composta, e tem que ser.** `1.1` existe nas três matérias e
> significa coisas diferentes: "Fundamentos" em Física, "Conjuntos e Lógica" em
> Matemática, "Estrutura Atômica" em Química. Chave só por `codigo` misturaria as
> três em silêncio — e o sintoma apareceria como estatística errada, não como erro.

```sql
CREATE TABLE questao_vestibular_topico (
    questao_id    text NOT NULL REFERENCES questao_vestibular(id) ON DELETE CASCADE,
    materia       text NOT NULL,
    topico_codigo text NOT NULL,
    confianca     text,                     -- 'alta' | 'media' | 'baixa'
    observacao    text,
    PRIMARY KEY (questao_id, materia, topico_codigo),
    FOREIGN KEY (materia, topico_codigo) REFERENCES topico_taxonomia(materia, codigo)
);
```

Tabela de ligação e não array em `jsonb` porque **questão mista é a regra, não a
exceção** — o schema do projeto original já previa múltiplos tópicos — e porque a
recorrência da P4 é um `GROUP BY` nessa tabela.

### 1.3 O importador

[`api/app/banco/importador.py`](../api/app/banco/importador.py) — lê
`banco-questoes/questoes_json/`, valida contra o schema, e faz upsert.

Três exigências, todas por experiência já paga no projeto:

1. **Idempotente.** Rodar duas vezes não duplica nada. Corrigir um JSON e rodar de
   novo é o ciclo de trabalho normal, não uma operação especial.
2. **Falha alto, não em silêncio.** Questão com tópico que não existe na taxonomia
   **para a importação** e diz qual arquivo. É o erro que, aceito em silêncio,
   vira questão invisível no filtro.
3. **Relatório no fim.** Quantas entraram, quantas sem classificação, quantas sem
   gabarito. Os números batem com a [§8](#8--riscos) ou algo mudou.

### 1.4 Os números esperados

Conferidos em 22/08 contra os arquivos:

| | |
|---|---|
| Questões | **934** |
| ITA F1 / F2 | 234 / 210 |
| IME F1 / F2 | 280 / 210 |
| Física / Química / Matemática | 323 / 288 / 323 |
| Anos | 2018 → 2025 |
| **Sem classificação** | **40** |
| **Dissertativas** (2ª fase) | **420** |
| **Sem gabarito** | **469** |
| Com imagem no S3 | 871 |
| Confiança alta / média / baixa | 890 / 3 / 1 |

### 1.5 Pronto quando

`migrate up` e `down` limpos nos dois sentidos; o importador roda duas vezes e a
contagem não muda; `select count(*) from questao_vestibular` devolve 934; e uma
questão mista (com dois tópicos) aparece nas duas contagens da P4.

---

## P2 · A API

### 2.1 Rotas

`api/app/routes/banco.py`, prefixo `/banco`:

| Rota | O quê |
|---|---|
| `GET /banco/taxonomia` | as três árvores, com contagem de questões por tópico |
| `GET /banco/questoes` | lista paginada e filtrada |
| `GET /banco/questoes/{id}` | uma questão |
| `GET /banco/estatisticas` | recorrência por tópico, por ano e por fase |

Filtros de `GET /banco/questoes`: `materia`, `vestibular`, `ano`, `fase`,
`topico`, `busca`, `pagina`, `por_pagina`.

### 2.2 Aqui a paginação é obrigatória — e não contradiz a armadilha 2

A [armadilha 2 do CLAUDE.md](../CLAUDE.md) diz que não existe paginação em lugar
nenhum e que `PGRST_DB_MAX_ROWS` ficou sem valor **de propósito**: um teto
truncaria leitura estatística em silêncio, e a média sairia errada *sem erro*.

Isso continua valendo, e esta rota não é o mesmo caso. A diferença é o que a
resposta significa:

- **Estatística** responde "qual é a média" — uma resposta truncada é uma resposta
  **errada**, e não parece errada.
- **Navegação** responde "mostre-me questões" — uma resposta paginada é uma
  resposta **completa da pergunta feita**, e a página seguinte está a um clique.

O `GET /banco/estatisticas` agrega **no servidor**, sobre a tabela inteira; ele
nunca pagina. Quem pagina é a listagem. Os dois convivem, e é a primeira vez no
projeto em que paginar é o certo — vale a linha de comentário no código citando
esta seção, senão alguém "conserta".

### 2.3 Permissão

A leitura vale para aluno e coordenação — é conteúdo público de prova, sem dado
pessoal. O que muda por perfil é **lista** (P5) e **estudo** (P6), onde o dono é a
pessoa. `get_current_coordenador` continua guardando só o que é da coordenação.

### 2.4 Pronto quando

`GET /banco/questoes?materia=Física&topico=7.2&ano=2019` devolve só o que casa
com os três; a paginação não perde nem repete questão na virada de página; e
`GET /banco/estatisticas` bate com um `GROUP BY` rodado à mão no psql.

---

## P3 · A aba, nos dois cascos

### 3.1 Uma tela, dois cascos — não duas telas

A aba é o mesmo produto para os dois perfis. O que muda é permissão, não código.
`Banco.tsx` recebe o perfil de [`sessao.tipo()`](../web/src/servicos/sessao.ts) e
esconde o que não se aplica.

Duplicar em `telas/Aluno/Banco` e `telas/Banco` garantiria divergência: o
primeiro conserto de CSS iria para um lado só, e ninguém descobriria por meses.

### 3.2 Onde a aba entra

| Casco | Onde | Como fica |
|---|---|---|
| Coordenação | `ABAS` em [Topbar.tsx:8](../web/src/componentes/layout/Topbar.tsx#L8) | Painel · Alunos · Simulados · Ciclos · **Banco** · Auditoria · Administração |
| Aluno | `TABS` em [ShellAluno.tsx:21](../web/src/telas/Aluno/ShellAluno.tsx#L21) | Painel · Simulados · **Banco** — a bottom nav passa de 2 para 3 itens |

### 3.3 Sub-abas são rotas, não estado

O site de hoje troca de aba com `setTopTab('banco')` mudando `display`. No SAS
isso seria repetir o erro que a migração React desfez ([16 §Registro](16-plano-migracao-react.md)):
recarregar voltava ao começo.

```
/banco                    o banco
/banco/estatisticas       recorrência
/banco/lista              montar lista
/banco/mensagem           só no casco do aluno
```

### 3.4 O que sai do CDN, e para onde vai

O site carrega quatro coisas de fora. As imagens de questão ficam no S3 (conta
própria, decidido). As outras quatro **não são conta própria** e caem na regra 6
do [CLAUDE.md](../CLAUDE.md):

| Hoje | Vira |
|---|---|
| `chart.js` via jsdelivr | **[P4](#p4--estatísticas-sem-chartjs)** — SVG à mão, como todo gráfico do SAS |
| `html-docx-js` via jsdelivr | dependência **npm** — é build, não runtime; não acrescenta terceiro à página (mesmo raciocínio do `vite-plugin-pwa` em [21 §P4](21-plano-mobile.md)) |
| Google Fonts (Fraunces + Inter) | **Plus Jakarta Sans**, que o SAS já serve local em [`assets/fonts/`](../web/assets/fonts/) |
| Logos ITA / IME / Ari no S3 | asset local. O do Ari **já existe**: [`assets/ari-logo-branca.png`](../web/assets/ari-logo-branca.png) |

### 3.5 Nasce responsiva — não vira dívida da P5 do mobile

Este sprint chega logo depois do [sprint mobile](21-plano-mobile.md), e o layout
do banco tem exatamente o defeito que a P5 de lá descreve: `.sidebar` de largura
fixa ao lado do conteúdo, sem media query nenhuma.

**Construir assim seria criar dívida no dia em que ela acabou de ser mapeada.** A
aba nasce verificada a 360px, e as regras da [§1.3 do plano mobile](21-plano-mobile.md#13-a-passada-de-toque)
valem desde o primeiro commit: campo com fonte de 16px, alvo de toque de 44px,
`100dvh`, `min-width: 0` em todo item de flex e grid.

O cartão de questão é a peça crítica: hoje ele é uma imagem PNG de largura
variável dentro de um container fixo. No celular precisa de `max-width: 100%;
height: auto`, como `Histograma` e `LinhaTemporal` já ganharam.

### 3.6 Pronto quando

Aluno e coordenador abrem `/banco`, filtram por matéria e tópico e leem uma
questão com imagem — **a 360px, sem zoom e sem rolagem lateral**; recarregar em
`/banco/estatisticas` continua ali; e nenhuma requisição sai para `jsdelivr`,
`fonts.googleapis` ou `fonts.gstatic`.

---

## P4 · Estatísticas sem Chart.js

O site usa Chart.js para a curva de recorrência por tópico ao longo dos anos. A
biblioteca sai por vir de CDN de terceiro, e **não entra como npm**: o SAS não tem
biblioteca de gráfico nenhuma por decisão de projeto — é tudo SVG escrito à mão
([21 §3.1](21-plano-mobile.md#31-gráficos-svg-à-mão-com-dimensões-fixas)).

Não é reescrever do zero. Dois componentes já existem e servem:

| O que o site mostra | O que o SAS já tem |
|---|---|
| Barras de recorrência por tópico | [`Histograma`](../web/src/componentes/ui/Histograma.tsx) |
| Curva do tópico ao longo dos anos | [`LinhaTemporal`](../web/src/componentes/ui/LinhaTemporal.tsx) |

Os dois já têm `viewBox` e já ganharam `max-width: 100%` no sprint mobile — ou
seja, já escalam no celular. O trabalho é adaptar a entrada de dados, não desenhar
gráfico.

> ⚠️ **É o item mais fácil de subestimar do sprint.** "Tirar o Chart.js" soa como
> deletar uma linha; é reimplementar quatro visualizações. Se o tempo apertar, o
> corte honesto é entregar a recorrência em **tabela ordenável**
> ([`TabelaOrdenavel`](../web/src/componentes/ui/TabelaOrdenavel.tsx), que já
> existe) e deixar a curva para depois — tabela certa vale mais que gráfico pela
> metade.

**Pronto quando:** a recorrência de um tópico por ano aparece nas duas leituras
(barra e curva), os números batem com o `GROUP BY` da P2, e nada importa Chart.js.

---

## P5 · Listas: montar, ordenar, exportar

Vale para os dois perfis — decisão de 22/08. O coordenador monta lista para dar
aos alunos; o aluno monta a própria lista de estudo. É a mesma mecânica com dono
diferente.

### 5.1 Por que a lista mora no servidor, e não no `localStorage`

O site guarda tudo em `localStorage`. Isso funciona num site sem login. Aqui não:
o aluno entra no celular e no computador, e uma lista que existe só num aparelho é
uma lista que ele perde sem saber por quê. O SAS tem conta desde a Sprint 2 —
usar é o mínimo.

### 5.2 Migration `0029`

```sql
CREATE TABLE lista_questoes (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo      text NOT NULL,
    dono_tipo   text NOT NULL CHECK (dono_tipo IN ('aluno', 'coordenacao')),
    dono_id     text NOT NULL,
    criada_em   timestamptz NOT NULL DEFAULT now(),
    atualizada_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE lista_questoes_item (
    lista_id   uuid NOT NULL REFERENCES lista_questoes(id) ON DELETE CASCADE,
    questao_id text NOT NULL REFERENCES questao_vestibular(id),
    posicao    int  NOT NULL,
    PRIMARY KEY (lista_id, questao_id)
);
```

`dono_tipo` + `dono_id` em vez de duas tabelas: a lista é a mesma coisa, e separar
duplicaria as rotas de reordenar e exportar. **Toda rota filtra pelo dono da
sessão** — um aluno nunca enxerga lista de outro, e isso é teste, não comentário.

### 5.3 Exportar

O `lista.js` de hoje exporta em dois formatos, e os dois caminhos se aproveitam:

- **PDF** — abre `window.open` e chama `print()`. Continua igual; o SAS já faz isso
  na ficha do aluno ([`exportar-aluno.js`](../web/src/exportacao/exportar-aluno.js),
  com `@media print`). Reusar o padrão de lá.
- **DOCX** — `html-docx-js` vira dependência npm.

> ⚠️ **A armadilha do PDF já mordeu este projeto.** O gerador da ficha do aluno
> teve estilo inline bloqueado pela CSP apertada, e a solução foi aplicar `style`
> por CSSOM ([16 §Bugs](16-plano-migracao-react.md)). O exportador do banco monta
> HTML com estilo embutido e vai bater na mesma parede. Testar **em produção**, não
> só no dev — a CSP de dev é mais frouxa.

**Pronto quando:** os dois perfis montam lista, reordenam, e o arquivo sai nos dois
formatos com as imagens visíveis; a lista sobrevive ao logout; e um aluno
autenticado recebe 404 ao pedir a lista de outro.

---

## P6 · Estudo do aluno (corta se faltar tempo)

Duas coisas que hoje vivem em `localStorage` e uma tela estática.

- **Resolvida** e **anotação** por questão, por aluno — `questao_estudo_aluno`,
  na mesma `0029`. É o que faz o banco virar ferramenta de estudo em vez de
  catálogo.
- **`/banco/mensagem`** — a aba de mensagem (as citações e a foto), **só no casco
  do aluno**, decidido em 22/08. Tela estática, sem dado. A foto entra como asset
  local otimizado em WebP, pela mesma régua do selo do login: 1,7 MB → 11,4 KB
  ([21 §12](21-plano-mobile.md#12--estado-em-22082026)).

**Pronto quando:** o aluno marca uma questão como resolvida no celular e ela
aparece marcada quando ele abre no computador.

---

## 6 · Ordem de execução

**Onda 1 · o dado** — não depende de tela nenhuma
[0.1](#01-desfazer-o-repositório-aninhado) · [0.2](#02-conferir-que-o-bucket-responde) ·
[P1](#p1--o-dado-entra-no-sas) inteira · [P2](#p2--a-api) inteira

**Onda 2 · a aba existe**
[P3](#p3--a-aba-nos-dois-cascos) inteira, verificada a 360px **antes** de seguir —
é mais barato acertar o cartão de questão agora do que em quatro telas depois

**Onda 3 · o que a aba serve**
[P4](#p4--estatísticas-sem-chartjs) e [P5](#p5--listas-montar-ordenar-exportar), em
paralelo — não se tocam

**Onda 4 · corta se o tempo acabar**
[P6](#p6--estudo-do-aluno-corta-se-faltar-tempo)

**O corte natural é o fim da Onda 3.**

---

## 7 · Onde o código mora — e por quê ali

Esta seção existe porque o pedido foi explícito: **organizar para conseguir
debugar e referenciar depois.** A regra que gerou o mapa abaixo é uma só —
*um arquivo, uma responsabilidade, e o nome diz qual é*.

### 7.1 O material bruto fica fora do runtime

```
banco-questoes/
├── README.md                       como uma prova nova vira JSON
├── config/
│   ├── taxonomia-fisica.json
│   ├── taxonomia-matematica.json
│   └── taxonomia-quimica.json
├── questoes_json/                  934 JSONs — a fonte da verdade
│   └── ita_2019_fase1/q01.json
└── pipeline/                       os 12 scripts Python
```

**Por que não dentro de `api/`:** o pipeline não roda em requisição nenhuma. Ele
lê PDF, chama OCR e fala com o S3 — `pymupdf`, `pytesseract`, `boto3`. Pô-lo em
`api/app/` obrigaria o container da API a carregar tudo isso para nunca usar.

Os nomes dos arquivos de taxonomia mudam (`taxonomia.json` → `taxonomia-fisica.json`).
O nome antigo dizia "a taxonomia" quando são três, e a de Física era a sem
sufixo por ter sido a primeira. Isso é acidente histórico virando armadilha.

### 7.2 O domínio na API

```
api/app/
├── banco/
│   ├── __init__.py
│   ├── importador.py       JSON → Postgres, idempotente
│   ├── consultas.py        filtros → PostgREST
│   ├── estatisticas.py     recorrência por tópico, ano e fase
│   └── listas.py           montar, reordenar, persistir
├── routes/banco.py         só HTTP: valida, chama, devolve
└── schemas/banco.py        os tipos da fronteira
```

`routes/banco.py` **não tem regra**. Isso já é o padrão do projeto (`stats/` ao
lado de `routes/`) e é o que permite testar a agregação sem subir a API.

### 7.3 O front

```
web/src/
├── telas/Banco/
│   ├── Banco.tsx           casca + sub-abas; recebe o perfil
│   ├── FiltrosBanco.tsx    reusa PainelFiltros
│   ├── ListaQuestoes.tsx
│   ├── CartaoQuestao.tsx   a peça crítica no celular
│   ├── Estatisticas.tsx
│   ├── MinhaLista.tsx
│   └── exportar.ts         PDF e DOCX
├── dominio/banco.ts        filtro, ordenação, agregação — puro e testável
└── styles/banco.css
```

`dominio/banco.ts` é o que os testes cobrem. É a camada que nasceu fora do plano
na migração React e virou onde as regras vivem ([16 §Registro](16-plano-migracao-react.md));
seguir isso aqui é o que evita "testar markup".

### 7.4 O CSS não vem colado

`banco.css` tem 1.622 linhas e um sistema visual próprio: Fraunces + Inter, cores
próprias, `tokens.css` próprio. Colar isso dentro do SAS traria **duas identidades
no mesmo produto** — e o aluno atravessaria a fronteira num clique.

O CSS entra **reescrito contra os tokens do SAS**, usando o `banco.css` como
referência de layout e não como fonte. As classes seguem o padrão de namespace por
tela que o projeto usa (`painel-*`, `alu-*`, `chat-*`): aqui, `banco-*`.

### 7.5 Rastreabilidade: do erro até o arquivo

É para isto que serve `questao_vestibular.arquivo_origem`. Quando alguém disser
"a questão 23 do IME 2018 está com o enunciado picotado":

```sql
select arquivo_origem, imagem_url
from questao_vestibular
where id = 'ime_2018_fase1_q23';
-- banco-questoes/questoes_json/ime_2018_fase1/q23.json
```

Abre o arquivo, corrige, roda o importador de novo. **Sem essa coluna**, o caminho
seria adivinhar o nome da pasta a partir do id — que funciona até o dia em que a
convenção mudar.

O mesmo vale para a classificação: `questao_vestibular_topico.observacao` guarda o
motivo escrito por quem classificou (*"Ondas sonoras em tubos: características
longitudinais…"*), e `confianca` diz o quanto confiar. Uma classificação errada é
diagnosticável em vez de misteriosa.

### 7.6 O que vai para os CLAUDE.md

O projeto tem contexto por camada ([api/CLAUDE.md](../api/CLAUDE.md),
[web/CLAUDE.md](../web/CLAUDE.md)). Três linhas entram:

- **Raiz** — `banco-questoes/` no mapa, com uma frase do que é
- **api/** — que `questao` e `questao_vestibular` são coisas diferentes, e qual é
  qual. É a confusão mais provável do sprint
- **web/** — que `telas/Banco/` serve os dois cascos e por quê

---

## 8 · Riscos

1. **`questao` × `questao_vestibular`.** Dois nomes parecidos para coisas
   diferentes, num projeto que já tem `get_supabase()` sem Supabase. Mitigação: o
   comentário do schema em cada tabela dizendo o que a outra é, e a linha no
   `api/CLAUDE.md`. É o risco mais provável do sprint, e é de leitura, não de
   código.
2. **Tirar o Chart.js é reescrever quatro gráficos.** Ver [P4](#p4--estatísticas-sem-chartjs).
   Sintoma de que foi subestimado: a Onda 3 começa e a P4 não termina no dia.
3. **40 questões sem classificação e 4 com confiança não-alta.** Não podem
   simplesmente sumir do filtro por tópico — o aluno estudaria um recorte
   incompleto sem saber. Precisam de um lugar visível: "sem assunto (40)".
4. **469 questões sem gabarito** — são as dissertativas de 2ª fase, e é o esperado,
   não defeito. O cartão não pode oferecer "ver gabarito" onde não há; a 2ª fase
   tem `resolucao_url` no lugar.
5. **Enunciado com sujeira de OCR.** Amostrando os JSONs aparecem `"Valor: 0,25"`,
   número de página solto (`"E": "I e III, apenas. 7"`). Como o render usa a
   **imagem**, isso não aparece na tela — mas a busca textual vai bater nesse lixo,
   e um dia alguém vai exibir o texto. Registrar, não consertar agora.
6. **Sem cópia das imagens** ([§0.2](#02-conferir-que-o-bucket-responde)). Dívida
   aceita, escrita aqui para não virar surpresa.
7. **A CSP e o exportador.** Ver [§5.3](#53-exportar). Já mordeu uma vez.

---

## 9 · Fora do escopo, de propósito

- **Classificar as 1.031 questões dos simulados do Canvas** pela mesma taxonomia.
  É o prêmio grande — 237.081 respostas de aluno já gravadas passariam a dizer
  *em que assunto* cada um erra, que é a promessa do produto. Fica para o sprint
  seguinte, e este o deixa mais barato ao pôr a taxonomia no banco como tabela.
  O gancho `questao.assunto` espera desde a [0015](../api/migrations/0015_questao_assunto_e_controle_sync.sql).
- **Cópia local das imagens** — decidido em 22/08.
- **Processar provas novas** (2026 em diante) — o pipeline vem junto, mas rodá-lo é
  operação, não sprint.
- **Revisar as classificações** — `revisado` é `false` em todas as 934. Precisa de
  professor, não de código.
- **Busca semântica** — a busca é textual, sobre `enunciado_md`.
- **Limpar o OCR dos enunciados** — risco 5.

---

## 10 · Como se verifica

| Nível | Ferramenta | Cobre |
|---|---|---|
| Importador | `pytest` sobre um diretório de amostra | idempotência, tópico inexistente, contagens |
| Agregação | teste sem banco, em `dominio/banco.ts` e `banco/estatisticas.py` | recorrência, questão mista contada nos dois tópicos |
| API | `curl` com filtros combinados | virada de página não perde nem repete |
| Cada tela | MCP `chrome` + `emulate 390x844x3,mobile,touch` | transbordo, alvo de toque, fonte de campo |
| Terceiros | `list_network_requests` no MCP `chrome` | nenhuma requisição para jsdelivr ou fonts.google |
| Exportação | em **produção**, não só no dev | a CSP apertada (risco 7) |

---

## 11 · O que falta decidir

| # | Pergunta | Quem responde | Trava |
|---|---|---|---|
| 1 | O rótulo da aba: **Banco**, **Questões** ou **ITA · IME**? | equipe | P3, uma string |
| 2 | O aluno vê o banco inteiro, ou só o do vestibular-alvo dele? O SAS sabe o alvo (`vestibular_alvo_aluno`), mas todo aluno é avaliado contra ITA **e** IME | coordenação | P3, um filtro padrão |
| 3 | As 40 sem classificação entram visíveis, ou ficam fora até alguém classificar? | coordenação | P3, risco 3 |
| 4 | Lista do coordenador é visível para os alunos, ou é material dele? | coordenação | P5, muda o `dono_id` |

**Decidido em 22/08:** o aluno monta e exporta a própria lista; a aba de mensagem
vai só no casco do aluno; as imagens continuam no S3, sem cópia local; a
classificação das questões do Canvas fica para o sprint seguinte.

---

## 12 · Estado em 22/08/2026

**Implementado por inteiro, verificado no browser com dado real.** Branch
`feat/banco-questoes`, saindo de `origin/main` (que já traz o merge do sprint
mobile, PR #15).

| | Estado |
|---|---|
| Migrations | `0028` e `0029` — `up` / `down` / `up` limpos |
| Dado no Postgres | **934** questões · **65** tópicos · **1.399** ligações |
| Testes | 120 na API · **134** no front (eram 133) |
| Lint | os 14 arquivos do sprint passam limpos; o repo continua nos mesmos 112 (API) e 9 (front) de antes |
| Bundle do front | 491 KB → **520 KB** (+8,5 KB gzip) |

### O que saiu como planejado

- **P1** — importador idempotente, com autoconferência contra os números da
  [§1.4](#14-os-números-esperados). Roda em menos de 1s; a segunda passada não
  muda nada. `arquivo_origem` gravado em todas as 934.
- **P2** — 13 rotas. Paginação determinística verificada: página 1 e 2 de
  Matemática não repetem nem perdem questão (0 de interseção, 100 únicos).
- **P3** — a aba está nos dois cascos. Verificada a **390px e 360px**, nas
  quatro sub-abas: `scrollWidth == clientWidth` em todas, zero campo com fonte
  abaixo de 16px.
- **P4** — sem Chart.js. A recorrência sai em `TabelaOrdenavel` (749px rolando
  dentro do próprio contêiner, não escondida) e a curva por ano em
  `LinhaTemporal`.
- **P5** — lista criada, reordenada e exportada; isolamento por dono verificado
  ponta a ponta (dono → 200, outro perfil → **404**, estudo para coordenador →
  403).
- **P6** — resolvida e anotação persistem; mandar só `anotacao` não apaga
  `resolvida`.

### O que a leitura do plano não previa, e só apareceu rodando

1. **Byte NUL no enunciado derruba a importação inteira.** 53 dos 934 JSONs
   trazem controles C0 no lugar de delimitadores que a fonte do PDF não mapeou;
   8 deles têm `U+0000`, que a coluna `text` do Postgres **não aceita** — o
   PostgREST devolvia `22P05` e o lote de 200 caía junto. Não é o risco 5
   (sujeira de OCR, adiada): é caractere que o tipo não carrega. O importador
   filtra C0; os JSONs ficam intactos.
2. **A CSP de produção barrava todas as imagens de questão.**
   [`infra/vps/nginx.conf`](../infra/vps/nginx.conf) tinha `img-src 'self' data:
   blob:` e o bucket não estava lá. Em produção o cartão cairia para o texto e o
   PDF sairia sem figura — e nada disso apareceria em dev, onde a CSP é mais
   frouxa. É consequência direta de manter as imagens no S3; a origem entrou na
   política, com o porquê comentado.
3. **A referência da questão era espremida a 8px no celular.** `flex: 1` com
   `min-width: 0` fazia toda a compressão cair sobre ela — os botões de ação não
   cedem —, e "IME 2025 · Fase 2 · nº 1" virava "I...". Num banco de questões,
   cartão sem identificação é o defeito que não pode passar.
4. **Duas questões diferentes tinham o mesmo nome.** A numeração recomeça em
   cada matéria, então a nº 1 de Matemática e a nº 1 de Física do IME 2025 F2
   davam o mesmo rótulo. A matéria entrou em `rotuloQuestao`, com teste de
   regressão.
5. **`LinhaTemporal` dizia "Ciclo atual" e "Média".** Rótulos do caso de origem,
   errados aqui. Viraram props opcionais — aditivo, quem já chamava continua
   igual.

### Decisões tomadas durante a execução

- **"Sem assunto" filtra de verdade.** O plano deixava a
  [§11 item 3](#11--o-que-falta-decidir) em aberto e a primeira versão mostrava a
  contagem sem deixar clicar. Contagem que o aluno vê e não consegue abrir é pior
  que não mostrar: `topico=sem-assunto` faz a diferença de conjuntos no servidor,
  então total e paginação continuam certos.
- **DOCX virou "Exportar Word", sem dependência.** O plano previa
  `html-docx-js` como npm ([§3.4](#34-o-que-sai-do-cdn-e-para-onde-vai)); o
  pacote está parado desde 2022 e o que ele faz por baixo é embrulhar HTML num
  envelope que o Word abre. São ~30 linhas e nenhuma superfície de terceiro. Sai
  `.doc`, não `.docx` — o botão diz "Word" para não prometer OOXML.
- **Dois scripts do pipeline saíram**: `gerar_banco_unificado.py` e
  `renderizar_html.py` produziam o HTML de 2,2 MB que a API substituiu.

### O que ainda não foi tocado

- **A exportação em produção.** O PDF e o Word foram testados no dev; a CSP
  apertada só existe na VPS, e é lá que o risco 7 mora.
- **Safari real** — a aba herda os três itens não verificáveis do sprint mobile
  ([21 §12](21-plano-mobile.md#12--estado-em-22082026)).
- **Deploy.** `./infra/vps/deploy.sh --migrar` (0028→0029).
- **As três decisões de produto** da [§11](#11--o-que-falta-decidir) que sobraram:
  rótulo da aba, banco inteiro × vestibular-alvo, e lista do coordenador visível
  ao aluno.


---

## 13 · O banco é a fonte da verdade — os JSONs saíram do git

**Decisão de 22/08/2026, depois da implementação.** O plano original tratava os
934 JSONs como fonte da verdade versionada e as tabelas como projeção
descartável ([§1.1](#11-o-que-entra), [§7.5](#75-rastreabilidade-do-erro-até-o-arquivo)).
Isso inflava o repositório com 4,2 MB de dado e fazia um PR de 992 arquivos para
~30 de código. **Inverteu-se:** o Postgres guarda, o repositório guarda código.

### O que mudou no schema

Nada de `jsonb`. Dado com estrutura vira tabela, porque blob de JSON dentro de
coluna não se consulta, não se restringe e não se lê:

| Antes | Agora |
|---|---|
| `questao_vestibular.alternativas jsonb` | tabela **`questao_vestibular_alternativa`** (questao_id, letra, texto) — espelha `questao_alternativa` da 0010 |
| `topico_taxonomia.assuntos jsonb` | tabela **`topico_taxonomia_assunto`** (materia, topico_codigo, ordem, texto) |
| *(não existia)* | colunas **`fonte_pdf`**, **`fonte_pagina`** — a proveniência que `arquivo_origem` não pode mais dar |
| *(não existia)* | **`classificado_por`** e as quatro flags de extração, como colunas booleanas |

Três campos do JSON **não** viraram coluna, por serem constantes nas 934:
`imagens[]` (sempre vazio), `fonte.bbox_questao` (sempre nulo) e
`status.classificado` (derivável de haver linha na ligação).

Volume depois da normalização: 934 questões · **2.459 alternativas** em 493
questões objetivas · 65 tópicos · **351 assuntos do edital** · 1.399 ligações.

### A saída, que é o que torna isto seguro

[`scripts/exportar_banco_questoes.py`](../api/scripts/exportar_banco_questoes.py)
faz o caminho inverso: Postgres → JSON, no formato que o pipeline escreve e lê.

```sh
python -m scripts.exportar_banco_questoes                  # regrava banco-questoes/questoes_json/
python -m scripts.exportar_banco_questoes --destino /tmp/x # backup em outro lugar
python -m scripts.exportar_banco_questoes --conferir DIR   # compara com uma referência
```

O `--conferir` rodou contra os JSONs originais e deu **zero divergência** em id,
prova, número, gabarito, alternativas, `topicos_ids` e página de origem. É a
prova de que o acervo não ficou preso no banco.

### ⚠️ Duas coisas que deixaram de ser verdade

1. **`migrate down` na 0028 passa a ser irreversível.** Antes o comentário
   prometia que as 934 voltavam rodando o importador; agora o `.down.sql` manda
   exportar primeiro. Rodar o `down` sem exportar apaga o acervo.
2. **O Canvas deixa de ser o backup.** [docs/15 §7](15-plano-hospedagem-vps.md)
   dispensou backup contínuo com o argumento de que "o Canvas é o arquivo" —
   todo dado do SAS vinha de lá e podia ser resincronizado. **O banco de questões
   é o primeiro dado do SAS que o Canvas não restaura.** Junto com as imagens,
   que só existem no S3 ([§0.2](#02-conferir-que-o-bucket-responde)), o acervo
   passa a ter duas cópias únicas. Rodar o exportador periodicamente é o
   remendo; backup do Postgres é a resposta de verdade, e continua em aberto.

### Como o dado chega em produção

O importador lê de `banco-questoes/questoes_json/`, que agora é local e não
viaja no `rsync` do deploy. Então a primeira carga é um passo explícito, feito
uma vez, da máquina que tem os arquivos:

```sh
POSTGREST_URL=<postgrest de produção> python -m scripts.importar_banco_questoes
```

Depois disso o Postgres de produção é a cópia que vale, e prova nova segue o
mesmo caminho: pipeline local → importar → exportar para conferir.
