## 16 — Plano: migração do frontend para React

**Estado:** concluída. Todas as etapas (0 a 9) foram executadas — o frontend está inteiramente em React + TypeScript.

O que foi verificado, o que não foi e o que ficou pendente: [17-migracao-react-verificacoes.md](17-migracao-react-verificacoes.md).

## Contexto

O frontend em `web/` é hoje **JavaScript puro com ES modules**, sem build step: ~9.700 linhas de JS + ~5.900 de CSS servidas cruas por nginx (`COPY . /usr/share/nginx/html`). Toda a UI é construída com um helper caseiro `el(tag, attrs, children)` ([js/dom.js](../web/js/dom.js)), o roteamento é um hash router de 42 linhas ([js/router.js](../web/js/router.js)), e o estado vive em objetos locais com funções `rerender()` que limpam e remontam subárvores do DOM à mão.

Isso funcionou até aqui, mas custa caro nas telas grandes: [screens/painel.js](../web/js/screens/painel.js) tem 925 linhas misturando esquema de colunas ITA/IME, cross-filtering, cálculo de médias virtuais e construção de `<td>`; [components/chat/conversa.js](../web/js/components/chat/conversa.js) faz reconciliação manual de bolhas de streaming SSE; [main.js](../web/js/main.js) mantém um cache de DOM por rota (`telaCache`) que é invalidado por um `CustomEvent` global. São três reimplementações caseiras de coisas que React resolve de fábrica (reconciliação, estado derivado, cache de dados).

**Objetivo:** migrar para React + TypeScript sem regressão visual nem funcional, mantendo o app deployável em produção em todos os commits do caminho.

**Restrição importante:** a produção na VPS (`portalsas.online`) está sendo montada esta semana. O plano é desenhado para não bloquear esse lançamento — a Etapa 0 já entrega um app buildado e deployável, e cada etapa seguinte é independente.

## Decisões fechadas

| Eixo | Decisão |
|------|---------|
| Estratégia | **Incremental por tela** — wrapper `<Legado>` monta o DOM antigo dentro do React; migra-se uma tela por PR |
| Linguagem | **TypeScript** — o contrato JSDoc de [services/api.js](../web/js/services/api.js) vira `tipos/dominio.ts` |
| Estilos | **CSS Modules** por tela, extraídos dos arquivos globais conforme a tela migra |
| Rotas | **Caminhos reais** (`/alunos/A023`) com React Router, `try_files` no nginx |
| Build | **Vite** |
| Dados | **TanStack Query** — substitui `cacheGet` (http-client), `telaCache` (main.js) e o evento `sas:dados-atualizados` |

## Arquitetura alvo

```
web/
├── index.html              entry do Vite (aponta pra /src/main.tsx)
├── package.json  vite.config.ts  tsconfig.json
├── assets/                 fontes e logos — ficam onde estão (Vite hasheia via url() do CSS)
├── styles/                 CSS global que sobrevive: tokens, base, fontes, comum
├── js/                     ⚠️ árvore legada — encolhe a cada etapa até ser deletada
└── src/
    ├── main.tsx            bootstrap + QueryClientProvider
    ├── App.tsx             rotas + guard de sessão
    ├── tipos/dominio.ts    Aluno, Simulado, Ciclo, Nota, ChatThread…
    ├── servicos/           http.ts (fetch+auth+erros), api.ts, sse.ts
    ├── hooks/              useAlunos, useSimulado, useCiclos… (wrappers de useQuery)
    ├── componentes/
    │   ├── layout/         AppShell, Topbar, Sidebar
    │   ├── ui/             Kpi, AlertCard, Sparkline, Heatmap, Histograma, Dialog…
    │   └── chat/
    ├── telas/
    │   └── Alunos/         Alunos.tsx + Alunos.module.css
    └── legado/Legado.tsx   wrapper que monta um nó DOM antigo
```

A árvore legada **não se move** na Etapa 0. Vite consegue importar `../../js/screens/painel.js` com `allowJs: true`, e o CSS importado de `src/` resolve `url(../assets/fonts/…)` relativo ao próprio arquivo CSS. Isso mantém os diffs legíveis: cada PR de tela é "adiciona `src/telas/X`, deleta `js/screens/x.js`".

### O wrapper `<Legado>`

É a peça que torna a migração incremental possível. Cerca de 25 linhas:

```tsx
// src/legado/Legado.tsx
export function Legado({ render, deps = [] }: { render: (ctx) => Promise<HTMLElement>, deps?: unknown[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let vivo = true;
    render({ sidebarEl: ref.current?.querySelector('.sidebar') }).then((el) => {
      if (vivo && ref.current) { ref.current.replaceChildren(el); }
    });
    return () => { vivo = false; };
  }, deps);
  return <div ref={ref} />;
}
```

As telas legadas já expõem exatamente a assinatura de que ele precisa: `renderPainel(ctx)`, `renderAlunos(ctx)`, `renderAlunoFicha({id})` — todas assíncronas e todas devolvendo um `HTMLElement` pronto. O único ponto de atrito é o `sidebarEl` que `main.js` injeta nas telas com filtros (alunos, simulados, ciclos, painel); o wrapper reproduz esse contrato passando o nó da sidebar do `AppShell`.

## Etapas

### Etapa 0 — Andaime (o app inteiro roda em React, nenhuma tela migrada ainda)

Objetivo: ao fim desta etapa o app se comporta **exatamente** como hoje, mas passa por `vite build`. É a etapa de maior risco de infra e a menor de risco de UI.

1. `package.json` com react, react-dom, react-router-dom, @tanstack/react-query, vite, typescript, @vitejs/plugin-react.
2. `vite.config.ts`: `root: '.'`, `build.outDir: 'dist'`, `server.proxy['/api'] → http://api:8000` (dev), `server.port: 8080`.
3. `tsconfig.json` com `allowJs: true`, `strict: true`, `noEmit: true`.
4. `index.html` perde o `<script>` inline de guard e os 12 `<link rel=stylesheet>`; passa a ter só `<div id="root">` e `<script type="module" src="/src/main.tsx">`. Os CSS globais são importados de `main.tsx`.
5. `src/main.tsx` + `src/App.tsx`: `QueryClientProvider`, `BrowserRouter`, rotas equivalentes às de [router.js](../web/js/router.js), guard de sessão (`sessionStorage.sas_auth`) como componente `<RotaProtegida>`, e a bifurcação aluno/coordenador que hoje está em `main.js:60`.
6. Todas as rotas renderizam `<Legado render={renderX} />`. O `AppShell` (topbar + sidebar + main) vira React já nesta etapa, porque é o casco que hospeda tudo — é o único código de `main.js` que não sobrevive como legado.
7. `src/servicos/http.ts`: porte direto de [http-client.js](../web/js/services/http-client.js) para TS, **removendo** o `cacheGet` (vira TanStack Query) e a detecção de `localhost` no `BASE_URL` (com o proxy do Vite, `/api` funciona em dev e prod igualmente). `streamSSE` e `postArquivo` (XHR com progresso) portam sem mudança de lógica.
8. `src/tipos/dominio.ts`: o bloco `@typedef ApiClient` de [api.js](../web/js/services/api.js) já enumera as ~45 operações — vira interface TS quase mecanicamente. Os tipos de entidade saem dos schemas Pydantic em [api/app/schemas/domain.py](../api/app/schemas/domain.py).
9. Infra (detalhado abaixo).

**Verificação da etapa:** clicar por todas as rotas e comparar com a versão atual lado a lado; `npm run build && npm run preview`; subir a stack prod local.

**Entregue.** O que existe no repositório depois desta etapa:

- `package.json`, `vite.config.ts`, `tsconfig.json` — build com Vite, `npm run build` roda `tsc --noEmit` antes.
- `src/main.tsx`, `src/App.tsx`, `src/rotas.ts` — bootstrap, rotas por caminho real, guard de sessão, chat launcher.
- `src/servicos/` — `http.ts` (fetch + auth + SSE + upload com progresso), `api.ts` (~45 operações tipadas), `sessao.ts`.
- `src/tipos/dominio.ts`, `src/hooks/consultas.ts` — tipos e hooks de leitura com chaves de cache.
- `src/componentes/layout/` — `AppShell` e `Topbar` em React; a topbar já usa a stack nova ponta a ponta (Query + rotas).
- `src/legado/` — `<Legado>`, `<TelaLegada>` e a ponte de eventos (links `#/`, `sas:dados-atualizados`).

Três ajustes no código legado que a mudança de rota exigiu, e que não dava para adiar:

1. `js/services/http-client.js` passou a usar `/api` sempre (o proxy do Vite cobre o dev) — antes detectava `localhost` e apontava para `:8000`.
2. Redirects relativos viraram absolutos: de `/alunos/A023`, `./login.html` resolveria para `/alunos/login.html`.
3. `js/components/chat/launcher.js` ganhou JSDoc na assinatura, para o TS aceitar a chamada tipada.

O casco (topbar, abas, sidebar, FAB do chat) foi verificado em browser headless; as telas autenticadas dependem de login real e ficaram para verificação manual.

### Etapa 1 — `alunos` (a tela-piloto)

[screens/alunos.js](../web/js/screens/alunos.js), 169 linhas — a menor tela real, mas exercita os três padrões que todas as outras repetem: filtros na sidebar com contagem cross-filtered, tabela ordenável, e sparkline por linha. Migrar ela primeiro fixa as convenções que os PRs seguintes copiam.

Traz junto (versões React de): `ui/filtros.js` (198), `ui/tabela-ordenavel.js` (110), `ui/sparkline.js` (86). Os arquivos legados **permanecem** até o último consumidor migrar — duplicação temporária, consciente e pequena.

O estado local (`estado.turmas`, `estado.sedes`, `estado.ordenacao`, `estado.abertas` — todos `Set`) vira `useState`; o `rerender()` manual de 60 linhas desaparece; o cross-filtering vira `useMemo`.

**Convenções a fixar aqui**, porque valem para as 9 telas seguintes:
- classes compartilhadas (`.card`, `.screen-subtitle`, `.tone-*`, `.nota-badge`, `.btn`, `.sidebar*`, `.empty-state`) ficam **globais** em `styles/comum.css` — não viram módulo, senão a extração trava;
- classes de prefixo próprio da tela viram módulo (`.filtros-*` → `Filtros.module.css`);
- um hook por recurso em `src/hooks/`, nunca `fetch` dentro de componente.

### Etapa 2 — `ciclos` + `simulados`

216 e 266 linhas, mesmíssimo padrão da Etapa 1 (lista + filtros + tabela). Traz `components/tabela-simulados.js` (140), `sim-filtros.js` (120) e `sim-filtros-logica.js` (80 — já é lógica pura, porta direto). Aqui entram as primeiras mutações: `criarCiclo` e `agendarSimulado` viram `useMutation` com `invalidateQueries`, substituindo o par `dispatchEvent('sas:dados-atualizados')` + `dispatchEvent(new HashChangeEvent('hashchange'))` que hoje força remontagem ([ciclos.js:197](../web/js/screens/ciclos.js#L197), [simulados.js:216](../web/js/screens/simulados.js#L216)). Traz também `components/agendar-simulado.js` (298) e `ui/dialog.js` (554) — os modais viram componentes controlados, e as três funções `abrirX(): Promise<valores|null>` viram estado `dialogAberto` no componente pai.

### Etapa 3 — Fichas: `simulado-ficha` + `ciclo-ficha`

251 e 504 linhas. Traz os gráficos SVG: `ui/histograma.js` (315), `ui/linha-temporal.js` (268), `ui/heatmap.js` (195), `ui/kpi.js`, `ui/alert-card.js`, `ui/insights-painel.js`. Gráficos SVG escritos à mão são o caso **mais fácil** de migrar: são funções puras `dados → nós SVG`, e JSX aceita SVG nativamente. O único ajuste é `stroke-width` → `strokeWidth` e afins. Some junto o helper `svgEl()` duplicado em [painel.js:13](../web/js/screens/painel.js#L13) e [aluno/shell.js:15](../web/js/screens/aluno/shell.js#L15).

### Etapa 4 — `aluno-ficha`

534 linhas + `ui/linha-evolucao.js` (288) + `calendario-anual.js` (107).

**Não migrar:** [services/panorama-aluno.js](../web/js/services/panorama-aluno.js) (385) e [services/exportar-aluno.js](../web/js/services/exportar-aluno.js) (248). Eles montam um nó DOM offscreen para exportar em PNG (via canvas) / PDF (via `window.print`) / CSV. São geradores de documento, não UI reativa — ficam como funções DOM puras, chamadas de um handler React. Migrar isso para JSX seria trabalho sem ganho e com risco de quebrar o layout de impressão.

### Etapa 5 — Área do aluno

`aluno/shell.js` (328) + `aluno/painel.js` (610) + `aluno/simulados.js` (413) e o `styles/aluno.css` (1.202 linhas, 152 classes `alu-*` — o arquivo mais limpo de extrair, é um namespace inteiro só dela).

Auto-contida: não compartilha tela nem estado com a coordenação, tem navegação própria por tabs (não usa o hash router). Pode ser feita fora de ordem, inclusive em paralelo, se alguém mais entrar no trabalho.

### Etapa 6 — `painel` (a tela mais difícil)

925 linhas. **Antes de converter para JSX, extrair a lógica pura para módulos testados**, e escrever testes contra a implementação atual:

- `ESQUEMA` ITA/IME e a resolução de colunas por ciclo (`simCol`/`mediaCol`, `painel.js:66-120`);
- cálculo das médias virtuais por aluno;
- cross-filtering das três seções da sidebar + busca individual + top-N com separadores de ranking.

Essa é a maior fonte de regressão silenciosa da migração inteira — são regras de negócio do domínio (fases ITA/IME, cortes por matéria) que só existem neste arquivo. Testes primeiro, conversão depois.

### Etapa 7 — `importar`

534 linhas. É a tela com mais estado vivo: upload XHR com barra de progresso, cronômetro de 100ms, polling do status a cada N ms ([importar.js:182-191](../web/js/screens/importar.js#L182)). Vira `useMutation` (upload) + `useQuery` com `refetchInterval` (polling), e os dois `setInterval` somem. Ao fim, `invalidateQueries` global substitui o `dispatchEvent('sas:dados-atualizados')` de [importar.js:425](../web/js/screens/importar.js#L425).

### Etapa 8 — Chat

`launcher.js` (203) + `conversa.js` (297) + `mensagem.js` (99) + `lista-threads.js` (53) + `tool-trace.js` (62) + `artefato.js` (86) + `perfis-sugestoes.js` (92).

O parser SSE de `http.ts` (`streamSSE`) **não muda** — o que muda é o consumidor: hoje `conversa.js` mantém `bolhaAssistantAtiva`, `textoEmStream`, `textoEl` e um `Map` de traces ativas, remendando o DOM a cada token. Vira um hook `useChatStream` com um reducer sobre os eventos (`token`, `tool_call`, `tool_result`, `fim`) e o React reconcilia. É a migração de maior ganho qualitativo do plano.

Cuidado: o launcher é montado **uma vez** fora da árvore de telas para sobreviver à navegação ([main.js:150](../web/js/main.js#L150)). Em React ele passa a viver no `App.tsx`, acima do `<Routes>` — mesmo efeito, sem gambiarra.

### Etapa 9 — Login e limpeza

`login.html` (220) + `login.js` (251) + `styles/login.css` (528). Hoje é uma segunda página HTML independente. Vira a rota `/login` do SPA, e o redirect `window.location.replace('./login.html')` de `http.ts` vira `navigate('/login')`.

Limpeza final: deletar `js/` inteiro, `dom.js`, `src/legado/`, o que restar dos CSS globais migrados; atualizar [docs/00-tech-stack.md](00-tech-stack.md) (a tabela do frontend inteira) e [web/README.md](../web/README.md) (que ainda descreve `mock-client.js`, removido há tempos).

## Infra — o que muda na Etapa 0

Esta é a parte que precisa ser acertada de uma vez, porque quebra o deploy se ficar pela metade.

**[web/Dockerfile](../web/Dockerfile)** vira multi-stage:
```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
```
Note a imagem **unprivileged** no estágio final — hoje o `web/Dockerfile` usa `nginx:1.27-alpine` (roda master como root) e só a stack da VPS usa a unprivileged. Unificar aqui elimina a divergência dev/prod.

**[infra/vps/docker-compose.yml](../infra/vps/docker-compose.yml)** — o serviço `web` hoje monta o código cru:
```yaml
volumes:
  - ../../web:/usr/share/nginx/html:ro   # ← precisa sair
```
Passa a `build: { context: ../../web }`, mantendo só o mount do `nginx.conf`. O `docker compose build --quiet` que já existe em [02-deploy.sh:104](../infra/vps/02-deploy.sh) passa a construir o front também — o fluxo `sync.sh` → `02-deploy.sh` continua idêntico para o operador. `sync.sh` já exclui `node_modules/`, então nada muda lá.

**[docker-compose.yml](../docker-compose.yml) (dev)** — o serviço `web` deixa de ser nginx e vira o dev server do Vite (`node:22-alpine` rodando `npm run dev -- --host`), com mount de `./web` e volume anônimo em `/app/node_modules`. Com `server.proxy` no Vite, o front chama `/api` em dev também — o que permite **remover** o `CORS_ALLOW_ORIGINS` especial do serviço `api` e a detecção de `localhost` no http-client.

**nginx** ([web/nginx.conf](../web/nginx.conf) e [infra/vps/nginx.conf](../infra/vps/nginx.conf)):
- `try_files $uri $uri/ /index.html;` — passa a ser **necessário** (rotas por caminho real), e passa a ser **seguro**: o comentário atual explica que o fallback transformaria um módulo `.js` quebrado em "Unexpected token '<'", mas com assets hasheados em `/assets/*.js` isso deixa de acontecer. Ainda assim, deixar `location /assets/ { try_files $uri =404; }` antes da regra geral, para que um asset ausente dê 404 honesto;
- cache invertido: `/assets/*` (com hash no nome) ganha `Cache-Control: immutable, max-age=31536000`; `index.html` continua `no-cache`. Hoje **tudo** é no-cache porque nada tem hash — a migração é o que finalmente permite cachear;
- CSP: `script-src 'unsafe-inline'` pode cair, porque o único script inline (o guard de sessão no `index.html`) deixa de existir. `style-src 'unsafe-inline'` provavelmente também, já que React aplica `style` via CSSOM e não via atributo — mas isso se **verifica** no fim, não se assume.

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Regressão silenciosa nas regras do painel (esquema ITA/IME, médias virtuais) | Testes Vitest sobre a lógica pura **antes** de converter (Etapa 6) |
| Regressão visual na extração de CSS Modules | Classes compartilhadas ficam globais; comparação de screenshot por tela antes/depois de cada PR |
| Deploy quebrar no meio da migração | Etapa 0 entrega o pipeline de build completo e testado; nenhuma etapa seguinte toca infra |
| Colidir com o lançamento em produção desta semana | Etapas são independentes e cada uma termina deployável — dá pra parar em qualquer ponto |
| Duplicação temporária de componentes `ui/` | Bounded e explícita: cada arquivo legado morre quando seu último consumidor migra; a Etapa 9 verifica que `js/` está vazio |

## Verificação

Por PR de tela:
1. `npm run typecheck && npm run build` — sem erro de TS, sem warning de import não resolvido.
2. Comparação visual: abrir a rota na versão anterior e na nova, mesma janela, mesmos dados; conferir tabela, filtros, ordenação e estados vazios.
3. Rede: DevTools → conferir que as chamadas disparadas são as mesmas de antes (TanStack Query deduplicando, não multiplicando).

Da migração como um todo:
1. `docker compose up` — front em :8080 com HMR, API em :8000, upload de planilha funcionando.
2. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build` — smoke da imagem de produção.
3. Chat: enviar mensagem e confirmar streaming token a token (é o que o `proxy_buffering off` do nginx sustenta — regressão aqui é silenciosa, a resposta só aparece de uma vez no fim).
4. `infra/vps/sync.sh && ssh … 02-deploy.sh` num deploy de teste antes do primeiro deploy real pós-migração.
5. Rotas profundas por caminho real: acessar `https://…/alunos/A023` **direto na barra de endereço** (não navegando) — é o que valida o `try_files`.
6. Console limpo de violação de CSP após o aperto das diretivas.

## Esforço aproximado

Etapa 0 é a mais imprevisível (infra): 2-3 dias. Etapas 1-5 e 7-9: 1-2 dias cada. Etapa 6 (painel): 3-4 dias, dos quais metade em testes. Total realista: **4 a 6 semanas** de trabalho focado, distribuível — mas o app fica utilizável e deployável do dia 3 em diante.


---

## Registro de execução

Todas as etapas foram executadas. O que saiu diferente do planejado, e por quê:

| Etapa | Desvio |
|---|---|
| 2 | `dialog.js` foi migrado na Etapa 3, não na 2: quem o consome são as fichas e o painel, não as listagens. |
| 5 | A área do aluno ganhou **rotas reais** (`/simulados/S12`) no lugar da navegação por estado interno. Recarregar a página deixou de voltar ao painel. |
| 9 | O login virou a rota `/login` e `login.html` deixou de existir. O build passou a ter uma entrada só. |
| — | `src/dominio/` nasceu como camada explícita. Não estava no plano, mas é onde as regras testáveis (esquemas ITA/IME, médias, filtros, ranking, streaming) passaram a viver — e é o que os 94 testes cobrem. |
| — | Os CSS Modules **não** foram adotados. Ver "CSS" abaixo. |

### CSS

O plano previa converter o CSS para CSS Modules tela a tela. Isso não foi feito,
e a decisão é consciente: as classes do projeto já são um namespace por tela
(`painel-*`, `alu-*`, `chat-*`, `lp-*`, `ciclo-*`), e a colisão que os Modules
resolvem não existe aqui. Converter significaria mexer em 5.900 linhas de CSS
para ganhar isolamento que o BEM já dá — trabalho grande, com risco visual real
e ganho nenhum.

O que os componentes React fazem é usar as mesmas classes, o que manteve a
migração visualmente neutra. Se em algum momento o CSS de uma tela começar a
vazar para outra, a conversão daquela tela específica continua possível — e aí
com motivo.

### Bugs encontrados no caminho

Três eram do código anterior e foram corrigidos:

1. **Chips de Sede e Turma nunca apareciam no Painel.** O filtro escondia chips
   sem contagem, e o Painel não calcula contagem — a seção inteira renderizava
   "—". O tooltip de ajuda anunciava um filtro que não funcionava. `contagem`
   ausente passou a significar "esta tela não conta", e não "zero".
2. **`selo-108anos.png` tem 1,7 MB** — maior que todo o JS do app somado.
   Continua pendente (é otimização de imagem, não de código).
3. **Estilo inline no gerador de PDF** seria bloqueado pela CSP apertada. O
   helper `el()` passou a aplicar `style` por CSSOM.

Três foram introduzidos durante a migração e corrigidos antes de fechar a etapa:

1. Um link antigo com hash (`/#/alunos/A023`) caía no painel, porque o redirect
   da rota `/` apagava o hash antes do listener ler.
2. O polling da importação só começava se o evento de upload concluído do XHR
   disparasse; passou a começar quando o POST responde.
3. O 401 global mandava para o login — inclusive quando o 401 era "senha
   errada" na própria tela de login, o que recarregava a página e apagava a
   mensagem de erro. As rotas `/auth/` ficaram de fora do redirect.
