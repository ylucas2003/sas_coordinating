// Lógica pura dos filtros de simulado — separada da UI pra ser reusada na
// tela de Simulados e na ficha do aluno.

import { rotuloCiclo } from './tabela-simulados.js';

export function aplicarFiltros(simulados, estado) {
  return simulados.filter((s) => {
    if (estado.ciclos.size && !estado.ciclos.has(s.cicloOrdem)) return false;
    if (estado.materias.size && !estado.materias.has(s.materia?.codigo)) return false;
    if (estado.fases.size && !estado.fases.has(s.tipo)) return false;
    if (estado.vestibulares.size && !estado.vestibulares.has(s.vestibularAlvo)) return false;
    if (estado.datas && estado.datas.size && !estado.datas.has(s.dataAplicacao)) return false;
    return true;
  });
}

export function montarOpcoes(simulados) {
  const ciclosMapa = new Map();
  for (const s of simulados) {
    if (s.cicloOrdem == null) continue;
    if (!ciclosMapa.has(s.cicloOrdem)) ciclosMapa.set(s.cicloOrdem, s.vestibularAlvo);
  }
  const ciclos = [...ciclosMapa.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([ordem, vest]) => ({ ordem, label: rotuloCiclo(ordem, vest) }));

  const materiasMapa = new Map();
  for (const s of simulados) {
    if (!s.materia) continue;
    materiasMapa.set(s.materia.codigo, s.materia.nome);
  }
  const materias = [...materiasMapa.entries()]
    .sort((a, b) => a[1].localeCompare(b[1]))
    .map(([codigo, nome]) => ({ codigo, nome }));

  const fases = [
    { valor: 'fase_1', label: 'Fase 1' },
    { valor: 'fase_2', label: 'Fase 2' },
  ];

  const vestibularesSet = new Set();
  for (const s of simulados) {
    if (s.vestibularAlvo) vestibularesSet.add(s.vestibularAlvo);
  }
  const vestibulares = [...vestibularesSet].sort();

  return { ciclos, materias, fases, vestibulares };
}

export function contarPorChip(simulados, estado) {
  const ciclo = new Map();
  const materia = new Map();
  const fase = new Map();
  const vestibular = new Map();

  function semCategoria(s, categoriaIgnorada) {
    if (categoriaIgnorada !== 'ciclos' && estado.ciclos.size && !estado.ciclos.has(s.cicloOrdem)) return false;
    if (categoriaIgnorada !== 'materias' && estado.materias.size && !estado.materias.has(s.materia?.codigo)) return false;
    if (categoriaIgnorada !== 'fases' && estado.fases.size && !estado.fases.has(s.tipo)) return false;
    if (categoriaIgnorada !== 'vestibulares' && estado.vestibulares.size && !estado.vestibulares.has(s.vestibularAlvo)) return false;
    if (estado.datas && estado.datas.size && !estado.datas.has(s.dataAplicacao)) return false;
    return true;
  }

  for (const s of simulados) {
    if (s.cicloOrdem != null && semCategoria(s, 'ciclos')) {
      ciclo.set(s.cicloOrdem, (ciclo.get(s.cicloOrdem) || 0) + 1);
    }
    if (s.materia && semCategoria(s, 'materias')) {
      materia.set(s.materia.codigo, (materia.get(s.materia.codigo) || 0) + 1);
    }
    if (s.tipo && semCategoria(s, 'fases')) {
      fase.set(s.tipo, (fase.get(s.tipo) || 0) + 1);
    }
    if (s.vestibularAlvo && semCategoria(s, 'vestibulares')) {
      vestibular.set(s.vestibularAlvo, (vestibular.get(s.vestibularAlvo) || 0) + 1);
    }
  }
  return { ciclo, materia, fase, vestibular };
}
