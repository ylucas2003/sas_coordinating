// Hooks da cantina — os três públicos (docs/38).
//
// Leitura aqui, escrita aqui: é o único arquivo de hooks do projeto que junta
// os dois, e a razão é que a superfície é pequena e inteiramente de um assunto
// só. Separar em `consultas`/`mutacoes` como o resto faria a invalidação
// atravessar arquivos para nada.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';

import * as api from '../servicos/api';
import type { CorpoCardapio } from '../servicos/api';
import type { Refeicao } from '../tipos/cantina';

export const chavesCantina = {
  calendario: (de: string, ate: string) => ['cantina', 'calendario', de, ate] as const,
  cardapio: (id: string) => ['cantina', 'cardapio', id] as const,
  contagem: (id: string) => ['cantina', 'contagem', id] as const,
  pedidos: (id: string) => ['cantina', 'pedidos', id] as const,
  doAluno: ['me', 'cantina'] as const,
  calendarioCoord: (de: string, ate: string) => ['coord', 'cantina', de, ate] as const,
  cardapioCoord: (id: string) => ['coord', 'cantina', 'cardapio', id] as const,
  direitos: ['administracao', 'direito-refeicao'] as const,
  cantinas: ['administracao', 'cantinas'] as const,
};

/** Publicar, salvar e copiar mudam o calendário E o dia. Invalidar o galho
    inteiro é mais barato que enumerar o que depende do quê. */
function invalidarCantina(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ['cantina'] });
  qc.invalidateQueries({ queryKey: ['coord', 'cantina'] });
}

// ─── A cantina ────────────────────────────────────────────────────────────

export function useCalendarioDaCantina(de: string, ate: string) {
  return useQuery({
    queryKey: chavesCantina.calendario(de, ate),
    queryFn: () => api.calendarioDaCantina(de, ate),
    staleTime: 30 * 1000,
  });
}

export function useCardapio(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.cardapio(id ?? ''),
    queryFn: () => api.obterCardapio(id!),
    enabled: !!id,
    staleTime: 0,
  });
}

export function useContagem(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.contagem(id ?? ''),
    queryFn: () => api.contagemDoCardapio(id!),
    enabled: !!id,
    staleTime: 0,
  });
}

export function usePedidosDoCardapio(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.pedidos(id ?? ''),
    queryFn: () => api.pedidosDoCardapio(id!),
    enabled: !!id,
    staleTime: 0,
  });
}

export function useCriarCardapio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { data: string; refeicao: Refeicao }) => api.criarCardapio(corpo),
    onSuccess: () => invalidarCantina(qc),
  });
}

export function useSalvarCardapio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: CorpoCardapio }) =>
      api.salvarCardapio(id, corpo),
    onSuccess: () => invalidarCantina(qc),
  });
}

export function usePublicarCardapio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.publicarCardapio(id),
    onSuccess: () => invalidarCantina(qc),
  });
}

export function useCopiarCardapio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, origemId }: { id: string; origemId: string }) =>
      api.copiarCardapio(id, origemId),
    onSuccess: () => invalidarCantina(qc),
  });
}

// ─── O aluno ──────────────────────────────────────────────────────────────

/**
 * O cardápio do aluno, e é aqui que mora a resposta de tempo real (docs/38 §9).
 *
 * Duas camadas, e as duas juntas custam pouco mais que uma linha:
 *
 *   0. `refetchOnWindowFocus` LIGADO, contra o default do app. A justificativa
 *      global (`main.tsx`: "os dados do SAS só mudam quando entra planilha nova
 *      ou alguém edita algo") não vale aqui — nesta tela o dado muda porque
 *      OUTRA PESSOA publicou. É o que cobre o caso real: o aluno volta ao app e
 *      o cardápio de hoje já está lá.
 *   1. polling de 60 s que se autodesliga, no padrão de `usePainelGravacoes`.
 *      Só roda para quem tem direito — 800 dos 900 alunos nunca pedem nada.
 *
 * SSE ficou de fora, e a decisão está escrita: o cardápio é publicado horas ou
 * um dia antes do prazo, então a diferença entre 60 s e 1 s é invisível. O que
 * faria valer a pena não é a publicação — é `disponivel = false` às 11h40, com
 * o prazo ainda aberto. Se esse caso aparecer na prática, é o gatilho para
 * subir a camada, e o caminho já está aberto (o chat já fala SSE, o nginx já
 * está configurado e `UVICORN_WORKERS=1` dispensa LISTEN/NOTIFY).
 */
export function useCantinaDoAluno() {
  return useQuery({
    queryKey: chavesCantina.doAluno,
    queryFn: api.cantinaDoAluno,
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchInterval: (consulta) => (consulta.state.data?.direitos.length ? 60_000 : false),
  });
}

export function useSalvarPedido() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ cardapioId, opcaoIds }: { cardapioId: string; opcaoIds: string[] }) =>
      api.salvarPedido(cardapioId, opcaoIds),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.doAluno }),
  });
}

export function useCancelarPedido() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cardapioId: string) => api.cancelarPedido(cardapioId),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.doAluno }),
  });
}

// ─── A coordenação ────────────────────────────────────────────────────────

export function useCalendarioNaCoordenacao(de: string, ate: string) {
  return useQuery({
    queryKey: chavesCantina.calendarioCoord(de, ate),
    queryFn: () => api.calendarioNaCoordenacao(de, ate),
    staleTime: 60 * 1000,
  });
}

export function useCardapioNaCoordenacao(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.cardapioCoord(id ?? ''),
    queryFn: () => api.cardapioNaCoordenacao(id!),
    enabled: !!id,
    staleTime: 0,
  });
}

export function useDireitos() {
  return useQuery({
    queryKey: chavesCantina.direitos,
    queryFn: api.listarDireitos,
    staleTime: 60 * 1000,
  });
}

export function useCantinas() {
  return useQuery({
    queryKey: chavesCantina.cantinas,
    queryFn: api.listarCantinas,
    staleTime: 60 * 1000,
  });
}

export function useConcederDireito() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { aluno_ids: string[]; refeicao: Refeicao; conceder: boolean }) =>
      api.conceberDireito(corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.direitos }),
  });
}

export function useSalvarRestricao() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ alunoId, restricao }: { alunoId: string; restricao: string | null }) =>
      api.salvarRestricaoAlimentar(alunoId, restricao),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.direitos }),
  });
}

export function useCriarCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { nome: string }) => api.criarCantina(corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

export function useEditarCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: Parameters<typeof api.editarCantina>[1] }) =>
      api.editarCantina(id, corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

export function useCriarContaDeCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { cantina_id: string; email: string; nome: string }) =>
      api.criarContaDeCantina(corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

export function useEditarContaDeCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: { nome?: string; ativo?: boolean } }) =>
      api.editarContaDeCantina(id, corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

export function useRedefinirSenhaDeCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.redefinirSenhaDeCantina(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}
