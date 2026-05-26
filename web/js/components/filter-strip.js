// Faixa de filtros globais. Pílulas que persistem entre abas — comportamento
// real virá quando houver dados; aqui são placeholders visuais.

import { el } from '../dom.js';

const FILTERS = [
  { label: 'Sede · todas' },
  { label: 'Turma · todas' },
  { label: 'Ciclo · C3 · 2026', active: true },
  { label: 'Tempo · últimos 30d' },
  { label: 'Matéria · todas' },
];

export function filterStrip() {
  return el('div', { class: 'card filter-strip' }, [
    ...FILTERS.map((f) =>
      el('button', { class: `filter-pill ${f.active ? 'is-active' : ''}` }, [f.label])
    ),
    el('div', { class: 'filter-strip__sep' }),
    el('button', { class: 'filter-pill', title: 'Atalho: /' }, ['/ buscar']),
  ]);
}
