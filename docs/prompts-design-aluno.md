# Prompts de design — área do aluno · v2, gamificada

Substitui a v1 (planta baixa). O diagnóstico que mudou tudo está em
[24-jornada-do-aluno.md §6](24-jornada-do-aluno.md): **a área do aluno não tem
loop diário** — nota muda a cada três semanas, e nenhuma mecânica de jogo pega
num produto sem novidade diária. O banco de questões vira o motor.

- **Gerador:** Ideogram ou Imagen. Proporção **9:16**.
- **Cada bloco é autossuficiente.** Copia inteiro, cola, gera.
- **A1 a A4 são a MESMA tela em quatro direções** — é a comparação que decide a
  linguagem visual. Gere as quatro antes de olhar o resto.
- **B1 e B2 são a mesma liga com e sem apelido** — decide a mecânica competitiva.
- **C1 e C2 são as telas que hoje não existem**: a celebração e a sessão de
  questões. Estão na direção A1; troco para a vencedora depois.
- **O que julgar:** onde o olho cai primeiro, se dá vontade de apertar o botão, e
  se parece jogo. Não a ortografia — todo modelo ainda erra letra.

Referências pesquisadas e o que foi roubado de cada uma estão na conversa; o
resumo curto: a tecla com 4px de sombra inferior, cor como estado e nunca
decoração, a chama que acelera quando a ofensiva está em risco, a barra que anda
mesmo no erro, e celebração em duas escalas.

---

## O sistema em dois temas — dia e noite

**Esta é a direção escolhida.** P1 e P4 viraram um sistema só: mesmo layout,
mesmos seis papéis de cor, e só os valores mudam entre os temas. Os dois prompts
abaixo são o par reconciliado — as inconsistências das primeiras gerações
(sequência, barra de meta, barra abaixo do corte) foram unificadas.

Duas trocas entre os temas são intencionais e forçadas pelo contraste: a **ação**
é sempre a cor que mais contrasta com o fundo (navy no dia, ouro na noite), e a
**magnitude** acompanha (quase-preto no dia, branco na noite). Todo o resto é
constante.

Sem mascote nos dois — o aviãozinho da primeira geração vazou da direção A2 e
nunca foi pedido. Se ele entrar, entra nos dois.

### Dia — claro

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — the DAY theme of a two-theme system: the school's blue and white,
bright and grown-up. A game, never austere.

Ground: white #FFFFFF. Raised surfaces #F4F7FC with 18px corner radius and a 2px
border #DCE6F7. Generous padding, big shapes, big numbers, strong contrast.
Secondary text #5C6883, kept deliberately muted so the colours dominate.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its
role and for nothing else:
- ACTION, the thing you press: navy #1B3F8B, white label, with a 4px hard bottom edge in #12275A
- VALUE, XP and anything earned, and the cut line: gold #F2C94C for strokes and fills, and darker #B07D12 whenever gold is text
- DATA, bars above the cut, progress fills, the active navigation item: blue #2E6BE6
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, the distance tag and nothing else: #E0452F
- MAGNITUDE, every large numeral: near-black navy #0F1B33
No green anywhere. No traffic-light palette. No colour outside this list.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur — a
physical key waiting to be pressed. Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 44 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. All figures tabular.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a coral flame icon with "12" beside it in large
MAGNITUDE numerals and a tiny uppercase label "SEQUÊNCIA" beneath in secondary
text; at the centre-right a small gold token with "1.240" and the label "XP"; at
the far right a circular avatar containing "RF".

HERO BLOCK, the dominant element of the screen: a small uppercase eyebrow in DATA
colour, "MISSÃO DE HOJE"; below it, very large in MAGNITUDE colour, "12 questões
de Termodinâmica"; below that one quieter line in secondary text, "Cai em 7% da
prova do ITA. Você acerta 41%."; then a full-width tall ACTION button labelled
"COMEÇAR" in bold uppercase, letterspaced.

STREAK CHAIN under the hero: seven small rounded squares, labelled S T Q Q S S D
beneath. Five are filled coral; the sixth is today, filled coral with a thin ring
around it; the seventh is empty — a hollow outline.

WEEKLY GOAL: uppercase label "META DA SEMANA" with "34/50" in MAGNITUDE colour at
the right end, and beneath it a rounded track filled 68% in DATA colour, the
remainder an unfilled track.

"ONDE VOCÊ ESTÁ", below a divider: five vertical bars labelled MAT FÍS QUÍ POR ING,
reaching 6,8 — 7,4 — 3,2 — 5,9 — 4,6 on a 0 to 10 axis, each value printed in
MAGNITUDE colour above its bar. Four bars are solid DATA colour. A single VALUE
horizontal line crosses all five at 4,0, labelled "CORTE" at its right end.
The QUÍ bar is HOLLOW — an outline with no fill — ends clearly below that line,
and carries a small ALERT tag reading "−0,8" beneath it.

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Plano,
Liga, Jornada. "Hoje" is active, in DATA colour with a short underline beneath;
the other three are muted.
```

### Noite — escuro

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — the NIGHT theme of the same system, same layout and same roles as the
day theme, only the values change. Night neon on the school's own colours.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Behind everything an extremely faint square grid
in #0E1A38, barely perceptible. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its
role and for nothing else:
- ACTION, the thing you press: lit gold #FFCE3A, near-black #050A18 label, with a 4px hard bottom edge in #C79A16
- VALUE, XP and anything earned, and the cut line: lit gold #FFCE3A
- DATA, bars above the cut, progress fills, the active navigation item: electric blue #2F6BFF, with ice blue #7FB6FF as its lighter register
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, the distance tag and nothing else: coral #FF6B4A
- MAGNITUDE, every large numeral: white #FFFFFF
No green anywhere. No traffic-light palette. No colour outside this list.

In this theme ACTION and VALUE are the same gold, and that is deliberate: on a
near-black ground gold is both the highest-contrast colour and the colour of
worth.

NEON TREATMENT, with restraint: key strokes — the cut line, the ring around
today, the active navigation underline — are thin neon tubes, a bright core with
a tight halo no wider than 4px. Filled surfaces, buttons and text have NO glow.
Anything empty or below a threshold is drawn UNLIT: a dark hollow outline, like a
burnt-out segment of a sign.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur.
Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 44 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. All figures tabular.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a coral flame icon with "12" beside it in large
MAGNITUDE numerals and a tiny uppercase label "SEQUÊNCIA" beneath in secondary
text; at the centre-right a small gold token with "1.240" and the label "XP"; at
the far right a circular avatar containing "RF".

HERO BLOCK, the dominant element of the screen: a small uppercase eyebrow in DATA
colour, "MISSÃO DE HOJE"; below it, very large in MAGNITUDE colour, "12 questões
de Termodinâmica"; below that one quieter line in secondary text, "Cai em 7% da
prova do ITA. Você acerta 41%."; then a full-width tall ACTION button labelled
"COMEÇAR" in bold uppercase, letterspaced.

STREAK CHAIN under the hero: seven small rounded squares, labelled S T Q Q S S D
beneath. Five are filled coral; the sixth is today, filled coral with a thin ring
around it; the seventh is empty — a hollow outline.

WEEKLY GOAL: uppercase label "META DA SEMANA" with "34/50" in MAGNITUDE colour at
the right end, and beneath it a rounded track filled 68% in DATA colour, the
remainder an unfilled track.

"ONDE VOCÊ ESTÁ", below a divider: five vertical bars labelled MAT FÍS QUÍ POR ING,
reaching 6,8 — 7,4 — 3,2 — 5,9 — 4,6 on a 0 to 10 axis, each value printed in
MAGNITUDE colour above its bar. Four bars are solid DATA colour. A single VALUE
horizontal line crosses all five at 4,0, labelled "CORTE" at its right end.
The QUÍ bar is HOLLOW — an outline with no fill — ends clearly below that line,
and carries a small ALERT tag reading "−0,8" beneath it.

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Plano,
Liga, Jornada. "Hoje" is active, in DATA colour with a short underline beneath;
the other three are muted.
```

---

## As quatro abas — Hoje · Estudar · Provas · Jornada

Estrutura aprovada em 29/08. A regra que a organiza: **as abas seguem o que o
aluno vem fazer, não o modelo de dados.** De 21 itens, 13 já existem, 4 são
adaptação e 4 são criação — e três coisas prontas na API que nenhuma tela
desenhava (`/me/trajetoria`, `/me/heatmap`, `/me/simulado/{id}/arquivo`) voltam
a ser vistas.

"Hoje" tem prompt próprio na seção anterior (o par dia/noite). As três abaixo
estão no tema NOITE; o bloco de troca para o tema DIA vem no fim.

### Estudar

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Behind everything an extremely faint square grid
in #0E1A38, barely perceptible. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its role
and for nothing else:
- ACTION, the thing you press: lit gold #FFCE3A, near-black #050A18 label, with a
  4px hard bottom edge in #C79A16
- VALUE, XP and anything earned, and the cut line: lit gold #FFCE3A
- DATA, bars above the cut, progress fills, the active navigation item: electric
  blue #2F6BFF, with ice blue #7FB6FF as its lighter register
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, a distance tag or a value below the cut, and nothing else: coral #FF6B4A
- MAGNITUDE, every large numeral: white #FFFFFF
No green anywhere. No traffic-light palette. No colour outside this list.

NEON TREATMENT, with restraint: key strokes — the cut line, rings, the active
navigation underline — are thin neon tubes, a bright core with a tight halo no
wider than 4px. Filled surfaces, buttons and text have NO glow. Anything empty,
locked or below a threshold is drawn UNLIT: a dark hollow outline, like a
burnt-out segment of a sign.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur.
Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Small uppercase letterspaced
labels for eyebrows. All figures tabular.

THE SCREEN — "Estudar": what to train, and the question bank as a tool rather
than a catalogue.

TOP BAR, 56px: "Estudar" at the left in MAGNITUDE colour, a circular avatar
containing "RF" at the right.

SEGMENTED CONTROL directly below, full width, three equal segments inside a
single rounded track: "Prioridade", "Meus erros", "Banco". "Prioridade" is
selected — a filled DATA-colour segment with near-black label; the other two are
unlit with dim labels.

COVERAGE STRIP: a full-width strip with a 1px hairline border and no fill,
carrying a small uppercase label "COBERTURA" and one quiet line: "Cobre
Matemática, Física e Química. Português, Inglês e Redação ainda não."

RANKED LIST of five topics, each row separated by a hairline, and a single
vertical hairline running down the left edge connecting all five rank numbers.
Each row contains: a two-digit rank in small uppercase (01 to 05); the topic name
in condensed grotesque 17px in MAGNITUDE colour; below it one quiet line of body
copy; and at the right edge a dual reading — a short horizontal track where a
gold VALUE tick marks how much the topic is worth in the exam and a solid DATA
fill shows the student's accuracy, the span between them left unlit.
Rows 01 and 02 also carry a small gold ACTION chip at their right reading
"TREINAR" with the 4px bottom edge.

Row 01 — "Termodinâmica" / "Cai em 7% da prova. Você acerta 41%."
Row 02 — "Estequiometria" / "Cai em 6% da prova. Você acerta 38%."
Row 03 — "Análise combinatória" / "Cai em 5% da prova. Você acerta 52%."
Row 04 — "Eletrostática" / "Cai em 5% da prova. Você acerta 64%."
Row 05 — "Geometria analítica" / "Cai em 4% da prova. Você acerta 70%."

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Estudar" is active, in DATA colour with a short neon underline
beneath; the other three are muted and unlit.
```

### Provas

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Behind everything an extremely faint square grid
in #0E1A38, barely perceptible. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its role
and for nothing else:
- ACTION, the thing you press: lit gold #FFCE3A, near-black #050A18 label, with a
  4px hard bottom edge in #C79A16
- VALUE, XP and anything earned, and the cut line: lit gold #FFCE3A
- DATA, bars above the cut, progress fills, the active navigation item: electric
  blue #2F6BFF, with ice blue #7FB6FF as its lighter register
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, a distance tag or a value below the cut, and nothing else: coral #FF6B4A
- MAGNITUDE, every large numeral: white #FFFFFF
No green anywhere. No traffic-light palette. No colour outside this list.

NEON TREATMENT, with restraint: key strokes — the cut line, rings, the active
navigation underline — are thin neon tubes, a bright core with a tight halo no
wider than 4px. Filled surfaces, buttons and text have NO glow. Anything empty,
locked or below a threshold is drawn UNLIT: a dark hollow outline, like a
burnt-out segment of a sign.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur.
Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Small uppercase letterspaced
labels for eyebrows. All figures tabular.

THE SCREEN — "Provas": how the student actually did.

TOP BAR, 56px: "Provas" at the left in MAGNITUDE colour, a circular avatar
containing "RF" at the right.

HERO CARD, a raised surface: a small uppercase eyebrow "ÚLTIMO SIMULADO"; the
name "Ciclo 4 · ITA · P5" in condensed grotesque; and a very large "6,4" in
MAGNITUDE colour, 64px, with a small DATA-coloured upward triangle and "+0,7 vs.
seu padrão" beside it. To the right of the number, three compact readings stacked
and divided by hairlines, each a tiny uppercase label above a value: "APLICADO /
18 AGO", "POSIÇÃO / 47 DE 312", "PERCENTIL / 85".

HEATMAP, below a divider, with the eyebrow "MATÉRIA POR CICLO": a grid of five
rows by five columns. Rows are labelled at the left in small uppercase MAT, FÍS,
QUÍ, POR, ING; columns are labelled beneath in small uppercase C1, C2, C3, C4,
C5. Each cell is a rounded square filled with DATA colour whose intensity encodes
the grade — the strongest cells fully saturated electric blue, the weakest a very
dim blue. Cells representing a grade below the cut are UNLIT: a dark hollow
outline with a thin coral edge. In the QUÍ row, the C4 and C5 cells are unlit.
A tiny legend beneath in dim uppercase: "0 ——— 10   ▢ ABAIXO DO CORTE".

SIMULADO LIST, below a divider, with the eyebrow "TODOS OS SIMULADOS": four rows
separated by hairlines. Each row has the label in condensed grotesque at the
left, the date in dim small uppercase beneath it, the grade in MAGNITUDE colour
at the right, and under the grade a tiny delta with a triangle in DATA colour for
a rise and coral for a fall.
"Ciclo 4 · ITA · P5" / "18 AGO" / 6,4 / ▲ 0,7
"Ciclo 4 · IME · P4" / "04 AGO" / 5,8 / ▲ 0,3
"Ciclo 3 · ITA · P3" / "12 JUL" / 5,5 / ▼ 0,2
"Ciclo 3 · IME · P2" / "28 JUN" / 5,7 / ▲ 1,1

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Provas" is active, in DATA colour with a short neon underline
beneath; the other three are muted and unlit.
```

### Jornada

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Behind everything an extremely faint square grid
in #0E1A38, barely perceptible. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its role
and for nothing else:
- ACTION, the thing you press: lit gold #FFCE3A, near-black #050A18 label, with a
  4px hard bottom edge in #C79A16
- VALUE, XP and anything earned, and the cut line: lit gold #FFCE3A
- DATA, bars above the cut, progress fills, the active navigation item: electric
  blue #2F6BFF, with ice blue #7FB6FF as its lighter register
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, a distance tag or a value below the cut, and nothing else: coral #FF6B4A
- MAGNITUDE, every large numeral: white #FFFFFF
No green anywhere. No traffic-light palette. No colour outside this list.

NEON TREATMENT, with restraint: key strokes — the cut line, rings, the active
navigation underline — are thin neon tubes, a bright core with a tight halo no
wider than 4px. Filled surfaces, buttons and text have NO glow. Anything empty,
locked or below a threshold is drawn UNLIT: a dark hollow outline, like a
burnt-out segment of a sign.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur.
Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Small uppercase letterspaced
labels for eyebrows. All figures tabular.

THE SCREEN — "Jornada": where the student stands and how far they have come.

TOP BAR, 56px: "Sua jornada" at the left in MAGNITUDE colour, a circular avatar
containing "RF" at the right.

HERO CARD, a raised surface, the dominant element: a small uppercase eyebrow
"ONDE VOCÊ ESTÁ"; then three horizontal bands stacked bottom to top as outlines
with hairline borders, labelled in small uppercase from bottom to top RISCO,
CINZENTA, TOP. The RISCO band is unlit. A solid DATA-coloured dot sits inside the
CINZENTA band with a hairline leader to a small label "VOCÊ". The boundary
between CINZENTA and TOP is a gold VALUE neon line labelled "CORTE 8,0" at its
right end. A vertical dimension line with arrowheads runs from the dot up to that
gold line with "1,2" set in a break in the middle. Under the bands, one quiet
line: "Faltam 1,2 em Química para sair da cinzenta."

TRAJECTORY CHART, below a divider, eyebrow "SUA TRAJETÓRIA": a wide line chart. A
0 to 10 axis runs down the left with tick marks. A gold VALUE neon line crosses
the whole chart at 4,0 labelled "CORTE" at its right end, and the region below it
is unlit. A solid DATA-coloured polyline plots five points labelled beneath in
small uppercase C1, C2, C3, C4, C5, starting below the gold line at C1, crossing
it between C2 and C3 — the crossing marked with a hollow ring and a hairline
leader to a small uppercase label "CRUZOU NO CICLO 3" — and rising to 6,4 at C5.
A dim dashed line shows the class average, with a tiny legend beneath reading
"— VOCÊ    - - - MÉDIA DA TURMA".

LEAGUE CARD, below a divider: a compact raised row with a small gold shield glyph
at the left; "Liga Ouro" in condensed grotesque with a dim line beneath reading
"6º de 34 · faltam 262 XP para subir"; and at the right a gold ACTION chip
reading "VER" with the 4px bottom edge.

ACHIEVEMENTS, below a divider, eyebrow "CONQUISTAS": a row of four square tiles.
Three are lit — a DATA-coloured 1px edge, a thin line icon inside, a small label
beneath and a tinier dim caption under that: "Cruzou o corte / CICLO 3",
"3 semanas seguidas / CONQUISTADO", "Primeiro 8,0 / FÍSICA · C4". The fourth is
UNLIT — dark hollow outline, dim label: "50 questões / 34 DE 50", with a thin
progress track beneath it filled 68% in DATA colour.

MESSAGE CARD, at the bottom: a quiet raised surface with a large gold quotation
mark glyph at its left, a small uppercase eyebrow "DE QUEM JÁ PASSOU", a line in
condensed grotesque reading "Três aprovados no ITA contam como estudaram", and a
dim text-only link at the right reading "Ler".

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Jornada" is active, in DATA colour with a short neon underline
beneath; the other three are muted and unlit.
```

### Trocar para o tema dia

```
Para gerar qualquer uma das telas no TEMA DIA, troque o bloco "TEMA — NOITE"
inteiro por este, e apague o parágrafo do NEON TREATMENT:

TEMA — DIA.

Ground: white #FFFFFF. Raised surfaces #F4F7FC with 18px corner radius and a 2px
border #DCE6F7. Generous padding. Secondary text #5C6883, kept deliberately muted.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its role
and for nothing else:
- ACTION, the thing you press: navy #1B3F8B, white label, with a 4px hard bottom
  edge in #12275A
- VALUE, XP and anything earned, and the cut line: gold #F2C94C for strokes and
  fills, darker #B07D12 whenever gold is text
- DATA, bars above the cut, progress fills, the active navigation item: blue
  #2E6BE6
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, a distance tag or a value below the cut, and nothing else: #E0452F
- MAGNITUDE, every large numeral: near-black navy #0F1B33
No green anywhere. No traffic-light palette. No colour outside this list.

Anything empty, locked or below a threshold is drawn HOLLOW: an outline with no
fill. Only buttons and tappable tiles carry the 4px hard bottom edge, with no
blur. Every other surface is flat.
```

---

## Login gamificado e as versões desktop

⚠️ **Versões de 29/08, com a referência ao ITA reforçada.** As primeiras versões
usavam pista de pouso e horizonte genérico. Entraram no lugar: **volume
horizontal modernista sobre pilotis com fachada de cobogó** (o campus do DCTA foi
projetado por Oscar Niemeyer nos anos 1940, e a planta do prédio principal lembra
a letra H), **campus arborizado** e o prédio **abaixo** da linha de ouro.

A ideia que amarra tudo: **a treliça do cobogó usa a mesma grade quadrada que já é
o fundo de todas as telas do app.** O `#0E1A38` deixa de ser textura e passa a ser
a fachada vista de perto.

Nenhum brasão, nenhuma insígnia, nenhuma marca — só arquitetura e paisagem.


O login é a **única tela do produto que pode ser ilustrada**. Todas as outras
proíbem ilustração de propósito — é o que faz esta valer.

⚠️ **Nenhuma insígnia real nos prompts.** O selo do ITA e o brasão do Ari são
marcas de terceiros; o prompt pede um selo abstrato de placeholder e evoca o
*mundo* (aeronáutica, horizonte, pista, planador) em vez da marca. Na
implementação, os assets reais já existem e já são servidos da nossa origem —
`web/assets/ari-logo-branca.png`, `sas-logo.png` e `selo-108anos.webp` — o que
mantém a regra 6 do CLAUDE.md intacta.

Os números da tira de rodapé ("900 alunos", "2.693 questões") são reais hoje, mas
**viram dado dinâmico ou saem** — número institucional errado na porta de entrada
é pior que número nenhum.

Desktop usa **três colunas**: rail de 240px à esquerda, coluna central de 640px
com o mesmo ritmo do celular, e uma coluna direita de 320px com os widgets
persistentes (sequência, XP, meta, liga). O conteúdo é redistribuído, nunca
esticado.

### Login · celular

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION: lit gold #FFCE3A is the primary button, the cut
line and anything earned; electric blue #2F6BFF with ice blue #7FB6FF is data and
state; coral #FF6B4A is the streak; white #FFFFFF is every large numeral and
headline. No green anywhere. No colour outside this list.

Type: a heavy condensed grotesque for headlines, 40px, and a rounded humanist
sans for body copy at 15 to 17px. Small uppercase letterspaced labels at 10px.

Only buttons carry a 4px hard bottom edge, with no blur. Every other surface is
flat. Nothing in this image glows.

⚠️ NO REAL LOGOS, NO CREST, NO WORDMARK, NO MILITARY INSIGNIA of any institution.
The architecture below is an evocation of mid-century Brazilian modernist campus
design, not a portrait of a specific protected building. Any emblem is an abstract
placeholder: a plain circular seal with a laurel ring and no legible text.

UPPER 55% OF THE SCREEN — one flat vector illustration, edge to edge, built only
from flat shapes. No photography, no 3D, no gradients except the sky bands.

The scene, from back to front:
1. SKY: a dawn sky in four stacked horizontal bands of deep blue, darkest at the
   top and lightest at the horizon. A sparse scatter of small stars in the upper
   bands, and one constellation of five stars joined by hairlines.
2. HILLS: low rolling hills across the horizon in a single darker blue silhouette
   — the Vale do Paraíba.
3. THE CUT LINE: a single continuous LIT GOLD horizontal line lying exactly on the
   horizon, labelled at its right end in tiny uppercase "CORTE". This is the same
   gold line that appears on every other screen of the product.
4. THE BUILDING, the centrepiece, which must read as unmistakably a mid-century
   Brazilian engineering campus: a LONG, LOW, STRICTLY HORIZONTAL modernist block
   on slender PILOTIS — thin columns lifting the volume off the ground with the
   landscape visible through the gap beneath. A flat dark silhouette in #0A1428
   with its façade rendered as a REGULAR LATTICE OF SMALL SQUARES, a cobogó
   breeze-block screen, a few of whose squares are lit from within in warm ice
   blue as if rooms were awake before dawn. The block runs off both edges, and its
   roofline sits just BELOW the gold line so the gold reads as the horizon behind
   it.
   ⚠️ The lattice must use exactly the same square grid rhythm as the faint
   background grid used throughout the rest of the app.
5. TREES: a row of flat rounded tree silhouettes in an even darker blue in front
   of the pilotis, sparse and irregular — a wooded campus, not a city.
6. THE GLIDER: a small sharp flat silhouette of a high-wing glider climbing to the
   upper right, well above the building, trailing a DOTTED ICE-BLUE path that
   begins low on the left BELOW the gold line, crosses it and rises: the path IS a
   grade curve, and the crossing is marked with a tiny hollow ring.

Overlaid at the top left of the illustration: a plain circular seal placeholder
32px wide, and beside it "SAS" in small uppercase letterspaced white with
"Colégio Ari de Sá · Turma ITA/IME" beneath in dim blue 10px.

Centred over the lower third of the illustration, the headline in heavy condensed
grotesque, white, two lines, 40px: "Todo dia acima da linha".

LOWER 45% — a raised surface panel with an 18px radius overlapping the bottom of
the illustration by about 24px, so the illustration runs behind it. Inside it,
stacked:

- the returning-student hook: a coral flame icon with "Sua sequência de 12 dias
  está esperando" in white 15px, and beneath it a chain of seven small rounded
  squares, six filled coral and the seventh an unlit hollow outline, with a tiny
  dim uppercase caption "VOLTE HOJE PARA NÃO PERDER";
- two stacked fields, each a dark inset with a 1px #1B2B57 edge and 16px text,
  with small uppercase labels above — "MATRÍCULA" and "SENHA", the second with an
  eye icon at its right;
- a full-width tall gold button labelled "ENTRAR" in bold uppercase letterspaced;
- a full-width secondary button, transparent with a 1px ice-blue border and no
  bottom edge, labelled "Entrar com o Canvas", with a small circular glyph at its
  left;
- two quiet dim links side by side separated by a middot: "Primeiro acesso" ·
  "Esqueci a senha";
- three tiny readings divided by vertical hairlines, dim uppercase labels with
  white values: "TURMA ITA/IME / 900 ALUNOS" · "BANCO / 2.693 QUESTÕES" ·
  "SIMULADOS / 5 CICLOS".
```

### Hoje · desktop

```
A single desktop web app screen, 1440x900, as a flat UI design mockup — no browser
chrome, no window frame, no laptop, no perspective, no reflections. Straight on,
edge to edge, filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Behind everything an extremely faint square grid
in #0E1A38, barely perceptible. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its role
and for nothing else:
- ACTION, the thing you press: lit gold #FFCE3A, near-black #050A18 label, with a
  4px hard bottom edge in #C79A16
- VALUE, XP and anything earned, and the cut line: lit gold #FFCE3A
- DATA, bars above the cut, progress fills, the active navigation item: electric
  blue #2F6BFF, with ice blue #7FB6FF as its lighter register
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, a distance tag or a value below the cut, and nothing else: coral #FF6B4A
- MAGNITUDE, every large numeral: white #FFFFFF
No green anywhere. No traffic-light palette. No colour outside this list.

NEON TREATMENT, with restraint: key strokes — the cut line, rings, the active
navigation underline — are thin neon tubes, a bright core with a tight halo no
wider than 4px. Filled surfaces, buttons and text have NO glow. Anything empty,
locked or below a threshold is drawn UNLIT: a dark hollow outline, like a
burnt-out segment of a sign.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur.
Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Small uppercase letterspaced
labels for eyebrows. All figures tabular.

DESKTOP LAYOUT — three columns, and the same content as the mobile screen
redistributed rather than stretched. Never a dense dashboard; the centre column
keeps mobile's generous rhythm.

- LEFT RAIL, 240px, a raised surface running the full height: at the top a plain
  circular brand mark with "SAS" beside it in small uppercase letterspaced, and
  "Área do estudante" beneath in dim 11px. Then four navigation items stacked
  vertically, each a full-width row with a thin line icon and a label at 15px:
  Hoje, Estudar, Provas, Jornada. The active item is a filled DATA-coloured row
  with near-black label; the others are transparent with dim labels. At the
  bottom of the rail, a row with the "RF" avatar, the name "Rafael F." and a
  small gear icon.
- CENTRE COLUMN, 640px wide, centred in the remaining space, holding the screen's
  main content with 32px gaps between blocks.
- RIGHT COLUMN, 320px, a stack of small persistent widgets present on EVERY
  screen: a streak card (coral flame, "12", the label "SEQUÊNCIA", and the chain
  of seven squares); an XP card (gold token, "1.240", "XP"); a weekly goal card
  ("META DA SEMANA", "34/50", a track filled 68% in DATA colour); and a league
  card ("Liga Ouro", "6º de 34", a gold ACTION chip reading "VER").

There is NO bottom navigation on desktop.

THE SCREEN — "Hoje". The active rail item is "Hoje".

CENTRE COLUMN, top to bottom:

HERO BLOCK, a raised surface, the dominant element of the page: a small uppercase
eyebrow in DATA colour "MISSÃO DE HOJE"; below it, very large in MAGNITUDE
colour, 56px on one line, "12 questões de Termodinâmica"; below that one quieter
line "Cai em 7% da prova do ITA. Você acerta 41%."; then an ACTION button 280px
wide labelled "COMEÇAR" in bold uppercase letterspaced.

"ONDE VOCÊ ESTÁ" block, a raised surface with that eyebrow: five vertical bars
labelled MAT FÍS QUÍ POR ING, reaching 6,8 — 7,4 — 3,2 — 5,9 — 4,6 on a 0 to 10
axis, each value printed in MAGNITUDE colour above its bar. Four bars are solid
DATA colour. A single VALUE horizontal line crosses all five at 4,0, labelled
"CORTE" at its right end. The QUÍ bar is HOLLOW, ends clearly below that line,
and carries a small ALERT tag reading "−0,8" beneath it.

"O QUE SEU CICLO MOSTRA" block, a raised surface with that eyebrow: three short
bullet lines of body copy, each preceded by a small DATA-coloured square marker.
```

### Estudar · desktop

```
A single desktop web app screen, 1440x900, as a flat UI design mockup — no browser
chrome, no window frame, no laptop, no perspective, no reflections. Straight on,
edge to edge, filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Behind everything an extremely faint square grid
in #0E1A38, barely perceptible. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its role
and for nothing else:
- ACTION, the thing you press: lit gold #FFCE3A, near-black #050A18 label, with a
  4px hard bottom edge in #C79A16
- VALUE, XP and anything earned, and the cut line: lit gold #FFCE3A
- DATA, bars above the cut, progress fills, the active navigation item: electric
  blue #2F6BFF, with ice blue #7FB6FF as its lighter register
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, a distance tag or a value below the cut, and nothing else: coral #FF6B4A
- MAGNITUDE, every large numeral: white #FFFFFF
No green anywhere. No traffic-light palette. No colour outside this list.

NEON TREATMENT, with restraint: key strokes — the cut line, rings, the active
navigation underline — are thin neon tubes, a bright core with a tight halo no
wider than 4px. Filled surfaces, buttons and text have NO glow. Anything empty,
locked or below a threshold is drawn UNLIT: a dark hollow outline, like a
burnt-out segment of a sign.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur.
Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Small uppercase letterspaced
labels for eyebrows. All figures tabular.

DESKTOP LAYOUT — three columns, and the same content as the mobile screen
redistributed rather than stretched. Never a dense dashboard; the centre column
keeps mobile's generous rhythm.

- LEFT RAIL, 240px, a raised surface running the full height: at the top a plain
  circular brand mark with "SAS" beside it in small uppercase letterspaced, and
  "Área do estudante" beneath in dim 11px. Then four navigation items stacked
  vertically, each a full-width row with a thin line icon and a label at 15px:
  Hoje, Estudar, Provas, Jornada. The active item is a filled DATA-coloured row
  with near-black label; the others are transparent with dim labels. At the
  bottom of the rail, a row with the "RF" avatar, the name "Rafael F." and a
  small gear icon.
- CENTRE COLUMN, 640px wide, centred in the remaining space, holding the screen's
  main content with 32px gaps between blocks.
- RIGHT COLUMN, 320px, a stack of small persistent widgets present on EVERY
  screen: a streak card (coral flame, "12", the label "SEQUÊNCIA", and the chain
  of seven squares); an XP card (gold token, "1.240", "XP"); a weekly goal card
  ("META DA SEMANA", "34/50", a track filled 68% in DATA colour); and a league
  card ("Liga Ouro", "6º de 34", a gold ACTION chip reading "VER").

There is NO bottom navigation on desktop.

THE SCREEN — "Estudar". The active rail item is "Estudar".

CENTRE COLUMN, top to bottom:

Page title "Estudar" in condensed grotesque 32px, MAGNITUDE colour.

SEGMENTED CONTROL, three equal segments in a single rounded track: "Prioridade",
"Meus erros", "Banco". "Prioridade" is selected — a filled DATA-colour segment
with near-black label; the other two unlit with dim labels.

COVERAGE STRIP: a full-width strip with a 1px hairline border and no fill, a small
uppercase label "COBERTURA" and one quiet line: "Cobre Matemática, Física e
Química. Português, Inglês e Redação ainda não."

RANKED LIST of five topics on a raised surface, rows separated by hairlines, with
a single vertical hairline down the left edge connecting the rank numbers. Each
row: a two-digit rank in small uppercase; the topic name in condensed grotesque
19px in MAGNITUDE colour; below it one quiet line; and at the right a dual
reading — a horizontal track where a gold VALUE tick marks the topic's weight in
the exam and a solid DATA fill shows the student's accuracy, the span between
them unlit. Rows 01 and 02 carry a small gold ACTION chip reading "TREINAR".

Row 01 — "Termodinâmica" / "Cai em 7% da prova. Você acerta 41%."
Row 02 — "Estequiometria" / "Cai em 6% da prova. Você acerta 38%."
Row 03 — "Análise combinatória" / "Cai em 5% da prova. Você acerta 52%."
Row 04 — "Eletrostática" / "Cai em 5% da prova. Você acerta 64%."
Row 05 — "Geometria analítica" / "Cai em 4% da prova. Você acerta 70%."
```

### Provas · desktop

```
A single desktop web app screen, 1440x900, as a flat UI design mockup — no browser
chrome, no window frame, no laptop, no perspective, no reflections. Straight on,
edge to edge, filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Behind everything an extremely faint square grid
in #0E1A38, barely perceptible. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its role
and for nothing else:
- ACTION, the thing you press: lit gold #FFCE3A, near-black #050A18 label, with a
  4px hard bottom edge in #C79A16
- VALUE, XP and anything earned, and the cut line: lit gold #FFCE3A
- DATA, bars above the cut, progress fills, the active navigation item: electric
  blue #2F6BFF, with ice blue #7FB6FF as its lighter register
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, a distance tag or a value below the cut, and nothing else: coral #FF6B4A
- MAGNITUDE, every large numeral: white #FFFFFF
No green anywhere. No traffic-light palette. No colour outside this list.

NEON TREATMENT, with restraint: key strokes — the cut line, rings, the active
navigation underline — are thin neon tubes, a bright core with a tight halo no
wider than 4px. Filled surfaces, buttons and text have NO glow. Anything empty,
locked or below a threshold is drawn UNLIT: a dark hollow outline, like a
burnt-out segment of a sign.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur.
Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Small uppercase letterspaced
labels for eyebrows. All figures tabular.

DESKTOP LAYOUT — three columns, and the same content as the mobile screen
redistributed rather than stretched. Never a dense dashboard; the centre column
keeps mobile's generous rhythm.

- LEFT RAIL, 240px, a raised surface running the full height: at the top a plain
  circular brand mark with "SAS" beside it in small uppercase letterspaced, and
  "Área do estudante" beneath in dim 11px. Then four navigation items stacked
  vertically, each a full-width row with a thin line icon and a label at 15px:
  Hoje, Estudar, Provas, Jornada. The active item is a filled DATA-coloured row
  with near-black label; the others are transparent with dim labels. At the
  bottom of the rail, a row with the "RF" avatar, the name "Rafael F." and a
  small gear icon.
- CENTRE COLUMN, 640px wide, centred in the remaining space, holding the screen's
  main content with 32px gaps between blocks.
- RIGHT COLUMN, 320px, a stack of small persistent widgets present on EVERY
  screen: a streak card (coral flame, "12", the label "SEQUÊNCIA", and the chain
  of seven squares); an XP card (gold token, "1.240", "XP"); a weekly goal card
  ("META DA SEMANA", "34/50", a track filled 68% in DATA colour); and a league
  card ("Liga Ouro", "6º de 34", a gold ACTION chip reading "VER").

There is NO bottom navigation on desktop.

THE SCREEN — "Provas". The active rail item is "Provas".

CENTRE COLUMN, top to bottom:

Page title "Provas" in condensed grotesque 32px, MAGNITUDE colour.

HERO CARD, a raised surface: eyebrow "ÚLTIMO SIMULADO"; the name "Ciclo 4 · ITA ·
P5" in condensed grotesque; a very large "6,4" in MAGNITUDE colour at 72px with a
small DATA-coloured upward triangle and "+0,7 vs. seu padrão" beside it; and to
the right, three compact readings divided by vertical hairlines, each a tiny
uppercase label above a value: "APLICADO / 18 AGO", "POSIÇÃO / 47 DE 312",
"PERCENTIL / 85".

HEATMAP on a raised surface, eyebrow "MATÉRIA POR CICLO": a grid of five rows by
five columns, rows labelled at the left in small uppercase MAT, FÍS, QUÍ, POR,
ING and columns labelled beneath as C1 to C5. Each cell is a rounded square filled
with DATA colour whose intensity encodes the grade — strongest cells fully
saturated electric blue, weakest a very dim blue. Cells below the cut are UNLIT:
a dark hollow outline with a thin coral edge; in the QUÍ row, C4 and C5 are unlit.
A tiny dim legend beneath: "0 ——— 10   ▢ ABAIXO DO CORTE".

SIMULADO LIST on a raised surface, eyebrow "TODOS OS SIMULADOS": four rows
separated by hairlines, each with the label in condensed grotesque at the left,
the date in dim small uppercase beneath, the grade in MAGNITUDE colour at the
right, and under it a tiny delta with a triangle in DATA colour for a rise and
coral for a fall.
"Ciclo 4 · ITA · P5" / "18 AGO" / 6,4 / ▲ 0,7
"Ciclo 4 · IME · P4" / "04 AGO" / 5,8 / ▲ 0,3
"Ciclo 3 · ITA · P3" / "12 JUL" / 5,5 / ▼ 0,2
"Ciclo 3 · IME · P2" / "28 JUN" / 5,7 / ▲ 1,1
```

### Jornada · desktop

```
A single desktop web app screen, 1440x900, as a flat UI design mockup — no browser
chrome, no window frame, no laptop, no perspective, no reflections. Straight on,
edge to edge, filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Behind everything an extremely faint square grid
in #0E1A38, barely perceptible. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION. Six roles, and a colour is used for its role
and for nothing else:
- ACTION, the thing you press: lit gold #FFCE3A, near-black #050A18 label, with a
  4px hard bottom edge in #C79A16
- VALUE, XP and anything earned, and the cut line: lit gold #FFCE3A
- DATA, bars above the cut, progress fills, the active navigation item: electric
  blue #2F6BFF, with ice blue #7FB6FF as its lighter register
- STREAK, the flame and the day chain: coral #FF6B4A
- ALERT, a distance tag or a value below the cut, and nothing else: coral #FF6B4A
- MAGNITUDE, every large numeral: white #FFFFFF
No green anywhere. No traffic-light palette. No colour outside this list.

NEON TREATMENT, with restraint: key strokes — the cut line, rings, the active
navigation underline — are thin neon tubes, a bright core with a tight halo no
wider than 4px. Filled surfaces, buttons and text have NO glow. Anything empty,
locked or below a threshold is drawn UNLIT: a dark hollow outline, like a
burnt-out segment of a sign.

Only buttons and tappable tiles carry the 4px hard bottom edge, with no blur.
Every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Small uppercase letterspaced
labels for eyebrows. All figures tabular.

DESKTOP LAYOUT — three columns, and the same content as the mobile screen
redistributed rather than stretched. Never a dense dashboard; the centre column
keeps mobile's generous rhythm.

- LEFT RAIL, 240px, a raised surface running the full height: at the top a plain
  circular brand mark with "SAS" beside it in small uppercase letterspaced, and
  "Área do estudante" beneath in dim 11px. Then four navigation items stacked
  vertically, each a full-width row with a thin line icon and a label at 15px:
  Hoje, Estudar, Provas, Jornada. The active item is a filled DATA-coloured row
  with near-black label; the others are transparent with dim labels. At the
  bottom of the rail, a row with the "RF" avatar, the name "Rafael F." and a
  small gear icon.
- CENTRE COLUMN, 640px wide, centred in the remaining space, holding the screen's
  main content with 32px gaps between blocks.
- RIGHT COLUMN, 320px, a stack of small persistent widgets present on EVERY
  screen: a streak card (coral flame, "12", the label "SEQUÊNCIA", and the chain
  of seven squares); an XP card (gold token, "1.240", "XP"); a weekly goal card
  ("META DA SEMANA", "34/50", a track filled 68% in DATA colour); and a league
  card ("Liga Ouro", "6º de 34", a gold ACTION chip reading "VER").

There is NO bottom navigation on desktop.

THE SCREEN — "Jornada". The active rail item is "Jornada".

CENTRE COLUMN, top to bottom:

Page title "Sua jornada" in condensed grotesque 32px, MAGNITUDE colour.

HERO CARD, a raised surface: eyebrow "ONDE VOCÊ ESTÁ"; three horizontal bands
stacked bottom to top as hairline outlines, labelled from bottom to top RISCO,
CINZENTA, TOP, with the RISCO band unlit. A solid DATA-coloured dot sits inside
CINZENTA with a hairline leader to a small label "VOCÊ". The boundary between
CINZENTA and TOP is a gold VALUE neon line labelled "CORTE 8,0" at its right end.
A vertical dimension line with arrowheads runs from the dot to that line with
"1,2" in a break in the middle. Beneath: "Faltam 1,2 em Química para sair da
cinzenta."

TRAJECTORY CHART on a raised surface, eyebrow "SUA TRAJETÓRIA": a wide line chart
with a 0 to 10 axis down the left. A gold VALUE neon line crosses at 4,0 labelled
"CORTE", the region below it unlit. A solid DATA-coloured polyline plots five
points labelled C1 to C5, starting below the gold line at C1, crossing between C2
and C3 — the crossing marked with a hollow ring and a hairline leader to a small
uppercase label "CRUZOU NO CICLO 3" — and rising to 6,4 at C5. A dim dashed line
shows the class average, with a tiny legend: "— VOCÊ    - - - MÉDIA DA TURMA".

ACHIEVEMENTS on a raised surface, eyebrow "CONQUISTAS": a row of four square
tiles. Three are lit with a DATA-coloured 1px edge, a thin line icon, a label and
a dim caption: "Cruzou o corte / CICLO 3", "3 semanas seguidas / CONQUISTADO",
"Primeiro 8,0 / FÍSICA · C4". The fourth is UNLIT: "50 questões / 34 DE 50", with
a thin track beneath filled 68% in DATA colour.

MESSAGE CARD at the bottom: a quiet raised surface with a large gold quotation
mark glyph at the left, eyebrow "DE QUEM JÁ PASSOU", a line in condensed grotesque
"Três aprovados no ITA contam como estudaram", and a dim text link "Ler".
```

### Login · desktop

```
A single desktop web app screen, 1440x900, as a flat UI design mockup — no browser
chrome, no window frame, no laptop, no perspective, no reflections. Straight on,
edge to edge, filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written.

TEMA — NOITE.

Ground: near-black blue #050A18. Raised surfaces #0C1530 with 18px corner radius
and a 1px luminous edge #1B2B57. Secondary text #6E85B8, kept deliberately dim.

COLOUR IS ROLE, NEVER DECORATION: lit gold #FFCE3A is the primary button, the cut
line and anything earned; electric blue #2F6BFF with ice blue #7FB6FF is data and
state; coral #FF6B4A is the streak; white #FFFFFF is every large numeral and
headline. No green anywhere. No colour outside this list.

Type: a heavy condensed grotesque for headlines, up to 56px, and a rounded humanist
sans for body copy at 15 to 17px. Small uppercase letterspaced labels at 10px.

Only buttons carry a 4px hard bottom edge, with no blur. Every other surface is
flat. Nothing in this image glows.

⚠️ NO REAL LOGOS, NO CREST, NO WORDMARK, NO MILITARY INSIGNIA of any institution.
The architecture below is an evocation of mid-century Brazilian modernist campus
design, not a portrait of a specific protected building. Any emblem is an abstract
placeholder: a plain circular seal with a laurel ring and no legible text.

LEFT COLUMN, 60% of the width — one flat vector illustration filling it edge to
edge, built only from flat shapes. No photography, no 3D, no gradients except the
sky bands. The wide format lets the horizontal architecture breathe, and it should.

The scene, from back to front:
1. SKY: a dawn sky in four stacked horizontal bands of deep blue, darkest at the
   top and lightest at the horizon. A sparse scatter of small stars in the upper
   bands, and one constellation of five stars joined by hairlines.
2. HILLS: low rolling hills across the horizon in a single darker blue silhouette
   — the Vale do Paraíba.
3. THE CUT LINE: a single continuous LIT GOLD horizontal line lying exactly on the
   horizon, labelled at its right end in tiny uppercase "CORTE". This is the same
   gold line that appears on every other screen of the product.
4. THE BUILDING, the centrepiece, which must read as unmistakably a mid-century
   Brazilian engineering campus: a LONG, LOW, STRICTLY HORIZONTAL modernist block
   on slender PILOTIS — thin columns lifting the volume off the ground with the
   landscape visible through the gap beneath. A flat dark silhouette in #0A1428
   with its façade rendered as a REGULAR LATTICE OF SMALL SQUARES, a cobogó
   breeze-block screen, a few of whose squares are lit from within in warm ice
   blue as if rooms were awake before dawn. The block runs off both edges, and its
   roofline sits just BELOW the gold line so the gold reads as the horizon behind
   it.
   ⚠️ The lattice must use exactly the same square grid rhythm as the faint
   background grid used throughout the rest of the app.
   In this wide format, add a second, shorter modernist volume set back and to the
   left, at a right angle to the first, so the two together suggest a campus plan
   rather than a single building.
5. TREES: a row of flat rounded tree silhouettes in an even darker blue in front
   of the pilotis, sparse and irregular — a wooded campus, not a city.
6. THE GLIDER: a small sharp flat silhouette of a high-wing glider climbing to the
   upper right, well above the building, trailing a DOTTED ICE-BLUE path that
   begins low on the left BELOW the gold line, crosses it and rises: the path IS a
   grade curve, and the crossing is marked with a tiny hollow ring.

Overlaid at the top left: a plain circular seal placeholder 40px wide with "SAS"
beside it in small uppercase letterspaced white and "Colégio Ari de Sá · Turma
ITA/IME" beneath in dim blue. Overlaid across the lower third, the headline in heavy
condensed grotesque white on two lines at 56px: "Todo dia acima da linha".

RIGHT COLUMN, 40% of the width, the ground colour, with the form centred
vertically in a 360px column:

- the returning-student hook: a coral flame icon with "Sua sequência de 12 dias
  está esperando" in white 15px, and beneath it a chain of seven small rounded
  squares, six filled coral and the seventh an unlit hollow outline, with a tiny
  dim uppercase caption "VOLTE HOJE PARA NÃO PERDER";
- two stacked fields, each a dark inset with a 1px #1B2B57 edge and 16px text,
  with small uppercase labels above — "MATRÍCULA" and "SENHA", the second with an
  eye icon at its right;
- a full-width tall gold button labelled "ENTRAR" in bold uppercase letterspaced;
- a full-width secondary button, transparent with a 1px ice-blue border and no
  bottom edge, labelled "Entrar com o Canvas", with a small circular glyph at its
  left;
- two quiet dim links side by side separated by a middot: "Primeiro acesso" ·
  "Esqueci a senha";
- three tiny readings divided by vertical hairlines, dim uppercase labels with
  white values: "TURMA ITA/IME / 900 ALUNOS" · "BANCO / 2.693 QUESTÕES" ·
  "SIMULADOS / 5 CICLOS".
```

---

## Paletas — as quatro exploradas (histórico)

A A1 ganhou. O que segue em aberto é a paleta, e a correção que vale nas três:
**barra acima do corte é neutra; só a que está abaixo ganha cor de alerta.** O
verde-e-vermelho da primeira geração é semáforo, e é o que mais puxa a idade
para baixo.

E "ofensiva" saiu: é a tradução brasileira do Duolingo. Virou **"Sequência"**.

### P1 · Ari claro — azul e branco

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise, no gradient.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — bright, blue and white, the school's own colours. A game, but a clean
and grown-up one.

Ground: white #FFFFFF with inset panels #EFF4FC, 16px corner radius and a 2px
border in #DCE6F7. Generous padding. Confident and legible, never austere.

Colour is state and never decoration, one meaning per hue and used nowhere else:
brand blue #1B3F8B is the primary action; gold #F2C94C is XP and anything earned;
coral #FF6B4A is the daily streak flame AND the only alert colour. Bars above the
cut line are brand blue #2E6BE6; only a bar BELOW the cut line is coral. Never
green, never a traffic-light palette. Text #0F1B33, secondary #5C6883 kept muted
so the colours dominate.

The primary button is solid #1B3F8B with white label and a 4px hard bottom edge in
#12275A, no blur — a physical key waiting to be pressed. Only buttons and tappable
tiles get that bottom edge; every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 44 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Button labels uppercase, bold,
letterspaced. All figures tabular.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a flame icon with "12" beside it in heavy numerals and
a tiny uppercase label "SEQUÊNCIA" beneath; at the centre-right a small token with
"1.240" and the label "XP"; at the far right a circular avatar containing "RF".

HERO BLOCK, the dominant element: a small uppercase eyebrow "MISSÃO DE HOJE";
below it, very large, "12 questões de Termodinâmica"; below that one quieter line
"Cai em 7% da prova do ITA. Você acerta 41%."; then a full-width tall primary
button labelled "COMEÇAR".

STREAK CHAIN under the hero: seven small rounded squares, labelled S T Q Q S S D
beneath. Five filled coral #FF6B4A, the sixth is today and carries a gold
ring, the seventh is an empty outline.

WEEKLY GOAL: uppercase label "META DA SEMANA" with "34/50" at the right end, and
beneath it a rounded track filled 68% in gold #F2C94C.

"ONDE VOCÊ ESTÁ", below a divider: five vertical bars labelled MAT FÍS QUÍ POR
ING, reaching 6,8 — 7,4 — 3,2 — 5,9 — 4,6 on a 0 to 10 axis. Four bars are
brand blue #2E6BE6. A single gold #F2C94C horizontal line crosses all five at 4,0,
labelled "CORTE" at its right end. The QUÍ bar is the alert colour, ends clearly
below that line, and carries a small tag reading "−0,8".

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Hoje" is active, marked in brand blue.
```

### P2 · Cobalto e lima — recomendada

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise, no gradient.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.
Colours are flat, with no glow and no bloom.

DIRECTION — deep cobalt with a single electric accent. Reads as twenty years old,
not thirteen: almost no colour, and the one colour there is arrives loud.

Ground: deep cobalt #0B1E5B, edge to edge. Raised surfaces #14307A with 18px
corner radius and no border. Big shapes, big numbers, lots of contrast.

ONE electric accent carries the whole screen: lime #C6F24E. It is the primary
button, the XP figure and the weekly progress fill — and it appears NOWHERE else.
Gold #F2C94C is demoted to earned things only, a small token beside the XP. Coral
#FF6B6B is the only alert colour: the streak flame and any value below the cut
line. Bars above the cut are pale blue #9CC4FF. Never green, never a traffic-light
palette, never more than these four hues. Text #FFFFFF, secondary #9FB3E0 kept
deliberately muted.

The primary button is solid lime #C6F24E with near-black #0B1E5B label text and a
4px hard bottom edge in #97BB2E, no blur — a physical key. Only buttons and
tappable tiles get that bottom edge; every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 44 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Button labels uppercase, bold,
letterspaced. All figures tabular.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a flame icon with "12" beside it in heavy numerals and
a tiny uppercase label "SEQUÊNCIA" beneath; at the centre-right a small token with
"1.240" and the label "XP"; at the far right a circular avatar containing "RF".

HERO BLOCK, the dominant element: a small uppercase eyebrow "MISSÃO DE HOJE";
below it, very large, "12 questões de Termodinâmica"; below that one quieter line
"Cai em 7% da prova do ITA. Você acerta 41%."; then a full-width tall primary
button labelled "COMEÇAR".

STREAK CHAIN under the hero: seven small rounded squares, labelled S T Q Q S S D
beneath. Five filled coral #FF6B6B, the sixth is today and carries a lime
ring, the seventh is an empty outline.

WEEKLY GOAL: uppercase label "META DA SEMANA" with "34/50" at the right end, and
beneath it a rounded track filled 68% in lime #C6F24E.

"ONDE VOCÊ ESTÁ", below a divider: five vertical bars labelled MAT FÍS QUÍ POR
ING, reaching 6,8 — 7,4 — 3,2 — 5,9 — 4,6 on a 0 to 10 axis. Four bars are
pale blue #9CC4FF. A single gold #F2C94C horizontal line crosses all five at 4,0,
labelled "CORTE" at its right end. The QUÍ bar is the alert colour, ends clearly
below that line, and carries a small tag reading "−0,8".

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Hoje" is active, marked in lime.
```

### P3 · Neon noturno

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise, no gradient.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.
Colours are flat and lit like an LED segment — saturated, but no bloom and no
outer glow.

DIRECTION — night neon, in the register of an esports interface. The youngest and
loudest of the options.

Ground: near-black blue #05070F. Raised surfaces #0D1220 with 16px corner radius
and a 1px luminous edge in #1E2942.

Colour is state and never decoration: electric cyan #22D3EE is the primary action;
lime #A3E635 is XP and anything earned; amber #FBBF24 is the daily streak flame;
magenta #F472B6 is the league and nothing else; hot coral #FB5D5D is the only
alert colour. Bars above the cut line are cool grey-blue #52719E; only a bar below
the cut line is coral. Never a traffic-light palette. Text #F8FAFC, secondary
#7C8AA5 kept deliberately muted so the neon dominates.

The primary button is solid cyan #22D3EE with near-black #05070F label text and a
4px hard bottom edge in #0E9BB4, no blur. Only buttons and tappable tiles get that
edge; every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 44 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Button labels uppercase, bold,
letterspaced. All figures tabular.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a flame icon with "12" beside it in heavy numerals and
a tiny uppercase label "SEQUÊNCIA" beneath; at the centre-right a small token with
"1.240" and the label "XP"; at the far right a circular avatar containing "RF".

HERO BLOCK, the dominant element: a small uppercase eyebrow "MISSÃO DE HOJE";
below it, very large, "12 questões de Termodinâmica"; below that one quieter line
"Cai em 7% da prova do ITA. Você acerta 41%."; then a full-width tall primary
button labelled "COMEÇAR".

STREAK CHAIN under the hero: seven small rounded squares, labelled S T Q Q S S D
beneath. Five filled amber #FBBF24, the sixth is today and carries a cyan
ring, the seventh is an empty outline.

WEEKLY GOAL: uppercase label "META DA SEMANA" with "34/50" at the right end, and
beneath it a rounded track filled 68% in lime #A3E635.

"ONDE VOCÊ ESTÁ", below a divider: five vertical bars labelled MAT FÍS QUÍ POR
ING, reaching 6,8 — 7,4 — 3,2 — 5,9 — 4,6 on a 0 to 10 axis. Four bars are
cool grey-blue #52719E. A single cyan #22D3EE horizontal line crosses all five at 4,0,
labelled "CORTE" at its right end. The QUÍ bar is the alert colour, ends clearly
below that line, and carries a small tag reading "−0,8".

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Hoje" is active, marked in cyan.
```

### P4 · Neon do Ari — azul, dourado e branco

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — night neon built entirely on the school's own colours: blues, lit
gold and white. Electric and young, but it is unmistakably this school and not a
generic synthwave app.

Ground: near-black blue #050A18, edge to edge. Raised surfaces #0C1530 with 18px
corner radius and a 1px luminous edge in #1B2B57. Behind everything, an extremely
faint square grid in #0E1A38 — barely perceptible, giving the dark ground depth
without becoming a texture.

THREE COLOURS DO ALL THE WORK, and each has exactly one job:
- LIT GOLD #FFCE3A — value. The primary button and the XP figure, and nothing
  else. Its darker shade for the button's bottom edge is #C79A16.
- ELECTRIC BLUE #2F6BFF, with ice blue #7FB6FF as its lighter register — state
  and data. Progress fills, bars, the active navigation item, rings.
- WHITE #FFFFFF — magnitude. Every large numeral and headline is white, which
  makes it the brightest thing on screen and gives the whole layout its lit
  quality. Secondary text is #6E85B8 and kept deliberately dim.
A single warm alert, coral #FF6B4A, is allowed on ONE tag only, nowhere else.
No green, no magenta, no cyan, no traffic-light palette.

NEON TREATMENT, applied with restraint: key strokes — the cut line, the ring
around today, the active nav underline — are drawn as thin neon tubes, a bright
core with a tight coloured halo no more than 4px wide. Filled surfaces, buttons
and text have NO glow at all. Anything that is inactive or below a threshold is
drawn UNLIT: a dark hollow outline, as if that segment of the sign has burnt out.

The primary button is solid lit gold #FFCE3A with near-black #050A18 label text
and a 4px hard bottom edge in #C79A16, no blur — a physical key waiting to be
pressed. Only buttons and tappable tiles get that bottom edge; every other
surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 44 to 64px in white,
and a rounded humanist sans for body copy at 15 to 17px. Button labels uppercase,
bold, letterspaced. All figures tabular.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a gold flame icon with "12" beside it in large white
numerals and a tiny uppercase label "SEQUÊNCIA" beneath in dim blue; at the
centre-right a small gold token with "1.240" in gold and the label "XP"; at the
far right a circular avatar with an electric blue ring, containing "RF".

HERO BLOCK, the dominant element of the screen: a small uppercase eyebrow in ice
blue "MISSÃO DE HOJE"; below it, very large and white, "12 questões de
Termodinâmica"; below that one quieter line in dim blue "Cai em 7% da prova do
ITA. Você acerta 41%."; then a full-width tall gold button labelled "COMEÇAR".

STREAK CHAIN under the hero: seven small rounded squares, labelled S T Q Q S S D
beneath in dim blue. Five are filled electric blue and clearly lit; the sixth is
today, filled gold with a thin gold neon ring around it; the seventh is unlit —
a dark hollow outline.

WEEKLY GOAL: uppercase label "META DA SEMANA" in ice blue with "34/50" in white at
the right end, and beneath it a rounded track, unlit dark for the remainder and
filled 68% in electric blue.

"ONDE VOCÊ ESTÁ", below a divider: five vertical bars labelled MAT FÍS QUÍ POR ING
in dim blue, reaching 6,8 — 7,4 — 3,2 — 5,9 — 4,6 on a 0 to 10 axis, with the
value printed in white above each bar. Four bars are lit electric blue with an ice
blue top edge. A single gold neon line crosses all five at 4,0, labelled "CORTE"
in gold at its right end. The QUÍ bar is UNLIT — a dark hollow outline — ends
clearly below the gold line, and carries a small coral tag reading "−0,8".

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Plano,
Liga, Jornada. "Hoje" is active, its icon and label in electric blue with a short
neon underline beneath; the other three are dim and unlit.
```

---

## A1 · Hoje — Navy do Ari, jogo cheio

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatars are a
plain circle with two letters inside — never a photograph of a person.

DIRECTION — "Navy do Ari", full game energy on the school's own colours.

Ground: deep navy #0A1836, edge to edge. Raised surfaces #12244A with 16px
corner radius. This is a saturated, high-energy game interface — big lit
numbers, filled bars, thick shapes. NOT a dashboard, NOT a spreadsheet.

Colour is state and never decoration, each hue used for exactly one meaning and
nowhere else: gold #F2C94C is XP, currency and anything earned; signal green
#2BD07A is correct and above the cut; orange #FF8A2B is the streak flame only;
red #FF4D5E is wrong and below the cut. Text is #FFFFFF, secondary #8FA3C8 and
deliberately muted so the coloured game elements dominate.

Buttons are the signature: a solid gold #F2C94C block with a 4px hard bottom
edge in darker gold #C9A32C and no blur — a physical key waiting to be pressed.
Only buttons and answer tiles get that bottom edge; every other surface is flat.

Type: a heavy condensed grotesque for numbers and headlines, 44 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Button labels are uppercase,
bold, letterspaced 0.8px. All figures tabular.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a flame icon with "12" beside it in heavy numerals
and a tiny mono uppercase label "OFENSIVA" beneath; at the centre-right a small
gold token shape with "1.240" and the mono label "XP"; at the far right a
circular avatar containing "RF".

HERO BLOCK, the dominant element of the screen: a small uppercase eyebrow
"MISSÃO DE HOJE"; below it, very large, "12 questões de Termodinâmica"; below
that one line of quieter body copy "Cai em 7% da prova do ITA. Você acerta 41%.";
and below that a full-width primary button, tall, label "COMEÇAR" in bold
uppercase with wide letterspacing.

STREAK CHAIN directly under the hero: seven small rounded squares in a row, one
per weekday, labelled S T Q Q S S D in tiny type beneath. Five are filled solid,
the sixth is the current day and carries a ring around it, the seventh is empty.

WEEKLY GOAL: a mono uppercase label "META DA SEMANA" with "34/50" at the right
end, and beneath it a rounded progress track filled 68%.

"ONDE VOCÊ ESTÁ" section, compact, below a divider: five short vertical bars
labelled in small uppercase MAT FÍS QUÍ POR ING, reaching 6,8 — 7,4 — 3,2 — 5,9
— 4,6 on a 0 to 10 scale. A single gold horizontal line crosses all five bars at
4,0, labelled "CORTE" at its right end. The QUÍ bar clearly ends below that gold
line and carries a small tag reading "−0,8".

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Hoje" is the active item.
```

---

## A2 · Hoje — Duolingo puro

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatars are a
plain circle with two letters inside — never a photograph of a person.

DIRECTION — bright, rounded, unmistakably a game, in the Duolingo register.

Ground: pure white #FFFFFF with #F7F7F7 inset panels. Everything has a 12px
corner radius and a 2px solid border in #E5E5E5. Generous 24px padding.
Cheerful, high-saturation, friendly, zero austerity.

Colour is state and never decoration: primary green #58CC02 with its 4px bottom
edge in #46A302; red #FF4B4B for wrong; orange #FF9600 for the streak flame;
yellow #FFC800 for XP; blue #1CB0F6 for information; purple #CE82FF for the
league. Text #4B4B4B, secondary #777777 kept deliberately muted so the colours
dominate.

Buttons are solid green with a 4px hard bottom edge in the darker green, no
blur, label uppercase bold letterspaced 0.8px. Only buttons and answer tiles get
that edge; other surfaces are flat with the 2px border.

Type: a heavy rounded sans throughout, headlines 32 to 48px, body 17px at weight
500. Chunky, soft-cornered letterforms.

One flat vector character appears at the right of the hero block, small: a
friendly paper aeroplane with simple dot eyes, drawn in flat shapes with no
gradient and no outline — a nod to the aeronautics school these students are
aiming for. No other illustration anywhere.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a flame icon with "12" beside it in heavy numerals
and a tiny mono uppercase label "OFENSIVA" beneath; at the centre-right a small
gold token shape with "1.240" and the mono label "XP"; at the far right a
circular avatar containing "RF".

HERO BLOCK, the dominant element of the screen: a small uppercase eyebrow
"MISSÃO DE HOJE"; below it, very large, "12 questões de Termodinâmica"; below
that one line of quieter body copy "Cai em 7% da prova do ITA. Você acerta 41%.";
and below that a full-width primary button, tall, label "COMEÇAR" in bold
uppercase with wide letterspacing.

STREAK CHAIN directly under the hero: seven small rounded squares in a row, one
per weekday, labelled S T Q Q S S D in tiny type beneath. Five are filled solid,
the sixth is the current day and carries a ring around it, the seventh is empty.

WEEKLY GOAL: a mono uppercase label "META DA SEMANA" with "34/50" at the right
end, and beneath it a rounded progress track filled 68%.

"ONDE VOCÊ ESTÁ" section, compact, below a divider: five short vertical bars
labelled in small uppercase MAT FÍS QUÍ POR ING, reaching 6,8 — 7,4 — 3,2 — 5,9
— 4,6 on a 0 to 10 scale. A single gold horizontal line crosses all five bars at
4,0, labelled "CORTE" at its right end. The QUÍ bar clearly ends below that gold
line and carries a small tag reading "−0,8".

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Hoje" is the active item.
```

---

## A3 · Hoje — Brilliant, jogo de raciocínio

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatars are a
plain circle with two letters inside — never a photograph of a person.

DIRECTION — a thinking game, in the Brilliant register: dark, elegant, and
confident rather than loud.

Ground: near-black #14161A. Surfaces #1E2126 with 14px corner radius and a 1px
#2C3037 edge. Generous negative space — far fewer elements per screen than a
typical app, each one given room. Quiet, precise, adult.

Restraint on colour: gold #F2C94C for anything earned and for the cut line, mint
#6EE7B7 for correct and above the line, and a muted #E0654F for below the line.
Nothing else is coloured. Text #F2F4F6, secondary #8A9199.

Buttons are flat with a 1px gold border and no fill, label in sentence case, not
uppercase — no 3D bottom edge anywhere. Depth comes from the surface layering,
not from mimicking physical keys.

A single geometric ornament sits behind the hero at very low contrast: a
tangram-like arrangement of flat triangles, barely visible, suggesting a puzzle.

Type: a large elegant grotesque, headlines 36 to 52px at a light-to-regular
weight, body 16px, labels in small caps rather than mono. Generous line height.
All figures tabular.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a flame icon with "12" beside it in heavy numerals
and a tiny mono uppercase label "OFENSIVA" beneath; at the centre-right a small
gold token shape with "1.240" and the mono label "XP"; at the far right a
circular avatar containing "RF".

HERO BLOCK, the dominant element of the screen: a small uppercase eyebrow
"MISSÃO DE HOJE"; below it, very large, "12 questões de Termodinâmica"; below
that one line of quieter body copy "Cai em 7% da prova do ITA. Você acerta 41%.";
and below that a full-width primary button, tall, label "COMEÇAR" in bold
uppercase with wide letterspacing.

STREAK CHAIN directly under the hero: seven small rounded squares in a row, one
per weekday, labelled S T Q Q S S D in tiny type beneath. Five are filled solid,
the sixth is the current day and carries a ring around it, the seventh is empty.

WEEKLY GOAL: a mono uppercase label "META DA SEMANA" with "34/50" at the right
end, and beneath it a rounded progress track filled 68%.

"ONDE VOCÊ ESTÁ" section, compact, below a divider: five short vertical bars
labelled in small uppercase MAT FÍS QUÍ POR ING, reaching 6,8 — 7,4 — 3,2 — 5,9
— 4,6 on a 0 to 10 scale. A single gold horizontal line crosses all five bars at
4,0, labelled "CORTE" at its right end. The QUÍ bar clearly ends below that gold
line and carries a small tag reading "−0,8".

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Hoje" is the active item.
```

---

## A4 · Hoje — Duolingo + instrumento

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatars are a
plain circle with two letters inside — never a photograph of a person.

DIRECTION — two worlds in one screen: the game on top, the instrument below,
and the contrast between them is the whole design.

TOP HALF, "the game": a dark slab #0A1836 bleeding to the screen edges, 20px
radius at its bottom corners only. Saturated and loud. Gold #F2C94C for XP and
anything earned, signal green #2BD07A for correct, orange #FF8A2B for the streak
flame, red #FF4D5E for wrong. Big lit numerals 48 to 64px. The primary button is
solid gold with a 4px hard bottom edge in #C9A32C.

BOTTOM HALF, "the instrument": warm paper white #FAFAF7. Disciplined and quiet.
1px hairline dividers #DDDDD6, ink #12181C, secondary #5A6670, and gold #F2C94C
allowed only for the cut line. No other colour, no shadows, no filled shapes —
outlines, hairlines and 45-degree hatching where a value falls below a
threshold. Type here is a condensed technical grotesque with small mono
uppercase labels, and distances are drawn as engineering dimension lines: a thin
line with arrowheads at both ends and the number set in a break in the middle.

The two halves meet at a hard horizontal edge with no gradient between them.

Type: heavy condensed grotesque for numbers in both halves, rounded humanist
sans for body copy on the dark half, technical grotesque on the paper half.

THE SCREEN — "Hoje", the daily loop.

TOP BAR, 56px: at the left a flame icon with "12" beside it in heavy numerals
and a tiny mono uppercase label "OFENSIVA" beneath; at the centre-right a small
gold token shape with "1.240" and the mono label "XP"; at the far right a
circular avatar containing "RF".

HERO BLOCK, the dominant element of the screen: a small uppercase eyebrow
"MISSÃO DE HOJE"; below it, very large, "12 questões de Termodinâmica"; below
that one line of quieter body copy "Cai em 7% da prova do ITA. Você acerta 41%.";
and below that a full-width primary button, tall, label "COMEÇAR" in bold
uppercase with wide letterspacing.

STREAK CHAIN directly under the hero: seven small rounded squares in a row, one
per weekday, labelled S T Q Q S S D in tiny type beneath. Five are filled solid,
the sixth is the current day and carries a ring around it, the seventh is empty.

WEEKLY GOAL: a mono uppercase label "META DA SEMANA" with "34/50" at the right
end, and beneath it a rounded progress track filled 68%.

"ONDE VOCÊ ESTÁ" section, compact, below a divider: five short vertical bars
labelled in small uppercase MAT FÍS QUÍ POR ING, reaching 6,8 — 7,4 — 3,2 — 5,9
— 4,6 on a 0 to 10 scale. A single gold horizontal line crosses all five bars at
4,0, labelled "CORTE" at its right end. The QUÍ bar clearly ends below that gold
line and carries a small tag reading "−0,8".

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Hoje" is the active item.

Place the top bar, hero block, streak chain and weekly goal inside the dark top
half; place the "ONDE VOCÊ ESTÁ" section on the paper bottom half, where the
gold cut line and the "−0,8" dimension line are drawn in the technical style.
```

---

## B1 · Liga anônima

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatars are a
plain circle with two letters inside — never a photograph of a person.

DIRECTION — "Navy do Ari", full game energy.

Ground: deep navy #0A1836, edge to edge. Raised surfaces #12244A with 16px
corner radius. Saturated, high-energy game interface — big lit numbers, filled
shapes, thick forms. NOT a dashboard.

Colour is state and never decoration: gold #F2C94C is XP, currency and anything
earned; signal green #2BD07A is promotion and correct; orange #FF8A2B is the
streak flame only; red #FF4D5E is relegation and wrong. Text #FFFFFF, secondary
#8FA3C8, deliberately muted so the coloured elements dominate.

Buttons are solid gold #F2C94C with a 4px hard bottom edge in darker gold
#C9A32C and no blur. Only buttons and tappable tiles get that bottom edge.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Labels uppercase and
letterspaced. All figures tabular.

THE SCREEN — the weekly league.

TOP BAR, 56px: a back chevron at the left, "Liga Ouro" centred, a circular
avatar containing "RF" at the right.

HEADER BLOCK: a large gold shield or badge shape, then "Liga Ouro" in large
type, then a mono uppercase line "TERMINA EM 2 DIAS · 34 PARTICIPANTES".

The list is divided into three zones, each introduced by a thin full-width
divider carrying a small uppercase label: "SOBE" in green at the top, then no
label for the middle group, then "DESCE" in red before the last group.

TEN ROWS. Each row has, left to right: the position number in heavy type; the
participant mark; and the week's XP at the right end in gold, right-aligned and
tabular. Positions 1 to 3 have their number replaced by a small medal shape.
Row 6 is the current user: it is visually lifted from the rest — a filled
surface behind it, a 2px gold left edge, and the label "VOCÊ".
XP values top to bottom: 2.410, 2.180, 1.995, 1.640, 1.502, 1.240, 1.180, 960,
740, 315.

Above row 5 there is a thin green line marking the promotion cut, and above row
9 a thin red line marking the relegation cut, each labelled in tiny uppercase.

Below the list, one line of body copy: "Faltam 262 XP para você subir."

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Liga" is the active item.

THE PARTICIPANT MARK IS ANONYMOUS AND THIS IS THE POINT OF THE SCREEN: no names
anywhere. Each participant is represented only by a small abstract geometric
glyph — a circle, a triangle, a hexagon, a diamond, a chevron, each in a
different flat colour drawn from a muted secondary set, all of them clearly
quieter than the gold. No nicknames, no initials, no letters, no faces. The only
row carrying a word is the user's, which reads "VOCÊ".
```

---

## B2 · Liga com apelido

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatars are a
plain circle with two letters inside — never a photograph of a person.

DIRECTION — "Navy do Ari", full game energy.

Ground: deep navy #0A1836, edge to edge. Raised surfaces #12244A with 16px
corner radius. Saturated, high-energy game interface — big lit numbers, filled
shapes, thick forms. NOT a dashboard.

Colour is state and never decoration: gold #F2C94C is XP, currency and anything
earned; signal green #2BD07A is promotion and correct; orange #FF8A2B is the
streak flame only; red #FF4D5E is relegation and wrong. Text #FFFFFF, secondary
#8FA3C8, deliberately muted so the coloured elements dominate.

Buttons are solid gold #F2C94C with a 4px hard bottom edge in darker gold
#C9A32C and no blur. Only buttons and tappable tiles get that bottom edge.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Labels uppercase and
letterspaced. All figures tabular.

THE SCREEN — the weekly league.

TOP BAR, 56px: a back chevron at the left, "Liga Ouro" centred, a circular
avatar containing "RF" at the right.

HEADER BLOCK: a large gold shield or badge shape, then "Liga Ouro" in large
type, then a mono uppercase line "TERMINA EM 2 DIAS · 34 PARTICIPANTES".

The list is divided into three zones, each introduced by a thin full-width
divider carrying a small uppercase label: "SOBE" in green at the top, then no
label for the middle group, then "DESCE" in red before the last group.

TEN ROWS. Each row has, left to right: the position number in heavy type; the
participant mark; and the week's XP at the right end in gold, right-aligned and
tabular. Positions 1 to 3 have their number replaced by a small medal shape.
Row 6 is the current user: it is visually lifted from the rest — a filled
surface behind it, a 2px gold left edge, and the label "VOCÊ".
XP values top to bottom: 2.410, 2.180, 1.995, 1.640, 1.502, 1.240, 1.180, 960,
740, 315.

Above row 5 there is a thin green line marking the promotion cut, and above row
9 a thin red line marking the relegation cut, each labelled in tiny uppercase.

Below the list, one line of body copy: "Faltam 262 XP para você subir."

BOTTOM NAVIGATION, four items with icons above labels: Hoje, Plano, Liga,
Jornada. "Liga" is the active item.

THE PARTICIPANT MARK IS A NICKNAME: each row shows a small circular avatar with
two letters inside next to a lowercase handle in medium weight. The handles, top
to bottom, are: turbina, delta7, mach_um, cadete_rj, ana.k, VOCÊ, jpp2007,
orbital, vetorial, quimico99. The user's row shows the word "VOCÊ" in place of a
handle.
```

---

## C1 · Celebração — cruzou o corte

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatars are a
plain circle with two letters inside — never a photograph of a person.

DIRECTION — "Navy do Ari", full game energy.

Ground: deep navy #0A1836, edge to edge. Raised surfaces #12244A with 16px
corner radius. Saturated, high-energy game interface — big lit numbers, filled
shapes, thick forms. NOT a dashboard.

Colour is state and never decoration: gold #F2C94C is XP, currency and anything
earned; signal green #2BD07A is promotion and correct; orange #FF8A2B is the
streak flame only; red #FF4D5E is relegation and wrong. Text #FFFFFF, secondary
#8FA3C8, deliberately muted so the coloured elements dominate.

Buttons are solid gold #F2C94C with a 4px hard bottom edge in darker gold
#C9A32C and no blur. Only buttons and tappable tiles get that bottom edge.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Labels uppercase and
letterspaced. All figures tabular.

THE SCREEN — a full-screen celebration, shown the moment the student crosses the
cut-off in a subject. There is no top bar and no bottom navigation: the moment
takes the whole screen.

Centred and stacked vertically, with generous space between the elements:

A burst of flat gold and green confetti radiating from the upper middle of the
screen — simple flat rectangles and triangles at varied angles, no gradients, no
glow, no realistic particles. Denser near the centre, sparse toward the edges.

Below it, the hero graphic: a horizontal gold line spanning most of the width,
labelled "CORTE 4,0" in small uppercase at its right end, with a solid green
marker sitting clearly ABOVE the line and a faint dashed ghost marker below it
showing where the student used to be. A vertical dimension line with arrowheads
connects the two, with "+1,4" set in a break in the middle.

Then, very large and centred: "VOCÊ CRUZOU O CORTE".
Under it, quieter: "Química · 4,2 no Ciclo 4".

Then a row of two reward chips side by side: one gold chip reading "+250 XP",
one green chip reading "PATENTE: CADETE" with a small chevron insignia.

Then a progress track showing the next rank: mono uppercase "PRÓXIMA PATENTE ·
ASPIRANTE" with the track filled 40% and "40%" at its right end.

At the bottom, a full-width solid gold button with a 4px hard bottom edge in
#C9A32C, label "CONTINUAR" in bold uppercase, and below it a quieter text-only
link reading "Ver a jornada".
```

---

## C2 · Sessão de questões — o loop diário

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
All interface text in Brazilian Portuguese, exactly as written. Avatars are a
plain circle with two letters inside — never a photograph of a person.

DIRECTION — "Navy do Ari", full game energy.

Ground: deep navy #0A1836, edge to edge. Raised surfaces #12244A with 16px
corner radius. Saturated, high-energy game interface — big lit numbers, filled
shapes, thick forms. NOT a dashboard.

Colour is state and never decoration: gold #F2C94C is XP, currency and anything
earned; signal green #2BD07A is promotion and correct; orange #FF8A2B is the
streak flame only; red #FF4D5E is relegation and wrong. Text #FFFFFF, secondary
#8FA3C8, deliberately muted so the coloured elements dominate.

Buttons are solid gold #F2C94C with a 4px hard bottom edge in darker gold
#C9A32C and no blur. Only buttons and tappable tiles get that bottom edge.

Type: a heavy condensed grotesque for numbers and headlines, 40 to 64px, and a
rounded humanist sans for body copy at 15 to 17px. Labels uppercase and
letterspaced. All figures tabular.

THE SCREEN — answering a question, the daily loop itself.

TOP BAR, 56px: a close X at the left; a wide rounded progress track filling most
of the width, filled 40% in green; and at the right a red heart icon with "4"
beside it.

Under the bar, a small mono uppercase line: "TERMODINÂMICA · QUESTÃO 5 DE 12 ·
IME 2016".

QUESTION BLOCK: a raised surface #12244A with 16px radius, containing two lines
of question text in regular weight, and beneath it a simple white-stroked
diagram of a piston in a cylinder with an arrow and the labels P, V and T — thin
strokes, no shading, no realism.

FOUR ANSWER TILES stacked vertically, each full width, 64px tall, 16px radius:
a surface a shade lighter than the ground, a 2px border, and a 4px hard bottom
edge — the same physical-key treatment as the buttons. Each tile carries a small
letter badge A, B, C, D at its left and the alternative text beside it.
Tile B is in the selected state: a green #2BD07A border, a faint green fill, and
its letter badge filled solid green.

At the bottom, a full-width solid green #2BD07A button with a 4px hard bottom
edge in #1FA05F, label "VERIFICAR" in bold uppercase letterspaced.

At the very bottom edge, a thin gold strip peeking upward with a tiny uppercase
label "+20 XP" — the reward waiting just off-screen. No bottom navigation on
this screen.
```

---
