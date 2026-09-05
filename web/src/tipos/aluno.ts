// Tipos das rotas /me — a visão que o próprio aluno tem dos seus dados.
// Espelham api/app/stats/aluno_dados.py e api/app/routes/me.py.

export interface SimuladoDoAluno {
  id: string;
  nome: string | null;
  rotulo: string | null;
  dataAplicacao: string | null;
  tipo: string | null;
  materia: string | null;
  nota: number;
  /** Sempre `true` aqui — `GET /me/simulados` só devolve o que o aluno fez. */
  presente: true;
  /** Diferença para a própria média histórica até aquele momento. */
  deltaSelf: number | null;
  mediaGeral: number | null;
  nPresentes: number;
  cicloId: string | null;
  cicloOrdem: number | null;
  vestibularAlvo: string | null;
  /** Marca o simulado mais recente. */
  novo: boolean;
}

/**
 * Um simulado que o aluno NÃO fez — o quadrado vazado da corrente.
 *
 * Só aparece em `GET /me/simulados?incluirFaltas=true`. Sem nota e sem delta
 * porque ausência não é desempenho: somá-la como zero puxaria a régua do aluno
 * para baixo por não ter feito a prova (docs/36 §2.1).
 */
export interface FaltaDoAluno
  extends Omit<SimuladoDoAluno, 'nota' | 'presente' | 'deltaSelf' | 'novo'> {
  nota: null;
  presente: false;
  deltaSelf: null;
  novo: false;
}

/** Discrimina por `presente` — o TypeScript estreita sozinho no `if`. */
export type SimuladoOuFalta = SimuladoDoAluno | FaltaDoAluno;

export interface GruposComparacao {
  voce: number | null;
  geral: number | null;
  top15: number | null;
  bottom15: number | null;
}

export interface DetalheSimuladoAluno {
  id: string;
  nome: string | null;
  rotulo: string | null;
  dataAplicacao: string | null;
  tipo: string | null;
  materia: string | null;
  vestibularAlvo: string | null;
  nota: number;
  deltaSelf: number | null;
  posicao: number;
  total: number;
  percentil: number;
  grupos: GruposComparacao | null;
}

export type ResultadoQuestao = 'correta' | 'errada' | 'em_branco';

export interface QuestaoDoAluno {
  posicao: number | null;
  resultado: ResultadoQuestao;
  textoResumo?: string | null;
  assunto?: string | null;
  alternativaCorreta?: string | null;
}

export interface QuestoesDoSimulado {
  temGabarito: boolean;
  temMinhasRespostas: boolean;
  questoes: QuestaoDoAluno[];
  acertos: number;
  erros: number;
  emBranco: number;
  duracaoMediaSegundos: number | null;
}

export interface EvolucaoAluno {
  ciclos: Array<{ label: string }>;
  /** Uma entrada por matéria; os arrays são paralelos a `ciclos`. */
  materias: Record<string, { aluno: Array<number | null>; turma: Array<number | null> }>;
}

export interface InsightDoAluno {
  disponivel: boolean;
  cicloOrdem: number | null;
  cicloNome: string | null;
  bullets: string[];
}
