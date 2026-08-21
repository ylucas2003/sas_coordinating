// Reducer do streaming do chat.
//
// A versão anterior remendava o DOM a cada evento: guardava a bolha ativa, o
// texto acumulado, o nó de texto e um Map de traces, e trocava elementos no
// lugar. Aqui os eventos viram estado e o React reconcilia — o que importa
// porque a ordem dos eventos não é garantida e a lógica de "qual trace é
// esta" fica explícita.
//
// Testado em chatStream.test.ts.

import type { ArtefatoChat, ToolCall } from '../tipos/chat';

export interface TraceTool {
  id: string;
  nome: string;
  args: Record<string, unknown>;
  resumo: string | null;
  finalizada: boolean;
}

export interface EstadoStream {
  /** Texto acumulado token a token. */
  texto: string;
  traces: TraceTool[];
  erros: string[];
  /** Preenchido no evento `end`: substitui o texto cru pelo markdown final. */
  final: { texto: string; artefatos: ArtefatoChat[] } | null;
  /** Título gerado pelo backend para a thread, quando vem. */
  titulo: string | null;
}

export const ESTADO_INICIAL: EstadoStream = {
  texto: '', traces: [], erros: [], final: null, titulo: null,
};

interface EventoBruto {
  nome: string;
  dados: unknown;
}

/**
 * Artefatos renderizáveis produzidos pelas tools da volta.
 *
 * Só gráficos e CSV viram artefato; o resto do resultado da tool já foi
 * incorporado ao texto da resposta pelo próprio agente.
 */
export function extrairArtefatos(toolCalls: readonly ToolCall[] = []): ArtefatoChat[] {
  const artefatos: ArtefatoChat[] = [];

  for (const tc of toolCalls) {
    const r = tc.resultado;
    if (!r || r.erro) continue;
    const nome = tc.nome ?? tc.name;

    if (nome === 'gerar_grafico' && (r.tipo === 'histograma' || r.tipo === 'linha_temporal')) {
      artefatos.push({ tipo: r.tipo, titulo: r.titulo, payload: r.payload });
    }
    if (nome === 'exportar_csv' && r.tipo === 'csv') {
      artefatos.push({
        tipo: 'csv',
        titulo: r.titulo,
        payload: { conteudo: r.conteudo, nLinhas: r.nLinhas },
      });
    }
  }
  return artefatos;
}

export function reduzirEvento(estado: EstadoStream, evento: EventoBruto): EstadoStream {
  const dados = (evento.dados ?? {}) as Record<string, any>;

  switch (evento.nome) {
    // Marcadores de ciclo de vida sem efeito na UI.
    case 'start':
    case 'user_salvo':
      return estado;

    case 'tool_call_start':
      return {
        ...estado,
        traces: [
          ...estado.traces,
          {
            id: String(dados.tool_call_id ?? estado.traces.length),
            nome: String(dados.nome ?? ''),
            args: (dados.args ?? {}) as Record<string, unknown>,
            resumo: null,
            finalizada: false,
          },
        ],
      };

    case 'tool_call_end': {
      const id = String(dados.tool_call_id ?? '');
      // Fecha a trace mantendo nome e args, que só o evento de início trouxe.
      return {
        ...estado,
        traces: estado.traces.map((t) =>
          t.id === id ? { ...t, resumo: dados.resumido ?? null, finalizada: true } : t,
        ),
      };
    }

    case 'token':
      return { ...estado, texto: estado.texto + (dados.texto ?? '') };

    case 'erro':
      return { ...estado, erros: [...estado.erros, String(dados.mensagem ?? 'erro desconhecido')] };

    case 'titulo':
      return { ...estado, titulo: dados.titulo ?? null };

    case 'end':
      return {
        ...estado,
        final: {
          texto: dados.texto_final ?? estado.texto,
          artefatos: extrairArtefatos(dados.tool_calls ?? []),
        },
      };

    default:
      return estado;
  }
}
