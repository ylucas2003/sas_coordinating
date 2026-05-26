// Ficha de ciclo — single-page, sem abas/filtros de fase.
//
// Hierarquia visual:
//   1. Hero (4 KPIs principais)
//   2. Evolução temporal (F1+F2 cronológicos)
//   3. Leitura prática (insights LLM acessíveis)
//   4. Análise conjunta (ciclo todo, F1+F2 agregados por aluno)
//   5. Por matéria (cada matéria com F1 e F2 lado a lado)
//   6. Tabela de simulados
//   7. [▼ Mostrar dados estatísticos avançados]
//      ↳ KPIs detalhados (forma, quantis, dispersão) + leitura técnica

import { getApiClient } from '../services/api.js';
import { el, clear, fmtNota, fmtDelta } from '../dom.js';
import { histograma } from '../components/ui/histograma.js';
import { linhaTemporal } from '../components/ui/linha-temporal.js';
import { insightsPainel } from '../components/ui/insights-painel.js';

export async function renderCicloFicha({ id }) {
  const api = getApiClient();
  const ciclo = await api.obterCiclo(id);

  if (!ciclo) {
    return el('section', { class: 'card' }, [
      el('div', { class: 'empty-state' }, [
        `Ciclo ${id} não encontrado.`,
        el('div', { class: 'empty-state__hint' }, [
          el('a', { href: '#/ciclos' }, ['← Voltar para a lista']),
        ]),
      ]),
    ]);
  }

  const simuladosTodos = await api.listarSimulados();
  const doCiclo = simuladosTodos
    .filter((s) => ciclo.simuladoIds.includes(s.id))
    .sort((a, b) => (a.dataAplicacao || '').localeCompare(b.dataAplicacao || ''));

  const estado = {
    payload: null,
    carregando: true,
    avancadoAberto: false,
  };

  const root = el('section', { class: 'card ciclo-ficha' }, []);

  async function carregar() {
    estado.carregando = true;
    estado.payload = null;
    renderizar();
    try {
      estado.payload = await api.estatisticasCiclo(id);
    } catch (err) {
      console.error('erro ao buscar estatísticas do ciclo', err);
      estado.payload = { erro: err };
    } finally {
      estado.carregando = false;
      renderizar();
    }
  }

  function renderizar() {
    clear(root);
    root.appendChild(renderHeader(ciclo, doCiclo));

    if (estado.carregando) {
      root.appendChild(el('div', { class: 'section' }, [
        el('p', { class: 'section__subtitle' }, ['Calculando estatísticas…']),
      ]));
      return;
    }
    if (estado.payload?.erro) {
      root.appendChild(el('div', { class: 'section' }, [
        el('p', { class: 'section__subtitle' }, [
          'Erro ao calcular estatísticas. Verifique o backend e tente novamente.',
        ]),
      ]));
      return;
    }

    const p = estado.payload;
    root.appendChild(renderHero(p));
    root.appendChild(renderEvolucao(p));
    root.appendChild(renderLeituraPratica(p));
    root.appendChild(renderConjunta(p));
    root.appendChild(renderPorMateria(p));
    root.appendChild(renderTabelaSimulados(doCiclo));
    root.appendChild(renderBotaoAvancado(estado, renderizar));
    if (estado.avancadoAberto) {
      root.appendChild(renderAvancado(p));
    }
  }

  carregar();
  return root;
}


// ─── Header ───────────────────────────────────────────────────────────────


function renderHeader(ciclo, simulados) {
  return el('div', { class: 'screen-header' }, [
    el('div', { class: 'screen-breadcrumb' }, [
      el('a', { href: '#/ciclos' }, ['Ciclos']),
      ' / ',
      ciclo.id,
    ]),
    el('h1', { class: 'screen-title' }, [ciclo.nome]),
    el('p', { class: 'screen-subtitle' }, [
      ciclo.vestibularAlvo
        ? el('span', { class: 'tag tone-navy', style: 'margin-right: 8px;' }, [ciclo.vestibularAlvo])
        : null,
      `Período: ${ciclo.periodoInicio || '—'} → ${ciclo.periodoFim || '—'} · ${simulados.length} simulados`,
    ]),
  ]);
}


// ─── Hero (4 KPIs principais) ─────────────────────────────────────────────


function renderHero(payload) {
  const r = payload.resumo || {};
  const delta = r.delta || {};
  return el('div', { class: 'section ciclo-hero' }, [
    el('div', { class: 'ciclo-hero__grid' }, [
      heroCard('Média geral', fmtNota(r.media), { delta: delta.media }),
      heroCard('% aprovados', fmtPct(r.pctAprovados), { delta: delta.pctAprovados, sufixo: '%' }),
      heroCard('% zona crítica', fmtPct(r.pctZonaCritica), { sufixo: '%', toneRule: pctCriticoTone }),
      heroCard('% excelência', fmtPct(r.pctExcelencia), { delta: delta.pctExcelencia, sufixo: '%' }),
    ]),
    payload.cicloAnterior
      ? el('p', { class: 'ciclo-hero__legenda' }, [
          `Variações comparam com ${payload.cicloAnterior.nome}.`,
        ])
      : null,
  ]);
}

function heroCard(rotulo, valor, { delta, sufixo = '', toneRule = null } = {}) {
  const numero = parseFloat((valor || '0').replace(',', '.'));
  const tone = toneRule ? toneRule(numero) : '';
  return el('div', { class: 'ciclo-hero__card' }, [
    el('div', { class: 'ciclo-hero__rotulo' }, [rotulo]),
    el('div', { class: `ciclo-hero__valor ${tone}` }, [
      valor,
      sufixo ? el('span', { class: 'ciclo-hero__sufixo' }, [sufixo]) : null,
    ]),
    delta != null
      ? el('div', {
          class: `ciclo-hero__delta ${delta > 0 ? 'tone-verde' : delta < 0 ? 'tone-vermelho' : ''}`,
        }, [fmtDelta(delta), sufixo ? ` ${sufixo}` : ' vs anterior'])
      : null,
  ]);
}


// ─── Evolução temporal ────────────────────────────────────────────────────


function renderEvolucao(payload) {
  const pontos = (payload.evolucaoTemporal || []).map((p) => ({
    ...p,
    // Sublinha visualmente fase no rótulo curto.
    rotuloCurto: p.rotuloCurto ? `${p.rotuloCurto}${p.fase === 'fase_2' ? ' (F2)' : ''}` : null,
  }));
  return el('div', { class: 'section' }, [
    el('div', { class: 'section__title' }, ['Evolução temporal']),
    el('div', { class: 'section__subtitle' }, [
      'Médias dos simulados ao longo do ciclo, do mais antigo ao mais recente.',
    ]),
    linhaTemporal(pontos, {
      width: 760,
      height: 220,
      corte: { valor: 4, eliminatoria: false },
    }),
  ]);
}


// ─── Leitura prática ──────────────────────────────────────────────────────


function renderLeituraPratica(payload) {
  const bullets = payload.conjunta?.insights?.pratico;
  return el('div', { class: 'section' }, [
    insightsPainel(bullets, {
      titulo: 'Leitura do coordenador',
      legenda: 'Análise em linguagem acessível, gerada a partir dos números do ciclo.',
    }),
  ]);
}


// ─── Análise conjunta ─────────────────────────────────────────────────────


function renderConjunta(payload) {
  const c = payload.conjunta;
  if (!c || !c.stats || c.stats.n === 0) {
    return el('div', { class: 'section' }, [
      el('p', { class: 'section__subtitle' }, ['Sem dados suficientes pra análise conjunta.']),
    ]);
  }
  const stats = c.stats;
  return el('div', { class: 'section' }, [
    el('div', { class: 'section__title' }, ['Visão geral do ciclo']),
    el('div', { class: 'section__subtitle' }, [
      `Distribuição da nota média de cada aluno no ciclo todo (F1 + F2 combinados). n = ${stats.n} alunos.`,
    ]),
    el('div', { class: 'ciclo-conjunta__layout' }, [
      el('div', { class: 'ciclo-conjunta__grafico' }, [
        histograma(c.histograma, {
          width: 480,
          height: 200,
          media: stats.media,
          mediana: stats.mediana,
          corte: c.corte != null ? { valor: c.corte, eliminatoria: false } : null,
          cicloAnterior: c.anterior?.histograma || null,
          kde: true,
        }),
      ]),
      el('div', { class: 'ciclo-conjunta__numeros' }, [
        miniCard('Média', fmtNota(stats.media)),
        miniCard('Mediana', fmtNota(stats.mediana)),
        miniCard('Desvio padrão', fmtNota(stats.desvioPadrao)),
        miniCard('Alunos', String(stats.n)),
      ]),
    ]),
  ]);
}


// ─── Por matéria ──────────────────────────────────────────────────────────


function renderPorMateria(payload) {
  const recortes = payload.porMateria || [];
  if (recortes.length === 0) {
    return el('div', { class: 'section' }, [
      el('div', { class: 'section__title' }, ['Por matéria']),
      el('p', { class: 'section__subtitle' }, ['Sem simulados por matéria neste ciclo.']),
    ]);
  }

  return el('div', { class: 'section' }, [
    el('div', { class: 'section__title' }, ['Por matéria']),
    el('div', { class: 'section__subtitle' }, [
      'Cada matéria mostra Fase 1 e Fase 2 lado a lado. As linhas tracejadas verticais marcam o corte.',
    ]),
    el('div', { class: 'ciclo-materias' }, recortes.map(renderBlocoMateria)),
  ]);
}


function renderBlocoMateria(rec) {
  const eliminatoriaF1 = rec.eliminatoriaF1;
  return el('div', { class: 'ciclo-materia' }, [
    el('div', { class: 'ciclo-materia__cabecalho' }, [
      el('h3', { class: 'ciclo-materia__titulo' }, [
        rec.materia.nome,
        eliminatoriaF1
          ? el('span', { class: 'tag tone-vermelho', style: 'margin-left: 8px;' }, ['F1 ELIMINATÓRIA'])
          : null,
      ]),
      renderResumoF1F2(rec),
    ]),
    el('div', { class: 'ciclo-materia__graficos' }, [
      renderMiniHistogramaFase(rec.fase1, 'Fase 1', eliminatoriaF1 ? 5 : 4, eliminatoriaF1),
      renderMiniHistogramaFase(rec.fase2, 'Fase 2', 4, false),
    ]),
    insightsPainel(rec.insights?.pratico, {
      titulo: `Leitura — ${rec.materia.nome}`,
      legenda: '',
    }),
  ]);
}


function renderResumoF1F2(rec) {
  const f1 = rec.fase1?.stats;
  const f2 = rec.fase2?.stats;
  const delta = rec.deltaF1F2;

  return el('div', { class: 'ciclo-materia__resumo' }, [
    miniBadge('Média F1', f1 ? fmtNota(f1.media) : '—'),
    el('span', { class: 'ciclo-materia__seta' }, ['→']),
    miniBadge('Média F2', f2 ? fmtNota(f2.media) : '—', { delta: delta?.media }),
    miniBadge('Aprovados F1', f1 ? `${fmtPct(f1.pctAprovados)}%` : '—'),
    el('span', { class: 'ciclo-materia__seta' }, ['→']),
    miniBadge('Aprovados F2', f2 ? `${fmtPct(f2.pctAprovados)}%` : '—', { delta: delta?.pctAprovados, sufixo: '%' }),
  ]);
}


function renderMiniHistogramaFase(bloco, label, corteValor, eliminatoria) {
  if (!bloco || bloco.stats.n === 0) {
    return el('div', { class: 'ciclo-materia__hist-vazio' }, [
      el('div', { class: 'ciclo-materia__hist-label' }, [label]),
      el('p', { class: 'empty-state' }, [`Sem dados de ${label}.`]),
    ]);
  }
  return el('div', { class: 'ciclo-materia__hist' }, [
    el('div', { class: 'ciclo-materia__hist-label' }, [
      label,
      el('span', { class: 'ciclo-materia__hist-n' }, [`  n = ${bloco.stats.n}`]),
    ]),
    histograma(bloco.histograma, {
      width: 320,
      height: 140,
      media: bloco.stats.media,
      mediana: bloco.stats.mediana,
      corte: { valor: corteValor, eliminatoria },
    }),
  ]);
}


// ─── Tabela de simulados (mantida) ────────────────────────────────────────


function renderTabelaSimulados(simulados) {
  return el('div', { class: 'section' }, [
    el('div', { class: 'section__title' }, ['Simulados no ciclo']),
    simulados.length === 0
      ? el('p', { class: 'section__subtitle' }, ['Ciclo sem simulados associados.'])
      : el('table', { class: 'data-table' }, [
          el('thead', {}, [
            el('tr', {}, [
              el('th', {}, ['Simulado']),
              el('th', {}, ['Data']),
              el('th', {}, ['Média']),
              el('th', {}, ['Mediana']),
              el('th', {}, ['Desvio']),
              el('th', {}, ['Presentes']),
              el('th', {}, ['']),
            ]),
          ]),
          el('tbody', {}, simulados.map((s) =>
            el('tr', { onclick: () => { window.location.hash = `#/simulados/${s.id}`; } }, [
              el('td', {}, [s.nome]),
              el('td', {}, [s.dataAplicacao]),
              el('td', {}, [fmtNota(s.media)]),
              el('td', {}, [fmtNota(s.mediana)]),
              el('td', {}, [fmtNota(s.desvioPadrao)]),
              el('td', {}, [String(s.nPresentes ?? '—')]),
              el('td', {}, [el('a', { href: `#/simulados/${s.id}` }, ['Ver →'])]),
            ])
          )),
        ]),
  ]);
}


// ─── Botão de dados avançados ─────────────────────────────────────────────


function renderBotaoAvancado(estado, renderizar) {
  return el('div', { class: 'ciclo-avancado__toggle' }, [
    el('button', {
      class: `ciclo-avancado__btn ${estado.avancadoAberto ? 'is-aberto' : ''}`,
      onclick: () => {
        estado.avancadoAberto = !estado.avancadoAberto;
        renderizar();
      },
    }, [
      estado.avancadoAberto ? '▲ Esconder' : '▼ Mostrar',
      ' dados estatísticos avançados',
    ]),
  ]);
}


function renderAvancado(payload) {
  return el('div', { class: 'section ciclo-avancado' }, [
    el('div', { class: 'section__title' }, ['Dados estatísticos avançados']),
    el('div', { class: 'section__subtitle' }, [
      'Forma da distribuição, quantis e dispersão para cada recorte. Inclui leitura técnica em jargão estatístico.',
    ]),

    el('div', { class: 'ciclo-avancado__bloco' }, [
      el('h3', { class: 'ciclo-avancado__h' }, ['Visão geral do ciclo']),
      renderGridAvancado(payload.conjunta?.stats),
      insightsPainel(payload.conjunta?.insights?.tecnico, {
        titulo: 'Leitura técnica — visão geral',
        legenda: 'Análise com jargão estatístico.',
      }),
    ]),

    ...(payload.porMateria || []).flatMap((rec) => [
      el('div', { class: 'ciclo-avancado__bloco' }, [
        el('h3', { class: 'ciclo-avancado__h' }, [
          rec.materia.nome,
          rec.eliminatoriaF1
            ? el('span', { class: 'tag tone-vermelho', style: 'margin-left: 8px;' }, ['F1 ELIM.'])
            : null,
        ]),
        el('div', { class: 'ciclo-avancado__fases' }, [
          rec.fase1
            ? el('div', { class: 'ciclo-avancado__fase' }, [
                el('div', { class: 'ciclo-avancado__fase-label' }, ['Fase 1']),
                renderGridAvancado(rec.fase1.stats),
              ])
            : null,
          rec.fase2
            ? el('div', { class: 'ciclo-avancado__fase' }, [
                el('div', { class: 'ciclo-avancado__fase-label' }, ['Fase 2']),
                renderGridAvancado(rec.fase2.stats),
              ])
            : null,
        ].filter(Boolean)),
        insightsPainel(rec.insights?.tecnico, {
          titulo: `Leitura técnica — ${rec.materia.nome}`,
          legenda: '',
        }),
      ]),
    ]),
  ]);
}


function renderGridAvancado(stats) {
  if (!stats || stats.n === 0) {
    return el('p', { class: 'section__subtitle' }, ['Sem dados.']);
  }
  return el('div', { class: 'ciclo-avancado__grupos' }, [
    grupo('Dispersão', [
      miniCard('Desvio padrão', fmtNota(stats.desvioPadrao)),
      miniCard('IQR', fmtNota(stats.iqr)),
      miniCard('Amplitude', fmtNota(stats.amplitude)),
      miniCard('Moda', fmtNota(stats.moda)),
    ]),
    grupo('Quantis', [
      miniCard('P10', fmtNota(stats.p10)),
      miniCard('P25', fmtNota(stats.p25)),
      miniCard('P75', fmtNota(stats.p75)),
      miniCard('P90', fmtNota(stats.p90)),
    ]),
    grupo('Forma', [
      miniCard('Assimetria', stats.skewness?.toFixed(2).replace('.', ',') || '—', {
        tooltip: 'Skewness. Positivo: cauda à direita. |valor| > 1 = forte assimetria.',
      }),
      miniCard('Curtose', stats.curtose?.toFixed(2).replace('.', ',') || '—', {
        tooltip: 'Excesso de curtose. Positivo: caudas pesadas (outliers).',
      }),
      el('div', { class: 'mini-card' }, [
        el('div', { class: 'mini-card__rotulo' }, ['Bimodal?']),
        el('div', { class: `mini-card__valor ${stats.bimodal ? 'tone-ambar' : 'tone-navy'}` }, [
          stats.bimodal ? 'Sim' : 'Não',
        ]),
      ]),
    ]),
    grupo('Taxas', [
      miniCard('% aprovados', `${fmtPct(stats.pctAprovados)}%`),
      miniCard('% zona crítica', `${fmtPct(stats.pctZonaCritica)}%`, { toneRule: pctCriticoTone }),
      miniCard('% excelência', `${fmtPct(stats.pctExcelencia)}%`),
    ]),
  ]);
}


// ─── Helpers ──────────────────────────────────────────────────────────────


function grupo(titulo, filhos) {
  return el('div', { class: 'ciclo-avancado__grupo' }, [
    el('div', { class: 'ciclo-avancado__grupo-titulo' }, [titulo]),
    el('div', { class: 'mini-cards' }, filhos),
  ]);
}

function miniCard(rotulo, valor, { tooltip = '', toneRule = null } = {}) {
  const numero = parseFloat((valor || '0').replace(',', '.'));
  const tone = toneRule ? toneRule(numero) : '';
  return el('div', { class: 'mini-card', title: tooltip || undefined }, [
    el('div', { class: 'mini-card__rotulo' }, [rotulo]),
    el('div', { class: `mini-card__valor ${tone}` }, [valor]),
  ]);
}

function miniBadge(rotulo, valor, { delta = null, sufixo = '' } = {}) {
  return el('div', { class: 'mini-badge' }, [
    el('span', { class: 'mini-badge__rotulo' }, [rotulo]),
    el('span', { class: 'mini-badge__valor' }, [valor]),
    delta != null
      ? el('span', {
          class: `mini-badge__delta ${delta > 0 ? 'tone-verde' : delta < 0 ? 'tone-vermelho' : ''}`,
        }, [` ${fmtDelta(delta)}${sufixo ? ' ' + sufixo : ''}`])
      : null,
  ]);
}

function fmtPct(v) {
  if (v == null) return '—';
  return v.toFixed(1).replace('.', ',');
}

function pctCriticoTone(v) {
  if (v == null || isNaN(v)) return '';
  if (v >= 20) return 'tone-vermelho';
  if (v >= 10) return 'tone-ambar';
  return 'tone-verde';
}
