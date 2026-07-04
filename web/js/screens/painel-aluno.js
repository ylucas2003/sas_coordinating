// Painel do aluno autenticado — visão pessoal de desempenho.
// Usa /me/* em vez de /alunos/{id}/*, sem exposição de outros alunos.

import { getApiClient } from '../services/api.js';
import { el, clear, fmtNota } from '../dom.js';
import { heatmap } from '../components/ui/heatmap.js';
import { linhaEvolucao } from '../components/ui/linha-evolucao.js';
import { simFiltros } from '../components/sim-filtros.js';
import {
  aplicarFiltros,
  montarOpcoes,
  contarPorChip,
} from '../components/sim-filtros-logica.js';
import { tabelaSimulados, rotuloCiclo } from '../components/tabela-simulados.js';

const PERFIL_LABEL   = { ancora: 'Âncora', misterio: 'Mistério', regular: 'Regular' };
const TENDENCIA_LABEL = { subindo: '↑ Subindo', estavel: '→ Estável', caindo: '↓ Caindo' };
const ZONA_LABEL     = { top: 'Zona Top', cinzenta: 'Zona Cinzenta', risco: 'Zona de Risco' };
const ZONA_TONE      = { top: 'tone-verde', cinzenta: 'tone-ambar', risco: 'tone-vermelho' };
const TENDENCIA_TONE = { subindo: 'tone-verde', estavel: 'tone-navy', caindo: 'tone-vermelho' };

// ─── Topbar do aluno ──────────────────────────────────────────────────────

function _svgAsterisco() {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', '20');
  svg.setAttribute('height', '20');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2.4');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('aria-hidden', 'true');
  for (const [x1, y1, x2, y2] of [[12,2,12,22],[3,7,21,17],[21,7,3,17]]) {
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    svg.appendChild(line);
  }
  return svg;
}

export function topbarAluno(nome) {
  const logoEl = el('div', { class: 'topbar__logo' });
  logoEl.appendChild(_svgAsterisco());

  return el('header', { class: 'topbar' }, [
    el('div', { class: 'topbar__brand' }, [
      logoEl,
      el('div', { class: 'topbar__brand-text' }, [
        el('span', { class: 'topbar__brand-name' }, ['SAS']),
        el('span', { class: 'topbar__brand-sub' }, ['meu painel']),
      ]),
    ]),
    el('div', { class: 'topbar__aluno-nome' }, [nome || '']),
    el('div', { class: 'topbar__actions' }, [
      el('button', {
        class: 'topbar__action',
        onclick: () => { sessionStorage.clear(); window.location.replace('./login.html'); },
      }, ['Sair']),
    ]),
  ]);
}

// ─── Séries para o gráfico (mesma lógica de aluno-ficha) ─────────────────

function _montarSeries({ simuladosFiltrados, notasPorSimulado, estado }) {
  const visiveis = simuladosFiltrados.filter((s) => notasPorSimulado.has(s.id));

  if (estado.materias.size > 0) {
    const porMateria = new Map();
    for (const s of visiveis) {
      const codigo = s.materia?.codigo;
      if (!codigo) continue;
      if (!porMateria.has(codigo)) porMateria.set(codigo, { nome: s.materia.nome, pontos: [] });
      const nota = notasPorSimulado.get(s.id);
      porMateria.get(codigo).pontos.push({
        cicloOrdem: s.cicloOrdem, vestibularAlvo: s.vestibularAlvo,
        nota, mediaTurma: s.media, simulado: s.nome, simuladoId: s.id,
        dataAplicacao: s.dataAplicacao, tipo: s.tipo, materia: s.materia.nome,
        abandonoProvavel: nota === 0,
      });
    }
    return [...porMateria.values()].sort((a, b) => a.nome.localeCompare(b.nome));
  }

  const porCiclo = new Map();
  for (const s of visiveis) {
    if (s.cicloOrdem == null) continue;
    const nota = notasPorSimulado.get(s.id);
    if (nota == null) continue;
    if (!porCiclo.has(s.cicloOrdem)) {
      porCiclo.set(s.cicloOrdem, {
        cicloOrdem: s.cicloOrdem, vestibularAlvo: s.vestibularAlvo,
        notas: [], medias: [], simulados: [], datas: [], tipos: new Set(),
      });
    }
    const ag = porCiclo.get(s.cicloOrdem);
    ag.notas.push(nota);
    if (s.media != null) ag.medias.push(s.media);
    ag.simulados.push(s.rotuloCurto || s.nome);
    ag.datas.push(s.dataAplicacao);
    if (s.tipo) ag.tipos.add(s.tipo);
  }

  const avg = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
  const pontos = [...porCiclo.values()].map((ag) => ({
    cicloOrdem: ag.cicloOrdem, vestibularAlvo: ag.vestibularAlvo,
    nota: avg(ag.notas), mediaTurma: ag.medias.length ? avg(ag.medias) : null,
    simulado: `${ag.simulados.length} simulado(s) do ciclo`, simuladoId: null,
    dataAplicacao: ag.datas.sort()[0],
    tipo: ag.tipos.size === 1 ? [...ag.tipos][0] : null,
    materia: 'Média do aluno', abandonoProvavel: false,
  }));
  return [{ nome: 'Média do aluno por ciclo', pontos }];
}

// ─── Seção: desempenho vs corte por matéria ──────────────────────────────

function _secaoCorte({ trajetoria, todosSimulados }) {
  const nomeMateria = new Map();
  for (const s of todosSimulados) {
    if (s.materia) nomeMateria.set(s.id, s.materia.nome);
  }

  const porMateria = new Map();
  for (const n of trajetoria) {
    const nome = nomeMateria.get(n.simuladoId);
    if (!nome) continue;
    if (!porMateria.has(nome)) porMateria.set(nome, []);
    porMateria.get(nome).push(n.pontuacao);
  }

  const materias = [...porMateria.entries()].sort(([a], [b]) => a.localeCompare(b, 'pt-BR'));
  if (!materias.length) {
    return el('p', { class: 'section__subtitle' }, ['Sem dados suficientes.']);
  }

  return el('table', { class: 'tabela-corte' }, [
    el('thead', {}, [
      el('tr', {}, [
        el('th', { class: 'tabela-corte__th' }, ['Matéria']),
        el('th', { class: 'tabela-corte__th tabela-corte__th--num' }, ['Minha média']),
        el('th', { class: 'tabela-corte__th tabela-corte__th--num' }, ['Simulados']),
        el('th', { class: 'tabela-corte__th tabela-corte__th--num' }, ['Corte']),
        el('th', { class: 'tabela-corte__th tabela-corte__th--num' }, ['Status']),
      ]),
    ]),
    el('tbody', {}, materias.map(([nome, notas]) => {
      const media = notas.reduce((a, b) => a + b, 0) / notas.length;
      const corte  = 4;
      const tone   = media >= 7 ? 'verde' : media >= corte ? 'ambar' : 'vermelho';
      const acima  = media >= corte;
      return el('tr', { class: 'tabela-corte__tr' }, [
        el('td', { class: 'tabela-corte__td' }, [nome]),
        el('td', { class: 'tabela-corte__td tabela-corte__td--num' }, [
          el('span', { class: `nota-badge nota-badge--${tone}` }, [fmtNota(media)]),
        ]),
        el('td', { class: 'tabela-corte__td tabela-corte__td--num' }, [String(notas.length)]),
        el('td', { class: 'tabela-corte__td tabela-corte__td--num' }, [fmtNota(corte)]),
        el('td', { class: 'tabela-corte__td tabela-corte__td--num' }, [
          el('span', { class: `tag ${acima ? 'tone-verde' : 'tone-vermelho'}` }, [
            acima ? 'Acima' : 'Abaixo',
          ]),
        ]),
      ]);
    })),
  ]);
}

// ─── Render principal ─────────────────────────────────────────────────────

export async function renderPainelAluno() {
  const api = getApiClient();

  const [aluno, trajetoria, heat, todosSimulados, turmas, sedes] = await Promise.all([
    api.obterMe(),
    api.trajetoriaMe().catch(() => []),
    api.heatmapMe().catch(() => null),
    api.listarSimulados().catch(() => []),
    api.listarTurmas().catch(() => []),
    api.listarSedes().catch(() => []),
  ]);

  if (!aluno) {
    return el('section', { class: 'card' }, [
      el('div', { class: 'empty-state' }, [
        'Não foi possível carregar seus dados. Tente recarregar a página.',
      ]),
    ]);
  }

  const turma = turmas.find((t) => t.id === aluno.turmaId);
  const sede  = sedes.find((s) => s.id === aluno.sedeId);
  const alvos = aluno.vestibularesAlvo.length > 0 ? aluno.vestibularesAlvo.join(', ') : '—';

  const notasPorSimulado = new Map();
  for (const n of trajetoria) {
    if (n.simuladoId != null) notasPorSimulado.set(n.simuladoId, n.pontuacao);
  }

  const simuladosDoAluno  = todosSimulados.filter((s) => notasPorSimulado.has(s.id));
  const opcoesDisponiveis = montarOpcoes(simuladosDoAluno);

  const estado = {
    ciclos: new Set(), materias: new Set(),
    fases: new Set(), vestibulares: new Set(), datas: new Set(),
  };

  const containerFiltros  = el('div', {}, []);
  const containerGrafico  = el('div', {}, []);
  const containerTabela   = el('div', { class: 'section' }, []);
  const subtituloEvol     = el('div', { class: 'section__subtitle' }, []);
  const subtituloHist     = el('div', { class: 'section__subtitle' }, []);

  function rerender() {
    const filtrados = aplicarFiltros(simuladosDoAluno, estado);
    const contagens = contarPorChip(simuladosDoAluno, estado);

    clear(containerFiltros);
    containerFiltros.appendChild(simFiltros({
      opcoesDisponiveis,
      estado,
      contagens,
      onToggle: (grupo, valor) => {
        const set = estado[grupo];
        if (set.has(valor)) set.delete(valor); else set.add(valor);
        rerender();
      },
      onReset: () => {
        for (const k of Object.keys(estado)) estado[k].clear();
        rerender();
      },
    }));

    const series = _montarSeries({ simuladosFiltrados: filtrados, notasPorSimulado, estado });
    const ciclosOrdens = [...new Set(
      filtrados.map((s) => s.cicloOrdem).filter((o) => o != null)
    )].sort((a, b) => a - b);
    const vestPorOrdem = new Map();
    for (const s of filtrados) {
      if (s.cicloOrdem != null && !vestPorOrdem.has(s.cicloOrdem))
        vestPorOrdem.set(s.cicloOrdem, s.vestibularAlvo);
    }
    const ciclosEixo = ciclosOrdens.map((ordem) => ({
      ordem, label: rotuloCiclo(ordem, vestPorOrdem.get(ordem)),
    }));

    clear(containerGrafico);
    containerGrafico.appendChild(linhaEvolucao({
      series, ciclosEixo, corte: 4, corteRotulo: 'corte 4',
    }));

    clear(subtituloEvol);
    const totalPontos = series.reduce((acc, s) => acc + s.pontos.length, 0);
    subtituloEvol.appendChild(document.createTextNode(
      estado.materias.size > 0
        ? `${series.length} matéria(s), ${totalPontos} ponto(s) — passe o mouse pra detalhes.`
        : 'Linha agregada: média por ciclo. Filtre por matéria pra ver linhas separadas.'
    ));

    clear(containerTabela);
    containerTabela.appendChild(tabelaSimulados({
      simulados: filtrados, notasAluno: notasPorSimulado, compacto: true,
    }));

    clear(subtituloHist);
    subtituloHist.appendChild(document.createTextNode(
      `${filtrados.length} de ${simuladosDoAluno.length} simulados`
    ));
  }

  rerender();

  return el('div', { class: 'screen-stack' }, [

    // ── Cabeçalho + classificações + filtros
    el('section', { class: 'card' }, [
      el('div', { class: 'aluno-ficha__header' }, [
        el('div', { class: 'aluno-ficha__header-info' }, [
          el('div', { class: 'screen-breadcrumb' }, ['Meu painel']),
          el('h1', { class: 'screen-title' }, [aluno.nome]),
          el('p', { class: 'screen-subtitle' }, [
            `${turma?.nome ?? '—'} · ${sede?.nome ?? '—'} · vestibulares: ${alvos}`,
          ]),
        ]),
      ]),
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Classificações']),
        el('div', { class: 'aluno-painel__tags' }, [
          el('span', { class: 'tag tone-navy' }, [PERFIL_LABEL[aluno.perfil] || aluno.perfil]),
          el('span', { class: `tag ${TENDENCIA_TONE[aluno.tendencia] || ''}` },
            [TENDENCIA_LABEL[aluno.tendencia] || aluno.tendencia]),
          el('span', { class: `tag ${ZONA_TONE[aluno.zona] || ''}` },
            [ZONA_LABEL[aluno.zona] || aluno.zona]),
          el('span', { class: 'tag tone-navy' }, [`Média: ${fmtNota(aluno.media)}`]),
          el('span', { class: 'tag tone-navy' }, [`${trajetoria.length} simulado(s)`]),
        ]),
      ]),
      containerFiltros,
    ]),

    // ── Gráfico de evolução
    el('section', { class: 'card' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Minha evolução']),
        subtituloEvol,
        containerGrafico,
      ]),
    ]),

    // ── Desempenho vs corte por matéria
    el('section', { class: 'card' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Desempenho por matéria vs corte']),
        el('div', { class: 'section__subtitle' }, [
          'Média de todas as provas feitas. Corte padrão: 4,0 (Inglês ITA F1: 5,0 eliminatório).',
        ]),
        _secaoCorte({ trajetoria, todosSimulados }),
      ]),
    ]),

    // ── Histórico de simulados
    el('section', { class: 'card' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Histórico de simulados']),
        subtituloHist,
        containerTabela,
      ]),
    ]),

    // ── Heatmap
    el('section', { class: 'card' }, [
      el('div', { class: 'section' }, [
        el('div', { class: 'section__title' }, ['Heatmap matérias × simulados']),
        el('div', { class: 'section__subtitle' }, [
          'Verde = nota alta · Vermelho = nota baixa. Cobre todo o histórico.',
        ]),
        heatmap(heat, { notaMaxima: 10 }),
      ]),
    ]),

  ]);
}
