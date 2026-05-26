// Heatmap matérias × simulados, agrupado por ciclo.
// Cores: degradê vermelho → âmbar → verde com base na pontuação / nota_maxima.
//
// Layout (3 níveis de header):
//   [Ciclo 1 · IME]  [Ciclo 2 · IME]  [Ciclo 3 · ITA]
//   [  F1   ][ F2 ]  [F1 ][ F2  ]     [   F1     ]
//   P1 P2    P3 P4   P5  P6 P7         P8 P9 P10
//   09/02   24/03    ...
//
// Bandas verticais alternadas separam ciclos visualmente.

import { el } from '../../dom.js';

const CELL_W = 50;
const CELL_H = 30;
const LABEL_W = 110;

const FASE_LABEL = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

export function heatmap(payload, opts = {}) {
  const { notaMaxima = 10 } = opts;

  if (!payload || !Array.isArray(payload.materias) || payload.materias.length === 0) {
    return el('div', { class: 'empty-state' }, ['Sem notas suficientes para o heatmap.']);
  }

  const { materias, simulados, celulas } = payload;
  const indice = new Map();
  for (const c of celulas) {
    indice.set(`${c.materia}|${c.simuladoId}`, c.pontuacao);
  }

  // ── Agrupa simulados sequencialmente em ciclos e dentro de cada ciclo em fases.
  // Mantém ordem do array (já vem ordenado por ciclo/fase/data do backend).
  const grupos = _agruparPorCiclo(simulados);

  // ── 3 linhas de header (Ciclo / Fase / Pn+Data) com colspan ──
  const cabecalhoCiclo = el('tr', { class: 'heatmap__head heatmap__head-ciclo' }, [
    el('th', { class: 'heatmap__th-canto' }, ['']),
    ...grupos.map((g) => {
      const total = g.fases.reduce((acc, f) => acc + f.simulados.length, 0);
      return el('th', {
        class: `heatmap__th-ciclo ${g.faixa === 'A' ? 'faixa-a' : 'faixa-b'}`,
        colspan: String(total),
      }, [
        g.cicloOrdem != null ? `Ciclo ${g.cicloOrdem}` : (g.cicloNome || 'Sem ciclo'),
        g.vestibularAlvo
          ? el('span', { class: 'heatmap__th-vestibular' }, [` · ${g.vestibularAlvo}`])
          : null,
      ]);
    }),
  ]);

  const cabecalhoFase = el('tr', { class: 'heatmap__head heatmap__head-fase' }, [
    el('th', { class: 'heatmap__th-canto' }, ['']),
    ...grupos.flatMap((g) =>
      g.fases.map((f, idx) =>
        el('th', {
          class: `heatmap__th-fase ${g.faixa === 'A' ? 'faixa-a' : 'faixa-b'} ${idx > 0 ? 'borda-esq' : ''}`,
          colspan: String(f.simulados.length),
        }, [FASE_LABEL[f.fase] || '—'])
      )
    ),
  ]);

  const cabecalhoSim = el('tr', { class: 'heatmap__head heatmap__head-sim' }, [
    el('th', { class: 'heatmap__th-canto' }, ['']),
    ...grupos.flatMap((g) =>
      g.fases.flatMap((f, faseIdx) =>
        f.simulados.map((s, simIdx) =>
          el('th', {
            class: `heatmap__th-sim ${g.faixa === 'A' ? 'faixa-a' : 'faixa-b'} ${faseIdx > 0 && simIdx === 0 ? 'borda-esq' : ''}`,
            title: `${s.nome} · ${s.dataAplicacao}`,
          }, [
            el('div', { class: 'heatmap__th-pn' }, [s.rotulo || s.nome]),
            el('div', { class: 'heatmap__th-data' }, [_fmtDataCurta(s.dataAplicacao)]),
          ])
        )
      )
    ),
  ]);

  // ── Linhas (uma por matéria) ──
  const linhas = materias.map((m) =>
    el('tr', {}, [
      el('th', { class: 'heatmap__th-mat' }, [m]),
      ...grupos.flatMap((g) =>
        g.fases.flatMap((f, faseIdx) =>
          f.simulados.map((s, simIdx) => {
            const v = indice.get(`${m}|${s.id}`);
            const classesBase = `heatmap__cel ${g.faixa === 'A' ? 'faixa-a' : 'faixa-b'} ${faseIdx > 0 && simIdx === 0 ? 'borda-esq' : ''}`;
            if (v == null) {
              return el('td', { class: `${classesBase} vazio` }, ['']);
            }
            const cor = _corPorNota(v, notaMaxima);
            return el('td',
              {
                class: classesBase,
                style: `background:${cor.fundo}; color:${cor.texto};`,
                title: `${m} · ${s.rotulo || s.nome} (${s.dataAplicacao}): ${_fmt(v)}`,
              },
              [_fmt(v)]
            );
          })
        )
      ),
    ])
  );

  return el('div', { class: 'heatmap__container' }, [
    el('table', {
      class: 'heatmap heatmap--agrupado',
      style: `--cell-w:${CELL_W}px; --cell-h:${CELL_H}px; --label-w:${LABEL_W}px;`,
    }, [
      el('thead', {}, [cabecalhoCiclo, cabecalhoFase, cabecalhoSim]),
      el('tbody', {}, linhas),
    ]),
  ]);
}


// ─── Helpers ──────────────────────────────────────────────────────────────


function _agruparPorCiclo(simulados) {
  // Agrupa sequencialmente. Cada vez que muda cicloId, vira um grupo novo.
  // Dentro do grupo, agrupa por fase (também sequencialmente).
  const grupos = [];
  let cicloAtual = null;
  let alternaFaixa = 'A';

  for (const s of simulados) {
    const cId = s.cicloId || `_sem_${s.fase || 'na'}`;
    if (!cicloAtual || cicloAtual.cicloId !== cId) {
      cicloAtual = {
        cicloId: s.cicloId,
        cicloOrdem: s.cicloOrdem,
        cicloNome: s.cicloNome,
        vestibularAlvo: s.vestibularAlvo,
        faixa: alternaFaixa,
        fases: [],
      };
      alternaFaixa = alternaFaixa === 'A' ? 'B' : 'A';
      grupos.push(cicloAtual);
    }
    const faseAtual = cicloAtual.fases[cicloAtual.fases.length - 1];
    if (!faseAtual || faseAtual.fase !== s.fase) {
      cicloAtual.fases.push({ fase: s.fase, simulados: [s] });
    } else {
      faseAtual.simulados.push(s);
    }
  }
  return grupos;
}


function _corPorNota(v, max) {
  if (v == null) return { fundo: 'transparent', texto: 'inherit' };
  const ratio = Math.max(0, Math.min(1, v / max));
  let fundo;
  if (ratio < 0.5) {
    fundo = _mistura('#d9354a', '#e89b2a', ratio / 0.5);
  } else {
    fundo = _mistura('#e89b2a', '#2e8c5a', (ratio - 0.5) / 0.5);
  }
  return { fundo, texto: '#fff' };
}


function _mistura(hexA, hexB, t) {
  const a = _hex(hexA);
  const b = _hex(hexB);
  const r = Math.round(a[0] + (b[0] - a[0]) * t);
  const g = Math.round(a[1] + (b[1] - a[1]) * t);
  const bb = Math.round(a[2] + (b[2] - a[2]) * t);
  return `rgb(${r}, ${g}, ${bb})`;
}


function _hex(h) {
  const x = h.replace('#', '');
  return [parseInt(x.slice(0, 2), 16), parseInt(x.slice(2, 4), 16), parseInt(x.slice(4, 6), 16)];
}


function _fmt(n) {
  return n == null ? '—' : n.toFixed(1).replace('.', ',');
}


function _fmtDataCurta(iso) {
  if (!iso) return '';
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}` : iso;
}
