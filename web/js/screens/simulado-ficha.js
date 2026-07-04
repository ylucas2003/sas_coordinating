// Ficha de simulado. Métricas, distribuição, quebras por matéria/sede,
// tabela de notas. Tudo vem da API (cache do stats engine).
//
// Suporta edição manual: botão "Editar simulado" no header e botão "Editar"
// por linha na tabela de notas. Cada edição passa por confirmação antes de
// chamar a API.

import { getApiClient } from '../services/api.js';
import { el, clear, fmtNota } from '../dom.js';
import { kpi } from '../components/ui/kpi.js';
import { histograma } from '../components/ui/histograma.js';
import { abrirEdicaoNota, abrirEdicaoSimulado } from '../components/ui/dialog.js';

export async function renderSimuladoFicha({ id }) {
  const api = getApiClient();

  // Container raiz persistente — recarregar() substitui seu conteúdo interno
  // sem desmontar o elemento que o router já inseriu na árvore.
  const raiz = el('section', { class: 'card' });

  let primeiraVez = true;

  async function recarregar() {
    if (!primeiraVez) api.limparCacheDados();
    primeiraVez = false;

    const simulado = await api.obterSimulado(id);
    if (!simulado) {
      clear(raiz);
      raiz.appendChild(
        el('div', { class: 'empty-state' }, [
          `Simulado ${id} não encontrado.`,
          el('div', { class: 'empty-state__hint' }, [
            el('a', { href: '#/simulados' }, ['← Voltar para a lista']),
          ]),
        ])
      );
      return;
    }

    const [hist, porMateria, porSede, notas] = await Promise.all([
      api.histogramaSimulado(id).catch(() => null),
      api.simuladoPorMateria(id).catch(() => []),
      api.simuladoPorSede(id).catch(() => []),
      api.notasSimulado(id).catch(() => []),
    ]);

    clear(raiz);

    // ── Header ──
    raiz.appendChild(
      el('div', { class: 'screen-header' }, [
        el('div', { class: 'screen-breadcrumb' }, [
          el('a', { href: '#/simulados' }, ['Simulados']),
          ' / ',
          simulado.id,
        ]),
        el('div', { style: 'display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;' }, [
          el('h1', { class: 'screen-title', style: 'margin:0;' }, [simulado.nome]),
          simulado.anulado
            ? el('span', { class: 'tag tone-anulado' }, ['Anulado'])
            : null,
        ]),
        el('div', { style: 'display:flex; align-items:center; gap:12px; margin-top:4px;' }, [
          el('p', { class: 'screen-subtitle', style: 'margin:0;' }, [
            `${({ fase_1: 'Fase 1 · ', fase_2: 'Fase 2 · ' })[simulado.tipo] || ''}` +
            `aplicado em ${simulado.dataAplicacao} · ${simulado.nPresentes ?? '—'} presentes`,
          ]),
          el('button', {
            class: 'btn-editar-sim',
            onclick: () => editarSimulado(simulado),
          }, ['✏ Editar simulado']),
        ]),
      ])
    );

    // ── Métricas ──
    raiz.appendChild(
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Métricas']),
        el('div', { class: 'kpi-grid' }, [
          kpi('Média', fmtNota(simulado.media)),
          kpi('Mediana', fmtNota(simulado.mediana)),
          kpi('Desvio padrão', fmtNota(simulado.desvioPadrao)),
          kpi('Presentes', String(simulado.nPresentes ?? '—')),
          kpi('Ausentes', String(hist?.nAusentes ?? '—')),
        ]),
      ])
    );

    // ── Distribuição ──
    raiz.appendChild(
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Distribuição']),
        el('p', { class: 'section__subtitle' }, [
          'Histograma de notas com bins de 0,5 ponto. Linhas tracejadas: média (vermelho) e mediana (âmbar).',
        ]),
        histograma(hist?.histograma, {
          media: hist?.media ?? simulado.media,
          mediana: hist?.mediana ?? simulado.mediana,
        }),
      ])
    );

    // ── Por matéria ──
    raiz.appendChild(
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
      ])
    );

    // ── Por sede ──
    raiz.appendChild(
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
      ])
    );

    // ── Notas individuais ──
    raiz.appendChild(
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
                  el('th', {}, ['']),
                ]),
              ]),
              el('tbody', {}, notas.map((n) =>
                el('tr', {
                  onclick: () => {
                    if (n.alunoId) window.location.hash = `#/alunos/${n.alunoId}`;
                  },
                }, [
                  el('td', {}, [n.nome]),
                  el('td', {}, [
                    n.presente
                      ? fmtNota(n.pontuacao)
                      : el('span', { class: 'tag tone-ambar' }, ['Ausente']),
                  ]),
                  el('td', {}, [
                    n.alunoId ? el('a', { href: `#/alunos/${n.alunoId}` }, ['Ver →']) : '',
                  ]),
                  el('td', { onclick: (ev) => ev.stopPropagation() }, [
                    el('button', {
                      class: 'btn-editar',
                      onclick: () => editarNota(n, simulado),
                    }, ['Editar']),
                  ]),
                ])
              )),
            ]),
      ])
    );
  }

  // ── Handlers de edição ──

  async function editarSimulado(simulado) {
    const resultado = await abrirEdicaoSimulado({
      nome: simulado.nome,
      rotuloAtual: simulado.rotuloCurto,
      notaMaximaAtual: simulado.notaMaxima,
      anuladoAtual: simulado.anulado,
    });
    if (!resultado) return;

    try {
      await api.editarSimulado(id, resultado);
      await recarregar();
    } catch (err) {
      alert(`Erro ao salvar: ${err.message}`);
    }
  }

  async function editarNota(notaLinha, simulado) {
    // notaLinha.pontuacao já está em escala 0–10 (vem de GET /simulados/{id}/notas).
    // O backend espera pontuação bruta — back-calculamos aqui.
    const pontuacaoRaw = notaLinha.presente && notaLinha.pontuacao != null && simulado.notaMaxima > 0
      ? Math.round(notaLinha.pontuacao / 10 * simulado.notaMaxima * 100) / 100
      : null;

    const resultado = await abrirEdicaoNota({
      nomeAluno: notaLinha.nome,
      nomeSimulado: simulado.rotuloCurto || simulado.nome,
      pontuacaoAtual: pontuacaoRaw,
      presenteAtual: notaLinha.presente,
      notaMaxima: simulado.notaMaxima,
    });
    if (!resultado) return;

    try {
      await api.editarNota(notaLinha.alunoId, id, resultado);
      await recarregar();
    } catch (err) {
      alert(`Erro ao salvar: ${err.message}`);
    }
  }

  await recarregar();
  return raiz;
}
