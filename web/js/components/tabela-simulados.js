// Tabela de simulados — usada tanto na tela Simulados quanto na ficha do aluno.
// Quando recebe `notasAluno` (Map<simuladoId, nota>), adiciona as colunas
// "Sua nota" e "Δ" (diferença vs média da turma).

import { el, fmtNota } from '../dom.js';

const TIPO_LABEL = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

export function fmtDataBR(iso) {
  if (!iso) return '—';
  const [ano, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${ano}`;
}

export function rotuloCiclo(ordem, vestibular) {
  if (ordem == null) return 'Sem ciclo';
  return vestibular ? `C${ordem} · ${vestibular}` : `C${ordem}`;
}

function celulaSuaNota(nota) {
  if (nota == null) return el('td', { class: 'sim-tabela__sua' }, ['—']);
  return el('td', { class: 'sim-tabela__sua' }, [fmtNota(nota)]);
}

function celulaDelta(nota, media) {
  if (nota == null || media == null) return el('td', {}, ['—']);
  const delta = nota - media;
  const sinal = delta > 0 ? '+' : '';
  const classe = delta > 0.1 ? 'tone-verde' : delta < -0.1 ? 'tone-vermelho' : '';
  return el('td', { class: `sim-tabela__delta ${classe}` }, [
    `${sinal}${delta.toFixed(1).replace('.', ',')}`,
  ]);
}

/**
 * @param {object} opcoes
 * @param {Array} opcoes.simulados
 * @param {Map<string, number>} [opcoes.notasAluno] - se presente, mostra colunas do aluno
 * @param {boolean} [opcoes.compacto] - oculta colunas mediana/sigma quando true
 * @param {(simulado: object, notaAtual: number|null) => void} [opcoes.onEditarNota] -
 *   callback de edição manual; quando fornecido, adiciona botão "Editar" por linha
 */
export function tabelaSimulados({ simulados, notasAluno = null, compacto = false, onEditarNota = null }) {
  if (!simulados.length) {
    return el('div', { class: 'sim-tabela__vazio' }, [
      'Nenhum simulado bate com os filtros.',
    ]);
  }

  const temAluno = !!notasAluno;

  const temEditar = !!onEditarNota;

  const cabecalho = el('tr', {}, [
    el('th', {}, ['Pn']),
    el('th', {}, ['Matéria']),
    el('th', {}, ['Fase']),
    el('th', {}, ['Vest.']),
    el('th', {}, ['Ciclo']),
    el('th', {}, ['Data']),
    temAluno ? el('th', {}, ['Sua nota']) : null,
    el('th', {}, ['Média']),
    temAluno ? el('th', {}, ['Δ']) : null,
    !compacto ? el('th', {}, ['Mediana']) : null,
    !compacto ? el('th', {}, ['σ']) : null,
    !compacto ? el('th', {}, ['n']) : null,
    el('th', {}, ['']),
    temEditar ? el('th', {}, ['']) : null,
  ].filter(Boolean));

  const linhas = simulados.map((s) => {
    const notaAluno = temAluno ? notasAluno.get(s.id) : null;

    const tdEditar = temEditar
      ? el('td', { onclick: (ev) => ev.stopPropagation() }, [
          el('button', {
            class: 'btn-editar',
            onclick: () => onEditarNota(s, notaAluno ?? null),
          }, ['Editar']),
        ])
      : null;

    return el(
      'tr',
      { onclick: () => { window.location.hash = `#/simulados/${s.id}`; } },
      [
        el('td', { class: 'sim-tabela__pn' }, [s.rotuloCurto || '—']),
        el('td', {}, [s.materia?.nome || '—']),
        el('td', {}, [TIPO_LABEL[s.tipo] || '—']),
        el('td', {}, [s.vestibularAlvo || '—']),
        el('td', {}, [rotuloCiclo(s.cicloOrdem, s.vestibularAlvo)]),
        el('td', { class: 'sim-tabela__data' }, [fmtDataBR(s.dataAplicacao)]),
        temAluno ? celulaSuaNota(notaAluno) : null,
        el('td', {}, [fmtNota(s.media)]),
        temAluno ? celulaDelta(notaAluno, s.media) : null,
        !compacto ? el('td', {}, [fmtNota(s.mediana)]) : null,
        !compacto ? el('td', {}, [fmtNota(s.desvioPadrao)]) : null,
        !compacto ? el('td', {}, [s.nPresentes == null ? '—' : String(s.nPresentes)]) : null,
        el('td', {}, [el('a', { href: `#/simulados/${s.id}` }, ['Ver →'])]),
        tdEditar,
      ].filter(Boolean)
    );
  });

  return el('table', { class: 'data-table sim-tabela' }, [
    el('thead', {}, [cabecalho]),
    el('tbody', {}, linhas),
  ]);
}
