// Tipos do chat — threads, mensagens e o que o stream SSE entrega.

export interface ChatThreadResumo {
  id: string;
  titulo: string | null;
  ultimaMsgEm?: string | null;
  arquivada?: boolean;
}

export interface ToolCall {
  name?: string;
  nome?: string;
  arguments?: Record<string, unknown>;
  args?: Record<string, unknown>;
  resultado?: {
    erro?: string;
    tipo?: string;
    titulo?: string;
    payload?: unknown;
    conteudo?: string;
    nLinhas?: number;
  } | null;
}

export interface ArtefatoChat {
  tipo: 'histograma' | 'linha_temporal' | 'csv' | 'navegacao' | string;
  titulo?: string;
  payload?: unknown;
}

export interface MensagemChat {
  papel: 'user' | 'assistant' | 'system' | 'tool';
  conteudo?: string | null;
  toolCalls?: ToolCall[];
  artefatos?: ArtefatoChat[];
}

export interface ChatThreadDetalhe extends ChatThreadResumo {
  mensagens: MensagemChat[];
}

/** Grupo de exemplos clicáveis na abertura da conversa. */
export interface GrupoSugestoes {
  grupo: string;
  exemplos: string[];
}
