// Hooks das rotas /me — usados só pela área do aluno.
//
// `staleTime: 0` de propósito: são os dados do próprio aluno, e ele volta à
// tela justamente para ver se saiu nota nova. O cliente antigo passava
// `{cache: false}` nestas rotas pela mesma razão.

import { useQuery } from '@tanstack/react-query';
import * as api from '../servicos/api';
import type {
  DetalheSimuladoAluno, EvolucaoAluno, InsightDoAluno, QuestoesDoSimulado,
  SimuladoDoAluno, Streak,
} from '../tipos/aluno';

export const chavesMe = {
  streak: ['me', 'streak'] as const,
  simulados: ['me', 'simulados'] as const,
  simulado: (id: string) => ['me', 'simulado', id] as const,
  questoes: (id: string) => ['me', 'simulado', id, 'questoes'] as const,
  evolucao: ['me', 'evolucao'] as const,
  insight: ['me', 'insight'] as const,
};

const semCache = { staleTime: 0 };

export function useStreakMe() {
  return useQuery({
    queryKey: chavesMe.streak,
    queryFn: () => api.streakMe() as Promise<Streak>,
    ...semCache,
  });
}

export function useSimuladosMe() {
  return useQuery({
    queryKey: chavesMe.simulados,
    queryFn: () => api.listarSimuladosMe() as Promise<SimuladoDoAluno[]>,
    ...semCache,
  });
}

export function useSimuladoMe(id: string | undefined) {
  return useQuery({
    queryKey: chavesMe.simulado(id ?? ''),
    queryFn: () => api.obterSimuladoMe(id!) as Promise<DetalheSimuladoAluno>,
    enabled: !!id,
    ...semCache,
  });
}

export function useQuestoesMe(id: string | undefined) {
  return useQuery({
    queryKey: chavesMe.questoes(id ?? ''),
    queryFn: () => api.questoesSimuladoMe(id!) as Promise<QuestoesDoSimulado | null>,
    enabled: !!id,
    ...semCache,
  });
}

export function useEvolucaoMe() {
  return useQuery({
    queryKey: chavesMe.evolucao,
    queryFn: () => api.evolucaoMe() as Promise<EvolucaoAluno | null>,
    ...semCache,
  });
}

/**
 * Insight do ciclo. Fica FORA do carregamento principal do painel: a primeira
 * geração chama o LLM e pode levar segundos — a tela não espera por ela.
 */
export function useInsightMe() {
  return useQuery({
    queryKey: chavesMe.insight,
    queryFn: () => api.insightMe() as Promise<InsightDoAluno>,
    ...semCache,
  });
}
