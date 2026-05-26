// Implementação mock do ApiClient. Espelha o que o backend FastAPI vai
// expor. Promessas resolvem imediatamente, mas mantemos `async` para
// que o callsite não mude quando trocarmos pelo HTTP real.

import {
  alertas as alertasMock,
  alunos as alunosMock,
  ciclos as ciclosMock,
  sedes as sedesMock,
  simulados as simuladosMock,
  turmas as turmasMock,
} from './mock-data.js';

function matchAluno(aluno, recorte) {
  if (!recorte) return true;
  if (recorte === 'em-risco') return aluno.zona === 'risco';
  if (recorte === 'em-ascensao') return aluno.tendencia === 'subindo';
  if (recorte === 'perfil-irregular') return aluno.perfil === 'misterio';
  if (recorte === 'zona-corte') return aluno.zona === 'cinzenta';
  return true;
}

export const mockClient = {
  async listarAlertas() {
    return alertasMock.slice();
  },

  async listarAlunos(filtros = {}) {
    return alunosMock.filter((a) => {
      if (filtros.sedeId && a.sedeId !== filtros.sedeId) return false;
      if (filtros.turmaId && a.turmaId !== filtros.turmaId) return false;
      if (!matchAluno(a, filtros.recorte)) return false;
      return true;
    });
  },

  async obterAluno(id) {
    return alunosMock.find((a) => a.id === id) ?? null;
  },

  async listarSimulados() {
    return simuladosMock.slice();
  },

  async obterSimulado(id) {
    return simuladosMock.find((s) => s.id === id) ?? null;
  },

  async listarCiclos() {
    return ciclosMock.slice();
  },

  async obterCiclo(id) {
    return ciclosMock.find((c) => c.id === id) ?? null;
  },

  async listarSedes() {
    return sedesMock.slice();
  },

  async listarTurmas() {
    return turmasMock.slice();
  },
};
