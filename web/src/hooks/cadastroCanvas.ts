// Hooks do cadastro de aluno no Canvas (docs/46). Leitura e escrita no mesmo
// arquivo, como `hooks/captacao.ts`: o recurso é um só.
//
// ⚠️ Nada aqui invalida a lista de alunos do SAS. Quem traz o aluno novo para
// o banco é o sync de 5 minutos, não o cadastro — invalidar agora só faria a
// tela buscar de novo a mesma lista sem ele.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as servico from '../servicos/cadastroCanvas';
import type { CadastroDeAluno, LinhaDaPrevia } from '../tipos/cadastroCanvas';

export const chavesCadastroCanvas = {
  raiz: ['cadastro-canvas'] as const,
  pacotes: (ano: number | null) => ['cadastro-canvas', 'pacotes', ano ?? 'padrao'] as const,
  lotes: ['cadastro-canvas', 'lotes'] as const,
  lote: (id: string) => ['cadastro-canvas', 'lote', id] as const,
};

/**
 * Os pacotes vêm do Canvas a cada leitura (nada é guardado no SAS). Cinco
 * minutos de `staleTime` porque curso novo aparece uma vez por ano, e sem isso
 * cada foco na janela custaria quatro chamadas ao Canvas.
 */
export function usePacotesDoCanvas(ano: number | null) {
  return useQuery({
    queryKey: chavesCadastroCanvas.pacotes(ano),
    queryFn: () => servico.listarPacotes(ano),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useCadastrarAluno() {
  return useMutation({ mutationFn: (corpo: CadastroDeAluno) => servico.cadastrarAluno(corpo) });
}

export function usePreviaDoLote() {
  return useMutation({
    mutationFn: ({ arquivo, ano }: { arquivo: File; ano: number | null }) =>
      servico.previaDoLote(arquivo, ano),
  });
}

export function useEnviarLote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ano, linhas }: { ano: number; linhas: LinhaDaPrevia[] }) =>
      servico.enviarLote(ano, linhas),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chavesCadastroCanvas.lotes }),
  });
}

export function useLotesRecentes() {
  return useQuery({
    queryKey: chavesCadastroCanvas.lotes,
    queryFn: servico.lotesRecentes,
    retry: false,
  });
}

/**
 * O lote que acabou de subir, consultado a cada 3 s enquanto o Canvas o
 * processa — e só enquanto: lote terminado não muda mais.
 */
export function useSituacaoDoLote(id: string | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: chavesCadastroCanvas.lote(id ?? ''),
    queryFn: async () => {
      const lote = await servico.situacaoDoLote(id as string);
      // Terminou: a lista de recentes precisa mostrar o estado final.
      if (lote.estado !== 'processando') {
        queryClient.invalidateQueries({ queryKey: chavesCadastroCanvas.lotes });
      }
      return lote;
    },
    enabled: id != null,
    refetchInterval: (consulta) =>
      consulta.state.data?.estado === 'processando' ? 3000 : false,
  });
}
