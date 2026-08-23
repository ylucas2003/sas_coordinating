// Tipos do banco de questões ITA · IME (docs/22).
//
// Espelham `api/app/schemas/banco.py` — campo que muda lá, muda aqui. É o que
// faz `porPagina` vs `por_pagina` aparecer no build, e não em runtime.
//
// ⚠️ Arquivo separado de `dominio.ts` de propósito: `QuestaoVestibular` é
// questão de PROVA PASSADA, sem simulado e sem nota. A questão de simulado-Quiz
// do Canvas é outra coisa e vive em outro lugar (docs/22 §8).

export type VestibularBanco = 'ITA' | 'IME';
export type MateriaBanco = 'Física' | 'Química' | 'Matemática';
/** Quanto o classificador confia no tópico que atribuiu à questão. */
export type Confianca = 'alta' | 'media' | 'baixa';
export type DonoLista = 'aluno' | 'coordenacao';

// ─── Taxonomia ───────────────────────────────────────────────────────────

export interface TopicoTaxonomia {
  /** '7.2' — único só dentro da matéria: o mesmo código existe nas três. */
  codigo: string;
  nome: string;
  /** O que o edital enumera dentro do tópico; descritivo, não é chave. */
  assuntos: string[];
  totalQuestoes: number;
}

export interface BlocoTaxonomia {
  codigo: string;
  nome: string;
  topicos: TopicoTaxonomia[];
  totalQuestoes: number;
}

export interface TaxonomiaMateria {
  materia: MateriaBanco;
  blocos: BlocoTaxonomia[];
  totalQuestoes: number;
  /**
   * Questões da matéria que ninguém classificou. A tela mostra o número em vez
   * de escondê-las: sumir com elas seria dar um recorte incompleto sem aviso
   * (docs/22 §8).
   */
  semClassificacao: number;
  anos: number[];
  fases: number[];
  vestibulares: VestibularBanco[];
}

// ─── Questão ─────────────────────────────────────────────────────────────

export interface TopicoDaQuestao {
  codigo: string;
  nome: string;
  blocoNome: string;
  confianca: Confianca | null;
  observacao: string | null;
}

export interface QuestaoVestibular {
  /** '{vestibular}_{ano}_fase{n}_q{NN}' — a mesma chave do JSON e do PNG. */
  id: string;
  vestibular: VestibularBanco;
  ano: number;
  fase: number;
  materia: MateriaBanco;
  numero: number;
  dissertativa: boolean;
  enunciadoMd: string;
  /** `null` quando dissertativa: 2ª fase não tem alternativa nem letra. */
  alternativas: Record<string, string> | null;
  gabarito: string | null;
  imagemUrl: string | null;
  /**
   * O enunciado é renderizado como imagem para preservar fórmula e figura da
   * prova; o texto existe para busca e classificação (migration 0028).
   */
  usaImagemNoRender: boolean;
  resolucaoUrl: string | null;
  topicos: TopicoDaQuestao[];
  revisado: boolean;
  /** Só vem preenchido para aluno autenticado. `null` = perfil sem estudo. */
  resolvida: boolean | null;
  anotacao: string | null;
}

/**
 * Página de questões. Paginar aqui é o certo e não contradiz a armadilha 2 do
 * CLAUDE.md: lá o teto é proibido porque truncar leitura *estatística* devolve
 * número errado sem parecer errado; aqui a resposta é *navegação*, e a página
 * seguinte está a um clique. Quem agrega (`/banco/estatisticas`) nunca pagina.
 * Ver docs/22 §2.2.
 */
export interface PaginaQuestoes {
  questoes: QuestaoVestibular[];
  total: number;
  pagina: number;
  porPagina: number;
}

/** Filtros de `GET /banco/questoes`. Campo ausente = sem filtro. */
export interface FiltrosBanco {
  materia?: MateriaBanco;
  vestibular?: VestibularBanco;
  ano?: number;
  fase?: number;
  /** Código do tópico, sempre dentro de uma matéria (ver `TopicoTaxonomia`). */
  topico?: string;
  /** Busca textual sobre o enunciado — não é semântica (docs/22 §8). */
  busca?: string;
  pagina?: number;
  porPagina?: number;
}

// ─── Estatísticas ────────────────────────────────────────────────────────

export interface RecorrenciaTopico {
  codigo: string;
  nome: string;
  blocoNome: string;
  total: number;
  /**
   * Só os anos/fases/vestibulares com ocorrência — ausência é zero, não buraco.
   * As chaves chegam como string no JSON, como toda chave de objeto: quem
   * itera com `Object.entries` converte com `Number(...)`.
   */
  porAno: Record<number, number>;
  porFase: Record<number, number>;
  porVestibular: Record<string, number>;
}

export interface EstatisticasBanco {
  materia: MateriaBanco;
  topicos: RecorrenciaTopico[];
  anos: number[];
  totalQuestoes: number;
  semClassificacao: number;
}

// ─── Listas ──────────────────────────────────────────────────────────────

export interface ListaResumo {
  id: string;
  titulo: string;
  donoTipo: DonoLista;
  totalQuestoes: number;
  criadaEm: string;
  atualizadaEm: string;
}

/** A lista aberta: o resumo mais as questões, já na ordem escolhida. */
export interface Lista extends ListaResumo {
  questoes: QuestaoVestibular[];
}

/**
 * Remendo de lista. `questaoIds` é a ordem **completa e explícita**: reordenar
 * é mandar a lista inteira, para o vaivém de "mover para cima" não virar N
 * requisições que chegam fora de ordem (`api/app/schemas/banco.py`).
 */
export interface RemendoLista {
  titulo?: string;
  questaoIds?: string[];
}

// ─── Estudo do aluno ─────────────────────────────────────────────────────

export interface EstudoQuestao {
  questaoId: string;
  resolvida: boolean;
  anotacao: string | null;
}

/** Campo omitido = não mexe. É `PUT` parcial de propósito (docs/22 §P6). */
export interface RemendoEstudo {
  resolvida?: boolean;
  anotacao?: string | null;
}
