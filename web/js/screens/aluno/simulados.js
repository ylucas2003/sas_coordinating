// Tela Simulados do aluno: lista + detalhe.
// Detalhe mostra ranking, range bar e dot grid com PRNG seeded (sem gabarito real).

import { el, clear } from '../../dom.js';
import { getApiClient } from '../../services/api.js';

// ─── Utilitários ─────────────────────────────────────────────────────────

function fmt(n, d = 1) {
  if (n == null) return '—';
  return Number(n).toFixed(d).replace('.', ',');
}

function fmtData(iso) {
  if (!iso) return '—';
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' }).replace(/\./g, '');
}

// ─── SVG helpers ─────────────────────────────────────────────────────────

function svgEl(tag, attrs = {}) {
  const ns = 'http://www.w3.org/2000/svg';
  const node = document.createElementNS(ns, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}

function icon(d, size = 18, color = 'currentColor', sw = 1.8) {
  const svg = svgEl('svg', {
    width: size, height: size, viewBox: '0 0 24 24',
    fill: 'none', stroke: color, 'stroke-width': sw,
    'stroke-linecap': 'round', 'stroke-linejoin': 'round',
  });
  svg.style.cssText = 'display:block;flex-shrink:0';
  svg.appendChild(svgEl('path', { d }));
  return svg;
}

// ─── PRNG seeded (gabarito simulado) ─────────────────────────────────────

function seededRng(seed) {
  let s = typeof seed === 'string'
    ? [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 0)
    : (seed | 0);
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xFFFFFFFF;
  };
}

function mockDotGrid(simuladoId, nota) {
  const totalQ = 45;
  const certas = Math.round((nota / 10) * totalQ);
  const erradas = totalQ - certas;
  const rng = seededRng(simuladoId);

  const order = Array.from({ length: totalQ }, (_, i) => i);
  order.sort(() => rng() - 0.5);
  const certasIdx = new Set(order.slice(0, certas));

  return Array.from({ length: totalQ }, (_, i) => ({
    num: i + 1,
    correct: certasIdx.has(i),
  }));
}

// ─── Cores por matéria e vestibular ──────────────────────────────────────

const MAT_COR = {
  'Matemática': { bg: '#E7EDF8', fg: '#16356A' },
  'Física':     { bg: '#EAF0F9', fg: '#2E5490' },
  'Química':    { bg: '#E2F2EA', fg: '#2C7355' },
  'Português':  { bg: '#F7ECDA', fg: '#9A6F32' },
  'Inglês':     { bg: '#F0EBF9', fg: '#5C3591' },
};

const VEST_COR = {
  'ITA': { bg: '#E7EDF8', fg: '#16356A' },
  'IME': { bg: '#EDE8F7', fg: '#4A2880' },
};

function _chip(label, bg, fg) {
  return el('span', { class: 'alu-sim-chip', style: `background:${bg};color:${fg}` }, [label]);
}

// ─── SVG: progress ring ───────────────────────────────────────────────────

function chartRing({ pct, size = 78, strokeW = 7, color = 'var(--alu-up)', track = 'var(--color-border)' }) {
  const r = size / 2 - strokeW / 2;
  const c = 2 * Math.PI * r;
  const wrap = el('div', { class: 'alu-ring', style: `width:${size}px;height:${size}px;flex-shrink:0` });

  const svg = svgEl('svg', { width: size, height: size });
  svg.style.cssText = `display:block;transform:rotate(-90deg)`;

  const bg = svgEl('circle', { cx: size/2, cy: size/2, r, fill: 'none', stroke: track, 'stroke-width': strokeW });
  const fg = svgEl('circle', {
    cx: size/2, cy: size/2, r, fill: 'none', stroke: color, 'stroke-width': strokeW,
    'stroke-dasharray': `${c * Math.min(1, Math.max(0, pct))} ${c}`,
    'stroke-linecap': 'round',
  });
  svg.appendChild(bg);
  svg.appendChild(fg);
  wrap.appendChild(svg);

  return wrap;
}

// ─── SVG: range bar ───────────────────────────────────────────────────────

function chartRange({ min = 0, max = 10, markers, width = 500, height = 62 }) {
  const padX = 18, trackY = 30, trackW = width - padX * 2;
  const X = v => padX + ((v - min) / (max - min)) * trackW;

  const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}` });
  svg.style.cssText = 'display:block;overflow:visible';
  const defs = svgEl('defs');

  const gradId = 'alu-rg-sim';
  const grad = svgEl('linearGradient', { id: gradId, x1: 0, y1: 0, x2: 1, y2: 0 });
  [['0%', '#F7ECDA'], ['40%', '#f5f7fb'], ['100%', '#E2F2EA']].forEach(([off, col]) => {
    grad.appendChild(svgEl('stop', { offset: off, 'stop-color': col }));
  });
  defs.appendChild(grad);
  svg.appendChild(defs);

  svg.appendChild(svgEl('rect', {
    x: padX, y: trackY - 4, width: trackW, height: 8, rx: 4, fill: `url(#${gradId})`,
  }));

  markers.forEach(m => {
    const x = X(m.value);
    const isYou = m.you;
    const g = svgEl('g');

    g.appendChild(svgEl('line', {
      x1: x, x2: x,
      y1: trackY - (isYou ? 14 : 8),
      y2: trackY + (isYou ? 14 : 8),
      stroke: m.color, 'stroke-width': isYou ? 3 : 2, 'stroke-linecap': 'round',
    }));

    if (isYou) {
      g.appendChild(svgEl('circle', {
        cx: x, cy: trackY, r: 6, fill: m.color, stroke: '#fff', 'stroke-width': 2,
      }));
    }

    const t = svgEl('text', {
      x, y: isYou ? trackY - 20 : height - 3,
      'text-anchor': 'middle',
      'font-size': isYou ? 11 : 9.5,
      'font-weight': isYou ? 600 : 400,
      fill: isYou ? '#1C2436' : '#9097a8',
      'font-family': 'inherit',
    });
    t.textContent = m.label;
    g.appendChild(t);

    svg.appendChild(g);
  });

  return svg;
}

// ─── Card de simulado na lista ────────────────────────────────────────────

function _simCard(sim, onClick) {
  const delta = sim.deltaSelf;
  const hasDelta = delta != null;
  const deltaClass = hasDelta
    ? delta >= 0 ? 'alu-delta--up' : 'alu-delta--down'
    : 'alu-delta--neutral';
  const deltaLabel = hasDelta
    ? `${delta >= 0 ? '+' : ''}${fmt(delta)}`
    : '—';

  const notaColor = sim.nota >= 7 ? 'var(--alu-up-deep)'
    : sim.nota >= 5 ? 'var(--color-text-primary)'
    : 'var(--alu-calm-deep)';

  const card = el('div', { class: 'alu-sim-card', onclick: onClick });

  // Ícone
  card.appendChild(el('div', { class: 'alu-sim-icon' }, [
    icon('M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M9 13h6 M9 17h4', 20, 'var(--color-navy)', 1.7),
  ]));

  // Info: nome + chips de contexto
  const infoEl = el('div', { class: 'alu-sim-info' });

  const nomeEl = el('div', { class: 'alu-sim-nome' }, [sim.rotulo || sim.nome || '—']);
  if (sim.novo) nomeEl.appendChild(el('span', { class: 'alu-sim-novo' }, ['NOVO']));
  infoEl.appendChild(nomeEl);

  // Chips: matéria (colorida), vestibular (ITA/IME), ciclo, data
  const chipsEl = el('div', { class: 'alu-sim-chips' });
  const matCors = MAT_COR[sim.materia];
  if (sim.materia) chipsEl.appendChild(_chip(sim.materia, matCors?.bg ?? '#E7EDF8', matCors?.fg ?? '#16356A'));
  const vestCors = VEST_COR[sim.vestibularAlvo];
  if (sim.vestibularAlvo) chipsEl.appendChild(_chip(sim.vestibularAlvo, vestCors?.bg ?? '#E7EDF8', vestCors?.fg ?? '#16356A'));
  if (sim.cicloOrdem != null) chipsEl.appendChild(_chip(`Ciclo ${sim.cicloOrdem}`, 'var(--color-surface-inset)', 'var(--color-text-secondary)'));
  if (sim.dataAplicacao) chipsEl.appendChild(el('span', { class: 'alu-sim-date' }, [fmtData(sim.dataAplicacao)]));
  infoEl.appendChild(chipsEl);

  card.appendChild(infoEl);

  // Coluna direita: nota + delta + média turma
  const notaWrap = el('div', { class: 'alu-sim-nota-wrap' });
  notaWrap.appendChild(el('div', { class: 'alu-sim-nota', style: `color:${notaColor}` }, [fmt(sim.nota)]));
  notaWrap.appendChild(el('div', { class: `alu-delta ${deltaClass}`, style: 'justify-content:flex-end;margin-top:3px' }, [deltaLabel]));
  if (sim.mediaGeral != null) {
    notaWrap.appendChild(el('div', { class: 'alu-sim-date', style: 'text-align:right;margin-top:2px' }, [`turma ${fmt(sim.mediaGeral)}`]));
  }
  card.appendChild(notaWrap);

  // Chevron
  card.appendChild(icon('M9 18l6-6-6-6', 18, 'var(--color-text-tertiary)', 2));

  return card;
}

// ─── Lista de simulados ───────────────────────────────────────────────────

async function _renderLista({ nav }) {
  const api = getApiClient();
  const simulados = await api.listarSimuladosMe();

  if (!simulados.length) {
    return el('div', { class: 'alu-empty' }, [
      'Nenhum simulado corrigido ainda.',
      el('div', { class: 'alu-empty__sub' }, ['As notas aparecem assim que o coordenador lançar os resultados.']),
    ]);
  }

  const wrap = el('div', { style: 'display:flex;flex-direction:column;gap:18px' });

  const header = el('div', { style: 'display:flex;align-items:center;justify-content:space-between;gap:12px' }, [
    el('div', {}, [
      el('div', { style: 'font-size:22px;font-weight:700;letter-spacing:-0.4px;color:var(--color-text-primary);line-height:1.2' }, ['Meus Simulados']),
      el('div', { style: 'font-size:13px;color:var(--color-text-secondary);margin-top:2px' }, [`${simulados.length} resultado${simulados.length !== 1 ? 's' : ''} corrigidos`]),
    ]),
  ]);
  wrap.appendChild(header);

  const listEl = el('div', { class: 'alu-sim-list' });
  simulados.forEach(sim => {
    listEl.appendChild(_simCard(sim, () => nav.go('simulados', { simId: sim.id, simNome: sim.rotulo || sim.nome })));
  });
  wrap.appendChild(listEl);

  return wrap;
}

// ─── Detalhe de um simulado ───────────────────────────────────────────────

async function _renderDetalhe({ nav, simId, simNome }) {
  const api = getApiClient();
  const detalhe = await api.obterSimuladoMe(simId);

  const wrap = el('div', { style: 'display:flex;flex-direction:column;gap:18px' });

  // Back link
  wrap.appendChild(el('div', { class: 'alu-back-link', onclick: () => nav.go('simulados') }, [
    icon('M19 12H5 M12 19l-7-7 7-7', 15, 'currentColor', 2),
    'Todos os simulados',
  ]));

  // Header
  const headerEl = el('div', { class: 'alu-sim-detail__header' });
  headerEl.appendChild(el('div', { class: 'alu-sim-detail__titulo' }, [detalhe.rotulo || detalhe.nome || simNome || '—']));

  const detChips = el('div', { class: 'alu-sim-chips', style: 'margin-top:8px' });
  const dMatCors = MAT_COR[detalhe.materia];
  if (detalhe.materia) detChips.appendChild(_chip(detalhe.materia, dMatCors?.bg ?? '#E7EDF8', dMatCors?.fg ?? '#16356A'));
  const dVestCors = VEST_COR[detalhe.vestibularAlvo];
  if (detalhe.vestibularAlvo) detChips.appendChild(_chip(detalhe.vestibularAlvo, dVestCors?.bg ?? '#E7EDF8', dVestCors?.fg ?? '#16356A'));
  if (detalhe.dataAplicacao) detChips.appendChild(el('span', { class: 'alu-sim-date' }, [fmtData(detalhe.dataAplicacao)]));
  headerEl.appendChild(detChips);

  wrap.appendChild(headerEl);

  // Hero stats row
  const pct = detalhe.total > 1 ? 1 - (detalhe.posicao - 1) / detalhe.total : 0.5;
  const ringEl = chartRing({
    pct, size: 78, strokeW: 7,
    color: pct > 0.5 ? 'var(--alu-up)' : 'var(--alu-calm)',
    track: 'var(--color-border)',
  });

  const heroStats = el('div', { class: 'alu-card', style: 'padding:20px;display:flex;align-items:center;gap:20px;flex-wrap:wrap' }, [
    ringEl,
    el('div', { style: 'flex:1;min-width:0' }, [
      el('div', { style: 'display:flex;align-items:baseline;gap:10px;flex-wrap:wrap' }, [
        el('div', { style: 'font-size:48px;font-weight:700;letter-spacing:-1.5px;font-variant-numeric:tabular-nums;line-height:0.9;color:var(--color-navy-deep)' }, [fmt(detalhe.nota)]),
        el('div', { style: 'font-size:13px;color:var(--color-text-secondary)' }, ['nota geral · 0–10']),
      ]),
      el('div', { style: 'display:flex;gap:18px;flex-wrap:wrap;margin-top:14px;padding-top:14px;border-top:1px solid var(--color-border)' }, [
        { r: 'Posição', v: `${detalhe.posicao}º de ${detalhe.total}` },
        { r: 'Percentil', v: `${detalhe.percentil}%` },
        { r: 'Média da turma', v: fmt(detalhe.grupos?.geral) },
      ].map(x => el('div', {}, [
        el('div', { style: 'font-size:10.5px;color:var(--color-text-tertiary);margin-bottom:2px;white-space:nowrap' }, [x.r]),
        el('div', { style: 'font-size:15px;font-weight:600;color:var(--color-text-primary);font-variant-numeric:tabular-nums' }, [x.v]),
      ]))),
    ]),
  ]);
  wrap.appendChild(heroStats);

  // Comparison bar
  if (detalhe.grupos) {
    const g = detalhe.grupos;
    const vals = [g.bottom15, g.geral, g.voce, g.top15].filter(v => v != null);
    const rMin = Math.max(0, Math.min(...vals) - 0.5);
    const rMax = Math.min(10, Math.max(...vals) + 0.5);

    const rangeWrap = el('div', { style: 'overflow-x:auto' });
    rangeWrap.appendChild(chartRange({
      min: rMin, max: rMax, width: 500, height: 62,
      markers: [
        { value: g.bottom15, label: 'Inferior-15', color: 'var(--alu-calm)', you: false },
        { value: g.geral,    label: 'Média geral', color: 'var(--color-text-secondary)', you: false },
        { value: g.voce,     label: `Você · ${fmt(g.voce)}`, color: 'var(--alu-up)', you: true },
        { value: g.top15,    label: 'Top-15',      color: 'var(--color-navy)', you: false },
      ].filter(m => m.value != null),
    }));

    wrap.appendChild(el('div', { class: 'alu-card' }, [
      el('div', { class: 'alu-section-title' }, ['Comparação com a turma']),
      rangeWrap,
    ]));
  }

  // Dot grid layout (2 col: dot grid esquerda, revisar lista direita)
  const dots = mockDotGrid(simId, detalhe.nota);
  const wrongDots = dots.filter(d => !d.correct);

  const gridEl = el('div', { class: 'alu-sim-detail__grid' });

  // Dot grid
  const dotGridCard = el('div', { class: 'alu-card' }, [
    el('div', { class: 'alu-section-title' }, ['Resultado questão a questão']),
    el('div', { class: 'alu-dot-grid' },
      dots.map(d => el('div', { class: `alu-dot alu-dot--${d.correct ? 'correct' : 'wrong'}` }, [String(d.num)])),
    ),
    el('div', { style: 'display:flex;gap:14px;margin-top:4px;font-size:12px;color:var(--color-text-secondary)' }, [
      el('div', { style: 'display:flex;align-items:center;gap:5px' }, [
        el('span', { style: 'width:10px;height:10px;border-radius:3px;background:var(--alu-up-soft);display:inline-block;border:1px solid var(--alu-up)' }),
        `${dots.filter(d => d.correct).length} corretas`,
      ]),
      el('div', { style: 'display:flex;align-items:center;gap:5px' }, [
        el('span', { style: 'width:10px;height:10px;border-radius:3px;background:var(--alu-calm-soft);display:inline-block;border:1px solid var(--alu-calm)' }),
        `${wrongDots.length} erradas`,
      ]),
    ]),
    el('div', { style: 'font-size:10.5px;color:var(--color-text-tertiary);margin-top:6px;font-style:italic' }, [
      '* Distribuição estimada com base na nota. Gabarito detalhado em breve.',
    ]),
  ]);
  gridEl.appendChild(dotGridCard);

  // Lista de questões para revisar
  const revisarCard = el('div', { class: 'alu-card' }, [
    el('div', { class: 'alu-section-title' }, [`Para revisar (${wrongDots.length})`]),
  ]);

  if (!wrongDots.length) {
    revisarCard.appendChild(el('div', { class: 'alu-empty', style: 'padding:24px 0' }, [
      'Nenhuma questão errada? Perfeito!',
    ]));
  } else {
    const assuntos = _mockAssuntos(simId, wrongDots.length, detalhe.materia);
    const lista = el('div', { class: 'alu-revisar-list' });
    wrongDots.slice(0, 12).forEach((d, idx) => {
      lista.appendChild(el('div', { class: 'alu-revisar-item' }, [
        el('div', { class: 'alu-revisar-item__num' }, [String(d.num)]),
        el('div', { class: 'alu-revisar-item__info' }, [
          el('div', { class: 'alu-revisar-item__assunto' }, [assuntos[idx] || `Questão ${d.num}`]),
          el('div', { class: 'alu-revisar-item__hint' }, ['Análise por assunto em breve']),
        ]),
      ]));
    });
    if (wrongDots.length > 12) {
      lista.appendChild(el('div', { style: 'font-size:12px;color:var(--color-text-tertiary);text-align:center;padding-top:6px' }, [
        `+ ${wrongDots.length - 12} mais`,
      ]));
    }
    revisarCard.appendChild(lista);
  }

  gridEl.appendChild(revisarCard);
  wrap.appendChild(gridEl);

  return wrap;
}

// Gera assuntos fictícios mas determinísticos para as questões erradas
function _mockAssuntos(simId, count, materia) {
  const ASSUNTOS = {
    'Matemática': ['Progressão Aritmética', 'Probabilidade', 'Geometria Analítica', 'Matrizes', 'Funções', 'Trigonometria', 'Logaritmos', 'Polinômios', 'Geometria Espacial', 'Sequências', 'Estatística', 'Álgebra Linear'],
    'Física':     ['Cinemática', 'Dinâmica', 'Termodinâmica', 'Ondas', 'Óptica', 'Eletromagnetismo', 'Gravitação', 'Hidrostática', 'Calorimetria', 'Eletrostática', 'Circuitos', 'Física Moderna'],
    'Química':    ['Estequiometria', 'Equilíbrio Químico', 'Cinética Química', 'Eletroquímica', 'Soluções', 'Termoquímica', 'Gases', 'Radioatividade', 'Ligações Químicas', 'Tabela Periódica', 'Oxidorredução', 'Isomeria'],
    'Português':  ['Interpretação de Texto', 'Análise Sintática', 'Coesão e Coerência', 'Semântica', 'Pontuação', 'Regência', 'Concordância', 'Morfologia', 'Funções da Linguagem', 'Literatura', 'Redação', 'Ortografia'],
    'Inglês':     ['Reading Comprehension', 'Vocabulary', 'Grammar', 'Text Cohesion', 'Inference', 'Synonyms', 'Prepositions', 'Verb Tenses', 'Discourse Markers', 'Figurative Language', 'Idiomatic Expressions', 'Context Clues'],
  };
  const pool = ASSUNTOS[materia] || ASSUNTOS['Matemática'];
  const rng = seededRng(simId + '_assuntos');
  const result = [];
  for (let i = 0; i < count; i++) {
    result.push(pool[Math.floor(rng() * pool.length)]);
  }
  return result;
}

// ─── Render principal ─────────────────────────────────────────────────────

export async function renderSimuladosAluno({ nav, params }) {
  if (params?.simId) {
    return _renderDetalhe({ nav, simId: params.simId, simNome: params.simNome });
  }
  return _renderLista({ nav });
}
