# Brief para o Claude Design — o Painel

> ⚠️ **Superado por [brief-claude-design-painel-e-cantina.md](brief-claude-design-painel-e-cantina.md)**,
> que traz este conteúdo inteiro com o terceiro card — a cantina — já
> especificado. Este arquivo ficou como registro da versão que saiu com o slot
> em branco.

Quarto ramo da coordenação, depois de
[provas](brief-claude-design-provas.md), [simulados](brief-claude-design-simulados.md)
e [alunos](brief-claude-design-alunos.md).

Cole o bloco abaixo **na mesma conversa** em que o brief de `/provas` já foi
colado — ele conta com o sistema de design daquele. Numa conversa nova não se
sustenta sozinho.

⚠️ **Um card está em aberto.** O terceiro card do Painel será a CANTINA, e ele
ainda não foi especificado — a discussão de produto está em andamento. O bloco
abaixo reserva o lugar dele de propósito. Quando fechar, o brief é atualizado
aqui e o slot é preenchido; a estrutura não muda.

---

```
# O QUE VOCÊ VAI FAZER AGORA

Uma tela só: o **PAINEL**, que é a home da coordenação. `/` cai nele, rota
desconhecida cai nele, e ele é a primeira coisa que dois ou três coordenadores
veem todo dia de manhã.

E o trabalho é quase todo SUBTRAÇÃO. O Painel de hoje empilha seis estratos:

    faixa de filtros (ano · vestibular · ciclo · sede · turma · busca)
    3 cartões de entrada
    título
    faixa de alertas
    4 KPIs em magnitude
    A TABELA — 900 alunos × até 14 colunas

Cinco dos seis saem. Fica a faixa de alertas, e entram três cards no lugar dos
cartões de entrada. É a maior remoção da história deste produto, e a tela que
sobra é a mais enxuta que a coordenação já teve.

# PRECEDÊNCIA — esta tela é a exceção do brief mestre

Se você tem o brief mestre da coordenação, ele vale inteiro **menos numa
frase**, e a frase é sobre esta tela exatamente:

    "Não transforme o Painel num hub de campos. No Painel um campo domina
     esmagadoramente: a varredura. Virar hub cobraria um clique a mais na
     tarefa mais frequente do dia, todo dia."

**Revertido em 05/09/2026 pelo dono do produto.** Não tente restaurar, e o
argumento importa para o seu desenho:

A tabela de varredura **sempre foi de um ciclo só** — 900 alunos × as matérias
de UM ciclo —, e a primeira coisa que o coordenador fazia ao chegar era escolher
o ciclo numa faixa de filtros. A tela pedia um contexto que a URL podia dar. A
tabela desceu para `/ciclos/:id`, onde perde três filtros de graça e herda a
régua de corte que já está lá.

O custo é real: **varrer passa a custar um clique a mais.** É o card do CICLO
que devolve esse clique, e é por isso que ele domina os outros dois.

# O QUE O PAINEL É, EM UMA FRASE

**Três portas e uma coisa que só ele faz.**

Os cards são ATALHOS para telas que existem em outros lugares da plataforma —
e é assim de propósito, por enquanto. A faixa de alertas é a única coisa da
tela que não existe em lugar nenhum além dali.

Essa assimetria é o desenho. Não tente equilibrá-la.

## A régua que justifica cada atalho — e que vale para os futuros

Um card vale o espaço se economiza cliques **que hoje custam decisão**:

    CICLO      sem ele: rail Provas → aba Ciclos → achar qual é o último → abrir
               com ele: 1 clique                                        −3

    SIMULADO   sem ele: rail Provas → aba Simulados → achar a última aplicada → abrir
               com ele: 1 clique                                        −3

    (um card de "Alunos" economizaria ZERO: a rail já leva lá em um clique.
     É por isso que ele não existe.)

O que o atalho poupa não é o caminho — é o **"achar qual"**. Guarde isso: é o
que separa este hub de um menu com números em cima.

# A TELA

    ┌────────────────────────────┐  ┌──────────────────┐
    │ CICLO                      │  │ SIMULADO         │
    │ Como está fechando?        │  │ A prova estava   │
    │                            │  │ boa?             │
    │      156                   │  │                  │
    │      cortados de 407       │  │ Física · P8      │
    │                            │  │ 14/08 · média 4,2│
    │ Ciclo 4 · ITA · 2026       │  └──────────────────┘
    │ 8 de 12 provas             │  ┌──────────────────┐
    └────────────────────────────┘  │ (terceiro card)  │
                                    │                  │
                                    └──────────────────┘

    O QUE MERECE ATENÇÃO
    [cartões de alerta, abertos, sem clique para aparecer]

Sem faixa de filtros. Sem fileira de KPIs. Sem tabela. Sem busca.

# O QUE SAIU, E POR QUÊ — não recoloque nada disto

**A tabela** → foi para `/ciclos/:id`. É a mudança inteira.

**A faixa de filtros (ano · vestibular · ciclo · sede · turma)** → o filtro de
ciclo existia para escolher o alvo da tabela. Sem tabela, ele não tem alvo: o
Painel é sempre o AGORA, e quem quer outro ciclo vai em Provas. Sede e turma
saíram junto — sem tabela e sem KPIs elas só recortariam os alertas, e uma home
com barra de filtro deixa de ser home e vira dashboard.

**Os 4 KPIs em magnitude** (alunos no ciclo · perto do corte · média geral ·
cortados) → todos os quatro são sobre o ciclo, e o card do ciclo já os carrega.
Uma fileira de quatro números repetindo o subtítulo do card ao lado é ruído com
peso 800. **O que sobrou deles é UMA magnitude, dentro do card do ciclo.**

**A busca** → sem tabela ela não peneira nada, e a topbar já busca aluno com o
atalho "/".

**O cartão "Quem mudou de zona?"** → apontava para `/painel#alertas`, que é a
própria tela. Era circular, e a faixa de alertas logo abaixo já responde: é o
alerta `ZONA_TRANSICAO`.

# OS CARDS

Anatomia do card de campo do sistema: olho em caixa alta, título grande (a
pergunta), subtítulo com dado vivo, SVG de traço fino à direita, borda sem
sombra, raio de 18px, afunda 2px ao ser pressionado.

Aplique C1 **na nomenclatura**: o OLHO carrega o objeto, o TÍTULO carrega a
pergunta, o SUBTÍTULO carrega o dado. "Último ciclo" como título seria corte
por recência, que a regra proíbe; como olho + subtítulo, está certo.

## Card 1 · CICLO — "Como está fechando?" → `/ciclos/:id`

**Este card domina os outros dois.** Ele é o destino da varredura, a tarefa de
todo dia, e é ele que devolve o clique que a reversão custou. Três cards de
peso igual seriam a reversão sem contrapartida.

Ele carrega **a única magnitude da tela inteira** — e ela não é um KPI. É o
número que decide **se vale a pena ir agora**: os cortados, ou o percentual
abaixo do corte. Um dashboard mostra o número porque o número é o produto; aqui
ele existe para responder "preciso abrir isto hoje?".

Subtítulo: `"Ciclo 4 · ITA · 2026 · 8 de 12 provas"`.

⚠️ **O card nomeia o vestibular, e isso não é decoração.** ITA e IME correm em
paralelo — existem "Ciclo 4 · ITA" e "Ciclo 4 · IME" ao mesmo tempo, e todo
aluno é avaliado contra os dois. O card mostra **um só**: aquele cuja prova mais
recente foi aplicada por último. Foi decisão do dono do produto, e o preço é que
o outro vestibular não aparece na home. Por isso o subtítulo é obrigado a dizer
qual metade do colégio está na tela.

## Card 2 · SIMULADO — "A prova estava boa?" → `/simulados/:id`

A **última prova aplicada** — por data de aplicação, não por nota lançada.

Subtítulo: `"Física · P8 · 14/08 · média 4,2 · 38% abaixo do corte"`.

⚠️ **Desenhe o estado em que a prova foi aplicada e as notas ainda não
chegaram.** Existe uma janela de dias entre aplicar e o Canvas trazer as notas,
e nela o card não tem média para mostrar. Ele **não** deve parecer quebrado: o
subtítulo passa a ser `"aplicada em 14/08 · notas ainda não lançadas"`, e aí o
card está avisando de uma pendência operacional — que é a informação mais útil
da tela naquela semana. Um estado sem dado que informa em vez de envergonhar.

## Card 3 · RESERVADO

O terceiro card será a CANTINA e ainda não foi especificado. Reserve o lugar e
desenhe o slot vazio como parte da composição — não desenhe conteúdo inventado
para ele, e não redistribua os outros dois para preencher o espaço.

# A FAIXA DE ALERTAS — a única coisa que só o Painel faz

    O QUE MERECE ATENÇÃO
    régua: Tio Leo

    ┌──────────────────────────────────────────────────────────┐
    │ QUEDA DE RENDIMENTO      há 2 dias                        │
    │ Turma 3B caiu 1,4 em Física                    ╱╲__       │
    │ 4 alunos saíram da zona top desde o Ciclo 3   ╱    ╲      │
    │                                     Ver detalhes →  Resolver│
    └──────────────────────────────────────────────────────────┘

Sete categorias, geradas por um motor de regras no servidor: queda de
rendimento · subida atípica · prova mal calibrada · matéria em risco ·
diferença entre sedes · panorama do ciclo · transição de zona.

Cada cartão tem: etiqueta da categoria · tempo relativo · título · subtítulo ·
sparkline de 6 a 10 pontos · "Ver detalhes →" (navega para o aluno, o simulado
ou a turma) · "Resolver".

Mostra três por padrão, com "Ver os outros N".

## O que muda nela, e o que você precisa resolver

**1 · Ela simplifica.** Hoje a faixa respeita o recorte da tela e precisa
avisar `"+3 fora do recorte atual"` — nunca esconder em silêncio. Sem faixa de
filtros, **não há recorte**: a faixa mostra tudo, e essa linha de rodapé morre.

**2 · "Resolver" virou uma das duas ações da tela inteira.** Antes era um
botãozinho de texto no canto de um cartão, numa tela que tinha 900 linhas
editáveis. Agora o Painel tem exatamente duas coisas que se pode fazer: entrar
por uma porta, ou resolver um alerta. A ação merece o desenho que nunca teve.

E ela é destrutiva de um jeito silencioso: resolver faz o alerta **sumir**, sem
motivo, sem desfazer, sem registro visível na tela. Se você propuser algo — um
desfazer curto, um motivo em uma linha —, diga o que ganha.

**3 · A sparkline do cartão não tem régua.** R2 diz que nunca se lê uma nota sem
a régua ao lado, e esses 6 a 10 pontos são notas. Como aqui é uma sparkline por
vez, e não 900 lado a lado, o problema é menor que na lista de alunos — mas a
linha de corte cabe, e sem ela "caiu" e "caiu para baixo do corte" são a mesma
curva.

**4 · O sino da topbar aponta para a âncora `#alertas`.** Com a tela reduzida, a
âncora é praticamente a tela inteira. Decida o que o sino faz agora — e se ele
ainda faz sentido.

# O PROBLEMA CENTRAL DESTA TELA

**Três cards e uma faixa episódica precisam sustentar uma tela de 1440×900 que
é a primeira coisa que alguém vê todo dia.**

O hub de Administração tem cinco cards e enche a tela. Aqui são três — um
grande e dois pequenos — mais uma faixa que pode estar vazia. Os dois modos de
errar são simétricos e igualmente ruins:

- **Esticar** os três cards para preencher a largura: vira um menu de
  instalador, e a hierarquia entre o card do ciclo e os outros some.
- **Deixar sobrar**: a home mais importante do produto com meia tela de fundo
  vazio, todo dia de manhã.

E some a isto a restrição do "por enquanto": **o Painel vai crescer.** A grade
tem que aceitar um quarto e um quinto card sem virar outra tela, e a faixa de
alertas é onde conteúdo analítico vai aparecer quando aparecer. Desenhe uma
estrutura que aguenta, não uma composição que só fecha com exatamente três.

Mostre a grade com três cards e com cinco, para provar que aguenta.

# ESTADOS A DESENHAR — o vazio aqui é frequente, não excepcional

    normal            ciclo em andamento, prova recente, alertas abertos

    SEM ALERTAS       acontece de verdade: houve um dia com 156 cortados e
                      ZERO alertas. Hoje a faixa mostra uma frase e, sem a
                      tabela embaixo, essa frase passa a ser o rodapé da tela.
                      Não pode virar uma caixa pálida vazia — caixa vazia diz
                      "aqui deveria ter algo" e quebra a leitura da tela toda.

    NADA RECENTE      janeiro, ou a semana depois de um ciclo fechar: o último
                      ciclo terminou, a última prova é de três semanas atrás.
                      Os atalhos apontam para coisa velha e viram peso morto.
                      É o estado que o enquadramento de "atalho" torna
                      obrigatório resolver: um atalho que envelheceu tem que
                      dizer que envelheceu.

    PRIMEIRO DIA      colégio sem nenhum ciclo e sem nenhuma prova. É a home no
                      começo do ano letivo.

    carregando        os três cards em esqueleto — nunca número inventado,
                      nunca "0" no lugar de "não sei"

    notas não         o card do simulado sem média (ver Card 2)
    lançadas

# DUAS NOTAS DE ENCANAMENTO

**O "voltar" do ciclo não sabe que existe Painel.** Quem entra em `/ciclos/:id`
pelo card cai numa tela cujo chevron de volta aponta para a lista de ciclos —
um lugar onde essa pessoa nunca esteve. A migalha dirá "Provas › Ciclos › Ciclo
4", o que é verdade sobre onde ela ESTÁ e mentira sobre de onde ela VEIO.
Proponha como a volta reconhece a origem.

**O Painel é o fallback de rota desconhecida.** Um link velho, um e-mail antigo
ou um typo caem aqui. Vale considerar se a tela diz alguma coisa nesse caso ou
se aparece como se nada tivesse acontecido.

# RESTRIÇÕES — as mesmas de sempre

Nenhum asset de terceiro (LGPD: são dados de menores). Nenhum gráfico com
biblioteca — SVG à mão. Nomes brasileiros inventados, avatar como círculo com
duas letras. Contraste AA nos dois temas. Foco de teclado visível. Nada de
pizza, donut, 3D, gradiente colorido ou visual de BI genérico.

# O QUE ENTREGAR

1. **O Painel nos dois temas, em 1440×900**, no estado normal.
2. **Os estados**: sem alertas · nada recente · primeiro dia · carregando.
3. **A grade com cinco cards**, para provar que a estrutura aguarda o
   crescimento sem virar outra tela.
4. **O cartão de alerta redesenhado**, com a sparkline ganhando régua e com a
   ação "Resolver" tratada como a ação que ela virou.
5. **Duas ou três linhas** dizendo como você fez o card do ciclo dominar os
   outros dois sem que eles pareçam um erro de alinhamento — e o que acontece
   com essa hierarquia quando entram o quarto e o quinto card.
```
