// Lógica da importação de planilha — progresso, etapas e deduplicação de
// eventos. Testada em importacao.test.ts.

/** 1-7: ingestão. 8-10: stats engine (métricas, classificação, alertas). */
export const TOTAL_ETAPAS = 10;
export const INTERVALO_POLLING_MS = 600;

export type EstadoImportacao = 'aguardando' | 'uploading' | 'processando' | 'sucesso' | 'erro';

export interface EventoUpload {
  nivel: 'info' | 'aviso' | 'erro';
  mensagem: string;
  criado_em: string;
  linha_planilha?: number | null;
  coluna_planilha?: string | null;
}

export interface ResumoUpload {
  alunos_processados?: number | null;
  sedes_processadas?: number | null;
  turmas_processadas?: number | null;
  ciclos_processados?: number | null;
  simulados_processados?: number | null;
  notas_gravadas?: number | null;
  colunas_ignoradas?: number | null;
  avisos?: string[];
}

export interface UploadDetalhe {
  upload: {
    id: string;
    status: 'processando' | 'sucesso' | 'erro';
    resumo?: ResumoUpload | null;
    erro_mensagem?: string | null;
  };
  eventos?: EventoUpload[];
}

export interface UploadHistorico {
  id: string;
  arquivo_origem: string;
  status: string;
  linhas_aceitas: number | null;
  criado_em: string;
}

/**
 * Posição da barra de progresso.
 *
 * O upload de bytes ocupa 0-30% (a parte rápida) e o processamento no servidor
 * 30-95%. Os 5% finais ficam reservados ao "concluído": chegar a 100% antes do
 * fim daria a impressão de travamento.
 */
export function porcentagem(
  estado: EstadoImportacao,
  bytes: { enviado: number; total: number },
  etapa: number,
  ultimaConhecida = 0,
): number {
  if (estado === 'uploading') {
    if (bytes.total === 0) return 0;
    return Math.round((bytes.enviado / bytes.total) * 30);
  }
  if (estado === 'processando') return 30 + Math.round((etapa / TOTAL_ETAPAS) * 65);
  if (estado === 'sucesso') return 100;
  if (estado === 'erro') return ultimaConhecida;
  return 0;
}

/**
 * Junta eventos novos aos já vistos, sem repetir. A dedup usa
 * `criado_em + mensagem` porque o polling rebusca a lista inteira a cada
 * volta e os eventos não têm id próprio.
 */
export function mesclarEventos(
  atuais: readonly EventoUpload[],
  novos: readonly EventoUpload[],
): EventoUpload[] {
  const vistos = new Set(atuais.map((e) => `${e.criado_em}|${e.mensagem}`));
  const resultado = [...atuais];

  for (const ev of novos) {
    const chave = `${ev.criado_em}|${ev.mensagem}`;
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    resultado.push(ev);
  }
  return resultado;
}

/**
 * Etapa mais avançada já anunciada pelo servidor. O pipeline emite linhas
 * "ETAPA 3/10: descrição"; a barra segue a maior vista, e não a última — os
 * eventos podem chegar fora de ordem entre duas voltas do polling.
 */
export function etapaMaisAvancada(
  eventos: readonly EventoUpload[],
): { etapa: number; descricao: string } | null {
  let etapa = 0;
  let descricao = '';

  for (const ev of eventos) {
    const m = (ev.mensagem || '').match(/^ETAPA\s+(\d+)\/\d+:\s*(.+)$/);
    if (!m) continue;
    const n = parseInt(m[1], 10);
    if (n > etapa) {
      etapa = n;
      descricao = m[2];
    }
  }
  return etapa > 0 ? { etapa, descricao } : null;
}

export function toneNivel(nivel: string): string {
  if (nivel === 'erro') return 'tone-vermelho';
  if (nivel === 'aviso') return 'tone-ambar';
  return 'tone-navy';
}

export function toneStatus(status: string): string {
  if (status === 'sucesso') return 'tone-verde';
  if (status === 'erro') return 'tone-vermelho';
  return 'tone-ambar';
}

export function formatarBytes(b: number | null | undefined): string {
  if (b == null) return '—';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatarSegundos(ms: number): string {
  return `${(ms / 1000).toFixed(1).replace('.', ',')}s`;
}

export function formatarHora(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString('pt-BR', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function formatarDataHora(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('pt-BR');
  } catch {
    return iso;
  }
}
