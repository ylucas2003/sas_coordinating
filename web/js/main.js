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
  painel:    ()         => renderPainel(),
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
  const ROTAS_SEM_FILTERSTRIP_GLOBAL = new Set(['simulados', 'simulado', 'ciclos', 'ciclo']);
  // Telas que escondem a sidebar contextual (têm layout próprio em tela cheia).
  const ROTAS_SEM_SIDEBAR = new Set(['importar']);

  // Esqueleto enquanto carrega.
  clear(root);
  const shell = el('div', { class: 'app-shell' }, [
    topbar({ activeTab }),
    ROTAS_SEM_FILTERSTRIP_GLOBAL.has(route.name) ? null : filterStrip(),
    el('div', { class: 'app-body' }, [
      ROTAS_SEM_SIDEBAR.has(route.name) ? null : sidebar({
        activeTab,
        activeRecorte: recorte,
        onSelect: (newRecorte) => {
          recortePorTab[activeTab] = newRecorte;
          render();
        },
      }),
      el('main', { class: 'app-main' }, [
        el('div', { class: 'card' }, [
          el('div', { class: 'empty-state' }, ['Carregando…']),
        ]),
      ]),
    ]),
  ]);
  root.appendChild(shell);

  const renderScreen = SCREENS[route.name] || SCREENS.painel;
  const screenEl = await renderScreen(route.params, { recorte });

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
