// Filtros locais da tela de Simulados: grupos de chips por categoria.
// Não compartilha estado com o filterStrip global — substitui-o nesta tela.

import { el } from '../dom.js';

/**
 * Renderiza uma linha de chips por categoria.
 *
 * @param {object} opcoes
 * @param {string} opcoes.rotulo
 * @param {Array<{valor: any, label: string, contagem?: number}>} opcoes.opcoes
 * @param {Set<any>} opcoes.selecionados
 * @param {(valor: any) => void} opcoes.onToggle
 */
function grupoChips({ rotulo, opcoes, selecionados, onToggle }) {
  // Esconde chips que não traríam nenhum resultado dado os outros filtros
  // (contagem == null/0). Mantém visíveis os que estão ativos, pra permitir
  // desmarcar — senão o usuário fica preso num filtro que ele não consegue
  // mais ver.
  const visiveis = opcoes.filter((opcao) => {
    const ativo = selecionados.has(opcao.valor);
    return ativo || (opcao.contagem != null && opcao.contagem > 0);
  });

  if (!visiveis.length) {
    return el('div', { class: 'sim-filtros__linha' }, [
      el('div', { class: 'sim-filtros__rotulo' }, [rotulo]),
      el('div', { class: 'sim-filtros__vazio' }, ['—']),
    ]);
  }

  return el('div', { class: 'sim-filtros__linha' }, [
    el('div', { class: 'sim-filtros__rotulo' }, [rotulo]),
    ...visiveis.map((opcao) => {
      const ativo = selecionados.has(opcao.valor);
      return el(
        'button',
        {
          class: `sim-chip${ativo ? ' is-active' : ''}`,
          onclick: () => onToggle(opcao.valor),
        },
        [
          opcao.label,
          opcao.contagem != null
            ? el('span', { class: 'sim-chip__contagem' }, [`· ${opcao.contagem}`])
            : null,
        ]
      );
    }),
  ]);
}

/**
 * @param {object} opcoes
 * @param {object} opcoes.opcoesDisponiveis - { ciclos, materias, fases, vestibulares }
 * @param {object} opcoes.estado - { ciclos: Set, materias: Set, fases: Set, vestibulares: Set }
 * @param {(grupo: string, valor: any) => void} opcoes.onToggle
 * @param {() => void} opcoes.onReset
 * @param {object} opcoes.contagens - { ciclo: Map, materia: Map, fase: Map, vestibular: Map }
 */
export function simFiltros({ opcoesDisponiveis, estado, onToggle, onReset, contagens }) {
  const algumAtivo =
    estado.ciclos.size + estado.materias.size + estado.fases.size +
    estado.vestibulares.size + estado.datas.size > 0;

  return el('div', { class: 'sim-filtros' }, [
    grupoChips({
      rotulo: 'Vestibular',
      opcoes: opcoesDisponiveis.vestibulares.map((v) => ({
        valor: v,
        label: v,
        contagem: contagens.vestibular.get(v),
      })),
      selecionados: estado.vestibulares,
      onToggle: (v) => onToggle('vestibulares', v),
    }),
    grupoChips({
      rotulo: 'Fase',
      opcoes: opcoesDisponiveis.fases.map((f) => ({
        valor: f.valor,
        label: f.label,
        contagem: contagens.fase.get(f.valor),
      })),
      selecionados: estado.fases,
      onToggle: (v) => onToggle('fases', v),
    }),
    grupoChips({
      rotulo: 'Ciclo',
      opcoes: opcoesDisponiveis.ciclos.map((c) => ({
        valor: c.ordem,
        label: c.label,
        contagem: contagens.ciclo.get(c.ordem),
      })),
      selecionados: estado.ciclos,
      onToggle: (v) => onToggle('ciclos', v),
    }),
    grupoChips({
      rotulo: 'Disciplina',
      opcoes: opcoesDisponiveis.materias.map((m) => ({
        valor: m.codigo,
        label: m.nome,
        contagem: contagens.materia.get(m.codigo),
      })),
      selecionados: estado.materias,
      onToggle: (v) => onToggle('materias', v),
    }),
    el('div', { class: 'sim-filtros__linha' }, [
      el('div', { class: 'sim-filtros__rotulo' }, ['']),
      el(
        'button',
        {
          class: 'sim-filtros__reset',
          disabled: !algumAtivo,
          onclick: onReset,
        },
        ['Limpar filtros']
      ),
    ]),
  ]);
}
