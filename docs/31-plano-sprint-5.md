# 31 — Sprint 5 · O assistente com contexto, a régua do coordenador e os gráficos em camadas

> **Origem:** a proposta da [Sprint 5](19-roadmap.md#sprint-5--assistente-e-gráficos-em-camadas--5-partes)
> — Bloco D do [docs/10](10-problemas-e-visao.md), a UI de critérios de
> [18 §1.10](18-plano-sprint-2.md#110-futuro-critérios-criados-pelo-coordenador)
> e os gráficos em camadas. O áudio de 29/08 ([25 §4](25-leitura-da-coordenacao.md#4--o-chat-do-coordenador))
> não pediu sprint nova: pediu que esta subisse de prioridade.
>
> **Escopo:** o assistente passa a saber onde a pessoa está e a mandá-la a algum
> lugar; a coordenação cria a própria régua de corte sem pedir código a ninguém;
> e o mesmo gráfico se lê em três profundidades. Antes de tudo isso, a régua do
> corte vira **uma só** — puxada da Sprint 4 · P5, porque sem ela a camada
> estatística dos gráficos consagra um número que pode estar errado.
>
> **Pronto quando:** o coordenador abre o chat na ficha do Ciclo 6, pergunta
> "e a Física?" sem dizer de qual ciclo, recebe três nomes clicáveis que o
> levam às fichas, cria a régua *"7 em Mat/Fís/Quím e acima de 4 em Português"*
> pelo próprio Painel, e vê o histograma daquele ciclo em três leituras —
> a frase, o insight e a estatística — com a linha de corte vindo da régua que
> ele escolheu, não de um `4` escrito no TSX.

---

> ## Estado: **ESCRITO E TESTADO LOCALMENTE — não deployado** *(30/08/2026)*
>
> As cinco partes estão implementadas. Migrations `0037` e `0038` aplicadas no
> banco local com `up`/`down`/`up` limpos. **279 testes na API** (eram 223) e
> **233 no front** (eram 191). Lint sem regressão: ruff em 101 achados
> pré-existentes, Biome em 52.
>
> **Verificado contra dados reais** (23 ciclos, 319 alunos no Ciclo 1 · IME):
> a régua "Meta 7 nas exatas" foi criada pela API, entrou no seletor,
> classificou (311 de 319 cortados), foi versionada (Química 7 → 5, virando 294
> cortados), e as duas guardas responderam — `PATCH` em régua embutida dá 422,
> `DELETE` dá 409. A troca de régua move o corte do payload de estatísticas
> junto com a tabela.
>
> **O que faltou, e é o único item:** a verificação visual a 390px e a 360px
> ([§5.5](#55-pronto-quando)). O Chrome do MCP não subiu — havia outra
> instância segurando o perfil. O CSS novo tem os breakpoints escritos
> (`.camadas__topo` empilha em 560px, `.criterio__requisito` cai para duas
> colunas em 480px) mas ninguém olhou.
>
> **Três defeitos que a implementação encontrou** — cada um virou teste:
>
> 1. **"Sem opinião" virava corte 0,0.** Uma régua que não cobra Inglês fazia o
>    payload dizer `corte: 0.0` e `pctAprovados: 100` — o produto afirmando que
>    a turma passou numa matéria que a régua sequer menciona. Agora é `None`, e
>    `None` quer dizer *sem linha*, não *linha no chão*.
> 2. **A folga do "top" herdava o `E` do Tio Leo.** `endurecer` + `avaliar` sob
>    o combinador `todos` perdoava a matéria sem margem: um aluno com 4,5 em
>    Matemática e 9,0 no resto saía como "top". Folga é sempre pergunta de `E`.
> 3. **`desativar('tio-leo')` respondia "não existe"** quando a carga inicial da
>    `0023` ainda não tinha rodado, em vez de "essa não se remove".
>
> ## E o que a revisão adversarial achou depois
>
> Antes do PR, uma revisão de 13 agentes (6 leitores por dimensão, 6 céticos
> tentando refutar, 1 síntese) leu o diff inteiro. **23 achados sobreviveram à
> refutação; dois foram refutados.** Todos consertados, e os cinco que mais
> importam ficaram assim:
>
> | O que quebrava | Onde |
> |---|---|
> | A frase da evolução dizia **"subiu" para um aluno que caiu** — `GET /simulados` ordena por data DESCENDENTE, e só o gráfico reordenava | `dominio/evolucaoAluno.ts` |
> | Um **aluno lia o nome de outro**: o preâmbulo de contexto era montado sem olhar o perfil, e resolvia qualquer id no banco | `chat/rotas.py` |
> | O **PATCH de simulado gravava métricas com corte 5,0** em vez de 4,0: faltava o embed da matéria no `select`, e a régua caía na exigência de média | `routes/simulados.py` |
> | Com **duas ou mais matérias**, o gráfico do aluno desenhava a linha da MÉDIA sobre séries de notas por matéria | `dominio/evolucaoAluno.ts` |
> | Uma régua podia ficar **ativa e sem requisito nenhum** se o segundo insert falhasse — e régua sem requisito aprova todo mundo | `stats/criterios_repo.py` |
>
> Três desses são a mesma lição, e vale escrevê-la: **o que a P1 mudou foi o
> significado do corte**, e todo lugar que tratava "corte" como constante virou
> um bug em potencial — o `select` que não trazia a matéria, a cascata invertida
> no front, o bin do histograma que só funcionava com corte múltiplo de 0,5.

---

## 0 · O que mudou desde a proposta — leia antes de planejar

A proposta da Sprint 5 foi escrita antes da migração React terminar. **Duas das
cinco partes já foram feitas, no todo ou em parte, sem que nenhum documento
registrasse.** Levantamento feito no código em 30/08/2026:

| Parte proposta | O que o roadmap diz | O que o código diz |
|---|---|---|
| **P1** Painel não-modal (D.1) | proposta — *"o mais barato do documento 10"* | ✅ **feito**, no commit `c1e0a5f` da migração React |
| **P2** Consciência de rota (D.4) | proposta | ⏳ **intocado** — `enviarChatMensagem` manda só `{conteudo}` |
| **P3** Abertura + lacunas de tools (D.2+D.3) | proposta | 🟡 **~70% feito** — abertura inteira e 5 das 6 lacunas |
| **P4** UI de critérios | *"falta só a tela"* | ⚠️ **falta a tela E o leitor E o CRUD** |
| **P5** Gráficos em camadas | proposta | ⏳ intocado, mas a matéria-prima existe |

### 0.1 P1 já está no ar — e três documentos ainda dizem que não

[`web/styles/chat.css`](../web/styles/chat.css) não tem mais `.chat-overlay`:
ele foi apagado na migração e substituído por um `padding-right` em `#root`.
O painel **empurra** o conteúdo em telas ≥ 900px e sobrepõe abaixo disso —
a pergunta *"sobrepor ou empurrar?"* de [10 §2.8](10-problemas-e-visao.md#28-bloco-d--assistente-como-copiloto)
foi respondida em código, com as duas respostas, cada uma na largura certa.
A pergunta do Esc também: [`ChatLauncher.tsx`](../web/src/componentes/chat/ChatLauncher.tsx)
fecha no Esc **só quando o foco está dentro do painel**, e clique-fora nunca
fecha — exatamente o que o documento propunha.

Ainda dizem o contrário: [10 §1.6.4](10-problemas-e-visao.md#164-o-chat-bloqueia-a-navegação-enquanto-está-aberto)
(🔴 "o drawer é modal de fato"), [19 §3](19-roadmap.md#3--próximos-ciclos--proposta)
(P1 proposta), [25 §4.2](25-leitura-da-coordenacao.md#42-os-três-gargalos-reais)
(gargalo 1) e o cartão da Sprint 5 em [sprints.html](sprints.html). Os quatro
apontam para arquivos que **não existem mais** (`web/js/components/chat/launcher.js`).

### 0.2 P3 está quase toda feita, e ninguém contou

- [`perfisSugestoes.ts`](../web/src/dados/perfisSugestoes.ts) já entrega as três
  coisas que [10 §2.8](10-problemas-e-visao.md#apresentação-da-abertura) pedia:
  exemplos **agrupados por intenção** (Encontrar · Diagnosticar · Comparar ·
  Gerar), lista recolhível de **capacidades** ("o que mais você sabe fazer?"),
  e **separação por perfil** — o bug 🔴 do aluno lendo *"quais alunos estão em
  risco?"* está morto.
- [`chat/tools/contexto.py`](../api/app/chat/tools/contexto.py) fechou **5 das 6
  lacunas** listadas em [10 §1.6.3](10-problemas-e-visao.md#163-lacunas-o-que-é-navegável-na-plataforma-e-o-chat-não-alcança):
  `listar_alertas`, `insights_do_ciclo`, `listar_alunos` (zona/perfil/tendência/
  turma/sede), `listar_sedes`, `listar_turmas`. São **26 tools**, não 21.

O que sobra da P3 são três itens, e um deles é a P2 disfarçada (sugestões
derivadas do contexto). Ver [P3](#p3--as-lacunas-que-sobraram).

### 0.3 P4 não é "falta só a tela"

A [migration 0023](../api/migrations/0023_criterio_classificacao.sql) criou
`criterio_classificacao` e `predicado_criterio`, com os cinco critérios
embutidos carregados. **Nenhuma linha de Python lê essas tabelas.**
`criterios.py:501` monta `CRITERIOS` de literais no arquivo, e
`ciclos.py:241` serve esse dicionário. As tabelas estão em produção, com dado
correto dentro, e são um monumento a si mesmas.

Então a P4 tem três camadas, não uma: o **leitor** (DB → `Criterio`), o **CRUD
versionado**, e a **tela**. A boa notícia é que a parte difícil — o formato e o
avaliador — de fato nasceu pronta, e `classificacao_ciclo.classificar()` recebe
um `Criterio` sem perguntar de onde ele veio.

### 0.4 A régua do corte divergiu de novo — nos gráficos

A Sprint 2 matou as três cópias da regra de corte no Painel. Elas voltaram
**nos gráficos**, que a Sprint 2 não olhou:

| Onde | O que está escrito | Deveria vir de |
|---|---|---|
| [`CicloFicha.tsx:203`](../web/src/telas/CicloFicha/CicloFicha.tsx#L203) | `corte={{ valor: 4, eliminatoria: false }}` | `corte_da_materia(criterio, …)` |
| [`CicloFicha.tsx:294`](../web/src/telas/CicloFicha/CicloFicha.tsx#L294) | `corte={rec.eliminatoriaF1 ? 5 : 4}` | idem |
| [`ciclo_estatisticas.py:99,276`](../api/app/stats/ciclo_estatisticas.py#L99) | `NOTA_CORTE_FASE_2`, `CORTE_INGLES_ITA_F1 = 5.0` | idem |
| [`metricas.py:113`](../api/app/stats/metricas.py#L113) | `corte_aplicavel()` com o mesmo par de constantes | idem |
| [`classificacao.py:219-239`](../api/app/stats/classificacao.py#L219) | `zona` por `th.NOTA_CORTE_FASE_2 + th.MARGEM_TOP_SOBRE_CORTE` | idem |

É por isso que a **Sprint 4 · P5** foi puxada para cá e virou a **P1 deste
sprint** (decisão de 30/08). Fazer os gráficos em camadas por cima de um corte
literal seria dar três leituras diferentes do mesmo número errado.

### 0.5 Tarefa de pré-voo: corrigir o que os documentos dizem

Regra da casa (`CLAUDE.md` §"Onde os documentos mentem"): quando divergirem do
código, o código vence — e vale corrigir na passagem. Antes de escrever
qualquer linha:

1. [10 §1.6.4](10-problemas-e-visao.md) — trocar o 🔴 por ✅ com a data e o
   commit; o §1.6.1 idem (o bug do aluno foi corrigido); o §1.6.2 vai de 21
   para 26 tools; o §1.6.3 marca as cinco linhas fechadas.
2. [19 §3](19-roadmap.md) — a tabela da Sprint 5 vira a deste documento.
3. [25 §4.2](25-leitura-da-coordenacao.md) — gargalo 1 sai; sobram dois.
4. [sprints.html](sprints.html) — o cartão da Sprint 5, e o placar
   ("34 nos próximos 6 sprints" deixa de fechar).

**Tamanho P.** É meia hora, e é o que impede a próxima pessoa de reimplementar
um overlay que já foi removido.

---

## Divisão em 5 partes

**Não é uma corrente.** A P1 destrava a P5 e melhora a P4; P2 e P3 são um par;
o resto é independente.

```
P1  régua única  ──────────┬────▶  P5  gráficos em camadas
   (thresholds ↔ critérios)│
                           └────▶  P4  o coordenador cria a régua

P2  consciência de rota  ──────▶  P3  as lacunas que sobraram
                                      (as sugestões contextuais são da P2)
```

| Parte | O quê | Demonstrável quando | Tamanho |
|---|---|---|---|
| **P1** | [A régua vira uma só](#p1--a-régua-vira-uma-só) | mudar o corte de um critério muda a linha do gráfico, a cor da célula e a `zona` do aluno — nos três, de uma vez | M |
| **P2** | [Consciência de rota](#p2--consciência-de-rota) | abrir o chat na ficha do Ciclo 6 e perguntar "e a Física?" | M |
| **P3** | [As lacunas que sobraram](#p3--as-lacunas-que-sobraram) | "quais questões o pessoal mais errou no P22?" e "leva eu pra ficha da Ana" | M |
| **P4** | [O coordenador cria a régua](#p4--o-coordenador-cria-a-própria-régua) | ele digita a régua dele no Painel e a lista reordena | G |
| **P5** | [Gráficos em camadas](#p5--gráficos-em-camadas) | o mesmo histograma lido por um leigo e por um estatístico | M |

> ⚠️ **Honestidade de tamanho:** cinco partes com uma delas G não cabem numa
> semana. A [ordem de execução](#6--ordem-de-execução) é desenhada para que,
> se o tempo acabar no meio, o que ficou pronto seja coerente.

---

## P1 · A régua vira uma só

*(Puxada da Sprint 4 · P5 por decisão de 30/08 — [19 §3](19-roadmap.md).)*

### 1.1 Por quê: a Sprint 2 curou o Painel, não o resto

`criterios.py` é declarado no [api/CLAUDE.md](../api/CLAUDE.md) como *"a única
definição de quem passou"*. Não é — é a única definição **na rota de
classificação do ciclo**. Fora dela, quem manda ainda é `thresholds.py`, e ele
não sabe o que é ITA nem IME: tem um `NOTA_CORTE_FASE_2 = 4.0` e um
`CORTE_INGLES_ITA_F1 = 5.0` **duplicado em dois módulos**
([`metricas.py:39`](../api/app/stats/metricas.py#L39) e
[`ciclo_estatisticas.py:62`](../api/app/stats/ciclo_estatisticas.py#L62)).

O sintoma que o coordenador vê hoje: ele troca o critério para "IME — Fase 2"
no Painel, a tabela reordena com pesos 3/2,5/2,5/1/1 — e o histograma ao lado
continua desenhando a linha em 4,0 com legenda genérica. Duas partes da mesma
tela, duas réguas.

### 1.2 Decisão: `criterios.py` responde por regra; `thresholds.py` fica com calibração

A divisão não é "mover tudo". `thresholds.py` continua existindo e continua
sendo o arquivo que a coordenação edita à mão — só que **do que é calibração
estatística**, e não do que é regra de edital:

| Fica em `thresholds.py` | Vai para `criterios.py` |
|---|---|
| `JANELA_CLASSIFICACAO`, `SLOPE_MINIMO` | `NOTA_CORTE_FASE_2` |
| `PERCENTIL_ANCORA`, `FATOR_DESVIO_*` | `CORTE_INGLES_ITA_F1` (as duas cópias) |
| Tudo de alertas (`DELTA_QUEDA_SUBIDA`, `MULTIPLO_VARIANCIA`, …) | `MATERIAS_PARA_CORTE` |
| — | `MARGEM_TOP_SOBRE_CORTE` → já existe lá como `MARGEM_CONFORTAVEL` |

O critério de separação, para não virar debate a cada constante: **se o número
tem artigo de edital, é regra; se ele foi escolhido por nós olhando dados, é
calibração.**

### 1.3 O ponto que decide a parte: `zona` não tem critério escolhido

`classificacao_aluno` tem `aluno_id` como PK — **uma zona por aluno**, calculada
em lote, sem ninguém ter escolhido régua. `criterios.avaliar()` exige um
`Criterio`. Os dois modelos não casam sozinhos.

**Decisão:** existe um **critério da casa**, e ele é o `tio-leo`.

```python
# criterios.py
#: A régua institucional — a que responde quando ninguém escolheu.
#: É a do colégio, não a de um edital, porque `zona` é leitura pedagógica
#: interna (alertas, chat, tela de Alunos), não simulação de vestibular.
CRITERIO_DA_CASA = "tio-leo"
```

E `classificacao_aluno` ganha **duas colunas informativas** (migration `0037`):
`criterio_slug` e `criterio_versao`. Sem elas, `zona = 'risco'` é um veredito
sem juiz — que é exatamente o defeito que a Sprint 2 corrigiu no Painel e
deixou passar aqui.

> ⚠️ Migration que cria coluna ⇒ `docker compose restart postgrest`.
> Armadilha 1 do `CLAUDE.md`. Em produção, `./infra/vps/deploy.sh --migrar`.

### 1.4 O que muda, arquivo por arquivo

| Arquivo | Mudança |
|---|---|
| `stats/criterios.py` | ganha `CRITERIO_DA_CASA` e `materias_de_corte(criterio)` (as matérias que o critério cobra — substitui `MATERIAS_PARA_CORTE`) |
| `stats/classificacao.py` | `_classificar_zona_por_materia` recebe um `Criterio` e usa `corte_da_materia` + `MARGEM_CONFORTAVEL`; grava `criterio_slug`/`criterio_versao` |
| `stats/metricas.py` | `corte_aplicavel(simulado)` vira `corte_aplicavel(simulado, criterio)`; a constante local morre |
| `stats/ciclo_estatisticas.py` | recebe o slug do critério (query param, default `CRITERIO_DA_CASA`) e devolve `corte` **e** `criterio` no payload, como `/classificacao` já faz |
| `chat/tools/heuristicas.py` | `materias_problematicas` para de importar `NOTA_CORTE_FASE_2`; o `corte` que ela devolve passa a ser o do critério |
| `stats/thresholds.py` | perde as 4 constantes de regra; ganha comentário dizendo onde elas foram parar |
| `web/.../CicloFicha.tsx` | os três `corte={…}` literais passam a vir do payload |

### 1.5 Pronto quando

- `grep -rn "NOTA_CORTE_FASE_2\|CORTE_INGLES_ITA_F1" api/app/` devolve **só**
  `criterios.py`.
- `grep -rn "corte={{ *valor: *[0-9]" web/src/` não devolve nada.
- Trocar o critério no Painel muda **a linha do histograma** junto com a tabela.
- Um teste em `api/tests/test_criterios.py` prova que mudar o corte do
  `tio-leo` muda `zona`, `corte_aplicavel` e o payload do ciclo — os três, de
  uma alteração só.
- `0037` faz `up`/`down`/`up` limpos.

---

## P2 · Consciência de rota

### 2.1 Por quê

Hoje `enviarChatMensagem(threadId, texto, onEvento)` manda `{conteudo}` e nada
mais ([api.ts:211](../web/src/servicos/api.ts#L211)). O painel convive com a
página desde a migração — mas continua cego para ela. Perguntar *"e esse
aluno?"* não tem referente, e as sugestões de abertura são as mesmas em toda
tela.

### 2.2 Decisão: o contexto é **declarado pela tela**, não deduzido da URL

Deduzir de `location.pathname` resolve `/alunos/A023` e falha no Painel, onde o
recorte que interessa (ciclo, fase, sede, turma, critério) mora em `useState` e
**não está na URL** ([Painel.tsx:35-43](../web/src/telas/Painel/Painel.tsx#L35)).
Um contexto que funciona em três telas e mente na mais usada é pior que nenhum.

O padrão já existe e é da casa: [`ProvedorMigalhas`](../web/src/componentes/layout/migalhas.tsx)
faz exatamente isso com o **nome** da coisa aberta — a ficha declara, o casco
costura. Generaliza-se o mesmo provedor para carregar o contexto inteiro.

```ts
// web/src/dominio/contextoDaTela.ts  — puro, com teste ao lado
export interface ContextoDaTela {
  tela: string;                        // 'painel' | 'ficha-aluno' | …
  caminho: string;                     // '/alunos/A023'
  entidade?: { tipo: 'aluno' | 'ciclo' | 'simulado'; id: string; nome: string };
  recorte?: { cicloId?: string; fase?: 1 | 2; criterio?: string;
              sedeIds?: string[]; turmaIds?: string[] };
}
```

`useContextoDaTela(ctx)` é irmão de `useTituloDaTela`. Telas sem nada a declarar
não declaram nada — e o contexto cai para `{tela, caminho}`, que já é mais do
que existe hoje.

### 2.3 Backend: o contexto entra como **preâmbulo do turno**, não no system

```python
class NovaMensagem(BaseModel):
    conteudo: str
    contexto: ContextoDaTela | None = None   # validado, nunca texto livre
```

Ele entra como uma mensagem `system` **imediatamente antes** da mensagem do
usuário, e não no `perfil.system_message`. Três razões:

1. O system é fixo e cacheável; o contexto muda a cada turno.
2. O histórico persistido guarda o contexto de **cada** turno — "onde ele
   estava quando perguntou aquilo" fica reconstruível.
3. `MAX_MENSAGENS_HISTORICO = 30` é FIFO: um contexto velho sai sozinho.

⚠️ **O contexto vem do browser e é entrada não confiável.** Ele é um modelo
Pydantic com campos fechados, os ids são **resolvidos no servidor** antes de
entrar no prompt (o nome que vai para a OpenAI é o do banco, não o que o front
mandou), e nenhum campo é string livre. Sem isso, `nome` seria injeção de
prompt com assinatura da casa.

### 2.4 Chat → página: `navegar_para` é **artefato**, não link no Markdown

[`Markdown.tsx`](../web/src/componentes/chat/Markdown.tsx) recusa links de
propósito — *"o texto vem do LLM, e ampliar a gramática ampliaria a superfície
de injeção"*. A decisão continua certa. A navegação entra pelo caminho que já
existe e já é validado: **artefato**.

- Tool `navegar_para(tipo, id)` → `{"tipo": "navegacao", "payload": {"rota": "/alunos/<uuid>", "rotulo": "Ana Souza"}}`.
- A rota é **montada no servidor** a partir de `(tipo, id)`, nunca recebida
  pronta do modelo.
- [`Artefato.tsx`](../web/src/componentes/chat/Artefato.tsx) ganha o caso
  `navegacao` — e já importa `useNavigate` para a linha temporal clicável.

O resultado é o "três em risco: A, B e C, cada um clicável" do
[10 §2.8](10-problemas-e-visao.md#consciência-de-contexto), sem abrir o
Markdown para `[texto](url)`.

### 2.5 Sugestões derivadas do contexto

`SUGESTOES_COORDENADOR` vira função do contexto, com os grupos atuais como
piso. Na ficha do Ciclo 6: *"Como foi a Física neste ciclo?"*, *"Compare com o
ciclo anterior"*, *"Quem caiu do último para este?"*. Regra que fecha a porta
para promessa vazia — a mesma já escrita em `perfisSugestoes.ts`: **toda frase
gerada tem que ter tool por trás.**

### 2.6 Pronto quando

- Abrir o chat na ficha do Ciclo 6, perguntar *"e a Física?"* e receber
  resposta sobre aquele ciclo, sem nomeá-lo.
- Perguntar *"quais alunos estão em risco?"* e clicar num nome leva à ficha,
  com o painel **aberto** do outro lado.
- Um teste puro em `contextoDaTela.test.ts` cobre as 6 telas.
- Um teste de rota prova que `contexto` com id inexistente não derruba a
  mensagem — degrada para "sem contexto".

---

## P3 · As lacunas que sobraram

### 3.1 O que já foi fechado

Cinco das seis lacunas de [10 §2.8](10-problemas-e-visao.md#fechar-as-lacunas-de-tools)
estão em `chat/tools/contexto.py`. Restam **três frentes**:

| # | Tool | Por quê |
|---|---|---|
| 4 | `questoes_do_simulado` | fecha a assimetria: o aluno pergunta o que errou (`minhas_questoes_erradas`); o coordenador, que precisa da visão agregada, não tem nada |
| 5 | `comparar_alunos` / `comparar_simulados` | "Comparar" é função declarada em [04-screens](04-screens.md) e só existe para ciclos |
| 6 | `navegar_para` | implementada na [P2 §2.4](#24-chat--página-navegar_para-é-artefato-não-link-no-markdown) |

### 3.2 O teto de tools — a pergunta de [10 §2.8](10-problemas-e-visao.md) volta

*"Existe teto prático de quantas tools cabem num prompt antes da escolha
degradar?"* Com 21 já era bastante; hoje são **26**; com estas quatro passa a **30**.

**Decisão para este sprint: não agrupar ainda, mas medir.** Um teste de
regressão com ~15 perguntas conhecidas conferindo *qual tool o modelo escolhe*
custa pouco e é o único jeito de saber se a próxima tool degradou a escolha.
Sem essa medida, "agrupar por perfil de uso" é palpite caro.

### 3.3 Antes de somar tool: auditar as 26

[25 §4.2](25-leitura-da-coordenacao.md#42-os-três-gargalos-reais) diz que o
gargalo real não é a lista — é que **nada compõe**: *"cada tool responde uma
pergunta"*. Uma tool que devolve prosa não encadeia com a seguinte. A auditoria
é barata (ler 26 `return`) e pode valer mais que qualquer tool nova. Se sobrar
tempo em vez de faltar, é aqui que ele rende.

### 3.4 Pronto quando

- *"Quais questões o pessoal mais errou no P22?"* devolve lista com percentual.
- *"Compare a Ana com o Pedro"* funciona sem passar por ciclo.
- O teste de escolha de tool passa com as 30.

---

## P4 · O coordenador cria a própria régua

### 4.1 As três camadas que faltam

O pedido é o de [18 §1.10](18-plano-sprint-2.md#110-futuro-critérios-criados-pelo-coordenador):
*"nota 7 em Mat/Fís/Quím e maior que 4 em Português"*. O formato nasceu pronto —
mas **entre a tabela e a tela falta o meio**:

```
criterio_classificacao  ✅ existe (0023), com os 5 embutidos carregados
        ↓  ❌ leitor: ninguém lê essas tabelas
Criterio (dataclass)    ✅ existe, e o avaliador é puro
        ↓  ❌ CRUD versionado: nenhuma rota escreve
tela                    ❌ não existe
```

### 4.2 Decisão: o arquivo vence para os embutidos; a tabela é dos criados

É o que a própria `0023` escreveu no comentário da carga inicial — *"se os dois
divergirem, o arquivo vence"*. Formalizando:

```python
def por_slug(slug: str, cliente=None) -> Criterio:
    """Embutidos vêm do arquivo; criados vêm do banco.

    O arquivo é a fonte da verdade das 5 réguas embutidas — é onde se lê o
    artigo do edital ao lado do número. A tabela guarda o que a coordenação
    criar. Um formato, um avaliador, duas origens.
    """
```

Consequência prática boa: **sem banco, os cinco embutidos continuam
respondendo.** O Painel não fica refém de uma consulta a mais.

### 4.3 Versionamento: editar cria versão, e a versão aparece

`UNIQUE (slug, versao)` já está na tabela; o que falta é a semântica.

- `PATCH` **nunca** altera linha: insere `versao + 1` e desativa a anterior.
- `por_slug` resolve para a maior `versao` com `ativo = true`.
- O slug aceita sufixo explícito (`minha-regua@2`) para fixar uma versão.
- O payload de `/classificacao` já devolve o critério; ganha `versao`, e a
  legenda do Painel passa a mostrar "v2" quando não for a 1.

Sem isso, editar uma régua muda retroativamente os números de quem já a usou —
em silêncio. É o motivo pelo qual o campo existe desde a `0023`.

### 4.4 Rotas

| Rota | O quê |
|---|---|
| `GET /ciclos/criterios/disponiveis` | **já existe** — passa a somar os do banco |
| `GET /criterios/{slug}` | uma régua, com predicados e todas as versões |
| `POST /criterios` | cria (`embutido = false`, `versao = 1`, `criado_por` do JWT) |
| `PATCH /criterios/{slug}` | cria versão nova |
| `DELETE /criterios/{slug}` | desativa (`ativo = false`); **recusa `embutido = true`** com 409 |

**Validação no servidor, e não só no formulário** — um critério sem predicado
não eliminatório e com combinador `algum` reprova todo mundo; um com `materia`
inexistente falha em silêncio no avaliador. As duas viram 422.

### 4.5 A tela — dentro do Painel, ao lado do seletor *(decisão de 30/08)*

O `<select>` de [`SeletorCriterio`](../web/src/telas/Painel/Painel.tsx#L333)
ganha um `<optgroup>` "Minhas réguas" e um item final **"Criar régua…"**, que
abre um `Dialogo` — o mesmo componente dos outros diálogos da casa.

O diálogo tem três blocos, e o terceiro é o que faz a tela funcionar:

1. **Identidade** — nome, e a fase a que se aplica (ou nenhuma).
2. **Requisitos** — linhas de `[matéria ▾] [operador ▾] [valor]`, com os
   avançados (`eliminatório`, `entra na média`, `peso`) escondidos atrás de
   "mostrar opções do edital". A régua típica do coordenador não usa nenhum
   dos três; expô-los de saída faz o formulário parecer o que ele não é.
3. **Prévia ao vivo** — *"com esta régua, 316 de 407 alunos deste ciclo seriam
   cortados"*, recalculada a cada mudança contra o ciclo aberto. É o único
   jeito de alguém perceber que digitou 7 onde queria 4 **antes** de salvar.
   A rota `/classificacao` já devolve `total` e `cortados`; a prévia é ela com
   um critério ainda não persistido.

> ⚠️ A prévia precisa de um `POST /criterios/previa` que **avalia sem gravar**.
> Sem ele, a alternativa é criar-e-apagar, que suja a auditoria e o
> versionamento.

### 4.6 Auditoria

Criar régua é decisão de coordenação e entra na trilha —
`canal="criterio"`, ações `criterio_criado` / `criterio_versionado` /
`criterio_desativado`, com o slug em `recurso`. A coluna `canal` não tem
`CHECK` ([0025](../api/migrations/0025_evento_auditoria_canal.sql)), então
o canal novo custa só o `COMMENT` e a opção no filtro da tela `/auditoria`.

### 4.7 Migration

**Nenhuma nova para a P4** — a `0023` já tem tudo, inclusive `criado_por` e
`ativo`. As duas migrations do sprint são da P1 (`0037`) e da P2 (`0038`).

### 4.8 Pronto quando

- O coordenador cria *"7 em Mat/Fís/Quím e > 4 em Português"* pelo Painel, a
  lista reordena, e a prévia bateu com o resultado.
- Editar a régua cria `versao = 2` e a v1 continua consultável.
- `DELETE` num embutido devolve 409.
- Derrubar o banco não impede o Painel de classificar por "Tio Leo".
- A criação aparece em `/auditoria` no canal "Critérios".

---

## P5 · Gráficos em camadas

### 5.1 As três camadas, e de onde cada uma já vem

*Leigo → insight → estatística* não é para inventar conteúdo novo: **duas das
três camadas já existem no backend**, separadas em outro lugar da tela.

| Camada | O que mostra | De onde vem |
|---|---|---|
| **Leigo** | uma frase e o essencial do desenho: barras, linha de corte, média | derivada no front, função pura em `src/dominio/` |
| **Insight** | 3–5 bullets em linguagem de colega | `insight_ciclo`, tipo `pratico` — **já existe** ([insights.py](../api/app/stats/insights.py)) |
| **Estatística** | mediana, quartis, desvio, KDE, eixo absoluto, comparação com o ciclo anterior | `tipo = tecnico` + as opções opt-in que o [`Histograma`](../web/src/componentes/ui/Histograma.tsx) **já aceita** |

A [`CicloFicha`](../web/src/telas/CicloFicha/CicloFicha.tsx) já faz isso — mas
**por página**, num acordeão "mostrar dados estatísticos avançados" que leva
junto tudo da página. As outras quatro telas de gráfico não fazem nada disso.

### 5.2 Decisão: o controle é **por gráfico** *(30/08)*

Cada gráfico carrega a própria profundidade. Segue o padrão que a `CicloFicha`
estabeleceu, uma granularidade abaixo. Consequências assumidas:

- **A camada é estado local do componente**, não preferência global — nada de
  persistir, nada de sincronizar entre telas.
- Dois gráficos lado a lado podem estar em camadas diferentes, e isso é
  desejável: comparar a distribuição bruta de um com a leitura do outro.
- O acordeão de página da `CicloFicha` **não sai** neste sprint: ele leva
  também as tabelas de estatística avançada, que não são gráfico.

### 5.3 O componente

```tsx
// componentes/ui/GraficoEmCamadas.tsx
<GraficoEmCamadas
  leigo={{ frase, grafico: <Histograma …/> }}
  insight={bullets}                    // insight_ciclo.pratico
  estatistica={{ grafico: <Histograma … kde eixoYAbsoluto/>, tabela, bullets: tecnico }}
/>
```

O seletor é o mesmo em todo lugar — três degraus rotulados, não um `▸ mais`
ambíguo — e é `<button>` real, com `aria-expanded` e foco visível
(`web-design-guidelines`). A frase da camada leigo sai de uma função pura em
`src/dominio/leituraDeGrafico.ts`, com teste ao lado: *"a maior parte da turma
ficou entre 4 e 6; 31% ficaram abaixo do corte."* **Não é LLM** — é derivada
dos mesmos números do gráfico, e por isso nunca mente nem custa token.

### 5.4 Cobertura

| Gráfico | Onde | Insight disponível? |
|---|---|---|
| `Histograma` | CicloFicha, SimuladoFicha, artefato do chat | ✅ `insight_ciclo` |
| `LinhaTemporal` | CicloFicha, Banco/Estatísticas, artefato do chat | 🟡 só no ciclo |
| `LinhaEvolucao` | AlunoFicha | 🟡 `insight_aluno_ciclo` (0016) |
| `Heatmap` | AlunoFicha | ❌ camada de insight fica vazia — e o componente lida com isso, como o `InsightsPainel` já lida |
| `Sparkline` | Alunos (tabela) | ❌ **fica de fora**: é glifo de 60px numa célula, não gráfico para ler em camadas |

### 5.5 Pronto quando

- Os quatro gráficos abrem nas três camadas, e o `Sparkline` continua como está.
- A linha de corte de todos vem do critério ([P1](#p1--a-régua-vira-uma-só)),
  com a legenda citando a régua e o artigo.
- A camada leigo tem teste puro cobrindo distribuição concentrada, bimodal e
  com n pequeno.
- Verificado a 390px e a 360px — os gráficos já são SVG responsivo, mas o
  seletor de três degraus é elemento novo numa faixa estreita.

---

## 6 · Ordem de execução

Desenhada para que parar no meio deixe algo coerente:

| # | O quê | Por que nesta posição |
|---|---|---|
| 0 | Pré-voo: corrigir os documentos ([§0.5](#05-tarefa-de-pré-voo-corrigir-o-que-os-documentos-dizem)) | meia hora; evita reimplementar o que já existe |
| 1 | **P1** régua única + `0037` | destrava P4 e P5; a outra migration é a `0038`, da P2 |
| 2 | **P5** gráficos em camadas | colhe a P1 imediatamente e é visível para o Leo |
| 3 | **P2** consciência de rota | independente; o `navegar_para` dela já é 1/3 da P3 |
| 4 | **P3** as duas tools que sobram + teste de escolha | curta, em cima da P2 |
| 5 | **P4** o coordenador cria a régua | a maior; se o tempo acabar, acaba aqui, e nada fica pela metade nas outras |

**O corte natural é o fim da 4.** P1+P5+P2+P3 já entregam "o assistente sabe
onde você está e te leva lá" e "os gráficos se leem em três níveis" — duas
frases inteiras, não meia funcionalidade em cinco lugares.

---

## 7 · Migrations

| # | O quê | Reinício do PostgREST? |
|---|---|---|
| `0037` | `classificacao_aluno.criterio_slug` + `criterio_versao` | **sim** — coluna nova (armadilha 1 do `CLAUDE.md`) |
| `0038` | `chat_artefato.tipo` passa a aceitar `'navegacao'`; `COMMENT` de `evento_auditoria.canal` ganha `criterio` | não — nenhuma coluna nova, só CHECK e comentário |

Par `.down.sql` obrigatório. As tabelas da P4 vêm da `0023`, já aplicada.

---

## 8 · Riscos

1. 🔴 **O `contexto` do chat é entrada do browser.** Mitigação em
   [§2.3](#23-backend-o-contexto-entra-como-preâmbulo-do-turno-não-no-system):
   modelo fechado, ids resolvidos no servidor, nenhum campo livre.
2. 🟠 **Recalcular `zona` com régua nova muda número que já foi lido.** Alertas
   e a tela de Alunos mudam junto. As colunas da `0037` tornam a mudança
   explicável — mas vale avisar o Leo **antes** do primeiro recálculo.
3. 🟠 **A prévia da P4 roda a classificação inteira a cada tecla.** ~1500 alunos
   sem paginação (armadilha 2). Debounce e recálculo só no `blur`.
4. 🟡 **30 tools podem degradar a escolha do modelo.** O teste de
   [§3.2](#32-o-teto-de-tools--a-pergunta-de-10-28-volta) é o que transforma
   isso de palpite em medida.
5. 🟡 **A P1 mexe em `metricas.py`, que roda no ingest.** Rodar o ingest de
   um simulado conhecido antes e depois, e comparar `metrica_simulado`.

---

## 9 · Fora do escopo, de propósito

- **Escrita pelo chat** ("marca fulano como ausente no P22"). O
  [10 §1.6.3](10-problemas-e-visao.md) já condicionava ao write-back; ele
  existe desde a Sprint 2, mas mistura permissão com conversa e merece sprint
  própria.
- **Servidor MCP do SAS.** É decisão de LGPD, não implementação —
  [25 §4.3](25-leitura-da-coordenacao.md#43-sobre-mcp).
- **Dossiê de ciclo como artefato composto** ([25 §4.4](25-leitura-da-coordenacao.md#44-conteúdo-denso-que-a-coordenação-consiga-usar)).
  Frente nova, não estava na Sprint 5.
- **Painel redimensionável / ancorável.** [10 §2.8](10-problemas-e-visao.md)
  já o tinha posto fora do primeiro corte; o corte agora é o segundo.
- **O acordeão de página da `CicloFicha`.** Ver [§5.2](#52-decisão-o-controle-é-por-gráfico-3008).
- **Sprint 4 · P1–P4 e P6.** Só a P5 foi puxada.

---

## 10 · Decisões

### Tomadas em 30/08/2026

| # | Decisão | Onde |
|---|---|---|
| 1 | A Sprint 4 · P5 (unificar `thresholds` com `criterios`) é puxada e vira a **P1** deste sprint | [§0.4](#04-a-régua-do-corte-divergiu-de-novo--nos-gráficos) |
| 2 | A tela de réguas mora **dentro do Painel**, ao lado do seletor de critério | [§4.5](#45-a-tela--dentro-do-painel-ao-lado-do-seletor-decisão-de-3008) |
| 3 | A troca de camada dos gráficos é **por gráfico**, sem preferência global | [§5.2](#52-decisão-o-controle-é-por-gráfico-3008) |
| 4 | `zona` passa a nomear a régua que a produziu; a régua da casa é `tio-leo` | [§1.3](#13-o-ponto-que-decide-a-parte-zona-não-tem-critério-escolhido) |
| 5 | Navegação chat → página é **artefato**, não link no Markdown | [§2.4](#24-chat--página-navegar_para-é-artefato-não-link-no-markdown) |
| 6 | Não agrupar tools ainda — **medir** a escolha primeiro | [§3.2](#32-o-teto-de-tools--a-pergunta-de-10-28-volta) |

### Ainda abertas

| # | Decisão | Trava | Quem |
|---|---|---|---|
| 1 | **Quem pode criar régua** — todo coordenador ou só quem administra? Hoje "todo mundo pode tudo" ([25 §5](25-leitura-da-coordenacao.md#5--decisões-em-aberto), item 4) | P4 | coordenação |
| 2 | **A régua criada pode ser usada em e-mail/Canvas**, ou é só leitura de tela? | P4 | Yan + Leo |
| 3 | **Recalcular `zona` retroativamente** ou só daqui para frente? | P1 | Yan + Leo |

---

## Fontes

- [10-problemas-e-visao.md](10-problemas-e-visao.md) §1.6, §2.8 — o Bloco D
- [18-plano-sprint-2.md](18-plano-sprint-2.md) §1.4, §1.7, §1.10 — o formato do critério
- [19-roadmap.md](19-roadmap.md) §3 — a proposta original das Sprints 4 e 5
- [25-leitura-da-coordenacao.md](25-leitura-da-coordenacao.md) §4 — o áudio de 29/08
- Código lido em 30/08/2026: `web/src/componentes/chat/`, `web/styles/chat.css`,
  `web/src/dados/perfisSugestoes.ts`, `api/app/chat/`, `api/app/stats/criterios.py`,
  `api/app/stats/thresholds.py`, `api/migrations/0023`
