// Operações da API, tipadas. É o contrato que as telas consomem — a mesma
// superfície do `httpClient` antigo, sem o cache (agora no TanStack Query).
//
// Convenção: funções puras de I/O. Nada de estado, nada de invalidação — quem
// invalida é o hook que chama (ver src/hooks/).

import { del, get, patch, post, put, qs, streamSSE } from './http';
import type { ContextoDaTela } from '../dominio/contextoDaTela';
import type { EventoSSE } from './http';
import type {
  Alerta, Aluno, Ciclo, ClassificacaoCiclo, CriterioClassificacao, Materia, PaginaAuditoria,
  PainelAcessos, PainelGravacoes, PendenciasCanvas, ResultadoLoteCanvas, Sede, Simulado, Turma,
  UsuarioCoordenacao,
} from '../tipos/dominio';

const enc = encodeURIComponent;

// ─── Autenticação ────────────────────────────────────────────────────────

export interface RespostaAutenticacao {
  access_token: string;
  tipo: string;
  nome: string;
  aluno_id?: string;
  temFoto: boolean;
}

/** O SSO pelo Canvas só aparece na tela se o servidor tiver a Developer Key. */
export const ssoCanvasDisponivel = () => get<{ disponivel: boolean }>('/auth/canvas/disponivel');

export const login = (corpo: { tipo: string; usuario: string; senha: string }) =>
  post<RespostaAutenticacao>('/auth/login', corpo);

// `primeiroAcesso` SAIU em 04/09 (docs/35 §11.5), com a rota
// `POST /auth/primeiro-acesso` que ela chamava: o aluno entra só pelo Canvas e
// não há senha de aluno para criar. Ver `routes/auth.py` para a lápide do lado
// do servidor.

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

// `resetarAcessoAluno` SAIU em 04/09 com `POST /alunos/{id}/resetar-acesso`
// (docs/35 §11.5, lápide em `routes/alunos.py`). Aluno sem acesso é aluno sem
// `canvas_user_id`, e isso se resolve no Canvas — a listagem de quem entra
// continua em `acessosDeAlunos`, mais abaixo.

export interface RespostaFoto {
  fotoDataUrl: string | null;
}

export const fotoDeAluno = (id: string) => get<RespostaFoto>(`/alunos/${enc(id)}/foto`);
/** Tira uma foto imprópria do ar (ação da staff) — o titular usa removerMinhaFoto. */
export const removerFotoDeAluno = (id: string) => del<{ ok: true }>(`/alunos/${enc(id)}/foto`);

// ─── Aluno autenticado (visão do próprio aluno) ──────────────────────────

export const obterMe = () => get<unknown>('/me');
export const trajetoriaMe = () => get<unknown[]>('/me/trajetoria');
export const heatmapMe = () => get<unknown>('/me/heatmap');
export const streakMe = () => get<{ count: number; label: string }>('/me/streak');
export const listarSimuladosMe = () => get<unknown[]>('/me/simulados');
export const obterSimuladoMe = (id: string) => get<unknown>(`/me/simulado/${enc(id)}`);
export const questoesSimuladoMe = (id: string) => get<unknown>(`/me/simulado/${enc(id)}/questoes`);
// `arquivoSimuladoMe` SAIU em 04/09 com `GET /me/simulado/{id}/arquivo`
// (docs/35 §8b) — ela devolvia URL assinada do PDF da prova, e este projeto já
// teve vulnerabilidade nascida de token de download (PR #7). A lápide inteira
// está no docstring de `routes/me.py`.
export const evolucaoMe = () => get<{ ciclos: unknown[]; materias: unknown }>('/me/evolucao');
export const insightMe = () =>
  get<{
    disponivel: boolean;
    cicloOrdem: number | null;
    cicloNome: string | null;
    bullets: string[];
  }>('/me/insight');
// `trocarSenhaMe` SAIU em 04/09 com `POST /me/senha` (docs/35 §11.5): sem
// senha de aluno, a folha só sabia responder "Senha atual incorreta".

/**
 * Foto de perfil — a MESMA rota para aluno e coordenação (routes/foto_perfil.py
 * lê o tipo do JWT). `conteudo_base64` já vem cropado/redimensionado do
 * `FotoPerfilEditor`; a foto nunca sai por URL, só embutida na resposta.
 */
export const minhaFoto = () => get<RespostaFoto>('/me/foto');
export const salvarMinhaFoto = (corpo: {
  conteudo_base64: string;
  content_type: string;
  declaracao_autorizacao: true;
}) => put<{ ok: true }>('/me/foto', corpo);
export const removerMinhaFoto = () => del<{ ok: true }>('/me/foto');

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

// ─── Réguas de corte criadas pela coordenação (docs/31 §P4) ──────────────

export interface PredicadoEntrada {
  materia: string | null;
  operador: string;
  valor_nota?: number | null;
  valor_acertos?: number | null;
  valor_de?: number | null;
  eliminatorio?: boolean;
  entra_na_media?: boolean;
  peso?: number;
  fonte?: string | null;
}

export interface CorpoCriterio {
  slug: string;
  nome: string;
  descricao?: string | null;
  combinador: 'todos' | 'algum';
  fase?: 1 | 2 | null;
  desempate?: string[];
  predicados: PredicadoEntrada[];
}

export interface PreviaCriterio {
  total: number;
  cortados: number;
  exemplos: Array<{ nome: string; motivo: string | null }>;
}

/** Avalia a régua contra um ciclo SEM gravar — é o rascunho, não a régua. */
export const previaCriterio = (corpo: CorpoCriterio, cicloId: string, fase?: 1 | 2) =>
  post<PreviaCriterio>(`/criterios/previa${qs({ ciclo_id: cicloId, fase })}`, corpo);

export const criarCriterio = (corpo: CorpoCriterio) =>
  post<{ slug: string; versao: number; nome: string }>('/criterios', corpo);

/** Editar cria a versão seguinte; a anterior fica inativa, não some. */
export const editarCriterio = (slug: string, corpo: Omit<CorpoCriterio, 'slug'>) =>
  patch<{ slug: string; versao: number; nome: string }>(`/criterios/${enc(slug)}`, corpo);

export const desativarCriterio = (slug: string) =>
  del<{ slug: string; ativo: boolean }>(`/criterios/${enc(slug)}`);
/**
 * `criterio` decide os cortes do payload inteiro — a linha vertical de cada
 * histograma e o pctAprovados de cada bloco. Omitir usa a régua da casa.
 */
export const estatisticasCiclo = (
  id: string,
  { comInsights = true, criterio }: { comInsights?: boolean; criterio?: string } = {},
) =>
  get<unknown>(
    `/ciclos/${enc(id)}/estatisticas${qs({ com_insights: comInsights ? undefined : 'false', criterio })}`,
  );
/** O que subiria se o ciclo inteiro fosse enviado. Leitura, sem efeito. */
export const pendenciasCanvasDoCiclo = (id: string) =>
  get<PendenciasCanvas>(`/ciclos/${enc(id)}/pendencias-canvas`);

/** Manda o ciclo inteiro: grupo → simulados → notas, com resultado por item. */
export const enviarCicloAoCanvasEmLote = (id: string) =>
  post<ResultadoLoteCanvas>(`/ciclos/${enc(id)}/enviar-canvas-lote`, {});

export const enviarCicloAoCanvas = (id: string) =>
  post<{ canvas_estado: string; erro?: string }>(`/ciclos/${enc(id)}/enviar-canvas`, {});
export const criarCiclo = (corpo: { ordem: number; vestibular: string; ano?: number; sincronizar_canvas: boolean }) =>
  post<Ciclo>('/ciclos', corpo);

// ─── Dimensões ───────────────────────────────────────────────────────────

export const listarSedes = () => get<Sede[]>('/sedes');
export const listarTurmas = () => get<Turma[]>('/turmas');
export const listarMaterias = () => get<Materia[]>('/materias');

// ─── Uploads de planilha — só leitura ────────────────────────────────────
//
// `enviarPlanilha` saiu em 03/09/2026: `POST /uploads` responde 410 e a
// entrada por planilha virou script (docs/32 §2.4). As duas leituras ficam
// porque o histórico de importações é dado de auditoria.

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
/**
 * `contexto` diz em que tela o usuário estava ao mandar a mensagem — é o que
 * dá referente a "e esse aluno?". Vai por turno, e não uma vez por thread,
 * porque o painel convive com a navegação: dá para trocar de tela três vezes
 * dentro da mesma conversa.
 */
export const enviarChatMensagem = (
  threadId: string,
  conteudo: string,
  onEvento: (evento: EventoSSE) => void,
  contexto?: ContextoDaTela | null,
) => streamSSE(
  `/chat/threads/${enc(threadId)}/mensagens`,
  contexto ? { conteudo, contexto } : { conteudo },
  onEvento,
);

// ─── Auditoria ───────────────────────────────────────────────────────────

export interface FiltroAuditoria {
  canal?: string;
  ator_id?: string;
  recurso?: string;
  desde?: string;
  ate?: string;
  limite?: number;
  antes_de_id?: number;
  incluir_logins?: boolean;
}

export const listarAuditoria = (filtro: FiltroAuditoria) =>
  get<PaginaAuditoria>(`/auditoria${qs({ ...filtro })}`);

// ─── Administração ───────────────────────────────────────────────────────

export const listarCoordenadores = () => get<UsuarioCoordenacao[]>('/administracao/coordenadores');
export const criarCoordenador = (corpo: { email: string; nome: string; canvas_user_id?: string }) =>
  post<UsuarioCoordenacao & { senha_inicial: string }>('/administracao/coordenadores', corpo);
export const editarCoordenador = (id: string, corpo: { nome?: string; ativo?: boolean; canvas_user_id?: string }) =>
  patch<UsuarioCoordenacao>(`/administracao/coordenadores/${enc(id)}`, corpo);
/** O SAS procura o id do Canvas pelo e-mail da conta — ninguém digita número. */
export const ligarCoordenadorAoCanvas = (id: string) =>
  post<{ id: string; canvas_user_id: string }>(`/administracao/coordenadores/${enc(id)}/ligar-canvas`, {});
export const redefinirSenhaCoordenador = (id: string) =>
  post<{ id: string; senha_nova: string }>(`/administracao/coordenadores/${enc(id)}/redefinir-senha`, {});
export const acessosDeAlunos = () => get<PainelAcessos>('/administracao/alunos-acesso');
export const fotoDeCoordenador = (id: string) =>
  get<RespostaFoto>(`/administracao/coordenadores/${enc(id)}/foto`);

// ─── Integrações · gravações de aula ─────────────────────────────────────

/** Cursos e aulas numa chamada só — a tela filtra em memória. */
export const painelGravacoes = () => get<PainelGravacoes>('/gravacoes-aula');
