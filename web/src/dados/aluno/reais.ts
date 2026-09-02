// Os hooks que batem na API de verdade.
//
// Tudo aqui tem entrada `'real'` no `registro.ts`, e a regra que organiza o
// arquivo é a do prompt de implementação: **nada que tenha endpoint é mockado.**
// Um mock a mais é uma integração a menos que ninguém percebe que falta.
//
// Três rotas entram aqui pela primeira vez, prontas e sem tela desde sempre
// (docs/29 §A.5): `/me/trajetoria`, `/me/heatmap` e `/me/simulado/{id}/arquivo`.
//
// ⚠️ `/me/streak` NÃO está aqui, e a ausência é deliberada. A rota existe, mas
// devolve "ciclos consecutivos acima da média da turma" — métrica relativa, que
// premia posição e não progresso (docs/24 §1.1). A mecânica nova é "simulados
// consecutivos sem faltar" (docs/26 §4). Ligar a rota errada seria pior que
// mockar, porque o número pareceria certo.

import { useQuery } from '@tanstack/react-query';

import {
  useEstatisticasBanco,
  useEstudo,
  useLista,
  useListas,
  useProgressoBanco,
  useQuestao,
  useQuestoes,
  useTaxonomia,
} from '../../hooks/banco';
import {
  useEvolucaoMe,
  useInsightMe,
  useQuestoesMe,
  useSimuladoMe,
  useSimuladosMe,
} from '../../hooks/aluno';
import * as api from '../../servicos/api';
import type { Aluno, ArquivoDoSimulado, HeatmapDoAluno, PontoDaTrajetoria } from './contratos';

/** Mesmo raciocínio de `hooks/aluno.ts`: são os dados do próprio aluno, e ele
 *  volta à tela justamente para ver se saiu nota nova. */
const semCache = { staleTime: 0 };

export const chavesAluno = {
  aluno: ['me'] as const,
  trajetoria: ['me', 'trajetoria'] as const,
  heatmap: ['me', 'heatmap'] as const,
  arquivo: (id: string) => ['me', 'simulado', id, 'arquivo'] as const,
};

export function useAluno() {
  return useQuery({
    queryKey: chavesAluno.aluno,
    queryFn: () => api.obterMe() as Promise<Aluno>,
    ...semCache,
  });
}

export function useTrajetoria() {
  return useQuery({
    queryKey: chavesAluno.trajetoria,
    queryFn: () => api.trajetoriaMe() as Promise<PontoDaTrajetoria[]>,
    ...semCache,
  });
}

export function useHeatmap() {
  return useQuery({
    queryKey: chavesAluno.heatmap,
    queryFn: () => api.heatmapMe() as Promise<HeatmapDoAluno>,
    ...semCache,
  });
}

/**
 * A URL assinada da prova em PDF.
 *
 * `enabled` sob demanda: a URL tem vida curta e pedir uma que ninguém vai abrir
 * é gastar assinatura à toa. `gcTime: 0` porque guardar uma URL expirada em
 * cache é pior que não ter nenhuma — o aluno clicaria e receberia 403.
 */
export function useArquivoDoSimulado(id: string | undefined, habilitada: boolean) {
  return useQuery({
    queryKey: chavesAluno.arquivo(id ?? ''),
    queryFn: () => api.arquivoSimuladoMe(id!) as Promise<ArquivoDoSimulado>,
    enabled: !!id && habilitada,
    gcTime: 0,
    ...semCache,
  });
}

// Os que já existiam seguem sendo os mesmos hooks — reexportados, não
// reescritos: uma segunda `useQuery` sobre a mesma rota criaria uma segunda
// chave de cache e a tela mostraria dois estados do mesmo dado.
export {
  useEvolucaoMe as useEvolucao,
  useInsightMe as useInsight,
  useQuestoesMe as useQuestoesDoSimulado,
  useSimuladoMe as useSimulado,
  useSimuladosMe as useSimulados,
};

export {
  useEstatisticasBanco as useEstatisticasDoBanco,
  useEstudo,
  useLista,
  useListas,
  useProgressoBanco,
  useQuestao as useQuestaoDoBanco,
  useQuestoes as useQuestoesDoBanco,
  useTaxonomia,
};
