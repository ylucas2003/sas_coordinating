// Hooks dos avisos neste aparelho (docs/45 §6).
//
// Leitura e escrita no mesmo arquivo, como `hooks/horarioEstudos.ts`: a
// superfície é pequena e de um assunto só. Toda mutação invalida a família
// `['avisos']` inteira — o estado do aparelho e a lista de aparelhos mudam
// juntos, e são três consultas baratas.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../servicos/api';
import * as avisos from '../servicos/avisosNoAparelho';

export const chavesAvisos = {
  tudo: ['avisos'] as const,
  configuracao: ['avisos', 'configuracao'] as const,
  aparelho: ['avisos', 'este-aparelho'] as const,
  aparelhos: ['avisos', 'aparelhos'] as const,
};

/** A chave pública e o "ligado" do servidor. Não muda durante a sessão. */
export function useConfiguracaoDosAvisos() {
  return useQuery({
    queryKey: chavesAvisos.configuracao,
    queryFn: api.configuracaoDosAvisos,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}

/**
 * O estado DESTE aparelho. `staleTime: 0`: a permissão pode ter mudado nos
 * ajustes do sistema desde a última vez que a folha abriu.
 */
export function useEsteAparelho(config: api.ConfiguracaoDosAvisos | undefined) {
  return useQuery({
    queryKey: chavesAvisos.aparelho,
    queryFn: () => avisos.lerAparelho(config as api.ConfiguracaoDosAvisos),
    enabled: !!config,
    staleTime: 0,
    retry: false,
  });
}

export function useAparelhosComAvisos(ligado: boolean) {
  return useQuery({
    queryKey: chavesAvisos.aparelhos,
    queryFn: api.listarAparelhosComAvisos,
    enabled: ligado,
    staleTime: 0,
  });
}

function useInvalidarAvisos() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: chavesAvisos.tudo });
}

/**
 * ⚠️ `mutate` recebe a PROMESSA da permissão, já pedida no `onClick`
 * (`avisos.pedirPermissao()`), e não a pede aqui dentro: a mutação roda depois
 * de um `await` interno do React Query, e o Safari só mostra o pedido com o
 * gesto do usuário ainda em andamento.
 */
export function useAtivarAvisos() {
  const invalidar = useInvalidarAvisos();
  return useMutation({
    mutationFn: ({ permissao, chavePublica }: { permissao: Promise<NotificationPermission>; chavePublica: string }) =>
      avisos.ativar(permissao, chavePublica),
    onSettled: invalidar,
  });
}

export function useDesativarAvisos() {
  const invalidar = useInvalidarAvisos();
  return useMutation({ mutationFn: avisos.desativar, onSettled: invalidar });
}

export function useRevogarAparelho() {
  const invalidar = useInvalidarAvisos();
  return useMutation({ mutationFn: (id: string) => api.revogarAparelho(id), onSettled: invalidar });
}

export function useTestarAvisos() {
  const invalidar = useInvalidarAvisos();
  return useMutation({ mutationFn: api.testarAvisos, onSettled: invalidar });
}
