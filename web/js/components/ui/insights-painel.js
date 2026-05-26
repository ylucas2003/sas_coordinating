// Painel de insights gerados por LLM — lista de bullets com leitura
// coordenacional do recorte. Lida com 3 estados:
//   - bullets presentes  → renderiza
//   - bullets = []       → estado "indisponível" (LLM não configurado, ou erro)
//   - bullets = null     → loading skeleton (caller pode setar enquanto fetch roda)

import { el } from '../../dom.js';

export function insightsPainel(bullets, opts = {}) {
  const {
    titulo = 'Leitura do coordenador',
    legenda = 'Geradas automaticamente a partir das estatísticas deste recorte.',
  } = opts;

  if (bullets == null) {
    return el('div', { class: 'insights-painel insights-painel--loading' }, [
      el('div', { class: 'insights-painel__header' }, [
        el('h3', { class: 'insights-painel__titulo' }, [titulo]),
      ]),
      el('div', { class: 'insights-painel__skeleton' }, [
        el('div', { class: 'insights-painel__skeleton-linha' }, []),
        el('div', { class: 'insights-painel__skeleton-linha' }, []),
        el('div', { class: 'insights-painel__skeleton-linha' }, []),
      ]),
    ]);
  }

  if (!Array.isArray(bullets) || bullets.length === 0) {
    return el('div', { class: 'insights-painel insights-painel--vazio' }, [
      el('div', { class: 'insights-painel__header' }, [
        el('h3', { class: 'insights-painel__titulo' }, [titulo]),
      ]),
      el('p', { class: 'insights-painel__indisponivel' }, [
        'Análise textual indisponível para este recorte. As estatísticas acima já contêm todos os números relevantes.',
      ]),
    ]);
  }

  return el('div', { class: 'insights-painel' }, [
    el('div', { class: 'insights-painel__header' }, [
      el('h3', { class: 'insights-painel__titulo' }, [titulo]),
      el('p', { class: 'insights-painel__legenda' }, [legenda]),
    ]),
    el('ul', { class: 'insights-painel__bullets' },
      bullets.map((b) => el('li', { class: 'insights-painel__bullet' }, [b])),
    ),
  ]);
}
