// KPI compacto: rótulo em cima, valor grande embaixo.
// Tom opcional muda a cor do valor (tone-verde/ambar/vermelho/navy).

import { el } from '../../dom.js';

export function kpi(rotulo, valor, { tone = '', suffix = '' } = {}) {
  return el('div', { class: 'kpi' }, [
    el('div', { class: 'kpi__rotulo' }, [rotulo]),
    el('div', { class: `kpi__valor ${tone}` }, [
      String(valor ?? '—'),
      suffix ? el('span', { class: 'kpi__sufixo' }, [suffix]) : null,
    ]),
  ]);
}
