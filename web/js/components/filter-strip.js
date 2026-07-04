// Faixa de filtros globais — pílulas dropdown + limpar filtros.

import { el } from '../dom.js';

const FILTERS = [
  { label: 'Sede · todas', dropdown: true },
  { label: 'Turma · todas', dropdown: true },
  { label: 'Ciclo · C3 · 2026', active: true, dropdown: true },
  { label: 'Tempo · últimos 30d', dropdown: true },
  { label: 'Matéria · todas', dropdown: true },
];

function chevron() {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('class', 'filter-pill__chevron');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2.5');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  const poly = document.createElementNS(ns, 'polyline');
  poly.setAttribute('points', '6 9 12 15 18 9');
  svg.appendChild(poly);
  return svg;
}

export function filterStrip() {
  const pills = FILTERS.map((f) => {
    const btn = el('button', { class: `filter-pill ${f.active ? 'is-active' : ''}` }, [f.label]);
    if (f.dropdown) btn.appendChild(chevron());
    return btn;
  });

  return el('div', { class: 'card filter-strip' }, [
    ...pills,
    el('div', { class: 'filter-strip__sep' }),
    el('button', { class: 'filter-strip__clear' }, ['Limpar filtros']),
  ]);
}
