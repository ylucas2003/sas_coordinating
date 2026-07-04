// Lista de simulados com filtros locais (chips por categoria) + calendário anual.
// Os filtros são AND entre categorias, OR dentro de uma categoria.

import { getApiClient } from '../services/api.js';
import { el, clear } from '../dom.js';
import { simFiltros } from '../components/sim-filtros.js';
import { calendarioAnual } from '../components/calendario-anual.js';
import { tabelaSimulados } from '../components/tabela-simulados.js';
import { aplicarFiltros, montarOpcoes, contarPorChip } from '../components/sim-filtros-logica.js';

export async function renderSimulados({ sidebarEl } = {}) {
  const api = getApiClient();
  const simulados = await api.listarSimulados();
  const opcoesDisponiveis = montarOpcoes(simulados);

  const estado = {
    ciclos: new Set(),
    materias: new Set(),
    fases: new Set(),
    vestibulares: new Set(),
    datas: new Set(),
  };

  // UI state: calendário começa oculto, usuário decide quando mostrar.
  let calendarioVisivel = false;

  const containerCalendario = el('div', {}, []);
  const containerTabela = el('div', { class: 'section' }, []);

  function rerender() {
    const filtrados = aplicarFiltros(simulados, estado);
    const contagens = contarPorChip(simulados, estado);

    // Datas que devem aparecer no calendário = datas dos simulados que passariam
    // por todos os filtros EXCETO o filtro de data (pra não anular a si mesmo).
    const estadoSemDatas = { ...estado, datas: new Set() };
    const datasNoCalendario = new Set(
      aplicarFiltros(simulados, estadoSemDatas).map((s) => s.dataAplicacao).filter(Boolean)
    );

    if (sidebarEl) {
      clear(sidebarEl);
      sidebarEl.appendChild(el('div', { class: 'sidebar__label' }, ['Filtros']));
      sidebarEl.appendChild(simFiltros({
        opcoesDisponiveis,
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

    clear(containerCalendario);
    const labelBotao = calendarioVisivel
      ? 'Ocultar calendário'
      : `Mostrar calendário · ${datasNoCalendario.size} dia(s)`;
    const botaoToggle = el(
      'button',
      {
        class: `sim-calendario-toggle${calendarioVisivel ? ' is-aberto' : ''}`,
        onclick: () => {
          calendarioVisivel = !calendarioVisivel;
          rerender();
        },
      },
      [
        el('span', { class: 'sim-calendario-toggle__seta' }, [calendarioVisivel ? '▾' : '▸']),
        labelBotao,
      ]
    );
    containerCalendario.appendChild(botaoToggle);
    if (calendarioVisivel) {
      containerCalendario.appendChild(calendarioAnual({
        datasComSimulado: datasNoCalendario,
        datasSelecionadas: estado.datas,
        onToggleData: (iso) => {
          if (estado.datas.has(iso)) estado.datas.delete(iso);
          else estado.datas.add(iso);
          rerender();
        },
      }));
    }

    clear(containerTabela);
    containerTabela.appendChild(tabelaSimulados({ simulados: filtrados }));

    const sub = document.getElementById('sim-subtitulo');
    if (sub) {
      sub.textContent = `${filtrados.length} de ${simulados.length} simulados`;
    }
  }

  rerender();

  return el('div', { class: 'screen-stack' }, [
    el('section', { class: 'card' }, [
      el('div', { class: 'screen-header' }, [
        el('div', { class: 'screen-breadcrumb' }, ['Simulados']),
        el('h1', { class: 'screen-title' }, ['Simulados aplicados']),
        el('p', { class: 'screen-subtitle', id: 'sim-subtitulo' }, [`${simulados.length} simulados`]),
      ]),
      containerCalendario,
    ]),
    el('section', { class: 'card' }, [
      containerTabela,
    ]),
  ]);
}
