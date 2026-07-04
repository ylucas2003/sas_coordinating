// Painel — explosão de dados: alunos × matérias/fases por ciclo.
// Sidebar com 3 seções (Ciclos, Sede, Turmas), busca individual e top-N.

import { getApiClient } from '../services/api.js';
import { clear, el, fmtNota } from '../dom.js';
import { abrirFichaNota } from '../components/ui/dialog.js';

// ─── SVG helper (el() usa createElement, não createElementNS) ────────────

function svgEl(tag, attrs = {}, children = []) {
  const ns = 'http://www.w3.org/2000/svg';
  const node = document.createElementNS(ns, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  for (const child of children) {
    if (typeof child === 'string') node.textContent += child;
    else node.appendChild(child);
  }
  return node;
}

function svgIcon(type) {
  const base = { xmlns: 'http://www.w3.org/2000/svg', width: '16', height: '16',
                  viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
                  'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' };
  if (type === 'ciclos') {
    return svgEl('svg', base, [
      svgEl('rect', { x: '3', y: '4', width: '18', height: '18', rx: '2', ry: '2' }),
      svgEl('line', { x1: '16', y1: '2', x2: '16', y2: '6' }),
      svgEl('line', { x1: '8', y1: '2', x2: '8', y2: '6' }),
      svgEl('line', { x1: '3', y1: '10', x2: '21', y2: '10' }),
    ]);
  }
  if (type === 'sede') {
    return svgEl('svg', base, [
      svgEl('path', { d: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z' }),
      svgEl('polyline', { points: '9 22 9 12 15 12 15 22' }),
    ]);
  }
  if (type === 'turmas') {
    return svgEl('svg', base, [
      svgEl('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
      svgEl('circle', { cx: '9', cy: '7', r: '4' }),
      svgEl('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
      svgEl('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' }),
    ]);
  }
  if (type === 'chevron') {
    return svgEl('svg', { ...base, width: '12', height: '12' }, [
      svgEl('polyline', { points: '6 9 12 15 18 9' }),
    ]);
  }
  if (type === 'search') {
    return svgEl('svg', base, [
      svgEl('circle', { cx: '11', cy: '11', r: '8' }),
      svgEl('line', { x1: '21', y1: '21', x2: '16.65', y2: '16.65' }),
    ]);
  }
  return svgEl('svg', base, []);
}

// ─── Helpers de definição de colunas ─────────────────────────────────────

function simCol(id, label, fase, normNome, tipo, extra = {}) {
  return { id, label, fase, virtual: false, novaFase: false, destaque: false,
           simKey: { normNome, tipo }, sim: null, ...extra };
}
function mediaCol(id, label, fase, extra = {}) {
  return { id, label, fase, virtual: true, novaFase: false, destaque: true,
           simKey: null, sim: null, ...extra };
}

// ─── Esquemas de colunas por vestibular ──────────────────────────────────

const ESQUEMA = {
  ITA: {
    completo: [
      simCol('MAT_F1', 'Matemática', '1°F', 'matematica', 'fase_1'),
      simCol('FIS_F1', 'Física',     '1°F', 'fisica',     'fase_1'),
      simCol('QUI_F1', 'Química',    '1°F', 'quimica',    'fase_1'),
      simCol('ING_F1', 'Inglês',     '1°F', 'ingles',     'fase_1'),
      mediaCol('MED_F1', 'Média',    '1°F'),
      simCol('MAT_F2', 'Matemática', '2°F', 'matematica', 'fase_2', { novaFase: true }),
      simCol('FIS_F2', 'Física',     '2°F', 'fisica',     'fase_2'),
      simCol('QUI_F2', 'Química',    '2°F', 'quimica',    'fase_2'),
      simCol('RED_F2', 'Redação',    '2°F', 'redacao',    'fase_2'),
      simCol('POR_F2', 'Português',  '2°F', 'portugues',  'fase_2'),
      mediaCol('MED_FINAL', 'Média', 'Final'),
    ],
    somenteF1: [
      simCol('MAT_F1', 'Matemática', '1°F', 'matematica', 'fase_1'),
      simCol('FIS_F1', 'Física',     '1°F', 'fisica',     'fase_1'),
      simCol('QUI_F1', 'Química',    '1°F', 'quimica',    'fase_1'),
      simCol('ING_F1', 'Inglês',     '1°F', 'ingles',     'fase_1'),
    ],
    somenteF2: [
      simCol('MAT_F2', 'Matemática', '2°F', 'matematica', 'fase_2'),
      simCol('FIS_F2', 'Física',     '2°F', 'fisica',     'fase_2'),
      simCol('QUI_F2', 'Química',    '2°F', 'quimica',    'fase_2'),
      simCol('RED_F2', 'Redação',    '2°F', 'redacao',    'fase_2'),
      simCol('POR_F2', 'Português',  '2°F', 'portugues',  'fase_2'),
      mediaCol('MED_FINAL', 'Média', 'Final'),
    ],
  },
  IME: {
    completo: [
      simCol('MAT_F1', 'Matemática', '1°F', 'matematica', 'fase_1'),
      simCol('FIS_F1', 'Física',     '1°F', 'fisica',     'fase_1'),
      simCol('QUI_F1', 'Química',    '1°F', 'quimica',    'fase_1'),
      simCol('MAT_F2', 'Matemática', '2°F', 'matematica', 'fase_2', { novaFase: true }),
      simCol('FIS_F2', 'Física',     '2°F', 'fisica',     'fase_2'),
      simCol('QUI_F2', 'Química',    '2°F', 'quimica',    'fase_2'),
      simCol('RED_F2', 'Redação',    '2°F', 'redacao',    'fase_2'),
      simCol('POR_F2', 'Português',  '2°F', 'portugues',  'fase_2'),
      simCol('ING_F2', 'Inglês',     '2°F', 'ingles',     'fase_2'),
      mediaCol('MED_FINAL', 'Média', 'Final'),
    ],
    somenteF1: [
      simCol('MAT_F1', 'Matemática', '1°F', 'matematica', 'fase_1'),
      simCol('FIS_F1', 'Física',     '1°F', 'fisica',     'fase_1'),
      simCol('QUI_F1', 'Química',    '1°F', 'quimica',    'fase_1'),
      mediaCol('MED_F1', 'Média',    '1°F'),
    ],
    somenteF2: [
      simCol('MAT_F2', 'Matemática', '2°F', 'matematica', 'fase_2'),
      simCol('FIS_F2', 'Física',     '2°F', 'fisica',     'fase_2'),
      simCol('QUI_F2', 'Química',    '2°F', 'quimica',    'fase_2'),
      simCol('RED_F2', 'Redação',    '2°F', 'redacao',    'fase_2'),
      simCol('POR_F2', 'Português',  '2°F', 'portugues',  'fase_2'),
      simCol('ING_F2', 'Inglês',     '2°F', 'ingles',     'fase_2'),
      mediaCol('MED_FINAL', 'Média', 'Final'),
    ],
  },
};

// ─── Helpers ──────────────────────────────────────────────────────────────

function normMateria(s) {
  return (s || '').toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z]/g, '');
}

function obterEsquema(vestibular, temF1, temF2) {
  const vest = (vestibular || '').toUpperCase();
  const variante = (temF1 && temF2) ? 'completo' : temF2 ? 'somenteF2' : 'somenteF1';
  return ESQUEMA[vest]?.[variante] ?? null;
}

function encontrarSimulado(sims, simKey) {
  if (!simKey) return null;
  return sims.find((s) =>
    s.tipo === simKey.tipo &&
    normMateria(s.materia?.nome || s.materia?.codigo || '') === simKey.normNome
  ) ?? null;
}

function buildColunasDinamicas(simsDociclo) {
  const visto = new Set();
  return simsDociclo
    .filter((s) => s.materia)
    .flatMap((s) => {
      const k = `${normMateria(s.materia.nome)}_${s.tipo}`;
      if (visto.has(k)) return [];
      visto.add(k);
      return [simCol(k, s.materia.nome, s.tipo === 'fase_1' ? '1°F' : '2°F',
                     normMateria(s.materia.nome), s.tipo)];
    });
}

function buildNotasAluno(alunos, simsDociclo, notasPorSim) {
  const mapa = {};
  for (const aluno of alunos) mapa[aluno.id] = {};
  for (const sim of simsDociclo) {
    const notas = notasPorSim[sim.id] || [];
    for (const { alunoId, nota } of notas) {
      if (mapa[alunoId]) mapa[alunoId][sim.id] = nota;
    }
  }
  return mapa;
}

function mediaGeralAluno(alunoId, notasAluno, colunas) {
  const vals = colunas
    .filter((c) => !c.virtual && c.sim)
    .map((c) => notasAluno[alunoId]?.[c.sim.id])
    .filter((v) => v != null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

// Calcula valores das colunas virtuais (médias) por aluno, respeitando as
// fórmulas de cada vestibular. Nota ausente (−) = 0,0.
function calcularMediasVirtuais(alunoId, colunas, notasAluno, vestibular) {
  const vest = (vestibular || '').toUpperCase();
  const computed = {};

  // Retorna valor de uma coluna (real ou virtual). Ausente = 0.
  function v(colId) {
    const col = colunas.find((c) => c.id === colId);
    if (!col) return 0;
    if (col.virtual) return computed[colId] ?? 0;
    if (!col.sim) return 0;
    return notasAluno[alunoId]?.[col.sim.id] ?? 0;
  }

  function media(...ids) {
    const vals = ids.map(v);
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  if (vest === 'ITA') {
    if (colunas.some((c) => c.id === 'MED_F1')) {
      computed['MED_F1'] = media('MAT_F1', 'FIS_F1', 'QUI_F1');
    }
    if (colunas.some((c) => c.id === 'MED_FINAL')) {
      const ling = media('RED_F2', 'POR_F2');
      const [m2, f2, q2, med1] = ['MAT_F2', 'FIS_F2', 'QUI_F2', 'MED_F1'].map(v);
      computed['MED_FINAL'] = (m2 + f2 + q2 + med1 + ling) / 5;
    }
  } else if (vest === 'IME') {
    if (colunas.some((c) => c.id === 'MED_F1')) {
      computed['MED_F1'] = media('MAT_F1', 'FIS_F1', 'QUI_F1');
    }
    if (colunas.some((c) => c.id === 'MED_FINAL')) {
      const [m, f, q, p, i] = ['MAT_F2', 'FIS_F2', 'QUI_F2', 'POR_F2', 'ING_F2'].map(v);
      computed['MED_FINAL'] = (3 * m + 2.5 * f + 2.5 * q + p + i) / 10;
    }
  }

  return computed;
}


// ─── Componente principal ─────────────────────────────────────────────────

export async function renderPainel({ sidebarEl } = {}) {
  const api = getApiClient();

  const [ciclos, alunos, simulados, sedes, turmas] = await Promise.all([
    api.listarCiclos(),
    api.listarAlunos(),
    api.listarSimulados(),
    api.listarSedes().catch(() => []),
    api.listarTurmas().catch(() => []),
  ]);

  const root = el('section', { class: 'card' }, []);

  const estado = {
    cicloId: ciclos[0]?.id ?? null,
    notasPorSim: {},
    carregando: false,
    sedeIds: new Set(),
    turmaIds: new Set(),
    busca: '',
    ordenacao: 'ranking',
    fase: '1',
    limitesCollapsed: new Set(),
    aberto: { ciclos: true, sede: false, turmas: false },
  };

  // ── DOM split: header e tabela separados ───────────────────────────────
  const headerEl = el('div', {}, []);
  const tabelaEl = el('div', {}, []);
  root.appendChild(headerEl);
  root.appendChild(tabelaEl);

  // ── Filtrar alunos (sem ordenação — a ordem é feita em renderTabelaDados) ─
  function filtrarAlunos() {
    let lista = alunos.slice();
    if (estado.sedeIds.size > 0) {
      lista = lista.filter((a) => estado.sedeIds.has(a.sedeId));
    }
    if (estado.turmaIds.size > 0) {
      lista = lista.filter((a) => estado.turmaIds.has(a.turmaId));
    }
    if (estado.busca.trim()) {
      const q = normMateria(estado.busca);
      lista = lista.filter((a) => normMateria(a.nome).includes(q));
    }
    return lista;
  }

  // ── Renderizar só a tabela ─────────────────────────────────────────────
  function renderizarTabela() {
    const cicloAtivo = ciclos.find((c) => c.id === estado.cicloId);
    clear(tabelaEl);
    if (estado.carregando) {
      tabelaEl.appendChild(
        el('div', { class: 'section' }, [
          el('p', { class: 'section__subtitle' }, ['Carregando notas…']),
        ])
      );
      return;
    }
    function onToggleLimite(n) {
      if (estado.limitesCollapsed.has(n)) estado.limitesCollapsed.delete(n);
      else estado.limitesCollapsed.add(n);
      renderizarTabela();
    }
    const toggler = estado.ordenacao === 'ranking' ? onToggleLimite : null;
    tabelaEl.appendChild(renderTabelaDados(cicloAtivo, estado, simulados, alunos, filtrarAlunos, toggler, editarNota));
  }

  // ── Renderizar header (muda só ao trocar de ciclo) ─────────────────────
  function renderizarHeader() {
    const cicloAtivo = ciclos.find((c) => c.id === estado.cicloId);
    clear(headerEl);
    headerEl.appendChild(
      el('div', { class: 'painel-header' }, [
        el('div', { class: 'painel-header__esq' }, [
          el('div', { class: 'screen-breadcrumb' }, ['Painel']),
          el('h1', { class: 'screen-title' }, ['Panorama geral']),
          el('p', { class: 'screen-subtitle' }, [
            cicloAtivo ? cicloAtivo.nome : 'Selecione um ciclo na barra lateral.',
          ]),
        ]),
        el('div', { class: 'painel-header__dir' }, [
          el('div', { class: 'painel-header__controles' }, [
            buildHelpBtn(),
            buildBusca(),
            buildOrdenacaoPills(),
          ]),
          ...(fasesDisponiveis().length >= 2 ? [buildFaseFiltro()] : []),
        ]),
      ])
    );
  }

  // Fases presentes nos simulados do ciclo ativo ('1' e/ou '2').
  function fasesDisponiveis() {
    const ciclo = ciclos.find((c) => c.id === estado.cicloId);
    if (!ciclo) return [];
    const sims = simulados.filter((s) => ciclo.simuladoIds.includes(s.id));
    const fases = [];
    if (sims.some((s) => s.tipo === 'fase_1')) fases.push('1');
    if (sims.some((s) => s.tipo === 'fase_2')) fases.push('2');
    return fases;
  }

  function buildFaseFiltro() {
    const fasesDisp = fasesDisponiveis();
    if (!fasesDisp.includes(estado.fase)) estado.fase = fasesDisp[0];
    const labels = { '1': '1ª Fase', '2': '2ª Fase' };
    const wrap = el('div', { class: 'painel-fase-filtro' }, fasesDisp.map((f) => {
      const btn = el('button', {
        class: `painel-topn__btn${estado.fase === f ? ' is-active' : ''}`,
      }, [labels[f]]);
      btn.addEventListener('click', () => {
        estado.fase = f;
        Array.from(wrap.querySelectorAll('.painel-topn__btn')).forEach((b, i) => {
          b.classList.toggle('is-active', fasesDisp[i] === f);
        });
        renderizarTabela();
      });
      return btn;
    }));
    return wrap;
  }

  function buildBusca() {
    const input = el('input', {
      class: 'painel-busca',
      type: 'text',
      placeholder: 'Buscar aluno…',
      value: estado.busca,
    }, []);
    input.addEventListener('input', (e) => {
      estado.busca = e.target.value;
      renderizarTabela();
    });
    return el('div', { class: 'painel-busca-wrap' }, [
      svgIcon('search'),
      input,
    ]);
  }

  function buildOrdenacaoPills() {
    const opcoes = [
      { label: 'Ranking', value: 'ranking' },
      { label: 'A–Z', value: 'alfabetica' },
    ];
    return el('div', { class: 'painel-topn' }, opcoes.map(({ label, value }) => {
      const btn = el('button', {
        class: `painel-topn__btn${estado.ordenacao === value ? ' is-active' : ''}`,
      }, [label]);
      btn.addEventListener('click', () => {
        estado.ordenacao = value;
        const wrap = btn.parentElement;
        if (wrap) {
          Array.from(wrap.querySelectorAll('.painel-topn__btn')).forEach((b, i) => {
            b.classList.toggle('is-active', opcoes[i].value === value);
          });
        }
        renderizarTabela();
      });
      return btn;
    }));
  }

  function buildHelpBtn() {
    const itens = [
      'Selecione um ciclo na barra lateral para carregar os dados.',
      'Filtre por Sede e Turmas na barra lateral (múltipla seleção).',
      'Use a busca para encontrar um aluno específico.',
      'Ordene por Geral (média final ponderada) ou 1ª Fase.',
      'Clique nos separadores Top 10 / 50 / 100 para ocultar ou exibir os alunos abaixo.',
    ];
    const legendas = [
      { cor: 'verde',    texto: 'Verde — sem cortes (todas as notas ≥ 5,0)' },
      { cor: 'vermelho', texto: 'Vermelho — cortado em alguma matéria (nota < 5,0)' },
    ];
    const tooltip = el('div', { class: 'painel-help-tooltip' }, [
      el('p', { class: 'painel-help-titulo' }, ['Legenda & funcionalidades']),
      el('ul', { class: 'painel-help-lista' }, itens.map((t) => el('li', {}, [t]))),
      el('div', { class: 'painel-help-sep' }, []),
      ...legendas.map(({ cor, texto }) =>
        el('div', { class: 'painel-help-legenda' }, [
          el('span', { class: `painel-help-dot painel-help-dot--${cor}` }, []),
          texto,
        ])
      ),
    ]);
    tooltip.style.display = 'none';

    const btn = el('button', { class: 'painel-help-btn' }, ['?']);
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      tooltip.style.display = tooltip.style.display === 'none' ? '' : 'none';
    });
    document.addEventListener('click', () => { tooltip.style.display = 'none'; });

    return el('div', { class: 'painel-help-wrap' }, [btn, tooltip]);
  }

  // ── Sidebar com 3 seções ───────────────────────────────────────────────
  function atualizarSidebar() {
    if (!sidebarEl) return;
    clear(sidebarEl);
    sidebarEl.appendChild(buildSidebarConteudo());
  }

  function buildSidebarConteudo() {
    return el('div', { class: 'psb-root' }, [
      buildSecao('ciclos', 'Ciclos', svgIcon('ciclos'), buildCicloItems()),
      buildSecao('sede',   'Sede',   svgIcon('sede'),   buildSedeItems()),
      buildSecao('turmas', 'Turmas', svgIcon('turmas'), buildTurmaItems()),
    ]);
  }

  function buildSecao(chave, label, icon, corpo) {
    const isAberto = estado.aberto[chave];
    const chevron = el('span', { class: `psb-secao__chevron${isAberto ? ' is-aberto' : ''}` }, [
      svgIcon('chevron'),
    ]);
    const corpoEl = el('div', {
      class: 'psb-secao__corpo',
      style: isAberto ? '' : 'display:none',
    }, corpo);
    const header = el('button', { class: 'psb-secao__header' }, [
      el('span', { class: 'psb-secao__icon' }, [icon]),
      el('span', { class: 'psb-secao__label' }, [label]),
      chevron,
    ]);
    header.addEventListener('click', () => {
      estado.aberto[chave] = !estado.aberto[chave];
      chevron.classList.toggle('is-aberto', estado.aberto[chave]);
      corpoEl.style.display = estado.aberto[chave] ? '' : 'none';
    });
    return el('div', { class: 'psb-secao' }, [header, corpoEl]);
  }

  function buildCicloItems() {
    return ciclos.map((c) => {
      const btn = el('button', {
        class: `psb-item${c.id === estado.cicloId ? ' is-active' : ''}`,
      }, [c.nome]);
      btn.addEventListener('click', () => selecionarCiclo(c.id));
      return btn;
    });
  }

  const NOMES_SEDE = {
    'AD':                 'Aldeota',
    'MF':                 'Major Facundo',
    'ONLINE':             'Online',
    'PROPOSITO':          'Propósito',
    'ONLINE_E_PROPOSITO': 'Online e Propósito',
    'PB':                 'Parangaba',
    '3O_ITA_MF_E_ONLINE': 'Terceiro Ano ITA',
  };

  function nomeSede(raw) {
    return NOMES_SEDE[raw] ?? raw.replace(/_/g, ' ').replace(/\b3O\b/g, '3°');
  }

  function buildSedeItems() {
    return sedes
      .filter((s) => !s.nome.startsWith('2025_'))
      .map((s) => {
        const checked = estado.sedeIds.has(s.id);
        const item = el('button', { class: `psb-item psb-item--check${checked ? ' is-active' : ''}` }, [
          el('span', { class: `psb-item__check${checked ? ' is-checked' : ''}` }, []),
          nomeSede(s.nome),
        ]);
        item.addEventListener('click', () => {
          if (estado.sedeIds.has(s.id)) estado.sedeIds.delete(s.id);
          else estado.sedeIds.add(s.id);
          item.classList.toggle('is-active', estado.sedeIds.has(s.id));
          item.querySelector('.psb-item__check').classList.toggle('is-checked', estado.sedeIds.has(s.id));
          renderizarTabela();
        });
        return item;
      });
  }

  function buildTurmaItems() {
    return turmas.map((t) => {
      const checked = estado.turmaIds.has(t.id);
      const item = el('button', { class: `psb-item psb-item--check${checked ? ' is-active' : ''}` }, [
        el('span', { class: `psb-item__check${checked ? ' is-checked' : ''}` }, []),
        t.nome,
      ]);
      item.addEventListener('click', () => {
        if (estado.turmaIds.has(t.id)) estado.turmaIds.delete(t.id);
        else estado.turmaIds.add(t.id);
        item.classList.toggle('is-active', estado.turmaIds.has(t.id));
        item.querySelector('.psb-item__check').classList.toggle('is-checked', estado.turmaIds.has(t.id));
        renderizarTabela();
      });
      return item;
    });
  }

  // ── Estatísticas de comparação para a ficha de nota ──────────────────
  function computarEstatisticasSimulado(simId, alunoId) {
    const notas = estado.notasPorSim[simId] || [];
    const presentes = notas
      .filter((n) => n.presente && n.nota != null)
      .map((n) => n.nota)
      .sort((a, b) => b - a);
    if (!presentes.length) return null;
    const n = presentes.length;
    const entrada = notas.find((x) => x.alunoId === alunoId);
    const nota = entrada?.nota ?? null;
    const posicao = nota != null ? presentes.filter((v) => v > nota).length + 1 : null;
    const media = presentes.reduce((a, b) => a + b, 0) / n;
    const maiorNota = presentes[0];
    const q = Math.max(1, Math.ceil(n * 0.15));
    const mediaTop15 = presentes.slice(0, q).reduce((a, b) => a + b, 0) / q;
    const mediaBottom15 = presentes.slice(-q).reduce((a, b) => a + b, 0) / q;
    const mediana = n % 2 === 0
      ? (presentes[n / 2 - 1] + presentes[n / 2]) / 2
      : presentes[Math.floor(n / 2)];
    return { posicao, totalPresentes: n, nota, media, maiorNota, mediaTop15, mediaBottom15, mediana };
  }

  // ── Edição de nota direto do painel ───────────────────────────────────
  async function editarNota(alunoId, simId) {
    const aluno = alunos.find((a) => a.id === alunoId);
    const sim = simulados.find((s) => s.id === simId);
    if (!aluno || !sim) return;

    const notaAtual = (estado.notasPorSim[simId] || []).find((n) => n.alunoId === alunoId);
    const resultado = await abrirFichaNota({
      nomeAluno: aluno.nome,
      nomeSimulado: sim.rotuloCurto || sim.nome,
      pontuacaoAtual: notaAtual?.acertos ?? null,
      presenteAtual: notaAtual?.presente ?? true,
      notaMaxima: notaAtual?.total ?? sim.notaMaxima ?? null,
      stats: computarEstatisticasSimulado(simId, alunoId),
    });
    if (!resultado) return;

    try {
      await api.editarNota(alunoId, simId, resultado);
      api.limparCacheDados();
      await carregarNotas();
      renderizarTabela();
    } catch (err) {
      alert(`Erro ao salvar: ${err.message}`);
    }
  }

  // ── Troca de ciclo ─────────────────────────────────────────────────────
  async function carregarNotas() {
    const ciclo = ciclos.find((c) => c.id === estado.cicloId);
    if (!ciclo) { estado.notasPorSim = {}; return; }
    const simsDociclo = simulados.filter((s) => ciclo.simuladoIds.includes(s.id));
    const resultados = await Promise.all(
      simsDociclo.map((s) => api.notasSimulado(s.id).catch(() => []))
    );
    const mapa = {};
    simsDociclo.forEach((s, i) => { mapa[s.id] = resultados[i] ?? []; });
    estado.notasPorSim = mapa;
  }

  async function selecionarCiclo(id) {
    if (estado.cicloId === id) return;
    estado.cicloId = id;
    estado.busca = '';
    estado.carregando = true;
    atualizarSidebar();
    renderizarHeader();
    renderizarTabela();
    await carregarNotas();
    estado.carregando = false;
    renderizarTabela();
  }

  // ── Bootstrap ──────────────────────────────────────────────────────────
  estado.carregando = true;
  renderizarHeader();
  renderizarTabela();
  atualizarSidebar();
  await carregarNotas();
  estado.carregando = false;
  renderizarTabela();

  return root;
}


// ─── Tabela de dados ──────────────────────────────────────────────────────

function renderTabelaDados(cicloAtivo, estado, todosSim, todosAlunos, filtrarAlunos, onToggleLimite, onEditarNota) {
  if (!cicloAtivo) {
    return el('div', { class: 'empty-state' }, ['Selecione um ciclo na barra lateral.']);
  }

  const simsDociclo = todosSim
    .filter((s) => cicloAtivo.simuladoIds.includes(s.id))
    .sort((a, b) => (a.dataAplicacao || '').localeCompare(b.dataAplicacao || ''));

  const temF1 = simsDociclo.some((s) => s.tipo === 'fase_1');
  const temF2 = simsDociclo.some((s) => s.tipo === 'fase_2');

  const esquema = obterEsquema(cicloAtivo.vestibularAlvo, temF1, temF2);
  const colunasDef = esquema ?? buildColunasDinamicas(simsDociclo);

  if (colunasDef.length === 0) {
    return el('div', { class: 'empty-state' }, [
      'Nenhum simulado com matéria e fase definidos neste ciclo.',
    ]);
  }

  // Conjunto completo de colunas — usado para CALCULAR as médias (a média
  // geral depende de matérias das duas fases, mesmo quando só uma é exibida).
  const colunasFull = colunasDef.map((c) => ({
    ...c,
    sim: c.virtual ? null : encontrarSimulado(simsDociclo, c.simKey),
  }));

  const notasAluno = buildNotasAluno(todosAlunos, simsDociclo, estado.notasPorSim);
  const alunosFiltrados = filtrarAlunos();
  const vestibular = cicloAtivo.vestibularAlvo;

  // Médias virtuais por aluno (fórmulas por vestibular) — sempre sobre o
  // conjunto completo de colunas.
  const mediasVirtuaisAluno = {};
  for (const aluno of alunosFiltrados) {
    mediasVirtuaisAluno[aluno.id] = calcularMediasVirtuais(aluno.id, colunasFull, notasAluno, vestibular);
  }

  // Filtro de fase: cada fase exibe suas matérias + a média geral.
  const fasesDisp = [];
  if (temF1) fasesDisp.push('1');
  if (temF2) fasesDisp.push('2');
  const faseSel = fasesDisp.includes(estado.fase) ? estado.fase : fasesDisp[0];
  estado.fase = faseSel;
  const colunas = colunasExibidas(colunasFull, faseSel);

  // Ordenação
  if (estado.ordenacao === 'alfabetica') {
    alunosFiltrados.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  } else {
    const getValorOrdenacao = (alunoId) => {
      const mv = mediasVirtuaisAluno[alunoId] || {};
      if (mv['MED_FINAL'] != null) return mv['MED_FINAL'];
      if (mv['MED_F1'] != null) return mv['MED_F1'];
      return mediaGeralAluno(alunoId, notasAluno, colunas) ?? -Infinity;
    };
    alunosFiltrados.sort((a, b) => getValorOrdenacao(b.id) - getValorOrdenacao(a.id));
  }

  // Médias da turma por coluna (reais + virtuais, sobre alunos filtrados)
  const mediasPorCol = {};
  for (const col of colunas) {
    if (!col.virtual && col.sim) {
      const vals = alunosFiltrados
        .map((a) => notasAluno[a.id]?.[col.sim.id])
        .filter((v) => v != null);
      mediasPorCol[col.id] = vals.length > 0
        ? vals.reduce((acc, v) => acc + v, 0) / vals.length
        : null;
    } else if (col.virtual) {
      const vals = alunosFiltrados
        .map((a) => mediasVirtuaisAluno[a.id]?.[col.id])
        .filter((v) => v != null);
      mediasPorCol[col.id] = vals.length > 0
        ? vals.reduce((acc, v) => acc + v, 0) / vals.length
        : null;
    }
  }

  return el('div', { class: 'painel-tabela-wrap' }, [
    el('table', { class: 'painel-tabela' }, [
      renderThead(colunas),
      renderTbody(alunosFiltrados, colunas, notasAluno, mediasVirtuaisAluno, mediasPorCol, estado.limitesCollapsed, onToggleLimite, onEditarNota),
    ]),
  ]);
}

// Colunas exibidas para a fase selecionada: matérias da fase + média geral.
function colunasExibidas(colunasFull, faseSel) {
  const faseLabel = faseSel === '1' ? '1°F' : '2°F';
  const materias = colunasFull.filter((c) => !c.virtual && c.fase === faseLabel);
  const virtuais = colunasFull.filter((c) => c.virtual);
  const geral = virtuais[virtuais.length - 1] || null; // MED_FINAL (ou MED_F1 em ciclos só de 1ª fase)
  return geral ? [...materias, geral] : materias;
}

function colClasses(...extras) {
  return extras.filter(Boolean).join(' ');
}

function renderThead(colunas) {
  const row1 = [
    el('th', { class: 'painel-tabela__th-pos', rowspan: '2' }, ['#']),
    el('th', { class: 'painel-tabela__th-aluno', rowspan: '2' }, ['Aluno']),
    ...colunas.map((col) =>
      el('th', {
        class: colClasses(
          'painel-tabela__th-col',
          col.novaFase && 'borda-nova-fase',
          col.destaque && 'col-destaque'
        ),
      }, [col.label])
    ),
  ];

  const row2 = colunas.map((col) =>
    el('th', {
      class: colClasses(
        'painel-tabela__th-fase',
        col.novaFase && 'borda-nova-fase',
        col.destaque && 'col-destaque'
      ),
    }, [col.fase])
  );

  return el('thead', {}, [
    el('tr', {}, row1),
    el('tr', {}, row2),
  ]);
}

// Posições onde aparece o separador de ranking
const LIMITES_RANKING = [10, 50, 100];

function statusNomeAluno(alunoId, colunas, notasAluno) {
  const simCols = colunas.filter((c) => !c.virtual && c.sim);
  if (simCols.length === 0) return 'neutro';
  const allOk = simCols.every((c) => {
    const n = notasAluno[alunoId]?.[c.sim.id];
    return n != null && n >= 5;
  });
  return allOk ? 'aprovado' : 'cortado';
}

function renderSeparadorRow(pos, colCount, limitesCollapsed, onToggleLimite) {
  const collapsed = limitesCollapsed.has(pos);
  const btnLabel = collapsed ? `▼ exibir abaixo do ${pos}°` : `▲ ocultar abaixo do ${pos}°`;
  const btn = el('button', { class: 'painel-corte__btn' }, [btnLabel]);
  btn.addEventListener('click', () => onToggleLimite(pos));
  return el('tr', { class: 'painel-corte-row' }, [
    el('td', { class: 'painel-corte__label', colspan: String(colCount + 2) }, [
      el('span', { class: 'painel-corte__tag' }, [`Top ${pos}`]),
      btn,
    ]),
  ]);
}

function posicaoBadge(pos) {
  return el('span', { class: 'pos-badge' }, [String(pos)]);
}

function renderTbody(alunos, colunas, notasAluno, mediasVirtuaisAluno, mediasPorCol, limitesCollapsed, onToggleLimite, onEditarNota) {
  const trMedia = el('tr', { class: 'painel-tabela__tr-media' }, [
    el('td', { class: 'painel-tabela__td-pos' }, []),
    el('td', { class: 'painel-tabela__td-aluno' }, ['Média da turma']),
    ...colunas.map((col) =>
      el('td', { class: tdClass(col) }, [notaBadge(mediasPorCol[col.id] ?? null, true)])
    ),
  ]);

  const colCount = colunas.length;
  const rows = [];

  for (let i = 0; i < alunos.length; i++) {
    const pos = i + 1;
    // Ocultar linhas que estão além de algum limite colapsado
    if (LIMITES_RANKING.some((l) => l < pos && limitesCollapsed.has(l))) continue;

    const aluno = alunos[i];
    const status = statusNomeAluno(aluno.id, colunas, notasAluno);
    const linkExtra = status === 'cortado' ? ' is-cortado' : status === 'aprovado' ? ' is-aprovado' : '';

    rows.push(el('tr', {}, [
      el('td', { class: 'painel-tabela__td-pos' }, [posicaoBadge(pos)]),
      el('td', { class: 'painel-tabela__td-aluno' }, [
        el('a', { class: `painel-tabela__aluno-link${linkExtra}`, href: `#/alunos/${aluno.id}`, title: aluno.nome }, [aluno.nome]),
      ]),
      ...colunas.map((col) => {
        const nota = col.virtual
          ? (mediasVirtuaisAluno[aluno.id]?.[col.id] ?? null)
          : (col.sim ? (notasAluno[aluno.id]?.[col.sim.id] ?? null) : null);
        const editavel = !col.virtual && col.sim && onEditarNota;
        return el('td', {
          class: tdClass(col) + (editavel ? ' is-editavel' : ''),
          onclick: editavel ? (ev) => { ev.stopPropagation(); onEditarNota(aluno.id, col.sim.id); } : null,
        }, [notaBadge(nota)]);
      }),
    ]));

    // Inserir separador de ranking após a posição N (apenas no modo ranking)
    if (onToggleLimite && LIMITES_RANKING.includes(pos) && i < alunos.length - 1) {
      rows.push(renderSeparadorRow(pos, colCount, limitesCollapsed, onToggleLimite));
    }
  }

  return el('tbody', {}, [trMedia, ...rows]);
}

function tdClass(col) {
  return colClasses(
    'painel-tabela__td-nota',
    col.novaFase && 'borda-nova-fase',
    col.destaque && 'col-destaque'
  );
}

function notaBadge(nota, isTurma = false) {
  if (nota == null) return el('span', { class: 'nota-badge nota-badge--vazia' }, ['—']);
  const tone = nota >= 7 ? 'verde' : nota >= 5 ? 'ambar' : 'vermelho';
  return el('span', {
    class: `nota-badge nota-badge--${tone}${isTurma ? ' nota-badge--media' : ''}`,
  }, [fmtNota(nota)]);
}
