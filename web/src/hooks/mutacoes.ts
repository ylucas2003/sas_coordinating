// Mutações — escrita na API mais a invalidação do que ficou velho.
//
// Cada mutação invalida as chaves afetadas em vez de recarregar a tela
// inteira, que era o que o código antigo fazia disparando
// `sas:dados-atualizados` + `hashchange`.

import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import * as api from '../servicos/api';
import type { CorpoAgendamento } from '../servicos/api';
import { chaves } from './consultas';

/**
 * Mutações que mexem em nota ou em prova mudam estatística, ranking e KPI de
 * várias telas ao mesmo tempo — invalidar o cache inteiro é mais barato que
 * enumerar tudo que depende do que mudou.
 */
function invalidarTudo(queryClient: QueryClient) {
  queryClient.invalidateQueries();
}

/** Agenda um simulado (P1): nasce no SAS e o backend o cria no Canvas. */
export function useAgendarSimulado() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: CorpoAgendamento) => api.agendarSimulado(corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useCancelarSimulado() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.cancelarSimulado(id),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useRetrySimuladoCanvas() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.retrySimuladoCanvas(id),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useCriarCiclo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { ordem: number; vestibular: string }) => api.criarCiclo(corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useEditarSimulado() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: unknown }) => api.editarSimulado(id, corpo),
    onSuccess: (_dados, { id }) => {
      queryClient.invalidateQueries({ queryKey: chaves.simulados });
      queryClient.invalidateQueries({ queryKey: chaves.simulado(id) });
    },
  });
}

export function useEditarNota() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alunoId, simuladoId, corpo }: { alunoId: string; simuladoId: string; corpo: unknown }) =>
      api.editarNota(alunoId, simuladoId, corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useResolverAlerta() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.resolverAlerta(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chaves.alertas }),
  });
}
