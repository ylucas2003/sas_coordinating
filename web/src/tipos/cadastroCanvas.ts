// Cadastro de aluno no Canvas (docs/46) — espelho de
// `api/app/routes/cadastro_canvas.py` e de `canvas_sync/cadastro.py`. Arquivo
// próprio, como `tipos/captacao.ts`: é um recurso fechado, só do administrador.

export interface CursoDoPacote {
  id: string;
  nome: string;
}

export interface SedeDoPacote {
  /** Id da section do curso de provas no Canvas. */
  id: string;
  nome: string;
}

/** Os cursos em que uma série é matriculada, lidos agora do Canvas. */
export interface PacoteDaSerie {
  serie: number;
  rotulo: string;
  cursos: CursoDoPacote[];
  curso_de_provas: string | null;
  exige_sede: boolean;
  sedes: SedeDoPacote[];
  /** Curso ou sede sem SIS ID: a série não entra no lote, só um por vez. */
  problemas_no_lote: string[];
}

export interface CatalogoDePacotes {
  ano: number;
  anos: number[];
  pacotes: PacoteDaSerie[];
}

export interface CadastroDeAluno {
  matricula: string;
  nome: string;
  email?: string | null;
  serie: number;
  sede_id?: string | null;
  ano?: number | null;
  confirmar_nome_existente?: boolean;
}

export type EstadoDoCurso = 'matriculado' | 'ja_estava' | 'outra_sede' | 'falhou';

export interface ResultadoDoCurso {
  id: string;
  nome: string;
  estado: EstadoDoCurso;
  detalhe?: string;
}

export interface ResultadoDoCadastro {
  matricula: string;
  nome: string;
  canvas_user_id: string;
  conta: 'criada' | 'existente';
  nome_no_canvas: string | null;
  email_enviado: boolean;
  ano: number;
  serie: number;
  sede: string | null;
  cursos: ResultadoDoCurso[];
  completo: boolean;
}

export type SituacaoDaLinha = 'nova' | 'existente' | 'erro';

export interface LinhaDaPrevia {
  /** Número da linha NA PLANILHA, cabeçalho incluído. */
  linha: number;
  matricula: string;
  nome: string;
  email: string | null;
  serie: number | null;
  sede_id: string | null;
  sede_nome: string | null;
  situacao: SituacaoDaLinha;
  erros: string[];
  avisos: string[];
  nome_no_canvas: string | null;
}

export interface ResumoDoLote {
  total: number;
  novas: number;
  existentes: number;
  com_erro: number;
  com_aviso: number;
}

export interface PreviaDoLote {
  ano: number;
  linhas: LinhaDaPrevia[];
  resumo: ResumoDoLote;
}

export type EstadoDoLote = 'processando' | 'concluido' | 'concluido_com_avisos' | 'falhou';

/** Um SIS Import do Canvas, no vocabulário da tela. */
export interface LoteNoCanvas {
  id: string;
  estado: EstadoDoLote;
  estado_canvas: string;
  progresso: number | null;
  criado_em: string | null;
  terminado_em: string | null;
  contas: number | null;
  matriculas: number | null;
  erros: string[];
  avisos: string[];
  total_erros: number;
  total_avisos: number;
  /** Só na resposta do envio: o que a prévia contou. */
  linhas?: ResumoDoLote;
}
