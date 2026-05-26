// Histograma SVG simples — recebe `{ largura_bin, maximo, contagens }` direto
// da rota /simulados/{id}/histograma. Linha vertical opcional pra média.
//
// Opções avançadas (opt-in, sem regressão no caller atual):
//   - eixoYAbsoluto: { max, ticks }  → eixo Y numerado, escala fixa (permite
//                                       comparar histogramas entre recortes).
//   - corte: { valor, label, eliminatoria }
//                                    → linha vertical do corte + sombreamento
//                                      da zona reprovada (fill semitransparente).
//   - cicloAnterior: { contagens, maximo }
//                                    → overlay tracejado pra comparação.
//   - kde: true                      → curva de densidade gaussiana sobre as barras.

import { el } from '../../dom.js';

const SVG_NS = 'http://www.w3.org/2000/svg';

export function histograma(payload, opts = {}) {
  const {
    width = 480,
    height = 180,
    color = 'var(--color-navy)',
    media = null,
    mediana = null,
    eixoYAbsoluto = null,
    corte = null,
    cicloAnterior = null,
    kde = false,
  } = opts;

  if (!payload || !Array.isArray(payload.contagens) || payload.contagens.length === 0) {
    return el('div', { class: 'empty-state' }, ['Sem dados de histograma ainda.']);
  }

  const { largura_bin: larguraBin, maximo, contagens } = payload;
  const nBins = contagens.length;

  // ── Escala Y ──
  // Por padrão, normaliza pelo máximo local. Se eixoYAbsoluto vier, usa
  // escala fixa (e renderiza ticks). Isso é o que permite comparar visualmente
  // dois histogramas de tamanhos diferentes.
  const maxLocal = Math.max(...contagens, 1);
  const maxAntLocal = cicloAnterior ? Math.max(...(cicloAnterior.contagens || []), 1) : 0;
  const maxContagem = eixoYAbsoluto?.max ?? Math.max(maxLocal, maxAntLocal);

  const padLeft = eixoYAbsoluto ? 36 : 28;
  const padBottom = 22;
  const padTop = 8;
  const padRight = 8;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;
  const binW = plotW / nBins;

  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'histograma');
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

  // Eixo X.
  const eixoX = document.createElementNS(SVG_NS, 'line');
  eixoX.setAttribute('x1', String(padLeft));
  eixoX.setAttribute('x2', String(padLeft + plotW));
  eixoX.setAttribute('y1', String(padTop + plotH));
  eixoX.setAttribute('y2', String(padTop + plotH));
  eixoX.setAttribute('stroke', 'var(--color-border-strong)');
  svg.appendChild(eixoX);

  // ── Sombreamento da zona reprovada (atrás das barras) ──
  if (corte && corte.valor != null) {
    const xCorte = padLeft + (corte.valor / maximo) * plotW;
    const rect = document.createElementNS(SVG_NS, 'rect');
    rect.setAttribute('x', String(padLeft));
    rect.setAttribute('y', String(padTop));
    rect.setAttribute('width', (xCorte - padLeft).toFixed(1));
    rect.setAttribute('height', String(plotH));
    rect.setAttribute('fill', corte.eliminatoria ? 'var(--color-red)' : 'var(--color-amber)');
    rect.setAttribute('opacity', '0.08');
    svg.appendChild(rect);
  }

  // ── Eixo Y com ticks numéricos (opt-in) ──
  if (eixoYAbsoluto) {
    const nTicks = eixoYAbsoluto.ticks ?? 4;
    for (let i = 0; i <= nTicks; i += 1) {
      const valor = (maxContagem * i) / nTicks;
      const y = padTop + plotH - (i / nTicks) * plotH;
      const tick = document.createElementNS(SVG_NS, 'line');
      tick.setAttribute('x1', String(padLeft - 3));
      tick.setAttribute('x2', String(padLeft));
      tick.setAttribute('y1', y.toFixed(1));
      tick.setAttribute('y2', y.toFixed(1));
      tick.setAttribute('stroke', 'var(--color-border-strong)');
      svg.appendChild(tick);

      const txt = document.createElementNS(SVG_NS, 'text');
      txt.setAttribute('x', String(padLeft - 5));
      txt.setAttribute('y', (y + 3).toFixed(1));
      txt.setAttribute('text-anchor', 'end');
      txt.setAttribute('font-size', '10');
      txt.setAttribute('fill', 'var(--color-text-tertiary)');
      txt.textContent = Math.round(valor);
      svg.appendChild(txt);
    }
  }

  // ── Barras (ciclo atual) ──
  contagens.forEach((c, i) => {
    const h = (c / maxContagem) * plotH;
    const r = document.createElementNS(SVG_NS, 'rect');
    r.setAttribute('x', (padLeft + i * binW + 1).toFixed(1));
    r.setAttribute('y', (padTop + plotH - h).toFixed(1));
    r.setAttribute('width', Math.max(1, binW - 2).toFixed(1));
    r.setAttribute('height', h.toFixed(1));
    r.setAttribute('fill', color);
    r.setAttribute('opacity', '0.85');
    const tip = document.createElementNS(SVG_NS, 'title');
    const inicio = (i * larguraBin).toFixed(1);
    const fim = ((i + 1) * larguraBin).toFixed(1);
    tip.textContent = `[${inicio} – ${fim}): ${c} alunos`;
    r.appendChild(tip);
    svg.appendChild(r);
  });

  // ── Overlay ciclo anterior (tracejado) ──
  if (cicloAnterior?.contagens?.length === nBins) {
    const pontos = cicloAnterior.contagens.map((c, i) => {
      const x = padLeft + (i + 0.5) * binW;
      const h = (c / maxContagem) * plotH;
      return `${x.toFixed(1)},${(padTop + plotH - h).toFixed(1)}`;
    }).join(' ');
    const linha = document.createElementNS(SVG_NS, 'polyline');
    linha.setAttribute('points', pontos);
    linha.setAttribute('fill', 'none');
    linha.setAttribute('stroke', 'var(--color-text-tertiary)');
    linha.setAttribute('stroke-width', '1.5');
    linha.setAttribute('stroke-dasharray', '4,3');
    linha.setAttribute('opacity', '0.7');
    const t = document.createElementNS(SVG_NS, 'title');
    t.textContent = 'Distribuição do ciclo anterior';
    linha.appendChild(t);
    svg.appendChild(linha);
  }

  // ── Curva KDE (kernel gaussiano simples) ──
  if (kde) {
    const curva = _kdeCurva(contagens, larguraBin, maxContagem, plotW, plotH, padLeft, padTop);
    if (curva) svg.appendChild(curva);
  }

  // ── Rótulos do eixo X ──
  const passo = Math.max(1, Math.ceil(nBins / 6));
  for (let i = 0; i <= nBins; i += passo) {
    const x = padLeft + i * binW;
    const tx = document.createElementNS(SVG_NS, 'text');
    tx.setAttribute('x', x.toFixed(1));
    tx.setAttribute('y', (padTop + plotH + 14).toFixed(1));
    tx.setAttribute('text-anchor', 'middle');
    tx.setAttribute('font-size', '10');
    tx.setAttribute('fill', 'var(--color-text-tertiary)');
    tx.textContent = (i * larguraBin).toFixed(1).replace('.', ',');
    svg.appendChild(tx);
  }

  // ── Linhas verticais (média, mediana, corte) ──
  _linhaVertical(svg, { padLeft, padTop, plotW, plotH, maximo }, media, 'var(--color-red)', 'Média');
  _linhaVertical(svg, { padLeft, padTop, plotW, plotH, maximo }, mediana, 'var(--color-amber)', 'Mediana');
  if (corte?.valor != null) {
    _linhaVertical(
      svg,
      { padLeft, padTop, plotW, plotH, maximo },
      corte.valor,
      corte.eliminatoria ? 'var(--color-red)' : 'var(--color-amber)',
      `Corte${corte.label ? ' ' + corte.label : ''}`,
      { tracejado: false, larguraExtra: true },
    );
  }

  return el('div', { class: 'histograma__container' }, [
    svg,
    el('div', { class: 'histograma__legenda' }, [
      _legendaItem('var(--color-red)', `Média: ${_fmt(media)}`),
      _legendaItem('var(--color-amber)', `Mediana: ${_fmt(mediana)}`),
      corte?.valor != null
        ? _legendaItem(
            corte.eliminatoria ? 'var(--color-red)' : 'var(--color-amber)',
            `Corte: ${_fmt(corte.valor)}${corte.eliminatoria ? ' (eliminatória)' : ''}`,
          )
        : null,
      cicloAnterior
        ? _legendaItem('var(--color-text-tertiary)', 'Ciclo anterior (tracejado)')
        : null,
    ].filter(Boolean)),
  ]);
}

function _linhaVertical(svg, { padLeft, padTop, plotW, plotH, maximo }, valor, cor, rotulo, opts = {}) {
  if (valor == null) return;
  const { tracejado = true, larguraExtra = false } = opts;
  const x = padLeft + (valor / maximo) * plotW;
  const ln = document.createElementNS(SVG_NS, 'line');
  ln.setAttribute('x1', x.toFixed(1));
  ln.setAttribute('x2', x.toFixed(1));
  ln.setAttribute('y1', String(padTop));
  ln.setAttribute('y2', String(padTop + plotH));
  ln.setAttribute('stroke', cor);
  if (tracejado) ln.setAttribute('stroke-dasharray', '3,3');
  ln.setAttribute('stroke-width', larguraExtra ? '2' : '1.5');
  const t = document.createElementNS(SVG_NS, 'title');
  t.textContent = `${rotulo}: ${valor.toFixed(1).replace('.', ',')}`;
  ln.appendChild(t);
  svg.appendChild(ln);
}

function _legendaItem(cor, texto) {
  return el('span', { class: 'histograma__legenda-item' }, [
    el('span', {
      class: 'histograma__legenda-marca',
      style: `background: ${cor}`,
    }, []),
    texto,
  ]);
}

function _fmt(n) {
  return n == null ? '—' : n.toFixed(1).replace('.', ',');
}

// Curva de densidade gaussiana simples — usa as contagens como pontos discretos,
// aplica kernel sobre o eixo X em escala 0–10 com largura de banda heurística.
function _kdeCurva(contagens, larguraBin, maxContagem, plotW, plotH, padLeft, padTop) {
  const nBins = contagens.length;
  const total = contagens.reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  // Largura de banda h = 1.06 * desvio * n^(-1/5) (regra de Silverman).
  const centros = contagens.map((_, i) => (i + 0.5) * larguraBin);
  const media = centros.reduce((acc, c, i) => acc + c * contagens[i], 0) / total;
  const variancia = centros.reduce(
    (acc, c, i) => acc + contagens[i] * (c - media) ** 2,
    0,
  ) / total;
  const desvio = Math.sqrt(variancia) || larguraBin;
  const h = 1.06 * desvio * Math.pow(total, -1 / 5);

  const passos = 60;
  const xMax = nBins * larguraBin;
  const pontos = [];
  let maxDensidade = 0;

  for (let i = 0; i <= passos; i += 1) {
    const x = (i / passos) * xMax;
    let d = 0;
    for (let j = 0; j < nBins; j += 1) {
      const u = (x - centros[j]) / h;
      d += contagens[j] * Math.exp(-0.5 * u * u);
    }
    d /= total * h * Math.sqrt(2 * Math.PI);
    pontos.push([x, d]);
    if (d > maxDensidade) maxDensidade = d;
  }

  if (maxDensidade === 0) return null;

  const path = document.createElementNS(SVG_NS, 'polyline');
  const pts = pontos.map(([x, d]) => {
    const px = padLeft + (x / xMax) * plotW;
    // Escala a densidade pra altura do bin máximo (estética: KDE acompanha as barras).
    const py = padTop + plotH - (d / maxDensidade) * plotH * 0.95;
    return `${px.toFixed(1)},${py.toFixed(1)}`;
  }).join(' ');
  path.setAttribute('points', pts);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'var(--color-navy)');
  path.setAttribute('stroke-width', '1.5');
  path.setAttribute('opacity', '0.45');
  return path;
}
