// Painel do aluno autenticado.
// Seções: greeting + streak, hero (último simulado), range bar de comparação,
// gráfico de evolução por matéria, AI insight (placeholder) e conquistas.

import { el, clear } from '../../dom.js';
import { getApiClient } from '../../services/api.js';

// ─── Helpers de formatação ────────────────────────────────────────────────

function fmt(n, d = 1) {
  if (n == null) return '—';
  return Number(n).toFixed(d).replace('.', ',');
}

function fmtData(iso) {
  if (!iso) return '—';
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }).replace(/\./g, '');
}

// ─── Cores por matéria ────────────────────────────────────────────────────

const MAT_COR = {
  'Matemática': '#234C8B',
  'Física':     '#4E79B5',
  'Química':    '#3E9B73',
  'Português':  '#C99A57',
  'Inglês':     '#7B5EA7',
};
function matCor(mat) { return MAT_COR[mat] || '#234C8B'; }

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

// ─── SVG: progress ring ───────────────────────────────────────────────────

function chartRing({ pct, size = 84, strokeW = 8, color = '#E6B94E', track = 'rgba(255,255,255,0.18)', labelEl }) {
  const r = size / 2 - strokeW / 2;
  const c = 2 * Math.PI * r;
  const wrap = el('div', { class: 'alu-ring', style: `width:${size}px;height:${size}px` });

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

  if (labelEl) {
    const inner = el('div', { class: 'alu-ring__inner' });
    inner.appendChild(labelEl);
    wrap.appendChild(inner);
  }
  return wrap;
}

// ─── SVG: line chart ─────────────────────────────────────────────────────

function chartLine({ series, xLabels, width = 560, height = 190, yMin = 4, yMax = 10 }) {
  const padL = 28, padR = 14, padT = 12, padB = 26;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const n = xLabels.length;
  if (n < 2) return el('div', { class: 'alu-loading' }, ['Dados insuficientes para o gráfico.']);

  const X = i => padL + (i / (n - 1)) * plotW;
  const Y = v => padT + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  const smooth = pts => {
    if (pts.length < 2) return '';
    let d = `M ${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i], [x1, y1] = pts[i + 1];
      const cx = (x0 + x1) / 2;
      d += ` C ${cx},${y0} ${cx},${y1} ${x1},${y1}`;
    }
    return d;
  };

  const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}` });
  svg.style.cssText = 'display:block;overflow:visible';
  const defs = svgEl('defs');
  svg.appendChild(defs);

  // Grid lines
  for (const t of [0, 0.5, 1]) {
    const yy = padT + plotH - t * plotH;
    const line = svgEl('line', {
      x1: padL, y1: yy, x2: width - padR, y2: yy,
      stroke: 'rgba(20,30,80,0.06)', 'stroke-width': 1, 'stroke-dasharray': '2 4',
    });
    svg.appendChild(line);
  }

  // X labels
  xLabels.forEach((lab, i) => {
    const t = svgEl('text', {
      x: X(i), y: height - 6, 'text-anchor': 'middle',
      'font-size': 10, fill: 'rgba(26,29,36,0.4)', 'font-family': 'inherit',
    });
    t.textContent = lab;
    svg.appendChild(t);
  });

  // Series
  series.forEach((s, si) => {
    const pts = s.values.map((v, i) => [X(i), Y(v)]);
    const path = smooth(pts);
    const last = pts[pts.length - 1];
    const g = svgEl('g');

    if (!s.dashed) {
      const gradId = `alu-lg-${si}-${Date.now()}`;
      const grad = svgEl('linearGradient', { id: gradId, x1: 0, y1: 0, x2: 0, y2: 1 });
      const s1 = svgEl('stop', { offset: '0%', 'stop-color': s.color, 'stop-opacity': '0.14' });
      const s2 = svgEl('stop', { offset: '100%', 'stop-color': s.color, 'stop-opacity': '0' });
      grad.appendChild(s1); grad.appendChild(s2);
      defs.appendChild(grad);

      const area = svgEl('path', {
        d: `${path} L ${last[0]},${padT + plotH} L ${pts[0][0]},${padT + plotH} Z`,
        fill: `url(#${gradId})`,
      });
      g.appendChild(area);
    }

    const line = svgEl('path', {
      d: path, fill: 'none', stroke: s.color,
      'stroke-width': s.dashed ? 1.8 : 2.4,
      ...(s.dashed ? { 'stroke-dasharray': '4 4' } : {}),
      opacity: s.dashed ? 0.6 : 1,
    });
    g.appendChild(line);

    if (!s.dashed) {
      const dot = svgEl('circle', {
        cx: last[0], cy: last[1], r: 4, fill: '#fff', stroke: s.color, 'stroke-width': 2,
      });
      g.appendChild(dot);
    }
    svg.appendChild(g);
  });

  return svg;
}

// ─── SVG: range bar ───────────────────────────────────────────────────────

function chartRange({ min = 0, max = 10, markers, width = 540, height = 62 }) {
  const padX = 18, trackY = 30, trackW = width - padX * 2;
  const X = v => padX + ((v - min) / (max - min)) * trackW;

  const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}` });
  svg.style.cssText = 'display:block;overflow:visible';
  const defs = svgEl('defs');

  const gradId = 'alu-rg';
  const grad = svgEl('linearGradient', { id: gradId, x1: 0, y1: 0, x2: 1, y2: 0 });
  const gs = [
    ['0%', '#F7ECDA'],
    ['40%', '#f5f7fb'],
    ['100%', '#E2F2EA'],
  ];
  gs.forEach(([off, col]) => {
    const s = svgEl('stop', { offset: off, 'stop-color': col });
    grad.appendChild(s);
  });
  defs.appendChild(grad);
  svg.appendChild(defs);

  const track = svgEl('rect', {
    x: padX, y: trackY - 4, width: trackW, height: 8, rx: 4, fill: `url(#${gradId})`,
  });
  svg.appendChild(track);

  markers.forEach(m => {
    const x = X(m.value);
    const isYou = m.you;
    const g = svgEl('g');

    const line = svgEl('line', {
      x1: x, x2: x,
      y1: trackY - (isYou ? 14 : 8),
      y2: trackY + (isYou ? 14 : 8),
      stroke: m.color,
      'stroke-width': isYou ? 3 : 2,
      'stroke-linecap': 'round',
    });
    g.appendChild(line);

    if (isYou) {
      const circle = svgEl('circle', {
        cx: x, cy: trackY, r: 6, fill: m.color, stroke: '#fff', 'stroke-width': 2,
      });
      g.appendChild(circle);
    }

    const text = svgEl('text', {
      x,
      y: isYou ? trackY - 20 : height - 3,
      'text-anchor': 'middle',
      'font-size': isYou ? 11 : 9.5,
      'font-weight': isYou ? 600 : 400,
      fill: isYou ? '#1C2436' : '#9097a8',
      'font-family': 'inherit',
    });
    text.textContent = m.label;
    g.appendChild(text);

    svg.appendChild(g);
  });

  return svg;
}

// ─── Seção: greeting + streak ─────────────────────────────────────────────

function _secaoGreeting(nome, streak) {
  const count = streak?.count || 0;
  const streakEl = count > 0
    ? el('div', { class: 'alu-streak' }, [
        icon('M12 2c1 4 5 5 5 9a5 5 0 0 1-10 0c0-1.5.6-2.6 1.3-3.5C9 9 9.5 8 9 6c2 1 2.5 2.8 3 4 .8-1 1-2.5 0-8z', 15, 'var(--alu-calm-deep)', 1.5),
        `${count} ciclos no fôlego`,
      ])
    : null;

  return el('div', { class: 'alu-greeting' }, [
    el('div', {}, [
      el('div', { class: 'alu-greeting__nome' }, [`Olá, ${nome || 'aluno'}`]),
      el('div', { class: 'alu-greeting__sub' }, ['Acompanhe sua evolução e identifique onde melhorar.']),
    ]),
    streakEl,
  ].filter(Boolean));
}

// ─── Seção: hero card (último simulado) ───────────────────────────────────

function _secaoHero(detalhe) {
  if (!detalhe) {
    return el('div', { class: 'alu-hero' }, [
      el('div', { style: 'color:rgba(255,255,255,0.7);font-size:14px' }, ['Nenhum simulado corrigido ainda.']),
    ]);
  }

  const { nota, deltaSelf, posicao, total, percentil, nome, rotulo, dataAplicacao, materia, grupos } = detalhe;
  const delta = deltaSelf ?? 0;
  const pct = total > 1 ? 1 - (posicao - 1) / total : 0.5;

  const labelEl = el('div', { class: 'alu-ring__inner' }, [
    el('div', { style: 'text-align:center;color:#fff' }, [
      el('div', { class: 'alu-ring__pos' }, [`${posicao}º`]),
      el('div', { class: 'alu-ring__total' }, [`de ${total}`]),
    ]),
  ]);

  const ringWrap = el('div', { class: 'alu-ring-wrap' }, [
    chartRing({ pct, size: 84, strokeW: 8, color: 'var(--color-gold)', track: 'rgba(255,255,255,0.18)', labelEl }),
    el('div', { class: 'alu-ring__desc' }, [
      el('div', { class: 'alu-ring__label' }, ['Sua posição na turma']),
      el('div', { class: 'alu-ring__sub' }, [
        percentil != null ? `Melhor que ${percentil}% da turma.` : '',
      ]),
    ]),
  ]);

  const statsRow = grupos ? el('div', { class: 'alu-hero__stats' }, [
    { r: 'Aplicado',       v: fmtData(dataAplicacao) },
    { r: 'Matéria',        v: materia || '—' },
    { r: 'Percentil',      v: percentil != null ? `${percentil}%` : '—' },
    { r: 'Acima da média', v: grupos.voce != null && grupos.geral != null ? `+${fmt(grupos.voce - grupos.geral)}` : '—' },
  ].map(x => el('div', { class: 'alu-hero__stat' }, [
    el('div', { class: 'alu-hero__stat-rotulo' }, [x.r]),
    el('div', { class: 'alu-hero__stat-valor' }, [x.v]),
  ]))) : null;

  const deltaEl = el('div', { class: 'alu-hero__delta' }, [
    icon(delta >= 0
      ? 'M12 19V5 M5 12l7-7 7 7'
      : 'M12 5v14 M19 12l-7 7-7-7',
      12, '#fff', 2.4),
    `${delta >= 0 ? '+' : ''}${fmt(delta)} vs. seu padrão`,
  ]);

  return el('div', { class: 'alu-hero' }, [
    el('div', { class: 'alu-hero__inner' }, [
      el('div', { class: 'alu-hero__left' }, [
        el('div', { class: 'alu-hero__label' }, [
          el('span', { class: 'alu-hero__label-line' }),
          `${rotulo || nome || '—'} · ${fmtData(dataAplicacao)}`,
        ]),
        el('div', { class: 'alu-hero__nota-row' }, [
          el('div', { class: 'alu-hero__nota' }, [fmt(nota)]),
          el('div', { class: 'alu-hero__nota-meta' }, [
            deltaEl,
            el('div', { class: 'alu-hero__escala' }, ['nota geral · escala 0–10']),
          ]),
        ]),
        statsRow,
      ].filter(Boolean)),
      ringWrap,
    ]),
  ]);
}

// ─── Seção: comparação com grupos ─────────────────────────────────────────

function _secaoComparacao(detalhe) {
  if (!detalhe?.grupos) return null;
  const g = detalhe.grupos;

  const valores = [g.bottom15, g.geral, g.voce, g.top15].filter(v => v != null);
  const rangeMin = Math.max(0, Math.min(...valores) - 0.5);
  const rangeMax = Math.min(10, Math.max(...valores) + 0.5);

  const rangeEl = el('div', { style: 'overflow-x:auto' });
  rangeEl.appendChild(chartRange({
    min: rangeMin, max: rangeMax, width: 540, height: 62,
    markers: [
      { value: g.bottom15, label: 'Inferior-15', color: 'var(--alu-calm)', you: false },
      { value: g.geral,    label: 'Média geral', color: 'var(--color-text-secondary)', you: false },
      { value: g.voce,     label: `Você · ${fmt(g.voce)}`, color: 'var(--alu-up)', you: true },
      { value: g.top15,    label: 'Top-15',      color: 'var(--color-navy)', you: false },
    ].filter(m => m.value != null),
  }));

  const legendaEl = el('div', { class: 'alu-range-legend' }, [
    g.voce != null && g.geral != null ? el('div', { class: 'alu-range-kpi alu-range-kpi--up' }, [
      el('span', { class: 'alu-range-kpi__value' }, [`+${fmt(g.voce - g.geral)}`]),
      'acima da média geral',
    ]) : null,
    g.top15 != null && g.voce != null ? el('div', { class: 'alu-range-kpi alu-range-kpi--calm' }, [
      el('span', { class: 'alu-range-kpi__value' }, [`−${fmt(g.top15 - g.voce)}`]),
      'para o top-15',
    ]) : null,
  ].filter(Boolean));

  return el('div', { class: 'alu-card' }, [
    el('div', { class: 'alu-section-title' }, ['Onde você está na turma']),
    rangeEl,
    legendaEl,
  ]);
}

// ─── Seção: evolução por matéria ──────────────────────────────────────────

function _secaoEvolucao(evolucao) {
  if (!evolucao || !evolucao.ciclos?.length) {
    return el('div', { class: 'alu-card' }, [
      el('div', { class: 'alu-section-title' }, ['Minha evolução']),
      el('div', { class: 'alu-empty' }, ['Sem dados de evolução ainda.']),
    ]);
  }

  const materias = Object.keys(evolucao.materias);
  if (!materias.length) return null;

  let matSel = materias[0];
  const chartWrap = el('div', { style: 'overflow-x:auto' });
  const legendaWrap = el('div', { class: 'alu-chart-legend' });
  const chipsWrap = el('div', { class: 'alu-mat-chips' });

  function _renderChart() {
    const matData = evolucao.materias[matSel] || { aluno: [], turma: [] };
    const labels = [];
    const alunoVals = [];
    const turmaVals = [];

    evolucao.ciclos.forEach((c, i) => {
      const a = matData.aluno[i];
      const t = matData.turma[i];
      if (a != null) {
        labels.push(c.label);
        alunoVals.push(a);
        turmaVals.push(t);
      }
    });

    clear(chartWrap);
    if (alunoVals.length < 2) {
      chartWrap.appendChild(el('div', { class: 'alu-empty', style: 'padding:32px 0' }, ['Dados insuficientes para esta matéria.']));
    } else {
      const series = [];
      if (turmaVals.some(v => v != null)) {
        series.push({ values: turmaVals.filter(v => v != null), color: 'rgba(20,30,80,0.2)', dashed: true });
      }
      series.push({ values: alunoVals, color: matCor(matSel) });

      const w = Math.max(340, Math.min(600, chartWrap.offsetWidth || 500));
      chartWrap.appendChild(chartLine({ series, xLabels: labels, width: w, height: 185 }));
    }

    clear(legendaWrap);
    legendaWrap.appendChild(el('span', { class: 'alu-chart-legend-item' }, [
      el('span', { class: 'alu-chart-legend-line', style: `background:${matCor(matSel)};height:2.4px;` }),
      'Você',
    ]));
    legendaWrap.appendChild(el('span', { class: 'alu-chart-legend-item' }, [
      el('span', { class: 'alu-chart-legend-line', style: 'background:rgba(20,30,80,0.2);height:0;border-top:2px dashed rgba(20,30,80,0.25)' }),
      'Média da turma',
    ]));
  }

  function _renderChips() {
    clear(chipsWrap);
    materias.forEach(m => {
      const chip = el('div', { class: `alu-mat-chip${m === matSel ? ' is-active' : ''}` }, [
        el('span', { class: 'alu-mat-dot', style: `background:${matCor(m)}` }),
        m,
      ]);
      chip.addEventListener('click', () => {
        matSel = m;
        _renderChips();
        _renderChart();
      });
      chipsWrap.appendChild(chip);
    });
  }

  _renderChips();
  _renderChart();

  return el('div', { class: 'alu-card' }, [
    el('div', { class: 'alu-section-title' }, [
      'Minha evolução',
      el('span', { class: 'alu-section-title__action' }, [`${evolucao.ciclos.length} ciclos`]),
    ]),
    chipsWrap,
    chartWrap,
    legendaWrap,
  ]);
}

// ─── Seção: AI insight (placeholder) ─────────────────────────────────────

function _secaoAI() {
  return el('div', { class: 'alu-ai-card' }, [
    el('div', { class: 'alu-ai-card__header' }, [
      el('div', { class: 'alu-ai-card__badge' }, [
        icon('M12 3l1.6 4.3L18 9l-4.4 1.7L12 15l-1.6-4.3L6 9l4.4-1.7z', 12, '#fff'),
        'IA · Insight do ciclo',
      ]),
      el('span', { class: 'alu-ai-card__soon' }, ['em breve, automático']),
    ]),
    el('div', { class: 'alu-ai-card__title' }, ['Análise personalizada do seu desempenho.']),
    el('div', { class: 'alu-ai-card__body' }, [
      'Em breve o assistente identificará automaticamente onde você pode melhorar mais com menos esforço — e vai sugerir o que revisar antes do próximo simulado.',
    ]),
    el('button', { class: 'alu-ai-card__cta', disabled: true }, ['Em breve']),
  ]);
}

// ─── Seção: conquistas (badges) ───────────────────────────────────────────

const BADGE_TONS = {
  gold:  ['#E6B94E', '#FAF0D6', '#A6822C'],
  up:    ['#3E9B73', '#E2F2EA', '#2C7355'],
  calm:  ['#C99A57', '#F7ECDA', '#9A6F32'],
  navy:  ['#234C8B', '#E7EDF8', '#16356A'],
};

function _badgeChip(badge) {
  const [color, soft, deep] = BADGE_TONS[badge.tone] || BADGE_TONS.navy;
  const bg = badge.unlocked ? soft : 'var(--color-surface-inset)';
  const iconColor = badge.unlocked ? color : 'var(--color-text-tertiary)';

  const iconD = {
    flame:  'M12 2c1 4 5 5 5 9a5 5 0 0 1-10 0c0-1.5.6-2.6 1.3-3.5C9 9 9.5 8 9 6c2 1 2.5 2.8 3 4 .8-1 1-2.5 0-8z',
    star:   'M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z',
    trophy: 'M6 9a6 6 0 0 0 12 0V3H6z M6 5H3v2a3 3 0 0 0 3 3 M18 5h3v2a3 3 0 0 1-3 3 M9 21h6 M12 15v6',
    medal:  'M12 15a6 6 0 1 0 0-12 6 6 0 0 0 0 12z M8.5 13L7 22l5-3 5 3-1.5-9',
    lock:   'M5 11h14v10H5z M8 11V7a4 4 0 0 1 8 0v4',
  }[badge.unlocked ? badge.icon : 'lock'] || '';

  const progressEl = (!badge.unlocked && badge.progress != null) ? el('div', { class: 'alu-badge-progress' }, [
    el('div', { class: 'alu-badge-progress__bar' }, [
      el('div', { class: 'alu-badge-progress__fill', style: `width:${Math.round(badge.progress * 100)}%;background:${deep}` }),
    ]),
    el('div', { class: 'alu-badge-progress__pct' }, [`${Math.round(badge.progress * 100)}%`]),
  ]) : null;

  return el('div', {
    class: `alu-badge${badge.unlocked ? '' : ' alu-badge--locked'}`,
    style: `background:${bg};border-color:${badge.unlocked ? 'transparent' : 'var(--color-border)'}`,
  }, [
    el('div', { class: 'alu-badge__icon', style: `background:${iconColor}` }, [
      icon(iconD, 18, '#fff', 1.8),
    ]),
    el('div', { class: 'alu-badge__label' }, [badge.label]),
    el('div', { class: 'alu-badge__sub' }, [badge.sub]),
    progressEl,
  ].filter(Boolean));
}

function _secaoBadges(streak, simulados, detalhe) {
  const temNota8 = simulados.some(s => s.nota >= 8.0);
  const noTop15 = detalhe && detalhe.total > 1 && detalhe.posicao <= Math.ceil(detalhe.total * 0.15);
  const count = streak?.count || 0;

  const badges = [
    {
      id: 'streak3', icon: 'flame', label: '3 ciclos no fôlego',
      sub: 'Acima da média 3 ciclos seguidos', unlocked: count >= 3,
      tone: 'calm', progress: count >= 3 ? 1 : count / 3,
    },
    {
      id: 'first8', icon: 'star', label: 'Primeiro 8,0',
      sub: 'Nota 8+ em alguma matéria', unlocked: temNota8, tone: 'gold',
    },
    {
      id: 'top15', icon: 'trophy', label: 'Top 15',
      sub: 'Top 15% da turma em um simulado', unlocked: !!noTop15, tone: 'up',
    },
    {
      id: 'sim10', icon: 'medal', label: '10 simulados',
      sub: 'Completou 10 simulados', unlocked: simulados.length >= 10,
      tone: 'navy', progress: Math.min(1, simulados.length / 10),
    },
  ];

  return el('div', { class: 'alu-card' }, [
    el('div', { class: 'alu-section-title' }, ['Conquistas']),
    el('div', { class: 'alu-badge-grid' }, badges.map(_badgeChip)),
  ]);
}

// ─── Render principal ─────────────────────────────────────────────────────

export async function renderPainelAluno({ nav, nome }) {
  const api = getApiClient();

  // Fetch em paralelo: streak, lista de simulados, dados de evolução
  const [streak, simulados, evolucao] = await Promise.all([
    api.streakMe().catch(() => ({ count: 0 })),
    api.listarSimuladosMe().catch(() => []),
    api.evolucaoMe().catch(() => null),
  ]);

  // Detalhe do simulado mais recente (ranking + grupos)
  const lastSim = simulados[0];
  const detalhe = lastSim
    ? await api.obterSimuladoMe(lastSim.id).catch(() => null)
    : null;

  const wrap = el('div', { style: 'display:flex;flex-direction:column;gap:18px' });

  wrap.appendChild(_secaoGreeting(nome, streak));
  wrap.appendChild(_secaoHero(detalhe));

  // 2-col no desktop: esquerda (evolução + comparação), direita (AI + badges)
  const colMain = el('div', { class: 'alu-painel__col' });
  const colSide = el('div', { class: 'alu-painel__col' });

  const evolEl = _secaoEvolucao(evolucao);
  const compEl = _secaoComparacao(detalhe);

  if (evolEl) colMain.appendChild(evolEl);
  if (compEl) colMain.appendChild(compEl);

  colSide.appendChild(_secaoAI());
  if (simulados.length > 0 || streak.count > 0) {
    colSide.appendChild(_secaoBadges(streak, simulados, detalhe));
  }

  wrap.appendChild(el('div', { class: 'alu-painel__grid' }, [colMain, colSide]));

  return wrap;
}
