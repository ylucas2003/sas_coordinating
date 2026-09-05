// Mutações — escrita na API mais a invalidação do que ficou velho.
//
// Cada mutação invalida as chaves afetadas em vez de recarregar a tela
// inteira, que era o que o código antigo fazia disparando
// `sas:dados-atualizados` + `hashchange`.

import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import * as api from '../servicos/api';
import type { CorpoAgendamento } from '../servicos/api';
import type { PapelCoordenacao } from '../tipos/dominio';
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
    mutationFn: ({ id, sincronizarCanvas }: { id: string; sincronizarCanvas: boolean }) =>
      api.cancelarSimulado(id, sincronizarCanvas),
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
    mutationFn: (corpo: { ordem: number; vestibular: string; sincronizar_canvas: boolean }) =>
      api.criarCiclo(corpo),
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
    mutationFn: ({ alunoId, simuladoId, corpo }: { alunoId: string; simuladoId: string; corpo: api.CorpoEdicaoNota }) =>
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

// ─── Administração ───────────────────────────────────────────────────────

function invalidarAdministracao(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['administracao'] });
  queryClient.invalidateQueries({ queryKey: ['auditoria'] });
}

export function useCriarCoordenador() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { email: string; nome: string; canvas_user_id?: string }) => api.criarCoordenador(corpo),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useEditarCoordenador() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: { nome?: string; ativo?: boolean; canvas_user_id?: string } }) =>
      api.editarCoordenador(id, corpo),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useLigarCoordenadorAoCanvas() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.ligarCoordenadorAoCanvas(id),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useAlterarPapelCoordenador() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, papel }: { id: string; papel: PapelCoordenacao }) =>
      api.alterarPapelDoCoordenador(id, papel),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useRedefinirSenhaCoordenador() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.redefinirSenhaCoordenador(id),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

// ─── Foto de perfil ───────────────────────────────────────────────────────
// `invalidarTudo`, e não só `chaves.fotoPropria`: a mesma foto aparece em
// /alunos, na ficha e na auditoria (via `temFoto`/`ator_tem_foto`), e a
// mutação não sabe de antemão quais telas estão montadas.

export function useSalvarMinhaFoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { conteudo_base64: string; content_type: string; declaracao_autorizacao: true }) =>
      api.salvarMinhaFoto(corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

/**
 * O alvo declarado no onboarding — a escrita que faltava para `/me/zona` ter
 * régua (docs/36 §1.4). `invalidarTudo` porque a zona, os cortes e tudo que
 * depende da régua mudam de resposta no mesmo instante.
 */
export function useDefinirVestibulares() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vestibulares: string[]) => api.definirVestibularesMe(vestibulares),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useRemoverMinhaFoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.removerMinhaFoto(),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

/** Ação da staff: tira do ar a foto de um aluno específico (P5). */
export function useRemoverFotoDeAluno() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alunoId: string) => api.removerFotoDeAluno(alunoId),
    onSuccess: () => invalidarTudo(queryClient),
  });
}


// ─── Réguas de corte (docs/31 §P4) ───────────────────────────────────────
// Invalidam tudo: a régua muda quem está cortado, a cor de cada célula, o KPI
// e a linha de corte de todo gráfico. Enumerar o que depende dela seria
// enumerar a coordenação inteira.

export function useCriarCriterio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: api.CorpoCriterio) => api.criarCriterio(corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useEditarCriterio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, corpo }: { slug: string; corpo: Omit<api.CorpoCriterio, 'slug'> }) =>
      api.editarCriterio(slug, corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useDesativarCriterio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.desativarCriterio(slug),
    onSuccess: () => invalidarTudo(queryClient),
  });
}


/**
 * Envio em lote do ciclo ao Canvas (docs/32 §4).
 *
 * Invalida tudo porque um lote bem-sucedido mexe em estado de ciclo, de
 * simulado e de nota ao mesmo tempo — e o selo "só no SAS" some de várias
 * telas de uma vez.
 */
export function useEnviarCicloAoCanvasEmLote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cicloId: string) => api.enviarCicloAoCanvasEmLote(cicloId),
    onSuccess: () => invalidarTudo(queryClient),
  });
}
