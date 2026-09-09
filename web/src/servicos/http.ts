// Transporte HTTP — conversa com o FastAPI.
//
// Porte de `js/services/http-client.js` com duas mudanças deliberadas:
//
//  1. Sem cache próprio. O `cacheGet` do cliente antigo (um Map de Promises
//     por path, invalidado à mão depois de cada mutação) é substituído pelo
//     TanStack Query, que já faz deduplicação, invalidação e revalidação.
//  2. `BASE_URL` fixo em `/api`. O cliente antigo detectava `localhost` para
//     apontar direto ao uvicorn em :8000, porque não havia build step para
//     injetar variável. Agora o dev server do Vite faz proxy de `/api`
//     (ver vite.config.ts), então dev e produção usam o mesmo caminho
//     relativo — e o CORS deixa de existir dos dois lados.
//
// Pelas regras de acesso a dados (alunos menores de idade), o frontend não
// fala direto com o banco: toda leitura passa por aqui.

import * as sessao from './sessao';

const BASE_URL = '/api';

// ─── O teto de tempo, e por que ele NÃO vale para streaming ──────────────
//
// `fetch` não tem tempo limite nenhum. Uma requisição cuja resposta nunca chega
// — o wi-fi que oscila e leva a conexão junto — fica pendente para sempre, e a
// promessa **nunca assenta**: nem `then`, nem `catch`, nem `finally`. Quem
// esperava por ela espera para sempre também. Foi assim que o leitor de QR do
// balcão parou de ler com a fila na frente, sem erro nenhum na tela
// (`telas/Cantina/AoVivo.tsx`, cuja trava de "uma confirmação por vez" só é
// solta no `finally`).
//
// ⚠️ **O teto vale para requisição normal e não para streaming — e a separação
// não é um sinalizador, é a forma do arquivo.** Só `requisitar()` é
// pergunta-e-resposta. Os dois streams do app têm `fetch` próprio, cada um com
// o seu fim de vida: `streamSSE()` aqui embaixo (o chat, que dura o quanto o
// modelo levar para responder) e `servicos/eventos.ts` (os três canais de tempo
// real da cantina, abertos o expediente inteiro, com heartbeat e reconexão).
// Um teto aplicado a eles cortaria a resposta do chat no meio e derrubaria os
// canais a cada N segundos — o remédio seria pior que a doença, e mais difícil
// de enxergar.
//
// O NÚMERO é o mesmo do nginx (`infra/vps/nginx.conf`: `proxy_read_timeout
// 300s`), e isso é escolha, não coincidência. Passado esse ponto o gateway já
// desistiu do upstream, então **nenhuma resposta legítima pode mais chegar**:
// o teto não tem como cortar uma requisição que o servidor ainda ia responder.
// É o que separa este número de um chute — as rotas lentas do SAS (o lote do
// Canvas, os insights do LLM) são calibradas para caber nesses mesmos 300 s;
// ver `TETO_NOTAS_POR_LOTE` em `api/app/routes/ciclos.py`, que existe
// justamente para não estourá-los. Qualquer teto mais curto seria eu adivinhando
// quanto tempo o Canvas leva, e erraria em silêncio: a tela diria "falhou" com o
// servidor ainda escrevendo.
//
// ⚠️ E é por isso que ele **não é o prazo de uma tela**. Cinco minutos de balcão
// cego continuam sendo cinco minutos, e quem conhece a tarefa é quem sabe quanto
// ela pode esperar — por isso o prazo é PEDÍVEL na chamada
// (`OpcoesDeRequisicao.tempoLimiteMs`). O pedido só encurta: acima deste teto não
// há resposta legítima para esperar, então deixar alguém pedir mais seria vender
// um tempo que o gateway não entrega.
//
// ⚠️ Antes daqui esta decisão dizia "quem precisa de resposta em segundos põe o
// próprio relógio em cima da chamada", e era meia verdade. Um `setTimeout` ao
// lado da chamada **não cancela a requisição**: ele solta o estado local e deixa
// a promessa pendurada. Funciona onde o estado é um `ref` — `AoVivo.tsx` solta
// `ocupadoRef` e a câmera volta a ler —, e NÃO funciona onde o estado é a própria
// promessa: no React Query o `fetchStatus` fica em `fetching` para sempre, e a
// tela do aluno (`telas/Aluno/CantinaRetirada.tsx`) ficava em "Renovando o
// código…" sem QR, sem erro e sem saída, com a fila na frente (docs/40 §6).
const TEMPO_LIMITE_MS = 300_000;

/** O que quem chama pode pedir a mais desta requisição. */
export interface OpcoesDeRequisicao {
  /**
   * O teto de tempo DESTA chamada, em ms — e ele só encurta.
   *
   * Um valor maior que `TEMPO_LIMITE_MS` é ignorado (fica no teto do gateway), e
   * um valor absurdo — zero, negativo, `NaN` — também: um teto que aborta antes
   * de a requisição sair é pior que teto nenhum, porque falha sempre e parece
   * problema de rede.
   */
  tempoLimiteMs?: number;
  /**
   * O sinal de quem chamou — o desmonte da tela, o cancelamento do React Query,
   * o botão que substitui uma tentativa pendurada por uma nova.
   *
   * Sem ele, cancelar do lado de fora só descarta o RESULTADO: a requisição
   * continua de pé até o teto. É o que faz `query.cancel()` do React Query virar
   * gesto vazio quando a `queryFn` não repassa o `signal` que recebeu.
   */
  sinal?: AbortSignal;
}

/**
 * O prazo desta chamada, dentro do teto do gateway.
 *
 * Pedido ausente ou sem sentido cai no teto — a chamada continua exatamente como
 * era antes de existir esta opção.
 */
function prazoDaChamada(pedido: number | undefined): number {
  if (pedido == null || !Number.isFinite(pedido) || pedido <= 0) return TEMPO_LIMITE_MS;
  return Math.min(TEMPO_LIMITE_MS, pedido);
}

/** Erro de API que preserva o status e o `detail` explicado pelo backend. */
export class ErroApi extends Error {
  readonly status: number;

  constructor(mensagem: string, status: number) {
    super(mensagem);
    this.name = 'ErroApi';
    this.status = status;
  }
}

export function cabecalhosAuth(): Record<string, string> {
  const t = sessao.token();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

/**
 * 401 significa sessão expirada ou token inválido: derruba a sessão e manda
 * para o login. É tratado aqui, e não em cada chamada, porque pode acontecer
 * em qualquer requisição.
 *
 * As rotas de `/auth/` são a exceção: ali o 401 é "senha errada", e mandar o
 * usuário para o login recarregaria a página que ele já está usando, apagando
 * a mensagem de erro antes de ele conseguir ler.
 */
export function seNaoAutorizado(status: number, caminho: string): void {
  if (status !== 401 || caminho.startsWith('/auth/')) return;
  sessao.encerrar();
  window.location.replace('/login');
}

/** Extrai o `detail` do FastAPI; sem ele o usuário só veria "→ 502". */
async function detalhe(res: Response): Promise<string> {
  try {
    const corpo = (await res.json()) as { detail?: string };
    return corpo.detail ?? '';
  } catch {
    return '';
  }
}

/**
 * A falha SEM resposta, dita para gente.
 *
 * `status: 0` é a convenção que `postArquivo` já usa aqui embaixo para "não
 * houve resposta HTTP nenhuma" — e é o que distingue este caso de um 4xx: não há
 * veredito do servidor, só ausência. Sem esta tradução a tela mostraria o texto
 * do motor de JS (`TypeError: Failed to fetch`, `signal is aborted without
 * reason`) para quem está no balcão, e `erro instanceof ErroApi` — que é como
 * toda tela decide o que escrever — daria falso.
 *
 * O que não for falha de transporte volta intacto: um corpo com JSON quebrado é
 * `SyntaxError` e continua sendo, porque "sem conexão" seria mentira.
 */
function comoFalhaDeRede(erro: unknown): unknown {
  if (erro instanceof Error && erro.name === 'AbortError') {
    return new ErroApi('O servidor não respondeu a tempo. Tente de novo.', 0);
  }
  if (erro instanceof TypeError) {
    return new ErroApi('Sem resposta do servidor. Verifique a conexão e tente de novo.', 0);
  }
  return erro;
}

async function requisitar<T>(
  metodo: string,
  caminho: string,
  corpo?: unknown,
  { tempoLimiteMs, sinal }: OpcoesDeRequisicao = {},
): Promise<T> {
  const abortador = new AbortController();
  const relogio = window.setTimeout(() => abortador.abort(), prazoDaChamada(tempoLimiteMs));

  // Dois gatilhos, um abortador: o teto e quem chamou. `AbortSignal.any([...])`
  // faria isto em uma linha, e é Safari 17.4 — mais novo que a base de aparelhos
  // que abre esta tela na fila (o mesmo motivo que já obriga `useTelaAcesa` a
  // degradar em silêncio). Chamar um estático que não existe não degrada: joga
  // `TypeError` e derruba TODA requisição naquele aparelho.
  const propagar = () => abortador.abort();
  if (sinal) {
    if (sinal.aborted) abortador.abort();
    else sinal.addEventListener('abort', propagar);
  }

  try {
    const res = await fetch(`${BASE_URL}${caminho}`, {
      method: metodo,
      headers: {
        ...(corpo !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...cabecalhosAuth(),
      },
      body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
      signal: abortador.signal,
    });

    seNaoAutorizado(res.status, caminho);
    if (!res.ok) {
      throw new ErroApi((await detalhe(res)) || `${metodo} ${caminho} → ${res.status}`, res.status);
    }
    // O `await` aqui não é decoração: sem ele a leitura do corpo escaparia do
    // `try` e do relógio. O nginx da produção serve `/api/` com
    // `proxy_buffering off`, então a resposta chega em pedaços — um corpo que
    // para no meio prenderia a promessa DEPOIS de os cabeçalhos terem chegado,
    // que é o mesmo travamento com outra cara.
    return (await res.json()) as T;
  } catch (erro) {
    // ⚠️ Um aborto de quem chamou volta com a mesma frase de "não respondeu a
    // tempo", e isso é aceito: quem cancela sabe que cancelou, e o React Query
    // descarta a rejeição da tentativa que ele mesmo substituiu (`cancel({
    // silent: true })`). Nenhuma tela lê essa frase por esse caminho.
    throw comoFalhaDeRede(erro);
  } finally {
    // Sempre: um relógio de 5 minutos vivo por requisição bem-sucedida seguraria
    // a closure inteira, e esta tela fica horas aberta. O ouvinte do sinal de
    // fora sai junto — ele aponta para este abortador, que já morreu.
    window.clearTimeout(relogio);
    sinal?.removeEventListener('abort', propagar);
  }
}

export function get<T>(caminho: string, opcoes?: OpcoesDeRequisicao): Promise<T> {
  return requisitar<T>('GET', caminho, undefined, opcoes);
}

export function post<T>(
  caminho: string,
  corpo?: unknown,
  opcoes?: OpcoesDeRequisicao,
): Promise<T> {
  return requisitar<T>('POST', caminho, corpo, opcoes);
}

export function patch<T>(
  caminho: string,
  corpo: unknown,
  opcoes?: OpcoesDeRequisicao,
): Promise<T> {
  return requisitar<T>('PATCH', caminho, corpo, opcoes);
}

/**
 * `PUT` existe para o estado de estudo do banco de questões: a linha
 * (aluno, questão) nasce na primeira marcação e é substituída nas seguintes —
 * upsert, não remendo de recurso existente (docs/22 §P6).
 */
export function put<T>(caminho: string, corpo: unknown, opcoes?: OpcoesDeRequisicao): Promise<T> {
  return requisitar<T>('PUT', caminho, corpo, opcoes);
}

export function del<T>(caminho: string, opcoes?: OpcoesDeRequisicao): Promise<T> {
  return requisitar<T>('DELETE', caminho, undefined, opcoes);
}

/** Monta uma query string, ignorando valores nulos. */
/**
 * Query string a partir de um objeto. `null`/`undefined` somem.
 *
 * Array vira parâmetro REPETIDO (`?anos=2024&anos=2023`), que é o que o FastAPI
 * lê como `list[int]` sem parser próprio. `String([2024, 2023])` daria
 * "2024,2023" numa chave só, e o backend receberia um inteiro malformado.
 *
 * ⚠️ A CHAVE É O NOME DO CAMPO. `qs()` serializa o objeto de filtros direto,
 * sem tabela de tradução, então o campo do front e o parâmetro da rota têm de
 * ter o mesmo nome. `anos` no front contra `ano` na rota já custou um filtro
 * que não filtrava, em silêncio — `test_colecao_banco.py` trava isso agora.
 * Array vazio não emite nada — e isso é deliberado: no filtro de anos, lista
 * vazia significa "todos", igual a ausente.
 */
export function qs(
  params: Record<
    string,
    string | number | boolean | readonly (string | number)[] | null | undefined
  >,
): string {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(params)) {
    if (valor == null) continue;
    if (Array.isArray(valor)) {
      for (const item of valor) busca.append(chave, String(item));
    } else {
      busca.set(chave, String(valor));
    }
  }
  const texto = busca.toString();
  return texto ? `?${texto}` : '';
}

// ─── Upload com progresso ────────────────────────────────────────────────
// XHR, e não fetch, porque só o XHR reporta progresso de upload de bytes — a
// tela de importação mostra uma barra durante o envio da planilha.

export interface OpcoesUpload {
  campos?: Record<string, string | null | undefined>;
  /** Bytes enviados / total, durante o envio. */
  onProgresso?: (enviados: number, total: number) => void;
  /** Disparado quando o último byte chega ao servidor. */
  onEnviado?: () => void;
}

export function postArquivo<T>(
  caminho: string,
  arquivo: File,
  { campos = {}, onProgresso, onEnviado }: OpcoesUpload = {},
): Promise<T> {
  return new Promise<T>((resolver, rejeitar) => {
    const form = new FormData();
    form.append('arquivo', arquivo);
    for (const [chave, valor] of Object.entries(campos)) {
      if (valor != null) form.append(chave, String(valor));
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}${caminho}`);

    const t = sessao.token();
    if (t) xhr.setRequestHeader('Authorization', `Bearer ${t}`);

    if (onProgresso) {
      xhr.upload.addEventListener('progress', (ev) => {
        if (ev.lengthComputable) onProgresso(ev.loaded, ev.total);
      });
    }
    if (onEnviado) {
      xhr.upload.addEventListener('load', () => onEnviado());
    }

    xhr.addEventListener('load', () => {
      let dados: { detail?: string } = {};
      try {
        dados = JSON.parse(xhr.responseText);
      } catch {
        /* resposta sem JSON — cai no erro genérico abaixo */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolver(dados as T);
      } else {
        seNaoAutorizado(xhr.status, caminho);
        rejeitar(new ErroApi(dados.detail || `POST ${caminho} → ${xhr.status}`, xhr.status));
      }
    });

    xhr.addEventListener('error', () => {
      rejeitar(new ErroApi('Falha de rede ao enviar a planilha (servidor offline?).', 0));
    });
    xhr.addEventListener('abort', () => {
      rejeitar(new ErroApi('Upload cancelado.', 0));
    });

    xhr.send(form);
  });
}

// ─── Streaming SSE ───────────────────────────────────────────────────────
// Parser leve sobre fetch + ReadableStream. `EventSource` não serve: ele só
// faz GET, e o chat precisa mandar a mensagem no corpo de um POST.

export interface EventoSSE {
  nome: string;
  dados: unknown;
}

/**
 * Envia `corpo` por POST e chama `onEvento` a cada evento do stream.
 *
 * ⚠️ **Sem `AbortController` e sem teto de tempo, de propósito** — não é
 * esquecimento, e não "falta padronizar com `requisitar()`". Aqui a promessa
 * dura o quanto o modelo levar para responder, e uma volta de tool calling passa
 * de 60 s com folga (é o que o `proxy_read_timeout 300s` do nginx compra). Um
 * teto por requisição cortaria a resposta do chat no meio de uma frase, e o
 * usuário veria a bolha parar sem erro. O que encerra este stream é o servidor
 * fechar o corpo.
 */
export async function streamSSE(
  caminho: string,
  corpo: unknown,
  onEvento: (evento: EventoSSE) => void,
): Promise<void> {
  const res = await fetch(`${BASE_URL}${caminho}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...cabecalhosAuth() },
    body: JSON.stringify(corpo),
  });

  seNaoAutorizado(res.status, caminho);
  if (!res.ok) {
    throw new ErroApi((await detalhe(res)) || `POST ${caminho} → ${res.status}`, res.status);
  }
  if (!res.body) throw new ErroApi('Resposta do chat veio sem corpo.', res.status);

  const leitor = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // Cada evento é separado por '\n\n'; dentro dele, linhas 'event:' e 'data:'.
  for (;;) {
    const { done, value } = await leitor.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep = buffer.indexOf('\n\n');
    while (sep >= 0) {
      const bloco = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const evento = parsearEvento(bloco);
      if (evento) onEvento(evento);
      sep = buffer.indexOf('\n\n');
    }
  }

  // Resto sem '\n\n' final: pode ser o último evento.
  if (buffer.trim()) {
    const evento = parsearEvento(buffer);
    if (evento) onEvento(evento);
  }
}

function parsearEvento(bloco: string): EventoSSE | null {
  let nome = 'message';
  const partes: string[] = [];

  for (const linha of bloco.split('\n')) {
    if (linha.startsWith('event:')) nome = linha.slice(6).trim();
    else if (linha.startsWith('data:')) partes.push(linha.slice(5).trim());
  }
  if (!partes.length) return null;

  let dados: unknown = {};
  try {
    dados = JSON.parse(partes.join('\n'));
  } catch {
    /* evento sem JSON válido — entrega o objeto vazio, como no cliente antigo */
  }
  return { nome, dados };
}
