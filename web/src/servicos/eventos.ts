import { cabecalhosAuth, seNaoAutorizado } from './http';

// Assinatura de eventos do servidor (SSE), com reconexão.
//
// Por que não `EventSource`: ele só faz GET **sem cabeçalho**, e toda rota
// autenticada do SAS exige `Authorization: Bearer`. É a mesma razão pela qual o
// chat já tinha um parser próprio sobre `fetch` + `ReadableStream`
// (`http.ts::streamSSE`) — este arquivo é o irmão dele para streams LONGOS.
//
// E as diferenças em relação ao do chat não são detalhe; são o que separa um
// stream de dez segundos de um que fica aberto o expediente inteiro:
//
//   * **reconexão com recuo.** O do chat é one-shot: pede uma resposta e acaba.
//     Este atravessa túnel, troca de wi-fi e tela bloqueada, e precisa voltar
//     sozinho — com espera crescente, senão um servidor fora do ar leva um
//     cliente a martelá-lo a cada 100 ms;
//   * **comentário de heartbeat.** O servidor manda `: ping` a cada 25 s porque
//     o nginx corta conexão silenciosa em 300 s. Linha que começa com `:` é
//     comentário no protocolo e tem de ser ignorada — tratá-la como evento
//     dispararia um refetch por minuto, para sempre;
//   * **401 encerra de vez.** Sessão morta não se resolve tentando de novo, e
//     reconectar em loop com token inválido é um ataque de negação de serviço
//     contra o próprio servidor.

/** Um evento do servidor: o nome e o que veio no `data:`, já desserializado. */
export interface EventoDoServidor {
  nome: string;
  dados: Record<string, unknown>;
}

const ESPERA_INICIAL_MS = 1_000;
const ESPERA_MAXIMA_MS = 30_000;

/**
 * Mantém uma assinatura viva até o `AbortSignal` disparar.
 *
 * Devolve uma `Promise` que resolve quando a assinatura termina de vez —
 * útil em teste, ignorável em componente.
 */
export async function assinarEventos(
  caminho: string,
  onEvento: (evento: EventoDoServidor) => void,
  sinal: AbortSignal,
): Promise<void> {
  let espera = ESPERA_INICIAL_MS;

  while (!sinal.aborted) {
    try {
      const res = await fetch(`/api${caminho}`, {
        headers: { ...cabecalhosAuth(), Accept: 'text/event-stream' },
        signal: sinal,
      });

      if (res.status === 401) {
        seNaoAutorizado(res.status, caminho);
        return;
      }
      if (!res.ok || !res.body) throw new Error(`GET ${caminho} → ${res.status}`);

      // Chegou até aqui: a conexão vale. Zerar a espera evita que uma queda
      // antiga continue penalizando reconexões futuras.
      espera = ESPERA_INICIAL_MS;
      await consumir(res.body, onEvento);
    } catch (erro) {
      // `AbortError` é saída limpa — o componente desmontou.
      if (sinal.aborted) return;
      void erro;
    }

    if (sinal.aborted) return;
    await dormir(espera, sinal);
    espera = Math.min(espera * 2, ESPERA_MAXIMA_MS);
  }
}

/** Lê o corpo até o fim, entregando um evento por bloco `\n\n`. */
async function consumir(
  corpo: ReadableStream<Uint8Array>,
  onEvento: (evento: EventoDoServidor) => void,
): Promise<void> {
  const leitor = corpo.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await leitor.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });

    let sep = buffer.indexOf('\n\n');
    while (sep >= 0) {
      const evento = parsear(buffer.slice(0, sep));
      buffer = buffer.slice(sep + 2);
      if (evento) onEvento(evento);
      sep = buffer.indexOf('\n\n');
    }
  }
}

/** `null` para comentário (`: ping`) e para bloco sem `data:`. */
export function parsear(bloco: string): EventoDoServidor | null {
  let nome = 'message';
  const partes: string[] = [];

  for (const linha of bloco.split('\n')) {
    // Comentário do protocolo. É o heartbeat, e tratá-lo como evento
    // dispararia um refetch a cada 25 s para sempre.
    if (linha.startsWith(':')) continue;
    if (linha.startsWith('event:')) nome = linha.slice(6).trim();
    else if (linha.startsWith('data:')) partes.push(linha.slice(5).trim());
  }
  if (!partes.length) return null;

  try {
    const dados = JSON.parse(partes.join('\n')) as Record<string, unknown>;
    return { nome, dados };
  } catch {
    // Bloco malformado não pode derrubar o stream: o próximo evento chega
    // igual, e a tela só perde um aviso.
    return null;
  }
}

function dormir(ms: number, sinal: AbortSignal): Promise<void> {
  return new Promise((resolver) => {
    const id = setTimeout(resolver, ms);
    sinal.addEventListener('abort', () => { clearTimeout(id); resolver(); }, { once: true });
  });
}
