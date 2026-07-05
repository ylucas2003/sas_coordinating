// Gráfico de linha pra evolução do aluno por ciclo.
// Eixo X = ciclos categóricos (C1, C2…). Eixo Y = nota 0–10 fixa.
// Suporta múltiplas séries (uma linha por matéria) e tooltip detalhado.

import { el, fmtNota } from '../../dom.js';

const NS = 'http://www.w3.org/2000/svg';

// Paleta pra séries por matéria — alinhada ao design system existente.
const CORES_SERIE = [
  'var(--color-navy)',
  '#c97c2a',         // âmbar
  '#1b8a5a',         // verde
  '#a23b3b',         // vermelho
  '#6b4cb3',         // roxo
  '#2a8fb3',         // ciano
];

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    node.setAttribute(k, String(v));
  }
  return node;
}

// Curva suave (Bézier) — mesmo algoritmo do gráfico da área do aluno
// (chartLine em screens/aluno/painel.js), pra unificar a linguagem visual.
function smoothPath(pts) {
  if (pts.length < 2) return '';
  let d = `M ${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const cx = (x0 + x1) / 2;
    d += ` C ${cx.toFixed(1)},${y0.toFixed(1)} ${cx.toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`;
  }
  return d;
}

const FASE_LABEL = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

function fmtDataBR(iso) {
  if (!iso) return '—';
  const [a, m, d] = iso.split('-');
  return `${d}/${m}/${a}`;
}

/**
 * @param {object} opcoes
 * @param {Array<{nome: string, cor?: string, pontos: Array<Ponto>}>} opcoes.series
 *   Ponto: { cicloOrdem, vestibularAlvo, nota, mediaTurma, simulado, simuladoId,
 *            dataAplicacao, tipo, materia, abandonoProvavel? }
 * @param {Array<{ordem: number, label: string}>} opcoes.ciclosEixo - ordem do eixo X
 * @param {number} [opcoes.corte=4] - linha tracejada de referência
 * @param {string} [opcoes.corteRotulo='corte 4']
 * @param {number} [opcoes.altura=320]
 */
export function linhaEvolucao({
  series,
  ciclosEixo,
  corte = 4,
  corteRotulo = 'corte 4',
  altura = 320,
}) {
  const wrapper = el('div', { class: 'linha-evol' }, []);

  if (!ciclosEixo.length || !series.length || series.every((s) => !s.pontos.length)) {
    wrapper.appendChild(el('div', { class: 'linha-evol__vazio' }, [
      'Sem dados pra plotar com os filtros atuais.',
    ]));
    return wrapper;
  }

  // Layout: margem maior à esquerda pra eixo Y, e em baixo pra eixo X.
  const margem = { top: 18, right: 24, bottom: 36, left: 42 };
  const larguraTotal = 760;
  const alturaTotal = altura;
  const plotW = larguraTotal - margem.left - margem.right;
  const plotH = alturaTotal - margem.top - margem.bottom;

  const svg = svgEl('svg', {
    class: 'linha-evol__svg',
    width: '100%',
    viewBox: `0 0 ${larguraTotal} ${alturaTotal}`,
    preserveAspectRatio: 'xMidYMid meet',
  });

  // Mapeia ordem -> índice no eixo
  const indicePorOrdem = new Map(ciclosEixo.map((c, i) => [c.ordem, i]));

  const xDe = (ordem) => {
    const i = indicePorOrdem.get(ordem);
    if (i == null) return null;
    if (ciclosEixo.length === 1) return margem.left + plotW / 2;
    return margem.left + (i / (ciclosEixo.length - 1)) * plotW;
  };
  const yDe = (nota) => margem.top + plotH - (nota / 10) * plotH;

  // ─── Gridlines + eixo Y ───────────────────────────────────────────────
  const gridGroup = svgEl('g', { class: 'linha-evol__grid' });
  for (const tick of [0, 2, 4, 6, 8, 10]) {
    const y = yDe(tick);
    gridGroup.appendChild(svgEl('line', {
      x1: margem.left, y1: y, x2: margem.left + plotW, y2: y,
      stroke: 'var(--color-border)', 'stroke-width': 1,
    }));
    const label = svgEl('text', {
      x: margem.left - 6, y: y + 3.5,
      'text-anchor': 'end',
      'font-size': 10,
      fill: 'var(--color-text-tertiary)',
    });
    label.textContent = String(tick);
    gridGroup.appendChild(label);
  }
  svg.appendChild(gridGroup);

  // ─── Linha de corte (vermelha tracejada) ──────────────────────────────
  const yCorte = yDe(corte);
  svg.appendChild(svgEl('line', {
    x1: margem.left, y1: yCorte, x2: margem.left + plotW, y2: yCorte,
    stroke: 'var(--color-red, #c44)',
    'stroke-width': 1.2,
    'stroke-dasharray': '4 4',
    opacity: 0.7,
  }));
  const corteLabel = svgEl('text', {
    x: margem.left + plotW - 6, y: yCorte - 4,
    'text-anchor': 'end',
    'font-size': 10,
    fill: 'var(--color-red, #c44)',
    opacity: 0.85,
  });
  corteLabel.textContent = corteRotulo;
  svg.appendChild(corteLabel);

  // ─── Eixo X (rótulos dos ciclos) ──────────────────────────────────────
  for (const c of ciclosEixo) {
    const x = xDe(c.ordem);
    const label = svgEl('text', {
      x, y: margem.top + plotH + 18,
      'text-anchor': 'middle',
      'font-size': 11,
      fill: 'var(--color-text-secondary)',
    });
    label.textContent = c.label;
    svg.appendChild(label);
  }

  // ─── Séries ───────────────────────────────────────────────────────────
  // Tooltip único, posicionado dinamicamente
  const tooltip = el('div', { class: 'linha-evol__tooltip', style: 'opacity:0;' }, []);
  wrapper.appendChild(tooltip);

  function moverTooltip(evento, ponto, cor) {
    const rect = svg.getBoundingClientRect();
    const px = evento.clientX - rect.left;
    const py = evento.clientY - rect.top;

    tooltip.innerHTML = '';
    const linhas = [
      ['simulado', ponto.simulado || '—'],
      ['ciclo', ponto.vestibularAlvo
        ? `C${ponto.cicloOrdem} · ${ponto.vestibularAlvo}`
        : `C${ponto.cicloOrdem}`],
      ['fase', FASE_LABEL[ponto.tipo] || '—'],
      ['data', fmtDataBR(ponto.dataAplicacao)],
    ];
    tooltip.appendChild(el('div', { class: 'linha-evol__tt-cab', style: `border-color:${cor};` }, [
      ponto.materia || 'Aluno',
    ]));
    for (const [rotulo, valor] of linhas) {
      tooltip.appendChild(el('div', { class: 'linha-evol__tt-linha' }, [
        el('span', { class: 'linha-evol__tt-rot' }, [rotulo]),
        el('span', { class: 'linha-evol__tt-val' }, [valor]),
      ]));
    }
    tooltip.appendChild(el('div', { class: 'linha-evol__tt-sep' }, []));
    tooltip.appendChild(el('div', { class: 'linha-evol__tt-linha' }, [
      el('span', { class: 'linha-evol__tt-rot' }, ['sua nota']),
      el('span', { class: 'linha-evol__tt-val linha-evol__tt-nota' }, [fmtNota(ponto.nota)]),
    ]));
    if (ponto.mediaTurma != null) {
      tooltip.appendChild(el('div', { class: 'linha-evol__tt-linha' }, [
        el('span', { class: 'linha-evol__tt-rot' }, ['média turma']),
        el('span', { class: 'linha-evol__tt-val' }, [fmtNota(ponto.mediaTurma)]),
      ]));
      const delta = ponto.nota - ponto.mediaTurma;
      const sinal = delta > 0 ? '+' : '';
      const classe = delta > 0.1 ? 'tone-verde' : delta < -0.1 ? 'tone-vermelho' : '';
      tooltip.appendChild(el('div', { class: 'linha-evol__tt-linha' }, [
        el('span', { class: 'linha-evol__tt-rot' }, ['posição']),
        el('span', { class: `linha-evol__tt-val ${classe}` }, [
          `${sinal}${delta.toFixed(1).replace('.', ',')} vs média`,
        ]),
      ]));
    }
    if (ponto.abandonoProvavel) {
      tooltip.appendChild(el('div', { class: 'linha-evol__tt-aviso' }, [
        '⚠ nota 0 — provável abandono',
      ]));
    }

    // Posiciona com clamp pras bordas
    const ttRect = tooltip.getBoundingClientRect();
    let left = px + 14;
    let top = py + 14;
    if (left + ttRect.width > rect.width) left = px - ttRect.width - 14;
    if (top + ttRect.height > rect.height) top = py - ttRect.height - 14;
    tooltip.style.left = `${Math.max(0, left)}px`;
    tooltip.style.top = `${Math.max(0, top)}px`;
    tooltip.style.opacity = '1';
  }

  function esconderTooltip() {
    tooltip.style.opacity = '0';
  }

  series.forEach((serie, idx) => {
    if (!serie.pontos.length) return;
    const cor = serie.cor || CORES_SERIE[idx % CORES_SERIE.length];

    // Ordena pontos pela ordem do eixo
    const ordenados = [...serie.pontos]
      .filter((p) => indicePorOrdem.has(p.cicloOrdem) && p.nota != null)
      .sort((a, b) => indicePorOrdem.get(a.cicloOrdem) - indicePorOrdem.get(b.cicloOrdem));

    if (ordenados.length === 0) return;

    // Linha — curva suave (Bézier), no mesmo estilo da área do aluno.
    if (ordenados.length >= 2) {
      const pts = ordenados.map((p) => [xDe(p.cicloOrdem), yDe(p.nota)]);
      svg.appendChild(svgEl('path', {
        d: smoothPath(pts),
        fill: 'none',
        stroke: cor,
        'stroke-width': 2,
        'stroke-linejoin': 'round',
        'stroke-linecap': 'round',
      }));
    }

    // Pontos (com hover) — dot branco com contorno colorido; abandono
    // provável vira um marcador sólido vermelho, pra saltar aos olhos.
    for (const p of ordenados) {
      const cx = xDe(p.cicloOrdem);
      const cy = yDe(p.nota);
      const ponto = svgEl('circle', {
        cx, cy,
        r: 4,
        fill: p.abandonoProvavel ? 'var(--color-red, #c44)' : '#fff',
        stroke: p.abandonoProvavel ? '#fff' : cor,
        'stroke-width': 2,
        class: 'linha-evol__ponto',
      });
      ponto.style.cursor = 'pointer';
      ponto.addEventListener('mouseenter', (ev) => moverTooltip(ev, p, cor));
      ponto.addEventListener('mousemove', (ev) => moverTooltip(ev, p, cor));
      ponto.addEventListener('mouseleave', esconderTooltip);
      if (p.simuladoId) {
        ponto.addEventListener('click', () => {
          window.location.hash = `#/simulados/${p.simuladoId}`;
        });
      }
      svg.appendChild(ponto);
    }
  });

  wrapper.appendChild(svg);

  // ─── Legenda ──────────────────────────────────────────────────────────
  if (series.length > 1 || series[0]?.nome) {
    const legenda = el('div', { class: 'linha-evol__legenda' }, []);
    series.forEach((serie, idx) => {
      if (!serie.pontos.length) return;
      const cor = serie.cor || CORES_SERIE[idx % CORES_SERIE.length];
      legenda.appendChild(el('span', { class: 'linha-evol__legenda-item' }, [
        el('span', { class: 'linha-evol__legenda-swatch', style: `background:${cor};` }, []),
        serie.nome,
      ]));
    });
    wrapper.appendChild(legenda);
  }

  return wrapper;
}
