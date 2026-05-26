// Lista de alunos. Ver 04-screens.md (4.2).

import { getApiClient } from '../services/api.js';
import { el, fmtNota } from '../dom.js';
import { sparkline } from '../components/ui/sparkline.js';

const PERFIL_LABEL = { ancora: 'Âncora', misterio: 'Mistério', regular: 'Regular' };
const TENDENCIA_LABEL = { subindo: '↑ Subindo', estavel: '→ Estável', caindo: '↓ Caindo' };
const ZONA_LABEL = { top: 'Top', cinzenta: 'Cinzenta', risco: 'Risco' };
const ZONA_TONE = { top: 'tone-verde', cinzenta: 'tone-ambar', risco: 'tone-vermelho' };
const TENDENCIA_TONE = { subindo: 'tone-verde', estavel: 'tone-navy', caindo: 'tone-vermelho' };

export async function renderAlunos({ recorte } = {}) {
  const api = getApiClient();
  const alunos = await api.listarAlunos({ recorte });
  const turmas = await api.listarTurmas();
  const sedes = await api.listarSedes();

  const turmaById = Object.fromEntries(turmas.map((t) => [t.id, t]));
  const sedeById = Object.fromEntries(sedes.map((s) => [s.id, s]));

  return el('section', { class: 'card' }, [
    el('div', { class: 'screen-header' }, [
      el('div', { class: 'screen-breadcrumb' }, ['Alunos']),
      el('h1', { class: 'screen-title' }, ['Alunos da turma ITM']),
      el('p', { class: 'screen-subtitle' }, [
        `${alunos.length} alunos${recorte ? ` · recorte: ${recorte}` : ''}`,
      ]),
    ]),
    alunos.length === 0
      ? el('div', { class: 'empty-state' }, [
          'Nenhum aluno atende a esses critérios.',
          el('div', { class: 'empty-state__hint' }, ['Tente remover algum filtro.']),
        ])
      : el('div', { class: 'section' }, [
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
            el('tbody', {}, alunos.map((a) =>
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
          ]),
        ]),
  ]);
}
