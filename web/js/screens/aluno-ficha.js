// Ficha individual de aluno. Classificações, evolução por ciclo (gráfico com
// filtros e tooltip), histórico no mesmo layout da aba Simulados (com colunas
// "Sua nota" e "Δ vs média"), heatmap matérias × simulados, perfis similares
// e exportação (PNG/CSV/PDF).

import { getApiClient } from '../services/api.js';
import { el, clear, fmtNota } from '../dom.js';
import { heatmap } from '../components/ui/heatmap.js';
import { kpi } from '../components/ui/kpi.js';
import { linhaEvolucao } from '../components/ui/linha-evolucao.js';
import { simFiltros } from '../components/sim-filtros.js';
import {
  aplicarFiltros,
  montarOpcoes,
  contarPorChip,
} from '../components/sim-filtros-logica.js';
import { tabelaSimulados, rotuloCiclo } from '../components/tabela-simulados.js';
import {
  exportarPNGGrafico,
  exportarCSVHistorico,
  exportarPDFFicha,
  exportarPanoramaPDF,
  exportarPanoramaPNG,
} from '../services/exportar-aluno.js';

const PERFIL_LABEL = { ancora: 'Âncora', misterio: 'Mistério', regular: 'Regular' };
const TENDENCIA_LABEL = { subindo: '↑ Subindo', estavel: '→ Estável', caindo: '↓ Caindo' };
const ZONA_LABEL = { top: 'Zona Top', cinzenta: 'Zona Cinzenta', risco: 'Zona de Risco' };
const ZONA_TONE = { top: 'tone-verde', cinzenta: 'tone-ambar', risco: 'tone-vermelho' };
const TENDENCIA_TONE = { subindo: 'tone-verde', estavel: 'tone-navy', caindo: 'tone-vermelho' };

// Corte adaptativo: Inglês na Fase 1 do ITA é eliminatório com corte 5;
// nas demais matérias o corte de avaliação é 4. Quando o filtro recorta
// exatamente para esse caso, mostramos o corte correspondente.
function decidirCorte(estado) {
  const soIngles = estado.materias.size === 1 && estado.materias.has('ingles');
  const soITA = estado.vestibulares.size === 1 && estado.vestibulares.has('ITA');
  const soF1 = estado.fases.size === 1 && estado.fases.has('fase_1');
  if (soIngles && soITA && soF1) {
    return { valor: 5, rotulo: 'corte 5 (eliminatório)' };
  }
  return { valor: 4, rotulo: 'corte 4' };
}

// Constrói as séries pro gráfico a partir dos simulados filtrados + notas do
// aluno. Quando há matéria selecionada, gera 1 linha por matéria; senão,
// gera 1 linha agregada (média do aluno por ciclo) — assim o usuário decide
// o nível de detalhe via filtros.
function montarSeries({ simuladosFiltrados, notasPorSimulado, estado }) {
  const visiveis = simuladosFiltrados.filter((s) => notasPorSimulado.has(s.id));

  if (estado.materias.size > 0) {
    // Uma série por matéria selecionada.
    const porMateria = new Map();
    for (const s of visiveis) {
      const codigo = s.materia?.codigo;
      if (!codigo) continue;
      if (!porMateria.has(codigo)) {
        porMateria.set(codigo, { nome: s.materia.nome, pontos: [] });
      }
      const nota = notasPorSimulado.get(s.id);
      porMateria.get(codigo).pontos.push({
        cicloOrdem: s.cicloOrdem,
        vestibularAlvo: s.vestibularAlvo,
        nota,
        mediaTurma: s.media,
        simulado: s.nome,
        simuladoId: s.id,
        dataAplicacao: s.dataAplicacao,
        tipo: s.tipo,
        materia: s.materia.nome,
        abandonoProvavel: nota === 0,
      });
    }
    return [...porMateria.values()].sort((a, b) => a.nome.localeCompare(b.nome));
  }

  // Sem filtro de matéria: agregamos por ciclo (média das notas do aluno
  // naquele ciclo) — fica uma linha única.
  const porCiclo = new Map();
  for (const s of visiveis) {
    if (s.cicloOrdem == null) continue;
    const nota = notasPorSimulado.get(s.id);
    if (nota == null) continue;
    if (!porCiclo.has(s.cicloOrdem)) {
      porCiclo.set(s.cicloOrdem, {
        cicloOrdem: s.cicloOrdem,
        vestibularAlvo: s.vestibularAlvo,
        notas: [],
        medias: [],
        simulados: [],
        datas: [],
        tipos: new Set(),
      });
    }
    const ag = porCiclo.get(s.cicloOrdem);
    ag.notas.push(nota);
    if (s.media != null) ag.medias.push(s.media);
    ag.simulados.push(s.rotuloCurto || s.nome);
    ag.datas.push(s.dataAplicacao);
    if (s.tipo) ag.tipos.add(s.tipo);
  }

  const pontos = [...porCiclo.values()].map((ag) => {
    const media = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
    return {
      cicloOrdem: ag.cicloOrdem,
      vestibularAlvo: ag.vestibularAlvo,
      nota: media(ag.notas),
      mediaTurma: ag.medias.length ? media(ag.medias) : null,
      simulado: `${ag.simulados.length} simulado(s) do ciclo`,
      simuladoId: null,
      dataAplicacao: ag.datas.sort()[0],
      tipo: ag.tipos.size === 1 ? [...ag.tipos][0] : null,
      materia: 'Média do aluno',
      abandonoProvavel: false,
    };
  });
  return [{ nome: 'Média do aluno por ciclo', pontos }];
}

function botaoExportar({ onPanoramaPDF, onPanoramaPNG, onPNG, onCSV, onPDF }) {
  let aberto = false;
  const lista = el('div', { class: 'export-menu__lista', style: 'display:none;' }, [
    el('div', { class: 'export-menu__secao' }, ['Panorama do aluno']),
    el('button', {
      class: 'export-menu__item',
      onclick: () => { onPanoramaPDF(); fechar(); },
    }, [
      el('span', {}, ['PDF — completo']),
      el('span', { class: 'export-menu__item-dica' }, ['Identificação + classificações + heatmap + tabelas']),
    ]),
    el('button', {
      class: 'export-menu__item',
      onclick: () => { onPanoramaPNG(); fechar(); },
    }, [
      el('span', {}, ['PNG — imagem do panorama']),
      el('span', { class: 'export-menu__item-dica' }, ['Snapshot único — bom pra compartilhar']),
    ]),

    el('div', { class: 'export-menu__secao' }, ['Componentes específicos']),
    el('button', {
      class: 'export-menu__item',
      onclick: () => { onPDF(); fechar(); },
    }, [
      el('span', {}, ['PDF da ficha atual']),
      el('span', { class: 'export-menu__item-dica' }, ['Imprime a página inteira com os filtros aplicados']),
    ]),
    el('button', {
      class: 'export-menu__item',
      onclick: () => { onCSV(); fechar(); },
    }, [
      el('span', {}, ['CSV do histórico']),
      el('span', { class: 'export-menu__item-dica' }, ['Tabela filtrada pra Excel']),
    ]),
    el('button', {
      class: 'export-menu__item',
      onclick: () => { onPNG(); fechar(); },
    }, [
      el('span', {}, ['PNG do gráfico']),
      el('span', { class: 'export-menu__item-dica' }, ['Só o gráfico de evolução']),
    ]),
  ]);

  function fechar() {
    aberto = false;
    lista.style.display = 'none';
  }

  function alternar(ev) {
    ev.stopPropagation();
    aberto = !aberto;
    lista.style.display = aberto ? 'flex' : 'none';
  }

  document.addEventListener('click', fechar);

  return el('div', { class: 'export-menu aluno-ficha__nao-imprimir' }, [
    el('button', { class: 'export-menu__botao', onclick: alternar }, [
      'Exportar',
      el('span', { class: 'export-menu__seta' }, ['▾']),
    ]),
    lista,
  ]);
}

export async function renderAlunoFicha({ id }) {
  const api = getApiClient();
  const aluno = await api.obterAluno(id);

  if (!aluno) {
    return el('section', { class: 'card' }, [
      el('div', { class: 'empty-state' }, [
        `Aluno ${id} não encontrado.`,
        el('div', { class: 'empty-state__hint' }, [el('a', { href: '#/alunos' }, ['← Voltar para a lista'])]),
      ]),
    ]);
  }

  const [turmas, sedes, trajetoria, heat, similares, todosSimulados] = await Promise.all([
    api.listarTurmas(),
    api.listarSedes(),
    api.trajetoriaAluno(id).catch(() => []),
    api.heatmapAluno(id).catch(() => null),
    api.alunosSimilares(id).catch(() => []),
    api.listarSimulados().catch(() => []),
  ]);

  const turma = turmas.find((t) => t.id === aluno.turmaId);
  const sede = sedes.find((s) => s.id === aluno.sedeId);
  const alvos = aluno.vestibularesAlvo.length > 0 ? aluno.vestibularesAlvo.join(', ') : '—';

  // Cruzamento: mapa simuladoId → nota do aluno.
  const notasPorSimulado = new Map();
  for (const n of trajetoria) {
    if (n.simuladoId != null) notasPorSimulado.set(n.simuladoId, n.pontuacao);
  }

  // Universo: só simulados que o aluno fez. Os filtros operam sobre esse
  // universo, não sobre todos os simulados existentes.
  const simuladosDoAluno = todosSimulados.filter((s) => notasPorSimulado.has(s.id));
  const opcoesDisponiveis = montarOpcoes(simuladosDoAluno);

  const estado = {
    ciclos: new Set(),
    materias: new Set(),
    fases: new Set(),
    vestibulares: new Set(),
    datas: new Set(),
  };

  const containerFiltros = el('div', {}, []);
  const containerGrafico = el('div', {}, []);
  const containerTabela = el('div', { class: 'section' }, []);
  const subtituloEvol = el('div', { class: 'section__subtitle' }, []);
  const subtituloHist = el('div', { class: 'section__subtitle' }, []);

  function rerender() {
    const filtrados = aplicarFiltros(simuladosDoAluno, estado);
    const contagens = contarPorChip(simuladosDoAluno, estado);

    // Filtros
    clear(containerFiltros);
    containerFiltros.appendChild(simFiltros({
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

    // Gráfico
    const series = montarSeries({ simuladosFiltrados: filtrados, notasPorSimulado, estado });
    const ciclosOrdens = [...new Set(filtrados.map((s) => s.cicloOrdem).filter((o) => o != null))].sort((a, b) => a - b);
    const vestPorOrdem = new Map();
    for (const s of filtrados) {
      if (s.cicloOrdem != null && !vestPorOrdem.has(s.cicloOrdem)) {
        vestPorOrdem.set(s.cicloOrdem, s.vestibularAlvo);
      }
    }
    const ciclosEixo = ciclosOrdens.map((ordem) => ({
      ordem,
      label: rotuloCiclo(ordem, vestPorOrdem.get(ordem)),
    }));
    const corte = decidirCorte(estado);

    clear(containerGrafico);
    containerGrafico.appendChild(linhaEvolucao({
      series,
      ciclosEixo,
      corte: corte.valor,
      corteRotulo: corte.rotulo,
    }));

    clear(subtituloEvol);
    const totalPontos = series.reduce((acc, s) => acc + s.pontos.length, 0);
    subtituloEvol.appendChild(document.createTextNode(
      estado.materias.size > 0
        ? `${series.length} matéria(s), ${totalPontos} ponto(s) no gráfico — passe o mouse pra detalhes.`
        : `Linha agregada: média do aluno por ciclo. Filtre por matéria pra ver linhas separadas.`
    ));

    // Histórico
    clear(containerTabela);
    containerTabela.appendChild(tabelaSimulados({
      simulados: filtrados,
      notasAluno: notasPorSimulado,
      compacto: true,
    }));

    clear(subtituloHist);
    subtituloHist.appendChild(document.createTextNode(
      `${filtrados.length} de ${simuladosDoAluno.length} simulados feitos pelo aluno`
    ));
  }

  rerender();

  // Helpers de exportação — acessam o estado atual e o SVG ao vivo do gráfico.
  function exportarPNG() {
    const svg = containerGrafico.querySelector('svg');
    exportarPNGGrafico(svg, aluno);
  }
  function exportarCSV() {
    const filtrados = aplicarFiltros(simuladosDoAluno, estado);
    exportarCSVHistorico(filtrados, notasPorSimulado, aluno);
  }
  function dadosPanorama() {
    // Snapshot completo (sem aplicar filtros) — o panorama mostra o histórico
    // total do aluno, não a visão filtrada da tela.
    return {
      aluno,
      turma,
      sede,
      simuladosDoAluno,
      notasPorSimulado,
      heat,
      similares,
    };
  }
  function exportarPanoramaPDFFn() {
    exportarPanoramaPDF(dadosPanorama());
  }
  function exportarPanoramaPNGFn() {
    exportarPanoramaPNG(dadosPanorama()).catch((err) => {
      console.error('erro ao exportar panorama PNG', err);
      alert('Não consegui gerar o PNG do panorama. Tente o PDF, ou veja o console pra detalhes.');
    });
  }

  return el('div', { class: 'screen-stack' }, [
    el('section', { class: 'card' }, [
      el('div', { class: 'aluno-ficha__header' }, [
        el('div', { class: 'aluno-ficha__header-info' }, [
          el('div', { class: 'screen-breadcrumb' }, [
            el('a', { href: '#/alunos' }, ['Alunos']),
            ' / ',
            aluno.id,
          ]),
          el('h1', { class: 'screen-title' }, [aluno.nome]),
          el('p', { class: 'screen-subtitle' }, [
            `${turma?.nome ?? '—'} · ${sede?.nome ?? '—'} · alvos: ${alvos}`,
          ]),
        ]),
        botaoExportar({
          onPanoramaPDF: exportarPanoramaPDFFn,
          onPanoramaPNG: exportarPanoramaPNGFn,
          onPNG: exportarPNG,
          onCSV: exportarCSV,
          onPDF: exportarPDFFicha,
        }),
      ]),
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Classificações']),
        el('div', { style: 'display: flex; gap: 8px;' }, [
          el('span', { class: 'tag tone-navy' }, [PERFIL_LABEL[aluno.perfil] || aluno.perfil]),
          el('span', { class: `tag ${TENDENCIA_TONE[aluno.tendencia] || ''}` }, [TENDENCIA_LABEL[aluno.tendencia] || aluno.tendencia]),
          el('span', { class: `tag ${ZONA_TONE[aluno.zona] || ''}` }, [ZONA_LABEL[aluno.zona] || aluno.zona]),
        ]),
      ]),
      containerFiltros,
    ]),

    el('section', { class: 'card' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Evolução do aluno']),
        subtituloEvol,
        containerGrafico,
      ]),
    ]),

    el('section', { class: 'card' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Histórico de simulados']),
        subtituloHist,
        containerTabela,
      ]),
    ]),

    el('section', { class: 'card aluno-ficha__nao-imprimir' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Heatmap matérias × simulados']),
        el('div', { class: 'section__subtitle' }, ['Cores: verde = nota alta · vermelho = nota baixa. Cobre todo o histórico do aluno (independente dos filtros acima).']),
        heatmap(heat, { notaMaxima: 10 }),
      ]),
    ]),

    el('section', { class: 'card aluno-ficha__nao-imprimir' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Perfis semelhantes']),
        el('div', { class: 'section__subtitle' }, [
          `kNN por vetor de features (média por matéria + desvio + tendência). ${similares.length} resultados.`,
        ]),
        similares.length === 0
          ? el('p', { class: 'section__subtitle' }, ['Sem similares — aluno ainda não tem features suficientes.'])
          : el('table', { class: 'tabela-similares' }, [
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
              el('tbody', {}, similares.map((s) =>
                el('tr', { onclick: () => { window.location.hash = `#/alunos/${s.alunoId}`; } }, [
                  el('td', {}, [s.nome]),
                  el('td', {}, [s.distancia.toFixed(2).replace('.', ',')]),
                  el('td', {}, [s.perfil ? (PERFIL_LABEL[s.perfil] || s.perfil) : '—']),
                  el('td', {}, [s.tendencia
                    ? el('span', { class: `tag ${TENDENCIA_TONE[s.tendencia] || ''}` }, [TENDENCIA_LABEL[s.tendencia] || s.tendencia])
                    : '—']),
                  el('td', {}, [s.zona ? el('span', { class: `tag ${ZONA_TONE[s.zona] || ''}` }, [ZONA_LABEL[s.zona] || s.zona]) : '—']),
                  el('td', {}, [fmtNota(s.media)]),
                ])
              )),
            ]),
      ]),
    ]),

    el('section', { class: 'card aluno-ficha__nao-imprimir' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Métricas internas']),
        el('div', { class: 'kpi-grid' }, [
          kpi('Média recente', fmtNota(aluno.media)),
          kpi('Notas no histórico', String(trajetoria.length)),
          kpi('Janela', String(aluno.sparkline?.length || 0)),
        ]),
      ]),
    ]),
  ]);
}
