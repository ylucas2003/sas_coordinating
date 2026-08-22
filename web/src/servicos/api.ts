// Operações da API, tipadas. É o contrato que as telas consomem — a mesma
// superfície do `httpClient` antigo, sem o cache (agora no TanStack Query).
//
// Convenção: funções puras de I/O. Nada de estado, nada de invalidação — quem
// invalida é o hook que chama (ver src/hooks/).

import { del, get, patch, post, postArquivo, qs, streamSSE } from './http';
import type { EventoSSE, OpcoesUpload } from './http';
import type {
  Alerta, Aluno, Ciclo, ClassificacaoCiclo, CriterioClassificacao, Materia, Sede, Simulado, Turma,
} from '../tipos/dominio';

const enc = encodeURIComponent;

// ─── Autenticação ────────────────────────────────────────────────────────

export interface RespostaAutenticacao {
  access_token: string;
  tipo: string;
  nome: string;
  aluno_id?: string;
}

export const login = (corpo: { tipo: string; usuario: string; senha: string }) =>
  post<RespostaAutenticacao>('/auth/login', corpo);

/**
 * Primeiro acesso: o aluno cria a própria senha validando matrícula +
 * e-mail do Canvas. Devolve o mesmo shape do login — entra direto.
 */
export const primeiroAcesso = (corpo: { matricula: string; email: string; senha_nova: string }) =>
  post<RespostaAutenticacao>('/auth/primeiro-acesso', corpo);

// ─── Alertas ─────────────────────────────────────────────────────────────

export const listarAlertas = () => get<Alerta[]>('/alertas');
export const resolverAlerta = (id: string) => post<unknown>(`/alertas/${enc(id)}/resolver`);

// ─── Alunos (visão da coordenação) ───────────────────────────────────────

export const listarAlunos = (filtros: Record<string, string> = {}) =>
  get<Aluno[]>(`/alunos${qs(filtros)}`);
export const obterAluno = (id: string) => get<Aluno | null>(`/alunos/${enc(id)}`);
export const trajetoriaAluno = (id: string) => get<unknown[]>(`/alunos/${enc(id)}/trajetoria`);
export const heatmapAluno = (id: string) => get<unknown>(`/alunos/${enc(id)}/heatmap`);
export const alunosSimilares = (id: string, k = 5) =>
  get<unknown[]>(`/alunos/${enc(id)}/similares${qs({ k })}`);

/** Zera a senha do aluno e libera um novo primeiro acesso (ação da staff). */
export const resetarAcessoAluno = (id: string, corpo: { email?: string } = {}) =>
  post<unknown>(`/alunos/${enc(id)}/resetar-acesso`, corpo);

// ─── Aluno autenticado (visão do próprio aluno) ──────────────────────────

export const obterMe = () => get<unknown>('/me');
export const trajetoriaMe = () => get<unknown[]>('/me/trajetoria');
export const heatmapMe = () => get<unknown>('/me/heatmap');
export const streakMe = () => get<{ count: number; label: string }>('/me/streak');
export const listarSimuladosMe = () => get<unknown[]>('/me/simulados');
export const obterSimuladoMe = (id: string) => get<unknown>(`/me/simulado/${enc(id)}`);
export const questoesSimuladoMe = (id: string) => get<unknown>(`/me/simulado/${enc(id)}/questoes`);
export const evolucaoMe = () => get<{ ciclos: unknown[]; materias: unknown }>('/me/evolucao');
export const insightMe = () =>
  get<{
    disponivel: boolean;
    cicloOrdem: number | null;
    cicloNome: string | null;
    bullets: string[];
  }>('/me/insight');
export const trocarSenhaMe = (corpo: { senha_atual: string; senha_nova: string }) =>
  post<unknown>('/me/senha', corpo);

// ─── Simulados ───────────────────────────────────────────────────────────

export const listarSimulados = () => get<Simulado[]>('/simulados');
export const obterSimulado = (id: string) => get<Simulado | null>(`/simulados/${enc(id)}`);
export const histogramaSimulado = (id: string) => get<unknown>(`/simulados/${enc(id)}/histograma`);
export const notasSimulado = (id: string) => get<unknown[]>(`/simulados/${enc(id)}/notas`);
export const simuladoPorMateria = (id: string) => get<unknown[]>(`/simulados/${enc(id)}/por-materia`);
export const simuladoPorSede = (id: string) => get<unknown[]>(`/simulados/${enc(id)}/por-sede`);
export const editarSimulado = (id: string, corpo: unknown) =>
  patch<Simulado>(`/simulados/${enc(id)}`, corpo);

/** Agendamento (P1) — o simulado nasce no SAS e é espelhado no Canvas. */
export interface CorpoAgendamento {
  cicloId: string;
  rotuloCurto: string;
  materiaId: string;
  dataAplicacao: string;
  hora?: string;
  notaMaxima: number;
  tipo: string;
  lembrarDiasAntes?: number;
  avisarAlunos?: boolean;
  /** Obrigatório — a API não tem default (docs/18 §2.3). */
  sincronizarCanvas: boolean;
}

export const agendarSimulado = (corpo: CorpoAgendamento) =>
  post<Simulado>('/simulados/agendar', corpo);
/** `sincronizarCanvas` apaga também o Assignment — irreversível, leva as submissions. */
export const cancelarSimulado = (id: string, sincronizarCanvas: boolean) =>
  del<{ status: string; apagadoNoCanvas: boolean }>(`/simulados/${enc(id)}${qs({ sincronizar_canvas: sincronizarCanvas })}`);
export const retrySimuladoCanvas = (id: string) =>
  post<unknown>(`/simulados/${enc(id)}/retry-canvas`);

// ─── Notas ───────────────────────────────────────────────────────────────

/** O que o diálogo devolve; a API fala snake_case. */
export interface CorpoEdicaoNota {
  pontuacao: number | null;
  presente: boolean;
  sincronizarCanvas: boolean;
}

export interface RespostaEdicaoNota {
  alunoId: string;
  simuladoId: string;
  pontuacao: number | null;
  presente: boolean;
  gravadoNoCanvas: boolean;
  canvasErro: string | null;
}

export const editarNota = (alunoId: string, simuladoId: string, corpo: CorpoEdicaoNota) =>
  patch<RespostaEdicaoNota>(`/notas/${enc(alunoId)}/${enc(simuladoId)}`, {
    pontuacao: corpo.pontuacao,
    presente: corpo.presente,
    sincronizar_canvas: corpo.sincronizarCanvas,
  });

// ─── Ciclos ──────────────────────────────────────────────────────────────

export const listarCiclos = () => get<Ciclo[]>('/ciclos');
export const obterCiclo = (id: string) => get<Ciclo | null>(`/ciclos/${enc(id)}`);
/**
 * Classificação do ciclo por um critério (Tio Leo, ITA, IME). A regra mora no
 * servidor; aqui chega veredito, motivo, cor e posição prontos.
 */
export const classificacaoCiclo = (id: string, criterio: string, fase?: 1 | 2) =>
  get<ClassificacaoCiclo>(`/ciclos/${enc(id)}/classificacao${qs({ criterio, fase })}`);
export const criteriosDisponiveis = () => get<CriterioClassificacao[]>('/ciclos/criterios/disponiveis');
export const estatisticasCiclo = (id: string, { comInsights = true } = {}) =>
  get<unknown>(`/ciclos/${enc(id)}/estatisticas${comInsights ? '' : '?com_insights=false'}`);
export const enviarCicloAoCanvas = (id: string) =>
  post<{ canvas_estado: string; erro?: string }>(`/ciclos/${enc(id)}/enviar-canvas`, {});
export const criarCiclo = (corpo: { ordem: number; vestibular: string; ano?: number; sincronizar_canvas: boolean }) =>
  post<Ciclo>('/ciclos', corpo);

// ─── Dimensões ───────────────────────────────────────────────────────────

export const listarSedes = () => get<Sede[]>('/sedes');
export const listarTurmas = () => get<Turma[]>('/turmas');
export const listarMaterias = () => get<Materia[]>('/materias');

// ─── Uploads de planilha ─────────────────────────────────────────────────

export const enviarPlanilha = (
  arquivo: File,
  { autor, ...resto }: { autor?: string } & OpcoesUpload = {},
) => postArquivo<unknown>('/uploads', arquivo, { campos: { autor }, ...resto });

export const listarUploads = () => get<unknown[]>('/uploads');
export const obterUpload = (id: string) => get<unknown>(`/uploads/${enc(id)}`);

// ─── Chat ────────────────────────────────────────────────────────────────

export const listarChatThreads = ({ incluirArquivadas = false } = {}) =>
  get<unknown[]>(`/chat/threads${incluirArquivadas ? '?incluir_arquivadas=true' : ''}`);
export const criarChatThread = (titulo?: string) =>
  post<unknown>('/chat/threads', { titulo: titulo ?? null });
export const obterChatThread = (id: string) => get<unknown>(`/chat/threads/${enc(id)}`);
export const atualizarChatThread = (id: string, remendo: unknown) =>
  patch<unknown>(`/chat/threads/${enc(id)}`, remendo);
export const apagarChatThread = (id: string) => del<unknown>(`/chat/threads/${enc(id)}`);

/** Envia a mensagem e streama a resposta do agente. Resolve no fim do stream. */
export const enviarChatMensagem = (
  threadId: string,
  conteudo: string,
  onEvento: (evento: EventoSSE) => void,
) => streamSSE(`/chat/threads/${enc(threadId)}/mensagens`, { conteudo }, onEvento);
