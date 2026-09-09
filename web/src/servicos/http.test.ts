import { afterEach, describe, expect, it, vi } from 'vitest';

import { ErroApi, get, post, streamSSE } from './http';

// O transporte, e o único comportamento dele que não se vê lendo o código: o
// teto de tempo. Um `fetch` sem `signal` fica pendente PARA SEMPRE quando a
// resposta não volta — a promessa nunca assenta, e quem esperava por ela também
// não. Foi assim que o leitor de QR do balcão parou de ler com a fila na frente.
//
// `http.ts` fala com o browser (`window.setTimeout`, `sessionStorage` pelo
// `sessao`, `fetch`), e em node nenhum dos três existe. O preparo abaixo empresta
// as peças; nada aqui simula comportamento.
function comBrowser() {
  vi.stubGlobal('window', globalThis);
  vi.stubGlobal('sessionStorage', {
    getItem: () => null,
    setItem: () => undefined,
    removeItem: () => undefined,
  });
}

/** O erro que a chamada levantou — e falha o teste se ela não levantar nenhum. */
async function erroDe(chamada: Promise<unknown>): Promise<ErroApi> {
  try {
    await chamada;
  } catch (erro) {
    return erro as ErroApi;
  }
  throw new Error('a chamada devia ter falhado, e voltou normalmente');
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('teto de tempo', () => {
  it('a requisição que não volta vira erro — não fica pendurada', async () => {
    comBrowser();
    vi.useFakeTimers();
    // O servidor que nunca responde: a promessa do `fetch` só assenta se
    // alguém abortar. É o wi-fi que oscilou e levou a conexão junto.
    vi.stubGlobal('fetch', (_url: string, init: RequestInit) => new Promise((_, rejeitar) => {
      init.signal?.addEventListener('abort', () => {
        rejeitar(new DOMException('abortada', 'AbortError'));
      });
    }));

    let assentou = false;
    const erro = get('/qualquer').catch((e) => { assentou = true; return e; });

    // Antes do teto ela CONTINUA esperando: cortar cedo mataria as rotas lentas
    // do SAS (o lote do Canvas, os insights do LLM), que cabem nos 300 s do
    // gateway de propósito.
    await vi.advanceTimersByTimeAsync(299_000);
    expect(assentou).toBe(false);

    await vi.advanceTimersByTimeAsync(2_000);
    const resultado = await erro;
    expect(resultado).toBeInstanceOf(ErroApi);
    expect((resultado as ErroApi).status).toBe(0);
  });

  it('falha de rede vira ErroApi, e não o texto do motor de JS', async () => {
    comBrowser();
    // É o que o browser levanta quando não há para onde mandar a requisição.
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Failed to fetch')));

    const erro = await erroDe(get('/qualquer'));
    expect(erro).toBeInstanceOf(ErroApi);
    // `status: 0` é a convenção de "não houve resposta HTTP nenhuma": é o que
    // `dominio/cantina.ts` lê para saber que ler o código de novo é a ação certa.
    expect(erro.status).toBe(0);
    expect(erro.message).not.toContain('Failed to fetch');
  });

  it('a recusa do servidor passa inteira, com status e frase', async () => {
    comBrowser();
    vi.stubGlobal('fetch', () => Promise.resolve(
      new Response(JSON.stringify({ detail: 'Esta refeição já foi retirada.' }), { status: 409 }),
    ));

    const erro = await erroDe(get('/qualquer'));
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.status).toBe(409);
    expect(erro.message).toBe('Esta refeição já foi retirada.');
  });

  it('corpo com JSON quebrado não vira "sem conexão"', async () => {
    comBrowser();
    // A tradução de falha de rede não pode engolir tudo: dizer "verifique a
    // conexão" para um corpo malformado manda procurar defeito no lugar errado.
    vi.stubGlobal('fetch', () => Promise.resolve(new Response('isto não é json')));

    const erro = await get('/qualquer').catch((e) => e);
    expect(erro).not.toBeInstanceOf(ErroApi);
    expect(erro).toBeInstanceOf(SyntaxError);
  });
});

describe('quem chama pode pedir um prazo mais curto', () => {
  /** Um servidor que nunca responde: só um aborto assenta esta promessa — e um
      sinal que JÁ chegou abortado rejeita na hora, como o `fetch` de verdade. */
  function servidorMudo() {
    vi.stubGlobal('fetch', (_url: string, init: RequestInit) => new Promise((_, rejeitar) => {
      const parar = () => rejeitar(new DOMException('abortada', 'AbortError'));
      if (init.signal?.aborted) parar();
      else init.signal?.addEventListener('abort', parar);
    }));
  }

  it('o prazo pedido vale, e a chamada assenta nele', async () => {
    comBrowser();
    vi.useFakeTimers();
    servidorMudo();

    // 15 s é o prazo da renovação do QR (`PRAZO_DA_RENOVACAO_MS`): sem poder
    // pedi-lo, a tela do aluno esperava os 300 s do gateway com o código já fora
    // da placa — "Renovando o código…" para sempre, com a fila na frente.
    let assentou = false;
    const erro = post('/me/cantina/retiradas/c1', {}, { tempoLimiteMs: 15_000 })
      .catch((e) => { assentou = true; return e; });

    await vi.advanceTimersByTimeAsync(14_000);
    expect(assentou).toBe(false);

    await vi.advanceTimersByTimeAsync(2_000);
    expect(await erro).toBeInstanceOf(ErroApi);
    expect(((await erro) as ErroApi).status).toBe(0);
  });

  it('pedir MAIS que o gateway não sobe o teto', async () => {
    comBrowser();
    vi.useFakeTimers();
    servidorMudo();

    // Passados os 300 s do `proxy_read_timeout` do nginx, nenhuma resposta
    // legítima pode mais chegar: esperar dez minutos seria vender um tempo que o
    // gateway não entrega.
    let assentou = false;
    const erro = get('/qualquer', { tempoLimiteMs: 600_000 })
      .catch((e) => { assentou = true; return e; });

    await vi.advanceTimersByTimeAsync(299_000);
    expect(assentou).toBe(false);
    await vi.advanceTimersByTimeAsync(2_000);
    expect(await erro).toBeInstanceOf(ErroApi);
  });

  it('prazo sem sentido cai no teto, em vez de abortar antes de sair', async () => {
    comBrowser();
    vi.useFakeTimers();
    servidorMudo();

    let assentou = false;
    const erro = get('/qualquer', { tempoLimiteMs: 0 }).catch((e) => { assentou = true; return e; });

    await vi.advanceTimersByTimeAsync(299_000);
    expect(assentou).toBe(false);
    await vi.advanceTimersByTimeAsync(2_000);
    expect(await erro).toBeInstanceOf(ErroApi);
  });

  it('o sinal de quem chamou aborta a requisição de verdade', async () => {
    comBrowser();
    servidorMudo();

    // É o que faz o cancelamento do React Query (desmonte da tela, ou o botão
    // que substitui a tentativa pendurada) parar a requisição, e não só descartar
    // o resultado dela.
    const controle = new AbortController();
    const erro = erroDe(get('/qualquer', { sinal: controle.signal }));
    controle.abort();
    expect((await erro).status).toBe(0);
  });

  it('sinal já abortado nem chega a esperar', async () => {
    comBrowser();
    servidorMudo();

    const controle = new AbortController();
    controle.abort();
    expect((await erroDe(get('/qualquer', { sinal: controle.signal }))).status).toBe(0);
  });
});

describe('o teto NÃO alcança o streaming', () => {
  it('requisição normal leva sinal de aborto; o stream do chat, não', async () => {
    comBrowser();
    const sinais: Array<AbortSignal | null | undefined> = [];
    vi.stubGlobal('fetch', (url: string, init: RequestInit) => {
      sinais.push(init.signal);
      // Uma responde JSON, a outra responde um evento SSE: são protocolos
      // diferentes, e é justamente por isso que são funções diferentes.
      return Promise.resolve(
        new Response(url.includes('/chat/') ? 'event: fim\ndata: {}\n\n' : '[]'),
      );
    });

    await get('/alunos');
    await streamSSE('/chat/threads/1/mensagens', { conteudo: 'oi' }, () => undefined);

    // ⚠️ Este é o teste que protege a decisão: um teto por requisição aplicado ao
    // stream cortaria a resposta do chat no meio de uma frase e derrubaria os
    // três canais de tempo real da cantina (`servicos/eventos.ts`, que tem
    // `fetch` próprio pelo mesmo motivo). A separação é a forma do arquivo — só
    // `requisitar()` é pergunta-e-resposta —, e é isto que a trava.
    expect(sinais[0]).toBeInstanceOf(AbortSignal);
    expect(sinais[1]).toBeUndefined();
  });
});
