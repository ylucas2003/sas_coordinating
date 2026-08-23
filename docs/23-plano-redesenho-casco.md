# 23 — Redesenho do casco: rail de ícones, migalhas e faixa de filtros

> **Origem:** canvas `SAS — Coordenação ITM` no Claude Design
> ([projeto `bd06bdc2`](https://claude.ai/design/p/bd06bdc2-3409-4958-8bf3-b4682bd839d8)),
> desenhado em 23/08/2026 e importado no mesmo dia. Sete telas: Painel,
> Alunos, Provas (Ciclos e Simulados), Banco, Administração, ficha de simulado
> e a lista de alertas.
>
> **Escopo:** trocar a navegação e a linguagem visual do app da coordenação
> inteiro. Não é uma pele nova sobre o mesmo casco — o menu horizontal de 7
> abas virou rail vertical de 5 destinos, a sidebar de filtros deixou de
> existir, e Ciclos e Simulados viraram abas de uma tela só.
>
> **Pronto quando:** o coordenador abre o SAS e vê o desenho do canvas —
> rail à esquerda, migalha na topbar, tabelas com a largura inteira da janela
> — sem que nenhuma rota salva tenha quebrado, e com `npm run typecheck`,
> `npm run lint` e `npm test` limpos.

> ## ⚠️ Estado: **implementado, não verificado**
>
> O código desta sprint está escrito e no working tree, mas **nada foi
> executado**. A máquina onde ele foi escrito não tem Node, npm, Docker nem
> `node_modules` — não houve typecheck, lint, teste nem uma única abertura no
> browser. O que foi conferido está na [§6](#6--o-que-foi-conferido-à-mão-e-o-que-isso-não-cobre),
> e é conferência de leitura, não de execução.
>
> **Ninguém deve dar isto como pronto antes de rodar a [§7](#7--roteiro-de-verificação).**

---

## 1 · Por quê mexer no casco

A topbar horizontal tinha 7 abas (`Painel`, `Alunos`, `Simulados`, `Ciclos`,
`Banco`, `Auditoria`, `Administração`) mais busca, botão de importar e botão de
sair, tudo na mesma faixa de 60px. Três problemas que se acumularam:

1. **A fila de abas não tinha para onde crescer.** O banco de questões entrou
   como a sétima em 23/08. A oitava não caberia sem encolher a fonte.
2. **Duas colunas antes do dado.** Cada listagem gastava 220px numa sidebar de
   filtros à esquerda. Numa tela de 1440px isso é 15% da largura tirada
   justamente das tabelas largas — que são a razão de o SAS existir.
3. **Auditoria e Importar competiam com o uso diário.** São tarefas de
   manutenção, feitas por quem administra, e estavam no mesmo nível de
   hierarquia que o Painel.

O canvas resolve os três de uma vez: rail vertical (cresce para baixo, cabem
muitos destinos), filtros em faixa horizontal (devolve a coluna), e as tarefas
de manutenção agrupadas sob Administração.

---

## 2 · Decisões tomadas antes de escrever código

Três perguntas foram feitas ao Yan em 23/08, porque cada uma mudava o que
implementar — não eram preferência de gosto:

| Pergunta | Decisão | Consequência |
|---|---|---|
| Adotar a navegação do canvas, ou só reskinar o que existe? | **Adotar** | Rotas mudam; `/ciclos` e `/simulados` deixam de ser destinos de menu |
| A sidebar de filtros vira faixa de pílulas? | **Sim** | `PainelFiltros` e `Sidebar` morrem; 6 telas reescrevem os filtros |
| Tudo de uma vez, ou por etapas? | **Tokens + casco primeiro, telas depois** | Esta sprint entrega estrutura; o polimento fino fica para a [§8](#8--o-que-falta--p4) |

O que **não** foi decidido e continua em aberto está na [§9](#9--decisões-em-aberto).

---

## 3 · Divisão em 4 partes

| Parte | O quê | Estado |
|---|---|---|
| P1 | Tokens — a paleta do canvas vira `tokens.css` | ✅ escrito, ⚠️ não verificado |
| P2 | O casco — rail, topbar com migalhas, área de conteúdo | ✅ escrito, ⚠️ não verificado |
| P3 | As telas — faixa de filtros, `/provas`, abas de Administração | ✅ escrito, ⚠️ não verificado |
| P4 | Polimento fino, tela a tela, com o browser aberto | ⏳ **não começou** |

---

## P1 · Tokens

### 1.1 O que já batia, e o que não

A fonte já era **Plus Jakarta Sans servida localmente** — não houve nada a
fazer, e é bom que não tenha: buscá-la do Google Fonts mandaria o IP de aluno
menor de idade para o Google sem base legal, e a CSP de
`infra/vps/nginx.conf` bloqueia (ver o cabeçalho de
[web/styles/fontes.css](../web/styles/fontes.css)). O navy `#1B3F8B` também já
era o do canvas.

O que mudou foi o resto da escala.

### 1.2 Cinza é sempre azulado

Os cinzas antigos eram `rgba(26,29,36,·)` — neutro puro com transparência. Ao
lado do navy, neutro puro lê como sujeira. Todos viraram cinza-azulado opaco:
`#16233D` (título), `#5C6883` (secundário), `#8A93A8` (metadado).

Opaco e não `rgba` porque a mesma cor aparece sobre branco, sobre `#F6F8FC` e
sobre `#EEF1F7`; com alfa, cada fundo produzia um cinza diferente.

### 1.3 O âmbar precisou virar dois tokens

`--color-amber` (`#D4A82E`) é bonito como **traço** — barra de gráfico, linha
de referência do histograma. Como **texto sobre fundo claro ele reprova em
AA**. Foi separado:

```css
--color-amber:      #D4A82E;  /* traço */
--color-amber-text: #B08419;  /* o mesmo âmbar escurecido até passar */
```

Quem escrever texto âmbar daqui em diante deve usar `--color-amber-text`.
Verde e vermelho não precisaram: `#2E8C5A` e `#D9354A` já passavam.

### 1.4 Bordas: três fios, não um

Antes havia `--color-border` e `--color-border-strong`. O canvas usa três
espessuras de separação, e juntá-las achatava a hierarquia:

| Token | Valor | Onde |
|---|---|---|
| `--color-shell-border` | `#EAEEF6` | Aresta do casco (rail, topbar) |
| `--color-border` | `#EEF1F7` | Fio de card, cabeçalho de tabela |
| `--color-divider` | `#F2F5FA` | Fio entre linhas de tabela |

O `--color-divider` é o mais claro de propósito: com o fio de card entre
linhas, a tabela vira grade e o olho para em cada linha.

### 1.5 Pronto quando

- [x] `tokens.css` reescrito, com os nomes antigos preservados (nada quebra
      por token renomeado)
- [x] `docs/03` corrigido — a tabela de tokens lá estava desatualizada, e o
      arquivo agora aponta para `tokens.css` como fonte da verdade
- [ ] Conferido no browser que nenhuma tela ficou com texto ilegível

---

## P2 · O casco

### 2.1 O rail abre no CSS, não no React

O rail tem 88px fechado e 228px aberto. Quem faz a troca é
`:has(.rail:hover)` — não um `useState`.

Não é preciosismo: com estado, cada passada de mouse sobre o menu remontaria a
árvore inteira do app, e o estado não sobrevive à navegação de todo jeito.

**O rail também abre no `:focus-within`.** Um rail só-ícone sem rótulo é
adivinhação; quem navega por Tab precisa ver o nome do destino. Pelo mesmo
motivo o `<span>` do rótulo fica sempre na árvore, só com `opacity: 0` quando
fechado — `display: none` o esconderia do leitor de tela também.

### 2.2 Full-bleed, não a moldura do canvas

O canvas desenha o app dentro de um retângulo branco arredondado, com 28px de
respiro cinza em volta. Isso é convenção de artboard, não requisito de
produto — em 1440px são 56px de largura jogados fora. O casco implementado
encosta na borda da janela.

### 2.3 A migalha tem duas fontes

A trilha até a tela sai da rota — o roteador já sabe. O que ele não sabe é o
nome da coisa aberta (`ITA 2026 · Simulado 06`), que só chega depois da
consulta. Por isso a ficha declara o próprio nome:

```tsx
useTituloDaTela(simulado?.nome);
```

⚠️ **É hook.** Tem que ser chamado **antes** de qualquer `return` antecipado de
carregamento ou erro. As três fichas já estão assim; quem criar a quarta que
não esqueça.

### 2.4 O rail vira barra inferior no celular

Abaixo de 760px o rail sai da lateral e vira barra fixa no rodapé, com
`env(safe-area-inset-bottom)` no padding — a régua de toque de
[docs/20 §1.3](20-mobile.md). A busca colapsa em ícone e expande sobre a
topbar ao receber foco.

⚠️ Isto foi escrito lendo a régua, **não medido em aparelho**. Ver [§7](#7--roteiro-de-verificação).

### 2.5 Pronto quando

- [x] `casco.css`, `Rail.tsx`, `Topbar.tsx`, `AppShell.tsx`, `migalhas.tsx`
- [x] Busca global preservada com o atalho `/` e navegação por setas
- [ ] Rail conferido com Tab (abre? o foco aparece? o rótulo é anunciado?)
- [ ] Barra inferior conferida a 390px e a 360px

---

## P3 · As telas

### 3.1 `/ciclos` e `/simulados` viraram abas de `/provas`

Eram dois destinos de menu, e a distinção nunca foi de navegação: um ciclo é
um agrupamento de simulados, e o coordenador alterna entre as duas leituras da
mesma prova o tempo todo.

**A aba vive na query (`?aba=simulados`), não no estado.** É o que faz o link
copiado abrir na aba certa e o botão voltar do navegador funcionar. A troca de
aba usa `replace` — voltar deve sair de Provas, não desfazer cliques de aba.

⚠️ **Os caminhos antigos continuam existindo**, como `<Navigate>`:

```tsx
<Route path="/simulados" element={<Navigate to="/provas?aba=simulados" replace />} />
<Route path="/ciclos"    element={<Navigate to="/provas" replace />} />
```

Não os remova. Estão em link salvo e **em e-mail de lembrete já enviado** —
os lembretes de P2/P3 da Sprint 1 apontam para lá. `/ciclos/:id` e
`/simulados/:id` seguem sendo rotas de verdade, não redirecionam.

### 3.2 Auditoria e Importar viraram abas de Administração

Saíram do rail. `AbasAdmin.tsx` é `NavLink`, não estado — cada uma continua
sendo rota própria, com URL, histórico e link direto. Só a apresentação mudou.

### 3.3 A faixa de filtros, e a exceção do Banco

`BarraFiltros` substitui `PainelFiltros`. Diferença de fundo além da
orientação: **todos os grupos ficam abertos**. Na sidebar eles eram
colapsáveis; o custo de esconder um filtro é o usuário não saber que ele
existe, e são poucos o bastante para caber numa linha.

**O Banco é exceção deliberada.** Ele mantém a coluna `.banco-filtros`
própria, que nasce empilhada no celular e vira coluna a partir de 880px. Os
assuntos por edital são 351 ([22 §1.1](22-plano-banco-questoes.md)) — não
cabem numa faixa horizontal. Isso está comentado no topo de `Banco.tsx` para
ninguém "uniformizar" depois.

### 3.4 Duas duplicações de CSS que já mordiam antes

Encontradas no caminho, não criadas por esta sprint:

- **`.btn` estava definido em `layout.css` e em `edicao.css`.** Como
  `edicao.css` carrega depois, era a definição *dos diálogos* que valia em
  toda tela do app. Consolidado em `layout.css`; `edicao.css` ficou com um
  comentário apontando para lá. As duas grafias do modificador
  (`btn-primary` nas telas, `btn--primary` nos diálogos) são atendidas —
  unificar a grafia seria um diff de quinze arquivos no meio do redesenho.
- **`.nota-badge` idem**, entre `layout.css` e `painel.css`. A de `painel.css`
  venceu (carrega depois) e virou a canônica, aceitando tanto `--verde` quanto
  `.tone-verde`.

### 3.5 O que foi apagado

| Arquivo | Por quê |
|---|---|
| `componentes/ui/filtros/PainelFiltros.tsx` | A sidebar de filtros não existe mais |
| `componentes/layout/Sidebar.tsx` | idem |
| `src/rotas.ts` | Só exportava `sidebarPara()`, que decidia qual sidebar cada rota mostrava |

Mais ~190 linhas de CSS morto em `painel.css` (`.psb-*`, a sidebar de três
seções de uma versão anterior — já não era usada por ninguém antes desta
sprint) e `filtros.css` (`.filtros-*`).

⚠️ **`docs/19` marcava C.1 como resolvido "em `PainelFiltros.tsx`".** O
problema (componente único de filtro) continua resolvido — mudou o componente,
que agora é `BarraFiltros.tsx`. O roadmap foi corrigido.

### 3.6 Pronto quando

- [x] 6 telas convertidas: Painel, Alunos, Ciclos, Simulados, Auditoria,
      Administração
- [x] `<main className="app-main">` → `.tela` em todas as 17 ocorrências
      (o `<main>` agora é do casco; dois `<main>` na página é HTML inválido)
- [ ] Cada tela aberta no browser, com dado real

---

## 4 · Onde o desenho implementado diverge do canvas

Divergências conscientes. Quem comparar tela e canvas vai bater nelas:

| Canvas | Implementado | Por quê |
|---|---|---|
| App dentro de moldura arredondada com respiro cinza | Full-bleed | Convenção de artboard; 56px de largura desperdiçada ([§2.2](#22-full-bleed-não-a-moldura-do-canvas)) |
| Foto de rosto nas linhas de aluno | Avatar de iniciais | O SAS não guarda foto de menor de idade (CLAUDE.md, regra 6) |
| Fonte via `fonts.googleapis.com` | `@font-face` local | Mesma regra; a CSP de produção bloqueia |
| Nomes fictícios (`Gabriel Almeida`) e números redondos | Dado real da API | — |
| Rail abre só no hover | Hover **e** `:focus-within` | Teclado ([§2.1](#21-o-rail-abre-no-css-não-no-react)) |

---

## 5 · Arquivos tocados

**Novos (6):** `styles/casco.css`, `componentes/layout/Rail.tsx`,
`componentes/layout/migalhas.tsx`, `componentes/layout/AbasAdmin.tsx`,
`componentes/ui/filtros/BarraFiltros.tsx`, `telas/Provas/Provas.tsx`.

**Apagados (3):** ver [§3.5](#35-o-que-foi-apagado).

**Modificados (21):** 11 telas, `App.tsx`, `main.tsx`, `AppShell.tsx`,
`Topbar.tsx`, `util/formato.ts`, e os CSS `tokens`, `layout`, `painel`,
`filtros`, `simulados`, `edicao`, `aluno-ficha`.

Saldo: **−780 linhas**.

---

## 6 · O que foi conferido à mão — e o que isso não cobre

Sem Node na máquina, a conferência foi por leitura e por script de texto:

| Conferido | Como |
|---|---|
| Chaves de CSS balanceadas nos 7 arquivos | contagem `{` vs `}` |
| Tags JSX balanceadas nos 18 arquivos tocados | regex de abertura/fechamento por elemento |
| Zero imports órfãos | varredura de cada identificador importado no resto do arquivo |
| Zero referências ao que foi apagado | `grep` por `PainelFiltros`, `Sidebar`, `sidebarPara`, `app-main`, `psb-`, `filtros-*` |
| Todo CSS existente está registrado em `main.tsx` | `diff` entre o `ls` e os imports |

**O que isso explicitamente NÃO cobre:** tipo errado, prop faltando,
`useExhaustiveDependencies`, hook chamado fora de ordem, layout quebrado,
contraste reprovado, foco invisível, e qualquer coisa que só aparece com dado
real. É o grosso do risco.

---

## 7 · Roteiro de verificação

**Antes de qualquer outra coisa:**

```sh
cd web && npm install
npm run typecheck     # o mais provável de pegar algo
npm run lint          # atenção a useExhaustiveDependencies
npm test              # 134 testes; nenhum toca no casco, mas confirme
```

`npm run typecheck` é o mais provável de acusar algo — nada nesta sprint foi
compilado uma vez sequer.

**Depois, com `docker compose up` e o MCP `chrome`:**

| # | O quê | Como se sabe que passou |
|---|---|---|
| 1 | Rail navega para os 5 destinos | O item ativo fica navy sólido |
| 2 | Rail abre por Tab | Rótulos aparecem; o anel de foco é visível |
| 3 | Migalha na ficha de aluno / ciclo / simulado | Mostra o **nome**, não "Ficha do aluno" |
| 4 | `/simulados` e `/ciclos` na barra de endereço | Redirecionam para `/provas` na aba certa |
| 5 | `/provas?aba=simulados` copiado e colado | Abre na aba Simulados |
| 6 | Filtros do Painel (ciclo, sede, turma) | Filtram; "Limpar filtros" reativa |
| 7 | Contagem nas pílulas | Cross-filtering ainda bate ([Alunos.tsx](../web/src/telas/Alunos/Alunos.tsx)) |
| 8 | Abas de Administração | Contas ↔ Auditoria ↔ Importar, com URL própria |
| 9 | Banco a 390px | A coluna de filtros empilha, como antes |
| 10 | Rodapé a 390px e 360px | Barra inferior não cobre conteúdo; safe-area respeitada |
| 11 | Impressão do panorama do aluno | Rail e topbar somem (a regra em `aluno-ficha.css` foi ajustada de `.sidebar` para `.rail` — **conferir**) |
| 12 | Console limpo | Sem aviso de key, de hook, de `<main>` aninhado |

**Por último, a régua de UI:** rodar a skill `web-design-guidelines` sobre as
telas convertidas. As 103 regras de toque, safe-area, foco e formulário não
foram passadas nesta sprint.

---

## 8 · O que falta — P4

O polimento fino, que precisa do browser aberto e de dado real:

| | O quê | Onde |
|---|---|---|
| 1 | Avatar de iniciais no ranking do Painel e nas notas individuais da ficha de simulado (hoje só a lista de Alunos tem) | `TabelaPainel.tsx`, `SimuladoFicha.tsx` |
| 2 | Densidade das tabelas conferida com 900 alunos, não com 8 | Painel, Alunos |
| 3 | A tela de alertas do canvas (`O que merece sua atenção`) não foi implementada — o sino da topbar aponta para `/painel#alertas`, que **não existe** | novo |
| 4 | Área do aluno e tela de login herdaram os tokens novos, mas o casco delas não foi revisado | `ShellAluno.tsx`, `Login.tsx` |
| 5 | `.screen-header` / `.screen-title` convivem com `.tela-cabecalho` / `.tela-titulo` — duas gramáticas para a mesma coisa | `layout.css` |

⚠️ O item 3 é um **link quebrado em produção** se esta sprint for pro ar como
está. Ou implementa a tela, ou o sino vira decoração sem `href`.

---

## 9 · Decisões em aberto

| Decisão | Trava | Quem decide |
|---|---|---|
| O sino da topbar: tela de alertas própria (como no canvas), ou drawer sobre a tela atual? | P4 · item 3 | Yan |
| "Importar planilha" era botão primário na topbar antiga; virou terceira aba de Administração. Isso torna a tarefa mais rara do que ela é? | — | Yan + coordenação |
| O rail abre no hover. Vale um botão de fixar aberto, para quem usa teclado o dia todo? | — | Yan, depois de usar |

---

## 10 · Armadilhas para quem pegar isto

1. **Não remova os `<Navigate>` de `/ciclos` e `/simulados`.** Estão em
   e-mail de lembrete já enviado ([§3.1](#31-ciclos-e-simulados-viraram-abas-de-provas)).
2. **`useTituloDaTela` é hook.** Antes de qualquer `return` antecipado.
3. **A tela não monta `<main>`.** Quem monta é o casco; a rota devolve
   `.tela`. Dois `<main>` é HTML inválido e o leitor de tela anuncia duas
   regiões principais.
4. **Texto âmbar usa `--color-amber-text`,** não `--color-amber` — o segundo
   reprova em AA sobre fundo claro ([§1.3](#13-o-âmbar-precisou-virar-dois-tokens)).
5. **`edicao.css` carrega depois de `layout.css`.** Um seletor repetido lá
   vence, mesmo fora de diálogo. Foi assim que `.btn` passou meses sendo
   definido pelo arquivo errado ([§3.4](#34-duas-duplicações-de-css-que-já-mordiam-antes)).
6. **O Banco não usa `BarraFiltros`,** e não é esquecimento
   ([§3.3](#33-a-faixa-de-filtros-e-a-exceção-do-banco)).
