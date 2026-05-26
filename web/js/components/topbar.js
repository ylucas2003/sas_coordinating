// Topbar — 4 abas + ações globais. Documentado em ../../../docs/02-information-architecture.md.

import { el } from '../dom.js';

const TABS = [
  { id: 'painel',    label: 'Painel',    href: '#/painel' },
  { id: 'alunos',    label: 'Alunos',    href: '#/alunos' },
  { id: 'simulados', label: 'Simulados', href: '#/simulados' },
  { id: 'ciclos',    label: 'Ciclos',    href: '#/ciclos' },
];

export function topbar({ activeTab }) {
  return el('header', { class: 'card topbar' }, [
    el('div', { class: 'topbar__brand' }, [
      el('div', { class: 'topbar__logo' }, ['S']),
      el('span', {}, ['SAS']),
    ]),
    el('nav', { class: 'topbar__nav' }, TABS.map((t) =>
      el('a', {
        class: `topbar__tab ${activeTab === t.id ? 'is-active' : ''}`,
        href: t.href,
      }, [t.label])
    )),
    el('div', { class: 'topbar__actions' }, [
      el('a', {
        class: 'topbar__action topbar__action--primary',
        href: '#/importar',
        title: 'Importar planilha do Canvas',
      }, ['Importar planilha']),
      el('button', { class: 'topbar__action', title: 'Buscar (/)' }, ['Buscar']),
      el('button', { class: 'topbar__action', title: 'Exportar' }, ['Exportar']),
      el('button', { class: 'topbar__action', title: 'Configurações' }, ['⚙']),
    ]),
  ]);
}
