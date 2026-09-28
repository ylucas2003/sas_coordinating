// Hooks da captação externa (docs/41) — leitura e o funil manual de escrita.
// Mesma divisão de `hooks/banco.ts`: chaves e mutações no mesmo arquivo,
// porque o recurso é um só (candidato + conquistas).
//
// Simplificação de 25/09/2026: sem fila de fusão, sem decisão permanente.
// Agrupar é sempre manual — as três mutações do fim do arquivo.

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as captacao from '../servicos/captacao';
import type { FiltrosCaptacao, RemendoCandidato } from '../tipos/captacao';

export const chavesCaptacao = {
  raiz: ['captacao'] as const,
  candidatos: ['captacao', 'candidatos'] as const,
  pagina: (filtros: FiltrosCaptacao) => ['captacao', 'candidatos', filtros] as const,
  provas: ['captacao', 'provas'] as const,
  perfis: (nomeNormalizado: string) => ['captacao', 'perfis', nomeNormalizado] as const,
};

/**
 * Página de nomes. `keepPreviousData` seguindo `useQuestoes` (hooks/banco.ts):
 * sem isso a lista pisca vazia a cada troca de página ou filtro, numa tabela
 * de 100 mil+ linhas que não tem como carregar inteira.
 */
export function useCandidatos(filtros: FiltrosCaptacao = {}) {
  return useQuery({
    queryKey: chavesCaptacao.pagina(filtros),
    queryFn: () => captacao.listarCandidatos(filtros),
    placeholderData: keepPreviousData,
  });
}

/** As provas que alimentam a lista (ITA, IME, OBMEP...) — muda raríssimo, só
 * quando um dev roda o pipeline manual pra uma fonte nova; `staleTime` longo
 * de propósito. */
export function useProvas() {
  return useQuery({
    queryKey: chavesCaptacao.provas,
    queryFn: () => captacao.listarProvas(),
    staleTime: 60 * 60 * 1000,
  });
}

/** Todo `candidato_externo` com este nome, cada um com as próprias
 * conquistas — os dados de `CaptacaoPerfil.tsx`. */
export function usePerfisDoNome(nomeNormalizado: string | null) {
  return useQuery({
    queryKey: chavesCaptacao.perfis(nomeNormalizado ?? ''),
    queryFn: () => captacao.obterPerfisDoNome(nomeNormalizado as string),
    enabled: !!nomeNormalizado,
  });
}

/** O funil manual (`status_captacao`/`observacoes`), editado direto em cada
 * cartão. `nomeNormalizado` é só pra saber o que invalidar — a escrita em si
 * é sempre por `id` de um `candidato_externo` específico. */
export function useAtualizarCandidato(id: string, nomeNormalizado: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (remendo: RemendoCandidato) => captacao.atualizarCandidato(id, remendo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chavesCaptacao.perfis(nomeNormalizado) });
      queryClient.invalidateQueries({ queryKey: chavesCaptacao.candidatos });
    },
  });
}

// ─── Modo avançado: agrupar é sempre manual (docs/41, 25/09/2026) ─────────
//
// As três mutações abaixo operam DENTRO de um nome aberto — cada uma só
// invalida `perfis(nomeNormalizado)`, não a lista geral: ela lê a view
// materializada (0063), que o backend já atualiza sozinho em segundo plano a
// cada escrita — invalidar aqui também seria redundante e só forçaria uma
// requisição a mais.

/** Perfil novo, vazio, com o mesmo nome — alvo pra arrastar um homônimo pra fora do candidato errado. */
export function useCriarPerfil(nomeNormalizado: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => captacao.criarPerfil(nomeNormalizado),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chavesCaptacao.perfis(nomeNormalizado) });
    },
  });
}

/** Move UMA conquista pra outro perfil do mesmo nome — o coração do arraste. */
export function useMoverConquista(nomeNormalizado: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ conquistaId, candidatoId }: { conquistaId: string; candidatoId: string }) =>
      captacao.moverConquista(conquistaId, candidatoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chavesCaptacao.perfis(nomeNormalizado) });
    },
  });
}

/** Remove um perfil que ficou (ou nasceu, e nunca recebeu nada) sem conquista nenhuma. */
export function useRemoverCandidatoVazio(nomeNormalizado: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (candidatoId: string) => captacao.removerCandidatoVazio(candidatoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chavesCaptacao.perfis(nomeNormalizado) });
    },
  });
}
