// Topbar — logo asterisco + 4 abas + ações globais.

import { el, clear } from '../dom.js';
import { getApiClient } from '../services/api.js';

const TABS = [
  { id: 'painel',    label: 'Painel',    href: '#/painel' },
  { id: 'alunos',    label: 'Alunos',    href: '#/alunos' },
  { id: 'simulados', label: 'Simulados', href: '#/simulados' },
  { id: 'ciclos',    label: 'Ciclos',    href: '#/ciclos' },
];

function normalizar(s) {
  return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

function svgSearchIcon() {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', '14');
  svg.setAttribute('height', '14');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('aria-hidden', 'true');
  const circ = document.createElementNS(ns, 'circle');
  circ.setAttribute('cx', '11'); circ.setAttribute('cy', '11'); circ.setAttribute('r', '8');
  const line = document.createElementNS(ns, 'line');
  line.setAttribute('x1', '21'); line.setAttribute('y1', '21');
  line.setAttribute('x2', '16.65'); line.setAttribute('y2', '16.65');
  svg.appendChild(circ);
  svg.appendChild(line);
  return svg;
}

// Cache em memória dos alunos+turmas pra busca — carregado só no primeiro
// uso (não a cada render da topbar) e reaproveitado enquanto durar a sessão;
// `http-client` já invalida isso via `limparCacheDados()` quando entra
// planilha nova.
let _cacheBusca = null;
async function carregarDadosBusca() {
  if (_cacheBusca) return _cacheBusca;
  const api = getApiClient();
  const [alunos, turmas] = await Promise.all([
    api.listarAlunos().catch(() => []),
    api.listarTurmas().catch(() => []),
  ]);
  const turmaPorId = new Map(turmas.map((t) => [t.id, t]));
  _cacheBusca = { alunos, turmaPorId };
  return _cacheBusca;
}

// Atalho global "/" foca a busca, de qualquer tela — bind uma única vez
// (a topbar é remontada a cada troca de rota, o listener no document não).
let _buscaInputAtivo = null;
let _atalhoGlobalLigado = false;
function ligarAtalhoGlobal() {
  if (_atalhoGlobalLigado) return;
  _atalhoGlobalLigado = true;
  document.addEventListener('keydown', (ev) => {
    if (ev.key !== '/' || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const alvo = ev.target;
    if (alvo && (alvo.tagName === 'INPUT' || alvo.tagName === 'TEXTAREA' || alvo.isContentEditable)) return;
    if (!_buscaInputAtivo) return;
    ev.preventDefault();
    _buscaInputAtivo.focus();
  });
}

function buildBusca() {
  const input = el('input', {
    class: 'topbar__busca-input',
    type: 'text',
    placeholder: 'Buscar aluno…',
    'aria-label': 'Buscar aluno',
  }, []);
  const resultadosEl = el('div', { class: 'topbar__busca-resultados' }, []);

  let dados = null;
  let resultados = [];
  let ativo = -1;

  function fechar() {
    resultadosEl.classList.remove('is-aberto');
    clear(resultadosEl);
    resultados = [];
    ativo = -1;
  }

  function renderResultados() {
    clear(resultadosEl);
    if (!resultados.length) {
      resultadosEl.appendChild(el('div', { class: 'topbar__busca-vazio' }, ['Nenhum aluno encontrado.']));
    } else {
      resultados.forEach((a, i) => {
        const turma = dados.turmaPorId.get(a.turmaId);
        resultadosEl.appendChild(el('a', {
          class: `topbar__busca-item${i === ativo ? ' is-ativo' : ''}`,
          href: `#/alunos/${a.id}`,
          onmousedown: (ev) => ev.preventDefault(), // evita o blur fechar antes do click
          onclick: fechar,
        }, [
          el('span', { class: 'topbar__busca-item-nome' }, [a.nome]),
          turma ? el('span', { class: 'topbar__busca-item-sub' }, [turma.nome]) : null,
        ].filter(Boolean)));
      });
    }
    resultadosEl.classList.add('is-aberto');
  }

  async function onInput() {
    const q = input.value.trim();
    if (!q) { fechar(); return; }
    if (!dados) dados = await carregarDadosBusca();
    const nq = normalizar(q);
    resultados = dados.alunos.filter((a) => normalizar(a.nome).includes(nq)).slice(0, 8);
    ativo = -1;
    renderResultados();
  }

  input.addEventListener('input', onInput);
  input.addEventListener('focus', onInput);
  input.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') {
      fechar();
      input.blur();
    } else if (ev.key === 'ArrowDown' && resultados.length) {
      ev.preventDefault();
      ativo = Math.min(ativo + 1, resultados.length - 1);
      renderResultados();
    } else if (ev.key === 'ArrowUp' && resultados.length) {
      ev.preventDefault();
      ativo = Math.max(ativo - 1, 0);
      renderResultados();
    } else if (ev.key === 'Enter') {
      const alvo = resultados[ativo >= 0 ? ativo : 0];
      if (alvo) {
        window.location.hash = `#/alunos/${alvo.id}`;
        fechar();
        input.blur();
      }
    }
  });
  input.addEventListener('blur', () => { setTimeout(fechar, 120); });

  _buscaInputAtivo = input;
  ligarAtalhoGlobal();

  return el('div', { class: 'topbar__busca' }, [
    svgSearchIcon(),
    input,
    el('span', { class: 'topbar__busca-atalho' }, ['/']),
    resultadosEl,
  ]);
}

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
      buildBusca(),
      el('a', {
        class: 'topbar__action topbar__action--primary',
        href: '#/importar',
        title: 'Importar planilha do Canvas',
      }, ['Importar planilha']),
    ]),
  ]);
}
