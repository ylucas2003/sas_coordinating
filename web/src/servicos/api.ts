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
  PainelAcessos, PainelGravacoes, PapelCoordenacao, PendenciasCanvas, ResultadoLoteCanvas, Sede,
  Simulado, Turma, UsuarioCoordenacao,
} from '../tipos/dominio';
import type {
  CantinaAdmin, CantinaDoAluno, Cardapio, ContaDeCantina, ContagemDeOpcao, ContagemDoCardapio,
  ContagemPresencial, DiaDoCalendario, MinhaCantina, PainelDeDireitos, PedidoDeAluno, Refeicao,
  RetiradaConfirmada, TokenDeRetirada,
} from '../tipos/cantina';
import { normalizarContagem } from '../dominio/cantina';

const enc = encodeURIComponent;

// ─── Autenticação ────────────────────────────────────────────────────────

export interface RespostaAutenticacao {
  access_token: string;
  /** 'aluno' | 'coordenador' | 'cantina' — o tipo da SESSÃO. */
  tipo: string;
  /** Só do login da coordenação: 'coordenador' ou 'administrador' (0045). */
  papel?: string | null;
  nome: string;
  aluno_id?: string | null;
  temFoto: boolean;
  /** Só do login da cantina: o nome do estabelecimento, para o casco exibir. */
  cantina?: string | null;
}

/** O SSO pelo Canvas só aparece na tela se o servidor tiver a Developer Key. */
export const ssoCanvasDisponivel = () => get<{ disponivel: boolean }>('/auth/canvas/disponivel');

/** `tipo` decide contra qual tabela o servidor autentica: 'coordenador' →
    `usuario_coordenacao` (0021), 'cantina' → `usuario_cantina` (0047). 'aluno'
    é recusado com uma mensagem que manda para o Canvas. */
export const login = (corpo: { tipo: string; usuario: string; senha: string }) =>
  post<RespostaAutenticacao>('/auth/login', corpo);

// `primeiroAcesso` SAIU em 04/09 (docs/35 §11.5), com a rota
// `POST /auth/primeiro-acesso` que ela chamava: o aluno entra só pelo Canvas e
// não há senha de aluno para criar. Ver `routes/auth.py` para a lápide do lado
// do servidor.

// ─── Alertas ─────────────────────────────────────────────────────────────

export const listarAlertas = () => get<Alerta[]>('/alertas');
export const resolverAlerta = (id: string) => post<unknown>(`/alertas/${enc(id)}/resolver`);
/** O desfazer do cartão resolvido (docs/39 §3, fase 1). Não cria alerta novo:
    reabre a MESMA linha e limpa a hora do resolver. */
export const reabrirAlerta = (id: string) => post<unknown>(`/alertas/${enc(id)}/reabrir`);

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
// `streakMe` SAIU em 05/09 com `GET /me/streak` (docs/36 §4). Ela media
// "ciclos consecutivos acima da média da turma" — relativa, premiava posição e
// não progresso (docs/24 §1.1). Quem responde por sequência agora é `jogoMe`,
// e ela conta simulados sem faltar.
export const listarSimuladosMe = () => get<unknown[]>('/me/simulados');
/** Os simulados COM as faltas juntas — os quadrados vazados da corrente. */
export const listarSimuladosComFaltasMe = () =>
  get<unknown[]>('/me/simulados?incluirFaltas=true');
export const jogoMe = () => get<unknown>('/me/jogo');
export const agendaMe = () => get<unknown>('/me/agenda');
export const metaMe = () => get<unknown>('/me/meta');
export const zonaMe = () => get<unknown>('/me/zona');
export const vestibularesMe = () =>
  get<{ vestibulares: string[]; completo: boolean }>('/me/vestibulares');
export const definirVestibularesMe = (vestibulares: string[]) =>
  put<{ vestibulares: string[]; completo: boolean }>('/me/vestibulares', { vestibulares });
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
/**
 * Promover a administrador ou rebaixar a coordenador.
 *
 * Rota SEPARADA do `editarCoordenador` de propósito: é a ação mais cara da
 * tela — administrador cria login e altera nota —, e um `papel` perdido num
 * corpo de "renomear" não pode promover ninguém de lado.
 */
export const alterarPapelDoCoordenador = (id: string, papel: PapelCoordenacao) =>
  patch<Pick<UsuarioCoordenacao, 'id' | 'email' | 'nome' | 'ativo' | 'papel'>>(
    `/administracao/coordenadores/${enc(id)}/papel`, { papel },
  );
export const redefinirSenhaCoordenador = (id: string) =>
  post<{ id: string; senha_nova: string }>(`/administracao/coordenadores/${enc(id)}/redefinir-senha`, {});
export const acessosDeAlunos = () => get<PainelAcessos>('/administracao/alunos-acesso');
export const fotoDeCoordenador = (id: string) =>
  get<RespostaFoto>(`/administracao/coordenadores/${enc(id)}/foto`);

// ─── Cantina (docs/38) ───────────────────────────────────────────────────
//
// Três públicos, três blocos, e a separação espelha a dos routers no servidor:
// quem chama o quê é a primeira coisa que se quer saber ao ler isto.

// A cantina — sessão `tipo: "cantina"`, casco próprio.
export const calendarioDaCantina = (de: string, ate: string) =>
  get<DiaDoCalendario[]>(`/cantina/calendario${qs({ de, ate })}`);
export const obterCardapio = (id: string) => get<Cardapio>(`/cantina/cardapios/${enc(id)}`);
export const criarCardapio = (corpo: { data: string; refeicao: Refeicao }) =>
  post<Cardapio>('/cantina/cardapios', corpo);
export const salvarCardapio = (id: string, corpo: CorpoCardapio) =>
  put<Cardapio>(`/cantina/cardapios/${enc(id)}`, corpo);
export const publicarCardapio = (id: string) =>
  post<Cardapio>(`/cantina/cardapios/${enc(id)}/publicar`, {});
/** ⚠️ Não leva o prazo junto: o servidor recalcula pela regra da casa para a
    data nova, senão a terça nasceria com o prazo vencido da segunda. */
export const copiarCardapio = (id: string, origemId: string) =>
  post<Cardapio>(`/cantina/cardapios/${enc(id)}/copiar-de`, { origem_id: origemId });
/** Quantos alunos podem pedir cada refeição. Zero = cardápio sem público —
    aviso, nunca impedimento (docs/38 §3.3.2). */
export const publicoDaCantina = () => get<Record<Refeicao, number>>('/cantina/publico');
/** O estabelecimento da sessão — nome, regra de prazo e preço de tabela. */
export const minhaCantina = () => get<MinhaCantina>('/cantina/eu');
/**
 * A contagem, e ela é a única rota da cantina que MUDOU DE FORMA (docs/40 §7).
 *
 * Era uma lista; virou objeto, porque o bloco de presencial não tem onde caber
 * dentro de um array. `normalizarContagem` aceita as duas formas de propósito:
 * o front e o backend desta feature sobem em ordens diferentes, e uma tela que
 * quebra com `[] .map is not a function` durante a janela entre os dois deploys
 * é um susto sem informação nenhuma.
 */
export const contagemDoCardapio = (id: string): Promise<ContagemDoCardapio> =>
  get<ContagemDeOpcao[] | ContagemDoCardapio>(`/cantina/cardapios/${enc(id)}/contagem`)
    .then(normalizarContagem);
export const pedidosDoCardapio = (id: string) =>
  get<PedidoDeAluno[]>(`/cantina/cardapios/${enc(id)}/pedidos`);

export interface CorpoCardapio {
  pedidos_ate: string | null;
  sem_refeicao: boolean;
  /**
   * ⚠️ snake_case aqui, camelCase na LEITURA (`Cardapio.aceitaPedido`). É o
   * contrato da rota — ver o comentário do tipo.
   *
   * O servidor trata a AUSÊNCIA como "não mexi neste campo", para um editor
   * antigo não desligar o presencial a cada salvamento. Este editor manda os
   * dois sempre, porque ele CONHECE os dois: aqui a ausência seria descuido,
   * não compatibilidade.
   */
  aceita_pedido: boolean;
  aceita_presencial: boolean;
  /** O estado FINAL: o que tem `id` é atualizado, o que não tem é criado, e o
      que sumiu é apagado. A ordem da lista vira a coluna `ordem`. */
  blocos: Array<{
    id?: string;
    nome: string;
    escolhas_minimas: number;
    escolhas_maximas: number;
    opcoes: Array<{ id?: string; nome: string; disponivel: boolean }>;
  }>;
}

// O aluno — rotas /me, com o `aluno_id` saindo do JWT.
export const cantinaDoAluno = () => get<CantinaDoAluno>('/me/cantina');
export const salvarPedido = (cardapioId: string, opcaoIds: string[]) =>
  put<{ cardapioId: string; opcaoIds: string[] }>(`/me/cantina/pedidos/${enc(cardapioId)}`, {
    opcao_ids: opcaoIds,
  });
export const cancelarPedido = (cardapioId: string) =>
  del<{ cardapioId: string }>(`/me/cantina/pedidos/${enc(cardapioId)}`);

/**
 * A retirada presencial do aluno (docs/40 §3).
 *
 * `iniciarRetirada` CRIA OU RENOVA — chamá-la de novo sobre a mesma linha é o
 * caminho normal, não um erro: é assim que o token de 2 minutos se renova
 * enquanto o QR está na tela. Ela não olha `pedidos_ate`: presencial é
 * justamente o caminho de quem não se planejou.
 */
export const iniciarRetirada = (cardapioId: string) =>
  post<TokenDeRetirada>(`/me/cantina/retiradas/${enc(cardapioId)}`, {});
/** Desistir — só enquanto ninguém leu o QR. Depois de `retirado_em`, o
    servidor recusa: o aluno já comeu, e não há desfazer. */
export const desistirDaRetirada = (cardapioId: string) =>
  del<{ ok: boolean }>(`/me/cantina/retiradas/${enc(cardapioId)}`);

// A leitura do QR, do lado da cantina — sessão `tipo: "cantina"`.
/** 409 = já retirado · 422 = token inválido ou vencido · 403 = outra cantina.
    Os três chegam como `ErroApi` com a frase do servidor; quem os traduz para
    a tela é `dominio/cantina.ts::lerRespostaDoQr`. */
export const confirmarRetirada = (token: string) =>
  post<RetiradaConfirmada>('/cantina/retiradas/confirmar', { token });

// A coordenação — leitura do cardápio, e a administração do direito e das
// contas. As de escrita são todas do administrador; o 403 vem do servidor, e a
// tela esconde o botão antes disso.
/** `cantina` vazio = a primeira ativa, que hoje é a única. O parâmetro existe
    para o dia em que houver duas, e para a tela não precisar mudar quando
    houver (docs/38 §8.1.1). */
export const calendarioNaCoordenacao = (de: string, ate: string, cantina?: string) =>
  get<DiaDoCalendario[]>(`/administracao/cantina/calendario${qs({ de, ate, ...(cantina ? { cantina } : {}) })}`);
/**
 * ⚠️ `presencial` é OPCIONAL de propósito, e a rota o manda desde a leva da
 * retirada na hora (docs/40 §10.1). Quem lê a tela contra um servidor anterior
 * simplesmente não o recebe — e `presencialDoCardapio` cai na lista de pedidos,
 * que já vem aqui, em vez de a coluna "O que cozinhar" dizer "nenhum pedido"
 * ao lado de doze nomes.
 */
export const cardapioNaCoordenacao = (id: string) =>
  get<Cardapio & {
    contagem: ContagemDeOpcao[];
    presencial?: ContagemPresencial | null;
    pedidos: PedidoDeAluno[];
  }>(`/administracao/cantina/cardapios/${enc(id)}`);
export const listarDireitos = () => get<PainelDeDireitos>('/administracao/direito-refeicao');
/** Um aluno ou oitenta, pela mesma rota — a concessão em lote existe porque só
    o administrador concede (docs/38 §3.4). */
export const conceberDireito = (corpo: { aluno_ids: string[]; refeicao: Refeicao; conceder: boolean }) =>
  post<{ alterados: number }>('/administracao/direito-refeicao', corpo);
export const salvarRestricaoAlimentar = (alunoId: string, restricao: string | null) =>
  put<{ id: string; restricaoAlimentar: string | null }>(
    `/administracao/alunos/${enc(alunoId)}/restricao-alimentar`,
    { restricao },
  );
export const listarCantinas = () => get<CantinaAdmin[]>('/administracao/cantinas');
/**
 * ⚠️ Os quatro `aceita_*` são a REGRA da casa, irmãos de `prazo_padrao_*`
 * (docs/40 §1): pré-preenchem o cardápio NOVO e não tocam em cardápio lançado.
 *
 * Opcionais nos dois corpos porque a ausência significa coisas diferentes e
 * úteis dos dois lados: no `POST` ela cai no default da 0051, no `PATCH` ela
 * quer dizer "não mexi neste campo".
 */
export const criarCantina = (corpo: {
  nome: string; prazo_padrao_dias_antes?: number; prazo_padrao_hora?: string;
  valor_almoco?: number | null; valor_janta?: number | null;
  aceita_pedido_almoco?: boolean; aceita_pedido_janta?: boolean;
  aceita_presencial_almoco?: boolean; aceita_presencial_janta?: boolean;
}) =>
  post<CantinaAdmin>('/administracao/cantinas', corpo);
export const editarCantina = (
  id: string,
  corpo: {
    nome?: string; ativo?: boolean; prazo_padrao_dias_antes?: number;
    prazo_padrao_hora?: string; valor_almoco?: number | null; valor_janta?: number | null;
    aceita_pedido_almoco?: boolean; aceita_pedido_janta?: boolean;
    aceita_presencial_almoco?: boolean; aceita_presencial_janta?: boolean;
  },
) => patch<CantinaAdmin>(`/administracao/cantinas/${enc(id)}`, corpo);
export const criarContaDeCantina = (corpo: { cantina_id: string; email: string; nome: string }) =>
  post<ContaDeCantina & { senha_inicial: string }>('/administracao/usuarios-cantina', corpo);
export const editarContaDeCantina = (id: string, corpo: { nome?: string; ativo?: boolean }) =>
  patch<ContaDeCantina>(`/administracao/usuarios-cantina/${enc(id)}`, corpo);
export const redefinirSenhaDeCantina = (id: string) =>
  post<{ id: string; senha_nova: string }>(`/administracao/usuarios-cantina/${enc(id)}/redefinir-senha`, {});

// ─── Integrações · gravações de aula ─────────────────────────────────────

/** Cursos e aulas numa chamada só — a tela filtra em memória. */
export const painelGravacoes = () => get<PainelGravacoes>('/gravacoes-aula');
