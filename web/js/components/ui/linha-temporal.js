// Linha temporal "rica" — substitui o sparkline na ficha do ciclo.
//
// Difere do sparkline em três pontos críticos pro coordenador:
//   1. Eixo Y numerado em escala absoluta (0–10) — fixa, não normalizada,
//      pra notas serem comparáveis entre gráficos.
//   2. Eixo X com datas (ou rótulos curtos) marcadas.
//   3. Pontos com tooltip (data + nome + média) e clicáveis.
//
// Aceita uma série secundária ("ciclo anterior") tracejada pra comparação.

import { el } from '../../dom.js';

const SVG_NS = 'http://www.w3.org/2000/svg';

/**
 * @param {Array<{simuladoId?, nome, rotuloCurto?, data, media, cicloAnteriorMedia?, materia?}>} pontos
 * @param {object} opts
 *   width, height: dimensões do SVG
 *   yMax: padrão 10
 *   corte: { valor, label, eliminatoria } — linha horizontal de referência
 *   onPontoClick: (ponto) => void
 *   mostrarCicloAnterior: bool — se algum ponto tem cicloAnteriorMedia, desenha a série tracejada
 */
export function linhaTemporal(pontos, opts = {}) {
  const {
    width = 720,
    height = 220,
    yMax = 10,
    corte = null,
    onPontoClick = null,
    mostrarCicloAnterior = true,
  } = opts;

  if (!Array.isArray(pontos) || pontos.length === 0) {
    return el('div', { class: 'empty-state' }, ['Sem dados suficientes pra mostrar evolução.']);
  }

  const padLeft = 40;
  const padRight = 16;
  const padTop = 14;
  const padBottom = 36;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const n = pontos.length;
  const stepX = n > 1 ? plotW / (n - 1) : 0;
  const xDe = (i) => (n > 1 ? padLeft + i * stepX : padLeft + plotW / 2);
  const yDe = (v) => padTop + plotH - (v / yMax) * plotH;

  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'linha-temporal');
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

  // ── Grid horizontal + rótulos do eixo Y (a cada 2 pontos: 0, 2, 4, 6, 8, 10) ──
  const ticksY = [0, 2, 4, 6, 8, 10];
  ticksY.forEach((t) => {
    const y = yDe(t);
    const linha = document.createElementNS(SVG_NS, 'line');
    linha.setAttribute('x1', String(padLeft));
    linha.setAttribute('x2', String(padLeft + plotW));
    linha.setAttribute('y1', y.toFixed(1));
    linha.setAttribute('y2', y.toFixed(1));
    linha.setAttribute('stroke', 'var(--color-border)');
    linha.setAttribute('stroke-width', '1');
    if (t !== 0) linha.setAttribute('stroke-dasharray', '2,3');
    svg.appendChild(linha);

    const txt = document.createElementNS(SVG_NS, 'text');
    txt.setAttribute('x', String(padLeft - 6));
    txt.setAttribute('y', (y + 3).toFixed(1));
    txt.setAttribute('text-anchor', 'end');
    txt.setAttribute('font-size', '10');
    txt.setAttribute('fill', 'var(--color-text-tertiary)');
    txt.textContent = String(t);
    svg.appendChild(txt);
  });

  // ── Linha do corte (horizontal) ──
  if (corte?.valor != null) {
    const y = yDe(corte.valor);
    const ln = document.createElementNS(SVG_NS, 'line');
    ln.setAttribute('x1', String(padLeft));
    ln.setAttribute('x2', String(padLeft + plotW));
    ln.setAttribute('y1', y.toFixed(1));
    ln.setAttribute('y2', y.toFixed(1));
    ln.setAttribute(
      'stroke',
      corte.eliminatoria ? 'var(--color-red)' : 'var(--color-amber)',
    );
    ln.setAttribute('stroke-width', '1.5');
    ln.setAttribute('stroke-dasharray', '6,3');
    const t = document.createElementNS(SVG_NS, 'title');
    t.textContent = `Corte: ${corte.valor.toFixed(1).replace('.', ',')}${corte.eliminatoria ? ' (eliminatória)' : ''}`;
    ln.appendChild(t);
    svg.appendChild(ln);
  }

  // ── Linha do ciclo anterior (tracejada, atrás) ──
  const temCicloAnt =
    mostrarCicloAnterior &&
    pontos.some((p) => p.cicloAnteriorMedia != null);
  if (temCicloAnt) {
    const pontosAnt = pontos
      .map((p, i) => (p.cicloAnteriorMedia != null ? [xDe(i), yDe(p.cicloAnteriorMedia)] : null))
      .filter(Boolean);
    if (pontosAnt.length >= 2) {
      const path = document.createElementNS(SVG_NS, 'polyline');
      path.setAttribute('points', pontosAnt.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' '));
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', 'var(--color-text-tertiary)');
      path.setAttribute('stroke-width', '1.5');
      path.setAttribute('stroke-dasharray', '4,3');
      path.setAttribute('opacity', '0.7');
      svg.appendChild(path);
    }
  }

  // ── Linha principal (ciclo atual) ──
  const pontosAtual = pontos.map((p, i) => [xDe(i), yDe(p.media)]);
  const linhaAtual = document.createElementNS(SVG_NS, 'polyline');
  linhaAtual.setAttribute(
    'points',
    pontosAtual.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' '),
  );
  linhaAtual.setAttribute('fill', 'none');
  linhaAtual.setAttribute('stroke', 'var(--color-navy)');
  linhaAtual.setAttribute('stroke-width', '2');
  linhaAtual.setAttribute('stroke-linejoin', 'round');
  linhaAtual.setAttribute('stroke-linecap', 'round');
  svg.appendChild(linhaAtual);

  // ── Pontos clicáveis com tooltip ──
  pontos.forEach((p, i) => {
    const [x, y] = pontosAtual[i];
    const g = document.createElementNS(SVG_NS, 'g');
    g.setAttribute('class', 'linha-temporal__ponto');
    if (onPontoClick) g.style.cursor = 'pointer';

    const circ = document.createElementNS(SVG_NS, 'circle');
    circ.setAttribute('cx', x.toFixed(1));
    circ.setAttribute('cy', y.toFixed(1));
    circ.setAttribute('r', '4');
    circ.setAttribute('fill', 'var(--color-navy)');
    circ.setAttribute('stroke', 'var(--color-bg)');
    circ.setAttribute('stroke-width', '2');
    g.appendChild(circ);

    const t = document.createElementNS(SVG_NS, 'title');
    const partes = [
      p.rotuloCurto || p.nome,
      `Data: ${p.data || '—'}`,
      `Média: ${p.media.toFixed(2).replace('.', ',')}`,
    ];
    if (p.cicloAnteriorMedia != null) {
      partes.push(`Ciclo anterior: ${p.cicloAnteriorMedia.toFixed(2).replace('.', ',')}`);
    }
    if (p.nPresentes != null) partes.push(`Presentes: ${p.nPresentes}`);
    t.textContent = partes.join('\n');
    g.appendChild(t);

    if (onPontoClick) {
      g.addEventListener('click', () => onPontoClick(p));
    }
    svg.appendChild(g);
  });

  // ── Rótulos do eixo X (data ou rótulo curto, alternando se muitos pontos) ──
  const passo = Math.max(1, Math.ceil(n / 8));
  pontos.forEach((p, i) => {
    if (i % passo !== 0 && i !== n - 1) return;
    const txt = document.createElementNS(SVG_NS, 'text');
    txt.setAttribute('x', xDe(i).toFixed(1));
    txt.setAttribute('y', (padTop + plotH + 16).toFixed(1));
    txt.setAttribute('text-anchor', 'middle');
    txt.setAttribute('font-size', '10');
    txt.setAttribute('fill', 'var(--color-text-tertiary)');
    txt.textContent = p.rotuloCurto || _fmtDataCurta(p.data);
    svg.appendChild(txt);

    // Segunda linha menor com data se rótulo curto for usado.
    if (p.rotuloCurto && p.data) {
      const txt2 = document.createElementNS(SVG_NS, 'text');
      txt2.setAttribute('x', xDe(i).toFixed(1));
      txt2.setAttribute('y', (padTop + plotH + 28).toFixed(1));
      txt2.setAttribute('text-anchor', 'middle');
      txt2.setAttribute('font-size', '9');
      txt2.setAttribute('fill', 'var(--color-text-tertiary)');
      txt2.setAttribute('opacity', '0.7');
      txt2.textContent = _fmtDataCurta(p.data);
      svg.appendChild(txt2);
    }
  });

  return el('div', { class: 'linha-temporal__container' }, [
    svg,
    el('div', { class: 'linha-temporal__legenda' }, [
      _legenda('var(--color-navy)', 'Ciclo atual'),
      temCicloAnt ? _legenda('var(--color-text-tertiary)', 'Ciclo anterior', { tracejado: true }) : null,
      corte?.valor != null
        ? _legenda(
            corte.eliminatoria ? 'var(--color-red)' : 'var(--color-amber)',
            `Corte ${corte.valor.toFixed(1).replace('.', ',')}${corte.eliminatoria ? ' (eliminatória)' : ''}`,
            { tracejado: true },
          )
        : null,
    ].filter(Boolean)),
  ]);
}

function _legenda(cor, texto, { tracejado = false } = {}) {
  return el('span', { class: 'linha-temporal__legenda-item' }, [
    el('span', {
      class: 'linha-temporal__legenda-marca',
      style: `background: ${tracejado ? 'transparent' : cor}; border: 2px ${tracejado ? 'dashed' : 'solid'} ${cor};`,
    }, []),
    texto,
  ]);
}

function _fmtDataCurta(iso) {
  if (!iso) return '—';
  // YYYY-MM-DD → DD/MM
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return iso;
  return `${m[3]}/${m[2]}`;
}
