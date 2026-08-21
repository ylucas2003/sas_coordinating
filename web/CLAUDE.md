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
  corte por matéria, reducer do streaming do chat — tudo isso é domínio, não
  componente. É o que `npm test` cobre.
- **Nenhum `fetch` em componente.** Leitura por hook de `hooks/consultas.ts`,
  escrita por `hooks/mutacoes.ts`.
- **Classes compartilhadas ficam globais** (`.card`, `.tone-*`, `.nota-badge`,
  `.btn`); só o CSS de prefixo próprio da tela vira módulo. Extração ao
  contrário trava.
- `tipos/dominio.ts` espelha `api/app/schemas/domain.py`. Mudou o schema
  Pydantic, mude aqui — é o que faz `turmaId` vs `turma_id` aparecer no build
  em vez de em runtime.

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
