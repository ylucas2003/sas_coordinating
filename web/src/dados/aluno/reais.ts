// Os hooks que batem na API de verdade.
//
// Tudo aqui tem entrada `'real'` no `registro.ts`, e a regra que organiza o
// arquivo é a do prompt de implementação: **nada que tenha endpoint é mockado.**
// Um mock a mais é uma integração a menos que ninguém percebe que falta.
//
// Duas rotas entraram aqui prontas e sem tela desde sempre (docs/29 §A.5):
// `/me/trajetoria` e `/me/heatmap`. A terceira era `/me/simulado/{id}/arquivo`,
// e ela SAIU em 04/09 junto com o botão "Abrir a prova" (docs/35 §8b) — a rota
// foi desligada no backend, não só escondida na tela.
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
import { get } from '../../servicos/http';
import type { Aluno, HeatmapDoAluno, MissaoDoDia, PontoDaTrajetoria } from './contratos';

/** Mesmo raciocínio de `hooks/aluno.ts`: são os dados do próprio aluno, e ele
 *  volta à tela justamente para ver se saiu nota nova. */
const semCache = { staleTime: 0 };

export const chavesAluno = {
  aluno: ['me'] as const,
  trajetoria: ['me', 'trajetoria'] as const,
  heatmap: ['me', 'heatmap'] as const,
  missaoDoDia: ['missao', 'hoje'] as const,
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
 * O desafio de hoje — `GET /missao/hoje`.
 *
 * Deixou de ser mock em 04/09 (docs/35 §9). O cartão da Hoje imprimia o NOME de
 * um fixture e a fila de treino consultava o CÓDIGO dele no banco real: como o
 * código existia e devolvia questões, nada quebrava — o cartão só dizia
 * "Termodinâmica" e o treino entregava Ondas e Acústica. Agora as duas coisas
 * saem da mesma linha da taxonomia, no servidor.
 *
 * Não é dado do aluno: é o mesmo assunto para toda a turma, sorteado pela data
 * em America/Fortaleza. Por isso `staleTime` não é zero — o que muda é a
 * virada do dia, não uma nota que acabou de sair.
 *
 * ⚠️ A chamada vai por `http.get` e não por `servicos/api.ts`, onde moram as
 * outras rotas de leitura. É pendência de costura desta leva de correções
 * (docs/35), não um padrão novo: assim que der, esta linha vira mais uma
 * função de lá.
 */
export function useMissaoDoDia() {
  return useQuery({
    queryKey: chavesAluno.missaoDoDia,
    queryFn: () => get<MissaoDoDia | null>('/missao/hoje'),
    staleTime: 30 * 60 * 1000,
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
