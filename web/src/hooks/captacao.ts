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
  fusoes: ['captacao', 'fusoes'] as const,
  paginaDeFusoes: (opcoes: { ufIncerta?: boolean; pagina?: number }) =>
    ['captacao', 'fusoes', opcoes] as const,
  fusao: (nomeNormalizado: string) => ['captacao', 'fusoes', nomeNormalizado] as const,
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

// ─── Fila de fusão de baixa confiança (docs/41 §8, item 1) ────────────────

export function useFusoes(opcoes: { ufIncerta?: boolean; pagina?: number; porPagina?: number } = {}) {
  return useQuery({
    queryKey: chavesCaptacao.paginaDeFusoes({ ufIncerta: opcoes.ufIncerta, pagina: opcoes.pagina }),
    queryFn: () => captacao.listarFusoes(opcoes),
    placeholderData: keepPreviousData,
  });
}

export function useFusao(nomeNormalizado: string | null) {
  return useQuery({
    queryKey: chavesCaptacao.fusao(nomeNormalizado ?? ''),
    queryFn: () => captacao.obterFusao(nomeNormalizado as string),
    enabled: !!nomeNormalizado,
  });
}

/**
 * Confirmar ou rejeitar, na mesma mutação: as duas ações têm o mesmo efeito
 * sobre o cache (o grupo sai da fila) e a mesma forma de chamada (só o
 * nome). Separar em dois hooks só duplicaria o `onSuccess`.
 */
export function useDecidirFusao(nomeNormalizado: string) {
  const queryClient = useQueryClient();
  return useMutation({
    // Anotado à mão: os dois braços devolvem formas diferentes (confirmar
    // devolve o sobrevivente, rejeitar só um `ok`), e quem chama nunca lê o
    // valor de volta — só espera a promessa assentar.
    mutationFn: (decisao: 'confirmar' | 'rejeitar'): Promise<unknown> =>
      decisao === 'confirmar'
        ? captacao.confirmarFusao(nomeNormalizado)
        : captacao.rejeitarFusao(nomeNormalizado),
    onSuccess: () => {
      // O grupo decidido não existe mais na fila (fundido ou marcado) — a
      // lista de candidatos também pode ter mudado (um id sumiu, outro
      // ganhou conquista) —, então invalida os dois.
      queryClient.invalidateQueries({ queryKey: chavesCaptacao.fusoes });
      queryClient.invalidateQueries({ queryKey: chavesCaptacao.candidatos });
    },
  });
}
