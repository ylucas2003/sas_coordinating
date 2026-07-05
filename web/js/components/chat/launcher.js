// Chat launcher — botão flutuante (FAB) no canto inferior direito + drawer
// lateral que abre por cima de qualquer página.
//
// Persistente entre rotas: o launcher é montado uma única vez na bootstrap
// (em main.js), separado da árvore de telas. Mantém estado interno enquanto
// o usuário navega, e fecha/abre só visualmente.

import { clear, el } from '../../dom.js';
import { getApiClient } from '../../services/api.js';
import { conversaPanel } from './conversa.js';
import { listaThreads } from './lista-threads.js';

export function montarChatLauncher(parent, { rotuloFab = 'Assistente', tituloDrawer = 'Assistente' } = {}) {
  let drawerAberto = false;
  let listaThreadsAberta = false;
  let threads = [];
  let threadAtivaId = null;
  let detalheAtual = null;
  let carregouThreadsUmaVez = false;

  // ── FAB ────────────────────────────────────────────────────────────────
  const fab = el('button', {
    class: 'chat-fab',
    title: `Conversar com o ${rotuloFab.toLowerCase()}`,
    onclick: _toggle,
  }, [
    el('span', { class: 'chat-fab__icone' }, ['💬']),
    el('span', { class: 'chat-fab__label' }, [rotuloFab]),
  ]);

  // ── Drawer ─────────────────────────────────────────────────────────────
  const drawer = el('aside', {
    class: 'chat-drawer',
    role: 'dialog',
    'aria-label': 'Chat com o assistente',
  }, []);

  const overlay = el('div', { class: 'chat-overlay', onclick: _toggle }, []);

  parent.appendChild(fab);
  parent.appendChild(overlay);
  parent.appendChild(drawer);

  // Atalho global: Cmd/Ctrl + K abre/fecha.
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      _toggle();
    }
    if (e.key === 'Escape' && drawerAberto) _toggle();
  });

  async function _toggle() {
    drawerAberto = !drawerAberto;
    parent.classList.toggle('chat-aberto', drawerAberto);
    drawer.classList.toggle('is-aberto', drawerAberto);
    overlay.classList.toggle('is-aberto', drawerAberto);

    if (drawerAberto && !carregouThreadsUmaVez) {
      await _carregarInicial();
      carregouThreadsUmaVez = true;
    }
    if (drawerAberto) {
      _renderDrawer();
    }
  }

  async function _carregarInicial() {
    const api = getApiClient();
    try {
      threads = await api.listarChatThreads();
    } catch (e) {
      threads = [];
      drawer.appendChild(_erroBox(`Falha carregando conversas: ${e.message}`));
      return;
    }

    if (threads.length === 0) {
      const nova = await api.criarChatThread();
      threads = [nova];
      threadAtivaId = nova.id;
    } else {
      threadAtivaId = threads[0].id;
    }
    detalheAtual = await api.obterChatThread(threadAtivaId);
  }

  async function _renderDrawer() {
    clear(drawer);

    // Cabeçalho.
    const cabecalho = el('div', { class: 'chat-drawer__header' }, [
      el('div', { class: 'chat-drawer__header-info' }, [
        el('button', {
          class: 'chat-drawer__btn-threads',
          title: 'Suas conversas',
          onclick: _toggleListaThreads,
        }, ['☰']),
        el('div', { class: 'chat-drawer__titulo-bloco' }, [
          el('div', { class: 'chat-drawer__pequeno' }, [tituloDrawer]),
          el('h2', { class: 'chat-drawer__titulo' }, [detalheAtual?.titulo || 'Conversa']),
        ]),
      ]),
      el('div', { class: 'chat-drawer__header-acoes' }, [
        el('button', {
          class: 'chat-drawer__btn-icone',
          title: 'Nova conversa',
          onclick: _novaThread,
        }, ['+']),
        el('button', {
          class: 'chat-drawer__btn-icone',
          title: 'Fechar (Esc)',
          onclick: _toggle,
        }, ['×']),
      ]),
    ]);
    drawer.appendChild(cabecalho);

    // Dropdown de threads (overlay interno).
    if (listaThreadsAberta) {
      const wrapper = el('div', { class: 'chat-drawer__threads-overlay' }, [
        listaThreads({
          threads,
          threadAtivaId,
          onNovaThread: () => { listaThreadsAberta = false; _novaThread(); },
          onSelecionar: (id) => { listaThreadsAberta = false; _selecionar(id); },
          onApagar: _apagar,
        }),
      ]);
      drawer.appendChild(wrapper);
    }

    // Conversa.
    if (detalheAtual) {
      const conversa = conversaPanel({
        thread: detalheAtual,
        onTituloAtualizado: _onTitulo,
      });
      drawer.appendChild(conversa);
    }
  }

  function _toggleListaThreads() {
    listaThreadsAberta = !listaThreadsAberta;
    _renderDrawer();
  }

  async function _novaThread() {
    const api = getApiClient();
    const nova = await api.criarChatThread();
    threads = [nova, ...threads];
    threadAtivaId = nova.id;
    detalheAtual = await api.obterChatThread(nova.id);
    _renderDrawer();
  }

  async function _selecionar(id) {
    if (id === threadAtivaId) return;
    const api = getApiClient();
    threadAtivaId = id;
    detalheAtual = await api.obterChatThread(id);
    _renderDrawer();
  }

  async function _apagar(id) {
    const api = getApiClient();
    try {
      await api.apagarChatThread(id);
    } catch (e) {
      alert('Falha ao apagar: ' + e.message);
      return;
    }
    threads = threads.filter((t) => t.id !== id);
    if (threadAtivaId === id) {
      if (threads.length === 0) {
        await _novaThread();
        return;
      }
      threadAtivaId = threads[0].id;
      detalheAtual = await api.obterChatThread(threadAtivaId);
    }
    _renderDrawer();
  }

  function _onTitulo(novoTitulo) {
    const t = threads.find((x) => x.id === threadAtivaId);
    if (t) t.titulo = novoTitulo;
    if (detalheAtual) detalheAtual.titulo = novoTitulo;
    // Atualização leve do título visível, sem re-render completo.
    const h = drawer.querySelector('.chat-drawer__titulo');
    if (h) h.textContent = novoTitulo;
  }
}

function _erroBox(msg) {
  return el('div', { class: 'chat-drawer__erro' }, [msg]);
}
