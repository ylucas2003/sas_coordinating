// Tipos do domínio do SAS.
//
// Espelham os schemas Pydantic em `api/app/schemas/domain.py` — quando um
// campo mudar lá, muda aqui. Substituem o bloco `@typedef` em JSDoc que vivia
// em `js/services/api.js`.
//
// Documentação dos campos: `docs/05-data-and-stats.md`.

export type Modalidade = 'presencial' | 'online';
export type Vestibular = 'ITA' | 'IME' | 'AFA' | 'EsPCEx' | 'EFOMM';
/** Apenas os 2 vestibulares no escopo do MVP. */
export type VestibularAlvo = 'ITA' | 'IME';
export type Perfil = 'ancora' | 'misterio' | 'regular';
export type Tendencia = 'subindo' | 'estavel' | 'caindo';
export type Zona = 'top' | 'cinzenta' | 'risco';
export type Severidade = 'vermelho' | 'ambar' | 'verde' | 'cinza';
export type TipoSimulado = 'fase_1' | 'fase_2';

export type CategoriaAlerta =
  | 'QUEDA_RENDIMENTO'
  | 'SUBIDA_ATIPICA'
  | 'PROVA_MAL_CALIBRADA'
  | 'MATERIA_EM_RISCO'
  | 'DIFERENCA_ENTRE_SEDES'
  | 'PANORAMA_CICLO'
  | 'ZONA_TRANSICAO';

export interface Sede {
  id: string;
  nome: string;
  modalidade: Modalidade;
}

export interface Turma {
  id: string;
  nome: string;
  sedeId: string;
  anoLetivo: number;
}

export interface Materia {
  id: string;
  codigo: string;
  nome: string;
}

export interface MateriaResumo {
  codigo: string;
  nome: string;
}

export interface Aluno {
  id: string;
  nome: string;
  turmaId: string;
  sedeId: string;
  vestibularesAlvo: Vestibular[];
  ativo: boolean;
  /** E-mail do Canvas — valida o primeiro acesso. */
  email: string | null;
  perfil: Perfil;
  tendencia: Tendencia;
  zona: Zona;
  media: number | null;
  sparkline: number[];
}

export interface Ciclo {
  id: string;
  nome: string;
  anoLetivo: number;
  vestibularAlvo: VestibularAlvo | null;
  periodoInicio: string;
  periodoFim: string;
  simuladoIds: string[];
}

export interface Simulado {
  id: string;
  /** Nome original vindo do Canvas — preservado para debug e para a ficha. */
  nome: string;
  /** "P38", "P22". */
  rotuloCurto: string | null;
  tipo: TipoSimulado | null;
  /** `null` nas provas agregadas. */
  materia: MateriaResumo | null;
  dataAplicacao: string;
  cicloId: string;
  cicloOrdem: number | null;
  vestibularAlvo: VestibularAlvo | null;
  notaMaxima: number;
  anulado: boolean;
  origem: 'canvas' | 'sas';
  /**
   * Sincronização SAS→Canvas (só relevante em `origem: 'sas'`). 'pendente' e
   * 'falhou' significam que o Assignment ainda não existe ou não reflete o
   * SAS — a UI mostra o limbo, e `canvasErro` carrega o motivo da última falha.
   */
  canvasEstado: EstadoCanvas;
  canvasErro: string | null;
  media: number | null;
  mediana: number | null;
  desvioPadrao: number | null;
  nPresentes: number | null;
}

export interface Alerta {
  id: string;
  categoria: CategoriaAlerta;
  severidade: Severidade;
  tagLabel: string;
  titulo: string;
  subtitulo: string;
  tempoRelativo: string;
  href: string;
  sparkline: number[];
}

/** Quem está logado — decidido pelo tipo do JWT, guardado no sessionStorage. */
export type TipoSessao = 'aluno' | 'coordenador';

// ─── Respostas de estatística ────────────────────────────────────────────
// Formatos devolvidos pelas rotas de análise. Não são entidades do banco:
// são recortes calculados pelo stats engine (ver api/app/stats/).

export interface RespostaHistograma {
  largura_bin: number;
  maximo: number;
  contagens: number[];
  media?: number | null;
  mediana?: number | null;
  nAusentes?: number | null;
}

/** Linha de quebra por matéria ou por sede na ficha do simulado. */
export interface QuebraSimulado {
  simuladoId?: string;
  materia?: string;
  sede?: string;
  media: number | null;
  mediana: number | null;
  desvioPadrao: number | null;
  nPresentes: number | null;
}

/** Nota individual de um aluno num simulado. */
export interface NotaSimulado {
  alunoId: string | null;
  nome: string;
  /** Já em escala 0-10. */
  pontuacao: number | null;
  presente: boolean;
}

/** Estatísticas de um recorte (ciclo inteiro, matéria, fase). */
export interface StatsRecorte {
  n: number;
  media: number | null;
  mediana: number | null;
  desvioPadrao: number | null;
  iqr?: number | null;
  amplitude?: number | null;
  moda?: number | null;
  p10?: number | null;
  p25?: number | null;
  p75?: number | null;
  p90?: number | null;
  skewness?: number | null;
  curtose?: number | null;
  bimodal?: boolean;
  pctAprovados?: number | null;
  pctZonaCritica?: number | null;
  pctExcelencia?: number | null;
}

export interface BlocoFase {
  stats: StatsRecorte;
  histograma: RespostaHistograma | null;
}

/** Insights do LLM: leitura acessível e leitura técnica do mesmo recorte. */
export interface Insights {
  pratico?: string[] | null;
  tecnico?: string[] | null;
}

export interface RecorteMateria {
  materia: MateriaResumo;
  /** Inglês na Fase 1 do ITA é eliminatório, com corte 5 em vez de 4. */
  eliminatoriaF1?: boolean;
  fase1: BlocoFase | null;
  fase2: BlocoFase | null;
  deltaF1F2?: { media?: number | null; pctAprovados?: number | null } | null;
  insights?: Insights | null;
}

/** Resposta de GET /ciclos/{id}/estatisticas. */
export interface EstatisticasCiclo {
  resumo?: {
    media?: number | null;
    pctAprovados?: number | null;
    pctZonaCritica?: number | null;
    pctExcelencia?: number | null;
    delta?: {
      media?: number | null;
      pctAprovados?: number | null;
      pctExcelencia?: number | null;
    } | null;
  } | null;
  cicloAnterior?: { nome: string } | null;
  evolucaoTemporal?: Array<{
    simuladoId?: string;
    nome: string;
    rotuloCurto?: string | null;
    data?: string | null;
    media: number;
    fase?: TipoSimulado | null;
    cicloAnteriorMedia?: number | null;
    nPresentes?: number | null;
  }> | null;
  conjunta?: {
    stats: StatsRecorte;
    histograma: RespostaHistograma | null;
    corte?: number | null;
    anterior?: { histograma: RespostaHistograma | null } | null;
    insights?: Insights | null;
  } | null;
  porMateria?: RecorteMateria[] | null;
}

/** Um ponto da trajetória do aluno (GET /alunos/{id}/trajetoria). */
export interface PontoTrajetoria {
  simuladoId: string | null;
  /** Já em escala 0-10. */
  pontuacao: number | null;
}

/** Vizinho no kNN de perfis semelhantes. */
export interface AlunoSimilar {
  alunoId: string;
  nome: string;
  distancia: number;
  perfil: Perfil | null;
  tendencia: Tendencia | null;
  zona: Zona | null;
  media: number | null;
}

// ─── Classificação por critério ──────────────────────────────────────────
// O servidor é dono da régua (docs/18 §1.2). O front recebe veredito, motivo,
// cor e posição prontos e só desenha — nenhuma regra de corte vive aqui.

/**
 * Estado de um objeto em relação ao Canvas. `divergente` = o coordenador
 * escolheu não enviar; o retry automático nunca o toca (docs/18 §2.5).
 */
export type EstadoCanvas = 'sincronizado' | 'pendente' | 'falhou' | 'divergente';

export type TomNota = 'verde' | 'ambar' | 'vermelho';

export interface PredicadoCriterio {
  materia: string | null;
  operador: string;
  minimo: number | { acertos: number; de: number };
  eliminatorio: boolean;
  entraNaMedia: boolean;
  peso: number;
  fonte: string;
}

export interface CriterioClassificacao {
  slug: string;
  nome: string;
  descricao: string;
  fase: 1 | 2 | null;
  combinador: 'todos' | 'algum';
  desempate: string[];
  predicados: PredicadoCriterio[];
}

export interface AlunoClassificado {
  alunoId: string;
  nome: string;
  turmaId: string | null;
  posicao: number;
  aprovado: boolean;
  /** "Química 3,2 — mínimo 4,0 (ITA §4.6.6.5)". `null` quando aprovado. */
  motivo: string | null;
  media: number | null;
  notas: Record<string, { nota: number; tom: TomNota }>;
}

export interface ClassificacaoCiclo {
  criterio: CriterioClassificacao;
  fase: 1 | 2 | null;
  total: number;
  cortados: number;
  alunos: AlunoClassificado[];
}
