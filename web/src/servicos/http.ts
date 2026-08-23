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

/** Erro de API que preserva o status e o `detail` explicado pelo backend. */
export class ErroApi extends Error {
  readonly status: number;

  constructor(mensagem: string, status: number) {
    super(mensagem);
    this.name = 'ErroApi';
    this.status = status;
  }
}

function cabecalhosAuth(): Record<string, string> {
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
function seNaoAutorizado(status: number, caminho: string): void {
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

async function requisitar<T>(metodo: string, caminho: string, corpo?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${caminho}`, {
    method: metodo,
    headers: {
      ...(corpo !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...cabecalhosAuth(),
    },
    body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
  });

  seNaoAutorizado(res.status, caminho);
  if (!res.ok) {
    throw new ErroApi((await detalhe(res)) || `${metodo} ${caminho} → ${res.status}`, res.status);
  }
  return res.json() as Promise<T>;
}

export function get<T>(caminho: string): Promise<T> {
  return requisitar<T>('GET', caminho);
}

export function post<T>(caminho: string, corpo?: unknown): Promise<T> {
  return requisitar<T>('POST', caminho, corpo);
}

export function patch<T>(caminho: string, corpo: unknown): Promise<T> {
  return requisitar<T>('PATCH', caminho, corpo);
}

/**
 * `PUT` existe para o estado de estudo do banco de questões: a linha
 * (aluno, questão) nasce na primeira marcação e é substituída nas seguintes —
 * upsert, não remendo de recurso existente (docs/22 §P6).
 */
export function put<T>(caminho: string, corpo: unknown): Promise<T> {
  return requisitar<T>('PUT', caminho, corpo);
}

export function del<T>(caminho: string): Promise<T> {
  return requisitar<T>('DELETE', caminho);
}

/** Monta uma query string, ignorando valores nulos. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(params)) {
    if (valor != null) busca.set(chave, String(valor));
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

/** Envia `corpo` por POST e chama `onEvento` a cada evento do stream. */
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

    let sep: number;
    while ((sep = buffer.indexOf('\n\n')) >= 0) {
      const bloco = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const evento = parsearEvento(bloco);
      if (evento) onEvento(evento);
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
