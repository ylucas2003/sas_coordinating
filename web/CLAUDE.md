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

⚠️ **E há uma rota pública fora dos três cascos: `/conectar-ia`**, o
consentimento do OAuth do MCP (`telas/ConectarIa/ConectarIa.tsx`, docs/43
§5.3). Mora em `App.tsx`, FORA da `RotaProtegida`, carregada por `lazy()` e
com moldura própria. Desde 26/10 quem aprova uma conexão do claude.ai ou do
ChatGPT prova a posse do e-mail da conta de IA com um código de 6 dígitos — não
com login: a aba que a IA abre chega sem sessão, porque a sessão mora no
`sessionStorage`, que é por aba. Por isso a página **não lê a sessão e não chama
rota nenhuma que exija uma** (nem `/mcp/disponibilidade`): um 401 ali derrubaria
a pessoa no login. Os e-mails que aprovam se cadastram na tela de Conexões de
IA (`telas/Administracao/ConexoesDeIa.tsx`, seção "E-mails da sua IA"), que é
da coordenação logada, e só aprovam depois de confirmados ali, com o código que
chega a eles (docs/43 §5.6). Nos 400 e 429 o consentimento mostra a frase do
servidor (`fraseDoServidor`): não enumerar e-mail depende de o backend não
variar essas frases com o e-mail — não troque por texto que dependa dele. A volta genérica do login (`dominio/voltaDoLogin.ts`,
`/login?proximo=…`) continua valendo para qualquer rota protegida aberta em
aba nova.

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

## O chat: os cartões passam por três peças

O chat é um só para os dois cascos (`componentes/chat/Conversa.tsx`); o que
muda por casco é QUEM DESENHA o cartão. Três peças, e as três precisam andar
juntas (docs/43 §4.4, docs/27 §7):

- **`CATALOGO_DE_ARTEFATOS`** (`dominio/chatStream.ts`) — o catálogo FECHADO
  dos tipos que qualquer tool pode anexar no campo `artefato: {tipo, titulo?,
  payload}`: `barras_corte`, `questao`, `lista_questoes`, `prova`,
  `linha_temporal` e `histograma`. Espelha `TIPOS_DE_ARTEFATO` de
  `api/app/chat/ferramentas.py` (o escopo `aluno`), e
  `api/tests/test_chat_ferramentas.py` lê esta constante e reprova se as duas
  divergirem. Tipo fora dele é descartado JÁ AO VIVO, porque o servidor também
  não o grava — mostrar um cartão que some ao reabrir é pior do que não
  mostrar. Tipo novo é mudança nos dois lados E migration no CHECK de
  `chat_artefato` (como a 0070). `csv` e `navegacao` ficam fora de propósito:
  só nascem das tools próprias (`exportar_csv`, `navegar_para`), senão qualquer
  tool fabricaria um link.
- **`artefatosNaResposta`** (`dominio/chatStream.ts`) — o servidor pendura o
  artefato na mensagem `tool` que o produziu, e `Mensagem` não desenha mensagem
  `tool`: sem esta passagem, nenhum cartão aparece ao REABRIR a conversa. Quem a
  aplica é a própria `Conversa`, nos dois cascos (até 25/10 só a folha do aluno
  fazia, e o coordenador perdia o link do `navegar_para` a cada thread
  reaberta). Não reaplique em quem usa a `Conversa`.
- **A prop `renderArtefato`** de `Conversa` e `Mensagem` — quem desenha. O
  padrão é `renderArtefatoPadrao` (o `Artefato.tsx` da coordenação); a
  `FolhaTioLeo` passa `desenharArtefatoDoAluno`, que usa
  `telas/Aluno/TioLeo/ArtefatoAluno.tsx`, com cada cartão no próprio
  `LimiteDeErro` e com tela cheia. Payload que não bate aparece como falha,
  nunca some: `ArtefatoNaoRenderizavel` na coordenação, "Cartão não desenhado"
  no aluno (e "Cartão não abriu" quando o cartão quebra).

## `src/exportacao/` é JavaScript de propósito

Três arquivos `.js` montando DOM à mão no meio de um front todo em TSX. É
deliberado e está justificado em [src/exportacao/LEIA-ME.md](src/exportacao/LEIA-ME.md):
são **geradores de documento** (PDF via `window.print`, PNG via SVG→canvas,
CSV), não UI reativa — o nó é construído offscreen, consumido e descartado. O
layout de impressão é sensível a estrutura, então converter para JSX seria
risco sem ganho.

Não "modernize" essa pasta. (`pdf.ts` e `desenharFolha.ts`, de 24/10, são
TypeScript de propósito: não montam DOM — ver o LEIA-ME de lá.)

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
  - **A área do aluno tem DUAS notas contra o corte, e as duas estão certas**
    (decisão do dono de 26/10): a do último simulado (`/me/evolucao`, as barras
    da Hoje) e a que conta na régua (`/me/zona`, o cartão `barras_corte` do Tio
    Léo e a zona). `dominio/notaContraCorte.ts` decide qual o gráfico mostra e
    com que nome (`LEGENDA_DAS_NOTAS`, a prop `notas` de `BarraCorte`). Barra
    contra o corte sem nome volta a parecer contradição — e nunca misture as
    duas no mesmo gráfico.
- **Nenhum `fetch` em componente.** Leitura por hook de `hooks/consultas.ts`,
  escrita por `hooks/mutacoes.ts`.
- **Classes compartilhadas ficam globais** (`.card`, `.tone-*`, `.nota-badge`,
  `.btn`); só o CSS de prefixo próprio da tela vira módulo. Extração ao
  contrário trava.
- **No celular a tabela tem DUAS respostas, e a escolha é por tabela**
  (docs/21 §13, 07/09):
  - `.data-table--cartoes` — tabela CURTA e larga, onde a linha é um objeto com
    nome próprio (um ciclo, uma prova, uma conta). Abaixo de 760px cada linha
    vira cartão. O rótulo sai de **`data-rotulo` escrito à mão em cada `<td>`**,
    e a primeira célula leva `data-titulo` para virar o título. ⚠️ **Não derive
    o rótulo do `<thead>` em runtime**: casaria célula com coluna por índice, e
    é isso que quebra em silêncio quando alguém insere coluna no meio. Um
    `data-rotulo` faltando some da tela; um índice errado mente.
  - **rolagem lateral** — a caixa com `overflow` que cada tela de varredura já
    tem (`.alunos-caixa`, `.painel-tabela-wrap`, `.cant-grade-rolagem`,
    `.banco-estatisticas__tabela`) — para a tabela de VARREDURA: 900
    linhas × 14 colunas, onde a tarefa é comparar e a coluna congelada dá
    sentido à linha. Vira 900 cartões de 14 campos se você "converter". Só a
    LINHA sobe para 44px.
  - ⚠️ **Virar cartão esconde o `<thead>`, e com ele o único controle de
    ORDENAÇÃO.** Toda tabela ordenável que ganhar `--cartoes` precisa levar
    `<OrdenarNoCelular>` junto (`componentes/ui/TabelaOrdenavel.tsx`), com as
    mesmas `colunas`/`ordenacao`/`onOrdenar` do `<TheadOrdenavel>`.
  - ⚠️ **O bloco do cartão é `@media screen and (max-width: 760px)`.** Media
    query de largura casa NA IMPRESSÃO, e a largura que ela consulta é a área
    da página: A4 com margem de 14mm dá ~688px. Sem o `screen and`, o PDF da
    ficha do aluno sai como pilha de cartões e sem as colunas `data-secundario`.
    `documento.css` tem um `@media print` que desfaz isso por segurança.
- **⚠️ Bloco de celular vai DEPOIS da regra que ele sobrescreve, no arquivo.**
  `@media` **não** acrescenta especificidade: uma media query declarada antes da
  regra-base perde para ela, e o sintoma é a regra simplesmente não valer, sem
  erro. Aconteceu com `.painel-tabela__celula` (media na linha 573, base com
  `height: 42px` na 837). Conferir o arquivo inteiro, não só a vizinhança.
- **Transbordo horizontal ALARGA o viewport de layout, e o estrago não fica
  onde nasceu.** Com a página transbordando, `window.innerWidth` vai a 460 num
  visor de 390 e a barra inferior (`fixed; left: 0; right: 0`) nasce com 460px,
  metade fora da tela. Antes de acusar um elemento posicionado, compare
  `innerWidth` com `clientWidth` — e, ao caçar o culpado, **suba a árvore
  procurando ancestral que recorta**, senão você acusa a tabela que rola certo
  dentro da própria caixa.
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
