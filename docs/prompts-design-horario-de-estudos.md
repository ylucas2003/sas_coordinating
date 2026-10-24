# Prompts de design — Horário de estudos · exploração de ideias

Companheiro do [42](42-plano-horario-de-estudos.md). O que está decidido lá
(o aluno monta tudo, privado, **sem XP, sem sequência e sem "cumpri"**) vale
aqui; o que está **em aberto** é a forma — e é isso que estes prompts exploram.

- ✅ **Ganhou a 2, a semana empilhada** (24/10). É a estrutura implementada — ver o
  [42 §4.2](42-plano-horario-de-estudos.md). Os prompts ficam como registro do que
  foi comparado e do porquê de as outras três terem saído.
- **Gerador:** Ideogram ou Imagen. Proporção **9:16** (o 6 é **16:10**).
- **Cada bloco é autossuficiente.** Copia inteiro, cola, gera.
- **1 a 4 são a MESMA tela, no mesmo tema (dia), em quatro estruturas.** É a
  comparação que decide a forma. Gere os quatro antes de olhar o resto.
- **5** é a folha de "adicionar bloco". **6, 7 e 8** são as peças ao redor: o
  cartão em Estudar, a linha na Hoje e o estado vazio.
- **O que julgar:** onde o olho cai primeiro; se dá para ver a semana inteira
  sem rolar; se parece **planilha** (o [24 §7](24-jornada-do-aluno.md) proíbe);
  e se dá vontade de montar o primeiro bloco. **Não a ortografia** — todo
  gerador erra letra.
- **Para ver a noite:** nos prompts 1 a 4, troque o parágrafo `GROUND AND COLOUR`
  pelo do bloco "Tema noite" no fim do arquivo. Os prompts 5 e 8 já estão na noite.

## Os dados de exemplo (os mesmos em todos)

Hoje é **terça, 17:40**. Próximo simulado: **P5, em 12 dias**.

| Dia | Blocos |
|---|---|
| Seg | 19:00–20:30 Termodinâmica |
| **Ter (hoje)** | 19:00–20:30 Estequiometria |
| Qua | 19:00–20:30 Análise combinatória |
| Qui | 18:00–19:00 Redação · 19:15–20:45 Revisar meus erros |
| Sex | 19:00–20:30 Eletrostática |
| Sáb | 14:00–16:00 Prova do ITA 2019 |
| Dom | 16:00–17:00 Inglês |

Total: **11h30 planejadas**.

---

## 1 · Dia a dia — faixa de sete dias e a lista do dia escolhido

A estrutura do plano. A semana cabe numa faixa; o detalhe de um dia por vez.

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — "day by day", the DAY theme of a study app for high-school seniors
preparing for engineering entrance exams. This is a PLANNING tool: calm, grown-up,
tactile like a game but never a game. It is a plan, never a record: NO checkmarks,
NO strikethrough, NO progress bar toward a goal, NO flame, NO trophy, NO green,
NO red anywhere inside the screen content.

GROUND AND COLOUR: ground white #FFFFFF with an extremely faint square grid, 24px
squares, navy at 4% opacity. Raised surfaces #F4F7FC, 18px corner radius, 2px
border #DCE6F7, never a drop shadow. Secondary text #5C6883, deliberately muted.
Colour is ROLE, never decoration: ACTION, the thing you press, navy #1B3F8B with
a white label and a 4px hard bottom edge #12275A, no blur; DATA, selected and
planned things, blue #2E6BE6; MAGNITUDE, every large numeral, near-black navy
#0F1B33. No other colour inside the content. Anything empty or unplanned is drawn
HOLLOW: an outline with no fill.

Type: extra-bold rounded geometric sans (Plus Jakarta Sans style), tight tracking,
for titles and numerals; regular weight for body at 15px. All figures tabular.
Eyebrow labels: 10px, bold, uppercase, letterspaced, in DATA colour.

THE SCREEN — "Horário de estudos", the weekly study schedule a student builds by
hand.

APP SHELL TOP BAR, 53px, not part of this screen's design: a small circular school
seal placeholder at the left; at the right a coral flame with "14", a small gold
token with "2.850", and a circular avatar with "BE".

HEADER on one line: a 44px square at the left holding a thin left chevron, and
beside it the title "Horário de estudos", extra-bold 28px, MAGNITUDE colour.

CONTEXT LINE under the header, two quiet facts at 13px in secondary text, one at
each end: "Próximo simulado: P5, em 12 dias" and "Semana: 11h30 planejadas". No bar,
no target.

DAY STRIP: seven equal tappable pills in one row, each at least 44px wide and 56px
tall, labelled SEG TER QUA QUI SEX SÁB DOM in 10px uppercase. TER is selected:
filled DATA blue with a white label, and a thin ring around it because it is today.
The other six are HOLLOW outlines. Under each label sit tiny dots counting that
day's blocks: one dot each, except QUI with two.

SECTION LABEL, DATA eyebrow: "TERÇA-FEIRA · HOJE".

BLOCK CARD, full width, raised surface. At the left the start time "19:00" very
large, 40px extra-bold MAGNITUDE, with "até 20:30" under it in secondary text. A thin
vertical divider, then the label "Estequiometria" 20px bold and under it a small
hollow pill "1h30". An eyebrow "PRÓXIMO · EM 1H20" in DATA colour at the top right
of the card. At the far right two small quiet line icons, a pencil and a trash can,
secondary colour, no fill.

Below the card one HOLLOW outlined slot, 56px tall, with centred muted text
"Nada mais para terça".

PRIMARY BUTTON, full width, fixed above the bottom navigation: ACTION navy, bold
uppercase letterspaced white label "ADICIONAR BLOCO", with the 4px hard bottom edge.

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Estudar" is active, in DATA colour with a 2px underline; the other
three are muted.
```

---

## 2 · Semana empilhada — os sete dias de uma vez, sem escolher

A aposta: **ver a semana inteira** vale mais que o detalhe de um dia. Custa rolagem.

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — "stacked week", the DAY theme of a study app for high-school seniors
preparing for engineering entrance exams. A PLANNING tool: calm, grown-up, tactile.
It is a plan, never a record: NO checkmarks, NO strikethrough, NO dimmed or "done"
blocks, NO progress bar, NO flame, NO trophy, NO green, NO red inside the content.

GROUND AND COLOUR: ground white #FFFFFF with an extremely faint square grid, 24px
squares, navy at 4% opacity. Raised surfaces #F4F7FC, 18px corner radius, 2px
border #DCE6F7, never a drop shadow. Secondary text #5C6883. Colour is ROLE: ACTION,
the thing you press, navy #1B3F8B with a white label and a 4px hard bottom edge
#12275A; DATA, today and planned things, blue #2E6BE6; MAGNITUDE, large numerals,
near-black navy #0F1B33. No other colour. Anything empty is drawn HOLLOW.

Type: extra-bold rounded geometric sans (Plus Jakarta Sans style) for titles and
numerals, regular for body. Tabular figures. Eyebrows 10px bold uppercase
letterspaced.

THE SCREEN — "Horário de estudos", all seven days stacked in one scrolling list.

APP SHELL TOP BAR, 53px: small circular seal placeholder at the left; at the right a
coral flame "14", a gold token "2.850", an avatar "BE".

HEADER on one line: a 44px square with a thin left chevron, then the title
"Horário de estudos", extra-bold 28px.
CONTEXT LINE, 13px secondary, one fact at each end: "Próximo simulado: P5, em 12 dias"
and "Semana: 11h30 planejadas".

THE LIST. Each day is a section. The section header is a row: the day name in
uppercase 12px bold at the left, the day total in secondary text at the right
("1h30"), and, at the far right, a 44px HOLLOW round button with a thin "+".
Under it, block rows as compact raised cards, 64px tall: the start time at the left
in 24px extra-bold MAGNITUDE, then the label in 16px bold, and under the label
"até 20:30 · 1h30" in 12px secondary.
Visible, top to bottom:
- "SEGUNDA" · "1h30" — "19:00" "Termodinâmica"
- "TERÇA · HOJE" · "1h30" — the day name in DATA colour with a small filled DATA dot
  before it; its card has a 2px DATA border and the eyebrow "PRÓXIMO"; "19:00"
  "Estequiometria"
- "QUARTA" · "1h30" — "19:00" "Análise combinatória"
- "QUINTA" · "2h30" — "18:00" "Redação", and the top of a second card "19:15"
  "Revisar meus erros" cut off by the bottom edge, as if the list continues.
No day is dimmed. Days with nothing would show one HOLLOW outlined row reading
"Sem bloco".

PRIMARY BUTTON, full width, fixed above the bottom navigation: ACTION navy, bold
uppercase letterspaced white label "ADICIONAR BLOCO", with the 4px hard bottom edge.

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Estudar" active in DATA colour with a 2px underline.
```

---

## 3 · Régua do dia — o dia numa linha do tempo, com os vazios à vista

A aposta: o que falta num horário é **o buraco entre os blocos**. É a ideia que
mais arrisca parecer planilha; é o que se quer descobrir.

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — "day ruler", the DAY theme of a study app for high-school seniors. A
PLANNING tool. It must NOT look like a spreadsheet: no cell borders, no columns, no
table header, only a quiet time axis and cards. NO checkmarks, NO progress bar, NO
flame, NO trophy, NO green, NO red inside the content.

GROUND AND COLOUR: ground white #FFFFFF with an extremely faint square grid, 24px
squares, navy at 4% opacity. Raised surfaces #F4F7FC, 18px corner radius, 2px
border #DCE6F7, never a drop shadow. Secondary text #5C6883. Colour is ROLE: ACTION
navy #1B3F8B with white label and a 4px hard bottom edge #12275A; DATA, selected and
planned things, blue #2E6BE6; MAGNITUDE, large numerals, near-black navy #0F1B33.
No other colour. Anything empty is drawn HOLLOW.

Type: extra-bold rounded geometric sans (Plus Jakarta Sans style) for titles and
numerals, regular for body. Tabular figures. Eyebrows 10px bold uppercase.

THE SCREEN — "Horário de estudos", one chosen day drawn on a time ruler.

APP SHELL TOP BAR, 53px: small circular seal placeholder at the left; at the right a
coral flame "14", a gold token "2.850", an avatar "BE".

HEADER on one line: a 44px square with a thin left chevron, then "Horário de
estudos", extra-bold 28px.

COMPACT DAY STRIP: seven pills, 44px wide and 40px tall, SEG TER QUA QUI SEX SÁB DOM
in 10px uppercase. QUI is selected, filled DATA blue with a white label. TER has a
thin ring around it because it is today. The rest are HOLLOW.

SECTION LABEL, DATA eyebrow: "QUINTA-FEIRA", and at its right in secondary text
"2h30".

THE RULER, filling the rest of the screen: a vertical time axis at the left with
hour labels "14", "15", "16" … "22" in 10px secondary tabular figures, one hour every
56px, and a very faint 1px hairline in #DCE6F7 across the width at each hour — a
ruler, not a grid.
Two block cards sit on the ruler with heights proportional to their length, aligned
to the hairlines:
- 18:00 to 19:00, one hour tall: start time "18:00" at the top-left in 20px
  extra-bold MAGNITUDE and the label "Redação" in 16px bold beneath;
- 19:15 to 20:45, a little taller: "19:15" and "Revisar meus erros".
The fifteen-minute gap between the two cards is visible and empty.
The long empty stretch from 14:00 to 18:00 is plain, with a single small HOLLOW
round "+" button at the 16:00 line, inviting a block.

PRIMARY BUTTON, full width, fixed above the bottom navigation: ACTION navy, bold
uppercase letterspaced white label "ADICIONAR BLOCO", 4px hard bottom edge.

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Estudar" active in DATA colour with a 2px underline.
```

---

## 4 · Semana em quadrados — a semana de relance, no motivo da grade

A aposta: a semana como **mosaico de quadradinhos** — o mesmo motivo do fundo e
do cobogó do login. Cheio é planejado, vazado é livre. Dá a densidade da semana
em um olhar; o detalhe vem logo abaixo.

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — "week in squares", the DAY theme of a study app for high-school seniors.
A PLANNING tool. The week is drawn as a MOSAIC of small rounded squares, echoing
the faint square grid of the background. NO checkmarks, NO progress bar, NO flame,
NO trophy, NO green, NO red inside the content.

GROUND AND COLOUR: ground white #FFFFFF with an extremely faint square grid, 24px
squares, navy at 4% opacity. Raised surfaces #F4F7FC, 18px corner radius, 2px
border #DCE6F7, never a drop shadow. Secondary text #5C6883. Colour is ROLE: ACTION
navy #1B3F8B with white label and a 4px hard bottom edge #12275A; DATA, planned time
and selection, blue #2E6BE6; MAGNITUDE, large numerals, near-black navy #0F1B33.
No other colour. Anything free is drawn HOLLOW.

Type: extra-bold rounded geometric sans (Plus Jakarta Sans style) for titles and
numerals, regular for body. Tabular figures. Eyebrows 10px bold uppercase.

THE SCREEN — "Horário de estudos", the whole week at a glance.

APP SHELL TOP BAR, 53px: small circular seal placeholder at the left; at the right a
coral flame "14", a gold token "2.850", an avatar "BE".

HEADER on one line: a 44px square with a thin left chevron, then "Horário de
estudos", extra-bold 28px.

THE BIG NUMBER: eyebrow "PLANEJADAS NA SEMANA", and under it "11h30" at 64px
extra-bold MAGNITUDE. At the right end of the same row, in 13px secondary text,
"Próximo simulado: P5, em 12 dias".

THE MOSAIC, inside one raised surface: seven columns labelled SEG TER QUA QUI SEX
SÁB DOM in 10px uppercase. Under each label a vertical stack of 18 small squares,
14px each with 4px corner radius and 4px gaps; each square is thirty minutes, from
14:00 at the top to 23:00 at the bottom, with three tiny hour labels "14h", "18h",
"22h" in secondary text at the left edge.
Planned time is a FILLED DATA-blue square; free time is a HOLLOW square outline in
#DCE6F7. The filled squares form short solid bars: three squares in the lower middle
of SEG, TER, QUA and SEX; QUI with two filled squares, one hollow square, then three
filled; SÁB with a bar of four squares higher up; DOM with a bar of two.
The TER column is selected: a 2px rounded DATA outline around the whole column, and
a thin ring around its label because it is today.

SELECTED DAY below, compact, DATA eyebrow "TERÇA-FEIRA · HOJE", then one row:
"19:00 – 20:30" in 20px extra-bold MAGNITUDE, and "Estequiometria" in 16px bold.

PRIMARY BUTTON, full width, fixed above the bottom navigation: ACTION navy, bold
uppercase letterspaced white label "ADICIONAR BLOCO", 4px hard bottom edge.

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Estudar" active in DATA colour with a 2px underline.
```

---

## 5 · O bloco em frase — a folha de "Novo bloco"

Outra ideia: montar o bloco **lendo uma frase** ("toda seg–sex, às 19:00, por 1h30,
estudar Termodinâmica") em vez de um formulário. É o gesto de "segunda a sexta de
uma vez" do [42 §3](42-plano-horario-de-estudos.md).

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written.

DIRECTION — "block as a sentence", the NIGHT theme of a study app for high-school
seniors. A bottom sheet, 72% of the screen height, slides over a dimmed schedule
screen; only a sliver of the dimmed page title is visible above it. No checkmarks,
no flame, no trophy, no green, no red.

GROUND AND COLOUR: the dimmed page behind is near-black blue #050A18. The sheet is
#0C1530 with 28px top corner radius and a 1px luminous edge #1B2B57, with a small
grabber bar centred at the top. An extremely faint square grid in #0E1A38 shows on
the sheet. Secondary text #6E85B8. Colour is ROLE: ACTION lit gold #FFCE3A with a
near-black #050A18 label and a 4px hard bottom edge #C79A16, no blur; DATA, selected
things, electric blue #2F6BFF, with ice blue #7FB6FF as its lighter register;
MAGNITUDE, large numerals, white #FFFFFF. No other colour. Anything not chosen is
drawn UNLIT: a dark hollow outline in #1B2B57. NO glow on fills or text.

Type: extra-bold rounded geometric sans (Plus Jakarta Sans style) for titles and
numerals, regular for body. Tabular figures. Eyebrows 10px bold uppercase
letterspaced in ice blue.

THE SHEET — "Novo bloco", built as one sentence read top to bottom.

Title row: "Novo bloco" in extra-bold 24px white, and at the right a 44px square with a
thin "x".

Row 1 — eyebrow "TODA". Seven pills in one row, each at least 44px, labelled SEG TER
QUA QUI SEX SÁB DOM. SEG TER QUA QUI SEX are FILLED electric blue with white labels;
SÁB and DOM are UNLIT hollow outlines.

Row 2 — eyebrow "ÀS". One large tappable field, a raised box with a 1px border, with
"19:00" at 48px extra-bold white, centred.

Row 3 — eyebrow "POR". Five pills: "30 min", "45 min", "1h", "1h30", "2h". "1h30" is
FILLED electric blue; the others UNLIT.

Row 4 — eyebrow "ESTUDAR". A text field, 56px tall, containing "Termodinâmica" in 18px
white, and under it, 13px secondary, "Termina às 20:30".

Fixed at the base: a full-width ACTION button, bold uppercase letterspaced near-black
label "SALVAR BLOCO", lit gold with the 4px hard bottom edge; and under it a quiet
centred text button "Cancelar" in secondary colour.
```

---

## 6 · O cartão em Estudar — quatro campos, 2×2 no desktop

O quarto campo. O desktop deixa de ser "três lado a lado" e vira grade 2×2
([42 §4.1](42-plano-horario-de-estudos.md)). **Proporção 16:10.**

```
A single desktop web app screen, 1440x900, as a flat UI design mockup — no browser
chrome, no device frame, no hands, no desk, no perspective, no reflections. Straight
on, edge to edge, filling the whole image. Crisp and high fidelity, no blur, no
noise. No mascot, no character, no illustration other than small thin-line icons.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with a letter inside — never a photograph.

DIRECTION — the DAY theme of a study app for high-school seniors. Three columns:
a left rail 240px, a centre column 640px, a right column 320px. The new element is
the FOURTH card in the centre grid.

GROUND AND COLOUR: ground white #FFFFFF with an extremely faint square grid, 24px
squares, navy at 4% opacity. Raised surfaces #F4F7FC, 18px corner radius, 2px
border #DCE6F7, never a drop shadow. Secondary text #5C6883. Colour is ROLE: ACTION
navy #1B3F8B; DATA, icons, eyebrows and the active item, blue #2E6BE6; MAGNITUDE,
large numerals and titles, near-black navy #0F1B33; VALUE gold #F2C94C and STREAK
coral #FF6B4A appear ONLY in the right-column widgets. No green. No other colour.

Type: extra-bold rounded geometric sans (Plus Jakarta Sans style) for titles and
numerals, regular for body. Tabular figures. Eyebrows 10px bold uppercase
letterspaced in DATA colour.

LEFT RAIL: at the top a circular school seal placeholder and, under it, the small
uppercase text "ÁREA DO ESTUDANTE". Four items stacked, 56px tall, with thin line
icons: Hoje, Estudar, Provas, Jornada. "Estudar" is active: a filled navy rounded
rectangle with a white label. At the bottom a profile row: a circle with "B", the
name "BENNY", and a small gear icon.

CENTRE COLUMN: the title "Estudar", extra-bold 40px MAGNITUDE. Under it a 2×2 grid of
four equal cards, about 311px wide and 250px tall, 18px gap. Each card holds, from
the top: the eyebrow, a bold title at 30px, a regular subtitle in secondary text, and
a thin-line icon, stroke 1.4px in DATA colour, at the bottom right.
1. eyebrow "MATERIAL", title "Banco de questões", subtitle "4.050 questões de prova do
   ITA e do IME", icon of a document sheet.
2. eyebrow "DIAGNÓSTICO", title "Estatísticas", subtitle "O que mais cai em cada
   assunto, ano a ano", icon of three ascending bars.
3. eyebrow "VOCÊ", title "Meu progresso", subtitle "5 de 4.050 questões marcadas",
   icon of a 3×3 grid of small squares, the first filled.
4. THE NEW CARD, same size and style: eyebrow "QUANDO", title "Horário de estudos",
   subtitle "Hoje, 19:00 · Estequiometria", icon of a round clock face outline with a
   solid filled wedge between twelve and seven o'clock — clearly different from a
   sheet, bars and a grid.
Under the grid, one quiet text link with a small arrow: "Revisar os 34 erros dos seus
simulados".

RIGHT COLUMN, three stacked cards: a streak card with a coral flame icon, the number
"14" very large, the eyebrow "SEQUÊNCIA", four small coral rounded chips and
"simulados sem faltar"; an XP card with a gold hexagon icon, "2.850" very large, the
eyebrow "XP" and "+1.240 neste ciclo"; and a league card with the eyebrow "LIGA OURO",
"6º de 34" and a gold button "VER" with a 4px hard bottom edge.
```

---

## 7 · A linha na Hoje — o aluno lê de volta o que escreveu

Uma linha só, quieta, sem bloco. Gere também **sem a linha** (apague o parágrafo
`THE QUIET LINE`) para comparar quanto ela pesa.

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — the DAY theme of a study app for high-school seniors, the home screen
"Hoje", which answers "what do I do now". Calm and tactile like a game. The new
element is ONE quiet line; it must not compete with the hero.

GROUND AND COLOUR: ground white #FFFFFF with an extremely faint square grid, 24px
squares, navy at 4% opacity. Raised surfaces #F4F7FC, 18px corner radius, 2px
border #DCE6F7, never a drop shadow. Secondary text #5C6883. Colour is ROLE: ACTION
navy #1B3F8B with white label and a 4px hard bottom edge #12275A; DATA blue #2E6BE6;
MAGNITUDE near-black navy #0F1B33; STREAK coral #FF6B4A and VALUE gold #F2C94C only
in the top bar. No green. No other colour.

Type: extra-bold rounded geometric sans (Plus Jakarta Sans style) for titles and
numerals, regular for body. Tabular figures. Eyebrows 10px bold uppercase
letterspaced in DATA colour.

TOP BAR, 53px: a small circular seal placeholder at the left; at the right a coral
flame "14", a small gold token "2.850", and a circular avatar "BE".

HERO, the dominant element: eyebrow "MISSÃO DE HOJE", then "12 questões de
Termodinâmica" at 44px extra-bold MAGNITUDE, a quieter line "Cai em 7% da prova do ITA.",
and a full-width tall ACTION button "COMEÇAR" in bold uppercase letterspaced white
with the 4px hard bottom edge.

THE QUIET LINE, directly under the hero: a single-row raised surface, 52px tall,
1px border #DCE6F7, with NO 4px key edge and no emphasis. At the left a thin-line clock
icon in DATA colour; then the text "Próximo: hoje, 19:00 · Estequiometria" in 15px, the
word "Próximo:" in secondary text and the rest in MAGNITUDE colour; at the far right a
small chevron. It reads as a link, not as a card.

COUNTDOWN BLOCK, under it, raised surface: eyebrow "PRÓXIMO SIMULADO", then "12" at 56px
extra-bold MAGNITUDE beside "dias · P5 · ITA · Fase 1", and under that a thin rounded
track filled about 70% in DATA blue, the remainder unfilled.

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Hoje" is active, in DATA colour with a 2px underline.
```

---

## 8 · O vazio — o primeiro bloco

A maioria dos alunos abre esta tela com zero blocos, então é o estado mais comum.
Ele tem de **ensinar o gesto** e não pedir desculpa.

```
A single mobile app screen, 390x844, as a flat UI design mockup — no device frame,
no hands, no desk, no perspective, no reflections. Straight on, edge to edge,
filling the whole image. Crisp and high fidelity, no blur, no noise.
No mascot, no character, no illustration of any kind.
All interface text in Brazilian Portuguese, exactly as written. Avatar is a plain
circle with two letters inside — never a photograph of a person.

DIRECTION — the NIGHT theme of a study app for high-school seniors. The EMPTY state
of "Horário de estudos": no block exists yet. It is an invitation to act, never a
sad notice. No checkmarks, no flame inside the content, no trophy, no green, no red.

GROUND AND COLOUR: ground near-black blue #050A18 with an extremely faint square grid
in #0E1A38. Raised surfaces #0C1530, 18px corner radius, 1px luminous edge #1B2B57.
Secondary text #6E85B8. Colour is ROLE: ACTION lit gold #FFCE3A with a near-black
#050A18 label and a 4px hard bottom edge #C79A16, no blur; DATA electric blue #2F6BFF,
ice blue #7FB6FF as its lighter register; MAGNITUDE white. No other colour. Anything
unplanned is UNLIT: a dark hollow outline in #1B2B57. NO glow on fills or text.

Type: extra-bold rounded geometric sans (Plus Jakarta Sans style) for titles,
regular for body. Eyebrows 10px bold uppercase letterspaced.

APP SHELL TOP BAR, 53px: a small circular seal placeholder at the left; at the right a
coral flame "14", a small gold token "2.850", a circular avatar "BE".

HEADER on one line: a 44px square with a thin left chevron, then "Horário de
estudos" in extra-bold 28px white.

THE EMPTY WEEK, one raised surface: seven columns labelled SEG TER QUA QUI SEX SÁB DOM
in 10px uppercase, each with a vertical stack of eight small rounded squares, 14px,
4px gaps. EVERY square is UNLIT, a dark hollow outline: the week is completely empty.
Only the TER label carries a thin ring, because it is today.

BELOW, centred: a quiet eyebrow "SEM BLOCOS AINDA" in secondary text; the headline
"Monte a sua semana de estudo" at 28px extra-bold white; the body "Escolha os dias, a
hora e o que estudar. Por exemplo: segunda a sexta, 19h, 1h30." at 15px secondary.

PRIMARY BUTTON, full width: ACTION lit gold, near-black bold uppercase letterspaced
label "CRIAR O PRIMEIRO BLOCO", with the 4px hard bottom edge.
Under it one quiet centred line with a small lock icon: "Só você vê o seu horário."

BOTTOM NAVIGATION, four items with thin line icons above labels: Hoje, Estudar,
Provas, Jornada. "Estudar" is active, in DATA colour with a 2px underline.
```

---

## Tema noite — troque o parágrafo `GROUND AND COLOUR` dos prompts 1 a 4 por este

```
GROUND AND COLOUR: ground near-black blue #050A18 with an extremely faint square
grid in #0E1A38. Raised surfaces #0C1530, 18px corner radius, 1px luminous edge
#1B2B57, never a drop shadow. Secondary text #6E85B8. Colour is ROLE: ACTION lit gold
#FFCE3A with a near-black #050A18 label and a 4px hard bottom edge #C79A16, no blur;
DATA, selected and planned things, electric blue #2F6BFF, with ice blue #7FB6FF as its
lighter register; MAGNITUDE, large numerals, white #FFFFFF. No other colour. Anything
empty or unplanned is drawn UNLIT: a dark hollow outline in #1B2B57. Key strokes —
the ring around today — are a thin neon tube, bright core with a tight halo no wider
than 4px; fills, buttons and text have NO glow.
```

Troque também, nos prompts 1 a 4, "navy" por "lit gold" na descrição do botão
(`ACTION navy … white label` vira `ACTION lit gold … near-black label`) e o texto
branco dentro do dia selecionado continua branco.

---

## O que decide depois

| Se a gente gostar de… | …então o desenho de verdade é |
|---|---|
| **1** | faixa de dias + lista, exatamente o [42 §4.2](42-plano-horario-de-estudos.md) |
| **2** | `EstudarHorario` vira uma lista única e some a faixa; **mexe no §4.2** |
| **3** | a lista do dia ganha eixo de horas; o banco e a API **não mudam** |
| **4** | o mosaico entra como cabeçalho da 1 ou da 2; é componente novo em SVG à mão, sem biblioteca |
| **5** | a `Folha` ganha o formulário em frase; vale com qualquer das quatro |
| **6** | `.alu-campos` passa a grade 2×2 a partir de 900px |
| **7** | uma linha em `Hoje.tsx`, escondida para quem não tem bloco |
| **8** | é o estado vazio de `EstudarHorario`, qualquer que seja a estrutura |

Escolhida a direção, o passo seguinte é o brief para o **Claude Design** (como o
[brief do aluno](brief-claude-design-aluno.md)), com a estrutura vencedora e os três
estados — vazio, preenchido e erro — em celular e desktop, nos dois temas.
