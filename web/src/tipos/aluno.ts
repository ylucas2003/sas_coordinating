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
  /**
   * A média da turma nesta prova. `null` sem métrica e, desde 26/10, com menos
   * de 10 notas — o PISO DE ANONIMATO do servidor (`PISO_DE_ANONIMATO`,
   * api/app/stats/aluno_dados.py): com duas pessoas na prova, a média da turma
   * menos a sua nota é a nota do colega. Quem mostrar tem de dizer por quê.
   */
  mediaGeral: number | null;
  /** Quantas notas a prova tem. Fica mesmo abaixo do piso: é ela que explica o `null`. */
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

/**
 * A comparação com a turma num simulado — médias de GRUPO, nunca a nota de um
 * colega (docs/27 §9, regra 4).
 *
 * ⚠️ O `null` aqui é o PISO DE ANONIMATO do servidor (`PISO_DE_ANONIMATO` e
 * `MINIMO_DO_GRUPO_DE_15`, api/app/stats/aluno_dados.py), e não dado faltando:
 * com pouca gente na prova, "a média da turma" é a nota de colegas com uma
 * conta de diferença. Quem mostra tem de dizer POR QUE o número não está lá, e
 * não sumir com ele em silêncio.
 */
export interface GruposComparacao {
  voce: number | null;
  /** `null` com menos de 10 notas na prova. */
  geral: number | null;
  /**
   * `null` com menos de 10 notas, OU quando o grupo de 15% teria menos de 3
   * pessoas (até 19 notas): a "média do top 15%" seria a nota do melhor da sala.
   */
  top15: number | null;
  /** O mesmo piso de `top15`, pelo mesmo motivo — a nota do último da sala. */
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
  /**
   * `null` com menos de 10 notas na prova — o mesmo piso de `grupos.geral`,
   * desde 26/10: com duas notas, "2º de 2" diz que o colega tirou mais. É
   * comparação com uma pessoa, não com a turma.
   */
  posicao: number | null;
  /** Quantas notas a prova tem. Fica mesmo abaixo do piso: é ela que explica o `null`. */
  total: number;
  /** O mesmo piso de `posicao`, pelo mesmo motivo. */
  percentil: number | null;
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
  /**
   * O tempo médio da TURMA na prova. `null` sem o dado do Canvas e, desde
   * 26/10, abaixo do mesmo piso de anonimato da ficha: com duas pessoas, é o
   * tempo do colega a uma conta de distância. A ficha já cala o `null`.
   */
  duracaoMediaSegundos: number | null;
}

export interface EvolucaoAluno {
  ciclos: Array<{ label: string }>;
  /**
   * Uma entrada por matéria; os arrays são paralelos a `ciclos`.
   *
   * ⚠️ `turma[i]` `null` com `aluno[i]` preenchido é o PISO DE ANONIMATO, desde
   * 26/10: a média de prova com menos de 10 notas não entra no lado da turma.
   * Não é "a turma não fez a prova" — é "não dá para mostrar sem expor colegas".
   */
  materias: Record<string, { aluno: Array<number | null>; turma: Array<number | null> }>;
}

export interface InsightDoAluno {
  disponivel: boolean;
  cicloOrdem: number | null;
  cicloNome: string | null;
  bullets: string[];
}
