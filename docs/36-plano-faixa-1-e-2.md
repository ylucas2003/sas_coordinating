# 36 — Plano da Faixa 1 e da Faixa 2 da área do aluno

> Escrito em **05/09/2026**, a partir do inventário de
> [30](30-estado-da-implementacao.md) e das oito decisões tomadas na mesma
> data. O que este documento tem e o 30 não: as **medições do banco** que
> derrubaram três premissas do inventário, e as decisões que resolvem cada uma.
>
> O 30 continua sendo o estado (e continua sendo **gerado** de
> `web/src/dados/aluno/registro.ts`). Este aqui é o plano de execução — some
> quando terminar de ser executado.

## 0 · O que a medição no banco mudou

O 30 ordena a tabela 2 por esforço e chama as cinco rotas de "todas pequenas, e
o dado já está no Postgres". Medindo o dado, **três das cinco não eram**.

| Premissa do 30 | O que o banco diz | Consequência |
|---|---|---|
| "`nota.presente` já tem a falta; falta só parar de filtrar" | **58,7%** das notas são `presente = false` (45.862 de 78.107). **440 alunos de 1.229 têm 100% de falta.** Por trilha: ITA 70,9% de presença · ONLINE 43,9% · INDEFINIDA 13,7% | Ligar a falta sem regra faz a corrente nascer vazada. Ver §1.1 |
| "`evento_agenda` já dispara e-mail; falta a rota" | **1 evento futuro** no banco inteiro e **1 simulado** com `evento_agenda_id`. E `evento_agenda` **não tem `vestibular` nem `fase`** — o contrato pede os dois | O caso comum da contagem regressiva é não haver nada a contar. Ver §1.2 |
| "`/me/erros` é só agregar o que `/me/simulado/{id}/questoes` já devolve" | **`questao.assunto` está 100% vazio** — 0 de 1.079. E são ~200 questões erradas por aluno, pior caso 676 | A rota funcionaria; o produto ("estudar por assunto") não. **Sai da Faixa 1.** Ver §4 |
| "`/me/zona` reusa a régua que a coordenação já lê" | Verdade — `classificacao_aluno` tem 568 linhas com `zona`, `criterio_slug` e `media_recente`. Mas **`vestibular_alvo_aluno` está vazia** (0 linhas) | A régua por aluno exige coletar o alvo. Ver §1.4 |

Uma quarta correção, menor: o fixture `ZONA` de `mocks.ts` é internamente
inconsistente — `media: 6.8` com `zona: 'cinzenta'` e `corteProximaZona: 8`.
Sob `tio-leo` (corte de média 5,0 + `MARGEM_CONFORTAVEL` 1,0) uma média de 6,8
já é `top`, e o número 8 não sai de régua nenhuma. Corrigido junto.

## 1 · As decisões

### 1.1 · O que conta como falta

**Falta é `presente = false` numa nota de aluno com matrícula ativa** —
`matricula_turma.ativo_ate IS NULL`. **Sem filtro de trilha.**

A trilha ficou de fora de propósito. `INDEFINIDA` não é lixo: são 664 alunos
reais cuja `section` do Canvas o parser não entendeu (é a população do commit
59cc7ce, "section fora do padrão deixava 521 alunos fora do SAS"). Excluí-los
da corrente seria punir o aluno por um defeito de ingest. E `presente = true`
quer dizer que a pessoa fez o simulado — o dado é confiável no sentido que
importa aqui.

⚠️ **`matricula_turma.ativo_desde` entra no filtro.** É `date NOT NULL`, então
existe para todo mundo: simulado aplicado antes da entrada do aluno na turma
não conta como falta nem quebra a sequência. Sem isso, quem entrou no meio do
ano abriria a Jornada com uma corrente vazada por provas que aconteceram antes
de ele existir no colégio.

### 1.2 · A agenda vazia

**Sem próximo simulado, o bloco não é renderizado.** Não é estado vazio, não é
"nenhum simulado marcado": o bloco some.

Com 1 evento futuro no banco inteiro, o vazio seria o que quase todo aluno veria
quase sempre — e um vazio permanente ensina a ignorar aquele espaço da tela.
Quando a coordenação passar a marcar os simulados na agenda, o bloco acende
sozinho.

`vestibular` e `fase` saem do `simulado` que aponta para o evento
(`simulado.evento_agenda_id`), e são `null` quando o evento não tem simulado
ligado. ⚠️ O contrato pede `fase: number` e o banco **não tem** `simulado.fase` — a
coluna existiu e saiu na migration 0003. Quem sabe a fase hoje é `simulado.tipo`
(`fase_1` / `fase_2`), e a tradução fica na borda da API, nunca no front.

### 1.3 · A janela da sequência

**A fita cobre o ciclo corrente mais o próximo simulado; os dois números
(`simulados` e `melhor`) cobrem o ano inteiro.**

É a leitura literal de `contratos.ts` ("um elo por simulado do ciclo corrente,
mais o próximo"; `melhor` "guardado separado: ele sobrevive à quebra"). A fita
cabe no cartão da Hoje; o recorde atravessa a virada de ciclo, que é o que dá
peso à sequência.

### 1.4 · A régua, e o onboarding que ela obriga

**A régua é o vestibular alvo do aluno, e o alvo é coletado num onboarding
obrigatório** — no primeiro acesso, e para quem ainda não preencheu.

`vestibular_alvo_aluno` existe desde a migration 0001 e **nunca teve quem
escrevesse nela**. Por isso o onboarding não é enfeite do plano: sem ele a
tabela continua vazia e a régua por aluno não existe. Ele pede duas coisas, e é
onde a foto de perfil passa a ser pedida também — `PUT /me/foto` já existe e
hoje só é alcançável pela folha de perfil do casco.

Decisões menores que caem junto, registradas para não ficarem implícitas:

- **Aluno já em `top`**: `corteProximaZona` e `distancia` viram `null`, e a
  tela mostra o corte que ele já passou. O contrato não tinha caso terminal.
- **Aluno sem linha em `classificacao_aluno`** (661 dos 1.229): a rota calcula
  na hora, com o mesmo avaliador, em vez de 404. A linha é cache de lote, não
  a fonte da verdade.
- **Aluno com ITA e IME**: a régua exibida é a do **alvo mais duro** entre os
  escolhidos, e o nome dela aparece no campo `regua` — que é justamente o que
  docs/24 §2 exige ("risco" sem dizer contra qual corte é só a má notícia).

### 1.5 · A meta do ciclo

**O sistema define, e a meta é presença**: "comparecer aos N simulados do
ciclo", com N vindo do próprio calendário do ciclo.

Fecha a decisão aberta de docs/24 §9.1 pelo caminho que não inventa produto: é
verificável com `nota.presente`, não depende de XP (que está travado no backtest
de docs/29 §H) e não precisa de tela de coordenação. É literalmente o que o
fixture já dizia — a diferença é que passa a ser contado.

## 2 · Faixa 1 — o que escrever

### 2.1 · Presença · `GET /me/simulados?incluirFaltas=true`

Hoje `simulados_do_aluno` filtra `.eq("presente", True)`
([aluno_dados.py:46](../api/app/stats/aluno_dados.py)). O filtro passa a ser
condicional, e a falta volta com `nota: null` e `presente: false`.

⚠️ **O default continua `false`.** As telas que já consomem `/me/simulados`
(Hoje, Provas, Jornada) calculam média e delta sobre a lista; incluir a falta
por default mudaria número em tela sem ninguém pedir. Quem quer a falta pede.

A segunda ocorrência de `.eq("presente", True)` no arquivo (linha 328) é
**guarda de acesso** — "o aluno só consulta simulado em que tem nota" — e fica
como está.

### 2.2 · Agenda · `GET /me/agenda`

Devolve `ProximoSimulado | null`. O próximo `evento_agenda` não cancelado com
`data_evento >= hoje`, escopado ao ano letivo do aluno pelo mesmo caminho que o
motor de lembretes já usa (`resolver_audiencia`, aluno → `matricula_turma` →
`turma.ano_letivo_id` → `ciclo` → `simulado.evento_agenda_id`).

`dataAnterior` é a data do último simulado que o aluno fez, para a barra medir
o intervalo inteiro.

### 2.3 · Sequência · `GET /me/jogo`

Devolve `Sequencia`. Sobre as notas do aluno com matrícula ativa e
`data_aplicacao >= matricula_turma.ativo_desde` (§1.1):

- `simulados` — quantos simulados seguidos, do mais recente para trás, sem
  `presente = false`;
- `melhor` — a maior sequência dessas no ano inteiro;
- `corrente` — um `EloDaCorrente` por simulado do ciclo corrente, mais um elo
  `presente: null` para o próximo simulado da agenda quando existir.

### 2.4 · Onboarding · `GET/PUT /me/vestibulares` e a tela

- `GET /me/vestibulares` → `{ vestibulares: string[], completo: boolean }`.
  `completo` é o que o casco usa para decidir o desvio.
- `PUT /me/vestibulares` recebe `{ vestibulares: ['ITA'] | ['IME'] | ['ITA','IME'] }`
  e reescreve as linhas do aluno em `vestibular_alvo_aluno`.

⚠️ `vestibular_alvo_aluno` **não tem chave primária declarada** — é
`(aluno_id, vestibular)` por convenção. A escrita apaga e reinsere as linhas do
aluno em vez de fazer upsert, para não depender de constraint que não existe.

A tela é nova (`telas/aluno/Onboarding.tsx`): pergunta o alvo, oferece a foto, e
o casco desvia para ela enquanto `completo` for `false`. A foto é **opcional** —
recusar não pode barrar o acesso; o alvo é obrigatório, porque é ele que a
régua consome.

### 2.5 · Zona · `GET /me/zona`

Devolve `{ zona, media, corteProximaZona, distancia, materiaMaisCurta, regua,
materias: MateriaContraCorte[] }` — **as duas fontes numa rota só**
(`zonaEDistancia` e `cortePorMateria`).

Reusa inteiro o que já existe em `stats/`: `criterios_repo.resolver` para a
régua do alvo do aluno, `criterios.avaliar` para a zona, `criterios.endurecer`
com `MARGEM_CONFORTAVEL` para separar `top` de `cinzenta`,
`criterios.corte_da_materia` / `corte_da_media` / `e_eliminatoria` para as
barras. Nenhuma cópia da regra de corte — foi exatamente esse o defeito que a
migration 0037 corrigiu.

`corteProximaZona` por zona: `risco` → o corte do critério; `cinzenta` → corte
+ `MARGEM_CONFORTAVEL`; `top` → `null` (§1.4).

## 3 · Faixa 2

### 3.1 · Fórmula matemática — o KaTeX que já estava lá

⚠️ **A decisão de docs/27 §12 já estava tomada no código, e o documento não
sabia.** O plano original desta seção escolhia Temml por tamanho de bundle. Ao
implementar, `web/package.json` mostrou `katex: ^0.16.47` já instalado, e
`componentes/ui/Markdown.tsx` já renderizando fórmula **desde 01/09** — com
macros pt-BR (`\sen`, `\tg`, `\cotg`, `\Ω`), fontes servidas do nosso próprio
domínio (a mesma regra de CDN da armadilha 6) e uma medição de 58 fórmulas que
falhavam. Ele já desenha as resoluções do banco e as questões do treino.

Então `formulaMatematica` sai do mock **sem dependência nova**: o artefato do
Tio Léo passou a usar o `<Markdown>` que já existe. Trazer o Temml teria criado
um segundo motor de fórmula para desenhar a mesma coisa — a dívida que este
projeto vive consertando.

É mais um caso do padrão que o CLAUDE.md registra em "Onde os documentos
mentem": quando o `.md` e o código divergirem, o código vence. docs/27 §12
precisa ser corrigido.

⚠️ O risco de docs/27 §10 **continua de pé e não é resolvido por renderizar**:
fórmula bonita e errada aumenta a confiança do aluno numa resposta falsa.
Renderizar bem o LaTeX do LLM não torna o LaTeX correto. O aviso abaixo do
bloco fica — deixou de dizer "ainda não desenhamos" e passou a dizer o que
importa: confira as contas.

### 3.2 · Depoimentos

Fica como **afordância**, exatamente como está: o contrato `Depoimento` é
título e chamada, e a tela entrega o cartão com o botão.

Não vira "real" porque não é trabalho de engenharia — trava numa citação
verdadeira de aprovado e na autorização de uso do nome. Sai do estado `mock` no
`registro.ts` quando o conteúdo existir, não quando o código mudar.

### 3.3 · Meta do ciclo · `GET /me/meta`

Devolve `{ alvo, feitos, rotulo }`. `alvo` é quantos simulados o ciclo corrente
tem; `feitos` é quantos o aluno fez (`presente = true`); `rotulo` é
"Comparecer aos N simulados do ciclo".

⚠️ Hoje **nenhuma tela consome `useMetaDoCiclo`** — a contagem regressiva ocupou
o lugar dela na Hoje. Esta rota nasce com a tela que a consome, ou não nasce:
uma fonte real sem leitor é a mesma dívida que um mock sem leitor, com mais
código.

## 4 · O que sai, e o que fica de fora

**Sai: `GET /me/streak`.** Ela mede "ciclos consecutivos acima da média da
turma" — métrica relativa, que premia posição e não progresso (docs/24 §1.1).
Nenhuma tela nova a consome. Sai no mesmo commit em que `/me/jogo` entra:
enquanto as duas existirem, há duas verdades sobre o mesmo número.

**Fica de fora: `GET /me/erros`.** `questao.assunto` está 100% vazio (0 de
1.079), então `ErroTransversal.assunto` sairia `null` em toda linha e a tela
prometeria "estude por assunto" sem saber o assunto. Volta no Sprint 6, junto
com `questao_topico` — e aí a rota nasce já útil. Continua `sem-rota` no
registro, com a observação atualizada.

## 5 · Ordem de execução

A ordem é de dependência. 1 e 2 são independentes entre si; 3 depende de 1;
5 depende de 4.

| | O quê | Depende de |
|---|---|---|
| 1 | `/me/simulados?incluirFaltas` + `/me/agenda` + `/me/meta` | — |
| 2 | Fórmula do Tio Léo no `<Markdown>` que já existe | — |
| 3 | `/me/jogo`, e `/me/streak` sai junto | 1 (a regra de falta de §1.1) |
| 4 | `/me/vestibulares` + tela de onboarding + portão no casco | — |
| 5 | `/me/zona` | 4 (sem alvo não há régua) |
| 6 | `registro.ts` e `npm run inventario` | todas |

O passo 6 não é burocracia: a tarja MOCK lê o `registro.ts` e desde 04/09
aparece **em produção, para o aluno** (docs/35 §10). Fonte que virou real e
continua marcada como mock mente para 900 pessoas.

## 6 · O que a implementação achou, e o plano não previa

⚠️ Esta seção existe pela mesma razão que a última de docs/30: plano que esconde
o que deu errado na execução é pior que nenhum. **Três dos quatro achados abaixo
só apareceram RODANDO a rota contra o banco** — nenhum teste de unidade os
pegaria, porque em todos os casos o código estava certo para o campo errado.

### 6.1 · A decisão da fórmula já estava tomada no código

Está em §3.1. O plano escolhia Temml; `package.json` já trazia KaTeX e
`componentes/ui/Markdown.tsx` já renderizava fórmula desde 01/09. Nenhuma
dependência entrou. **docs/27 §12 precisa ser corrigido** — ele ainda descreve a
decisão como aberta.

### 6.2 · `cicloOrdem` se repete entre anos letivos

A fita da corrente agrupava por `cicloOrdem`, e existe um ciclo 29 de 2025 **e**
um de 2026. A primeira resposta de `/me/jogo` num aluno real trouxe provas de
setembro de 2025 e de setembro de 2026 na mesma fita. Passou a agrupar por
`cicloId`. A comparação estava certa; o campo é que não era único.

### 6.3 · A zona e a média podem discordar — e o certo é as duas discordarem

O caso real: **média 5,1, zona `risco`**. O critério da casa combina com
"todos" — só corta quem falha em TUDO (docs/18 §1.7) —, então quem segura este
aluno é uma matéria, não a média.

Isso quebrou a primeira versão de `cortes_na_regua` duas vezes, em direções
opostas, e o conserto foi separar as duas perguntas:

| Campo | Sai de | Porque |
|---|---|---|
| `corteProximaZona` | da **zona** | é a linha que a escada desenha no topo da faixa do aluno. Tirando-a da média, um aluno em `risco` recebia "CORTE 6,0" sobre a divisa risco→cinzenta, que vale 5,0 |
| `corteAtual` | da **média** | é uma afirmação sobre a pessoa — "você já passou disto". Tirando-a da zona, um aluno com média 4,67 em `cinzenta` era informado de que passou o 5,0 que não passou |

E quando a média já passou a fronteira da própria faixa, `distancia` sai `null`:
a tela esconde a cota e a frase passa a dizer o que é o caso — *"Sua média é 5,1
e já passa o corte de 5,0. O que segura você é matéria, e a mais atrasada é
Química."* Medir uma distância de média que não é o que segura o aluno apontaria
para o lugar errado com um número correto.

### 6.4 · `ime-f2` não cobra média, e isso é fiel ao edital

Um teste parametrizado sobre as cinco réguas quebrou em `ime-f2`: os mínimos do
IME na 2ª fase são todos **por matéria** (Art. 37, III) e não há número de média
no edital para a escada apontar.

A resposta é `(None, None)`, e a escada **esconde a fronteira e a cota** em vez
de desenhar "CORTE 0,0" — inventar régua é o pecado que a migration 0037
corrigiu. O veredito continua honesto: o nome do critério fica no cabeçalho
(docs/24 §2) e as distâncias que existem são as das barras por matéria.

Consequência de produto que **fica em aberto**: um aluno que mira só IME e tem
nota de Fase 2 vê a Jornada sem cota nenhuma. O desempate de quem mira os dois
já prefere a régua que consegue responder, mas quem marcou só IME não tem
desempate. Resolver isso é decisão de produto, não conserto.

## 7 · Estado da entrega

| | Fonte | Estado |
|---|---|---|
| ✅ | `presencaNosSimulados`, `sequencia`, `proximoSimulado`, `zonaEDistancia`, `cortePorMateria`, `metaDoCiclo`, `formulaMatematica` | **real**, verificadas em 390px e 1440px com sessão de aluno de verdade |
| ✅ | `GET /me/streak` | removida; o tool `meu_streak` do Tio Léo repontado para `/me/jogo` |
| ✅ | Onboarding | tela nova, portão no `AppAluno`, `GET/PUT /me/vestibulares` |
| ⏸️ | `depoimentos` | continua `mock` — trava em conteúdo editorial, não em código |
| ⏸️ | `meusErros` | continua `sem-rota`, por §4 |

Testes: **503** no backend (+41) e **341** no front. `docs/30` regenerado.
