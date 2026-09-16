// Espelha `api/app/routes/captacao.py` (docs/41). Snake_case de propósito, e
// não camelCase como `tipos/banco.ts`: a rota devolve as linhas quase cruas de
// `v_candidato_externo`/`conquista_externa`, sem schema Pydantic com alias no
// meio — o mesmo desenho de `FiltroAuditoria`/`UsuarioCoordenacao` em
// `servicos/api.ts`. Mudou uma coluna lá, mude aqui.

export type StatusCaptacao = 'novo' | 'contatado' | 'interessado' | 'matriculado' | 'descartado';

/** Uma linha da lista — o resumo de `v_candidato_externo` (migration 0058). */
export interface CandidatoExterno {
  id: string;
  nome: string;
  escola: string | null;
  cidade: string | null;
  uf: string | null;
  serie_referencia_min: number | null;
  serie_referencia_max: number | null;
  ano_referencia_serie: number | null;
  status_captacao: StatusCaptacao;
  observacoes: string | null;
  criado_em: string;
  atualizado_em: string;
  /** Nº de conquistas cruzadas — o sinal mais forte de lead (docs/41 §5). */
  conquistas_total: number;
  provas_distintas: number;
  ano_mais_recente: number | null;
}

/** Uma conquista, com o nome e a categoria da prova já resolvidos pelo backend. */
export interface ConquistaExterna {
  id: string;
  prova_id: string;
  ano: number;
  nivel_texto: string | null;
  serie_referencia_min: number | null;
  serie_referencia_max: number | null;
  resultado: string;
  nome_informado: string;
  escola_informada: string | null;
  cidade_informada: string | null;
  uf_informada: string | null;
  fonte_url: string;
  raspado_em: string;
  prova_nome: string | null;
  prova_categoria: string | null;
}

/** A ficha: o candidato e TODAS as conquistas cruzadas dele, ano decrescente. */
export interface CandidatoFicha extends CandidatoExterno {
  conquistas: ConquistaExterna[];
}

export interface PaginaCandidatos {
  candidatos: CandidatoExterno[];
  total: number;
  pagina: number;
  por_pagina: number;
}

export interface FiltrosCaptacao {
  uf?: string;
  status_captacao?: StatusCaptacao;
  conquistas_min?: number;
  prova_id?: string;
  busca?: string;
  pagina?: number;
  por_pagina?: number;
}

/** Só o funil manual — os outros campos são derivados (0056 §3). */
export interface RemendoCandidato {
  status_captacao?: StatusCaptacao;
  observacoes?: string;
}
