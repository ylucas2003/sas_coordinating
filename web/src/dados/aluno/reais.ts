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
// ⚠️ `/me/streak` não está aqui porque ela DEIXOU DE EXISTIR em 05/09
// (docs/36 §4). Enquanto foi mock, a razão de não ligá-la era que ela media a
// coisa errada — "ciclos consecutivos acima da média da turma", relativa, que
// premia posição e não progresso (docs/24 §1.1). Agora `useSequencia` fala com
// `/me/jogo`, que conta simulados sem faltar (docs/26 §4), e a rota antiga saiu
// do backend junto: duas verdades sobre o mesmo número é pior que nenhuma.

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
import type { SimuladoOuFalta } from '../../tipos/aluno';
import type {
  Aluno,
  CicloDePresenca,
  HeatmapDoAluno,
  MateriaContraCorte,
  MetaDoCiclo,
  MissaoDoDia,
  PontoDaTrajetoria,
  ProximoSimulado,
  Sequencia,
  ZonaEDistancia,
} from './contratos';

/** Mesmo raciocínio de `hooks/aluno.ts`: são os dados do próprio aluno, e ele
 *  volta à tela justamente para ver se saiu nota nova. */
const semCache = { staleTime: 0 };

export const chavesAluno = {
  aluno: ['me'] as const,
  trajetoria: ['me', 'trajetoria'] as const,
  heatmap: ['me', 'heatmap'] as const,
  missaoDoDia: ['missao', 'hoje'] as const,
  jogo: ['me', 'jogo'] as const,
  agenda: ['me', 'agenda'] as const,
  meta: ['me', 'meta'] as const,
  zona: ['me', 'zona'] as const,
  vestibulares: ['me', 'vestibulares'] as const,
  presenca: ['me', 'simulados', 'com-faltas'] as const,
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


// ─── A corrente, a agenda e a régua ──────────────────────────────────────
// As cinco fontes que docs/30 listava como "dado existe, rota não" e que
// docs/36 §2 destravou. O que faltava nelas nunca foi dado — era a regra de
// quem pode ser chamado de falta, e ela mora no servidor
// (`stats/aluno_jornada.py`), num lugar só.

/** `GET /me/jogo` — simulados consecutivos sem faltar (docs/26 §4). */
export function useSequencia() {
  return useQuery({
    queryKey: chavesAluno.jogo,
    queryFn: () => api.jogoMe() as Promise<Sequencia>,
    ...semCache,
  });
}

/**
 * `GET /me/agenda` — o próximo simulado, ou `null`.
 *
 * ⚠️ `null` é resposta legítima e frequente, não erro: a tela ESCONDE o bloco
 * (docs/36 §1.2). Medindo em 05/09 havia 1 evento futuro no banco inteiro, e um
 * vazio permanente ensina o aluno a ignorar aquele espaço.
 */
export function useProximoSimulado() {
  return useQuery({
    queryKey: chavesAluno.agenda,
    queryFn: () => api.agendaMe() as Promise<ProximoSimulado | null>,
    ...semCache,
  });
}

/** `GET /me/meta` — o alvo do ciclo, que é presença (docs/36 §1.5). */
export function useMetaDoCiclo() {
  return useQuery({
    queryKey: chavesAluno.meta,
    queryFn: () => api.metaMe() as Promise<MetaDoCiclo | null>,
    ...semCache,
  });
}

/** `GET /me/zona` — zona, distância, régua e as matérias contra o corte. */
export function useZona() {
  return useQuery({
    queryKey: chavesAluno.zona,
    queryFn: () => api.zonaMe() as Promise<ZonaEDistancia | null>,
    ...semCache,
  });
}

/**
 * As barras de matéria contra o corte.
 *
 * Mesma `queryKey` de `useZona` de propósito: é a MESMA resposta, recortada com
 * `select`. Uma segunda chave faria uma segunda chamada e — pior — abriria a
 * porta para a tela mostrar a barra de uma régua e o rótulo de outra.
 */
export function useMateriasContraCorte() {
  return useQuery({
    queryKey: chavesAluno.zona,
    queryFn: () => api.zonaMe() as Promise<ZonaEDistancia | null>,
    select: (zona): MateriaContraCorte[] => zona?.materias ?? [],
    ...semCache,
  });
}

/**
 * A corrente por ciclo — `GET /me/simulados?incluirFaltas=true`, agrupado.
 *
 * O agrupamento é do lado do cliente porque a rota já devolve `cicloOrdem` em
 * cada linha: uma rota nova só para dobrar a mesma lista seria dívida, não
 * serviço.
 */
export function usePresencaPorCiclo() {
  return useQuery({
    queryKey: chavesAluno.presenca,
    queryFn: () => api.listarSimuladosComFaltasMe() as Promise<SimuladoOuFalta[]>,
    select: agruparPorCiclo,
    ...semCache,
  });
}

function agruparPorCiclo(simulados: SimuladoOuFalta[]): CicloDePresenca[] {
  const porOrdem = new Map<number, CicloDePresenca>();
  const cronologico = [...simulados].sort((a, b) =>
    (a.dataAplicacao ?? '').localeCompare(b.dataAplicacao ?? ''),
  );
  for (const s of cronologico) {
    if (s.cicloOrdem == null) continue;
    let ciclo = porOrdem.get(s.cicloOrdem);
    if (!ciclo) {
      ciclo = { ciclo: `Ciclo ${s.cicloOrdem}`, elos: [] };
      porOrdem.set(s.cicloOrdem, ciclo);
    }
    ciclo.elos.push({
      simuladoId: s.id,
      rotulo: s.rotulo ?? s.nome ?? '',
      data: s.dataAplicacao,
      presente: s.presente,
    });
  }
  return [...porOrdem.entries()].sort(([a], [b]) => a - b).map(([, ciclo]) => ciclo);
}

// ─── Onboarding ──────────────────────────────────────────────────────────

/**
 * `GET /me/vestibulares` — e `completo` é o portão do casco.
 *
 * ⚠️ `vestibular_alvo_aluno` existe desde a migration 0001 e **nunca teve quem
 * escrevesse nela** (0 linhas em 05/09). Por isso o onboarding não é enfeite:
 * sem ele a tabela continua vazia e `/me/zona` cai na régua da casa para todo
 * mundo, que é o contrário de "cada aluno contra o edital que persegue".
 */
export function useVestibulares() {
  return useQuery({
    queryKey: chavesAluno.vestibulares,
    queryFn: () => api.vestibularesMe(),
    ...semCache,
  });
}
