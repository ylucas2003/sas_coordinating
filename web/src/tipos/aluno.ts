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

export interface Streak {
  count: number;
  label: string;
}

export interface InsightDoAluno {
  disponivel: boolean;
  cicloOrdem: number | null;
  cicloNome: string | null;
  bullets: string[];
}
