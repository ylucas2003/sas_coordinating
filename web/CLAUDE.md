# web — contexto para o Claude Code

Frontend React 19 + TypeScript + Vite. Estrutura, scripts e convenções em
[README.md](README.md), que está correto e atualizado — não repito aqui. O que
segue é o que só se descobre errando.

Contexto do repositório em [../CLAUDE.md](../CLAUDE.md).

## A migração acabou

`web/js/` **não existe mais**. Se algum documento (notadamente
[docs/16](../docs/16-plano-migracao-react.md)) falar em "árvore legada",
wrapper `<Legado>` ou hash router, está descrevendo o passado. Rotas são
caminhos reais (`/alunos/A023`), o login é a rota `/login`, e a entrada é uma
só: `index.html`.

## São TRÊS cascos, não dois

`App.tsx::RotaProtegida` monta um de três, por `sessao.tipo()`: a coordenação
(rail + topbar), o aluno (barra de quatro destinos) e — desde 05/09 — a
**cantina** (`telas/Cantina/CascoCantina.tsx`), que é marca, nome e sair, e
nada mais.

⚠️ Aquele `switch` era um ternário `aluno ? … : coordenação`, e o `else` só era
seguro enquanto existiam dois tipos. Hoje o default volta ao login: um
`sas_tipo` que esta versão não conhece não pode cair no casco mais poderoso
(docs/38 §1.1). O mesmo vale para o array `TIPOS` de `servicos/sessao.ts` —
tipo fora dele faz `tipo()` devolver `null` e a sessão nasce morta.

O login também são três portas em DOIS endereços: `/login` alterna aluno e
coordenação por um link no rodapé; `/login-cantina` é URL própria e não tem
travessia. O formulário de e-mail e senha é um só (`Login/FormularioSenha.tsx`),
usado pelas duas portas com senha.

## O casco: rail de ícones, não topbar de abas

`componentes/layout/` monta rail (5 destinos) + topbar (migalhas, busca, sino,
avatar) + `<main>`. Três consequências que se descobre errando:

- **Não existe mais sidebar de filtros, e agora não há exceção.** `PainelFiltros`,
  `Sidebar` e `rotas.ts::sidebarPara` foram apagados. Filtro é `BarraFiltros` —
  faixa horizontal de `.pill` acima da tabela — nas **oito** superfícies,
  inclusive o Banco, que tinha `<aside>` próprio até a Sprint de polimento
  (docs/33 §7). São oito e não sete porque `/provas` tem duas (Ciclos e
  Simulados, conforme `?aba=`) e `/integracoes/aulas` é uma delas.
  - A faixa **colapsa sozinha quando o conteúdo passa de uma linha**, com o
    resumo do que está ativo no lugar, e lembra a escolha por superfície. Ao
    acrescentar um grupo, **passe `resumo`**: é ele que impede um filtro em
    vigor de ficar invisível quando a faixa fecha. Os helpers estão em
    `dominio/filtros.ts`.
  - A `tela` que a faixa recebe é a SUPERFÍCIE, não a rota (`provas.ciclos` ≠
    `provas.simulados`).
  - No Painel ela também carrega **régua, fase e ordenação**, que eram um
    segundo estrato de recorte na linha do título. Cada um passa `resumo` — e a
    régua é o caso mais caro, porque ela muda TODA a leitura da tela.
- **Duas buscas, e elas não competem.** A da topbar é NAVEGAÇÃO — digite de
  qualquer tela, atalho `/`, e vá para a ficha do aluno. A da `BarraFiltros`
  (`<Busca>`) é RECORTE: peneira as linhas da tela em que você está. A primeira
  já existia e não estava documentada, o que fez o inventário do docs/25 §1.1
  concluir que faltava busca global.
- **A tela não monta `<main>`.** Quem monta é o casco; a rota devolve
  `.tela`, que é só a coluna de blocos. Dois `<main>` na página é HTML
  inválido e o leitor de tela anuncia duas regiões principais.
- **Coluna lateral de 320px só em tela de LEITURA** (ficha do aluno). Painel,
  Alunos e Banco são de varredura: lá a tabela tem 14 colunas com o nome
  congelado, e 320px do lado direito saem da tarefa mais frequente do dia.
- **Quem abre o rail é o CSS**, por `:has(.rail:hover)` e `:focus-within` —
  não um `useState`. Estado aqui remontaria a árvore a cada passada de mouse.

`/ciclos` e `/simulados` viraram abas de `/provas` (`?aba=simulados`). Os
caminhos antigos continuam existindo como `<Navigate>` porque estão em link
salvo e em e-mail de lembrete — **não os remova.** Já `/ciclos/:id` e
`/simulados/:id` seguem sendo rotas de verdade.

Migalha de ficha: a rota dá a trilha, a tela dá o nome da coisa aberta via
`useTituloDaTela(...)`. Ele é hook — chame **antes** de qualquer `return`
antecipado de carregamento ou erro.

## `src/exportacao/` é JavaScript de propósito

Três arquivos `.js` montando DOM à mão no meio de um front todo em TSX. É
deliberado e está justificado em [src/exportacao/LEIA-ME.md](src/exportacao/LEIA-ME.md):
são **geradores de documento** (PDF via `window.print`, PNG via SVG→canvas,
CSV), não UI reativa — o nó é construído offscreen, consumido e descartado. O
layout de impressão é sensível a estrutura, então converter para JSX seria
risco sem ganho.

Não "modernize" essa pasta.

## Onde cada coisa mora

- **Regra de negócio vai para `src/dominio/`**, como função pura, com teste ao
  lado (`*.test.ts`). Esquema de colunas ITA/IME, médias, cross-filtering,
  reducer do streaming do chat, a leitura em linguagem simples dos gráficos,
  o contexto de tela que o chat manda — tudo isso é domínio, não componente.
  É o que `npm test` cobre.
- **A régua de corte NÃO é regra daqui.** `dominio/criterios.ts` só *consulta*
  o que o servidor já resolveu (`cortes`, `corteGenerico`, `corteMedia`,
  `eliminatorias` vêm prontos de `_descrever_criterio`). Reimplementar o
  encadeamento em TypeScript foi exatamente o que a Sprint 2 proibiu, depois de
  a mesma regra existir em três lugares e divergir — e ela tinha voltado nos
  gráficos, com `corte={{ valor: 4 }}` escrito no TSX (docs/31 §P1).
- **Nenhum `fetch` em componente.** Leitura por hook de `hooks/consultas.ts`,
  escrita por `hooks/mutacoes.ts`.
- **Classes compartilhadas ficam globais** (`.card`, `.tone-*`, `.nota-badge`,
  `.btn`); só o CSS de prefixo próprio da tela vira módulo. Extração ao
  contrário trava.
- **A cor tem uma pilha de cinco arquivos, e a ordem é obrigatória**
  (docs/37): `paleta.css` (os hexadecimais, uma vez cada) → `papeis.css` (os
  seis papéis e os três blocos de tema) → `tokens.css` (`--color-*`) e
  `aluno-tokens.css` (`--alu-*`), que são só alias → `documento.css`
  (`--doc-*`), **por último**, porque o `@media print` dele remapeia a paleta e
  blocos `:root` têm a mesma especificidade.

  ⚠️ Nenhuma tela lê `--dia-*`, `--noite-*` direto: eles são matéria-prima.
  `dominio/tokensCss.test.ts` trava isso — e existe porque um `*/` perdido já
  comentou sete tokens sem o build reclamar: `var()` indefinido é descartado em
  silêncio.
- **O semáforo não existe mais.** Acima do corte é preenchido, abaixo é vazado,
  a intensidade carrega a distância, e o vermelho fica só na etiqueta e na
  falha operacional. `dominio/selo.ts` faz a tradução; o backend continua
  mandando `'verde' | 'ambar' | 'vermelho'`, e isso está certo.
- **O padrão de campo** (`componentes/ui/Campo.tsx`) é como uma tela pesada
  vira várias leves: divisão por PERGUNTA, subtítulo com dado vivo nos três
  estados, destino em tela inteira com URL própria, chevron de 44px na mesma
  linha do título, e o elo quieto que some quando está vazio **ou quando a
  consulta falha**. Está em Administração e na ficha de ciclo.
- `tipos/dominio.ts` espelha `api/app/schemas/domain.py`. Mudou o schema
  Pydantic, mude aqui — é o que faz `turmaId` vs `turma_id` aparecer no build
  em vez de em runtime. O mesmo vale para `tipos/banco.ts` ↔ `schemas/banco.py`.
- **⚠️ `telas/Banco/` NÃO serve mais os dois cascos.** A intenção era essa —
  `Banco.tsx` ainda recebe `perfil` —, mas o aluno tem
  `telas/Aluno/EstudarBanco.tsx`, uma reimplementação, e `perfil="aluno"` em
  `Banco.tsx` virou **código morto**.

  Vale registrar como custou: a falta de espinha comum fez o mesmo produto ser
  construído duas vezes. A razão declarada da duplicação era que a tela da
  coordenação é toda em tokens da coordenação e não sobreviveria ao tema
  escuro do aluno — e **essa razão morreu em 05/09/2026**, quando `--color-*`
  passou a apontar para os mesmos papéis que `--alu-*` (docs/37 §7.3).
  Reunificá-las voltou a ser possível, e é trabalho próprio.

## Ferramentas

```sh
npm run dev          # :8080 com HMR, proxy de /api para a API
npm test             # Vitest sobre src/dominio/
npm run typecheck    # tsc --noEmit
npm run lint         # Biome
npm run lint:fix
npm run lint:a11y    # só as regras de acessibilidade, sob demanda
```

**O linter é Biome, não ESLint.** Não é preferência: o projeto usa TypeScript 7
e o `typescript-eslint` recusa a rodar (`throw`, não aviso) em TS ≥ 7. O Biome
tem parser próprio em Rust e não depende do pacote `typescript`.

A regra que justifica o linter existir é `useExhaustiveDependencies` — o
equivalente do `react-hooks/exhaustive-deps`. Dependência faltando num
`useEffect`/`useMemo` produz tela com dado velho, sem erro no console, e o
`tsc` não pega. Configuração em [biome.json](biome.json).

**O formatter do Biome está desligado.** Ligá-lo reformataria o repositório
inteiro num diff gigante. Se quiser ligar, faça num commit isolado.

Regras deliberadamente rebaixadas, para o relatório não afogar o que importa:
`noNonNullAssertion` (o `!` é idioma daqui), `useButtonType`,
`noSvgWithoutTitle` (os gráficos são SVG decorativo), `useKeyWithClickEvents` e
`noStaticElementInteractions`. A dívida de acessibilidade que elas apontam é
real — `npm run lint:a11y` mostra ela inteira quando for a hora de encarar.

## Verificar no browser de verdade

O MCP `chrome` ([../.mcp.json](../.mcp.json)) abre o app rodando e dá acesso a
console, rede, trace de performance e screenshot. Para qualquer afirmação sobre
usabilidade, layout ou desempenho, use ele — não deduza da leitura do TSX.
