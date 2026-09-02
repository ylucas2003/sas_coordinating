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

/**
 * As duas coleções do acervo, em vocabulário de produto.
 *
 * Quem as separa no banco é `extraido_por` (0031/0033), mas nem o aluno nem a
 * URL precisam do nome da coluna: 'recentes' é o recorte fino da questão, e
 * 'arquivo' é a página inteira do caderno. A tradução mora num lugar só, na
 * camada de consulta do backend.
 */
export type ColecaoBanco = 'recentes' | 'arquivo';

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
  /** 'banca' = letra publicada pela banca; 'sugerido' = deduzida (0031). `null` sem gabarito. */
  gabaritoOrigem: 'banca' | 'sugerido' | null;
  /** Só existe quando gabaritoOrigem é 'sugerido'. Decide se a letra aparece — só 'alta' entra na tela. */
  gabaritoConfianca: Confianca | null;
  imagemUrl: string | null;
  /**
   * O enunciado é renderizado como imagem para preservar fórmula e figura da
   * prova; o texto existe para busca e classificação (migration 0028).
   */
  usaImagemNoRender: boolean;
  resolucaoUrl: string | null;
  /** Resolução escrita no cartão — o acervo histórico que o Ari não comenta (0031). */
  resolucaoMd: string | null;
  resolucaoOrigem: 'ari' | 'sugerida' | null;
  /**
   * 'visao' = página escaneada lida como imagem; texto é o principal, imagem
   * vira consulta. 'pagina' = a imagem é a página inteira do PDF onde a
   * questão está (docs/24), sem recorte fino — usada no acervo histórico.
   */
  extraidoPor: 'pipeline' | 'visao' | 'pagina' | null;
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
  colecao?: ColecaoBanco;
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
  /**
   * O DOMÍNIO da série temporal, e não uma lista decorativa.
   *
   * ⚠️ Preencha a série contra ela, nunca contra as chaves de `porAno`:
   * `porAno` só traz o ano com ocorrência, e plotar só essas chaves comprime o
   * tempo — o buraco some, e o buraco é a informação. `dominio/banco.ts`
   * (`seriesPorAno`) é quem faz isso.
   *
   * ⚠️ E ela COMEÇA onde há acervo, nunca num ano cravado no código: pedindo
   * `vestibular=ITA` o primeiro ano é 2008, porque o acervo do ITA começa ali
   * (migration 0031). Desenhar o ITA em zero antes disso AFIRMA que o assunto
   * não caía no ITA, quando a verdade é que não temos a prova.
   */
  anos: number[];
  /**
   * Quantas questões a banca cobrou em cada ano DESTE recorte — o denominador
   * de "% da prova".
   *
   * ⚠️ Não tente derivá-lo somando `total` dos tópicos: questão mista soma nos
   * dois tópicos de propósito (docs/22 §1.5), então a soma passa do total e o
   * percentual sairia menor que a verdade.
   */
  questoesPorAno: Record<number, number>;
  totalQuestoes: number;
  semClassificacao: number;
}

// ─── Progresso do aluno no acervo ────────────────────────────────────────
//
// ⚠️ TODO NÚMERO VEM COM O SEU PAR. "412 questões" não é progresso; "412 de
// 2.693" é. E "feitas" é `resolvida`, que é AUTO-DECLARADO — a tela pode dizer
// "o que você marcou como feito", nunca "seu domínio" nem "seu acerto".

export interface ParDeProgresso {
  feitas: number;
  total: number;
}

export interface ProgressoPorMateria extends ParDeProgresso {
  materia: MateriaBanco;
}

export interface ProgressoPorAssunto extends ParDeProgresso {
  materia: MateriaBanco;
  /** 'sem-assunto' na linha das órfãs — vale como filtro em `/banco/questoes`. */
  codigo: string;
  nome: string;
  blocoNome: string;
}

export interface ProgressoPorAno extends ParDeProgresso {
  materia: MateriaBanco;
  ano: number;
}

export interface ProgressoDoAluno extends ParDeProgresso {
  porMateria: ProgressoPorMateria[];
  porAssunto: ProgressoPorAssunto[];
  /**
   * Só os pares (matéria, ano) que EXISTEM no acervo. Par ausente é "não houve
   * prova dessa matéria nesse ano" — diferente de "houve e você não fez
   * nenhuma", e a grade tem de desenhar os dois casos diferente. Ler ausência
   * como zero faz o aluno confundir buraco de acervo com buraco de estudo.
   */
  porAno: ProgressoPorAno[];
  anos: number[];
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
  /** A letra marcada no treino (0042). `null` = pulou, ou nunca respondeu. */
  alternativaEscolhida: string | null;
  /**
   * ⚠️ `null` é "não dá para dizer", NUNCA "errou": questão dissertativa ou
   * sem gabarito importado não tem como ser conferida. Desenhar `null` como
   * erro dá ao aluno o conselho de estudo oposto ao certo.
   *
   * ⚠️ E não é `resolvida`. `resolvida` é auto-declarado ("eu fiz esta") e
   * pode existir sem resposta nenhuma; `acertou` foi conferido contra o
   * gabarito. As duas não se somam nem se tira média entre elas.
   */
  acertou: boolean | null;
}

/** Campo omitido = não mexe. É `PUT` parcial de propósito (docs/22 §P6). */
export interface RemendoEstudo {
  resolvida?: boolean;
  anotacao?: string | null;
  /**
   * A letra do treino; `''` limpa a resposta.
   *
   * ⚠️ `acertou` não entra aqui de propósito — quem confere é o servidor,
   * contra o gabarito do banco (0042).
   */
  alternativaEscolhida?: string | null;
}
