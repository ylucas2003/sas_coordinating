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
  /** Chave de agrupamento (maiúsculas, sem acento) — é o que liga esta pessoa à fila de fusão (0059/0061) e ao grupo dela na view agrupada (0062). */
  nome_normalizado: string;
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
  /** Nota por matéria, quando a fonte publica (só IME e EFOMM têm — 0056/0060). Chave livre: cada prova usa o próprio vocabulário ("mat", "fis", "media"...). */
  notas_por_materia: Record<string, number> | null;
}

/** A ficha: o candidato e TODAS as conquistas cruzadas dele, ano decrescente. */
export interface CandidatoFicha extends CandidatoExterno {
  conquistas: ConquistaExterna[];
  /** Quantos OUTROS `candidato_externo` têm este mesmo nome, ainda pendentes na fila de fusão (0 = nome sozinho, sem duplicata). Base do alerta na ficha. */
  duplicatas_pendentes: number;
  /** Sinal FORTE de que as duplicatas são pessoas diferentes (nível de ensino conflitante no mesmo ano) — não só "cuidado" como ufs_distintas. */
  tem_conflito_nivel: boolean;
}

/** Uma linha da lista geral — vem de `v_candidato_externo_agrupado` (0062): nome ainda pendente na fila de fusão já chega colapsado num representante só. */
export interface CandidatoExternoAgrupado extends CandidatoExterno {
  /** Quantos `candidato_externo` este representante resume — 1 = nome sem ambiguidade (nada foi colapsado). */
  perfis_no_grupo: number;
  tem_conflito_nivel: boolean;
}

export interface PaginaCandidatos {
  candidatos: CandidatoExternoAgrupado[];
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

// ─── Fila de fusão de baixa confiança (docs/41 §8, item 1) ────────────────
// O resolver só funde por nome+escola exatos (§4.1); isto aqui é o segundo
// nível, nome sozinho — nunca funde automático, só sugere pra um humano
// confirmar ou rejeitar.

/** Uma linha da fila: um NOME com mais de um `candidato_externo`. */
export interface GrupoFusao {
  nome_normalizado: string;
  /** Quantos `candidato_externo` distintos têm este nome. */
  candidatos: number;
  /** 1 = todos batem na mesma UF (alta confiança); mais que 1 = cuidado. */
  ufs_distintas: number;
  /** Nível de ensino conflitante no mesmo ano entre candidatos do grupo — sinal FORTE de gente diferente, não só "cuidado" (scripts/sinalizar_fusoes_conflito_de_nivel.py). */
  tem_conflito_nivel: boolean;
}

export interface PaginaFusoes {
  grupos: GrupoFusao[];
  total: number;
  pagina: number;
  por_pagina: number;
}

/** Um candidato do grupo, com as próprias conquistas — pra comparar lado a lado. */
export interface MembroDaFusao extends CandidatoExterno {
  conquistas: ConquistaExterna[];
}

export interface DetalheDaFusao {
  nome_normalizado: string;
  candidatos: MembroDaFusao[];
}

export interface ResultadoDaFusao {
  sobrevivente_id: string;
  candidatos_fundidos: number;
}

// ─── Modo avançado: dividir um grupo à mão (docs/41, 24/09/2026) ──────────
// O binário acima decide o grupo INTEIRO de uma vez; estas ações operam num
// perfil ou numa conquista por vez, pra separar quem o resolver misturou.

export interface ResultadoDaConclusao {
  status: 'confirmada' | 'rejeitada';
  perfis_finais: number;
}
