// Shell responsivo da área do aluno.
// Gerencia tabs (painel | simulados), renderiza o header e o bottom nav mobile.
// Toda navegação interna passa pelo objeto `nav` — sem hash routing.

import { el, clear } from '../../dom.js';
import { renderPainelAluno } from './painel.js';
import { renderSimuladosAluno } from './simulados.js';

// ─── SVG helpers ─────────────────────────────────────────────────────────

function svgEl(tag, attrs = {}) {
  const ns = 'http://www.w3.org/2000/svg';
  const node = document.createElementNS(ns, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}

// Ícone de casa
function iconHome(size = 18, color = 'currentColor') {
  const svg = svgEl('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color, 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
  svg.style.cssText = 'display:block;flex-shrink:0';
  svg.appendChild(svgEl('path', { d: 'M3 11.5l9-7.5 9 7.5M5 10v9a1 1 0 0 0 1 1h3v-6h6v6h3a1 1 0 0 0 1-1v-9' }));
  return svg;
}

// Ícone de documento
function iconDoc(size = 18, color = 'currentColor') {
  const svg = svgEl('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color, 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
  svg.style.cssText = 'display:block;flex-shrink:0';
  svg.appendChild(svgEl('path', { d: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M9 13h6 M9 17h4' }));
  return svg;
}

// Ícone de chapéu de formatura
function iconGrad(size = 18, color = 'currentColor') {
  const svg = svgEl('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color, 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
  svg.style.cssText = 'display:block;flex-shrink:0';
  svg.appendChild(svgEl('path', { d: 'M22 10L12 5 2 10l10 5 10-5z M6 12v5c0 1 2.7 2.5 6 2.5s6-1.5 6-2.5v-5' }));
  return svg;
}

// ─── Logo ─────────────────────────────────────────────────────────────────

function _logo(size = 34) {
  const wrap = el('div', { class: 'alu-header__logo', style: `width:${size}px;height:${size}px` });
  wrap.appendChild(iconGrad(size * 0.5, '#fff'));
  wrap.appendChild(el('span', { class: 'alu-header__logo-bar' }));
  return wrap;
}

// ─── Header desktop ───────────────────────────────────────────────────────

function _headerDesktop({ nome, primeiro, tabEls }) {
  const inicial = (nome || 'A').charAt(0).toUpperCase();

  const header = el('header', { class: 'alu-header' }, [
    el('div', { class: 'alu-header__brand' }, [
      _logo(),
      el('div', { class: 'alu-header__brand-text' }, [
        el('span', { class: 'alu-header__brand-name' }, ['SAS']),
        el('span', { class: 'alu-header__brand-sub' }, ['Área do estudante']),
      ]),
    ]),
    el('div', { class: 'alu-header__tabs' }, tabEls),
    el('div', { class: 'alu-header__user' }, [
      el('div', { class: 'alu-header__user-info' }, [
        el('div', { class: 'alu-header__user-name' }, [nome || '']),
      ]),
      el('div', { class: 'alu-avatar' }, [inicial]),
      el('button', {
        class: 'alu-header__sair',
        onclick: () => { sessionStorage.clear(); window.location.replace('./login.html'); },
      }, ['Sair']),
    ]),
  ]);

  return header;
}

// ─── Header mobile ────────────────────────────────────────────────────────

function _headerMobile({ nome }) {
  const inicial = (nome || 'A').charAt(0).toUpperCase();

  return el('header', { class: 'alu-header alu-header--mobile' }, [
    el('div', { class: 'alu-header__brand' }, [
      _logo(30),
      el('div', { class: 'alu-header__brand-text' }, [
        el('span', { class: 'alu-header__brand-name', style: 'font-size:15px' }, ['SAS']),
      ]),
    ]),
    el('div', { class: 'alu-header__user', style: 'margin-left:auto' }, [
      el('div', { class: 'alu-avatar', style: 'width:30px;height:30px;font-size:13px' }, [inicial]),
      el('button', {
        class: 'alu-header__sair',
        onclick: () => { sessionStorage.clear(); window.location.replace('./login.html'); },
      }, ['Sair']),
    ]),
  ]);
}

// ─── Tab element factory ──────────────────────────────────────────────────

function _tabEl(id, label, iconFn, activeTab, navigate) {
  const isActive = id === activeTab;
  const tabEl = el('div', {
    class: `alu-tab${isActive ? ' is-active' : ''}`,
    dataset: { tab: id },
    onclick: () => navigate(id),
  });
  tabEl.appendChild(iconFn(16, isActive ? 'var(--color-navy)' : 'var(--color-text-secondary)'));
  tabEl.appendChild(document.createTextNode(label));
  return tabEl;
}

// ─── Bottom nav ───────────────────────────────────────────────────────────

function _bottomNav(activeTab, navigate) {
  const tabs = [
    { id: 'painel', label: 'Painel', iconFn: iconHome },
    { id: 'simulados', label: 'Simulados', iconFn: iconDoc },
  ];

  return el('nav', { class: 'alu-bottom-nav' },
    tabs.map(t => {
      const isActive = t.id === activeTab;
      const item = el('div', {
        class: `alu-nav-item${isActive ? ' is-active' : ''}`,
        dataset: { navItem: t.id },
        onclick: () => navigate(t.id),
      });
      item.appendChild(t.iconFn(22, isActive ? 'var(--color-navy)' : 'var(--color-text-tertiary)'));
      item.appendChild(document.createTextNode(t.label));
      return item;
    })
  );
}

// ─── Shell principal ──────────────────────────────────────────────────────

export async function renderAlunoShell() {
  const nome = sessionStorage.getItem('sas_nome') || '';
  const primeiro = nome.split(' ')[0] || nome;

  let currentTab = 'painel';
  let currentParams = {};

  // Estado mutável — referências aos elementos que serão atualizados
  const bodyEl = el('div', { class: 'alu-body' });
  const innerEl = el('div', { class: 'alu-body__inner' });
  bodyEl.appendChild(innerEl);

  // Tabs e bottom nav são criados depois do nav ser definido
  const tabEls = []; // populado abaixo
  let bottomNavEl;

  // ── Funções de navegação ──

  function _updateActiveState() {
    // Tabs desktop
    bodyEl.closest('.alu-shell')?.querySelectorAll('[data-tab]').forEach(t => {
      t.classList.toggle('is-active', t.dataset.tab === currentTab);
      const iconEl = t.querySelector('svg');
      if (iconEl) {
        iconEl.setAttribute('stroke', currentTab === t.dataset.tab
          ? 'var(--color-navy)'
          : 'var(--color-text-secondary)');
      }
    });
    // Bottom nav
    bodyEl.closest('.alu-shell')?.querySelectorAll('[data-nav-item]').forEach(n => {
      n.classList.toggle('is-active', n.dataset.navItem === currentTab);
      const iconEl = n.querySelector('svg');
      if (iconEl) {
        iconEl.setAttribute('stroke', currentTab === n.dataset.navItem
          ? 'var(--color-navy)'
          : 'var(--color-text-tertiary)');
      }
    });
  }

  async function navigate(tab, params = {}) {
    currentTab = tab;
    currentParams = params;
    _updateActiveState();
    bodyEl.scrollTop = 0;
    await _renderScreen();
  }

  const nav = {
    go: navigate,
    get tab() { return currentTab; },
    get params() { return currentParams; },
  };

  // ── Renderização de tela ──

  async function _renderScreen() {
    clear(innerEl);
    innerEl.appendChild(el('div', { class: 'alu-loading' }, ['Carregando…']));

    let screen;
    try {
      if (currentTab === 'painel') {
        screen = await renderPainelAluno({ nav, nome: primeiro });
      } else if (currentTab === 'simulados') {
        screen = await renderSimuladosAluno({ nav, params: currentParams });
      }
    } catch (err) {
      console.error('[shell] erro ao renderizar tela:', err);
      screen = el('div', { class: 'alu-empty' }, [
        'Erro ao carregar. Tente recarregar a página.',
      ]);
    }

    clear(innerEl);
    if (screen) innerEl.appendChild(screen);
  }

  // ── Montagem do shell ──

  const tabsDesktop = [
    _tabEl('painel', 'Painel', iconHome, currentTab, navigate),
    _tabEl('simulados', 'Simulados', iconDoc, currentTab, navigate),
  ];

  const bottomNav = _bottomNav(currentTab, navigate);

  const root = el('div', { class: 'alu-shell' }, [
    _headerDesktop({ nome, primeiro, tabEls: tabsDesktop }),
    _headerMobile({ nome }),
    bodyEl,
    bottomNav,
  ]);

  // Renderiza tela inicial
  await _renderScreen();

  return root;
}
