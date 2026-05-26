// Sidebar contextual — perguntas/recortes (não entidades).
// Ver ../../../docs/02-information-architecture.md.

import { el } from '../dom.js';

const ITEMS_BY_TAB = {
  painel: [
    'Alertas críticos',
    'Quedas recentes',
    'Subidas atípicas',
    'Variância suspeita',
    'Diferenças entre sedes',
  ],
  alunos: [
    'Em risco',
    'Em ascensão',
    'Perfil irregular',
    'Zona de corte (ITA / IME)',
    'Comparar alunos',
  ],
  simulados: [
    'Mais difíceis',
    'Maior variância',
    'Por matéria',
    'Distribuição',
    'Comparar simulados',
  ],
  ciclos: [
    'Evolução temporal',
    'Aprovação projetada',
    'Coortes históricas',
    'Compressão/dispersão',
    'Comparar ciclos',
  ],
};

export function sidebar({ activeTab, activeRecorte, onSelect }) {
  const items = ITEMS_BY_TAB[activeTab] || [];

  return el('aside', { class: 'card sidebar' }, [
    el('div', { class: 'sidebar__label' }, ['Recortes']),
    ...items.map((label) => {
      const id = slug(label);
      return el('button', {
        class: `sidebar__item ${activeRecorte === id ? 'is-active' : ''}`,
        onclick: () => onSelect && onSelect(activeRecorte === id ? null : id),
      }, [label]);
    }),
  ]);
}

function slug(s) {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}
