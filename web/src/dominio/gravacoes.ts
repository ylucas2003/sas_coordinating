// Acompanhamento das gravações de aula — lógica pura, testada em
// gravacoes.test.ts.
//
// O backend tem dez `status` de pipeline e seis `canvasEstado`; o coordenador
// não quer saber de "compondo" nem de "baixado". A tradução para as cinco
// situações que ele acompanha ("já foi", "está indo", "vai ser") mora aqui e
// não no componente, para o rótulo ser o mesmo em qualquer tela que mostre a
// mesma aula.

import type {
  EstadoCanvasGravacao,
  GravacaoAula,
  StatusGravacao,
} from '../tipos/dominio';

/**
 * O ciclo de vida do vídeo em cinco degraus, na ordem em que acontecem.
 *
 * `na_fila` é separado de `processando` porque a espera tem causas diferentes:
 * na fila a aula depende do cron da hora seguinte, processando ela já está
 * consumindo os 45-90 min de download + ffmpeg + upload. Juntar os dois faria
 * o coordenador achar que travou.
 */
export const SITUACOES = ['aguardando', 'na_fila', 'processando', 'publicado', 'erro'] as const;
export type Situacao = (typeof SITUACOES)[number];

const POR_STATUS: Record<StatusGravacao, Situacao> = {
  aguardando_gravacao: 'aguardando',
  pendente: 'na_fila',
  baixando: 'processando',
  baixado: 'processando',
  compondo: 'processando',
  composto: 'processando',
  publicando: 'processando',
  publicado: 'publicado',
  // Subiu, mas a confirmação do YouTube não voltou. É sucesso: reprocessar
  // geraria segunda cópia no canal (api/CLAUDE.md).
  publicado_sem_confirmacao: 'publicado',
  erro: 'erro',
};

/**
 * Sem cabeçalho de coluna para se apoiar, cada rótulo precisa dizer sozinho de
 * qual lado do pipeline ele fala — "erro" solto num card não diz se quem
 * falhou foi o YouTube ou o Canvas.
 */
export const ROTULO_SITUACAO: Record<Situacao, string> = {
  aguardando: 'aguardando gravação',
  na_fila: 'na fila',
  processando: 'processando vídeo',
  publicado: 'no YouTube',
  erro: 'erro ao publicar',
};

export function situacaoDe(a: GravacaoAula): Situacao {
  return POR_STATUS[a.status] ?? 'aguardando';
}

export function toneSituacao(s: Situacao): string {
  if (s === 'publicado') return 'tone-verde';
  if (s === 'erro') return 'tone-vermelho';
  if (s === 'processando') return 'tone-navy';
  return 'tone-ambar';
}

/**
 * Liga o polling. Só `na_fila` e `processando` mudam sozinhos em minutos —
 * `aguardando` depende de o BigBlueButton terminar de processar a gravação,
 * o que leva horas, e recarregar de 30 em 30 s não adiantaria nada.
 */
export function algumEmAndamento(aulas: readonly GravacaoAula[]): boolean {
  return aulas.some((a) => {
    const s = situacaoDe(a);
    return s === 'na_fila' || s === 'processando';
  });
}

/**
 * O que a rotina está fazendo agora, ou `null` se está parada.
 *
 * Separa "processando" de "na fila" porque as duas esperas são diferentes:
 * na fila a aula espera o cron da hora seguinte, processando ela já está
 * consumindo os 45-90 min. Chamar as duas de "processando agora" faria o
 * coordenador esperar um vídeo que ainda nem começou a ser baixado.
 */
export function resumoAndamento(aulas: readonly GravacaoAula[]): string | null {
  let processando = 0;
  let naFila = 0;
  for (const a of aulas) {
    const s = situacaoDe(a);
    if (s === 'processando') processando += 1;
    else if (s === 'na_fila') naFila += 1;
  }
  if (processando) return `processando ${processando} agora`;
  if (naFila) return `${naFila} na fila`;
  return null;
}

// ─── Estado no Canvas ────────────────────────────────────────────────────

export const ROTULO_CANVAS: Record<EstadoCanvasGravacao, { texto: string; titulo: string }> = {
  pendente: {
    texto: 'a publicar no Canvas',
    titulo: 'O vídeo ainda não foi embutido na página da aula.',
  },
  publicado: {
    texto: 'na página do Canvas',
    titulo: 'O vídeo está embutido na página da aula. Clique para abrir.',
  },
  falhou: {
    texto: 'Canvas recusou',
    titulo: 'O Canvas recusou a escrita. Tenta de novo na próxima rodada.',
  },
  ambiguo: {
    texto: 'Canvas: página ambígua',
    titulo: 'Mais de uma página com essa data — o SAS não escolhe no escuro. Embuta à mão.',
  },
  conflito: {
    texto: 'Canvas: já tem outro vídeo',
    titulo: 'A página já tem OUTRO vídeo do YouTube. O SAS não sobrescreve o professor.',
  },
  ignorado: {
    texto: 'Canvas desligado',
    titulo: 'A publicação no Canvas está desligada para este curso.',
  },
};

export function toneCanvas(e: EstadoCanvasGravacao): string {
  if (e === 'publicado') return 'tone-verde';
  if (e === 'falhou') return 'tone-vermelho';
  if (e === 'ambiguo' || e === 'conflito') return 'tone-ambar';
  return 'tone-cinza';
}

/** Só faz sentido cobrar o Canvas de aula cujo vídeo já existe. */
export function esperaCanvas(a: GravacaoAula): boolean {
  return situacaoDe(a) === 'publicado';
}

// ─── Filtro ──────────────────────────────────────────────────────────────

export interface FiltroGravacoes {
  cursos: ReadonlySet<string>;
  situacoes: ReadonlySet<Situacao>;
}

export const FILTRO_GRAVACOES_VAZIO: FiltroGravacoes = {
  cursos: new Set(),
  situacoes: new Set(),
};

export function algumFiltroAtivo(f: FiltroGravacoes): boolean {
  return f.cursos.size + f.situacoes.size > 0;
}

function passa(a: GravacaoAula, f: FiltroGravacoes, ignorada?: keyof FiltroGravacoes): boolean {
  if (ignorada !== 'cursos' && f.cursos.size && !f.cursos.has(a.cursoId)) return false;
  if (ignorada !== 'situacoes' && f.situacoes.size && !f.situacoes.has(situacaoDe(a))) return false;
  return true;
}

export function aplicarFiltros(
  aulas: readonly GravacaoAula[],
  f: FiltroGravacoes,
): GravacaoAula[] {
  return aulas.filter((a) => passa(a, f));
}

/**
 * Contagem por chip ignorando o próprio eixo — senão o número de cada pílula
 * viraria sempre o total já selecionado.
 */
export function contarPorChip(aulas: readonly GravacaoAula[], f: FiltroGravacoes) {
  const curso = new Map<string, number>();
  const situacao = new Map<Situacao, number>();

  for (const a of aulas) {
    if (passa(a, f, 'cursos')) curso.set(a.cursoId, (curso.get(a.cursoId) ?? 0) + 1);
    if (passa(a, f, 'situacoes')) {
      const s = situacaoDe(a);
      situacao.set(s, (situacao.get(s) ?? 0) + 1);
    }
  }
  return { curso, situacao };
}

/**
 * Ordena da aula mais recente para a mais antiga, com as SEM data no topo:
 * conferência agendada e ainda não iniciada tem `iniciadaEm` nulo, e é
 * justamente a que o coordenador quer ver primeiro ("a que vai ser
 * processada"). O backend já ordena, mas ele não sabe dessa preferência e o
 * PostgREST joga nulo para o fim.
 */
export function ordenarParaAcompanhamento(aulas: readonly GravacaoAula[]): GravacaoAula[] {
  return [...aulas].sort((x, y) => {
    if (!x.iniciadaEm && !y.iniciadaEm) return 0;
    if (!x.iniciadaEm) return -1;
    if (!y.iniciadaEm) return 1;
    return y.iniciadaEm.localeCompare(x.iniciadaEm);
  });
}

// ─── Título para o card ──────────────────────────────────────────────────

// O que o card já diz em outro lugar, e por isso sai do título: a data (é a
// tarja da esquerda), a hora e a duração (rodapé), o prefixo do canal e a
// turma (idênticos em toda aula do curso).
const _SEGMENTO_DESCARTAVEL = [
  /^\d{1,2}\/\d{1,2}(\/\d{2,4})?$/, //            25/08/2026, 27/08/26
  /^\d{1,2}[:h]\d{2}$/, //                         17:30, 17h30
  /^SAS\s+ITA\/IME\s+\d{4}$/i, //                  prefixo do canal
  /^Turma\s+\d(\s+e\s+\d)?$/i, //                 Turma 1, Turma 1 e 2
];

const _DATA_ENTRE_PARENTESES_NO_FIM = /\s*\(\s*\d{1,2}\/\d{1,2}\/\d{2,4}\s*\)\s*$/;

/**
 * Enxuga o título para caber num card sem virar sopa de letras.
 *
 * Cada professor nomeia a conferência do seu jeito e o resultado cru é longo e
 * repetitivo ("SAS ITA/IME 2026 - Turma 1 e 2 - Redação - Prof Camila Oliveira
 * - 09:00 (29/08/2026)"). A função só REMOVE segmentos redundantes e nunca
 * inventa nem reordena: se sobrar vazio, devolve o título original — um card
 * com título feio é melhor que um card sem título.
 *
 * O corte é por segmento inteiro entre " - ", nunca por trecho: "Tira-dúvidas"
 * tem hífen sem espaços e precisa sobreviver.
 */
export function tituloParaCartao(bruto: string): string {
  const base = bruto.replace(_DATA_ENTRE_PARENTESES_NO_FIM, '').trim();
  const segmentos = base
    .split(/\s+[-–]\s+/)
    .map((p) => p.trim())
    .filter((p) => p && !_SEGMENTO_DESCARTAVEL.some((r) => r.test(p)));
  return segmentos.length ? segmentos.join(' · ') : bruto.trim();
}

// ─── Formatação ──────────────────────────────────────────────────────────

/** A tarja do card: dia, mês abreviado e ano — a data é a identidade da aula. */
export function partesDaData(iso: string | null | undefined) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return {
    dia: d.toLocaleDateString('pt-BR', { day: '2-digit' }),
    mes: d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '').toUpperCase(),
    ano: d.toLocaleDateString('pt-BR', { year: 'numeric' }),
  };
}

export function formatarHora(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

export function formatarDuracao(minutos: number | null | undefined): string {
  if (minutos == null) return '—';
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return h ? `${h}h${String(m).padStart(2, '0')}` : `${m} min`;
}
