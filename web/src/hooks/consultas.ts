// Hooks de leitura — um por recurso. As telas nunca chamam `fetch` nem
// `api.*` direto: chamam um destes, e o TanStack Query cuida de deduplicar
// requisições concorrentes, cachear e revalidar.
//
// Substitui o `cacheGet` que vivia dentro do cliente HTTP antigo.

import { useQuery } from '@tanstack/react-query';
import * as api from '../servicos/api';
import type {
  Aluno, AlunoSimilar, EstatisticasCiclo, NotaSimulado, PontoTrajetoria,
  QuebraSimulado, RespostaHistograma,
} from '../tipos/dominio';
import type { PayloadHeatmap } from '../componentes/ui/Heatmap';
import { algumEmAndamento } from '../dominio/gravacoes';
import type { NotaDoPainel, NotasPorSimulado } from '../dominio/painel';
import type { Ciclo, Simulado } from '../tipos/dominio';

/**
 * Chaves de cache. Centralizadas para a invalidação conseguir alcançar um
 * subconjunto coerente — `['alunos']` invalida a lista e todas as fichas.
 */
export const chaves = {
  alertas: ['alertas'] as const,
  pendenciasCanvas: (cicloId: string) => ['ciclos', cicloId, 'pendencias-canvas'] as const,
  alunos: ['alunos'] as const,
  aluno: (id: string) => ['alunos', id] as const,
  simulados: ['simulados'] as const,
  simulado: (id: string) => ['simulados', id] as const,
  ciclos: ['ciclos'] as const,
  ciclo: (id: string) => ['ciclos', id] as const,
  sedes: ['sedes'] as const,
  turmas: ['turmas'] as const,
  materias: ['materias'] as const,
  fotoPropria: ['foto', 'propria'] as const,
  foto: (tipo: 'aluno' | 'coordenador', id: string) => ['foto', tipo, id] as const,
};

/** O que do ciclo ainda não está no Canvas. Só carrega quando pedido. */
export function usePendenciasCanvas(cicloId: string | null) {
  return useQuery({
    queryKey: chaves.pendenciasCanvas(cicloId ?? ''),
    enabled: !!cicloId,
    queryFn: () => api.pendenciasCanvasDoCiclo(cicloId as string),
  });
}

export function useAlertas() {
  return useQuery({ queryKey: chaves.alertas, queryFn: api.listarAlertas });
}

/**
 * Opções comuns a todos os hooks de leitura. `habilitada: false` segura a
 * requisição até a tela precisar dela — é o que mantém a busca da topbar
 * preguiçosa, em vez de baixar a lista inteira de alunos em toda navegação.
 */
export interface OpcoesConsulta {
  habilitada?: boolean;
}

export function useAlunos({ habilitada = true }: OpcoesConsulta = {}) {
  return useQuery({
    queryKey: chaves.alunos,
    queryFn: () => api.listarAlunos(),
    enabled: habilitada,
  });
}

export function useSimulados() {
  return useQuery({ queryKey: chaves.simulados, queryFn: api.listarSimulados });
}

export function useCiclos() {
  return useQuery({ queryKey: chaves.ciclos, queryFn: api.listarCiclos });
}

export function useSedes() {
  return useQuery({ queryKey: chaves.sedes, queryFn: api.listarSedes });
}

export function useTurmas({ habilitada = true }: OpcoesConsulta = {}) {
  return useQuery({
    queryKey: chaves.turmas,
    queryFn: api.listarTurmas,
    enabled: habilitada,
  });
}

export function useMaterias() {
  return useQuery({ queryKey: chaves.materias, queryFn: api.listarMaterias });
}

// ─── Ficha do simulado ───────────────────────────────────────────────────

export function useSimulado(id: string) {
  return useQuery({ queryKey: chaves.simulado(id), queryFn: () => api.obterSimulado(id) });
}

export function useHistogramaSimulado(id: string) {
  return useQuery({
    queryKey: [...chaves.simulado(id), 'histograma'],
    queryFn: () => api.histogramaSimulado(id) as Promise<RespostaHistograma | null>,
  });
}

export function useSimuladoPorMateria(id: string) {
  return useQuery({
    queryKey: [...chaves.simulado(id), 'por-materia'],
    queryFn: () => api.simuladoPorMateria(id) as Promise<QuebraSimulado[]>,
  });
}

export function useSimuladoPorSede(id: string) {
  return useQuery({
    queryKey: [...chaves.simulado(id), 'por-sede'],
    queryFn: () => api.simuladoPorSede(id) as Promise<QuebraSimulado[]>,
  });
}

export function useNotasSimulado(id: string) {
  return useQuery({
    queryKey: [...chaves.simulado(id), 'notas'],
    queryFn: () => api.notasSimulado(id) as Promise<NotaSimulado[]>,
  });
}

// ─── Ficha do ciclo ──────────────────────────────────────────────────────

export function useCiclo(id: string) {
  return useQuery({ queryKey: chaves.ciclo(id), queryFn: () => api.obterCiclo(id) });
}

/**
 * Estatísticas do ciclo sob uma régua. O critério entra na chave porque muda
 * todo corte do payload — trocar a régua tem que redesenhar os gráficos, e não
 * devolver o cache da régua anterior.
 */
export function useEstatisticasCiclo(id: string, criterio?: string) {
  return useQuery({
    queryKey: [...chaves.ciclo(id), 'estatisticas', criterio ?? null],
    queryFn: () => api.estatisticasCiclo(id, { criterio }) as Promise<EstatisticasCiclo>,
    // O cálculo passa pelo stats engine e pode chamar o LLM: é caro o
    // suficiente para não valer refazer a cada volta à ficha.
    staleTime: 15 * 60 * 1000,
  });
}

/**
 * Classificação do ciclo pelo critério escolhido. Chave inclui critério e fase
 * porque mudar qualquer um muda a lista inteira — e a nota editada invalida
 * `ciclo(id)`, que alcança isto também.
 */
export function useClassificacaoCiclo(cicloId: string | null, criterio: string, fase?: 1 | 2) {
  return useQuery({
    queryKey: [...chaves.ciclo(cicloId ?? ''), 'classificacao', criterio, fase ?? null],
    queryFn: () => api.classificacaoCiclo(cicloId!, criterio, fase),
    enabled: !!cicloId,
  });
}

export function useCriteriosDisponiveis() {
  return useQuery({
    queryKey: ['criterios'],
    queryFn: api.criteriosDisponiveis,
    // Os critérios embutidos mudam por deploy, não por uso.
    staleTime: 60 * 60 * 1000,
  });
}

export function useAuditoria(filtro: api.FiltroAuditoria) {
  return useQuery({
    queryKey: ['auditoria', filtro],
    queryFn: () => api.listarAuditoria(filtro),
    // A trilha só cresce: o que já carregou não muda, mas o topo ganha linhas.
    staleTime: 30 * 1000,
  });
}

export function useCoordenadores() {
  return useQuery({ queryKey: ['administracao', 'coordenadores'], queryFn: api.listarCoordenadores });
}

export function useAcessosDeAlunos() {
  return useQuery({ queryKey: ['administracao', 'alunos-acesso'], queryFn: api.acessosDeAlunos });
}

// ─── Ficha do aluno ──────────────────────────────────────────────────────

export function useAluno(id: string) {
  return useQuery({
    queryKey: chaves.aluno(id),
    queryFn: () => api.obterAluno(id) as Promise<Aluno | null>,
  });
}

export function useTrajetoriaAluno(id: string) {
  return useQuery({
    queryKey: [...chaves.aluno(id), 'trajetoria'],
    queryFn: () => api.trajetoriaAluno(id) as Promise<PontoTrajetoria[]>,
  });
}

export function useHeatmapAluno(id: string) {
  return useQuery({
    queryKey: [...chaves.aluno(id), 'heatmap'],
    queryFn: () => api.heatmapAluno(id) as Promise<PayloadHeatmap | null>,
  });
}

export function useAlunosSimilares(id: string) {
  return useQuery({
    queryKey: [...chaves.aluno(id), 'similares'],
    queryFn: () => api.alunosSimilares(id) as Promise<AlunoSimilar[]>,
  });
}

// ─── Painel ──────────────────────────────────────────────────────────────

/**
 * Notas de todos os simulados de um ciclo, indexadas por simulado.
 *
 * São N requisições (uma por prova) disparadas em paralelo — a API não expõe
 * uma rota de notas por ciclo. Falha individual vira lista vazia: uma prova
 * sem notas não pode derrubar a tabela inteira.
 */
export function useNotasDoCiclo(ciclo: Ciclo | null | undefined, simulados: readonly Simulado[]) {
  const ids = ciclo
    ? simulados.filter((s) => ciclo.simuladoIds.includes(s.id)).map((s) => s.id)
    : [];

  return useQuery({
    queryKey: ['painel', 'notas', ciclo?.id ?? null, ids],
    enabled: !!ciclo,
    queryFn: async () => {
      const resultados = await Promise.all(
        ids.map((id) => (api.notasSimulado(id) as Promise<NotaDoPainel[]>).catch(() => [])),
      );
      const mapa: NotasPorSimulado = {};
      ids.forEach((id, i) => { mapa[id] = resultados[i] ?? []; });
      return mapa;
    },
  });
}

// ─── Foto de perfil ───────────────────────────────────────────────────────

/**
 * Uma foto por vez, sob demanda — nunca em lote. `<Avatar>` só habilita
 * depois que o próprio componente entra na viewport (useVisivelUmaVez), então
 * uma tabela com centenas de linhas não dispara centenas de requisições no
 * primeiro render; só pelas que a pessoa de fato rolou até ver.
 */
export function useFotoPerfil({
  tipo, id, proprio = false, habilitada = true,
}: {
  tipo: 'aluno' | 'coordenador';
  id?: string;
  /** Foto da própria sessão (GET /me/foto) — dispensa `id`. */
  proprio?: boolean;
  habilitada?: boolean;
}) {
  return useQuery({
    queryKey: proprio ? chaves.fotoPropria : chaves.foto(tipo, id ?? ''),
    queryFn: () =>
      proprio ? api.minhaFoto() : tipo === 'aluno' ? api.fotoDeAluno(id ?? '') : api.fotoDeCoordenador(id ?? ''),
    enabled: habilitada && (proprio || !!id),
    staleTime: 10 * 60 * 1000,
  });
}

/**
 * Acompanhamento das gravações de aula (aba Integrações).
 *
 * O polling se autodesliga: `refetchInterval` como FUNÇÃO lê a própria
 * resposta e devolve `false` assim que nenhuma aula está mais na fila ou em
 * processamento. Passar o intervalo de fora exigiria um segundo observador na
 * mesma chave só para descobrir o estado — dois observadores discordando de
 * quanto vale o intervalo é justamente o que não dá para depurar depois.
 */
export function usePainelGravacoes() {
  return useQuery({
    queryKey: ['integracoes', 'gravacoes'],
    queryFn: api.painelGravacoes,
    // 30 s, e não os 600 ms do Importar: a etapa cara aqui (baixar ~500 MB,
    // recodificar e subir) leva de 45 a 90 min.
    refetchInterval: (consulta) =>
      algumEmAndamento(consulta.state.data?.aulas ?? []) ? 30_000 : false,
    staleTime: 0,
  });
}
