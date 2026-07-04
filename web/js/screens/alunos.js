// Lista de alunos com filtros por turma e sede na sidebar.

import { getApiClient } from '../services/api.js';
import { el, clear, fmtNota } from '../dom.js';
import { sparkline } from '../components/ui/sparkline.js';

const PERFIL_LABEL = { ancora: 'Âncora', misterio: 'Mistério', regular: 'Regular' };
const TENDENCIA_LABEL = { subindo: '↑ Subindo', estavel: '→ Estável', caindo: '↓ Caindo' };
const ZONA_LABEL = { top: 'Top', cinzenta: 'Cinzenta', risco: 'Risco' };
const ZONA_TONE = { top: 'tone-verde', cinzenta: 'tone-ambar', risco: 'tone-vermelho' };
const TENDENCIA_TONE = { subindo: 'tone-verde', estavel: 'tone-navy', caindo: 'tone-vermelho' };

export async function renderAlunos({ sidebarEl } = {}) {
  const api = getApiClient();
  const [alunos, turmas, sedes] = await Promise.all([
    api.listarAlunos(),
    api.listarTurmas(),
    api.listarSedes(),
  ]);

  const turmaById = Object.fromEntries(turmas.map((t) => [t.id, t]));
  const sedeById = Object.fromEntries(sedes.map((s) => [s.id, s]));

  const estado = {
    turmas: new Set(),
    sedes: new Set(),
  };

  const subtitulo = el('p', { class: 'screen-subtitle' }, []);
  const containerTabela = el('div', { class: 'section' }, []);

  function rerender() {
    const filtrados = alunos.filter((a) => {
      if (estado.turmas.size && !estado.turmas.has(a.turmaId)) return false;
      if (estado.sedes.size && !estado.sedes.has(a.sedeId)) return false;
      return true;
    });

    const algumAtivo = estado.turmas.size + estado.sedes.size > 0;

    if (sidebarEl) {
      // Cross-filtering counts: each dimension ignores its own filter
      const cTurmas = new Map();
      const cSedes = new Map();
      for (const a of alunos) {
        const passaSede = estado.sedes.size === 0 || estado.sedes.has(a.sedeId);
        const passaTurma = estado.turmas.size === 0 || estado.turmas.has(a.turmaId);
        if (passaSede) cTurmas.set(a.turmaId, (cTurmas.get(a.turmaId) || 0) + 1);
        if (passaTurma) cSedes.set(a.sedeId, (cSedes.get(a.sedeId) || 0) + 1);
      }

      const chipsTurma = turmas
        .filter((t) => estado.turmas.has(t.id) || (cTurmas.get(t.id) || 0) > 0)
        .map((t) =>
          el('button', {
            class: `sim-chip${estado.turmas.has(t.id) ? ' is-active' : ''}`,
            onclick: () => {
              if (estado.turmas.has(t.id)) estado.turmas.delete(t.id);
              else estado.turmas.add(t.id);
              rerender();
            },
          }, [
            t.nome,
            el('span', { class: 'sim-chip__contagem' }, [`· ${cTurmas.get(t.id) || 0}`]),
          ])
        );

      const chipsSede = sedes
        .filter((s) => estado.sedes.has(s.id) || (cSedes.get(s.id) || 0) > 0)
        .map((s) =>
          el('button', {
            class: `sim-chip${estado.sedes.has(s.id) ? ' is-active' : ''}`,
            onclick: () => {
              if (estado.sedes.has(s.id)) estado.sedes.delete(s.id);
              else estado.sedes.add(s.id);
              rerender();
            },
          }, [
            s.nome,
            el('span', { class: 'sim-chip__contagem' }, [`· ${cSedes.get(s.id) || 0}`]),
          ])
        );

      clear(sidebarEl);
      sidebarEl.appendChild(el('div', { class: 'sidebar__label' }, ['Filtros']));
      sidebarEl.appendChild(el('div', { class: 'sim-filtros' }, [
        chipsTurma.length
          ? el('div', { class: 'sim-filtros__linha' }, [
              el('div', { class: 'sim-filtros__rotulo' }, ['Turma']),
              ...chipsTurma,
            ])
          : null,
        chipsSede.length
          ? el('div', { class: 'sim-filtros__linha' }, [
              el('div', { class: 'sim-filtros__rotulo' }, ['Sede']),
              ...chipsSede,
            ])
          : null,
        el('div', { class: 'sim-filtros__linha' }, [
          el('div', { class: 'sim-filtros__rotulo' }, ['']),
          el('button', {
            class: 'sim-filtros__reset',
            disabled: !algumAtivo,
            onclick: () => {
              estado.turmas.clear();
              estado.sedes.clear();
              rerender();
            },
          }, ['Limpar filtros']),
        ]),
      ]));
    }

    subtitulo.textContent = `${filtrados.length} alunos${algumAtivo ? ` de ${alunos.length}` : ''}`;

    clear(containerTabela);
    if (filtrados.length === 0) {
      containerTabela.appendChild(
        el('div', { class: 'empty-state' }, [
          'Nenhum aluno atende a esses critérios.',
          el('div', { class: 'empty-state__hint' }, ['Tente remover algum filtro.']),
        ])
      );
    } else {
      containerTabela.appendChild(
        el('table', { class: 'data-table' }, [
          el('thead', {}, [
            el('tr', {}, [
              el('th', {}, ['Aluno']),
              el('th', {}, ['Turma']),
              el('th', {}, ['Sede']),
              el('th', {}, ['Média']),
              el('th', {}, ['Tendência']),
              el('th', {}, ['Perfil']),
              el('th', {}, ['Zona']),
              el('th', {}, ['Trajetória']),
              el('th', {}, ['']),
            ]),
          ]),
          el('tbody', {}, filtrados.map((a) =>
            el('tr', { onclick: () => { window.location.hash = `#/alunos/${a.id}`; } }, [
              el('td', {}, [a.nome]),
              el('td', {}, [turmaById[a.turmaId]?.nome ?? '—']),
              el('td', {}, [sedeById[a.sedeId]?.nome ?? '—']),
              el('td', {}, [fmtNota(a.media)]),
              el('td', {}, [el('span', { class: `tag ${TENDENCIA_TONE[a.tendencia]}` }, [TENDENCIA_LABEL[a.tendencia]])]),
              el('td', {}, [PERFIL_LABEL[a.perfil]]),
              el('td', {}, [el('span', { class: `tag ${ZONA_TONE[a.zona]}` }, [ZONA_LABEL[a.zona]])]),
              el('td', {}, [sparkline(a.sparkline || [], { color: 'var(--color-navy)' })]),
              el('td', {}, [el('a', { href: `#/alunos/${a.id}` }, ['Ver →'])]),
            ])
          )),
        ])
      );
    }
  }

  rerender();

  return el('section', { class: 'card' }, [
    el('div', { class: 'screen-header' }, [
      el('div', { class: 'screen-breadcrumb' }, ['Alunos']),
      el('h1', { class: 'screen-title' }, ['Alunos da turma ITM']),
      subtitulo,
    ]),
    containerTabela,
  ]);
}
