// Ficha de simulado. Métricas, distribuição, quebras por matéria/sede,
// tabela de notas. Tudo vem da API (cache do stats engine).

import { getApiClient } from '../services/api.js';
import { el, fmtNota } from '../dom.js';
import { kpi } from '../components/ui/kpi.js';
import { histograma } from '../components/ui/histograma.js';

export async function renderSimuladoFicha({ id }) {
  const api = getApiClient();
  const simulado = await api.obterSimulado(id);

  if (!simulado) {
    return el('section', { class: 'card' }, [
      el('div', { class: 'empty-state' }, [
        `Simulado ${id} não encontrado.`,
        el('div', { class: 'empty-state__hint' }, [el('a', { href: '#/simulados' }, ['← Voltar para a lista'])]),
      ]),
    ]);
  }

  const [hist, porMateria, porSede, notas] = await Promise.all([
    api.histogramaSimulado(id).catch(() => null),
    api.simuladoPorMateria(id).catch(() => []),
    api.simuladoPorSede(id).catch(() => []),
    api.notasSimulado(id).catch(() => []),
  ]);

  return el('section', { class: 'card' }, [
    el('div', { class: 'screen-header' }, [
      el('div', { class: 'screen-breadcrumb' }, [
        el('a', { href: '#/simulados' }, ['Simulados']),
        ' / ',
        simulado.id,
      ]),
      el('h1', { class: 'screen-title' }, [simulado.nome]),
      el('p', { class: 'screen-subtitle' }, [
        `${({ fase_1: 'Fase 1 · ', fase_2: 'Fase 2 · ' })[simulado.tipo] || ''}aplicado em ${simulado.dataAplicacao} · ${simulado.nPresentes ?? '—'} presentes`,
      ]),
    ]),

    el('div', { class: 'section' }, [
      el('div', { class: 'section__title' }, ['Métricas']),
      el('div', { class: 'kpi-grid' }, [
        kpi('Média', fmtNota(simulado.media)),
        kpi('Mediana', fmtNota(simulado.mediana)),
        kpi('Desvio padrão', fmtNota(simulado.desvioPadrao)),
        kpi('Presentes', String(simulado.nPresentes ?? '—')),
        kpi('Ausentes', String(hist?.nAusentes ?? '—')),
      ]),
    ]),

    el('div', { class: 'section' }, [
      el('div', { class: 'section__title' }, ['Distribuição']),
      el('p', { class: 'section__subtitle' }, ['Histograma de notas com bins de 0,5 ponto. Linhas tracejadas: média (vermelho) e mediana (âmbar).']),
      histograma(hist?.histograma, {
        media: hist?.media ?? simulado.media,
        mediana: hist?.mediana ?? simulado.mediana,
      }),
    ]),

    el('div', { class: 'section' }, [
      el('div', { class: 'section__title' }, ['Por matéria']),
      porMateria.length === 0
        ? el('p', { class: 'section__subtitle' }, ['Simulado sem irmãos por matéria no mesmo dia.'])
        : el('table', { class: 'data-table' }, [
            el('thead', {}, [
              el('tr', {}, [
                el('th', {}, ['Matéria']),
                el('th', {}, ['Média']),
                el('th', {}, ['Mediana']),
                el('th', {}, ['Desvio']),
                el('th', {}, ['Presentes']),
              ]),
            ]),
            el('tbody', {}, porMateria.map((m) =>
              el('tr', { onclick: () => { window.location.hash = `#/simulados/${m.simuladoId}`; } }, [
                el('td', {}, [m.materia]),
                el('td', {}, [fmtNota(m.media)]),
                el('td', {}, [fmtNota(m.mediana)]),
                el('td', {}, [fmtNota(m.desvioPadrao)]),
                el('td', {}, [String(m.nPresentes ?? '—')]),
              ])
            )),
          ]),
    ]),

    el('div', { class: 'section' }, [
      el('div', { class: 'section__title' }, ['Por sede']),
      porSede.length === 0
        ? el('p', { class: 'section__subtitle' }, ['Métricas por sede ainda não calculadas.'])
        : el('table', { class: 'data-table' }, [
            el('thead', {}, [
              el('tr', {}, [
                el('th', {}, ['Sede']),
                el('th', {}, ['Média']),
                el('th', {}, ['Mediana']),
                el('th', {}, ['Desvio']),
                el('th', {}, ['Presentes']),
              ]),
            ]),
            el('tbody', {}, porSede.map((s) =>
              el('tr', {}, [
                el('td', {}, [s.sede]),
                el('td', {}, [fmtNota(s.media)]),
                el('td', {}, [fmtNota(s.mediana)]),
                el('td', {}, [fmtNota(s.desvioPadrao)]),
                el('td', {}, [String(s.nPresentes ?? '—')]),
              ])
            )),
          ]),
    ]),

    el('div', { class: 'section' }, [
      el('div', { class: 'section__title' }, [`Notas individuais (${notas.length})`]),
      notas.length === 0
        ? el('p', { class: 'section__subtitle' }, ['Sem notas registradas ainda.'])
        : el('table', { class: 'data-table' }, [
            el('thead', {}, [
              el('tr', {}, [
                el('th', {}, ['Aluno']),
                el('th', {}, ['Pontuação']),
                el('th', {}, ['']),
              ]),
            ]),
            el('tbody', {}, notas.map((n) =>
              el('tr', { onclick: () => { if (n.alunoId) window.location.hash = `#/alunos/${n.alunoId}`; } }, [
                el('td', {}, [n.nome]),
                el('td', {}, [n.presente ? fmtNota(n.pontuacao) : el('span', { class: 'tag tone-ambar' }, ['Ausente'])]),
                el('td', {}, [n.alunoId ? el('a', { href: `#/alunos/${n.alunoId}` }, ['Ver →']) : '']),
              ])
            )),
          ]),
    ]),
  ]);
}
