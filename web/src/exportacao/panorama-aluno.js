// Panorama do aluno — monta um nó HTML completo com todas as informações
// relevantes do aluno num único layout printer-friendly. Usado tanto para
// exportação PDF (via window.print + CSS de print) quanto para PNG (via
// SVG + canvas).

import { el, fmtNota } from '../dom.js';

const PERFIL_LABEL = { ancora: 'Âncora', misterio: 'Mistério', regular: 'Regular' };
const TENDENCIA_LABEL = { subindo: '↑ Subindo', estavel: '→ Estável', caindo: '↓ Caindo' };
const ZONA_LABEL = { top: 'Zona Top', cinzenta: 'Zona Cinzenta', risco: 'Zona de Risco' };
const FASE_LABEL = { fase_1: 'F1', fase_2: 'F2' };


/**
 * Monta o painel do panorama (DOM node já populado).
 *
 * @param {object} dados
 * @param {object} dados.aluno
 * @param {object} dados.turma
 * @param {object} dados.sede
 * @param {Array}  dados.simuladosDoAluno  — simulados que o aluno fez (com ciclo + fase + matéria)
 * @param {Map}    dados.notasPorSimulado  — Map<simuladoId, nota>
 * @param {object} dados.heat              — payload de /alunos/{id}/heatmap (com ciclo info)
 * @param {Array}  dados.similares        — perfis similares
 */
export function montarPanorama({ aluno, turma, sede, simuladosDoAluno, notasPorSimulado, heat, similares }) {
  const alvos = aluno.vestibularesAlvo?.length ? aluno.vestibularesAlvo.join(', ') : '—';
  const hoje = new Date().toLocaleDateString('pt-BR');

  // KPIs derivados
  const notas = [...notasPorSimulado.values()].filter((n) => n != null);
  const totalNotas = notas.length;
  const media = totalNotas ? notas.reduce((a, b) => a + b, 0) / totalNotas : null;
  const ultimas5 = [...simuladosDoAluno]
    .filter((s) => notasPorSimulado.get(s.id) != null)
    .sort((a, b) => (b.dataAplicacao || '').localeCompare(a.dataAplicacao || ''))
    .slice(0, 5)
    .map((s) => ({
      data: s.dataAplicacao,
      simulado: s.nome,
      materia: s.materia?.nome || '—',
      fase: s.tipo,
      cicloOrdem: s.cicloOrdem,
      nota: notasPorSimulado.get(s.id),
      mediaTurma: s.media,
    }));

  // Resumo por matéria
  const porMateria = _resumoPorMateria(simuladosDoAluno, notasPorSimulado);

  return el('div', { class: 'panorama' }, [
    _header(aluno, turma, sede, alvos, hoje),
    _classificacoes(aluno),
    _kpisPrincipais(media, aluno.mediaRecente ?? media, totalNotas, simuladosDoAluno.length),
    _heatmapCompacto(heat),
    _tabelaPorMateria(porMateria),
    _ultimosSimulados(ultimas5),
    _perfisSimilares(similares),
    _footer(),
  ]);
}


// ─── Seções ───────────────────────────────────────────────────────────────


function _header(aluno, turma, sede, alvos, hoje) {
  return el('div', { class: 'panorama__header' }, [
    el('div', { class: 'panorama__header-info' }, [
      el('h1', { class: 'panorama__nome' }, [aluno.nome]),
      el('p', { class: 'panorama__meta' }, [
        `Matrícula ${aluno.matricula || aluno.id} · ${turma?.nome ?? '—'} · ${sede?.nome ?? '—'}`,
      ]),
      el('p', { class: 'panorama__meta' }, [
        `Vestibulares-alvo: ${alvos}`,
      ]),
    ]),
    el('div', { class: 'panorama__header-marca' }, [
      el('div', { class: 'panorama__marca-titulo' }, ['Colégio Ari de Sá']),
      el('div', { class: 'panorama__marca-sub' }, [`Panorama emitido em ${hoje}`]),
    ]),
  ]);
}


function _classificacoes(aluno) {
  return el('div', { class: 'panorama__bloco' }, [
    el('h2', { class: 'panorama__h' }, ['Classificações atuais']),
    el('div', { class: 'panorama__tags' }, [
      el('span', { class: 'panorama__tag tone-navy' }, [
        'Perfil: ', PERFIL_LABEL[aluno.perfil] || aluno.perfil,
      ]),
      el('span', { class: `panorama__tag ${_toneTendencia(aluno.tendencia)}` }, [
        'Tendência: ', TENDENCIA_LABEL[aluno.tendencia] || aluno.tendencia,
      ]),
      el('span', { class: `panorama__tag ${_toneZona(aluno.zona)}` }, [
        ZONA_LABEL[aluno.zona] || aluno.zona,
      ]),
    ]),
  ]);
}


function _kpisPrincipais(media, mediaRecente, nNotas, totalSim) {
  return el('div', { class: 'panorama__bloco' }, [
    el('h2', { class: 'panorama__h' }, ['Indicadores gerais']),
    el('div', { class: 'panorama__kpis' }, [
      _kpiCard('Média geral', fmtNota(media)),
      _kpiCard('Média recente', fmtNota(mediaRecente)),
      _kpiCard('Notas no histórico', String(nNotas)),
      _kpiCard('Simulados realizados', String(totalSim)),
    ]),
  ]);
}


function _heatmapCompacto(heat) {
  if (!heat || !heat.materias?.length || !heat.simulados?.length) {
    return el('div', { class: 'panorama__bloco' }, [
      el('h2', { class: 'panorama__h' }, ['Heatmap matérias × simulados']),
      el('p', { class: 'panorama__vazio' }, ['Sem dados suficientes.']),
    ]);
  }

  const indice = new Map();
  for (const c of heat.celulas || []) {
    indice.set(`${c.materia}|${c.simuladoId}`, c.pontuacao);
  }

  return el('div', { class: 'panorama__bloco' }, [
    el('h2', { class: 'panorama__h' }, ['Heatmap matérias × simulados']),
    el('p', { class: 'panorama__legenda' }, [
      'Verde = nota alta · vermelho = nota baixa. Agrupado por ciclo (bandas alternadas) e separado por fase.',
    ]),
    el('table', { class: 'panorama__heatmap' }, [
      el('thead', {}, _headersHeatmap(heat.simulados)),
      el('tbody', {}, heat.materias.map((m) =>
        el('tr', {}, [
          el('th', { class: 'panorama__heatmap-mat' }, [m]),
          ...heat.simulados.map((s) => {
            const v = indice.get(`${m}|${s.id}`);
            if (v == null) {
              return el('td', { class: 'panorama__heatmap-cel vazio' }, ['']);
            }
            const cor = _corPorNota(v, 10);
            return el('td', {
              class: 'panorama__heatmap-cel',
              style: `background:${cor.fundo}; color:${cor.texto};`,
            }, [_fmt(v)]);
          }),
        ])
      )),
    ]),
  ]);
}


function _headersHeatmap(simulados) {
  // Reusa a lógica de agrupamento do heatmap.js (versão simplificada inline).
  const grupos = [];
  let cur = null;
  let alterna = 'A';
  for (const s of simulados) {
    const cId = s.cicloId || `_sem_${s.fase || ''}`;
    if (!cur || cur.cicloId !== cId) {
      cur = { ...s, cicloId: s.cicloId, faixa: alterna, fases: [] };
      alterna = alterna === 'A' ? 'B' : 'A';
      grupos.push(cur);
    }
    const fAtual = cur.fases[cur.fases.length - 1];
    if (!fAtual || fAtual.fase !== s.fase) {
      cur.fases.push({ fase: s.fase, simulados: [s] });
    } else {
      fAtual.simulados.push(s);
    }
  }

  return [
    el('tr', {}, [
      el('th', {}, ['']),
      ...grupos.map((g) => {
        const total = g.fases.reduce((acc, f) => acc + f.simulados.length, 0);
        return el('th', {
          class: `panorama__heatmap-ciclo faixa-${g.faixa.toLowerCase()}`,
          colspan: String(total),
        }, [g.cicloOrdem != null ? `C${g.cicloOrdem}` : '—']);
      }),
    ]),
    el('tr', {}, [
      el('th', {}, ['']),
      ...grupos.flatMap((g) => g.fases.map((f) =>
        el('th', {
          class: `panorama__heatmap-fase faixa-${g.faixa.toLowerCase()}`,
          colspan: String(f.simulados.length),
        }, [FASE_LABEL[f.fase] || '—'])
      )),
    ]),
    el('tr', {}, [
      el('th', {}, ['']),
      ...grupos.flatMap((g) => g.fases.flatMap((f) => f.simulados.map((s) =>
        el('th', {
          class: `panorama__heatmap-pn faixa-${g.faixa.toLowerCase()}`,
        }, [s.rotulo || s.nome || '—'])
      ))),
    ]),
  ];
}


function _resumoPorMateria(simulados, notasPorSimulado) {
  const acumulador = new Map();
  for (const s of simulados) {
    const codigo = s.materia?.codigo;
    if (!codigo) continue;
    const nota = notasPorSimulado.get(s.id);
    if (nota == null) continue;
    if (!acumulador.has(codigo)) {
      acumulador.set(codigo, {
        nome: s.materia.nome,
        notas: [],
      });
    }
    acumulador.get(codigo).notas.push(nota);
  }
  return [...acumulador.values()]
    .map((m) => {
      const n = m.notas.length;
      const media = n ? m.notas.reduce((a, b) => a + b, 0) / n : null;
      const min = n ? Math.min(...m.notas) : null;
      const max = n ? Math.max(...m.notas) : null;
      return { nome: m.nome, n, media, min, max };
    })
    .sort((a, b) => a.nome.localeCompare(b.nome));
}


function _tabelaPorMateria(porMateria) {
  if (porMateria.length === 0) return el('div', {}, []);
  return el('div', { class: 'panorama__bloco' }, [
    el('h2', { class: 'panorama__h' }, ['Desempenho por matéria']),
    el('table', { class: 'panorama__tabela' }, [
      el('thead', {}, [
        el('tr', {}, [
          el('th', {}, ['Matéria']),
          el('th', {}, ['Notas']),
          el('th', {}, ['Média']),
          el('th', {}, ['Mínima']),
          el('th', {}, ['Máxima']),
        ]),
      ]),
      el('tbody', {}, porMateria.map((m) =>
        el('tr', {}, [
          el('td', {}, [m.nome]),
          el('td', {}, [String(m.n)]),
          el('td', {}, [fmtNota(m.media)]),
          el('td', {}, [fmtNota(m.min)]),
          el('td', {}, [fmtNota(m.max)]),
        ])
      )),
    ]),
  ]);
}


function _ultimosSimulados(ultimas) {
  if (ultimas.length === 0) return el('div', {}, []);
  return el('div', { class: 'panorama__bloco' }, [
    el('h2', { class: 'panorama__h' }, ['Últimos simulados']),
    el('table', { class: 'panorama__tabela' }, [
      el('thead', {}, [
        el('tr', {}, [
          el('th', {}, ['Data']),
          el('th', {}, ['Simulado']),
          el('th', {}, ['Matéria']),
          el('th', {}, ['Fase']),
          el('th', {}, ['Nota']),
          el('th', {}, ['Média turma']),
        ]),
      ]),
      el('tbody', {}, ultimas.map((u) =>
        el('tr', {}, [
          el('td', {}, [_fmtData(u.data)]),
          el('td', {}, [u.simulado]),
          el('td', {}, [u.materia]),
          el('td', {}, [FASE_LABEL[u.fase] || '—']),
          el('td', {}, [fmtNota(u.nota)]),
          el('td', {}, [fmtNota(u.mediaTurma)]),
        ])
      )),
    ]),
  ]);
}


function _perfisSimilares(similares) {
  if (!similares || similares.length === 0) return el('div', {}, []);
  return el('div', { class: 'panorama__bloco' }, [
    el('h2', { class: 'panorama__h' }, ['Perfis semelhantes (kNN)']),
    el('p', { class: 'panorama__legenda' }, [
      'Alunos com vetor de features (média por matéria, desvio, tendência) mais próximo. Distância em escala 0–10 (menor = mais parecido).',
    ]),
    el('table', { class: 'panorama__tabela' }, [
      el('thead', {}, [
        el('tr', {}, [
          el('th', {}, ['Aluno']),
          el('th', {}, ['Distância']),
          el('th', {}, ['Perfil']),
          el('th', {}, ['Tendência']),
          el('th', {}, ['Zona']),
          el('th', {}, ['Média']),
        ]),
      ]),
      el('tbody', {}, similares.slice(0, 5).map((s) =>
        el('tr', {}, [
          el('td', {}, [s.nome || '—']),
          el('td', {}, [(s.distancia ?? 0).toFixed(2).replace('.', ',')]),
          el('td', {}, [PERFIL_LABEL[s.perfil] || s.perfil || '—']),
          el('td', {}, [TENDENCIA_LABEL[s.tendencia] || s.tendencia || '—']),
          el('td', {}, [ZONA_LABEL[s.zona] || s.zona || '—']),
          el('td', {}, [fmtNota(s.media)]),
        ])
      )),
    ]),
  ]);
}


function _footer() {
  return el('div', { class: 'panorama__footer' }, [
    'Documento gerado automaticamente pelo SAS (Sistema de Análise de Simulados).',
  ]);
}


// ─── Helpers ──────────────────────────────────────────────────────────────


function _kpiCard(rotulo, valor) {
  return el('div', { class: 'panorama__kpi' }, [
    el('div', { class: 'panorama__kpi-rotulo' }, [rotulo]),
    el('div', { class: 'panorama__kpi-valor' }, [valor]),
  ]);
}


function _toneZona(z) {
  return ({ top: 'tone-verde', cinzenta: 'tone-ambar', risco: 'tone-vermelho' })[z] || '';
}


function _toneTendencia(t) {
  return ({ subindo: 'tone-verde', estavel: 'tone-navy', caindo: 'tone-vermelho' })[t] || '';
}


function _corPorNota(v, max) {
  const ratio = Math.max(0, Math.min(1, v / max));
  if (ratio < 0.5) return { fundo: _mistura('#d9354a', '#e89b2a', ratio / 0.5), texto: '#fff' };
  return { fundo: _mistura('#e89b2a', '#2e8c5a', (ratio - 0.5) / 0.5), texto: '#fff' };
}


function _mistura(hexA, hexB, t) {
  const a = _hex(hexA);
  const b = _hex(hexB);
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * t)},${Math.round(a[1] + (b[1] - a[1]) * t)},${Math.round(a[2] + (b[2] - a[2]) * t)})`;
}


function _hex(h) {
  const x = h.replace('#', '');
  return [parseInt(x.slice(0, 2), 16), parseInt(x.slice(2, 4), 16), parseInt(x.slice(4, 6), 16)];
}


function _fmt(n) {
  return n == null ? '—' : n.toFixed(1).replace('.', ',');
}


function _fmtData(iso) {
  if (!iso) return '—';
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1].slice(2)}` : iso;
}
