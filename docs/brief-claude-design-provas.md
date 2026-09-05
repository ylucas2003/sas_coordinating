# Brief para o Claude Design — a aba Provas da coordenação

Terceiro da família. [brief-claude-design-aluno.md](brief-claude-design-aluno.md)
criou o sistema; [brief-claude-design-coordenacao.md](brief-claude-design-coordenacao.md)
o estendeu para a coordenação inteira; **este aprofunda um ramo só — `/provas` —
e reverte uma decisão daquele.**

Cole o bloco abaixo inteiro no Claude Design. Anexe, se tiver:

- o brief mestre da coordenação, como sistema de referência;
- capturas de HOJE de `/provas`, `/ciclos/:id`, `/simulados/:id` e do Painel —
  são o **antes**, não a direção;
- capturas da área do ALUNO nos dois temas — essas são a direção.

⚠️ **LGPD.** Toda captura da coordenação mostra nome de menor. Anonimize antes
de anexar (CLAUDE.md §6).

---

```
# O QUE VOCÊ VAI FAZER

Você vai desenhar SETE telas de um ramo só de uma ferramenta profissional: a
aba PROVAS do SAS, a plataforma de coordenação do Colégio Ari de Sá.

O sistema de design já existe, está implementado e não está em discussão. Ele
está descrito inteiro aqui embaixo. O que você vai resolver é ESTRUTURA: uma
árvore de sete telas que acabou de mudar de forma por decisão do dono do
produto, e que tem no meio dela um problema de composição difícil e explícito,
descrito na seção "O PROBLEMA CENTRAL".

Não é um redesenho de pele. As telas existem e funcionam. O que está errado é
a distribuição do peso entre elas.

# PRECEDÊNCIA — leia antes de qualquer coisa

Se você tem o brief mestre da coordenação, ele é o SISTEMA: cores, papéis,
tipografia, as sete regras do semáforo, as cinco do padrão de campo. Vale tudo.

**Com UMA exceção, e ela é o motivo deste documento existir.**

O brief mestre diz, com todas as letras:

    "Não transforme o Painel num hub de campos. No Painel um campo domina
     esmagadoramente: a varredura. Virar hub cobraria um clique a mais na
     tarefa mais frequente do dia, todo dia."

**Essa decisão foi revertida em 05/09/2026 pelo dono do produto.** A tabela de
varredura sai do Painel e desce para dentro do ciclo. O Painel vira hub.

Não tente restaurar. E o argumento que sustenta a reversão importa para o seu
desenho, então leia:

A tabela de varredura **sempre foi de um ciclo só**. Ela nunca mostrou 900
alunos em geral — mostra 900 alunos × as matérias de UM ciclo, e a primeira
coisa que o coordenador fazia ao chegar era escolher o ciclo numa faixa de
filtros. Ou seja: a tela pedia um contexto que a URL já poderia ter dado. Ao
descer para `/ciclos/:id`, a tabela perde três filtros de graça — ano,
vestibular e ciclo viram a rota — e herda a régua de corte que já está no topo
daquela tela.

O custo é real e você tem que projetar contra ele: **varrer passa a custar um
clique a mais.** Painel → card "Como está fechando?" → tabela. Todo dia. Seu
desenho da entrada do ciclo tem que devolver esse clique em legibilidade, ou a
reversão foi um mau negócio.

Onde este documento e qualquer imagem discordarem, este documento vence.

# CONTEXTO — o que é este produto

O SAS acompanha ~900 estudantes do terceiro ano do ensino médio do Colégio Ari
de Sá (Fortaleza, Brasil) que se preparam para o ITA e o IME, as duas academias
militares de engenharia mais disputadas do país. Eles fazem simulados agrupados
em ciclos ao longo do ano; cada simulado é corrigido e vira nota de 0 a 10.

A coordenação é a metade da plataforma que a EQUIPE usa. A promessa dela, em
uma frase: **sinalizar o que merece atenção, em vez de esperar que o
coordenador saiba o que procurar.**

## Quem usa

Dois ou três coordenadores pedagógicos. Não são analistas de dados. Usam a
ferramenta oito horas por dia, muito no teclado, num monitor grande. O trabalho
real, em ordem de frequência:

1. **Varrer.** Achar, entre 900 linhas, quem caiu, quem está abaixo do corte e
   em quantas matérias. É a tarefa dominante do dia e ela vive dentro de
   `/provas` a partir de agora — é por isso que este ramo ganhou um brief só
   para ele.
2. **Julgar a prova, não o aluno.** Quando a turma inteira vai mal, a pergunta
   é se a prova estava mal calibrada. Histograma, média, desvio, percentis.
3. **Comparar.** Sede contra sede, turma contra turma, este ciclo contra o
   anterior.
4. **Operar.** Conferir o que o Canvas sincronizou, corrigir nota lançada
   errada, gerar o dossiê do ciclo em PDF para a reunião.

## Vocabulário — use estes termos, são do produto

- **CICLO**: uma rodada completa de simulados, Fase 1 + Fase 2. ~5 por ano.
  Nomeados "Ciclo 4 · ITA · 2026". É o objeto central deste brief.
- **SIMULADO**: uma prova. Tem fase (1 ou 2), matéria, data e nota de 0 a 10.
  Um ciclo tem de 6 a 14 simulados.
- **FASE 1 / FASE 2**: as duas fases do vestibular. F1 objetiva, F2 discursiva.
- **RÉGUA / CRITÉRIO**: o conjunto de cortes em vigor. São TRÊS e o coordenador
  escolhe qual está olhando: `tio-leo` (a pedagógica do colégio), `ITA` e `IME`
  (as do edital). **Todo aluno é avaliado contra ITA E IME.** Trocar a régua
  muda quem está cortado — não é um filtro, é uma lente.
- **CORTE**: a nota mínima que a régua exige naquela matéria. 4,0 é o padrão.
  O Inglês da Fase 1 do ITA é a ÚNICA matéria ELIMINATÓRIA, com corte 5,0.
  O corte é o conceito central do produto e vira o elemento visual central:
  uma linha.
- **DISTÂNCIA DO CORTE**: nota menos corte. É o ordenador padrão de toda tabela
  de aluno, ascendente — o pior primeiro.
- **MOTIVO**: por que o aluno foi cortado, em palavras — "Física 3,2 < 4,0".
  É a única explicação de corte que existe no produto.
- **ZONA**: `top` · `cinzenta` · `risco`. Onde o aluno está contra o corte.
- **SEDE e TURMA**: os dois recortes organizacionais. 2 sedes, ~12 turmas.
- **MATÉRIAS**: matemática, física, química, português, inglês, redação.
- **CANVAS**: o LMS do colégio, de onde vêm as notas e para onde vão os
  simulados. Estados: sincronizado · pendente · falhou · divergente.
- **DOSSIÊ**: o PDF/Word do ciclo, gerado da tela, levado para reunião.

## Idioma e escrita

TUDO em português do Brasil: rótulo, título, mensagem de erro, estado vazio, e
também nome de componente e classe CSS.

Número sempre com vírgula decimal ("6,4"). Nota sempre com uma casa. Sentence
case em título e botão. O único lugar com CAIXA ALTA é o rótulo de olho.

# O SISTEMA DE DESIGN — já decidido, não reabra

## Não existe verde nesta interface

O semáforo verde/âmbar/vermelho foi banido em 05/09/2026. A cor não era
decoração — era o mecanismo de varredura —, então o que entrou no lugar tem
que varrer melhor, não só ficar mais bonito. São sete regras e elas são o
coração do sistema:

**R1 · PREENCHIDO É ACIMA, VAZADO É ABAIXO.**
Célula, barra e selo de nota acima do corte são PREENCHIDOS na cor DADO.
Abaixo do corte são VAZADOS — contorno sem preenchimento, fundo transparente.
A varredura deixa de ser leitura de matiz e vira leitura de FORMA: um aluno em
risco é uma linha de buracos numa grade cheia, e o olho acha um buraco mais
rápido do que acha um vermelho no meio de outros vermelhos. Funciona no
daltonismo e funciona impresso.

**R2 · A RÉGUA É OURO E ESTÁ SEMPRE DESENHADA.**
Toda escala de nota mostra a linha de corte, em OURO, rotulada. Nunca se lê uma
nota sem a régua ao lado. E o corte NÃO é sempre 4,0: quando o corte da matéria
diverge do majoritário (o Inglês F1 do ITA, 5,0), ele vira um traço curto sobre
a própria barra.

**R3 · A INTENSIDADE CARREGA A DISTÂNCIA.**
Acima do corte, a saturação do preenchimento cresce com a distância acima.
Abaixo, a espessura e a opacidade do contorno crescem com a distância abaixo.
Escala sequencial de MATIZ ÚNICO, ancorada no corte — nunca divergente.

**R4 · ALERTA SÓ NA ETIQUETA, NUNCA NA SUPERFÍCIE.**
Vermelho existe para dois casos e só dois: (a) a etiqueta que diz a distância
abaixo do corte — "−1,4"; (b) a falha operacional — prova sem nota lançada,
sync do Canvas falhou. Nunca pinta linha, célula, cartão, barra ou número.

**R5 · A COMPARAÇÃO É CINZA.**
Média histórica, média da turma, ciclo anterior, banda de meta: tudo
REFERÊNCIA, cinza azulado, atrás do dado.

**R6 · A ORDENAÇÃO FAZ O TRABALHO QUE A COR FAZIA.**
Se o olho não pode achar o aluno em risco pela cor, a tela tem de ENTREGÁ-LO.
Toda tabela de aluno abre ordenada por **distância do corte, ascendente**, e o
ordenador em vigor é visível e NOMEADO no cabeçalho. Sem R6 as outras seis não
bastam.

**R7 · SILÊNCIO: uma escala semântica por tela.**
Se a tabela carrega a leitura, os KPIs e as tags acima dela ficam neutros.

### O que a R1 significa, célula a célula

    nota 8,7 · corte 4,0   →  ▉ preenchido, saturação alta
    nota 5,2 · corte 4,0   →  ▒ preenchido, saturação baixa
    nota 4,0 · corte 4,0   →  ▒ preenchido, mínimo — está NO corte, passou
    nota 3,6 · corte 4,0   →  ▢ vazado, contorno fino     + etiqueta −0,4
    nota 0,8 · corte 4,0   →  ▢ vazado, contorno grosso   + etiqueta −3,2
    sem nota               →  célula vazia com hachura diagonal, cinza
    ausente                →  glifo de ausência, cinza — NÃO é zero

A última linha importa: ausência e zero são coisas diferentes no domínio e a
interface nunca pode confundi-las.

## Cor é papel, nunca decoração — seis papéis

| Papel      | É                                                       |
|------------|---------------------------------------------------------|
| ACAO       | o que se aperta: botão primário, link, aba ativa         |
| VALOR      | a RÉGUA — linha de corte, banda de meta, critério em vigor |
| DADO       | o valor medido: barra, ponto, linha, célula cheia        |
| REFERENCIA | a comparação: histórico, média da turma, ciclo anterior  |
| ALERTA     | só a etiqueta de distância e a falha operacional         |
| MAGNITUDE  | todo numeral grande                                      |

    /* DIA */
    --fundo: #FFFFFF;      --superficie: #F4F7FC;   --borda: #DCE6F7;
    --acao: #1B3F8B;       --acao-base: #12275A;    --acao-texto: #FFFFFF;
    --valor: #F2C94C;      --valor-texto: #B07D12;
    --dado: #2E6BE6;       --dado-claro: #7FB6FF;
    --referencia: #8A93A8; --alerta: #E0452F;
    --magnitude: #0F1B33;  --texto: #16233D;        --texto-2: #5C6883;

    /* NOITE */
    --fundo: #050A18;      --superficie: #0C1530;   --borda: #1B2B57;
    --acao: #FFCE3A;       --acao-base: #C79A16;    --acao-texto: #050A18;
    --valor: #FFCE3A;      --valor-texto: #FFCE3A;
    --dado: #2F6BFF;       --dado-claro: #7FB6FF;
    --referencia: #6E85B8; --alerta: #FF6B4A;
    --magnitude: #FFFFFF;  --texto: #E6EDFB;        --texto-2: #6E85B8;

A regra que explica as trocas entre temas: **a ação é sempre a cor de maior
contraste com o fundo** — navy no dia, ouro na noite.

⚠️ Na noite, ACAO e VALOR são o mesmo amarelo. Numa tela cheia de gráficos com
linha de corte — que é metade deste brief — isso é risco real. **Resolva por
forma:** a régua é sempre traço fino tracejado com rótulo; o botão é sempre
retângulo sólido com raio. Se colidirem, a régua fica com o ouro e o botão
daquela tela vira fantasma.

⚠️ No dia a superfície leva borda de 2px; na noite, 1px.

## Forma

- **Raio: três valores e só três.** 18px em superfície, 12px em elemento
  pequeno, 999px em pílula.
- **Superfície: borda, NUNCA sombra flutuante.** Sem exceção.
- **Grade de fundo** quadrada de 24px, quase imperceptível, sob o conteúdo.
- **A tecla, só no botão primário, a 3px:** `box-shadow: 0 3px 0 0 <acao-base>`,
  e ao ser pressionado desce 3px e perde a sombra. Sem blur, nunca. Todo o
  resto é chapado.
- **Sem CAIXA ALTA em botão.**
- Alvo de toque mínimo 44px, inclusive nas pílulas de filtro.

## Tipografia

Plus Jakarta Sans, servida localmente, variável 200–800.

| Uso                  | Tamanho    | Peso | Observação                          |
|----------------------|------------|------|-------------------------------------|
| MAGNITUDE (KPI)      | 32–44px    | 800  | tracking −0.035em, tabular, lh 0.95 |
| Título de tela       | 26–28px    | 700  | sentence case                       |
| Migalha da topbar    | 19px       | 700  |                                     |
| Título de seção      | 16–17px    | 600  |                                     |
| Texto corrente       | 14–15px    | 400  | line-height 1.6                     |
| Rótulo e metadado    | 13px       | 400  | cinza                               |
| OLHO (eyebrow)       | 10px       | 700  | CAIXA ALTA, letter-spacing 0.12em   |
| Cabeçalho de tabela  | 12–13px    | 500  | cinza, sentence case                |
| Tag / pílula         | 12–13px    | 500  |                                     |

- **O olho substitui o rótulo de KPI.**
- **Numeral SEMPRE tabular.** Nota e média vivem em coluna.
- Sem negrito no meio de frase.

## Densidade — a única coisa que não se copia do aluno

A área do aluno lê uma coluna de 640px, uma coisa por vez, com ritmo generoso.
Aqui se varre uma tabela de 900 linhas × 14 colunas com a coluna do nome
congelada à esquerda. **O sistema é o mesmo; o RITMO não é.**

A tabela tem métrica própria: linha de 40–44px, padding horizontal de 10–20px,
fio entre linhas mais claro que a borda do card — senão a tabela vira grade e o
olho para em cada linha. O que se herda do aluno é o espaço ENTRE blocos, não
o espaço DENTRO da tabela.

## O padrão de campo — cinco regras

Cards que abrem tela inteira. Já existe no produto e é a coisa que mais reduziu
poluição visual na história do projeto. Copiar a aparência sem as regras dá um
menu bonito e inútil.

**C1 · A DIVISÃO É POR PERGUNTA, NUNCA POR TIPO DE OBJETO NEM POR RECÊNCIA.**

    ERRADO  "Último simulado"   →  CERTO  "A prova estava boa?"
    ERRADO  "Último ciclo"      →  CERTO  "Como está fechando?"
    ERRADO  "Melhores alunos"   →  CERTO  "Quem mudou de zona?"

A terceira troca é a mais importante: os melhores alunos são exatamente os que
menos precisam do coordenador.

**C2 · O SUBTÍTULO É DADO VIVO, NÃO DESCRIÇÃO.** "62 de 900 cortados · régua
Tio Leo", nunca "veja a classificação". Desenhe os TRÊS estados sempre:
carregando (esqueleto, sem número), vazio (a frase que convida), com dado.
Número escrito à mão envelhece calado.

**C3 · O DESTINO É TELA INTEIRA, COM URL PRÓPRIA.** Não acordeão, não modal,
não aba.

**C4 · A VOLTA É UM CHEVRON DE 44px NA MESMA LINHA DO TÍTULO.** Nunca um
"← Voltar" em linha própria. É chevron `‹`, não seta — a seta promete
"desfazer", o chevron diz "subir um nível". O nome acessível diz o DESTINO
("Voltar para Ciclo 4 · ITA · 2026").

**C5 · O ELO QUIETO.** O que precisa ser alcançável mas não é um campo vira
link discreto abaixo dos cards, com contagem. **Some quando está vazio, e some
quando a consulta FALHA** — "0 pendências" para quem tem 34 é a mentira mais
cara da tela.

### Anatomia do card de campo

    ┌──────────────────────────────────────────────┬────────┐
    │ OLHO EM CAIXA ALTA                           │        │
    │ Título grande                                │  SVG   │
    │ 27px · peso 800 · tracking −0.02em           │ 70×70  │
    │ subtítulo com dado vivo, 14px, texto-2       │ traço  │
    └──────────────────────────────────────────────┴────────┘

Superfície do sistema: borda, raio 18px, sem sombra. Afunda 2px ao ser
pressionado — menos que a tecla de 3px do botão, porque um card do tamanho da
tela afundando 3px parece solto. Ícone SVG em traço de 1.4, cor DADO,
decorativo: quem nomeia o destino é o texto.

# A ÁRVORE — sete telas

    /provas                    HUB de dois cards                    ← NOVA
      ├─ /provas/ciclos        lista de ciclos
      │    └─ /ciclos/:id      ENTRADA + 2 campos + A TABELA        ← A DIFÍCIL
      │         ├─ /ciclos/:id/calibracao   "A prova estava boa?"
      │         └─ /ciclos/:id/comparacao   "Onde estamos diferentes?"
      └─ /provas/simulados     lista de simulados
           └─ /simulados/:id   ficha de uma prova

Hoje `/provas` são duas ABAS (Ciclos | Simulados) e o ciclo tem TRÊS campos
(Calibração, Régua, Comparação). As duas coisas mudam.

# O PROBLEMA CENTRAL — leia duas vezes

`/ciclos/:id` passa a carregar, numa rolagem só:

    migalha + identidade do ciclo (nome · vestibular · ano · datas · N provas)
    controles: seletor de RÉGUA DE CORTE + [Dossiê PDF] [Dossiê Word]
    4 KPIs em magnitude
    2 cards de campo
    elo quieto das pendências
    ─────────────────────────────────────────────────────────
    A TABELA: 900 alunos × até 14 colunas, com filtros próprios
              (sede, turma, busca, fase), ordenação e edição de nota

**Isso é exatamente a doença que o padrão de campo existe para curar** — duas
escalas de atenção na mesma rolagem, e a maior perdendo. A diferença é que
desta vez é intencional: a tabela pertence ao ciclo, e a alternativa
(escondê-la atrás de um terceiro card) foi rejeitada.

Então o seu trabalho é este, e é o mais difícil do brief:

**Faça os dois campos e os KPIs deixarem de ser um obstáculo entre a chegada e
a tabela, sem escondê-los.**

Restrições que a solução tem que respeitar:

1. **A varredura é a tarefa dominante do dia.** Se o coordenador tiver que
   rolar por meia tela de cards toda vez que abre um ciclo, a mudança piorou o
   produto. O clique que ele já perdeu (Painel → ciclo) não pode virar um
   clique mais uma rolagem.
2. **Os campos não podem virar rodapé.** "A prova estava boa?" e "Onde estamos
   diferentes?" são perguntas que o coordenador não sabe que quer fazer — é
   por isso que elas são cards e não itens de menu. Enterrar embaixo da tabela
   é o mesmo que apagar.
3. **A régua de corte é global da tela.** O seletor no topo decide o corte da
   tabela E dos dois campos. Ele precisa parecer isso — não pode ler como mais
   um filtro da tabela.
4. **A tabela tem filtros próprios** (sede, turma, busca por nome, fase 1/2) e
   um ordenador nomeado. Eles pertencem à tabela, não à tela.

Direções possíveis, e você não está preso a nenhuma: uma faixa de campos fina e
horizontal em vez de cards grandes; os campos como uma coluna lateral ao lado
dos KPIs; a tabela como seção ancorada com o cabeçalho grudando ao rolar; os
campos encolhendo quando a tabela entra em foco. Escolha, justifique, e desenhe
o estado rolado além do estado de chegada.

# AS TELAS, UMA A UMA

## 1 · `/provas` — o hub, tela nova

Dois cards de campo. Nomes definidos pelo dono do produto e não são
negociáveis: **"Ciclos completos"** e **"Provas específicas"**.

    CICLOS COMPLETOS
    subtítulo vivo: "4 ciclos · Ciclo 4 · ITA em andamento, fecha em 6 dias"

    PROVAS ESPECÍFICAS
    subtítulo vivo: "255 provas · 3 sem nota lançada"

Dois cards numa tela inteira é pouca coisa e vai ficar vazio se você tratar
como grade de cards. Resolva a composição — é uma tela de bifurcação, não um
painel. Desenhe os três estados de C2.

## 2 · `/provas/ciclos` — a lista

Tabela: Ciclo · Vestibular · Período · Simulados · Canvas. Filtros em faixa de
pílulas: busca por nome, vestibular, ano letivo, intervalo de datas. Botão
primário "Criar ciclo". ~20 linhas, não 900 — a densidade aqui pode respirar
mais que a tabela grande.

O selo do Canvas tem quatro estados e um deles (`divergente`) é o mais
importante e o menos óbvio: o ciclo existe nos dois lados e eles não batem.

## 3 · `/ciclos/:id` — a entrada · **É A TELA DIFÍCIL**

Ver "O PROBLEMA CENTRAL". Conteúdo:

**Identidade:** "Ciclo 4 · ITA · 2026", pílula do vestibular, período
("14/08 → 26/09"), "8 de 12 provas aplicadas".

**Controles:** seletor de régua (Tio Leo · ITA · IME) + Dossiê PDF + Dossiê
Word.

**4 KPIs em magnitude:** Média geral · % aprovados · % zona crítica ·
% excelência.

**2 cards de campo:**

    CALIBRAÇÃO   "A prova estava boa?"
                 "6 matérias · 2 fora do padrão histórico"

    COMPARAÇÃO   "Onde estamos diferentes?"
                 "2 sedes · 12 turmas · maior diferença 1,4"

**Elo quieto:** "3 provas sem nota lançada" · "1 simulado não foi ao Canvas".
Some quando zero e some quando a consulta falha.

**A tabela.** Colunas: nome do aluno (congelada à esquerda) + uma coluna por
simulado do ciclo, agrupadas por matéria e separadas por um fio mais forte na
virada de fase, + média + **Situação** + **Distância**.

As duas últimas colunas são novas e vêm de uma tela que está sendo absorvida:
**Situação** é o motivo em palavras ("Física 3,2 < 4,0" ou "Passou") e
**Distância** é a distância do corte ("−1,4"). Elas são a única explicação de
corte do produto e não podem se perder na fusão.

A tabela abre por distância do corte, ascendente, com o ordenador nomeado num
cabeçalho visível (R6). Célula segue R1/R3/R4. Célula clicável abre a edição
de nota. Média da turma na última linha, em REFERENCIA.

**Desenhe o estado vazio.** Existem ciclos com ZERO simulados no banco (ex.:
"Ciclo 1 · IME · 2022"). Hoje a tela mostra quatro travessões, três cards
dizendo "ainda não" e nada mais — é a pior tela do produto. Um ciclo sem prova
aplicada tem que dizer o que é e o que fazer, não mostrar quatro buracos.

## 4 · `/ciclos/:id/calibracao` — "A prova estava boa?"

Aqui vive tudo que hoje está escondido atrás de um toggle "avançado" — e ele
deixa de precisar de toggle porque a tela é dele.

Por matéria, F1 e F2: histograma com a régua de ouro desenhada, média, mediana,
desvio, IQR, p10/p25/p75/p90, moda, assimetria, curtose, sinal de bimodalidade,
e o delta entre as fases. Comparação com o padrão histórico da matéria em
REFERENCIA, atrás do dado.

Chevron de volta (C4). Seletor de régua na mesma linha do título.

Doze histogramas numa tela é o risco óbvio. Resolva a repetição — pequenos
múltiplos com escala compartilhada, e a matéria fora do padrão ganhando
destaque por posição ou tamanho, nunca por cor.

## 5 · `/ciclos/:id/comparacao` — "Onde estamos diferentes?"

Sede × sede, turma × turma, e este ciclo contra o anterior. A comparação é o
lugar onde a R5 trabalha mais: o valor de referência é cinza e fica ATRÁS do
dado, sempre.

Cuidado com a armadilha do brief mestre: comparar duas sedes com duas cores
categóricas reinventa o semáforo por outro caminho. Máximo 5 cores
categóricas, e prefira posição a cor.

## 6 · `/provas/simulados` — a lista

Tabela de ~255 linhas: prova · ciclo · fase · matéria · data · média · estado
no Canvas. Filtros: busca, ciclo, fase, matéria, intervalo de datas.
Botão primário "Agendar simulado".

## 7 · `/simulados/:id` — a ficha da prova

Uma prova, uma matéria, uma data. Distribuição com a régua desenhada, quem
faltou, quem zerou, o estado no Canvas, a lista de notas.

**Ausência e zero são coisas diferentes e a tela é obrigada a separá-las** —
falta contando como zero deturpa toda média, e é um problema conhecido do
domínio. Desenhe a distinção.

# OS DADOS — use estes números nos mocks

    ~900 alunos · 2 sedes · ~12 turmas · 6 matérias · ~5 ciclos por ano
    um ciclo tem de 6 a 14 simulados
    média de turma tipicamente entre 3,8 e 6,2
    entre 25% e 45% dos alunos abaixo do corte em pelo menos uma matéria
    matemática e física puxam para baixo; português e inglês para cima
    ~255 simulados no acervo, ~5 anos de histórico

    Nota        0 a 10, uma casa, vírgula. Pode ser nula (sem lançamento) e
                pode ser AUSÊNCIA — que não é zero.
    Stats       n, média, mediana, desvio, IQR, p10/p25/p75/p90, moda,
                assimetria, curtose, bimodal, % aprovados, % zona crítica
    Canvas      sincronizado | pendente | falhou | divergente

Nomes brasileiros plausíveis e inventados. **Nenhum nome real de aluno, nenhuma
foto de pessoa** — avatar é círculo com duas letras.

# RESTRIÇÕES QUE NÃO SÃO NEGOCIÁVEIS

- **Nenhum asset de terceiro.** Sem CDN, sem Google Fonts, sem biblioteca de
  ícone remota, sem telemetria. Os dados são de menores de idade e isso é
  regra de LGPD do projeto, não preferência. Ícones como SVG inline.
- **Nenhum gráfico com biblioteca.** Todos os gráficos do projeto são SVG
  escrito à mão. Chart.js e equivalentes estão fora por decisão registrada.
- **Nenhuma marca real de terceiro.** Nada de brasão do ITA ou do IME.
- **Proibidos:** pizza, donut, 3D, velocímetro, gradiente colorido, brilho,
  neon, sombra pesada, mais de 5 cores categóricas, visual de BI genérico.
- **Contraste WCAG AA em todo texto, nos dois temas.** O ouro puro reprova como
  letra sobre fundo claro: use `--valor-texto` quando o ouro for texto, e
  `--valor` só para traço e preenchimento.
- **Foco de teclado visível em tudo.** A ferramenta é usada muito no teclado e
  já existe atalho global "/" para a busca.
- Respeite `prefers-reduced-motion`.

# ARMADILHAS DESTE RAMO

**1 · O dossiê não pode escurecer.** O PDF e o PNG do ciclo são gerados
lendo os tokens de cor em tempo de execução, e saem DESTAS telas. Existe uma
paleta clara FIXA só para documento, que não responde a tema. Se você amarrar
alguma cor de gráfico ao tema, o coordenador que trabalha à noite gera um
dossiê preto.

**2 · O dossiê é UM documento com tudo.** Os campos dividem a leitura na tela,
não o documento impresso. E ele reaproveita os MESMOS SVGs desenhados na tela
— dois desenhos do mesmo gráfico divergem no primeiro ajuste. Qualquer gráfico
que você desenhe tem que funcionar também em preto e branco, numa folha A4.

**3 · O servidor ainda manda nome de cor.** Os campos de tom são literais
`'verde' | 'ambar' | 'vermelho'`, calculados no backend a partir do corte.
Banir o verde não é só CSS. A tradução é:

    verde     → preenchido, saturação alta      (bem acima do corte)
    ambar     → preenchido, saturação baixa     (acima, mas na margem)
    vermelho  → vazado + etiqueta de distância  (abaixo do corte)
    cinza     → sem dado

**4 · A régua dupla.** Existiu uma função que decidia a cor da média com um
ternário fixo (≥7 verde, ≥5 âmbar) sem relação nenhuma com o corte em uso,
enquanto a célula logo abaixo usava o corte de verdade — o mesmo número verde
em cima e vermelho embaixo. Ela morreu. Não a reintroduza sob outro nome:
**nenhum número desta tela tem cor que não venha do corte da régua em vigor.**

**5 · A faixa de filtros mede a si mesma.** Ela colapsa quando o conteúdo passa
de uma linha, o que significa medir altura e reagir. Mantenha a pílula com
altura fixa.

**6 · O rail abre por CSS, não por estado** (`:hover`, `:focus-within`). Não
desenhe nada que exija JavaScript para o rail abrir.

# O CASCO — não muda, mas enquadra tudo

    RAIL à esquerda, 88px fechado / 228px aberto no hover e no foco.
    Cinco destinos: Painel · Alunos · Provas · Banco · Administração
    Marca no topo, logo do colégio no rodapé.

    TOPBAR de 72px: migalhas à esquerda ("Provas › Ciclos › Ciclo 4 · ITA ·
    2026"); busca global de aluno (atalho "/"); sino de alertas; avatar.

    <main> no resto.

As migalhas ganham um nível com esta mudança — desenhe o caminho de quatro
degraus e o que ele faz quando o nome do ciclo é longo.

# O QUE ENTREGAR

1. **As sete telas, nos dois temas, em 1440×900.** A entrada do ciclo em DOIS
   estados: chegada e rolado até a tabela.
2. **O estado vazio da entrada do ciclo** — ciclo sem prova aplicada.
3. **O kit de peças novo deste ramo:** o card de campo em faixa fina (se for a
   sua solução), o cabeçalho de tabela com ordenador nomeado, a célula de nota
   nos sete estados da R1, o selo do Canvas nos quatro estados, o histograma
   com régua de ouro, e a linha de corte em gráfico nos dois temas.
4. **Um documento curto de decisões:** o que você mudou e por quê —
   especialmente COMO resolveu o problema central, e o que sacrificou para
   resolver. Se a sua solução cobra alguma coisa da varredura, diga o quê.

Onde este documento e qualquer imagem anexada discordarem, este documento
vence, sempre.
```
