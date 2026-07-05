// Sparkline SVG sem eixos — curva suave (Bézier) com preenchimento em
// gradiente e dot final branco, no mesmo estilo visual da área do aluno
// (ver chartLine em screens/aluno/painel.js).

import { el } from '../../dom.js';

const NS = 'http://www.w3.org/2000/svg';

function smoothPath(pts) {
  if (pts.length < 2) return '';
  let d = `M ${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const cx = (x0 + x1) / 2;
    d += ` C ${cx},${y0} ${cx},${y1} ${x1},${y1}`;
  }
  return d;
}

let _gradSeq = 0;

export function sparkline(values, { width = 90, height = 32, color = 'currentColor' } = {}) {
  if (!values || values.length < 2) return el('span', {}, []);

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const yDe = (v) => height - ((v - min) / span) * height;

  const pts = values.map((v, i) => [i * stepX, yDe(v)]);
  const path = smoothPath(pts);
  const [lastX, lastY] = pts[pts.length - 1];

  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class', 'sparkline');
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

  const gradId = `spark-grad-${_gradSeq++}`;
  const defs = document.createElementNS(NS, 'defs');
  const grad = document.createElementNS(NS, 'linearGradient');
  grad.setAttribute('id', gradId);
  grad.setAttribute('x1', '0'); grad.setAttribute('y1', '0');
  grad.setAttribute('x2', '0'); grad.setAttribute('y2', '1');
  const stop1 = document.createElementNS(NS, 'stop');
  stop1.setAttribute('offset', '0%');
  stop1.setAttribute('stop-color', color);
  stop1.setAttribute('stop-opacity', '0.35');
  const stop2 = document.createElementNS(NS, 'stop');
  stop2.setAttribute('offset', '100%');
  stop2.setAttribute('stop-color', color);
  stop2.setAttribute('stop-opacity', '0');
  grad.appendChild(stop1);
  grad.appendChild(stop2);
  defs.appendChild(grad);
  svg.appendChild(defs);

  const area = document.createElementNS(NS, 'path');
  area.setAttribute('d', `${path} L ${lastX.toFixed(1)},${height} L ${pts[0][0].toFixed(1)},${height} Z`);
  area.setAttribute('fill', `url(#${gradId})`);
  svg.appendChild(area);

  const line = document.createElementNS(NS, 'path');
  line.setAttribute('d', path);
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', color);
  line.setAttribute('stroke-width', '1.5');
  line.setAttribute('stroke-linejoin', 'round');
  line.setAttribute('stroke-linecap', 'round');
  svg.appendChild(line);

  // Marca o último ponto — dot branco com contorno na cor da série.
  const dot = document.createElementNS(NS, 'circle');
  dot.setAttribute('cx', lastX.toFixed(1));
  dot.setAttribute('cy', lastY.toFixed(1));
  dot.setAttribute('r', '2.5');
  dot.setAttribute('fill', '#fff');
  dot.setAttribute('stroke', color);
  dot.setAttribute('stroke-width', '1.5');
  svg.appendChild(dot);

  return svg;
}
