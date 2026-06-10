// Bootstrap da SPA. Sem framework — apenas DOM, hash router e funções de
// tela. Cada rota tem uma função `render*()` que devolve um elemento já
// montado e populado com dados do `ApiClient` (mock no momento).

import { parseHash, topbarTabFor } from './router.js';
import { getApiClient } from './services/api.js';
import { topbar } from './components/topbar.js';
import { filterStrip } from './components/filter-strip.js';
import { sidebar } from './components/sidebar.js';
import { clear, el } from './dom.js';

import { renderPainel } from './screens/painel.js';
import { renderAlunos } from './screens/alunos.js';
import { renderAlunoFicha } from './screens/aluno-ficha.js';
import { renderSimulados } from './screens/simulados.js';
import { renderSimuladoFicha } from './screens/simulado-ficha.js';
import { renderCiclos } from './screens/ciclos.js';
import { renderCicloFicha } from './screens/ciclo-ficha.js';
import { renderImportar } from './screens/importar.js';
import { montarChatLauncher } from './components/chat/launcher.js';

const SCREENS = {
  painel:    (_, ctx)   => renderPainel(ctx),
  alunos:    (_, ctx)   => renderAlunos({ recorte: ctx.recorte }),
  aluno:     (params)   => renderAlunoFicha({ id: params.id }),
  simulados: ()         => renderSimulados(),
  simulado:  (params)   => renderSimuladoFicha({ id: params.id }),
  ciclos:    ()         => renderCiclos(),
  ciclo:     (params)   => renderCicloFicha({ id: params.id }),
  importar:  ()         => renderImportar(),
};

const recortePorTab = {}; // estado da sidebar, resetado quando troca de aba

// Cache das telas já montadas (DOM + dados), por rota. Voltar para uma aba
// reusa o elemento em vez de remontá-lo e rebuscar tudo — navegação fica
// instantânea. Cada entrada guarda o conteúdo da tela e, para o painel, a
// sidebar de ciclos que ele mesmo populou. Invalidado em massa quando entra
// uma planilha nova (evento 'sas:dados-atualizados').
const telaCache = new Map();

// Importar tem timers/polling e estado vivo próprio — não vale a pena cachear.
const ROTAS_SEM_CACHE = new Set(['importar']);

async function render() {
  const root = document.getElementById('root');
  if (!root) return;

  const route = parseHash(window.location.hash);
  const activeTab = topbarTabFor(route.name);
  const recorte = recortePorTab[activeTab] || null;

  // Chave de cache: rota + id + recorte (filtros diferentes = telas diferentes).
  const routeKey = `${route.name}:${route.params.id || ''}:${recorte || ''}`;
  const podeCachear = !ROTAS_SEM_CACHE.has(route.name);
  const cacheado = podeCachear ? telaCache.get(routeKey) : null;

  // Telas que substituem o filter-strip global por filtros locais próprios.
  const ROTAS_SEM_FILTERSTRIP_GLOBAL = new Set(['simulados', 'simulado', 'ciclos', 'ciclo', 'painel']);
  // Telas que escondem a sidebar contextual (têm layout próprio em tela cheia).
  const ROTAS_SEM_SIDEBAR = new Set(['importar']);

  // Para o painel, a sidebar mostra ciclos (populada pelo próprio painel).
  // No hit de cache, reusamos a sidebar já populada em vez do placeholder.
  const isPainel = route.name === 'painel';
  let sidebarPainelEl = null;
  if (isPainel) {
    sidebarPainelEl = cacheado?.sidebarPainelEl || el('aside', { class: 'card sidebar' }, [
      el('div', { class: 'sidebar__label' }, ['Ciclos']),
      el('div', { class: 'empty-state', style: 'padding: 20px 16px; font-size: 12px;' }, ['Carregando…']),
    ]);
  }

  const sidebarEl = ROTAS_SEM_SIDEBAR.has(route.name)
    ? null
    : isPainel
      ? sidebarPainelEl
      : sidebar({
          activeTab,
          activeRecorte: recorte,
          onSelect: (newRecorte) => {
            recortePorTab[activeTab] = newRecorte;
            render();
          },
        });

  // Esqueleto enquanto carrega.
  clear(root);
  const shell = el('div', { class: 'app-shell' }, [
    topbar({ activeTab }),
    ROTAS_SEM_FILTERSTRIP_GLOBAL.has(route.name) ? null : filterStrip(),
    el('div', { class: 'app-body' }, [
      sidebarEl,
      el('main', { class: 'app-main' }, [
        el('div', { class: 'card' }, [
          el('div', { class: 'empty-state' }, ['Carregando…']),
        ]),
      ]),
    ]),
  ]);
  root.appendChild(shell);

  // Hit de cache: reusa o DOM já montado (sem await, sem rede). Miss: monta a
  // tela, e guarda no cache se a rota for cacheável.
  let screenEl;
  if (cacheado) {
    screenEl = cacheado.screenEl;
  } else {
    const renderScreen = SCREENS[route.name] || SCREENS.painel;
    screenEl = await renderScreen(route.params, { recorte, sidebarEl: sidebarPainelEl });
    if (podeCachear) telaCache.set(routeKey, { screenEl, sidebarPainelEl });
  }

  // Substitui o placeholder pelo conteúdo real.
  const main = shell.querySelector('.app-main');
  if (main) {
    clear(main);
    main.appendChild(screenEl);
  }
}

window.addEventListener('hashchange', render);

// Quando entra uma planilha nova, os dados em cache ficam velhos: limpa tanto
// o cache de telas (DOM) quanto o de dados (HTTP), forçando remontagem fresca.
window.addEventListener('sas:dados-atualizados', () => {
  telaCache.clear();
  getApiClient().limparCacheDados();
});

render();

// Chat launcher (FAB + drawer) — montado uma vez, persiste entre rotas.
montarChatLauncher(document.body);
