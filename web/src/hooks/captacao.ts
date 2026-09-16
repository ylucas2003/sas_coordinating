// Hooks da captação externa (docs/41) — leitura e o funil manual de escrita.
// Mesma divisão de `hooks/banco.ts`: chaves e mutações no mesmo arquivo,
// porque o recurso é um só (candidato + conquistas).

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as captacao from '../servicos/captacao';
import type { FiltrosCaptacao, RemendoCandidato } from '../tipos/captacao';

export const chavesCaptacao = {
  raiz: ['captacao'] as const,
  candidatos: ['captacao', 'candidatos'] as const,
  pagina: (filtros: FiltrosCaptacao) => ['captacao', 'candidatos', filtros] as const,
  candidato: (id: string) => ['captacao', 'candidatos', id] as const,
};

/**
 * Página de candidatos. `keepPreviousData` seguindo `useQuestoes`
 * (hooks/banco.ts): sem isso a lista pisca vazia a cada troca de página ou
 * filtro, numa tabela de 26 mil linhas que não tem como carregar inteira.
 */
export function useCandidatos(filtros: FiltrosCaptacao = {}) {
  return useQuery({
    queryKey: chavesCaptacao.pagina(filtros),
    queryFn: () => captacao.listarCandidatos(filtros),
    placeholderData: keepPreviousData,
  });
}

export function useCandidato(id: string | null) {
  return useQuery({
    queryKey: chavesCaptacao.candidato(id ?? ''),
    queryFn: () => captacao.obterCandidato(id as string),
    enabled: !!id,
  });
}

export function useAtualizarCandidato(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (remendo: RemendoCandidato) => captacao.atualizarCandidato(id, remendo),
    onSuccess: (candidato) => {
      // A ficha aberta atualiza na hora, sem esperar reconsulta; as páginas da
      // lista (que somam por status/conquistas) só invalidam, porque um PATCH
      // de status pode mudar em qual página este candidato aparece.
      queryClient.setQueryData(chavesCaptacao.candidato(id), candidato);
      queryClient.invalidateQueries({ queryKey: chavesCaptacao.candidatos });
    },
  });
}
