# 20 — Mobile: decisão de rota, ferramentas e auditoria de partida

> **Origem:** conversa de 22/08/2026 — "o que podemos fazer na mesma linha para
> fazer a versão mobile". A pergunta era de **ferramental** (que MCP, que skill),
> mas ferramenta se escolhe depois de escolher a rota, e a rota não estava
> escrita em lugar nenhum. Este documento fecha as duas coisas.
>
> **Estado: nada de mobile foi implementado.** O que existe aqui é a decisão, o
> ferramental instalado e o inventário do que está quebrado — não uma entrega.
>
> **Escopo:** o front (`web/`). O backend não muda: a API já é a mesma para
> qualquer cliente.
>
> **Pronto quando:** um aluno abre `portalsas.online` no celular, entra, vê a
> nota do último simulado e conversa com o mentor — sem zoom, sem rolagem
> horizontal, sem elemento cortado.

---

## 1 — A decisão: web responsiva, não aplicativo

Três rotas possíveis, mutuamente exclusivas na prática:

| Rota | O que é | Reaproveita `web/` | Ordem de grandeza |
|---|---|---|---|
| **A. Responsiva + PWA** | o mesmo `portalsas.online`, usável no celular e instalável na tela inicial | ~100% | dias |
| B. Capacitor | o mesmo React embrulhado num app nativo (loja, push) | ~95% | semanas |
| C. Expo / React Native | app nativo, base de código separada | ~0% da UI | meses |

**Escolhida: A.** As razões, em ordem de peso:

1. **Quem usa celular é o aluno, não o coordenador.** A área do aluno é ficha,
   gráfico e chat — cabe em tela estreita. As telas de coordenação são tabelas
   densas de ~900 alunos com colunas por matéria ([TabelaPainel.tsx](../web/src/telas/Painel/TabelaPainel.tsx));
   isso não vira celular, vira outro produto. Rota A permite tratar as duas
   coisas com prioridades diferentes; B e C obrigam a portar tudo.
2. **O trabalho já começou.** Das 13 folhas de estilo, 7 já têm media query —
   12 de largura (mais 3 de `@media print`) e um `env(safe-area-inset-bottom)`.
   É terminar, não começar.
3. **LGPD (regra 6 do [CLAUDE.md](../CLAUDE.md)).** São dados de menores. Rota A
   não acrescenta nenhum terceiro. B e C acrescentam loja, build na nuvem do
   fornecedor e SDKs nativos — cada um é uma superfície nova a justificar.
4. **Push notification não é requisito hoje.** É o único motivo real para B; o
   canal de aviso ao aluno já é e-mail ([12-plano-p2-motor-lembretes.md](12-plano-p2-motor-lembretes.md)).

**O que reabre a decisão:** exigência de app na loja, ou push como requisito de
produto. Nesse caso a rota é B (Capacitor), não C — a rota A feita direito é
pré-requisito das duas, então nada deste trabalho se perde.

---

## 2 — Ferramental instalado

### Skills (versionadas em `.claude/skills/`)

| Skill | Origem | Para quê |
|---|---|---|
| `frontend-design` | [anthropics/skills](https://github.com/anthropics/skills) | direção visual ao redesenhar tela — tipografia, hierarquia, layout |
| `web-design-guidelines` | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | revisar UI contra 103 regras (toque, safe-area, foco, formulário) |

Ambas foram **copiadas para o repositório** em vez de instaladas globalmente
(`npx skills add -g`): assim a régua fica versionada, o diff de uma mudança de
régua aparece no git, e quem clonar o repo recebe a mesma revisão.

`web-design-guidelines` teve o `SKILL.md` alterado de propósito: o original
busca as regras por HTTP a cada revisão, o que torna o resultado dependente de
rede e não reprodutível. As regras agora vivem em
[`.claude/skills/web-design-guidelines/regras.md`](../.claude/skills/web-design-guidelines/regras.md),
baixadas em 22/08/2026. Atualizar = rebaixar o arquivo e commitar o diff.

### MCP

| Servidor | Estado | Observação |
|---|---|---|
| `chrome` (já existia) | **funcional** | é a ferramenta principal desta rota |
| `mobile` (novo) | **inerte** | sobe e expõe 27 ferramentas, mas não enxerga aparelho nenhum |

O `chrome` já fazia tudo que a rota A precisa — faltava usá-lo assim. O
`--viewport 1440x900` do [.mcp.json](../.mcp.json) é só o padrão de abertura; a
ferramenta `emulate` aceita `390x844x3,mobile,touch`, além de throttle de rede
(`Slow 3G`…`Fast 4G`), CPU e user-agent. **Armadilha conhecida:** o
`performance_start_trace` às vezes ignora o throttle do `emulate`
([issue #1955](https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/1955)) —
confira no relatório se o trace saiu realmente throttled.

O `mobile` ([mobile-next/mobile-mcp](https://github.com/mobile-next/mobile-mcp))
existe para o que o Chrome **não** cobre: o Safari do iOS de verdade — `100vh`
com a barra de endereço, `env(safe-area-inset-*)` no notch, zoom ao focar
input, teclado empurrando o layout do chat. Nada disso o Chrome emula com
fidelidade.

**Ele não funciona nesta máquina ainda.** Verificado em 22/08: o handshake
responde, as 27 ferramentas aparecem, e `mobile_list_available_devices` devolve
`{"devices":[]}`. Falta:

- **iOS** — só o Command Line Tools está instalado (`xcode-select -p` →
  `/Library/Developer/CommandLineTools`), e `simctl` não existe nele. O
  Simulator vem no **Xcode completo**, da App Store (~10 GB).
- **Android** — sem `adb`; precisa do Android Platform Tools + um emulador.

Enquanto isso, ele fica no `.mcp.json` sem atrapalhar: não achar aparelho é uma
resposta vazia, não um erro que derruba a sessão.

> **Proibido:** as ferramentas `mobile_login_to_cloud_provider` e
> `mobile_list_remote_devices` alugam aparelho em nuvem de terceiro. Não usar
> com dado real de aluno — é a mesma regra 6 do [CLAUDE.md](../CLAUDE.md) que
> tirou as fontes do Google.

---

## 3 — Auditoria de partida (22/08/2026)

Feita contra o dev server em `localhost:8080`, com `emulate` em
`390x844x3,mobile,touch` (iPhone 14) e `360x640x2` (Android comum).

### Cobertura — leia antes de confiar nos números

| O que | Como foi visto |
|---|---|
| Tela de login | **no browser**, medida e fotografada |
| Todo o resto | **só análise estática** do CSS/TSX |

As telas atrás do login **não foram abertas**. Autenticar exigiria ou alterar a
senha de uma conta no banco, ou emitir um JWT — as duas coisas foram barradas, e
com razão, por serem mexidas em credencial. Para destravar, ver a
[§5](#5--o-que-falta-para-completar-a-auditoria).

### O que a tela de login mostra

O login é o pior caso e o mais importante: é a primeira tela de todo aluno, e é
a única pública. Ele **não tem uma única media query** — `login.css` tem zero.

O layout é `grid-template-columns: 5fr 6fr` ([login.css:24](../web/styles/login.css#L24)),
duas colunas que nunca colapsam. Como item de grid nasce com `min-width: auto`,
as colunas se recusam a encolher abaixo do próprio conteúdo — e cada uma carrega
112px e 104px de padding lateral ([login.css:35](../web/styles/login.css#L35),
[:321](../web/styles/login.css#L321)). Resultado medido:

| Largura | Transbordo horizontal | Efeito |
|---|---|---|
| 390px (iPhone 14) | **+32px**, 36 elementos fora da viewport | painel azul cortado, texto quebrando uma palavra por linha |
| 360px (Android) | **+47px** | a coluna do formulário começa em **x = −46px** (sai da tela à esquerda); o formulário fica com 236px e o painel azul come 29% do visor |

Outros achados na mesma tela:

| Achado | Onde | Por que importa no celular |
|---|---|---|
| `input` com `font-size: 14px` (matrícula e senha) | [login.css](../web/styles/login.css) | Safari do iOS **dá zoom sozinho** ao focar input com fonte < 16px, e não volta |
| Botão do olho da senha: **23×23px**, sem nome acessível | `.lp-field__eye` | mínimo de toque é 44×44; e o Lighthouse acusa `button-name` |
| Link "Criar minha senha": 17px de altura | `.lp-first-access` | idem |
| `min-height: 100vh` | [login.css:9](../web/styles/login.css#L9), [base.css:17](../web/styles/base.css#L17) | no Safari do iOS `100vh` ignora a barra de endereço e corta o rodapé; hoje se usa `100dvh` |
| Sem `<main>`, contraste insuficiente em 3 elementos | — | Lighthouse mobile: **acessibilidade 82** |

Lighthouse mobile no `/login`: acessibilidade **82**, boas práticas **100**,
SEO **83**, CLS 0,057. (`robots.txt` e `meta description` também falham, mas
isso é artefato do dev server do Vite devolvendo `index.html` para tudo —
não vale como achado.)

### O que a análise estática mostra do resto

**6 das 13 folhas de estilo não têm nenhuma media query** — e são justamente as
das telas centrais:

| Folha | Media queries |
|---|---|
| `login.css`, `painel.css`, `simulados.css`, `filtros.css`, `auditoria.css`, `edicao.css` | **0** |
| `layout.css` | 6 |
| `aluno.css` | 4 |
| `chat.css` | 3 |
| `aluno-ficha.css` | 2 |

Padrões ausentes no projeto inteiro (`web/styles/*.css`):

| Padrão | Ocorrências | Consequência |
|---|---|---|
| `touch-action: manipulation` | **0** | atraso de ~300ms no toque por causa do duplo-toque-zoom |
| `-webkit-tap-highlight-color` | **0** | flash cinza do Android em cada toque |
| `overscroll-behavior: contain` | **0** | rolar dentro do chat/diálogo arrasta a página atrás |
| `env(safe-area-inset-*)` | **1** ([aluno.css:228](../web/styles/aluno.css#L228)) | conteúdo sob o notch e a barra de gestos do iPhone |
| `<meta name="theme-color">` | **0** | barra do navegador não acompanha a identidade |
| `manifest.webmanifest` | **0** | não dá para instalar na tela inicial — é o "P" de PWA |

**Tabelas:** 11 arquivos usam `<table>`, com 4 a 14 colunas.

> ⚠️ **Corrigido em 22/08, depois do mapa completo do front.** A primeira
> versão deste parágrafo dizia que "cinco folhas embrulham em `overflow-x:
> auto`". É verdade sobre as folhas e **enganoso sobre as tabelas**: das 6
> ocorrências da propriedade, só **duas** são wrapper de tabela —
> `.painel-tabela-wrap` ([painel.css:16](../web/styles/painel.css#L16)) e
> `.heatmap__container` ([layout.css:942](../web/styles/layout.css#L942)). As
> outras quatro são o calendário, o artefato do chat, o preview do agendamento
> e um `overflow-x: hidden`. A cobertura real é bem menor do que o número
> sugeria — contar propriedade não é contar tabela.

Todas as demais usam `.data-table { width: 100% }`
([layout.css:782](../web/styles/layout.css#L782)) direto dentro de
`.section`/`.card`, sem wrapper de rolagem: em tela estreita espremem ou
estouram. E `aluno.css:207` usa `overflow-x: hidden`, que **não** é a mesma
coisa que `auto`: esconde o transbordo em vez de deixar rolar, e o conteúdo
fica inalcançável.

Rolar lateralmente uma tabela de ~900 linhas × N matérias também não é uma tela
de celular, é uma tela de desktop apertada. Ver [§4](#4--backlog), item 6, e o
plano em [20 §P5](21-plano-mobile.md#p5--coordenação-o-casco-antes-das-tabelas).

---

## 4 — Backlog

Ordem de execução, com o critério: primeiro o que todo aluno vê, depois o que
o aluno usa, e por último o coordenador (que continua no desktop).

| # | O quê | Por quê agora |
|---|---|---|
| 1 | **Login colapsar em uma coluna** abaixo de ~760px — `grid-template-columns: 1fr` e `minmax(0, …)` nas colunas; decidir se o painel azul vira topo curto ou some | primeira tela de todo aluno, e hoje está quebrada |
| 2 | **`font-size: 16px` em todo `input`/`select`/`textarea`** | mata o zoom automático do Safari, que é o defeito mais notado por quem usa |
| 3 | **Alvos de toque ≥ 44×44** e `aria-label` no botão do olho | acessibilidade e Lighthouse; o olho hoje tem 23px |
| 4 | **`100vh` → `100dvh`** nas duas ocorrências | rodapé cortado no Safari |
| 5 | **Base de toque**: `touch-action: manipulation`, `-webkit-tap-highlight-color`, `overscroll-behavior: contain` nos diálogos e no chat, `env(safe-area-inset-*)` no que é full-bleed | uma passada de CSS resolve um conjunto grande de irritações |
| 6 | **Área do aluno tela a tela** a 390px: ficha, evolução, chat com teclado aberto | é o produto que vai para o celular |
| 7 | **PWA**: `manifest.webmanifest`, ícones, `theme-color`, `vite-plugin-pwa` | instalar na tela inicial; nenhum terceiro envolvido |
| 8 | **Telas de coordenação**: decidir por tela entre rolagem lateral (o que já existe) e um modo cartão | é decisão de produto, não de CSS — e o coordenador não é usuário de celular hoje |
| 9 | Rodar `web-design-guidelines` sobre `web/src` e `web/styles` | pega o que esta auditoria não olhou (foco, formulário, i18n) |

Itens 1–5 são mecânicos e verificáveis com o `chrome` MCP sozinho. O 6 depende
de login (§5). O 8 depende de conversa com a coordenação.

---

## 5 — O que falta para completar a auditoria

| Bloqueio | Como destravar |
|---|---|
| **Telas atrás do login não auditadas** | uma conta de aluno e uma de coordenação de teste, no banco local, com senha conhecida — ou autorização explícita para criá-las/emitir um JWT de dev |
| **Safari do iOS não verificado** | instalar o **Xcode completo** (App Store, ~10 GB); o `mobile` MCP passa a enxergar o Simulator sozinho |
| **Chrome do Android não verificado** | Android Platform Tools + um AVD |

Os artefatos desta auditoria (capturas e o relatório do Lighthouse) ficam em
`.auditoria-mobile/`, fora do git.

---

## 6 — Regras que passam a valer

1. **Nada de terceiro no front, incluindo em mobile** — sem CDN de ícone, sem
   fonte remota, sem SDK de push de fornecedor, sem aparelho em nuvem com dado
   real. É a regra 6 do [CLAUDE.md](../CLAUDE.md), e ela não afrouxa porque a
   tela ficou menor.
2. **Toda tela nova nasce medida a 390px** antes de virar PR. O custo é uma
   chamada de `emulate` + um screenshot.
3. **A régua é `regras.md`**, versionada. Mudou a régua? Vira commit.
