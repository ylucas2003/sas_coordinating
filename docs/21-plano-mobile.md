# 21 — Mobile: a área do aluno no celular

> **Origem:** decisão de 22/08/2026 de tratar mobile como prioridade. A rota, as
> razões dela e a auditoria que originou este plano estão em
> [20-mobile.md](20-mobile.md) — **leia primeiro**; aqui só se executa o que lá
> se decidiu.
>
> **Isto não é a "Sprint 3" do [docs/19-roadmap.md](19-roadmap.md).** Aquele
> documento já reservava o nome para outra coisa — fechar o Bloco A
> (requerimento de questões, cobrança de professor, WhatsApp). Este trabalho
> furou a fila por decisão direta de prioridade; o roadmap precisa ser
> atualizado para refletir isso, não o contrário.
>
> **Prioridade:** alta. É a primeira vez que o produto vai ser usado no aparelho
> em que o aluno de fato está.
>
> **Estado (22/08/2026): Onda 1 e Onda 2 implementadas e verificadas no
> browser com dado real (conta de teste do Benny Pereira Freitas, matrícula
> 21217933, 17 notas). Onda 3 começada — painel, `/simulados` e o chat do
> aluno verificados a 390px, zero transbordo. Ver [§12](#12--estado-em-22082026)
> para o que saiu diferente do planejado.
>
> **Escopo:** o front (`web/`, 6.496 linhas de CSS). O backend não muda — a API
> já serve qualquer cliente. Nenhuma migration.
>
> **Pronto quando:** um aluno abre `portalsas.online` no celular, entra, vê a
> nota do último simulado, navega pela evolução e conversa com o mentor — sem
> zoom, sem rolagem horizontal, sem elemento cortado, e sem esperar 10 segundos
> por uma imagem decorativa.

---

## O ponto de partida não é zero — e não é o que parecia

A auditoria de [19 §3](20-mobile.md#3--auditoria-de-partida-22082026) contou
media queries e concluiu "6 folhas sem nenhuma". O mapa completo mostra uma
divisão bem mais nítida, e ela redesenha o sprint:

| Camada | Estado real |
|---|---|
| **Casco do aluno** ([ShellAluno.tsx](../web/src/telas/Aluno/ShellAluno.tsx)) | **quase pronto.** Tem header desktop *e* header mobile, `.alu-bottom-nav` com `env(safe-area-inset-bottom)`, e `.alu-shell { height: 100dvh }` — a unidade certa, que o resto do projeto ainda não usa. É o modelo a seguir, não o problema |
| **Casco da coordenação** ([layout.css](../web/styles/layout.css)) | **nenhuma media query.** `.app-body` é um flex com `.sidebar { width: 220px; position: sticky }` lado a lado do conteúdo **em qualquer largura**. As 5 media queries de largura de `layout.css` cobrem só a `/ciclos/:id` |
| **Gráficos** | SVG à mão, sem biblioteca. **Dimensões fixas em px** na maioria |
| **Tabelas** | ~15 tabelas; **duas** têm container com rolagem |
| **Login** | zero media queries |

Ou seja: o trabalho de mobile do projeto começou pela área do aluno e parou no
casco. O sprint continua de onde parou — e o que sobra de mais caro não é
layout, é **gráfico e tabela**.

---

## Divisão em 5 partes

Isto **é** uma corrente, diferente da [Sprint 2](18-plano-sprint-2.md). A P1 é
fundação: mexe em tokens e em CSS-base que as outras quatro herdam. Fazer P3
antes de P1 é escrever duas vezes.

```
P1  fundação ──▶ P2  login ──▶ P3  área do aluno ──▶ P4  PWA
    (tokens,        (a porta)     (gráficos, chat)     (instalável)
     toque, peso)
                                        │
                      P5  coordenação ◀─┘
                          (casco + tabelas; pode cair)
```

| Parte | O quê | Demonstrável quando |
|---|---|---|
| **P1** | [Fundação](#p1--fundação-o-que-vale-para-o-app-inteiro) | nenhuma tela dá zoom ao focar input; o login carrega em menos de 2s no 3G |
| **P2** | [Login](#p2--login-a-porta-de-entrada) | a 360px o formulário está inteiro na tela, em uma coluna |
| **P3** | [Área do aluno](#p3--área-do-aluno-o-conteúdo-dentro-do-casco) | dá para usar o produto inteiro de celular, do login ao chat |
| **P4** | [PWA](#p4--pwa-instalável) | o aluno instala na tela inicial e abre sem barra de navegador |
| **P5** | [Coordenação](#p5--coordenação-o-casco-antes-das-tabelas) | o coordenador consegue consultar (não editar) do celular |

> ⚠️ **O corte natural é o fim da P3.** P1+P2+P3 entregam um produto usável no
> celular — que é a promessa. P4 e P5 são melhorias sobre algo que já funciona;
> se o tempo acabar, elas caem inteiras, e não pela metade.

---

## 0 · Pré-voo — não é parte, mas trava

### 0.1 Conta de teste — **bloqueia a P3 inteira**

A auditoria só conseguiu abrir a tela de login. Todo o resto foi análise
estática, porque autenticar exigiria mexer em credencial.

Precisa existir, no banco **local**, uma conta de aluno e uma de coordenação de
teste, com senha conhecida e anotada onde a equipe acha. Sem isso a P3 é feita
às cegas: dá para consertar o CSS, mas não para **ver** que consertou.

**Resolvido em 22/08 — a receita está em [docs/09 §Conta para entrar no
ambiente local](09-docker.md#conta-para-entrar-no-ambiente-local).** Resumo:
para aluno, [`api/scripts/criar_acesso.py`](../api/scripts/criar_acesso.py) já
existe para isto — é a ferramenta documentada em
[docs/15 §7.2](15-plano-hospedagem-vps.md), não algo a construir. Para
coordenação não há script: as 3 contas de hoje foram criadas à mão porque
`POST /administracao/coordenadores` exige token de coordenador (ovo-e-galinha)
e nenhuma migration semeia a tabela — o caminho é gerar o hash com
`app.auth.hash_senha` e inserir direto. **Este item deixa de bloquear**; falta
só executar e anotar onde a equipe acha (e-mail/matrícula, nunca a senha).

### 0.2 Xcode completo — recomendado, não bloqueante

O MCP `mobile` já está no [.mcp.json](../.mcp.json) e não enxerga aparelho
nenhum: falta o Xcode completo (App Store, ~10 GB); o Command Line Tools
instalado não traz o `simctl`. Ver [19 §2](20-mobile.md#2--ferramental-instalado).

Sem ele, tudo é feito no Chrome emulado, que cobre a maior parte. **Três itens
não são verificáveis sem Safari real**: `100dvh` com a barra de endereço,
`env(safe-area-inset-*)` no notch, e o teclado empurrando o chat.

### 0.3 Decidir os aparelhos-alvo

A auditoria usou 390×844 (iPhone 14) e 360×640 (Android comum). **360px é o
piso** até alguém dizer o contrário.

---

## P1 · Fundação: o que vale para o app inteiro

### 1.1 Por quê: os breakpoints de hoje são de tablet, não de celular

12 media queries de largura, **6 valores distintos**, nenhuma coordenação:

| Valor | Ocorrências | Onde | Cobre |
|---|---|---|---|
| 540px | 2 | `chat.css` | FAB vira círculo; drawer ocupa a tela |
| 660px | 1 | `layout.css` | `.mini-cards` → 2 colunas |
| 700px | 3 | `aluno.css` | header mobile + bottom nav; grids do aluno |
| 760px | 2 | `layout.css` | grids da `/ciclos/:id` |
| 880px | 2 | `layout.css` | grids da `/ciclos/:id` |
| 900px | 2 | `chat.css`, `aluno.css` | drawer empurra o conteúdo; grid do painel do aluno |

**O menor é 540px** — nada no projeto foi desenhado para um telefone; o que
existe é desktop encolhendo até caber num tablet. E as 5 queries de largura de
`layout.css`, que é a maior folha (1.781 linhas), atendem **uma única rota**:
a `/ciclos/:id`.

Sem nenhuma media query: `login.css`, `painel.css`, `simulados.css`,
`filtros.css`, `auditoria.css`, `edicao.css`.

### 1.2 Uma escala de breakpoints, em `tokens.css`

`tokens.css` tem 48 linhas e só cores, raios e sombras. Ganha três degraus,
nomeados pelo que significam:

| Nome | Valor | O que muda |
|---|---|---|
| `--bp-celular` | 560px | uma coluna, navegação compacta, tabela vira cartão |
| `--bp-tablet` | 880px | duas colunas, sidebar colapsa |
| `--bp-desktop` | 1200px | o layout de hoje |

Os valores 540/660/700/760/880/900 migram para o degrau mais próximo. **Isto é
refatoração, não redesign**: a tela a 900px deve continuar igual. Se mudou, é bug.

> ⚠️ Custom property **não funciona dentro de `@media`** — `@media (max-width:
> var(--bp-celular))` é inválido e falha em silêncio. Ou se usa `@custom-media`
> (PostCSS), ou os números ficam literais e os tokens servem de documentação.
> **Decidir antes da primeira query**, senão metade da folha vira regra morta
> sem ninguém notar.

### 1.3 A passada de toque

| O quê | Onde | Sintoma que some |
|---|---|---|
| `font-size: 16px` em `input`/`select`/`textarea` | base | o Safari do iOS **dá zoom sozinho** ao focar campo com fonte menor, e não desfaz. Hoje o login usa 14px |
| `touch-action: manipulation` | base | atraso de ~300ms em todo toque |
| `-webkit-tap-highlight-color` | base | retângulo cinza piscando a cada toque no Android |
| `overscroll-behavior: contain` | `.chat-drawer`, `.dialog`, `.alu-modal` | rolar até o fim do chat arrasta a página atrás |
| `100vh` → `100dvh` | [base.css:17](../web/styles/base.css#L17), [login.css:9](../web/styles/login.css#L9) | rodapé cortado pela barra de endereço. **`aluno.css:25` já usa `100dvh`** — é o padrão a copiar |
| `env(safe-area-inset-*)` | tudo full-bleed | existe **um** uso hoje, na `.alu-bottom-nav` |

Alvos de toque mínimos de 44×44. Medidos: botão do olho da senha **23×23px**
(e sem nome acessível — o Lighthouse acusa `button-name`), link "Criar minha
senha" com 17px de altura.

### 1.4 O peso: 1,7 MB numa imagem exibida a 88px

Medido em 22/08 contra o build de produção, com o Chrome emulando **Fast 3G**:

| Recurso | Peso | Tempo |
|---|---|---|
| **`selo-108anos.png`** | **1.692 KB** | **10.490 ms** |
| `index.js` | 454 KB | 3.672 ms |
| `index.css` | 92 KB | 1.613 ms |
| fonte, logos, favicon | 49 KB | < 1s |
| **total do login** | **2.287 KB** | FCP 4.392 ms |

O selo é `1254×1254px` e é exibido com `height: 88px`
([login.css:423](../web/styles/login.css#L423)) — 14× maior que o necessário em
cada dimensão. Redimensionado para 264px (88 × DPR 3) ele vai a **92 KB**: 94,6%
menor, **1,56 MB a menos** no primeiro carregamento de todo aluno.

E o insulto: ele vive no painel azul do login, que no celular está cortado — o
aluno espera 10 segundos por uma imagem que ele **não vê**.

1. **Redimensionar o selo** para 264px. Ganho: 1,56 MB. Custo: um comando.
2. **Não carregar o painel direito no celular** — se a P2 decidir escondê-lo, o
   `<img>` não pode só estar com `display: none`, tem que não ser pedido.
3. **Auditar as outras imagens** com a mesma régua.

O bundle de 454 KB é um arquivo só porque **nenhuma tela é lazy-loaded** —
`App.tsx` importa todas estaticamente, sem `React.lazy`. Dívida real, mas
mudança estrutural: fica **fora deste sprint**.

### 1.5 Pronto quando

`grep -rn "100vh" web/styles` não devolve nada; nenhum `input` computa
`font-size` menor que 16px a 390px; o selo pesa menos de 100 KB; o login carrega
abaixo de 2s no Fast 3G; e a tela a 900px está **pixel a pixel igual** à de
antes da migração de breakpoints.

---

## P2 · Login: a porta de entrada

### 2.1 O estado de hoje, medido

`login.css` (561 linhas) não tem **uma única** media query. O layout é
`grid-template-columns: 5fr 6fr` ([login.css:24](../web/styles/login.css#L24)),
duas colunas que nunca colapsam. Item de grid nasce com `min-width: auto`, então
as colunas se recusam a encolher abaixo do próprio conteúdo — e cada uma carrega
112px e 104px de padding lateral.

| Largura | Transbordo | Efeito |
|---|---|---|
| 390px | **+32px**, 36 elementos fora da viewport | painel azul cortado, manchete quebrando uma palavra por linha |
| 360px | **+47px** | a coluna do formulário começa em **x = −46px**, fora da tela; sobra 236px para o formulário e o painel azul come 29% do visor |

### 2.2 O que fazer

Abaixo de `--bp-tablet`: uma coluna (`grid-template-columns: 1fr`), e
`minmax(0, 1fr)` para as colunas poderem encolher de verdade — sem isso o
`min-width: auto` continua mandando.

**Decisão pendente, de produto:** o painel institucional (selo, "108 anos",
estatísticas de aprovação) no celular vira faixa curta acima do formulário, ou
some? Some é mais honesto: é peça de marca para quem chega pelo desktop, e no
celular custa 1,7 MB e empurra o campo de matrícula para baixo da dobra.
**Recomendação: some abaixo de `--bp-celular`, faixa curta entre celular e
tablet.** Quem decide é quem responde pela marca — mas é barato de reverter e
caro de adiar, porque a [§1.4](#14-o-peso-17-mb-numa-imagem-exibida-a-88px)
depende dela.

Junto: `aria-label` no botão do olho, alvos de 44px. O `autocomplete` já está
correto (`username` e `current-password` — verificado).

### 2.3 Pronto quando

A 360px e a 390px: `document.documentElement.scrollWidth === clientWidth`
(zero transbordo), o botão "Entrar" visível sem rolar, nenhum campo dando zoom
ao foco, e o Lighthouse mobile de acessibilidade **≥ 90** (hoje 82).

---

## P3 · Área do aluno: o conteúdo dentro do casco

O casco já está feito ([ShellAluno.tsx](../web/src/telas/Aluno/ShellAluno.tsx),
`aluno.css` com 1.202 linhas e 4 media queries). São **três rotas** —
`/`, `/simulados`, `/simulados/:id` — e o que falta está *dentro* delas.

**Depende da conta de teste da [§0.1](#01-conta-de-teste--bloqueia-a-p3-inteira).**

### 3.1 Gráficos: SVG à mão, com dimensões fixas

Não há biblioteca de gráfico no projeto — é tudo SVG escrito à mão. Isso é bom
(nenhum terceiro, ver regra 6 do [CLAUDE.md](../CLAUDE.md)) e é o problema:

| Componente | Como está declarado | Escala? | Onde aparece |
|---|---|---|---|
| `LinhaEvolucao` | `width="100%"` + `viewBox` 760, **sem `height`** | **sim** — é o modelo | ficha do aluno |
| `BarraComparacao`, `GraficoLinha` | `viewBox` dinâmico | sim | painel do aluno |
| **`Histograma`** | `viewBox` **e** `width={480} height={180}` | não, mas é barato | ciclo, simulado, **e o chat** |
| **`LinhaTemporal`** | `viewBox` **e** `width={720} height={220}` | não, mas é barato | ciclo, **e o chat** |
| **`Anel`** | `width`/`height` por prop, **sem `viewBox`**, em wrapper com `flexShrink: 0` | **não** | painel do aluno, detalhe do simulado |
| `Sparkline` | 90×32 fixos | não, mas cabe | célula de tabela |

**O detalhe que muda a prioridade:** `chat/Artefato` importa e renderiza
`Histograma` e `LinhaTemporal` ([Artefato.tsx:2-3](../web/src/componentes/chat/Artefato.tsx)).
O chat é do aluno. Então os dois gráficos de 480px e 720px chegam ao celular por
dentro do chat, num viewport de 390px.
`.chat-artefato { overflow-x: auto }` ([chat.css:455](../web/styles/chat.css#L455))
faz eles rolarem em vez de estourar — curativo, não conserto.

**A boa notícia:** `Histograma` e `LinhaTemporal` **já têm `viewBox`**. O que
trava a escala são os atributos `width`/`height` explícitos, e o conserto é
CSS — `max-width: 100%; height: auto` nas classes `.histograma` e
`.linha-temporal`, que já têm container próprio
([layout.css:913](../web/styles/layout.css#L913), [:1684](../web/styles/layout.css#L1684)).
Não é reescrever componente.

`Anel` é o caso diferente: sem `viewBox`, ele não responde a CSS de jeito nenhum
— só ao valor da prop `tamanho`. Ou ganha `viewBox`, ou quem o chama passa um
tamanho menor no celular.

### 3.2 Chat: `position: fixed` encontrando o teclado

`.chat-drawer` é `position: fixed` com `top/bottom: 0` (não `100vh` — correto),
`width: var(--chat-largura)` de 460px, e abaixo de 540px vira `100vw`.

O que precisa de atenção no celular:
- **Teclado virtual**: o composer é `textarea` com `max-height: 200px`. Com o
  teclado aberto num aparelho de 640px de altura, sobra pouco para a conversa.
  **Só verificável no Safari real** ([§0.2](#02-xcode-completo--recomendado-não-bloqueante)).
- **`overscroll-behavior: contain`** em `.chat-conversa__lista`, que hoje não tem.
- **Bug de empilhamento:** `.chat-fab` é `z-index: 950`, enquanto
  `.alu-modal-overlay` é `200` e `.dialog-overlay` é `900`. **O botão do chat
  flutua por cima de qualquer modal aberto** — e no celular, onde o FAB fica
  sobre a bottom nav, ele encosta no botão de ação do modal. Consertar a escala
  de `z-index` é item da P1, não da P3.

### 3.3 Modais do aluno

`Modal` e `ModalTrocarSenha` são definidos **inline** em `ShellAluno.tsx`
(linhas 145 e 170) e **não usam portal** — ficam dentro de `.alu-shell`, que tem
`overflow: hidden`. `.alu-modal { width: min(380px, 100%) }` já é responsivo em
largura, mas **não tem `max-height` nem rolagem interna**: num aparelho de 640px
com o teclado aberto, o formulário de troca de senha não tem como rolar.

Mesmo defeito no lado da coordenação: `.dialog { max-width: 420px }`
([edicao.css:23](../web/styles/edicao.css#L23)), sem `max-height`.
`edicao.css` tem **zero** media queries.

### 3.4 Ordem e pronto quando

Ordem: 3.1 (gráficos, o mais caro) → 3.2 (chat) → 3.3 (modais) → varredura das
três rotas a 360px.

**Pronto quando:** um percurso completo de celular, registrado em captura:
login → painel do aluno → evolução → um simulado → chat, mandando uma pergunta,
recebendo resposta em streaming e **abrindo um artefato de gráfico**. Se
qualquer passo exigir zoom ou rolagem lateral, não está pronto.

---

## P4 · PWA: instalável

O "P" de PWA não existe: sem `manifest.webmanifest`, sem `theme-color`, sem
ícone — o [index.html](../web/index.html) não tem sequer `<link rel="icon">`.

| O quê | Detalhe |
|---|---|
| `manifest.webmanifest` | `display: standalone`, cores vindas de `tokens.css` |
| Ícones | 192, 512 e um **maskable** 512. `assets/sas-logo.png` é 201×88 — pequeno demais; provavelmente precisa do original vetorial |
| `<meta name="theme-color">` | a barra do navegador acompanha a identidade |
| Nome | ⚠️ o `<title>` é hoje **"SAS · coordenação ITM"**. Na tela inicial de um aluno isso está errado — o manifest precisa de `name`/`short_name` que façam sentido para ele |
| `vite-plugin-pwa` | dependência de **build**, não de runtime: não acrescenta terceiro à página, então passa na regra 6 |

**Fora do escopo:** service worker com cache offline. Cachear tela de nota é
convidar o aluno a ver dado velho achando que é novo, e a invalidação disso é um
projeto, não um item de sprint.

**Pronto quando:** o Chrome oferece "Instalar"; instalado, abre sem barra de
navegador, com ícone e nome corretos.

---

## P5 · Coordenação: o casco, antes das tabelas

**Esta parte é decisão de produto, e é a primeira a cair.** Mas o diagnóstico
mudou: o problema maior não são as tabelas.

### 5.1 O casco não colapsa em largura nenhuma

`.app-shell { max-width: 1320px; padding: 20px 28px 48px }` e
`.app-body { display: flex; gap: 18px }` com
`.sidebar { width: 220px; flex-shrink: 0 }` — **sem nenhuma media query**, e o
`flex-shrink: 0` garante que ela não ceda um pixel
([layout.css:3](../web/styles/layout.css#L3), [:586](../web/styles/layout.css#L586)).
A sidebar fica ao lado do conteúdo a 360px do mesmo jeito que a 1440px,
deixando ~120px para a tela inteira. A topbar também não tem tratamento.

Isso é anterior a qualquer conversa sobre tabela: **nenhuma rota de coordenação
é utilizável no celular hoje**, mesmo as que não têm tabela (`/auditoria` é uma
timeline e sofre igual).

### 5.2 Tabelas: duas de ~15 têm rolagem

Onze arquivos usam `<table>`, e as tabelas vão de 4 a 14 colunas. **Só duas têm
container com rolagem**: `.painel-tabela-wrap` ([painel.css:16](../web/styles/painel.css#L16),
com colunas sticky para `#` e `Aluno`) e `.heatmap__container`
([layout.css:942](../web/styles/layout.css#L942)).

Todas as demais usam `.data-table { width: 100% }`
([layout.css:782](../web/styles/layout.css#L782)) direto dentro de
`.section`/`.card`, **sem wrapper de rolagem** — em tela estreita elas espremem
ou estouram. As piores:

| Rota | Tabela | Colunas |
|---|---|---|
| `/painel` | `.painel-tabela` | 2 fixas + N de matéria×fase, `<thead>` de 2 linhas — a mais larga do sistema (**tem rolagem**) |
| `/simulados` | `TabelaSimulados` | 8 a 14, conforme as props |
| `/alunos` | `.data-table` | 9 |
| `/ciclos/:id` | `.data-table` | 7 |
| `/administracao` | duas | 6 e 5 |

> A auditoria de [19](20-mobile.md) contou 6 ocorrências de `overflow-x` e
> soou melhor do que é: das 6, só 2 são wrapper de tabela — as outras são o
> calendário, o artefato do chat, o preview do agendamento e um
> `overflow-x: hidden`. O parágrafo lá já foi corrigido; fica o aprendizado de
> que **contar propriedade não é contar tabela**.

E `aluno.css:207` usa `overflow-x: hidden`, que **não** é a mesma coisa: esconde
o transbordo em vez de deixar rolar, e o conteúdo fica inalcançável. Isso é bug,
e vale consertar mesmo se a P5 inteira cair.

### 5.3 A pergunta que decide o tamanho da P5

**O coordenador usa celular para quê?** As respostas levam a lugares diferentes:

- "Só para dar uma olhada no ranking" → casco colapsando + a rolagem que o
  painel já tem. Barato.
- "Para checar um aluno específico" → casco + busca + ficha do aluno. Médio.
- "Para trabalhar de verdade" → tabela vira cartão. É um sprint próprio.

Enquanto não houver resposta, a régua é: **consultar sim, editar não.** Edição
de nota, envio ao Canvas e importação continuam desktop, com aviso claro em vez
de um formulário quebrado.

---

## 6 · A trava: sem ela, a auditoria vence a batalha e perde a guerra

A auditoria é uma **foto**. Sem verificação que rode sozinha, a primeira tela
nova reintroduz o transbordo e ninguém percebe até um aluno reclamar.

O front tem 7 arquivos de teste, **todos de lógica de domínio pura** — nenhum
toca DOM ([17](17-migracao-react-verificacoes.md)). O harness de browser da
migração React viveu no scratchpad da sessão e **não roda em CI**. Não existe
`.github/workflows`.

Mas existe portão: [`portoes_locais`](../infra/vps/deploy.sh) no `deploy.sh`,
com uma divisão explícita — **bloqueia** teste e typecheck (dizem se está
*quebrado*), **avisa** ruff e biome (dizem se está *feio*).

Transbordo horizontal é *quebrado*. Então:

- Um script **no repositório**, não no scratchpad, que abre cada rota a 360px e
  falha se `scrollWidth > clientWidth`, ou se algum `input` computar fonte menor
  que 16px.
- Entra em `portoes_locais` como **bloqueante**, junto do vitest.
- Precisa da conta de teste da [§0.1](#01-conta-de-teste--bloqueia-a-p3-inteira)
  para alcançar as rotas autenticadas. **É a segunda razão pela qual aquele item
  vem primeiro.**
- Cobre as duas árvores de rota: `/simulados` existe no lado do aluno **e** no
  da coordenação, com telas diferentes, e o script tem que saber disso.

---

## 7 · Ordem de execução

**Onda 1 · fundação, não depende de ninguém**
[1.4](#14-o-peso-17-mb-numa-imagem-exibida-a-88px) (o selo — melhor retorno do
sprint inteiro, e é um comando) · [1.2](#12-uma-escala-de-breakpoints-em-tokenscss)
(com a decisão do `@custom-media` tomada) · [1.3](#13-a-passada-de-toque) ·
escala de `z-index` ([3.2](#32-chat-position-fixed-encontrando-o-teclado))

**Onda 2 · a porta**
[P2](#p2--login-a-porta-de-entrada) inteira, junto da decisão sobre o painel
institucional · começar a trava da [§6](#6--a-trava-sem-ela-a-auditoria-vence-a-batalha-e-perde-a-guerra)
cobrindo o login, que é rota pública e não precisa de conta de teste

**Onda 3 · o produto** — destravada pela conta de teste
[P3](#p3--área-do-aluno-o-conteúdo-dentro-do-casco) na ordem 3.1 → 3.3 · a trava
passa a cobrir as rotas autenticadas

**Onda 4 · corta se o tempo acabar**
[P4](#p4--pwa-instalável) · [P5](#p5--coordenação-o-casco-antes-das-tabelas) ·
divisão do bundle por rota

**O corte natural é o fim da Onda 3.**

---

## 8 · Riscos

1. **A migração de breakpoints quebra o desktop em silêncio.** É o risco mais
   provável: 12 queries migrando para 3 degraus, sem teste que olhe markup.
   Mitigação: capturar as telas principais a 1440px **antes**, comparar depois.
   A regra é "a 900px nada muda".
2. **A P3 fica cega sem a conta de teste.** Não é risco técnico, é de
   sequenciamento — é o único bloqueio duro do sprint.
3. **Três defeitos não são verificáveis sem Safari real** (`100dvh`, safe-area,
   teclado no chat). Sem Xcode, vão para produção *provavelmente* certos. Ou se
   instala o Xcode, ou alguém abre no próprio iPhone e confere à mão — e isso
   fica escrito, não subentendido.
4. **`overflow-x: hidden` esconde bug em vez de resolver.** Ao arrumar
   transbordo, a tentação é aplicá-lo e ver o sintoma sumir. O conteúdo continua
   inalcançável. Só entra onde o transbordo já foi resolvido de verdade.
5. **Trocar dimensão fixa por `viewBox` muda a densidade do gráfico.** Um
   histograma de 480px comprimido em 360 fica ilegível mesmo escalando certo:
   rótulo de eixo some, barra vira risco. Pode ser preciso **reduzir a série**
   no celular, e isso é decisão de leitura de dado, não de CSS.
6. **Redimensionar o selo degrada o desktop.** 264px cobre 88px a DPR 3.
   Verificado: só há um uso
   ([PainelDireito.tsx:43](../web/src/telas/Login/PainelDireito.tsx#L43)).

---

## 9 · Fora do escopo, de propósito

- **Aplicativo em loja** (Capacitor / React Native) — [19 §1](20-mobile.md#1--a-decisão-web-responsiva-não-aplicativo)
- **Service worker com cache offline** — [P4](#p4--pwa-instalável)
- **Push notification** — o canal de aviso continua e-mail ([12](12-plano-p2-motor-lembretes.md))
- **Divisão do bundle por rota / `React.lazy`** — dívida real, mudança estrutural
- **Tabela da coordenação virando cartão** — só depois de responder [5.3](#53-a-pergunta-que-decide-o-tamanho-da-p5)
- **Migrar para CSS Modules** — `main.tsx` diz que é o plano; não é deste sprint
- **Redesenho visual** — este sprint faz caber, não faz bonito. A skill
  `frontend-design` entra quando alguém pedir redesign, não aqui.

---

## 10 · Como se verifica

| Nível | Ferramenta | Cobre |
|---|---|---|
| A cada tela | MCP `chrome` + `emulate 390x844x3,mobile,touch` | transbordo, alvo de toque, fonte de input |
| A cada parte | skill `web-design-guidelines` sobre os arquivos tocados | as 103 regras — foco, formulário, safe-area |
| Peso | `emulate` com `Fast 3G` + `performance.getEntriesByType('resource')` | o que o aluno espera de verdade |
| Regressão | o script da [§6](#6--a-trava-sem-ela-a-auditoria-vence-a-batalha-e-perde-a-guerra), no portão do `deploy.sh` | que nada disso volte |
| Safari real | MCP `mobile` + Simulator | os três itens que só o iOS mostra |

⚠️ O `performance_start_trace` às vezes ignora o throttle do `emulate`
([issue #1955](https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/1955));
confira no relatório se o trace saiu realmente throttled antes de citar número.

---

## 11 · O que falta decidir

| # | Pergunta | Quem responde | Trava |
|---|---|---|---|
| ~~1~~ | ~~Conta de teste de aluno e de coordenação no banco local~~ — ✅ receita pronta em [09](09-docker.md#conta-para-entrar-no-ambiente-local), falta só executar | equipe | P3 e a trava da §6 |
| 2 | O painel institucional do login some no celular ou vira faixa? | quem responde pela marca | P2, e o item 2 da §1.4 |
| ~~3~~ | ~~`@custom-media` ou números literais?~~ — ✅ literais, decidido na prática: sem isso os breakpoints de `login.css` e `aluno.css` já escritos teriam ficado inconsistentes com o resto do arquivo | equipe | — |
| ~~4~~ | ~~Gráfico no celular: escala, ou reduz a série?~~ — ✅ escala, para `GraficoLinha`/`BarraComparacao`/`Histograma`/`LinhaTemporal`: todos já tinham `viewBox`, só faltava `width:100%`/`max-width:100%`. **Não resolve** legibilidade em telas muito estreitas — se um histograma com 20 barras ficar ilegível a 360px, essa conversa reabre | quem lê os dados (coordenação) | — |
| 5 | O coordenador usa celular para quê? | coordenação (Leo) | P5 inteira |
| 6 | Instalar o Xcode completo? | equipe | verificação dos 3 itens de Safari |
| 7 | Existe aparelho de aluno menor que 360px? | coordenação | o piso da §0.3 |

---

## 12 · Estado em 22/08/2026

Implementado e verificado no browser (`chrome` MCP, `emulate 390x844x3,mobile,touch`
e `360x640x2,mobile,touch`) contra o dev server, autenticado com a conta de
teste do Benny Pereira Freitas (matrícula `21217933`, 17 notas reais).

### O que saiu como planejado

- **P1.3, passada de toque** — `font-size:16px` em todo `input/select/textarea`,
  `touch-action:manipulation`, `-webkit-tap-highlight-color:transparent`,
  `100vh`→`100dvh` em `base.css` e `login.css`.
- **P1.4, o selo** — `1.692 KB → 11,4 KB` (WebP, não JPEG: comparei os três
  formatos no mesmo recorte de 264px e o WebP ganhou por margem folgada — 11,4
  contra 27,6 KB do JPEG). PNG antigo removido do repositório.
- **P2, login** — colapsa para uma coluna abaixo de 880px, painel institucional
  some (a decisão da §2.2, tomada: ele tinha logo, selo, manchete e 4
  estatísticas — não cabia em faixa curta sem decisão de conteúdo). Botão do
  olho 44×44 com `aria-label`, link "Criar minha senha" com alvo de 42×44,
  `grid-template-columns: minmax(0, …)`. Zero transbordo medido a 390 e 360px;
  desktop a 1440px pixel-a-pixel igual ao anterior (grid 5fr/6fr, painel
  visível, padding original).
- **z-index dos overlays** — `.dialog-overlay` e `.alu-modal-overlay` subiram
  para 960, acima do chat (950/945): um modal aberto não fica mais atrás do
  FAB do mentor.
- **`.dialog` e `.alu-modal`** ganharam `max-height` + `overflow-y:auto` +
  `overscroll-behavior:contain` — não estouram mais com o teclado virtual
  aberto.

### O que a auditoria estática não via, e só apareceu com dado real

Três achados que **nenhuma contagem de media query pega**, porque só existem
em runtime, com layout real:

1. **`body { display:flex; align-items:center; justify-content:center }`
   vazava do `login.css` para o app inteiro.** Todo CSS é importado sem
   escopo por rota em `main.tsx` — a regra que centraliza o card do login
   (correta ali) fazia `#root` encolher para caber no conteúdo em vez de
   ocupar 100% da tela, em **qualquer** rota. Era a causa raiz de um
   transbordo de +224px no painel do aluno que não tinha relação nenhuma com
   o CSS do próprio painel. Corrigido movendo a centralização para um
   wrapper `.lp-page`, só no componente `Login`.
2. **Item de flex/grid sem `min-width:0` cresce para caber o conteúdo em vez
   de respeitar o container.** Apareceu duas vezes na mesma árvore —
   `.alu-shell` (o casco) e `.alu-painel__col` (uma coluna do grid) — cada
   uma escondendo a outra até serem corrigidas em sequência. É um padrão que
   pode recorrer em qualquer novo `display:flex`/`display:grid` que a P3
   ainda vá tocar; vale desconfiar dele especificamente, não só medir
   `scrollWidth` da página uma vez e seguir em frente.
3. **`GraficoLinha` e `BarraComparacao`** (`componentes/aluno/graficos.tsx`) —
   os gráficos do **painel do próprio aluno**, não só os do chat — tinham
   `width={largura}` (número fixo) apesar do `viewBox`, exatamente o defeito
   que a [19 §3](20-mobile.md) só tinha documentado para `Histograma` e
   `LinhaTemporal`. Corrigido para `width="100%"` + `preserveAspectRatio`,
   igual ao padrão que `LinhaEvolucao` já usava certo.

### O que ainda não foi tocado

- **P1.2, migração dos 12 breakpoints existentes** (`aluno.css`, `chat.css`,
  `layout.css`) para os 3 valores canônicos — adiado de propósito: a maior
  parte dessas regras vive em telas de coordenação, e não há conta de teste
  de coordenador para verificar depois de mexer. Ver [§0.1](#01-conta-de-teste--bloqueia-a-p3-inteira)
  — mesma trava, metade resolvida.
- **P3.2/3.3 no Safari real** — teclado empurrando o composer do chat, e os
  modais com o teclado aberto — seguem não verificáveis sem Xcode.
- **P4 (PWA) e P5 (coordenação)** — não começados.
- **A trava automatizada da §6** — ainda não escrita.
