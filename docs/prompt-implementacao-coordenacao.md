# Prompt de implementação — a coordenação nova

Cole o bloco abaixo numa sessão de Claude Code **na raiz do repositório**.

⚠️ **Antes de colar, faça duas coisas:**

1. Rode `/design-login` uma vez, para a sessão conseguir ler o canvas do Claude
   Design pelo MCP `claude_design`. Sem isso o desenho não entra.
2. Confira `git status`. Hoje a árvore tem trabalho não commitado (o sprint do
   onboarding do aluno). Esta refatoração toca `web/styles/` inteiro e vai
   conflitar — feche o que está aberto, ou aponte a branch de onde partir.

O desenho vive em
`https://claude.ai/design/p/a8bf25f7-1c37-499e-bc9b-ed5f21a4f12e`
(arquivo `Coordenação.dc.html`, que importa `support.js`).

---

```
Você vai implementar, no repositório real, a refatoração visual da COORDENAÇÃO
do SAS: estender a ela o sistema de design que hoje só a área do aluno tem.

# COMO COMEÇAR — você não tem nada disto em contexto

Esta é uma sessão nova. Todo o desenho foi decidido em outra conversa e mora em
documentos deste repositório. ANTES de escrever uma linha de código:

1. Leia, nesta ordem: `CLAUDE.md`, `web/CLAUDE.md`,
   `docs/brief-claude-design-coordenacao.md` (é O documento deste trabalho — as
   sete regras que substituem o semáforo e as cinco do padrão de campo estão
   lá), `docs/03-design-system.md` (o sistema ANTIGO, que você está
   substituindo — leia para saber o que morre) e `docs/19-roadmap.md`.

2. Abra e leia com os próprios olhos, porque o código vence qualquer documento:
   - `web/styles/aluno-tokens.css` — o sistema que você vai estender
   - `web/styles/tokens.css` e `web/styles/layout.css` — o que vai ser trocado
   - `web/src/componentes/layout/` — o casco
   - `web/src/telas/Aluno/Estudar.tsx` e `pecas/CabecaDoCampo.tsx` — o padrão
     de campo, com os comentários que explicam por que ele funciona
   - `web/src/exportacao/` e o `LEIA-ME.md` de lá

3. Leia o canvas do Claude Design pelo MCP `claude_design`:
   projeto `a8bf25f7-1c37-499e-bc9b-ed5f21a4f12e`, arquivos `Coordenação.dc.html`
   e `support.js`. Se o MCP recusar por falta de autorização, PARE e me peça
   para rodar `/design-login` — não invente o desenho.

4. Rode os testes ANTES de mexer em qualquer coisa, para saber qual é a linha de
   base. Se algo já estiver vermelho, me diga antes de continuar.

5. Só então me apresente um plano, PR a PR, e espere eu aprovar.

# O DESENHO: o que é autoridade e o que não é

O canvas do Claude Design é **autoridade visual**: paleta, medida, hierarquia,
densidade, os estados de cada peça. Onde ele e o brief discordarem em COR, FORMA
ou MEDIDA, o canvas vence.

Onde eles discordarem em COMPORTAMENTO, REGRA DE PRODUTO ou VOCABULÁRIO, o
`docs/brief-claude-design-coordenacao.md` vence — e você me avisa que houve
divergência, em vez de escolher calado.

O código do canvas é REFERÊNCIA DE MARCAÇÃO E CSS, não código para colar. Ele
pode vir com nomes em inglês, classes próprias, dados inventados e dependências.
**Nada disso entra.** Você reescreve como componentes deste projeto, aproveitando
a estrutura visual, as medidas e o CSS adaptado às nossas classes e tokens.

## A stack, e ela não muda

    React 19 + TypeScript, empacotado por Vite
    react-router-dom 7 — rotas de verdade, nunca navegação por estado
    @tanstack/react-query 5 — todo dado de servidor passa por hook
    Biome — lint (NÃO é ESLint; o typescript-eslint recusa TS ≥ 7)
    Vitest — testes, sobre `src/dominio/`
    CSS puro em `web/styles/`, um arquivo por tela. SEM CSS Modules, SEM
      Tailwind, SEM qualquer framework de utilitário.

⚠️ **Não instale dependência nenhuma.** Se o canvas precisar de uma biblioteca,
o desenho é que se reescreve. Gráfico é SVG à mão — é decisão registrada, e
`web/src/componentes/ui/` já tem sete deles para você copiar o estilo.

# A REGRA CENTRAL: isto é REFATORAÇÃO, não reescrita

A coordenação está EM PRODUÇÃO, com usuários reais e dados de menores de idade.
Nada de comportamento pode mudar por acidente. Cada PR é uma troca de pele que
preserva o que a tela fazia — **exceto** nesta lista, que é o que muda DE
PROPÓSITO:

1. O semáforo verde/âmbar/vermelho sai da tela inteira (as sete regras do brief).
2. `toneMedia` em `web/src/telas/Painel/Painel.tsx` DESAPARECE. Ela é um
   ternário fixo (≥7 verde, ≥5 âmbar) que não tem relação com o corte em uso,
   enquanto a célula logo abaixo usa o corte de verdade — duas réguas na mesma
   tela. Não a substitua por outra função de cor: não sobra cor para ela.
3. Toda tabela de aluno passa a abrir ordenada por DISTÂNCIA DO CORTE,
   ascendente, com o ordenador nomeado no cabeçalho (regra R6).
4. Administração deixa de ser quatro abas e vira quatro campos.
5. Ficha de ciclo deixa de ser uma rolagem e vira três campos.
6. O Painel ganha a faixa de entrada e perde dois estratos, por fusão.
7. Passa a existir tema escuro.
8. As fichas ganham coluna lateral de 320px; Painel, Alunos e Banco não têm.

Fora dessa lista: mesma URL, mesmo dado, mesma permissão, mesmo texto, mesmo
atalho de teclado, mesmo comportamento de filtro. Se você achar que algo mais
precisa mudar, **pergunte** — não decida sozinho.

# A ORDEM — nove PRs, e a ordem tem motivo

Um PR por vez, cada um verde nos portões antes do seguinte. Não junte dois.

## PR 1 · A pilha de tokens (sem mudança visual nenhuma)

Cria `web/styles/paleta.css` (os hexadecimais, uma vez cada, sem semântica) e
`web/styles/papeis.css` (os seis papéis, os três blocos de tema). Reescreve
`tokens.css` e `aluno-tokens.css` como ALIASES dos papéis.

⚠️ **Este PR não pode mudar um pixel.** É o portão que prova que a pilha está
certa: se algo mudar de aparência aqui, o mapeamento está errado. Verifique com
screenshot antes/depois no MCP `chrome`, nas cinco telas principais.

## PR 2 · A paleta de documento

Cria `web/styles/documento.css` com `--doc-*`: paleta clara FIXA, que não
responde a tema. Aponta `web/src/exportacao/*.js` para ela.

⚠️ **Vem ANTES do tema escuro, nunca depois.** Os três geradores leem
`--color-navy`, `--color-bg`, `--color-text-primary` etc. em tempo de execução
para montar o nó fora da tela. No dia em que `--color-*` responder ao tema, o
coordenador que trabalha à noite gera um dossiê preto.

Pronto quando: gere um dossiê de aluno e um panorama de ciclo antes e depois do
PR e compare — têm de ser idênticos.

## PR 3 · Superfície e forma

Borda no lugar de sombra (`--shadow-card` e `--shadow-float` morrem), três raios
em vez de quatro, a grade de fundo de 24px, a tecla de 3px no botão primário.
Toca `layout.css`, `casco.css` e o resto do CSS da coordenação.

## PR 4 · Magnitude e olho

Numeral de KPI em 800 com tracking negativo e tabular; o rótulo de KPI vira o
olho de 10px em caixa alta espaçada. Toca `componentes/ui/Kpi.tsx` e o CSS.

É o ganho mais barato do projeto — a Plus Jakarta Sans já carrega o peso 800,
declarado em `fontes.css`. Nenhum asset novo, e não pode entrar nenhum
(regra 6 do CLAUDE.md, dados de menores).

## PR 5 · O fim do semáforo

As sete regras R1–R7 do brief. Preenchido/vazado, a régua de ouro, a intensidade
por distância, o alerta só na etiqueta, a referência cinza.

⚠️ **NÃO mexa no backend.** `Severidade` e `TomNota` continuam sendo
`'verde' | 'ambar' | 'vermelho'` vindos de `api/app/stats/criterios.py`, que os
calcula a partir do corte da régua em vigor — e isso está certo. O que muda é o
que o front DESENHA com eles:

    verde     → preenchido, saturação alta
    ambar     → preenchido, saturação baixa
    vermelho  → vazado + etiqueta de distância
    cinza     → sem dado

Renomear no backend é limpeza posterior e não é deste trabalho.

⚠️ **Não reimplemente a régua em TypeScript.** `dominio/criterios.ts` só
CONSULTA o que o servidor já resolveu. A Sprint 2 proibiu isso depois de a mesma
regra existir em três lugares e divergir, e ela já voltou uma vez escrita no TSX.

## PR 6 · A ordenação por distância do corte (R6)

A regra vai para `web/src/dominio/`, como função pura com teste ao lado — é
regra de negócio, e é o que `npm test` cobre. Veja `dominio/painel.ts` e
`componentes/ui/ordenacao.ts` para escolher onde encaixa.

É o PR que mais muda o produto, e não só a pele: sem ele, tirar a cor deixa a
varredura sem mecanismo. Merece PR próprio e revisão minha.

## PR 7 · O tema escuro

Só depois de 2 e 5, senão é retrabalho. Inclui o seletor de tema para a
coordenação, os sete gráficos SVG e as rampas do heatmap.

Pronto quando: as catorze superfícies abrem nos dois temas sem contraste
reprovado e sem cor cravada em hexadecimal fora de `paleta.css`.

## PR 8 · As telas que mudam de estrutura

Nesta ordem, e uma por vez:

    a) Administração  — quatro abas viram quatro campos (o caso mais limpo;
                        faça primeiro, é ele que ensina o padrão ao código)
    b) Ficha de ciclo — três campos: Calibração, Régua, Comparação
    c) Painel         — a faixa de entrada + a fusão dos quatro estratos em dois
    d) Ficha do aluno — a coluna lateral e a barra de corte do aluno reusada
    e) Login          — a fachada de cobogó, conversando com o login do aluno

⚠️ A fusão do Painel mexe na `BarraFiltros`, que **mede a si mesma** para
colapsar quando passa de uma linha. Mantenha a pílula com altura fixa, e ao
acrescentar grupo **passe `resumo`** — é ele que impede um filtro em vigor de
ficar invisível quando a faixa fecha. Helpers em `dominio/filtros.ts`.

⚠️ A `tela` que a faixa recebe é a SUPERFÍCIE, não a rota
(`provas.ciclos` ≠ `provas.simulados`).

## PR 9 · Limpeza

Some com os aliases `--color-*` que não têm mais uso, apaga o CSS órfão, e
corrige os documentos na passagem (seção "A entrega").

# O QUE NÃO TOCAR

- **`web/src/exportacao/`** — os três `.js` que montam DOM à mão são geradores
  de documento, não UI reativa, e o layout de impressão é sensível a estrutura.
  Está justificado em `src/exportacao/LEIA-ME.md`. Você aponta os tokens deles
  para `--doc-*` no PR 2 e não faz mais nada ali.
- **O backend**, exceto se eu pedir. Nenhuma migration, nenhuma rota, nenhum
  schema. Esta refatoração é de front.
- **As rotas antigas que redirecionam** (`/simulados`, `/ciclos`) — estão em
  link salvo e em e-mail de lembrete.
- **`APP_ENV` e o guard de configuração** — default `production`, falha fechado.
- **A abertura do rail por CSS** (`:has(.rail:hover)`, `:focus-within`). Um
  `useState` ali remontaria a árvore a cada passada de mouse.
- **O formatter do Biome, que está desligado.** Ligá-lo reformataria o
  repositório inteiro num diff que ninguém revisa.

# CONVENÇÕES QUE NÃO SE NEGOCIAM

- **Português em tudo**: arquivo, função, variável, classe CSS, coluna.
- **Comentário explica o PORQUÊ, não o quê** — e cita a fonte
  (`docs/brief-claude-design-coordenacao.md §R6`). É o padrão do projeto
  inteiro; ao editar, mantenha o que já está lá.
- `async def` e type hints se você por acaso encostar no backend.
- **Nenhum `fetch` em componente.** Leitura por `hooks/consultas.ts`, escrita
  por `hooks/mutacoes.ts`.
- **Classes compartilhadas ficam globais** (`.card`, `.tone-*`, `.btn`); só o
  CSS de prefixo próprio da tela vira arquivo próprio.
- **A tela não monta `<main>`** — quem monta é o casco. Dois `<main>` é HTML
  inválido e o leitor de tela anuncia duas regiões principais.
- `useTituloDaTela(...)` é hook: chame ANTES de qualquer `return` antecipado.
- `tipos/dominio.ts` espelha `api/app/schemas/domain.py`. Não divirja.

# PISO DE QUALIDADE — os portões de cada PR

    cd web && npm test && npm run lint && npm run typecheck
    cd api && ./.venv/bin/python -m pytest tests/ -q
    cd api && ./.venv/bin/ruff check .

Os testes da API entram mesmo num PR de front: é o que prova que você não mexeu
onde disse que não ia mexer.

E, para cada tela que você tocar, ANTES de passar para a seguinte:

- abra no MCP `chrome`, **nos dois temas**, em 1440×900 e em 390×844;
- rode a skill `web-design-guidelines` contra ela (103 regras de toque,
  safe-area, foco e formulário; as regras estão em `regras.md` dentro do
  diretório da própria skill);
- confira `list_console_messages` e `list_network_requests` — erro de console e
  requisição repetida denunciam hook mal escrito.

⚠️ Isto não é zelo. O sprint mobile achou **três defeitos que nenhuma leitura de
CSS pegaria**, porque só existem em runtime: um `display:flex` do login vazando
para o app inteiro, item de grid sem `min-width:0` escondendo outro, e dois
gráficos com largura fixa apesar do `viewBox`.

# AS FERRAMENTAS, E COMO ENTRAR NO APP

`docker compose up` sobe front em :8080, API em :8000, postgrest em :3000.

⚠️ O `docker` do PATH está quebrado nesta máquina (symlink para um
`/Volumes/Docker/` que não existe). O binário real é
`/Applications/Docker.app/Contents/Resources/bin/docker`.

⚠️ **Para ver a coordenação no browser você precisa de login de coordenação.**
O banco local tem `dev@local` (Dev QA), mas a senha não está em documento nenhum
— **peça a mim**, não tente adivinhar. Sem ela você não verifica nada e vai
acabar deduzindo do TSX, que é exatamente o que este projeto proíbe.

Outras ferramentas ligadas neste repositório:

- MCP `postgres`, em modo leitura, apontando para o Postgres do compose. Use
  para conferir volume antes de mexer em tabela grande — **não existe paginação
  em lugar nenhum** e `PGRST_DB_MAX_ROWS` foi deixado sem valor de propósito.
- MCP `mobile`: **hoje não enxerga aparelho nenhum** (falta o Xcode completo, o
  `simctl` não vem no Command Line Tools). Se precisar de Safari real, registre
  como não verificado em vez de tentar. E nunca use aparelho em nuvem com dado
  real de aluno.
- Skill `frontend-design`: quando o canvas não cobrir uma decisão — um estado
  vazio que ninguém desenhou, um erro, uma densidade —, use-a em vez de
  inventar, para o que você acrescentar continuar parecendo o mesmo produto.
- O hook `PostToolUse` roda Biome ou ruff no arquivo que você acabou de editar e
  devolve o resultado na hora. Se reclamar, conserte antes de seguir.

# COMO TRABALHAR

Um PR por vez, na ordem acima. Para cada um:

1. Branch própria a partir de `main`.
2. Implementa, com os portões verdes.
3. Verifica no browser, nos dois temas e nos dois tamanhos.
4. Me mostra antes/depois em screenshot e espera eu aprovar antes do próximo.

Não abra o PR 2 antes de o 1 estar aprovado. A pilha de tokens é a fundação:
errar nela e descobrir no PR 7 custa reescrever sete PRs.

# A ENTREGA

Além do código, escreva `docs/37-plano-refatoracao-visual-coordenacao.md`, no
formato dos planos deste repositório (veja `docs/33-plano-polimento-coordenacao.md`
como modelo): §0 levantamento, §1 ordem, um § por PR com "o que muda / arquivos /
pronto quando", §riscos, §decisões, §verificação.

E corrija, na passagem, os documentos que esta refatoração torna falsos — é
convenção do projeto, e o `CLAUDE.md` mantém uma tabela de "onde os documentos
mentem". No mínimo estes:

- `docs/03-design-system.md` — descreve o sistema que você está substituindo.
  A tabela de cor semântica, a escala tipográfica e a seção de sombras ficam
  falsas no PR 3. Ou reescreva, ou aponte para o brief e marque como histórico.
- `web/CLAUDE.md` — afirma que `telas/Banco/` "serve os dois cascos". Não serve
  mais: o aluno tem `telas/Aluno/EstudarBanco.tsx`, uma reimplementação, e
  `perfil="aluno"` em `Banco.tsx` virou código morto. Registre isso — é a
  evidência de que a falta de espinha comum já custou um produto construído duas
  vezes, e é o argumento para reunificá-lo depois.
- `docs/19-roadmap.md` — é o único documento que diz o que está feito. Se ele
  não registrar esta refatoração, ela não aconteceu.

⚠️ O documento tem de ser verdadeiro, não otimista. Se um PR ficou pela metade,
ele diz isso. Se uma tela não foi verificada no browser porque faltou login, ele
diz isso. Um plano que esconde buraco é pior que nenhum, porque o próximo a
mexer confia nele.
```
