// Espelha `api/app/routes/captacao.py` (docs/41). Snake_case de propósito, e
// não camelCase como `tipos/banco.ts`: a rota devolve as linhas quase cruas de
// `v_candidato_externo`/`conquista_externa`, sem schema Pydantic com alias no
// meio — o mesmo desenho de `FiltroAuditoria`/`UsuarioCoordenacao` em
// `servicos/api.ts`. Mudou uma coluna lá, mude aqui.
//
// Simplificação de 25/09/2026: não existe mais fila de fusão, decisão
// permanente nem sinal de confiança (`tem_conflito_nivel`/`ufs_distintas`) —
// causavam um bug sério (nome "decidido" ficava escondido pra sempre, mesmo
// ganhando conquista nova depois). Separar (não juntar) é que é só manual.
//
// Ajuste de 28/09/2026 (docs/41 §16): o default voltou a ser 1
// `candidato_externo` por NOME (não por conquista) — o resolver anexa
// conquista nova ao perfil existente em vez de sempre criar um novo.

export type StatusCaptacao = 'novo' | 'contatado' | 'interessado' | 'matriculado' | 'descartado';

/** Um `candidato_externo` — nasce com todas as conquistas já conhecidas do
 * nome (`resolver_candidatos_externos.py` anexa ao perfil existente, docs/41
 * §16); só fica em MAIS de um perfil quando um humano separa arrastando
 * (`mover_conquista`, criando um perfil novo primeiro). É o formato de UM
 * CARTÃO em `CaptacaoPerfil.tsx`. */
export interface CandidatoExterno {
  id: string;
  nome: string;
  /** Chave de agrupamento (maiúsculas, sem acento) — é o que liga este perfil aos outros com o mesmo nome. */
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

/** Um perfil do nome, com as próprias conquistas — o que um cartão de `CaptacaoPerfil.tsx` desenha. */
export interface PerfilDoNome extends CandidatoExterno {
  conquistas: ConquistaExterna[];
}

/** Todo `candidato_externo` com um nome — a tela inteira de `CaptacaoPerfil.tsx`. */
export interface PerfisDoNome {
  nome_normalizado: string;
  candidatos: PerfilDoNome[];
}

/** Uma linha da lista geral — vem de `v_candidato_externo_por_nome` (migration
 * 0063): TODO nome vira uma linha, sempre, incondicional. escolas/cidades/ufs/
 * status_captacao são CONJUNTOS — o que qualquer conquista/perfil daquele nome
 * já teve —, não um valor escolhido por heurística. Arrays independentes,
 * nunca pareados por índice entre si (duas conquistas podem repetir cidade com
 * UF diferente por erro de digitação da fonte). */
export interface CandidatoPorNome {
  nome_normalizado: string;
  nome: string;
  escolas: string[];
  cidades: string[];
  ufs: string[];
  status_captacao: StatusCaptacao[];
  conquistas_total: number;
  provas_distintas: number;
  /** Quantos `candidato_externo` existem hoje pra este nome — 1 = nada fragmentado. */
  perfis_no_grupo: number;
  ano_mais_recente: number | null;
  criado_em: string;
  atualizado_em: string;
}

export interface PaginaCandidatos {
  candidatos: CandidatoPorNome[];
  total: number;
  pagina: number;
  por_pagina: number;
}

export interface FiltrosCaptacao {
  uf?: string;
  status_captacao?: StatusCaptacao;
  conquistas_min?: number;
  busca?: string;
  pagina?: number;
  por_pagina?: number;
}

/** Só o funil manual — os outros campos são derivados (0056 §3). Editado direto em cada cartão de `CaptacaoPerfil.tsx`. */
export interface RemendoCandidato {
  status_captacao?: StatusCaptacao;
  observacoes?: string;
}

/** Uma prova (ITA, IME, OBMEP...) com o intervalo de anos carregado — o rodapé "quais fontes alimentam esta lista" de `Captacao.tsx`. */
export interface ResumoProva {
  nome: string;
  categoria: string;
  ano_min: number | null;
  ano_max: number | null;
  conquistas_total: number;
}

export interface PaginaProvas {
  provas: ResumoProva[];
}
