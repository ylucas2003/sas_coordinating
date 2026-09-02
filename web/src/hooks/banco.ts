// Hooks do banco de questões ITA · IME (docs/22) — leitura e escrita.
//
// Mesma divisão de trabalho de `consultas.ts` + `mutacoes.ts`: a tela nunca
// chama `servicos/banco.ts` direto. Os dois lados moram no mesmo arquivo aqui
// porque o recurso é um só e a invalidação de lista e de estudo só faz sentido
// ao lado das chaves que ela alcança.

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import * as banco from '../servicos/banco';
import type {
  FiltrosBanco, MateriaBanco, RemendoEstudo, RemendoLista, VestibularBanco,
} from '../tipos/banco';
import type { OpcoesConsulta } from './consultas';

/**
 * Chaves sob o prefixo `['banco']`, para a invalidação alcançar subconjuntos
 * coerentes por prefixo: `['banco', 'listas']` invalida o índice **e** todas as
 * listas abertas, `['banco', 'questoes']` invalida páginas e fichas.
 */
export const chavesBanco = {
  raiz: ['banco'] as const,
  taxonomia: (materia?: MateriaBanco) => ['banco', 'taxonomia', materia ?? null] as const,
  questoes: ['banco', 'questoes'] as const,
  pagina: (filtros: FiltrosBanco) => ['banco', 'questoes', filtros] as const,
  questao: (id: string) => ['banco', 'questoes', id] as const,
  estatisticas: (materia: MateriaBanco | null, vestibular?: VestibularBanco, fase?: number) =>
    ['banco', 'estatisticas', materia, vestibular ?? null, fase ?? null] as const,
  listas: ['banco', 'listas'] as const,
  lista: (id: string) => ['banco', 'listas', id] as const,
  estudo: ['banco', 'estudo'] as const,
  progresso: ['banco', 'progresso'] as const,
};

/**
 * Questão de prova passada só muda quando alguém importa uma prova nova — isso
 * é deploy, não uso. Uma hora de frescor evita rebaixar a mesma página a cada
 * volta do aluno à aba. O que muda por uso (`resolvida`, `anotacao`) chega por
 * invalidação explícita, que ignora o `staleTime`.
 */
const FRESCOR_CONTEUDO_DE_PROVA = 60 * 60 * 1000;

// ─── Leitura ─────────────────────────────────────────────────────────────

/** Sem `materia`, traz as três árvores — é o que a tela usa para montar o menu. */
export function useTaxonomia(materia?: MateriaBanco) {
  return useQuery({
    queryKey: chavesBanco.taxonomia(materia),
    queryFn: () => banco.obterTaxonomia(materia),
    staleTime: FRESCOR_CONTEUDO_DE_PROVA,
  });
}

/**
 * Página de questões filtrada. `keepPreviousData` segura a página atual na tela
 * enquanto a próxima carrega: sem isso a lista pisca vazia a cada clique de
 * paginação, e no celular o scroll salta para o topo.
 */
export function useQuestoes(filtros: FiltrosBanco = {}, { habilitada = true }: OpcoesConsulta = {}) {
  return useQuery({
    queryKey: chavesBanco.pagina(filtros),
    queryFn: () => banco.listarQuestoes(filtros),
    enabled: habilitada,
    placeholderData: keepPreviousData,
    staleTime: FRESCOR_CONTEUDO_DE_PROVA,
  });
}

export function useQuestao(id: string | null) {
  return useQuery({
    queryKey: chavesBanco.questao(id ?? ''),
    queryFn: () => banco.obterQuestao(id!),
    enabled: !!id,
    staleTime: FRESCOR_CONTEUDO_DE_PROVA,
  });
}

/**
 * Recorrência por tópico. Agrega no servidor sobre a tabela inteira (docs/22 §2.2).
 *
 * `fase` entra na chave de cache junto com `vestibular`: os dois estreitam a
 * resposta inteira, e duas respostas de recortes diferentes sob a mesma chave
 * fariam a tela mostrar o número de um recorte sob o rótulo do outro.
 */
export function useEstatisticasBanco(
  materia: MateriaBanco | null,
  vestibular?: VestibularBanco,
  fase?: number,
) {
  return useQuery({
    queryKey: chavesBanco.estatisticas(materia, vestibular, fase),
    queryFn: () => banco.estatisticasBanco(materia!, vestibular, fase),
    enabled: !!materia,
    staleTime: FRESCOR_CONTEUDO_DE_PROVA,
  });
}

/**
 * Quanto do acervo o aluno marcou como feito, já agregado.
 *
 * Sem `staleTime`: ao contrário do conteúdo de prova, isto muda por USO — o
 * aluno marca uma questão e volta para a tela de progresso esperando ver o
 * número subir. A invalidação de `useAtualizarEstudo` cobre o caminho curto;
 * o frescor zero cobre o aluno que marcou no celular e abriu no computador.
 */
export function useProgressoBanco({ habilitada = true }: OpcoesConsulta = {}) {
  return useQuery({
    queryKey: chavesBanco.progresso,
    queryFn: banco.progressoDoBanco,
    enabled: habilitada,
  });
}

export function useListas({ habilitada = true }: OpcoesConsulta = {}) {
  return useQuery({
    queryKey: chavesBanco.listas,
    queryFn: banco.listarListas,
    enabled: habilitada,
  });
}

export function useLista(id: string | null) {
  return useQuery({
    queryKey: chavesBanco.lista(id ?? ''),
    queryFn: () => banco.obterLista(id!),
    enabled: !!id,
  });
}

/**
 * O que o aluno já resolveu e anotou. A rota é só do casco do aluno — a tela
 * passa `habilitada: perfil === 'aluno'` para o coordenador não pedir um 403.
 */
export function useEstudo({ habilitada = true }: OpcoesConsulta = {}) {
  return useQuery({
    queryKey: chavesBanco.estudo,
    queryFn: banco.listarEstudo,
    enabled: habilitada,
  });
}

// ─── Escrita ─────────────────────────────────────────────────────────────

/** Alcança o índice e cada lista aberta, por prefixo. */
function invalidarListas(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: chavesBanco.listas });
}

export function useCriarLista() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (titulo: string) => banco.criarLista(titulo),
    onSuccess: () => invalidarListas(queryClient),
  });
}

/** Renomear e reordenar são a mesma rota: `questaoIds` é a ordem completa. */
export function useAtualizarLista() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, remendo }: { id: string; remendo: RemendoLista }) =>
      banco.atualizarLista(id, remendo),
    onSuccess: () => invalidarListas(queryClient),
  });
}

export function useApagarLista() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => banco.apagarLista(id),
    onSuccess: () => invalidarListas(queryClient),
  });
}

export function useAdicionarQuestaoNaLista() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listaId, questaoId }: { listaId: string; questaoId: string }) =>
      banco.adicionarQuestaoNaLista(listaId, questaoId),
    onSuccess: () => invalidarListas(queryClient),
  });
}

export function useRemoverQuestaoDaLista() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listaId, questaoId }: { listaId: string; questaoId: string }) =>
      banco.removerQuestaoDaLista(listaId, questaoId),
    onSuccess: () => invalidarListas(queryClient),
  });
}

/**
 * Marcar resolvida ou anotar. Invalida mais do que `/banco/estudo` porque
 * `resolvida` e `anotacao` viajam **dentro** de cada `QuestaoVestibular` quando
 * o aluno está autenticado: sem isso, o cartão da listagem continuaria
 * desmarcado até o cache expirar. A taxonomia e as estatísticas não carregam o
 * estado do aluno, então ficam de fora.
 */
export function useAtualizarEstudo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ questaoId, remendo }: { questaoId: string; remendo: RemendoEstudo }) =>
      banco.atualizarEstudo(questaoId, remendo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chavesBanco.estudo });
      queryClient.invalidateQueries({ queryKey: chavesBanco.questoes });
      // O progresso é contado a partir de `resolvida`: sem esta linha, marcar
      // uma questão e voltar para "Meu progresso" mostraria o número velho, e
      // o aluno concluiria que a marcação não pegou.
      queryClient.invalidateQueries({ queryKey: chavesBanco.progresso });
      invalidarListas(queryClient);
    },
  });
}
