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

## O casco: rail de rótulos, não topbar de abas

`componentes/layout/` monta rail (5 destinos) + topbar + `<main>`. O que se
descobre errando:

- **O rail NÃO abre.** Eram 88px que viravam 228px no `:has(.rail:hover)` do
  CSS; a decisão 7 do docs/39 o fixou em **252px, com o rótulo sempre**. O
  custo (−164px de largura em toda tela, o tempo todo) está aceito e escrito em
  `Rail.tsx`. Não há estado nenhum ali além da sessão. O **Sair** desceu do
  avatar da topbar para o rodapé do rail.
- **A topbar é migalha + tema + identidade, e nada mais.** A **busca global e o
  sino SAÍRAM** (docs/39 §1, decisão 5): o sino apontava para `#alertas`, que
  no Painel novo é quase a tela inteira, e a busca de navegação competia com a
  `<Busca>` da `BarraFiltros`. A pílula de identidade é PLACA, não botão. A
  âncora `#alertas` continua de pé para link salvo e e-mail — não a remova.
- **Não existe mais sidebar de filtros, e agora não há exceção.** `PainelFiltros`,
  `Sidebar` e `rotas.ts::sidebarPara` foram apagados. Filtro é `BarraFiltros` —
  faixa horizontal de `.pill` acima da tabela — nas **nove** superfícies:
  `alunos`, `provas.ciclos`, `provas.simulados`, `ciclo` (a ficha, que ganhou a
  tabela do Painel), `banco`, `auditoria`, `administracao`, `cantina.direitos`
  e `integracoes.aulas`. **O Painel não é uma delas** — perdeu a faixa inteira
  na fase 2 do docs/39.
  - A faixa **colapsa sozinha quando o conteúdo passa de uma linha**, com o
    resumo do que está ativo no lugar, e lembra a escolha por superfície. Ao
    acrescentar um grupo, **passe `resumo`**: é ele que impede um filtro em
    vigor de ficar invisível quando a faixa fecha. Os helpers estão em
    `dominio/filtros.ts`.
  - A `tela` que a faixa recebe é a SUPERFÍCIE, não a rota (`provas.ciclos` ≠
    `provas.simulados`).
  - Na ficha de ciclo ela também carrega **régua, fase e ordenação** — o
    segundo estrato que era do Painel e desceu junto com a tabela. A régua é o
    caso mais caro, porque ela muda TODA a leitura da tela.
- **A tela não monta `<main>`.** Quem monta é o casco; a rota devolve
  `.tela`, que é só a coluna de blocos. Dois `<main>` na página é HTML
  inválido e o leitor de tela anuncia duas regiões principais.
- **Coluna lateral de 320px só em tela de LEITURA** (ficha do aluno). Alunos,
  Banco e a ficha de ciclo são de varredura: lá a tabela tem 14 colunas com o
  nome congelado, e 320px do lado direito saem da tarefa mais frequente do dia.

`/provas` é um **hub de duas portas**, não mais abas: as listas ganharam URL
própria em `/provas/ciclos` e `/provas/simulados`. Os caminhos antigos
`/ciclos` e `/simulados` continuam existindo como `<Navigate>` porque estão em
link salvo e em e-mail de lembrete — **não os remova**; e o mesmo vale para
`/ciclos/:id/regua`, cuja tela foi apagada e absorvida pela tabela do ciclo. Já
`/ciclos/:id` e `/simulados/:id` seguem sendo rotas de verdade.

**O Painel virou hub.** Três cartões de campo (`campo.css`) numa grade de 12
colunas mais a faixa de decisão, e mais nada: sem filtros, sem KPIs, sem busca
e sem tabela — ela desceu para `telas/CicloFicha/TabelaDoCiclo.tsx`. Por isso
`dominio/painel.ts` e as classes `.painel-tabela__*` de `ciclo.css` têm nome
que já não descreve onde moram; é herança, como `get_supabase()` no backend.

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
  - **Qual régua está em vigor também mora lá:** `REGUA_DA_CASA` e
    `reguaDaCasa(criterios)`. O slug `'tio-leo'` estava cravado em oito lugares
    e tinha ganhado DOIS nomes de constante na mesma refatoração; a varredura
    do docs/39 §6 juntou tudo. Toda tela sem seletor de régua chama
    `reguaDaCasa` — inclusive o resto honesto (`criterios[0]`) para quando o
    servidor renomear o slug.
- **Nenhum `fetch` em componente.** Leitura por hook de `hooks/consultas.ts`,
  escrita por `hooks/mutacoes.ts`.
- **Classes compartilhadas ficam globais** (`.card`, `.tone-*`, `.nota-badge`,
  `.btn`); só o CSS de prefixo próprio da tela vira módulo. Extração ao
  contrário trava.
- **A cor tem uma pilha de quatro arquivos, e a ordem é obrigatória**
  (docs/37, docs/39 §0): `paleta.css` (os hexadecimais, uma vez cada) →
  `papeis.css` (os seis papéis e os três blocos de tema) → `aluno-tokens.css`
  (`--alu-*`, que é alias) → `documento.css` (`--doc-*`), **por último**,
  porque o `@media print` dele remapeia a paleta e blocos `:root` têm a mesma
  especificidade.

  Eram cinco: `tokens.css` traduzia os papéis para um alias da coordenação
  (`--color-navy`, `--color-gold`, `--color-red`…) e morreu na fase 0 do
  docs/39, com as 1.067 leituras dele trocadas pelo papel. **A coordenação lê
  `--sas-*` direto.** Os nomes que não eram cor — raio, largura do rail, altura
  da topbar, `--font-family` — foram para `styles/forma.css`, fora da pilha,
  porque não respondem a tema.

  ⚠️ Nenhuma tela lê `--dia-*`, `--noite-*` direto: eles são matéria-prima.
  `dominio/tokensCss.test.ts` trava isso — e existe porque um `*/` perdido já
  comentou sete tokens sem o build reclamar: `var()` indefinido é descartado em
  silêncio. Ele também trava a cobertura do `@media print`: papel que a tela lê
  e o bloco de impressão não congela é **folha preta** para quem trabalha à
  noite, sem erro e sem aviso.
- **O semáforo não existe mais.** Acima do corte é preenchido, abaixo é vazado,
  a intensidade carrega a distância, e o vermelho fica só na etiqueta e na
  falha operacional. `dominio/selo.ts` faz a tradução; o backend continua
  mandando `'verde' | 'ambar' | 'vermelho'`, e isso está certo.
  - As `.tone-*` globais de `layout.css` estão neutralizadas (`color: inherit`),
    e `.tag.tone-*` virou contorno. ⚠️ **Dois seletores mais específicos ainda
    vencem essa regra e pintam:** `.gravacao__data.tone-*` em `integracoes.css`
    (a tarja de data de `/integracoes/aulas`, com verde, âmbar, vermelho e
    azul) e `.panorama__tag.tone-*` em `layout.css` (o panorama EXPORTADO do
    aluno). Os dois ficaram fora do docs/39 e estão registrados no §6 dele.
    Ao encostar em qualquer um, tire a cor — não copie o padrão.
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
  escuro do aluno — e **essa razão morreu em 05/09/2026**, quando o alias da
  coordenação passou a apontar para os mesmos papéis que `--alu-*` (docs/37
  §7.3) e, na fase 0 do docs/39, deixou de existir. Reunificá-las voltou a ser
  possível, e é trabalho próprio.

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
