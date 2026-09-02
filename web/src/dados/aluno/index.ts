// O ponto único de importação das telas do aluno.
//
// Nenhuma tela importa `mocks.ts`, e nenhuma importa `reais.ts` direto — as
// duas coisas entram por aqui, com a mesma assinatura. É o que faz desmockar
// ser trocar uma linha DESTE arquivo, em vez de caçar dado falso pelo código.
//
// Todo hook devolve `useQuery`, inclusive os de mock, e todo mock devolve
// `Promise`: assim `isPending`, `isError`, `data` e a invalidação por chave já
// funcionam antes de existir servidor do outro lado, e a troca não muda a
// assinatura de nada.
//
// ⚠️ Toda chave de fonte usada aqui tem de existir em `registro.ts`, e
// `costura.test.ts` falha se não tiver. É o que impede a superfície mockada de
// crescer sem entrar no inventário — e o inventário é o que vira `docs/30`.

import { useQuery } from '@tanstack/react-query';

import * as mocks from './mocks';

export type * from './contratos';
export { estadoDaFonte, FONTES, fonte, fontesPorEstado } from './registro';
export type { EstadoFonte, Fonte } from './registro';

// ─── REAL ────────────────────────────────────────────────────────────────

export {
  chavesAluno,
  useAluno,
  useArquivoDoSimulado,
  useEstatisticasDoBanco,
  useEstudo,
  useEvolucao,
  useHeatmap,
  useInsight,
  useLista,
  useListas,
  useProgressoBanco,
  useQuestaoDoBanco,
  useQuestoesDoBanco,
  useQuestoesDoSimulado,
  useSimulado,
  useSimulados,
  useTaxonomia,
  useTrajetoria,
} from './reais';

export {
  useAdicionarQuestaoNaLista,
  useApagarLista,
  useAtualizarEstudo,
  useAtualizarLista,
  useCriarLista,
  useRemoverQuestaoDaLista,
} from '../../hooks/banco';

// ─── SEM-ROTA e MOCK ─────────────────────────────────────────────────────
//
// A `queryKey` começa com `'mock'` de propósito: no devtools do React Query dá
// para ver de relance quanto da tela ainda não fala com o servidor, sem ler
// código. Quando a fonte virar real, a chave muda junto com a `queryFn`.

/** `staleTime: Infinity` — o mock não muda, e revalidar dado falso é ruído. */
const fixo = { staleTime: Number.POSITIVE_INFINITY };

/** sem-rota · `nota.presente` (docs/29 §A.2, docs/26 §4) */
export function useSequencia() {
  return useQuery({ queryKey: ['mock', 'sequencia'], queryFn: mocks.buscarSequencia, ...fixo });
}

/** sem-rota · `evento_agenda` (docs/29 §A.1) */
export function useProximoSimulado() {
  return useQuery({
    queryKey: ['mock', 'proximoSimulado'],
    queryFn: mocks.buscarProximoSimulado,
    ...fixo,
  });
}

/** sem-rota · `classificacao_aluno.zona` + avaliador de critérios (docs/29 §A.4) */
export function useZona() {
  return useQuery({ queryKey: ['mock', 'zonaEDistancia'], queryFn: mocks.buscarZona, ...fixo });
}

/** sem-rota · `criterio_classificacao` (docs/24 §2) */
export function useMateriasContraCorte() {
  return useQuery({
    queryKey: ['mock', 'cortePorMateria'],
    queryFn: mocks.buscarMateriasContraCorte,
    ...fixo,
  });
}

/** sem-rota · agregação de `/me/simulado/{id}/questoes` (docs/29 §A.3) */
export function useMeusErros() {
  return useQuery({ queryKey: ['mock', 'meusErros'], queryFn: mocks.buscarErros, ...fixo });
}

/** sem-rota · `nota.presente` por ciclo (docs/29 §A.2) */
export function usePresencaPorCiclo() {
  return useQuery({
    queryKey: ['mock', 'presencaNosSimulados'],
    queryFn: mocks.buscarCiclosAnteriores,
    ...fixo,
  });
}

/** mock · docs/26 §3 — e o backtest de docs/29 §H é portão antes de fixar número */
export function useXp() {
  return useQuery({ queryKey: ['mock', 'xp'], queryFn: mocks.buscarXp, ...fixo });
}

/** mock · docs/26 §3 */
export function useExtratoXp() {
  return useQuery({ queryKey: ['mock', 'extratoXp'], queryFn: mocks.buscarExtratoXp, ...fixo });
}

/** mock · docs/26 §5.1 */
export function useLiga() {
  return useQuery({ queryKey: ['mock', 'liga'], queryFn: mocks.buscarLiga, ...fixo });
}

/** mock · docs/26 §6 */
export function useConquistas() {
  return useQuery({ queryKey: ['mock', 'conquistas'], queryFn: mocks.buscarConquistas, ...fixo });
}

/** mock · o cartão de aprovados, entregue como afordância */
export function useDepoimento() {
  return useQuery({ queryKey: ['mock', 'depoimentos'], queryFn: mocks.buscarDepoimento, ...fixo });
}

/** mock · docs/24 §4.5 — depende do Sprint 6 */
export function useMissaoDoDia() {
  return useQuery({ queryKey: ['mock', 'missaoDoDia'], queryFn: mocks.buscarMissao, ...fixo });
}

/** mock · docs/24 §7.3 — a meta semanal virou meta do ciclo */
export function useMetaDoCiclo() {
  return useQuery({ queryKey: ['mock', 'metaDoCiclo'], queryFn: mocks.buscarMetaDoCiclo, ...fixo });
}

// ─── Funções puras da camada de mock ─────────────────────────────────────
// Não são hooks: são a regra que ainda não existe no servidor, aplicada sobre
// dado real. `ordenarFilaDeTreino` recebe questões de verdade do
// `/banco/questoes` e só decide a ORDEM — é a fronteira exata entre o que já
// funciona e o que falta (docs/28 §3).

export { RAZAO_DA_FILA, ordenarFilaDeTreino, resumoDoTreino } from './mocks';
