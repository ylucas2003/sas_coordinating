# Brief para o Claude Design — o Painel e a cantina

Complementar de [provas](brief-claude-design-provas.md),
[simulados](brief-claude-design-simulados.md) e [alunos](brief-claude-design-alunos.md).

**Substitui e absorve** [brief-claude-design-painel.md](brief-claude-design-painel.md),
que saiu antes de a cantina estar decidida e por isso deixava um card em
branco. Este traz o Painel inteiro, com o card fechado, mais as quatro telas da
cantina.

Cole o bloco abaixo **na mesma conversa** em que os briefs de provas, simulados
e alunos já foram colados — ele conta com o sistema de design daqueles (as sete
regras do fim do semáforo, os seis papéis de cor, os dois temas, o padrão de
campo). Numa conversa nova não se sustenta sozinho.

⚠️ **LGPD, e aqui em grau diferente.** A cantina é a única parte do produto com
**dado de saúde** de menor de idade — restrição alimentar. Trate a seção sobre
ela como restrição de desenho, não como sugestão.

---

```
# O QUE VOCÊ VAI FAZER AGORA

Duas frentes, e um card costura as duas:

    PARTE 1 · O PAINEL      a home da coordenação. Uma tela, e o trabalho
                            é quase todo SUBTRAÇÃO.

    PARTE 2 · A CANTINA     quatro telas de um domínio que você ainda não viu.

O terceiro card do Painel é a cantina. Ele é a junção, e está especificado nas
duas partes.

════════════════════════════════════════════════════════════════════════════
PARTE 1 · O PAINEL
════════════════════════════════════════════════════════════════════════════

O Painel é a home da coordenação. `/` cai nele, rota desconhecida cai nele, e
ele é a primeira coisa que dois ou três coordenadores veem todo dia de manhã.

Hoje ele empilha seis estratos:

    faixa de filtros (ano · vestibular · ciclo · sede · turma · busca)
    3 cartões de entrada
    título
    faixa de alertas
    4 KPIs em magnitude
    A TABELA — 900 alunos × até 14 colunas

**Cinco dos seis saem.** Fica a faixa de alertas, e entram três cards. É a
maior remoção da história deste produto.

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

Os cards são ATALHOS para telas que existem em outros lugares da plataforma — e
é assim de propósito, por enquanto. A faixa de alertas é a única coisa da tela
que não existe em lugar nenhum além dali.

Essa assimetria é o desenho. Não tente equilibrá-la.

## A régua que justifica cada atalho — e que vale para os futuros

Um card vale o espaço se economiza cliques **que hoje custam decisão**:

    CICLO      sem ele: rail Provas → aba Ciclos → achar qual é o último → abrir
    SIMULADO   sem ele: rail Provas → aba Simulados → achar a última aplicada → abrir
    CANTINA    sem ele: rail Administração → card Cantina → grade do mês →
                        achar hoje → abrir a refeição
               com cada um: 1 clique                              −3, −3, −4

    (um card de "Alunos" economizaria ZERO: a rail já leva lá em um clique.
     É por isso que ele não existe.)

O que o atalho poupa não é o caminho — é o **"achar qual"**. Guarde isso: é o
que separa este hub de um menu com números em cima.

# A TELA

    ┌────────────────────────────┐  ┌──────────────────┐
    │ CICLO                      │  │ SIMULADO         │
    │ Como está fechando?        │  │ A prova estava   │
    │                            │  │ boa?             │
    │      156                   │  │ Física · P8      │
    │      cortados de 407       │  │ 14/08 · média 4,2│
    │ Ciclo 4 · ITA · 2026       │  └──────────────────┘
    │ 8 de 12 provas             │  ┌──────────────────┐
    └────────────────────────────┘  │ CANTINA          │
                                    │ O que é hoje?    │
                                    │ almoço 62 ·      │
                                    │ janta 41 pedidos │
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

# OS TRÊS CARDS

Anatomia do card de campo do sistema: olho em caixa alta, título grande (a
pergunta), subtítulo com dado vivo, SVG de traço fino à direita, borda sem
sombra, raio de 18px, afunda 2px ao ser pressionado.

Aplique C1 **na nomenclatura**: o OLHO carrega o objeto, o TÍTULO carrega a
pergunta, o SUBTÍTULO carrega o dado. "Último ciclo" como título seria corte por
recência, que a regra proíbe; como olho + subtítulo, está certo.

## Card 1 · CICLO — "Como está fechando?" → `/ciclos/:id`

**Este card domina os outros dois.** Ele é o destino da varredura, a tarefa de
todo dia, e é ele que devolve o clique que a reversão custou. Três cards de peso
igual seriam a reversão sem contrapartida.

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

## Card 3 · CANTINA — "O que é hoje?" → `/cantina/:hoje`

**Ele mostra as DUAS refeições**, e é decisão do dono do produto. Almoço e janta
convivem no mesmo card, com os pedidos de cada uma:
`"almoço 62 · janta 41 pedidos"`.

O destino é o **dia inteiro** — uma tela nova, `/cantina/:data`, com as duas
refeições. Não é a rota por refeição que já existe: um card com dois links
quebraria a anatomia do campo, que é uma superfície tocável com um destino.

**O que ele NÃO diz:** "cardápio de amanhã não lançado". Essa é a pergunta do
card da Administração, e os dois cards de cantina do produto só se justificam
enquanto os subtítulos disserem coisas diferentes. O do Painel é OPERAÇÃO — o
que se come hoje. O da Administração é SUPERVISÃO — o mês está lançado?

**Três estados deste card:**

    dia normal        "almoço 62 · janta 41 pedidos"
    só uma refeição   a que existe, e o card diz que a outra não é servida
    SEM REFEIÇÃO      sábado, feriado, recesso. O card diz "sem refeição hoje"
                      e fica INERTE — não leva a lugar nenhum. É o mesmo
                      tratamento que o calendário da cantina já dá ao dia sem
                      cardápio, e a razão é a mesma: a coordenação lê, não lança.

Um card inerte na home é incomum e precisa de desenho — ele não pode parecer
desabilitado por erro nem parecer clicável e não ser.

# A FAIXA DE ALERTAS — a única coisa que só o Painel faz

    O QUE MERECE ATENÇÃO
    régua: Tio Leo

    ┌──────────────────────────────────────────────────────────┐
    │ QUEDA DE RENDIMENTO      há 2 dias                        │
    │ Turma 3B caiu 1,4 em Física                    ╱╲__       │
    │ 4 alunos saíram da zona top desde o Ciclo 3   ╱    ╲      │
    │                                    Ver detalhes →  Resolver│
    └──────────────────────────────────────────────────────────┘

Sete categorias, geradas por um motor de regras no servidor: queda de
rendimento · subida atípica · prova mal calibrada · matéria em risco ·
diferença entre sedes · panorama do ciclo · transição de zona.

Cada cartão tem: etiqueta da categoria · tempo relativo · título · subtítulo ·
sparkline de 6 a 10 pontos · "Ver detalhes →" (navega para o aluno, o simulado
ou a turma) · "Resolver". Mostra três por padrão, com "Ver os outros N".

## O que muda nela, e o que você precisa resolver

**1 · Ela simplifica.** Hoje a faixa respeita o recorte da tela e precisa avisar
`"+3 fora do recorte atual"` — nunca esconder em silêncio. Sem faixa de filtros,
**não há recorte**: a faixa mostra tudo, e essa linha de rodapé morre.

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

# O PROBLEMA CENTRAL DO PAINEL

**Três cards e uma faixa episódica precisam sustentar uma tela de 1440×900 que é
a primeira coisa que alguém vê todo dia.**

O hub de Administração tem cinco cards e enche a tela. Aqui são três — um grande
e dois pequenos — mais uma faixa que pode estar vazia. Os dois modos de errar
são simétricos e igualmente ruins:

- **Esticar** os três cards para preencher a largura: vira um menu de
  instalador, e a hierarquia entre o card do ciclo e os outros some.
- **Deixar sobrar**: a home mais importante do produto com meia tela de fundo
  vazio, todo dia de manhã.

E some a isto a restrição do "por enquanto": **o Painel vai crescer.** A grade
tem que aceitar um quarto e um quinto card sem virar outra tela, e a faixa de
alertas é onde conteúdo analítico vai aparecer quando aparecer. Desenhe uma
estrutura que aguenta, não uma composição que só fecha com exatamente três.

Mostre a grade com três cards e com cinco, para provar que aguenta.

# ESTADOS DO PAINEL — o vazio aqui é frequente, não excepcional

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

# DUAS NOTAS DE ENCANAMENTO

**O "voltar" do ciclo não sabe que existe Painel.** Quem entra em `/ciclos/:id`
pelo card cai numa tela cujo chevron de volta aponta para a lista de ciclos — um
lugar onde essa pessoa nunca esteve. A migalha dirá "Provas › Ciclos › Ciclo 4",
o que é verdade sobre onde ela ESTÁ e mentira sobre de onde ela VEIO. Proponha
como a volta reconhece a origem.

**O Painel é o fallback de rota desconhecida.** Um link velho, um e-mail antigo
ou um typo caem aqui. Vale considerar se a tela diz alguma coisa nesse caso.

════════════════════════════════════════════════════════════════════════════
PARTE 2 · A CANTINA
════════════════════════════════════════════════════════════════════════════

# CONTEXTO — um domínio que você ainda não viu

A cantina serve refeição aos alunos do colégio. Ela entrou no produto em
setembro de 2026 e trouxe um **terceiro tipo de sessão**: além do aluno e da
coordenação, existe agora um login de cantina, com casco próprio.

O ciclo é este:

    a CANTINA         lança o cardápio de um dia, com prazo para pedir
    o ALUNO           vê o cardápio e faz o pedido, enquanto o prazo está aberto
    a COORDENAÇÃO     LÊ tudo isso, e concede o direito de comer

## ⚠️ A coordenação não publica nada

Nenhum botão de publicar, criar ou editar cardápio nas telas que você vai
desenhar. **Publicar é da cantina.** Um coordenador publicando em nome dela
apagaria a autoria do cardápio, que fica registrada. O servidor recusa de
qualquer jeito — a tela não oferecer é a metade que evita a pessoa descobrir o
limite levando um erro na cara.

O que a coordenação escreve é outra coisa: **quem tem direito** a comer, e
**quem lança** (as contas da cantina). Cardápio, nunca.

## Vocabulário

- **REFEIÇÃO**: são duas, `almoço` e `janta`. Um dia pode ter uma, as duas ou
  nenhuma.
- **CARDÁPIO**: o que se serve numa refeição de um dia. Tem itens.
- **PRAZO**: até quando o aluno pode pedir. A cantina tem um *prazo padrão* —
  "1 dia antes, às 10h" — que pré-preenche cada cardápio novo, e que ela pode
  trocar no dia específico.
- **DIREITO**: quem pode comer. É por refeição — um aluno pode ter almoço e não
  ter janta. **É benefício binário, sem preço**: não existe cobrança, fatura nem
  conciliação em lugar nenhum deste produto.
- **RESTRIÇÃO ALIMENTAR**: o que aquele aluno não pode comer. Dado de saúde.
- **PEDIDO**: o aluno reservando a refeição de um dia.
- **CANTINA**: o estabelecimento. Hoje há uma; a estrutura suporta várias.

## Os cinco estados de um dia — é o coração do calendário

    sem-cardapio    a cantina ainda não lançou nada para este dia
    rascunho        lançou, mas não publicou. O aluno NÃO vê
    aberto          publicado e o prazo ainda corre — o aluno pode pedir
    fechado         publicado e o prazo passou — o aluno vê, não pode mais pedir
    sem-refeicao    não se serve neste dia (fim de semana, feriado, recesso)

⚠️ **Dois desses estados são criados pelo RELÓGIO, não por uma ação.** Um dia
passa de `aberto` para `fechado` sozinho, quando o prazo vence. Ninguém aperta
nada. O calendário tem que ser legível sabendo que metade dos estados dele muda
com o tempo, e que a mesma tela aberta às 9h59 e às 10h01 mostra coisas
diferentes.

# A ÁRVORE

    /cantina                    HUB — três cards (dois, para quem não é admin)
      ├─ /cantina/cardapios     o calendário do mês
      │    ├─ /cantina/:data              o DIA, as duas refeições   ← rota nova
      │    └─ /cantina/:data/:refeicao    uma refeição               ← já existe
      ├─ /cantina/direitos      quem come aqui — ~900 alunos
      └─ /cantina/acesso        as cantinas e as contas — SÓ ADMINISTRADOR

    quem aponta para cá:
      Painel         card "O que é hoje?"        → /cantina/:hoje   (o dia)
      Administração  card "A cantina está        → /cantina         (o hub)
                           em dia?"

⚠️ O card do Painel **pula o hub** de propósito: é o que mantém o caminho diário
em um clique. O da Administração aponta para o hub, e é ele que impede o hub de
ficar órfão — o que já aconteceu uma vez nesta parte do produto, quando uma tela
ficou alcançável só digitando a URL.

# TELA A · `/cantina` — o hub

    CARDÁPIOS                 DIREITOS                ADMINISTRAR CANTINAS
    O que foi lançado?        Quem come aqui?         Quem lança o cardápio?
    setembro · 18 dias        87 de 900 alunos        1 cantina · 2 contas
    lançados · 2 em rascunho  62 almoço · 41 janta    prazo: 1 dia antes, 10h

Os três estados de cada card: carregando · vazio · com dado.

## O problema desta tela: ela muda de tamanho conforme quem entra

**"Administrar cantinas" é escrita exclusiva do administrador.** Existem dois
papéis na coordenação, e o coordenador comum vê **dois cards**; o administrador
vê **três**.

O card ausente **não aparece cinza** — some. É a regra que esta parte do produto
já segue: botão que existe para dar erro ensina a pessoa a desconfiar da tela.

Desenhe as duas composições. Três cards e dois cards não são a mesma grade com
um buraco, e a de dois não pode parecer que algo faltou.

⚠️ Este hub é alcançado a partir de OUTRO hub (Administração). Dois hubs em
sequência viram corredor se o segundo não informar nada por conta própria — é
por isso que os subtítulos vivos aqui não são enfeite: são o que faz a viagem
valer a pena.

# TELA B · `/cantina/cardapios` — o calendário

Uma grade do mês. Cada dia tem **duas células** — almoço e janta —, e cada
célula está num dos cinco estados. Um mês são ~60 células de estado.

É a tela mais densa de ESTADO do produto inteiro, e o desenho dela é o problema
central desta parte: cinco estados que precisam ser distinguíveis de relance,
sem semáforo, num sistema onde vermelho está reservado para falha operacional e
verde não existe.

Pense em termos das sete regras: `rascunho` e `sem-cardapio` são ausências de
coisas diferentes; `aberto` e `fechado` são o mesmo cardápio em dois momentos do
relógio; `sem-refeicao` não é falta, é "não se aplica" — e o dia sem cardápio
fica **inerte**, sem link, porque a coordenação lê e não lança.

Acima da grade: o mês navegável, o total de pedidos do mês, e quantos dias estão
em rascunho.

**O seletor de cantina** aparece **só quando houver mais de uma**. Com uma
cantina só, um seletor de uma opção é ruído — mesma lógica do elo quieto que
some quando está vazio.

# TELA B.2 · `/cantina/:data` — o dia — **ROTA NOVA**

O destino do card do Painel. As **duas refeições** de um dia, numa tela: o
cardápio de cada uma com seus itens, o prazo, quantos pediram cada coisa, e quem
pediu.

Ela não existe hoje — o que existe é a tela de UMA refeição
(`/cantina/:data/:refeicao`), que continua valendo porque a grade do calendário
tem um link por célula. As duas precisam parecer a mesma peça, uma com um
conteúdo e outra com dois.

Estados: dia com as duas refeições · dia com uma só · dia sem refeição · dia que
a cantina ainda não lançou.

# TELA C · `/cantina/direitos` — quem come aqui

~900 alunos numa tabela: **Aluno · Turma · Direito · Restrição alimentar**. Dois
KPIs em cima: alunos ativos, e quantos têm direito. Faixa de filtros: almoço ·
janta · sem direito, mais busca por nome ou matrícula.

## Duas telas na mesma rota

**Para o administrador**, é tela de escrita, e ela tem DOIS modos de conceder,
porque são dois momentos diferentes do ano:

- **Em lote** — seleção múltipla e uma barra de ação (`+ almoço`, `− almoço`,
  `+ janta`, `− janta`). Existe por causa da véspera do ano letivo: ligar o
  direito de 80 alunos um a um é a tarefa que não acontece, e o que não acontece
  na véspera derruba a funcionalidade inteira.
- **Na própria linha** — um toque concede ou revoga aquele aluno. É o caso do
  meio do ano: *"o Pedro passou a ter direito a janta"*. Hoje isso obriga a
  marcar um checkbox, subir até a barra, clicar, e ver a seleção limpar.

Os dois convivem na mesma tabela e é seu trabalho fazer com que não briguem.

**Para o coordenador comum**, é leitura: mesma lista, mesmos filtros, sem
checkbox e sem barra de lote. Não é a tela do administrador com botões cinzas —
é uma tela mais curta. Desenhe as duas.

## ⚠️ A restrição alimentar — dado de saúde de menor

É a categoria mais sensível da LGPD, é o único dado dessa natureza no produto, e
hoje ela é o texto na quarta coluna de uma tabela de 900 linhas, visível a
qualquer coordenador que role a lista.

**Decisão tomada: a coluna passa a dizer apenas que existe restrição, e o texto
abre sob clique.** Alcançável por quem precisa, não varrida por acidente por
quem procurava outra coisa.

Desenhe a revelação: o que a célula mostra fechada, o que aparece ao abrir, e
como se fecha. Editar continua sendo só do administrador; **ler passa a ser um
ato deliberado para todo mundo.** Não use isto como oportunidade de esconder o
dado atrás de algo bonito e difícil de achar — quem precisa dele precisa rápido.

# TELA D · `/cantina/acesso` — administrar cantinas · SÓ ADMINISTRADOR

Duas metades: **a cantina como estabelecimento** (nome, prazo padrão, ativa ou
inativa — criar, renomear, ajustar o prazo, desativar) e **as contas de acesso**
de cada uma (criar, editar, redefinir senha).

## Três coisas que esta tela precisa desenhar direito

**1 · A senha aparece UMA vez, e nunca mais.** Ao criar uma conta ou redefinir a
senha, o sistema sorteia uma e a mostra — uma vez só, sem jeito de recuperar
depois. É o momento mais frágil da tela: quem fechar sem copiar cria uma conta
inútil. Desenhe esse instante como o que ele é.

**2 · Desativar a CANTINA e desativar uma CONTA têm raios de explosão
diferentes.** Desligar o estabelecimento tranca todo mundo de uma vez —
inclusive uma conta criada depois. É o botão para *"a cantina saiu do colégio"*,
não para *"a Dona Maria saiu de férias"*. As duas ações não podem parecer a
mesma coisa em tamanhos diferentes.

**3 · Nada é apagado, nunca.** Desativar não remove linha: uma linha apagada
viraria um identificador sem nome na autoria dos cardápios e na trilha de
auditoria. A tela precisa dizer isso — "desativar" e "apagar" não são sinônimos
aqui, e o usuário vai supor que são.

⚠️ **O estado vazio desta tela já causou um defeito real.** O botão de criar
conta ficava escondido atrás de "já existe cantina", então a PRIMEIRA cantina
não tinha como nascer: a tela dizia "crie a cantina antes de criar as contas" e
não oferecia onde. **Estado vazio que dá uma instrução sem oferecer o caminho é
pior que estado vazio mudo.** Desenhe o primeiro dia: nenhuma cantina, nenhuma
conta.

# ESTADOS DA CANTINA

    hub              carregando · nenhuma cantina cadastrada ·
                     administrador (3 cards) · coordenador (2 cards)
    calendário       mês cheio · mês sem nada lançado · mês em curso com
                     passado fechado e futuro aberto · uma cantina · várias
    o dia            duas refeições · uma · nenhuma · não lançado
    direitos         administrador · coordenador · filtro sem resultado ·
                     nenhum aluno com direito (o primeiro dia) ·
                     restrição fechada e aberta
    acesso           primeiro dia (zero cantinas) · cantina inativa ·
                     senha recém-sorteada na tela

════════════════════════════════════════════════════════════════════════════

# RESTRIÇÕES — valem para as duas partes

Nenhum asset de terceiro (LGPD: são dados de menores). Nenhum gráfico com
biblioteca — SVG à mão. Nomes brasileiros inventados; nenhuma foto de pessoa;
avatar como círculo com duas letras. Nenhuma restrição alimentar que soe como
diagnóstico médico de alguém — use as genéricas ("sem lactose", "sem glúten",
"vegetariano"). Contraste AA nos dois temas. Foco de teclado visível. Nada de
pizza, donut, 3D, gradiente colorido ou visual de BI genérico.

# O QUE ENTREGAR

**Do Painel:**

1. O Painel nos dois temas, em 1440×900, no estado normal.
2. Os estados: sem alertas · nada recente · primeiro dia · carregando.
3. O card da cantina nos três estados, inclusive o inerte de dia sem refeição.
4. A grade com cinco cards, para provar que a estrutura aguenta o crescimento
   sem virar outra tela.
5. O cartão de alerta redesenhado, com a sparkline ganhando régua e com a ação
   "Resolver" tratada como a ação que ela virou.

**Da cantina:**

6. As quatro telas, nos dois temas, em 1440×900.
7. O hub nas duas composições: três cards e dois cards.
8. A grade do calendário com os cinco estados, lado a lado e legendados — é a
   peça mais difícil deste brief.
9. A tela de direitos nas duas versões, administrador e coordenador, com os dois
   modos de conceder convivendo.
10. A revelação da restrição alimentar: fechada, abrindo, aberta.

**E um documento curto de decisões**, respondendo a duas coisas:

- como você fez o card do ciclo dominar os outros dois sem que eles pareçam um
  erro de alinhamento — e o que acontece com essa hierarquia quando entram o
  quarto e o quinto card;
- como distinguiu os cinco estados do calendário sem semáforo, e o que fez para
  que `aberto` e `fechado`, que são o mesmo cardápio em dois momentos do
  relógio, não parecessem coisas diferentes.
```
