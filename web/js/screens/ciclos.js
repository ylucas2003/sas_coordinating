// Lista de ciclos com filtros locais (Vestibular, Ano letivo).

import { getApiClient } from '../services/api.js';
import { el, clear } from '../dom.js';

function fmtData(iso) {
  if (!iso) return '—';
  const [a, m, d] = iso.split('-');
  return `${d}/${m}/${a}`;
}

function aplicarFiltros(ciclos, estado) {
  return ciclos.filter((c) => {
    if (estado.vestibulares.size && !estado.vestibulares.has(c.vestibularAlvo)) return false;
    if (estado.anos.size && !estado.anos.has(c.anoLetivo)) return false;
    return true;
  });
}

function montarOpcoes(ciclos) {
  const vestibulares = [...new Set(ciclos.map((c) => c.vestibularAlvo).filter(Boolean))].sort();
  const anos = [...new Set(ciclos.map((c) => c.anoLetivo).filter(Boolean))].sort((a, b) => b - a);
  return { vestibulares, anos };
}

function contarPorChip(ciclos, estado) {
  const vestibular = new Map();
  const ano = new Map();

  function passa(c, ignorada) {
    if (ignorada !== 'vestibulares' && estado.vestibulares.size && !estado.vestibulares.has(c.vestibularAlvo)) return false;
    if (ignorada !== 'anos' && estado.anos.size && !estado.anos.has(c.anoLetivo)) return false;
    return true;
  }

  for (const c of ciclos) {
    if (c.vestibularAlvo && passa(c, 'vestibulares')) {
      vestibular.set(c.vestibularAlvo, (vestibular.get(c.vestibularAlvo) || 0) + 1);
    }
    if (c.anoLetivo && passa(c, 'anos')) {
      ano.set(c.anoLetivo, (ano.get(c.anoLetivo) || 0) + 1);
    }
  }
  return { vestibular, ano };
}

function grupoChips({ rotulo, opcoes, selecionados, onToggle }) {
  const visiveis = opcoes.filter((o) => {
    const ativo = selecionados.has(o.valor);
    return ativo || (o.contagem != null && o.contagem > 0);
  });
  if (!visiveis.length) {
    return el('div', { class: 'sim-filtros__linha' }, [
      el('div', { class: 'sim-filtros__rotulo' }, [rotulo]),
      el('div', { class: 'sim-filtros__vazio' }, ['—']),
    ]);
  }
  return el('div', { class: 'sim-filtros__linha' }, [
    el('div', { class: 'sim-filtros__rotulo' }, [rotulo]),
    ...visiveis.map((o) => {
      const ativo = selecionados.has(o.valor);
      return el(
        'button',
        {
          class: `sim-chip${ativo ? ' is-active' : ''}`,
          onclick: () => onToggle(o.valor),
        },
        [
          o.label,
          o.contagem != null
            ? el('span', { class: 'sim-chip__contagem' }, [`· ${o.contagem}`])
            : null,
        ]
      );
    }),
  ]);
}

function filtrosCiclos({ opcoes, estado, contagens, onToggle, onReset }) {
  const algumAtivo = estado.vestibulares.size + estado.anos.size > 0;
  const linhas = [
    grupoChips({
      rotulo: 'Vestibular',
      opcoes: opcoes.vestibulares.map((v) => ({ valor: v, label: v, contagem: contagens.vestibular.get(v) })),
      selecionados: estado.vestibulares,
      onToggle: (v) => onToggle('vestibulares', v),
    }),
  ];
  // Ano letivo só aparece se houver mais de um ano (senão é redundante)
  if (opcoes.anos.length > 1) {
    linhas.push(
      grupoChips({
        rotulo: 'Ano letivo',
        opcoes: opcoes.anos.map((a) => ({ valor: a, label: String(a), contagem: contagens.ano.get(a) })),
        selecionados: estado.anos,
        onToggle: (v) => onToggle('anos', v),
      })
    );
  }
  linhas.push(
    el('div', { class: 'sim-filtros__linha' }, [
      el('div', { class: 'sim-filtros__rotulo' }, ['']),
      el(
        'button',
        { class: 'sim-filtros__reset', disabled: !algumAtivo, onclick: onReset },
        ['Limpar filtros']
      ),
    ])
  );
  return el('div', { class: 'sim-filtros' }, linhas);
}

function tabelaCiclos(ciclos) {
  if (!ciclos.length) {
    return el('div', { class: 'sim-tabela__vazio' }, ['Nenhum ciclo bate com os filtros.']);
  }
  return el('table', { class: 'data-table' }, [
    el('thead', {}, [
      el('tr', {}, [
        el('th', {}, ['Ciclo']),
        el('th', {}, ['Vestibular']),
        el('th', {}, ['Período']),
        el('th', {}, ['Simulados']),
        el('th', {}, ['']),
      ]),
    ]),
    el('tbody', {}, ciclos.map((c) =>
      el(
        'tr',
        { onclick: () => { window.location.hash = `#/ciclos/${c.id}`; } },
        [
          el('td', {}, [c.nome]),
          el('td', {}, [
            c.vestibularAlvo
              ? el('span', { class: 'tag tone-navy' }, [c.vestibularAlvo])
              : '—',
          ]),
          el('td', {}, [`${fmtData(c.periodoInicio)} → ${fmtData(c.periodoFim)}`]),
          el('td', {}, [String((c.simuladoIds || []).length)]),
          el('td', {}, [el('a', { href: `#/ciclos/${c.id}` }, ['Ver →'])]),
        ]
      )
    )),
  ]);
}

export async function renderCiclos({ sidebarEl } = {}) {
  const api = getApiClient();
  const ciclos = await api.listarCiclos();
  const opcoes = montarOpcoes(ciclos);

  const estado = {
    vestibulares: new Set(),
    anos: new Set(),
  };

  const containerTabela = el('div', { class: 'section' }, []);

  function rerender() {
    const filtrados = aplicarFiltros(ciclos, estado);
    const contagens = contarPorChip(ciclos, estado);

    if (sidebarEl) {
      clear(sidebarEl);
      sidebarEl.appendChild(el('div', { class: 'sidebar__label' }, ['Filtros']));
      sidebarEl.appendChild(filtrosCiclos({
        opcoes,
        estado,
        contagens,
        onToggle: (grupo, valor) => {
          const set = estado[grupo];
          if (set.has(valor)) set.delete(valor);
          else set.add(valor);
          rerender();
        },
        onReset: () => {
          for (const k of Object.keys(estado)) estado[k].clear();
          rerender();
        },
      }));
    }

    clear(containerTabela);
    containerTabela.appendChild(tabelaCiclos(filtrados));

    const sub = document.getElementById('ciclo-subtitulo');
    if (sub) {
      sub.textContent = `${filtrados.length} de ${ciclos.length} ciclos`;
    }
  }

  rerender();

  return el('div', { class: 'screen-stack' }, [
    el('section', { class: 'card' }, [
      el('div', { class: 'screen-header' }, [
        el('div', { class: 'screen-breadcrumb' }, ['Ciclos']),
        el('h1', { class: 'screen-title' }, ['Ciclos do ano letivo']),
        el('p', { class: 'screen-subtitle', id: 'ciclo-subtitulo' }, [`${ciclos.length} ciclos`]),
      ]),
    ]),
    el('section', { class: 'card' }, [
      containerTabela,
    ]),
  ]);
}
