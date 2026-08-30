# 26 — As mecânicas do jogo · só se premia o que se verifica

> Decidido em **29/08/2026**, e é a diretriz que reescreveu a camada de
> gamificação inteira: **o SAS só pontua aquilo que consegue verificar que o
> aluno fez.** A direção visual está em
> [24-jornada-do-aluno.md §7](24-jornada-do-aluno.md); aqui está a regra de cada
> mecânica.

---

## 1 · O que o SAS verifica, e o que não

Levantado contra o schema em 29/08.

### Verificado — pode pagar

| Dado | Onde | Desde |
|---|---|---|
| **Presença** no simulado | `nota.presente` | migration `0001` |
| **Nota** | `nota.pontuacao` | `0001` |
| **Resposta por questão** | `questao_resposta_aluno` — 237.081 linhas | `0010` |
| **Posição e percentil** | derivado das notas do simulado | — |
| **Zona e corte** | avaliador de critérios, `criterio_classificacao` | `0023` |
| **Melhora contra si mesmo** | `deltaSelf`, já exposto em `/me/simulados` | — |

O comentário da coluna `nota.presente` diz a regra que torna isso confiável:
*"false quando a célula da planilha veio vazia. **Falta ≠ zero.**"*

### Não verificado — não pode pagar

| Dado | Por quê |
|---|---|
| `questao_estudo_aluno.resolvida` | **autodeclarado.** Nada impede marcar 50 questões sem abrir nenhuma |
| `questao_estudo_aluno.anotacao` | idem |
| Tempo de estudo | não existe |
| Aula assistida | `aluno_modulo_progresso` existe no schema desde a `0010` — *"estudou Combinatória antes da prova?"* — mas **nenhuma linha em `api/app/` a referencia.** Nunca foi sincronizada do Canvas |

⚠️ **Este é o achado que fecha a questão:** não existe nenhuma atividade
**diária** verificável no SAS. O único evento verificado é o simulado, a cada
~3 semanas.

---

## 2 · A consequência: hábito de ciclo, não hábito diário

O app deixa de ser Duolingo e passa a ser **treino e prova**: o aluno treina
livre, sem pontuar, e pontua no dia da corrida. Para preparação de vestibular
isso é mais honesto do que fingir um loop diário que o dado não sustenta.

**O que sobrevive sem pontuar:** a missão de treino continua existindo e
continua sendo escolhida pelo `importância × (1 − meu acerto)`. Ela diz *o que*
treinar. Só não paga — porque não dá para verificar que foi feita.

**O gancho diário passa a ser a contagem regressiva**, não a corrente: *"faltam
12 dias para o P5"*. É verdade, é verificável, e cria urgência sem inventar
moeda.

---

## 3 · XP

**XP não é métrica nova — é a régua de corte existente, pontuada.** O mesmo
avaliador que classifica o aluno para o coordenador é o que paga o aluno. Fonte
da verdade única: é impossível o aluno ver um veredito e o coordenador outro.

### A tabela

| Evento | XP | Verificado por |
|---|---|---|
| **Fez o simulado** | 100 | `nota.presente` |
| **Cada matéria acima do corte** | 40 | avaliador de critérios (`0023`) |
| **Passou na régua completa** | 200 | `criterio_classificacao` |
| **Superou o próprio padrão** | 80 + 40 × delta | `deltaSelf` |
| **Sua melhor nota do ano na matéria** | 150 | histórico de `nota` |
| **Top 50 da escola** | 150 | ranking do simulado |
| **Top 10** | 400 | " |
| **Top 3** | 700 | " |
| **Top 1** | 1.200 | " |

### ⚠️ XP é derivado, nunca gravado como saldo

Nota é corrigida e simulado é anulado — a Sprint 2 inteira tratou disso. Se o XP
for sempre **recalculado a partir de `nota`**, uma correção se propaga sozinha e
o problema não existe. Se for saldo acumulado, cada correção vira um estorno
manual.

A única exceção: **o extrato de uma liga já encerrada é congelado.** Senão o
pódio muda depois de anunciado. Ver [29 §B.1](29-area-do-aluno-o-que-falta.md).

### As duas regras de composição

1. **O ranking paga só o nível mais alto.** As faixas são aninhadas; somar top
   50 + top 10 + top 3 + top 1 infla o topo em quatro vezes.
2. **As categorias somam entre si.** Presença, matérias, régua, progresso e
   ranking são eixos diferentes.

### Por que as linhas de progresso pessoal existem

⚠️ **Sem elas, a liga é o ranking de nota com outro nome.** Os mesmos 20 alunos
ganham todo ciclo e o jogo morre para os outros 880 — exatamente quem mais
precisa dele. É o mesmo defeito do streak antigo, que media posição em vez de
progresso ([24 §1.1](24-jornada-do-aluno.md)).

`deltaSelf` é o equalizador, e é verificado: um aluno indo de 3,0 para 4,0
melhorou tanto quanto um de 8,0 para 9,0, e só um dos dois chega perto do top 50.

### Como fica na prática

| Aluno | Conta | XP |
|---|---|---|
| Em risco, só apareceu | 100 | **100** |
| Em risco, apareceu e melhorou 0,5 | 100 + 80 + 20 | **200** |
| Mediano: 4 de 6 matérias, passou na régua, top 50 | 100 + 160 + 200 + 150 | **610** |
| Top 1 do ciclo | 100 + 240 + 200 + 1.200 | **1.740** |

Os números são **primeira calibração**. Ver [§7](#7--o-presente-que-a-diretriz-trouxe).

---

## 4 · Sequência

**Simulados consecutivos sem faltar.** Decidido em 29/08.

Foi escolhida entre três candidatas porque é a única que **não morre justamente
para quem mais precisa dela**: presença é alcançável por todo aluno, inclusive o
que está em zona de risco. Sequência de "sem ser cortado" deixaria metade da
escola em zero para sempre.

- Verificada por `nota.presente`.
- Guarda a atual e o recorde, separados.
- Quebra na falta. **Sem folga**: um simulado a cada três semanas não comporta
  a mesma misericórdia que um app diário — perdoar falta em prova é dizer que
  faltar tudo bem, e é o oposto do que a coordenação precisa.

⚠️ **Depende de uma decisão ainda aberta.** Enquanto "zero = provável ausência"
não tiver limiar ([19 §4](19-roadmap.md), trava Sprint 3 · P3), um aluno que
entregou a prova em branco conta como presente e mantém a sequência. O erro é
pequeno, mas está lá.

---

## 5 · Liga e Esquadrilha — duas coisas, e as duas coexistem

Decidido em 29/08. São mecânicas diferentes com riscos opostos, e uma cobre o
buraco da outra.

### 5.1 A Liga — o chão, e todo mundo está nela

**Liga do ciclo**, não da semana: o XP só se move quando sai nota.

- Grupos de ~30, formados pelo XP do ciclo anterior.
- Sobe o top 5, desce o bottom 5. Zera quando o ciclo fecha.
- **Anônima**: cada participante é um glifo geométrico estável no ciclo. Sem
  nome, sem apelido, sem inicial.

⚠️ **Os grupos têm de cruzar turma e sede.** Com ~900 alunos são 30 grupos; se
um grupo coincidir com uma turma, o anonimato cai por dedução.

### 5.2 A Esquadrilha — opcional, de amigos, e ela SOMA

O aluno monta um time com quem ele quiser. O nome vem do mundo deles: uma
esquadrilha é uma formação pequena voando junta.

| | |
|---|---|
| **Tamanho** | 3 a 6. Pequeno o bastante para ser amizade real |
| **O que compara** | o **XP somado da esquadrilha** contra outras esquadrilhas |
| **Por dentro** | **ninguém é ranqueado.** É a diferença entre um time e um placar |
| **Entrada** | por código de convite. **Nunca por busca de aluno** — buscar colega abre outra caixa inteira |
| **Saída** | a qualquer momento, sem avisar ninguém |

### 5.3 Por que as duas, e não só uma

**A esquadrilha melhora o consentimento e piora a exposição.** Numa liga anônima
o produto protege por design; numa esquadrilha o aluno **escolhe** com quem
compara — o que é consentimento de verdade, e é a razão de ela existir.

Mas ela cria dois riscos concretos numa escola: **quem não é convidado para
nenhuma**, e **o aluno mais fraco virando "o peso do time"**.

Os dois se resolvem com duas regras:

1. **A esquadrilha soma, não rankeia por dentro.** Sem último lugar, não há peso
   morto.
2. **A liga anônima é o chão e é automática.** Quem não tem esquadrilha não
   perde nada — continua na liga como todo mundo. A esquadrilha é aditiva, nunca
   a única forma de jogar.

⚠️ **Ainda é dado de desempenho de um menor sendo compartilhado com outro
menor**, por escolha do titular. Precisa passar por quem responde por LGPD antes
de subir — e continua dependendo da decisão de coordenação "gamificação pode ser
competitiva?" ([24 §9.1](24-jornada-do-aluno.md)).

---

## 6 · Conquistas e celebração

**Conquistas** existem hoje como quatro medalhas calculadas no front
(`PainelAluno.tsx`). Sob a diretriz, todas as regras passam a sair de dado
verificado: "cruzou o corte", "N simulados sem faltar", "sua melhor nota do
ano", "passou na régua completa pela primeira vez". Sai "Top 15%", que premia
posição.

**Celebração** precisa de `conquista_aluno(aluno_id, chave, em)` — sem registro
do que já foi celebrado, a tela cheia repete a cada abertura.

---

## 7 · O presente que a diretriz trouxe

**O XP é calculável para trás.** Como sai de notas que já estão no banco, o
aluno entra no primeiro dia e já tem XP, sequência e histórico de liga do ano
inteiro. Gamificação normalmente nasce zerada e leva meses para ter graça; esta
nasce cheia.

**E dá para aferir a tabela antes de subir.** Rodar os 5 ciclos de 2026 e ver
quem ganharia o quê, quantos alunos ficariam abaixo de 200 XP, se o top se
descola demais. Quase nenhum jogo consegue testar o próprio balanceamento contra
dado real antes do primeiro jogador entrar. **Fazer esse backtest é obrigatório
antes de fixar os números.**

---

## 8 · O que a diretriz matou

| Ideia anterior | Por quê |
|---|---|
| XP por questão do banco | autodeclarado |
| Sequência de **dias** | não há dia verificável |
| A chama que acelera à noite | não há o que estar em risco hoje |
| Meta da **semana** | vira meta do ciclo |
| Liga **semanal** | vira liga do ciclo |
| Teto diário de XP | sem sentido — o XP chega em blocos, não em fluxo |
| O log `evento_estudo` | **sai do caminho crítico.** Ainda serve para "o que já resolvi", mas o XP não depende dele: **uma migration a menos** |

---

## 9 · O que criar

| O quê | Depende de | Tamanho |
|---|---|---|
| Cálculo de XP por simulado, reusando o avaliador de critérios | — | **M** |
| `xp_aluno_simulado` materializado (para ranking e liga) | o cálculo | **P** |
| Sequência de presença | `nota.presente` | **P** |
| Endpoint `/me/jogo` — XP total, sequência, posição na liga | os dois acima | **P** |
| `conquista_aluno` + as regras novas | XP | **P** |
| Meta do ciclo | — | **P** |
| `liga_grupo` + `liga_participacao` | XP + decisão da coordenação | **G** |
| `esquadrilha` + `esquadrilha_membro` + convite por código | XP + parecer de LGPD | **G** |
| Backtest contra os 5 ciclos de 2026 | o cálculo | **P**, e é portão |

**Nada disso depende do Sprint 6.** O XP sai de nota, e nota já está no ar.
O Sprint 6 continua sendo o que personaliza o *treino* — não o que paga.

---

## 10 · O que muda nas telas já desenhadas

Os mockups aprovados em 29/08 foram desenhados sobre o modelo diário. O que
precisa ser refeito:

| Na tela | Vira |
|---|---|
| Corrente de 7 dias (S T Q Q S S D) | corrente de **simulados do ciclo** — um quadrado por prova |
| "SEQUÊNCIA 12" com chama | "12 SIMULADOS SEM FALTAR" |
| "META DA SEMANA 34/50" | **contagem regressiva** para o próximo simulado |
| "MISSÃO DE HOJE" | segue existindo, sem XP — é sugestão de treino |
| XP em fluxo contínuo | XP em blocos, com o extrato do último simulado |

---

## 11 · Decisões em aberto

| Decisão | Trava |
|---|---|
| Os números da tabela de XP, depois do backtest | fixar a tabela |
| "Gamificação pode ser competitiva?" — a liga | a Liga inteira |
| "Zero = provável ausência" (limiar) | a exatidão da sequência de presença |
| Quem define a meta do ciclo — aluno ou sistema | a meta |
| Temporada: o que zera na virada do ano letivo | XP, liga e esquadrilha em janeiro |
| Parecer de LGPD sobre a esquadrilha | a Esquadrilha inteira |
