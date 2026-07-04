// Topbar — logo asterisco + 4 abas + ações globais.

import { el } from '../dom.js';

const TABS = [
  { id: 'painel',    label: 'Painel',    href: '#/painel' },
  { id: 'alunos',    label: 'Alunos',    href: '#/alunos' },
  { id: 'simulados', label: 'Simulados', href: '#/simulados' },
  { id: 'ciclos',    label: 'Ciclos',    href: '#/ciclos' },
];

function svgAsterisco() {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', '20');
  svg.setAttribute('height', '20');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2.4');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('aria-hidden', 'true');
  for (const coords of [
    [12, 2, 12, 22],
    [3, 7, 21, 17],
    [21, 7, 3, 17],
  ]) {
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', coords[0]);
    line.setAttribute('y1', coords[1]);
    line.setAttribute('x2', coords[2]);
    line.setAttribute('y2', coords[3]);
    svg.appendChild(line);
  }
  return svg;
}

export function topbar({ activeTab }) {
  const logoEl = el('div', { class: 'topbar__logo' });
  logoEl.appendChild(svgAsterisco());

  return el('header', { class: 'topbar' }, [
    el('div', { class: 'topbar__brand' }, [
      logoEl,
      el('div', { class: 'topbar__brand-text' }, [
        el('span', { class: 'topbar__brand-name' }, ['SAS']),
        el('span', { class: 'topbar__brand-sub' }, ['coordenação ITM']),
      ]),
    ]),
    el('nav', { class: 'topbar__nav' }, TABS.map((t) =>
      el('a', {
        class: `topbar__tab${activeTab === t.id ? ' is-active' : ''}`,
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
    ]),
  ]);
}
