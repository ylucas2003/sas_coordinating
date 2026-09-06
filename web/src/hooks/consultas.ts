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
import type { DiaDoCalendario, Refeicao } from '../tipos/cantina';
// A chave vem de `hooks/cantina.ts`, e não de uma nova daqui: o dia da
// coordenação lê a MESMA rota do calendário do mês, e duas chaves para a mesma
// resposta fariam a tela do dia ignorar a invalidação que a publicação de um
// cardápio dispara.
import { chavesCantina } from './cantina';

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

/**
 * A lista de alunos — e, desde a fase 4 do docs/39, ela já vem com **as três
 * médias** (`aluno.medias`: do ano, do primeiro ciclo e do último, cada uma
 * aberta em Matemática, Física e Química) e com os **direitos de refeição**
 * (`aluno.direitos`).
 *
 * As duas coisas são do servidor: derivar as médias aqui custaria baixar as
 * notas dos 900 a cada carregamento, e o recorte de "qual é o primeiro ciclo e
 * qual é o último" é decisão dele, não da tela — ver `useRotulosDasMedias`.
 *
 * ⚠️ A restrição alimentar NÃO está aqui e não deve ser buscada em paralelo:
 * é dado de saúde de menor e mora na tela de direitos da cantina (docs/38 §2.6).
 */
export function useAlunos({ habilitada = true }: OpcoesConsulta = {}) {
  return useQuery({
    queryKey: chaves.alunos,
    queryFn: () => api.listarAlunos(),
    enabled: habilitada,
  });
}

/** Como nomear as três colunas de média nesta carga. */
export interface RotulosDasMedias {
  /** `'2026'` — o ano letivo vigente. */
  ano: string | null;
  /** `'1º Ciclo · ITA'` — o ciclo que o servidor escolheu como o primeiro. */
  primeiroCiclo: string | null;
  ultimoCiclo: string | null;
}

/**
 * Os rótulos das três colunas de média, tirados da própria carga.
 *
 * Existe para as telas não perguntarem ao servidor uma segunda vez qual é o
 * ciclo: o rótulo viaja dentro de `aluno.medias`, junto do número que ele
 * nomeia, e é isso que impede a coluna de dizer "1º Ciclo" enquanto soma outro.
 * Aqui só se lê o primeiro aluno que já tem médias — todos carregam o mesmo
 * rótulo, porque o recorte é o mesmo para a lista inteira.
 *
 * Tudo `null` enquanto carrega, e também quando nenhum ciclo do ano começou —
 * aí a coluna existe e não tem o que nomear, e o cabeçalho degrada em vez de
 * inventar um "Ciclo 1" que ninguém aplicou.
 */
export function useRotulosDasMedias(opcoes: OpcoesConsulta = {}): RotulosDasMedias {
  const { data } = useAlunos(opcoes);
  const comMedias = (data ?? []).find((aluno) => aluno.medias?.ano.referencia != null);
  return {
    ano: comMedias?.medias?.ano.referencia ?? null,
    primeiroCiclo: comMedias?.medias?.primeiroCiclo.referencia ?? null,
    ultimoCiclo: comMedias?.medias?.ultimoCiclo.referencia ?? null,
  };
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

// ─── O dia da cantina, na coordenação (docs/39 · fase 5) ─────────────────

/** As duas refeições de um dia, cada uma podendo não existir. */
export interface DiaDaCantina {
  /** ISO `YYYY-MM-DD` — o mesmo dia que veio na URL. */
  data: string;
  /**
   * `null` = **não há cardápio** para esta refeição neste dia, que é diferente
   * de "cardápio vazio". O servidor não manda dia sem cardápio (é ele que
   * evitaria desenhar a grade do mês por nós), então a ausência é a lacuna, e é
   * a tela que a nomeia.
   */
  almoco: DiaDoCalendario | null;
  janta: DiaDoCalendario | null;
  /** Nem almoço nem janta lançados — o dia inteiro em branco. */
  vazio: boolean;
}

/**
 * O dia da cantina para a tela `/cantina/:data`.
 *
 * **Não existe rota nova para isto**, e é de propósito:
 * `GET /administracao/cantina/calendario?de=X&ate=X` já devolve as duas
 * refeições de um dia como LINHAS SEPARADAS — uma por cardápio, ordenadas por
 * (data, refeição). Pedir a janela de um dia só é a consulta do dia, e uma rota
 * dedicada seria uma segunda definição de "o que é um dia de cantina".
 *
 * O detalhe de cada refeição (blocos, contagem de produção, lista do balcão)
 * continua sendo `useCardapioNaCoordenacao(id)`, um id por vez — o `id` que
 * sai daqui é o que se passa para ele.
 *
 * ⚠️ Para o número de "quantos têm direito" a esta refeição, conte por
 * `useAlunos()` (`aluno.direitos`), **não** por `useDireitos()`: o painel de
 * direitos traz a restrição alimentar de cada aluno junto, e puxá-lo só para
 * ter uma contagem carregaria dado de saúde de menor numa tela que não o pede
 * (docs/38 §2.6).
 */
export function useDiaDaCantina(data: string | null | undefined, cantina?: string) {
  const dia = data ?? '';
  return useQuery({
    queryKey: chavesCantina.calendarioCoord(dia, dia, cantina),
    enabled: !!data,
    queryFn: () => api.calendarioNaCoordenacao(dia, dia, cantina),
    // Mesma janela do calendário do mês: a contagem de pedidos muda o dia
    // inteiro enquanto o prazo está aberto.
    staleTime: 60 * 1000,
    select: (linhas: DiaDoCalendario[]): DiaDaCantina => {
      const de = (refeicao: Refeicao) =>
        linhas.find((l) => l.data === dia && l.refeicao === refeicao) ?? null;
      const almoco = de('almoco');
      const janta = de('janta');
      return { data: dia, almoco, janta, vazio: !almoco && !janta };
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
