// Client HTTP — conversa com o FastAPI em `BASE_URL`.
//
// Pelas regras de acesso a dados (alunos menores de idade), o frontend
// **não** fala direto com o Supabase. Toda leitura passa pela API.
// Ver decisão pendente #10 em ../../../docs/06-open-questions.md.

// Dev local (localhost/127.*) fala com o uvicorn local; qualquer outro host
// (Render, etc.) fala com a API publicada. Sem build step, então a detecção
// é em runtime mesmo.
const BASE_URL = /^(localhost|127\.)/.test(window.location.hostname)
  ? 'http://localhost:8000'
  : 'https://sas-coordinating.onrender.com';

// Cache em memória das respostas GET. Os dados do SAS só mudam quando entra
// uma planilha nova, então cachear evita rebuscar alunos/notas/simulados a
// cada troca de aba. Guardamos a Promise (não o valor já resolvido) para
// também deduplicar chamadas concorrentes ao mesmo path. Invalidado por
// `limparCacheDados()` após um upload bem-sucedido.
const cacheGet = new Map();

function _authHeaders() {
  const token = sessionStorage.getItem('sas_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function _onUnauthorized(res) {
  if (res.status === 401) {
    sessionStorage.clear();
    window.location.replace('./login.html');
  }
}

async function get(path, { cache = true } = {}) {
  if (cache && cacheGet.has(path)) return cacheGet.get(path);
  const promessa = (async () => {
    const res = await fetch(`${BASE_URL}${path}`, { headers: _authHeaders() });
    _onUnauthorized(res);
    if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
    return res.json();
  })();
  if (cache) {
    cacheGet.set(path, promessa);
    // Não cacheia falhas — se der erro, libera o path pra nova tentativa.
    promessa.catch(() => cacheGet.delete(path));
  }
  return promessa;
}

/** Limpa o cache de GET. Chamar quando os dados mudam (ex.: após upload). */
function limparCacheDados() {
  cacheGet.clear();
}

async function post(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ..._authHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  _onUnauthorized(res);
  if (!res.ok) {
    let detalhe = '';
    try { detalhe = (await res.json()).detail || ''; } catch {}
    throw new Error(detalhe || `POST ${path} → ${res.status}`);
  }
  return res.json();
}

function postArquivo(path, arquivo, campos = {}, { onProgress, onUploaded } = {}) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('arquivo', arquivo);
    for (const [chave, valor] of Object.entries(campos)) {
      if (valor != null) form.append(chave, String(valor));
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}${path}`);

    const token = sessionStorage.getItem('sas_token');
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    // Progresso do upload de bytes (0%–100%).
    if (onProgress) {
      xhr.upload.addEventListener('progress', (ev) => {
        if (ev.lengthComputable) {
          onProgress(ev.loaded, ev.total);
        }
      });
    }

    // Disparado quando o último byte chega ao servidor.
    xhr.upload.addEventListener('load', () => {
      if (onUploaded) onUploaded();
    });

    xhr.addEventListener('load', () => {
      let dados = {};
      try { dados = JSON.parse(xhr.responseText); } catch {}
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(dados);
      } else {
        reject(new Error(dados.detail || `POST ${path} → ${xhr.status}`));
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('Falha de rede ao enviar a planilha (servidor offline?).'));
    });

    xhr.addEventListener('abort', () => {
      reject(new Error('Upload cancelado.'));
    });

    xhr.send(form);
  });
}

export const httpClient = {
  // Alertas
  listarAlertas: () => get('/alertas'),
  resolverAlerta: (id) => post(`/alertas/${encodeURIComponent(id)}/resolver`),

  // Alunos (visão do coordenador)
  listarAlunos: (filtros = {}) => {
    const qs = new URLSearchParams(filtros).toString();
    return get(`/alunos${qs ? `?${qs}` : ''}`);
  },
  obterAluno: (id) => get(`/alunos/${encodeURIComponent(id)}`),
  trajetoriaAluno: (id) => get(`/alunos/${encodeURIComponent(id)}/trajetoria`),
  heatmapAluno: (id) => get(`/alunos/${encodeURIComponent(id)}/heatmap`),
  alunosSimilares: (id, k = 5) => get(`/alunos/${encodeURIComponent(id)}/similares?k=${k}`),

  // Aluno autenticado (visão do próprio aluno)
  obterMe: () => get('/me', { cache: false }),
  trajetoriaMe: () => get('/me/trajetoria', { cache: false }),
  heatmapMe: () => get('/me/heatmap', { cache: false }),
  streakMe: () => get('/me/streak', { cache: false }),
  listarSimuladosMe: () => get('/me/simulados', { cache: false }),
  obterSimuladoMe: (id) => get(`/me/simulado/${encodeURIComponent(id)}`, { cache: false }),
  questoesSimuladoMe: (id) => get(`/me/simulado/${encodeURIComponent(id)}/questoes`, { cache: false }),
  evolucaoMe: () => get('/me/evolucao', { cache: false }),
  insightMe: () => get('/me/insight', { cache: false }),
  trocarSenhaMe: (body) => post('/me/senha', body),

  // Acesso do aluno (staff): zera a senha e libera novo primeiro acesso.
  resetarAcessoAluno: (id, body = {}) =>
    post(`/alunos/${encodeURIComponent(id)}/resetar-acesso`, body),

  // Simulados
  listarSimulados: () => get('/simulados'),
  obterSimulado: (id) => get(`/simulados/${encodeURIComponent(id)}`),
  histogramaSimulado: (id) => get(`/simulados/${encodeURIComponent(id)}/histograma`),
  notasSimulado: (id) => get(`/simulados/${encodeURIComponent(id)}/notas`),
  simuladoPorMateria: (id) => get(`/simulados/${encodeURIComponent(id)}/por-materia`),
  simuladoPorSede: (id) => get(`/simulados/${encodeURIComponent(id)}/por-sede`),
  editarSimulado: (id, body) => patchJson(`/simulados/${encodeURIComponent(id)}`, body),

  // Notas (edição manual)
  editarNota: (alunoId, simuladoId, body) =>
    patchJson(`/notas/${encodeURIComponent(alunoId)}/${encodeURIComponent(simuladoId)}`, body),

  // Ciclos
  listarCiclos: () => get('/ciclos'),
  obterCiclo: (id) => get(`/ciclos/${encodeURIComponent(id)}`),
  estatisticasCiclo: (id, { comInsights = true } = {}) => {
    const qs = comInsights ? '' : '?com_insights=false';
    return get(`/ciclos/${encodeURIComponent(id)}/estatisticas${qs}`);
  },

  // Dimensões
  listarSedes: () => get('/sedes'),
  listarTurmas: () => get('/turmas'),

  // Upload de planilha → POST /uploads
  enviarPlanilha: (arquivo, { autor, onProgress, onUploaded } = {}) =>
    postArquivo('/uploads', arquivo, { autor }, { onProgress, onUploaded }),
  // Uploads mudam a cada importação e são consultados em polling — sem cache.
  listarUploads: () => get('/uploads', { cache: false }),
  obterUpload: (id) => get(`/uploads/${encodeURIComponent(id)}`, { cache: false }),

  // ─── Chat ─────────────────────────────────────────────────────────────
  // Threads e mensagens mudam em tempo real (envio/arquivamento) — sem cache.
  listarChatThreads: ({ incluirArquivadas = false } = {}) =>
    get(`/chat/threads${incluirArquivadas ? '?incluir_arquivadas=true' : ''}`, { cache: false }),
  criarChatThread: (titulo) => post('/chat/threads', { titulo: titulo || null }),
  obterChatThread: (id) => get(`/chat/threads/${encodeURIComponent(id)}`, { cache: false }),
  atualizarChatThread: (id, patch) => patchJson(`/chat/threads/${encodeURIComponent(id)}`, patch),
  apagarChatThread: (id) => del(`/chat/threads/${encodeURIComponent(id)}`),
  /**
   * Envia mensagem e streama eventos SSE.
   * @param {string} threadId
   * @param {string} conteudo
   * @param {(evento: {nome: string, dados: any}) => void} onEvento
   * @returns {Promise<void>} resolve quando o stream encerra
   */
  enviarChatMensagem: (threadId, conteudo, onEvento) =>
    streamSSE(`/chat/threads/${encodeURIComponent(threadId)}/mensagens`, { conteudo }, onEvento),

  limparCacheDados,
  baseUrl: () => BASE_URL,
};

// ─── helpers locais (PATCH, DELETE, SSE) ────────────────────────────────

async function patchJson(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  _onUnauthorized(res);
  if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`);
  return res.json();
}

async function del(path) {
  const res = await fetch(`${BASE_URL}${path}`, { method: 'DELETE', headers: _authHeaders() });
  _onUnauthorized(res);
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`);
  return res.json();
}

/** Streamer SSE — parser leve em cima do fetch + ReadableStream. */
async function streamSSE(path, body, onEvento) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  _onUnauthorized(res);
  if (!res.ok) {
    let detalhe = '';
    try { detalhe = (await res.json()).detail || ''; } catch {}
    throw new Error(`POST ${path} → ${res.status} ${detalhe}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // Cada evento SSE é separado por '\n\n'. Dentro: linhas 'event: nome' + 'data: {json}'.
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep;
    while ((sep = buffer.indexOf('\n\n')) >= 0) {
      const bloco = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const evento = parseEvento(bloco);
      if (evento) onEvento(evento);
    }
  }
  // Resto (sem \n\n final): tenta parsear caso seja último evento.
  if (buffer.trim()) {
    const evento = parseEvento(buffer);
    if (evento) onEvento(evento);
  }
}

function parseEvento(bloco) {
  let nome = 'message';
  const dataParts = [];
  for (const linha of bloco.split('\n')) {
    if (linha.startsWith('event:')) nome = linha.slice(6).trim();
    else if (linha.startsWith('data:')) dataParts.push(linha.slice(5).trim());
  }
  if (!dataParts.length) return null;
  let dados = null;
  try { dados = JSON.parse(dataParts.join('\n')); } catch {}
  return { nome, dados: dados ?? {} };
}
