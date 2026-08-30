# 24 — A jornada do aluno · do retrato à trajetória

> **Origem:** três áudios do Yan em **29/08/2026** (11h52, 11h54, 11h59). Este
> documento é a transcrição estruturada deles mais o que o código já responde.
> Nada aqui está implementado — é plano e desenho, não estado. O estado é
> [19-roadmap.md](19-roadmap.md).
>
> A frase que organiza tudo: **"como a gente cria uma jornada para o aluno sair
> de um D e ir para um A?"** Hoje a área do aluno responde *onde ele está*. Ela
> não responde *para onde ir* nem *o que fazer amanhã de manhã*.

O par deste documento, do lado da coordenação, é
[25-leitura-da-coordenacao.md](25-leitura-da-coordenacao.md).

---

## 1 · O que já existe hoje — inventário honesto

Levantado do código em 29/08, não da documentação.

| Onde | O que faz | Arquivo |
|---|---|---|
| `/` (painel) | Saudação + streak, hero do último simulado (nota, delta, percentil, posição), evolução por matéria vs. média da turma, comparação com grupos, card de insight de IA, 4 conquistas | `web/src/telas/Aluno/PainelAluno.tsx` |
| `/simulados` | Lista e ficha de cada simulado do aluno | `web/src/telas/Aluno/SimuladosAluno.tsx` |
| `/banco` | O banco ITA·IME inteiro, com filtro, lista de estudo, anotação e "resolvida" | `web/src/telas/Banco/` |
| Chat "Mentor" | 6 tools: `minhas_notas`, `meu_desempenho_em_simulado`, `minha_evolucao`, `meu_streak`, `minhas_questoes_erradas`, `meu_insight_do_ciclo` | `api/app/chat/tools_aluno.py` |
| Gamificação | Streak ("N ciclos no fôlego") + 4 badges: 3 ciclos no fôlego, primeiro 8,0, top 15%, 10 simulados | `PainelAluno.tsx` §`Conquistas` |

**Conclusão:** a base é melhor do que a conversa sugeria. O que falta não é
gráfico — é **direção**. Tudo acima olha para trás.

### 1.1 Os três buracos que o inventário revela

1. **Nenhum número olha para a frente.** Não há meta, não há "faltam X para o
   corte", não há próximo passo. O aluno lê seis indicadores e fecha a aba.
2. **`assunto` não existe do lado do aluno.** O `/banco` sabe classificar por
   tópico do edital; os simulados do colégio, não. São dois mundos que não se
   falam — e é o assunto do [§3](#3--a-ponte-que-falta-o-assunto).
3. **O streak mede a coisa errada.** Streak hoje é *"ciclos consecutivos com
   média acima da média da turma"* (`api/app/chat/prompt_aluno.py`). É
   **relativo**: uma turma inteira que melhora junto não acumula streak
   nenhum, e um aluno que estagna enquanto a turma cai ganha streak. Premia
   posição, não progresso — o oposto do que o áudio pede.

---

## 2 · O que "jornada" quer dizer, em termos do que o SAS já sabe

"Sair de um D e ir para um A" não precisa de uma escala inventada: **o SAS já
tem a escala.** `classificacao_aluno.zona` classifica cada aluno em
`risco` → `cinzenta` → `top` contra a nota de corte
(`api/app/stats/classificacao.py`), e a Sprint 2 tornou a régua um dado
(`criterio_classificacao`, migration `0023`) com cinco variantes — Tio Leo,
ITA F1/F2, IME F1/F2.

**Proposta: a jornada é a subida de zona sob uma régua nomeada, e nada mais.**

| Por que | Consequência |
|---|---|
| A escala já existe e já é auditada | não se inventa métrica nova para o aluno ver |
| A régua é a do colégio, com artigo do edital atrás | "subir de zona" significa algo fora da plataforma |
| Coordenação e aluno passam a olhar o mesmo número | hoje o coordenador vê `zona` e o aluno não sabe que ela existe |

✅ **Decidido em 29/08:** **o aluno vê a própria zona, e vê a distância até a
próxima** — *"zona de risco · faltam 0,8 em Química para sair"*. A distância é
o que torna o rótulo acionável em vez de sentença; sem ela, "risco" é só um
carimbo. Isso destrava a P2 do Sprint 7 inteira.

⚠️ **O que a decisão obriga na tela.** O rótulo nunca aparece sozinho: onde
houver zona, tem que haver a distância e a régua que a produziu ("sob o
critério Tio Leo"). Um aluno lendo "risco" sem saber contra qual corte, e sem
saber quanto falta, recebe só a má notícia.

### 2.1 Os quatro elementos de uma jornada

Nenhum deles existe hoje.

1. **Onde estou** — zona atual + distância numérica até a próxima
   (`falta 0,8 em Química para sair do risco`). O dado existe; a leitura, não.
2. **Para onde vou** — a meta do ciclo. Ou o aluno escolhe, ou o sistema
   propõe a partir do corte. Precisa de tabela nova (`meta_aluno`).
3. **O que faço agora** — **um** próximo passo, não uma lista de dez. É o
   produto de [§3](#3--a-ponte-que-falta-o-assunto) × [§4](#4--o-índice-de-importância-do-assunto).
4. **O que já andei** — histórico de zona ao longo dos ciclos. Já existe
   snapshot por ciclo (`alertas.py` compara com "a classificação anterior"),
   mas nunca foi exposto como linha do tempo do próprio aluno.

---

## 3 · A ponte que falta: o assunto

É o **pré-requisito duro de tudo neste documento**. Sem ele não há "quais
assuntos eu mais errei", não há prioridade de estudo, e o Tio Léo não tem o
que dizer além do que já diz.

### 3.1 O estado

- `questao.assunto` existe desde a migration **0015** e é **NULL em todas**.
  O comentário da coluna diz literalmente *"gancho sem classificador ainda"*.
- São **1.031 questões** de simulado do colégio e **237.081 respostas de aluno**
  já gravadas (`questao_resposta_aluno`, migration `0010`).
- Do outro lado, `questao_vestibular_topico` classifica **2.693 questões** de
  prova contra a taxonomia dos editais (`topico_taxonomia`, migration `0028`),
  com 65 tópicos e 351 assuntos.

**A alavanca:** classificar 1.031 questões faz 237.081 respostas passarem a
dizer *em que assunto* cada aluno erra. É a maior razão de retorno sobre
esforço do projeto inteiro.

### 3.2 A decisão de modelo — e ela não é a coluna que existe

`questao.assunto` é `text`. Usá-la significaria assunto em texto livre, sem
ligação com o edital — e a estatística do banco não conversaria com a do
simulado. **Recomendação: não usar a coluna 0015.** Criar
`questao_topico (questao_id, materia, topico_codigo, confianca, observacao)`,
espelhando `questao_vestibular_topico` — mesma FK composta para
`topico_taxonomia`, mesma regra de questão mista somando nos dois tópicos.

| Por quê | |
|---|---|
| Questão mista é a regra | uma coluna `text` guarda um assunto só |
| A FK composta é obrigatória | `1.1` existe nas três matérias e significa coisa diferente em cada uma (`0028`) |
| Duas estruturas para a mesma ideia são duas formas de errar | é o argumento que a própria `0028` usa sobre `questao_alternativa` |

A coluna `assunto` da 0015 vira dívida a remover — ela nunca foi escrita por
nada.

### 3.3 O buraco de cobertura que ninguém mediu ainda

**A taxonomia do edital só cobre três matérias:** Física, Química e Matemática
(`banco-questoes/config/taxonomia-*.json`). Os simulados do colégio têm também
**Português, Inglês e Redação** — e o Inglês da Fase 1 do ITA é o único
eliminatório, com corte 5,0.

Ou seja: a análise por assunto nasce **cega justamente na matéria que mais
elimina**.

✅ **Decidido em 29/08: cobrir só as três, e dizer na tela.** Não se escreve
taxonomia nova para Português, Inglês e Redação neste sprint — o Sprint 6 sai
no prazo, e o Inglês eliminatório segue acompanhado só pela nota, como é hoje.

⚠️ **O que a decisão obriga**, e não é opcional: onde houver leitura por
assunto, tem que estar escrito **quais matérias ela cobre**. É a mesma regra
que a `0028` já aplica às questões sem classificação — *"o aluno estudaria um
recorte incompleto sem saber que é incompleto"*. Um plano de revisão que
silenciosamente ignora Inglês é pior que nenhum plano, porque o aluno conclui
que está coberto.

**Fica registrado como o próximo candidato**, e o Inglês na frente do
Português: é o único com corte eliminatório, e saber se o aluno cai em leitura,
gramática ou vocabulário é acionável de um jeito que "nota 4,2 em Inglês" não
é. Redação provavelmente nunca entra — não tem "assunto" no mesmo sentido.

### 3.4 Como classificar

O pipeline do banco já faz exatamente isto e está no repositório:
`banco-questoes/pipeline/classificar.py` (listar → patch → aplicar), com a
regra de "no máximo 3 blocos distintos por questão". O que muda é a entrada:
em vez de JSON de prova, o HTML da questão do Canvas (`questao.texto`, que já
vem com LaTeX e imagem embutidos do Quiz Statistics).

⚠️ **Não roda em requisição.** Como todo o `banco-questoes/`, é trabalho de
lote, fora de `api/`.

---

## 4 · O índice de importância do assunto

O pedido do áudio 3, literal: *"a gente tem que valorizar principalmente os
últimos anos; assuntos que caíam muito e deixaram de cair passam a ser um pouco
menos importantes. É claro que isso deve ser exposto."*

### 4.1 O que existe hoje e por que não basta

`api/app/banco/estatisticas.py` já devolve, por tópico: `total`, `porAno`,
`porFase`, `porVestibular` — sem teto e sem paginação, de propósito. **É
incidência bruta.** Dois problemas para virar "importância":

1. **Anos não são comparáveis entre si.** Uma prova com 60 questões e outra
   com 30 contribuem contagens de escalas diferentes; somar as duas dá peso a
   mais ao ano com prova maior, sem que ninguém veja isso acontecer.
2. **Não há noção de tempo.** 2009 pesa igual a 2024.

### 4.2 O desenho proposto — quatro passos

**Passo 1 · Normalizar por ano.** A unidade honesta não é a contagem, é a
fatia da prova:

```
p(t, a) = questões do tópico t no ano a ÷ questões classificadas no ano a
```

`p` se lê sozinho: *"Termodinâmica foi 7% da prova de 2023"*.

**Passo 2 · Pesar por recência com meia-vida.**

```
w(a) = 0,5 ^ ((ano_referência − a) / H)          H = meia-vida, em anos
```

✅ **Decidido em 29/08: H = 5, fixa para todos.** Uma prova de 5 anos atrás vale
metade da do ano passado; de 10 anos atrás, um quarto. Explicável em uma frase
para um aluno de 16 anos, e — o que decidiu — **todo mundo vê o mesmo número**:
a coordenação discute uma régua só, e o Tio Léo sempre sabe qual ranking o
aluno está olhando. Um controle na tela ensinaria o conceito ao custo de dois
alunos verem ordens diferentes do mesmo assunto.

O valor é **parâmetro, não constante espalhada**: mora num lugar só, do mesmo
jeito que a régua de corte virou dado na Sprint 2. Mudá-lo é decisão de
coordenação, não deploy.

> **Por que meia-vida e não uma janela de 5 anos.** A janela joga fora sinal
> e cria um degrau: quando 2019 sai da janela, o número pula sem que nada
> tenha acontecido no mundo. A exponencial decai liso e nenhum ano some.

**Passo 3 · O índice.**

```
I(t) = Σ_a w(a)·p(t, a) ÷ Σ_a w(a)
```

Média ponderada das fatias anuais. Continua na unidade de `p` — *"esse tópico
vale ~4% da prova, hoje"* — e é isso que vai à tela. Um ranking 0–100
(`I(t) ÷ max I × 100`) pode acompanhar, mas **como segunda linha**: percentual
da prova é informação, índice normalizado é só ordenação.

**Passo 4 · Expor a tendência, separada do índice.** É o pedido explícito do
áudio, e é o que impede o índice de esconder o que ele ponderou:

```
T(t) = média de p nos últimos 5 anos − média de p nos 5 anteriores
```

Na tela, com os dois números visíveis: *"caía em 6% das questões até 2015 · cai
em 2% desde 2020 ▼"*. **O índice diz o quanto estudar; a tendência diz por quê.**

### 4.3 Recorte — e é onde se erra mais fácil

Importância é sempre **por (vestibular, matéria, fase)**. Misturar ITA F1 com
IME F2 produz um número que não descreve prova nenhuma. Como *todo* aluno é
avaliado contra ITA **e** IME (regra do projeto), a tela mostra **dois
índices**, lado a lado, nunca uma média dos dois.

### 4.4 Os quatro limites, para constarem na tela e não só aqui

| Limite | O que fazer |
|---|---|
| **Tópico com n pequeno** — 2 questões em 18 anos ranqueia por ruído | mostrar sempre o `n`; não entrar na lista "priorize isto" com n < 3, mas **nunca sumir** — "não caiu em oito anos" é informação de estudo (`estatisticas.py`) |
| **Questão mista soma nos dois tópicos** | já é a regra da `0028`; a soma das fatias passa de 100% e a tela precisa dizer isso |
| **Mudança de edital** | um tópico pode estar caindo porque *saiu do edital*. O índice não distingue isso de "a banca perdeu interesse". Precisa de nota humana em `topico_taxonomia` |
| **Cobertura desigual do acervo** | ITA tem 2008–2025; IME tem 1996–2019 + objetiva 2007–2016, com anos faltando. Anos ausentes não são anos com zero — o denominador tem que ser "anos que existem no acervo" |

### 4.5 O que isso destrava: prioridade pessoal

Com [§3](#3--a-ponte-que-falta-o-assunto) e [§4](#4--o-índice-de-importância-do-assunto) juntos:

```
prioridade(aluno, t) = I(t) × (1 − acerto(aluno, t))
```

Cai muito **e** eu erro muito. Com `acerto` puxado para a média da turma
quando o aluno tem menos de ~5 questões naquele tópico — senão um único erro
vira 0% de acerto e o tópico salta para o topo da lista.

**A leitura em duas dimensões é melhor que a lista.** Um gráfico de
importância × meu acerto, com quatro quadrantes, responde de relance:

```
        meu acerto alto │  ok, mantenha   │  ponto forte, e vale muito
                        ├─────────────────┼──────────────────────────
        meu acerto baixo│  deixa para depois │  ⚠ ESTUDE ISTO PRIMEIRO
                        └─────────────────┴──────────────────────────
                          importância baixa   importância alta
```

É o mesmo "gráfico em camadas" que a Sprint 5 · P5 já previa
([19 §3](19-roadmap.md)) — leigo lê o quadrante, o interessado lê os eixos, o
curioso lê os números.

---

## 5 · Tio Léo

O áudio 3 pede a renomeação do bot do aluno de "Mentor"/"Assistente" para
**Tio Léo**, com "linguagem amigável, motivadora", RAG sobre livros de método
de estudo, e acesso às métricas de importância de assunto.

### 5.1 A colisão de nome — precisa decidir antes

**"Tio Leo" já é o nome de uma das cinco réguas de corte** (`criterio_classificacao`,
migration `0023`), e aparece no seletor do Painel da coordenação ao lado de
"ITA" e "IME". Se o bot do aluno também se chamar Tio Léo, o mesmo nome passa
a significar duas coisas no mesmo produto.

✅ **Decidido em 29/08: assumir a colisão, de propósito.** O bot *é* a pedagogia
do Leo falando com o aluno, e a régua de corte é a mesma pessoa — o nome
repetido é coerência, não acidente. O aluno nunca vê o seletor de critério, e a
régua continua se chamando "Tio Leo" em `criterio_classificacao`: nada muda em
dado de produção.

⚠️ **O custo fica todo do lado de dentro, e é este:** daqui em diante "Tio Leo"
é ambíguo em conversa, em log e em busca de código. A convenção para desfazer:
**"a régua do Tio Leo"** para o critério (`criterio_classificacao`), **"o Tio
Léo"** para o bot (`perfil_aluno`). O acento não separa nada — a palavra antes
dele, sim.

### 5.2 O que muda de fato, além do rótulo

Renomear é uma linha em três arquivos (`App.tsx` `rotuloFab`/`tituloDrawer`,
`prompt_aluno.py`, `Conversa.tsx` placeholder). O pedido do áudio é maior:

**Tools novas** — hoje as 6 tools do aluno só sabem de nota. Faltam:

| Tool | Depende de |
|---|---|
| `importancia_dos_assuntos(vestibular, materia)` | §4 |
| `meus_assuntos_fracos()` — acerto por tópico | §3 |
| `meu_plano_de_revisao()` — o ranking de prioridade | §3 + §4 |
| `questoes_do_banco_sobre(topico)` — devolve questões reais para treinar | já existe no `/banco`, falta a tool |
| `minha_zona_e_distancia()` | §2, e depende da decisão sobre mostrar zona |

**RAG dos livros de método de estudo** — o pedido de "carregado com vários
livros de aprendizado". Isso é **um sprint inteiro por si só**: exige
armazenar os textos, decidir a legalidade de cada obra, escolher embeddings e
um índice vetorial que hoje **não existe no projeto** (o Postgres não tem
`pgvector`, e não há nada de RAG em `api/`). Recomendação: **não misturar com
o resto.** As tools acima entregam 80% do valor conversacional sem nenhuma
infra nova; o RAG entra depois, medido contra o que a resposta melhorou de
fato.

### 5.3 O tom, e por que ele não é só prompt

"Amigável e motivador" tem um limite documentado no próprio prompt de hoje:
*"encorajador e honesto — reconheça avanços, aponte riscos sem alarmismo, sem
falsa positividade"*. Vale manter escrito assim. Um bot que só elogia um aluno
que está caindo é pior que uma tabela.

---

## 6 · Gamificação — o que vale e o que faz mal

O áudio 2 pede gamificação. O projeto já tem streak e badges. Três regras
antes de acrescentar:

1. **Premiar processo, não posição.** Badge de "top 15%" premia estar acima de
   colegas; badge de "revisou os 5 assuntos que mais errou" premia o que o
   aluno controla. Com [§3](#3--a-ponte-que-falta-o-assunto) o segundo tipo
   passa a ser possível pela primeira vez.
2. **Consertar o streak** ([§1.1](#11-os-três-buracos-que-o-inventário-revela)).
   Streak deve medir a evolução do aluno contra ele mesmo — "N ciclos seguidos
   sem cair" ou "N ciclos subindo" — não contra a média da turma.
3. **Nada que rankeie aluno com nome na frente de outro aluno.** É a regra que
   o chat já obedece (*"comparações só com agregados"*), e vale para toda a
   tela. Também é a resposta padrão para a foto de perfil de colega.

---

## 7 · Design — a direção decidida em 29/08

Do áudio 2: *"evitar esse esquema de planilhas"*. Do lado do aluno é consenso —
**a área do aluno não deve ter tabela nenhuma** que não seja a lista de
simulados.

A direção saiu de uma rodada de exploração com quatro linguagens e quatro
paletas renderizadas. Prompts e histórico em
[prompts-design-aluno.md](prompts-design-aluno.md).

### 7.1 O que ficou decidido

**Sub-marca própria do aluno**, não o casco institucional da coordenação — um
aluno de 17 anos não volta todo dia a um sistema do colégio.

**Jogo de verdade, não dashboard.** A referência de mecânica é o Duolingo, e o
que faz ele parecer jogo cabe em seis regras, todas aplicáveis aqui:

1. **A tecla com 4px de borda inferior sólida** que comprime ao apertar. É a
   regra que sozinha faz mais diferença que o resto. **Só botão e bloco
   tocável** ganham isso; todo o resto é chapado.
2. **Cor é papel, nunca decoração** — ver a tabela em [§7.2](#72-o-sistema-em-dois-temas).
3. **A chama acelera quando a sequência está em risco.** Parada gira ±2° a cada
   2s; à noite sem estudo, 0,8s e ±3°. Quinze linhas de CSS, e é a mecânica de
   retenção mais forte que existe.
4. **A barra de progresso anda um pouco mesmo no erro** — mata a sensação de
   travado, que é fatal para quem acerta 41% de um assunto.
5. **Celebração em duas escalas**: 300ms para recompensa pequena e repetida,
   tela cheia só para marco (3 · 7 · 30 · 100 dias, cruzar o corte). Usar a
   grande em tudo mata as duas.
6. **Silenciar o que não é o jogo.** Texto secundário deliberadamente apagado
   para a cor do jogo dominar.

**O herói é a missão do dia, não a nota.** A Casa deixou de ser boletim: a nota
desceu para uma tira compacta no rodapé, e o topo virou o que fazer hoje.

**A barra inferior vira `Hoje · Plano · Liga · Jornada`.** O Banco deixa de ser
aba e vira o **motor** de "Hoje" e "Plano".

### 7.2 O sistema em dois temas

Não são duas paletas: é **um sistema, seis papéis, dois temas**. O mesmo
componente serve os dois; o tema troca valores, nunca papéis.

| Papel | Onde aparece | Dia | Noite |
|---|---|---|---|
| **Ação** | o que se aperta | navy `#1B3F8B`, base `#12275A` | ouro `#FFCE3A`, base `#C79A16` |
| **Valor** | XP, conquista, linha de corte | ouro `#F2C94C`; `#B07D12` como texto | ouro `#FFCE3A` |
| **Dado** | barras, progresso, nav ativa | azul `#2E6BE6` | azul elétrico `#2F6BFF` |
| **Sequência** | chama e corrente de dias | coral `#FF6B4A` | coral `#FF6B4A` |
| **Alerta** | só a etiqueta de distância | `#E0452F` | `#FF6B4A` |
| **Magnitude** | numeral grande | `#0F1B33` | `#FFFFFF` |
| Fundo · superfície · borda | | `#FFFFFF` · `#F4F7FC` · `#DCE6F7` | `#050A18` · `#0C1530` · `#1B2B57` |
| Texto secundário | | `#5C6883` | `#6E85B8` |

**Duas trocas entre os temas são intencionais**, e a regra que as explica é uma
só: *a ação é sempre a cor de maior contraste com o fundo*. Ouro sobre branco
não dá botão; navy sobre quase-preto some. A magnitude acompanha. Todo o resto é
constante — e as inconsistências que apareceram nas primeiras gerações
(sequência, barra de meta, barra abaixo do corte) foram unificadas.

⚠️ **O par ouro-traço / ouro-texto não é firula.** É o mesmo padrão que
`--color-amber` e `--color-amber-text` já resolvem em
[web/styles/tokens.css](../web/styles/tokens.css): ouro puro reprova em
contraste como texto sobre fundo claro.

**A barra abaixo do corte é vazada nos dois temas** — no escuro lê como segmento
queimado, no claro como não-preenchido. Mesma ideia, mesmo componente. É o que
mata o semáforo verde-e-vermelho, que era o que mais puxava a idade da tela para
baixo.

⚠️ **Custo honesto:** o projeto **não tem modo escuro em lugar nenhum** hoje
([06 §6](06-open-questions.md) adiou para v2). Fazer os dois temas é barato
**agora**, porque tudo nasce como token; é caro depois, como retrofit. Este é o
momento mais barato que vai existir.

### 7.3 As mecânicas: o que existe, o que precisa de migration, o que é invenção

Levantado contra o schema em 29/08. **Duas das oito coisas da tela existem.**

| Na tela | Existe? | O que fazer |
|---|---|---|
| **Onde você está** — 5 barras vs. corte | ✅ no ar | só muda o desenho |
| **−0,8 até o corte** | ✅ | decidido em 29/08 ([§2](#2--o-que-jornada-quer-dizer-em-termos-do-que-o-sas-já-sabe)) |
| **Avatar** | ✅ | Sprint Foto |
| **Missão de hoje** | ⏳ **depende do Sprint 6** | é `importância × (1 − meu acerto)`. Sem classificar as 1.031, a missão não tem como escolher assunto — é o primeiro produto visível do Sprint 6 |
| **Sequência** | ❌ | ~~dias~~ → **simulados consecutivos sem faltar**, por `nota.presente`. Decidido em 29/08 pela diretriz do verificável — ver [26](26-mecanicas-do-jogo.md) |
| **XP** | ❌ | ~~por questão do banco~~ → **por simulado**: presença, matérias acima do corte, régua completa, progresso contra si mesmo e faixa de ranking. É a régua de corte existente, pontuada — ver [26 §3](26-mecanicas-do-jogo.md) |
| **Meta do ciclo** | ❌ | ~~semanal~~ — o XP só se move quando sai nota. Quem define o alvo segue aberto em [§9.1](#91-ainda-abertas) |
| **Liga** | ❌ | depende de XP existir primeiro |

**Nomes.** "Ofensiva" é a tradução brasileira do Duolingo — virou **"Sequência"**.
**XP fica XP**: é a única palavra que todo mundo de 17 anos já sabe, e renomear
cobra pedágio de aprendizado sem devolver nada.

> ⚠️ **Esta seção foi reescrita em 29/08.** A diretriz *"só se premia o que se
> verifica"* derrubou a sequência de dias, o XP por questão do banco e a meta
> semanal — nada disso é verificável, porque `questao_estudo_aluno.resolvida` é
> autodeclarado. **A especificação que vale é [26-mecanicas-do-jogo.md](26-mecanicas-do-jogo.md).**
>
> A consequência de produto: não existe atividade diária verificável no SAS
> (`aluno_modulo_progresso` está no schema desde a `0010` e nunca foi
> sincronizada), então o app é **hábito de ciclo, não hábito diário** — treino
> livre sem pontuar, e a prova é a corrida que vale.

### 7.4 Régua de execução

A skill `frontend-design` para a direção visual e a `web-design-guidelines` para
a revisão (toque, safe-area, foco) — ambas versionadas em `.claude/skills/`. E a
regra 6 do `CLAUDE.md` continua valendo: **nenhum asset de terceiro**, o que
exclui qualquer biblioteca de gamificação com CDN — e também o mascote que
apareceu sozinho numa das gerações, se ele for adotado: teria de ser ilustração
própria, servida da nossa origem.

---

## 8 · Ordem proposta e dependências

Nada aqui é opinável: a ordem sai das dependências.

```
  ┌─ A · Classificar os simulados por tópico  ──────────┐   (§3)
  │     1.031 questões → 237.081 respostas com assunto  │
  └──────────────────┬──────────────────────────────────┘
                     │
  ┌─ B · Índice de importância ─────────┐                    (§4)
  │     incidência × recência + tendência│  (independente de A)
  └──────────────────┬───────────────────┘
                     ▼
  ┌─ C · Prioridade pessoal + quadrantes ───────────────┐     (§4.5)
  │     exige A e B                                     │
  └──────────────────┬──────────────────────────────────┘
                     ▼
  ┌─ D · Jornada: zona, meta, próximo passo, linha do tempo ┐ (§2)
  └──────────────────┬──────────────────────────────────────┘
                     ▼
  ┌─ E · Tio Léo: nome, tools novas ────────────────────┐     (§5)
  └─────────────────────────────────────────────────────┘
  ┌─ F · RAG dos livros ────── sprint próprio, depois ──┐     (§5.2)
  └─────────────────────────────────────────────────────┘
```

**B pode começar hoje** — só depende do que já está no Postgres. **A é o
caminho crítico** de todo o resto e é trabalho de lote, não de tela.

---

## 9 · Decisões em aberto

### 9.1 Ainda abertas

| # | Decisão | Trava | Quem decide |
|---|---|---|---|
| 1 | **O aluno escolhe a meta do ciclo, ou o sistema propõe?** | §2.1, item 2 | Coordenação |
| 2 | **Gamificação pode ser competitiva?** Ranking com nome de colega está proibido hoje pela regra do chat — vale manter na tela? | §6, regra 3 | Coordenação |
| 3 | **RAG de livros: quais obras, e com que direito de uso?** | §5.2 — e o sprint só existe depois disso | Yan + jurídico |
| 4 | **Taxonomia de Inglês, num sprint futuro?** Fechada por ora ("só as três"), mas é o próximo candidato — e é o único eliminatório | — | Coordenação |
| 5 | **A área do aluno tem mascote?** Um avião de papel apareceu sozinho numa geração e não foi pedido. Se entrar, é ilustração própria, nos dois temas, e vira decisão de marca | §7.4 | Yan |

### 9.2 Fechadas em 29/08

| Decisão | Resposta | Onde |
|---|---|---|
| O aluno vê a própria zona? | **Sim, e com a distância até a próxima** | [§2](#2--o-que-jornada-quer-dizer-em-termos-do-que-o-sas-já-sabe) |
| "Tio Léo" com a régua já se chamando "Tio Leo"? | **Assumir a colisão** — é a mesma pessoa; a convenção interna separa os dois | [§5.1](#51-a-colisão-de-nome--precisa-decidir-antes) |
| Meia-vida do índice de importância? | **5 anos, fixa para todos** | [§4.2](#42-o-desenho-proposto--quatro-passos) |
| O que entra primeiro? | **Sprint 6** — o assunto. O índice (P3) começa em paralelo, sem depender da classificação | [§8](#8--ordem-proposta-e-dependências) |
| Direção visual da área do aluno | **Um sistema, dois temas** — dia claro azul-e-branco, noite neon azul-ouro-branco, mesmos seis papéis de cor | [§7.2](#72-o-sistema-em-dois-temas) |
| O que a gamificação pode premiar | **Só o verificável.** Sequência vira simulados sem faltar; XP sai do simulado, não do banco; e progresso contra si mesmo entra na tabela | [26](26-mecanicas-do-jogo.md) |
| Português, Inglês e Redação? | **Fora do Sprint 6** — cobre só Mat/Fís/Quím, e a tela diz quais matérias cobre | [§3.3](#33-o-buraco-de-cobertura-que-ninguém-mediu-ainda) |

---

## 10 · O que este documento não decide

- **Não escolhe sprint.** A ordem do [§8](#8--ordem-proposta-e-dependências) é
  técnica; a prioridade contra a Sprint 3 (cobrança de professor) é do Yan.
- **Não mexe em nada que já está no ar.** Toda proposta aqui é aditiva, exceto
  o conserto do streak ([§6](#6--gamificação--o-que-vale-e-o-que-faz-mal),
  regra 2), que muda um número que o aluno já vê.
