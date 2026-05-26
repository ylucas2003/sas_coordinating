// Cartão de alerta — componente central do Painel.
// Anatomia documentada em ../../../../docs/04-screens.md (4.1).

import { el } from '../../dom.js';
import { sparkline } from './sparkline.js';

export function alertCard(alerta, { onResolver } = {}) {
  const tone = `tone-${alerta.severidade}`;

  const acoes = [
    el('a', { class: 'alert-card__link', href: alerta.href }, ['Ver detalhes →']),
  ];
  if (onResolver) {
    acoes.push(
      el('button', {
        class: 'btn-link-resolver',
        onclick: (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          onResolver(alerta);
        },
      }, ['Resolver'])
    );
  }

  return el('div', {
    class: `alert-card ${tone}`,
    onclick: () => { window.location.hash = alerta.href.replace(/^#/, ''); },
  }, [
    el('div', { class: `alert-card__bar ${tone}` }),
    el('div', { class: 'alert-card__main' }, [
      el('div', { class: 'alert-card__meta' }, [
        el('span', { class: `alert-card__tag ${tone}` }, [alerta.tagLabel]),
        el('span', { class: 'alert-card__time' }, [alerta.tempoRelativo]),
      ]),
      el('div', { class: 'alert-card__title' }, [alerta.titulo]),
      el('div', { class: 'alert-card__subtitle' }, [alerta.subtitulo]),
    ]),
    el('div', { class: 'alert-card__viz' }, [
      sparkline(alerta.sparkline || [], { color: 'currentColor' }),
    ]),
    el('div', { style: 'display: flex; flex-direction: column; gap: 6px; align-items: flex-end;' }, acoes),
  ]);
}
