// Painel — "O que merece sua atenção agora". Ver 04-screens.md (4.1).

import { getApiClient } from '../services/api.js';
import { alertCard } from '../components/ui/alert-card.js';
import { clear, el } from '../dom.js';

export async function renderPainel() {
  const api = getApiClient();
  let alertas = await api.listarAlertas();

  const lista = el('div', {}, []);
  const subtitulo = el('p', { class: 'screen-subtitle' }, []);

  function pintar() {
    subtitulo.textContent = `${alertas.length} alertas ordenados por severidade`;
    clear(lista);
    if (alertas.length === 0) {
      lista.appendChild(
        el('div', { class: 'empty-state' }, [
          'Tudo tranquilo nesta semana.',
          el('div', { class: 'empty-state__hint' }, ['Veja o panorama dos ciclos.']),
        ])
      );
      return;
    }
    for (const a of alertas) {
      lista.appendChild(alertCard(a, { onResolver: resolver }));
    }
  }

  async function resolver(alerta) {
    try {
      await api.resolverAlerta(alerta.id);
      alertas = alertas.filter((a) => a.id !== alerta.id);
      pintar();
    } catch (e) {
      console.warn('Falha ao resolver alerta', e);
    }
  }

  pintar();

  return el('section', { class: 'card' }, [
    el('div', { class: 'screen-header' }, [
      el('div', { class: 'screen-breadcrumb' }, ['Painel']),
      el('h1', { class: 'screen-title' }, ['O que merece sua atenção']),
      subtitulo,
    ]),
    lista,
  ]);
}
