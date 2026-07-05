// Bootstrap da SPA. Sem framework — apenas DOM, hash router e funções de
// tela. Cada rota tem uma função `render*()` que devolve um elemento já
// montado e populado com dados do `ApiClient` (mock no momento).

import { parseHash, topbarTabFor } from './router.js';
import { getApiClient } from './services/api.js';
import { topbar } from './components/topbar.js';
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
import { renderAlunoShell } from './screens/aluno/shell.js';

const SCREENS = {
  painel:    (_, ctx)   => renderPainel(ctx),
  alunos:    (_, ctx)   => renderAlunos(ctx),
  aluno:     (params)   => renderAlunoFicha({ id: params.id }),
  simulados: (_, ctx)   => renderSimulados(ctx),
  simulado:  (params)   => renderSimuladoFicha({ id: params.id }),
  ciclos:    (_, ctx)   => renderCiclos(ctx),
  ciclo:     (params)   => renderCicloFicha({ id: params.id }),
  importar:  ()         => renderImportar(),
};

// Cache das telas já montadas (DOM + dados), por rota. Voltar para uma aba
// reusa o elemento em vez de remontá-lo e rebuscar tudo — navegação fica
// instantânea. Cada entrada guarda o conteúdo da tela e, para rotas com
// sidebar dinâmica, o elemento de sidebar já populado. Invalidado em massa
// quando entra uma planilha nova (evento 'sas:dados-atualizados').
const telaCache = new Map();

// Importar tem timers/polling e estado vivo próprio — não vale a pena cachear.
const ROTAS_SEM_CACHE = new Set(['importar']);

// Rotas onde a tela popula uma sidebar de filtros (em vez de recortes estáticos).
const ROTAS_COM_FILTROS = new Set(['alunos', 'simulados', 'ciclos']);

async function renderAlunoApp() {
  const root = document.getElementById('root');
  if (!root) return;
  clear(root);
  const shell = await renderAlunoShell();
  root.appendChild(shell);
}

async function render() {
  const root = document.getElementById('root');
  if (!root) return;

  // Alunos autenticados veem apenas o próprio painel.
  if (sessionStorage.getItem('sas_tipo') === 'aluno') {
    return renderAlunoApp();
  }

  const route = parseHash(window.location.hash);
  const activeTab = topbarTabFor(route.name);

  // Chave de cache: rota + id. Filtragem é client-side dentro das telas.
  const routeKey = `${route.name}:${route.params.id || ''}`;
  const podeCachear = !ROTAS_SEM_CACHE.has(route.name);
  const cacheado = podeCachear ? telaCache.get(routeKey) : null;

  // Telas que escondem a sidebar (têm layout próprio em tela cheia).
  const ROTAS_SEM_SIDEBAR = new Set(['importar']);

  // Para o painel, a sidebar mostra ciclos (populada pelo próprio painel).
  const isPainel = route.name === 'painel';
  let sidebarPainelEl = null;
  if (isPainel) {
    sidebarPainelEl = cacheado?.sidebarPainelEl || el('aside', { class: 'card sidebar' }, [
      el('div', { class: 'sidebar__label' }, ['Ciclos']),
      el('div', { class: 'empty-state', style: 'padding: 20px 16px; font-size: 12px;' }, ['Carregando…']),
    ]);
  }

  // Para alunos/simulados/ciclos, a sidebar mostra filtros (populada pela tela).
  const temFiltros = ROTAS_COM_FILTROS.has(route.name);
  let sidebarFiltrosEl = null;
  if (temFiltros) {
    sidebarFiltrosEl = cacheado?.sidebarFiltrosEl || el('aside', { class: 'card sidebar' }, [
      el('div', { class: 'sidebar__label' }, ['Filtros']),
      el('div', { class: 'empty-state', style: 'padding: 12px 16px; font-size: 12px;' }, ['Carregando…']),
    ]);
  }

  const sidebarEl = ROTAS_SEM_SIDEBAR.has(route.name)
    ? null
    : isPainel
      ? sidebarPainelEl
      : temFiltros
        ? sidebarFiltrosEl
        : null;

  // Esqueleto enquanto carrega.
  clear(root);
  root.appendChild(topbar({ activeTab }));
  const shell = el('div', { class: 'app-shell' }, [
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
    const sidebarCtx = sidebarPainelEl || sidebarFiltrosEl || null;
    screenEl = await renderScreen(route.params, { sidebarEl: sidebarCtx });
    if (podeCachear) telaCache.set(routeKey, { screenEl, sidebarPainelEl, sidebarFiltrosEl });
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
// O aluno ganha um launcher próprio ("Mentor") dentro da área dele; o da
// coordenação não deve aparecer para ele.
if (sessionStorage.getItem('sas_tipo') !== 'aluno') {
  montarChatLauncher(document.body);
}
