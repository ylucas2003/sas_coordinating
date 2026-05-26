// Sidebar de threads do chat. Lista as conversas do usuário e permite criar
// nova / selecionar / arquivar.

import { el } from '../../dom.js';

const FORMATADOR_DATA = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
});

export function listaThreads({ threads, threadAtivaId, onNovaThread, onSelecionar, onApagar }) {
  return el('aside', { class: 'chat-threads' }, [
    el('div', { class: 'chat-threads__header' }, [
      el('span', { class: 'chat-threads__titulo' }, ['Conversas']),
      el('button', {
        class: 'chat-threads__nova',
        onclick: onNovaThread,
        title: 'Nova conversa',
      }, ['+ Nova']),
    ]),
    threads.length === 0
      ? el('div', { class: 'chat-threads__vazio' }, ['Nenhuma conversa ainda. Crie a primeira.'])
      : el('ul', { class: 'chat-threads__lista' }, threads.map((t) =>
          el('li', {
            class: `chat-threads__item ${t.id === threadAtivaId ? 'is-ativa' : ''}`,
            onclick: () => onSelecionar(t.id),
          }, [
            el('div', { class: 'chat-threads__item-titulo' }, [t.titulo || 'Nova conversa']),
            el('div', { class: 'chat-threads__item-rodape' }, [
              el('span', { class: 'chat-threads__item-data' }, [
                _formatarData(t.ultimaMsgEm),
              ]),
              el('button', {
                class: 'chat-threads__item-apagar',
                title: 'Apagar conversa',
                onclick: (e) => {
                  e.stopPropagation();
                  if (confirm(`Apagar a conversa "${t.titulo}"?`)) onApagar(t.id);
                },
              }, ['×']),
            ]),
          ]),
        )),
  ]);
}

function _formatarData(iso) {
  if (!iso) return '';
  try {
    return FORMATADOR_DATA.format(new Date(iso));
  } catch {
    return '';
  }
}
