// Bootstrap da SPA. Sem framework — apenas DOM, hash router e funções de
// tela. Cada rota tem uma função `render*()` que devolve um elemento já
// montado e populado com dados do `ApiClient` (mock no momento).

import { parseHash, topbarTabFor } from './router.js';
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

async function render() {
  const root = document.getElementById('root');
  if (!root) return;

  const route = parseHash(window.location.hash);
  const activeTab = topbarTabFor(route.name);
  const recorte = recortePorTab[activeTab] || null;

  // Telas que substituem o filter-strip global por filtros locais próprios.
  const ROTAS_SEM_FILTERSTRIP_GLOBAL = new Set(['simulados', 'simulado', 'ciclos', 'ciclo', 'painel']);
  // Telas que escondem a sidebar contextual (têm layout próprio em tela cheia).
  const ROTAS_SEM_SIDEBAR = new Set(['importar']);

  // Para o painel, a sidebar mostra ciclos (populada pelo próprio painel).
  const isPainel = route.name === 'painel';
  let sidebarPainelEl = null;
  if (isPainel) {
    sidebarPainelEl = el('aside', { class: 'card sidebar' }, [
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

  const renderScreen = SCREENS[route.name] || SCREENS.painel;
  const screenEl = await renderScreen(route.params, { recorte, sidebarEl: sidebarPainelEl });

  // Substitui o placeholder pelo conteúdo real.
  const main = shell.querySelector('.app-main');
  if (main) {
    clear(main);
    main.appendChild(screenEl);
  }
}

window.addEventListener('hashchange', render);
render();

// Chat launcher (FAB + drawer) — montado uma vez, persiste entre rotas.
montarChatLauncher(document.body);
