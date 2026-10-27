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
    /**
     * O artefato que QUALQUER tool pode anexar ao resultado (docs/43 §4.1).
     * `unknown` de propósito: quem escolheu o tipo foi o modelo, e ele só vira
     * `ArtefatoChat` depois de conferido no catálogo (`dominio/chatStream.ts`).
     */
    artefato?: unknown;
    /** O resto do resultado: cada tool devolve o próprio dado ao lado. */
    [campo: string]: unknown;
  } | null;
}

export interface ArtefatoChat {
  tipo:
    // Os dos formatos próprios das tools da coordenação: os dois gráficos de
    // `gerar_grafico`, o CSV de `exportar_csv` e o link de `navegar_para`.
    | 'histograma'
    | 'linha_temporal'
    | 'csv'
    | 'navegacao'
    // Os novos do catálogo do aluno (docs/27 §7), que chegam no campo
    // `artefato` — os dois gráficos acima também podem chegar por ele
    // (`CATALOGO_DE_ARTEFATOS`, dominio/chatStream.ts).
    | 'barras_corte'
    | 'questao'
    | 'lista_questoes'
    | 'prova'
    | string;
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
