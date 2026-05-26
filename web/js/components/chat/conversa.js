// Área de conversa — mensagens persistidas + composer de input + handling
// de streaming SSE pra resposta do agente.

import { clear, el } from '../../dom.js';
import { getApiClient } from '../../services/api.js';
import { artefatoChat } from './artefato.js';
import { mensagemBolha } from './mensagem.js';
import { toolTrace } from './tool-trace.js';

const SUGESTOES_INICIAIS = [
  'Quais alunos estão em risco no momento?',
  'Compare o ciclo mais recente com o anterior',
  'Em quais matérias devo focar agora?',
  'Mostre a evolução do aluno X',
];

export function conversaPanel({ thread, onTituloAtualizado }) {
  const root = el('section', { class: 'chat-conversa' }, []);
  const lista = el('div', { class: 'chat-conversa__lista' }, []);
  const composer = _renderComposer({
    onEnviar: (texto) => _enviar(texto),
    enviando: false,
  });

  root.appendChild(lista);
  root.appendChild(composer.elemento);

  // Estado local
  let enviando = false;
  let bolhaAssistantAtiva = null;     // div da resposta em andamento
  let textoEmStream = '';              // acumulado dos tokens
  let textoEl = null;
  let tracesAtivas = new Map();        // tool_call_id → elemento da trace

  _renderHistorico();

  if (thread.mensagens.length === 0) {
    _renderSugestoes();
  }

  function _renderHistorico() {
    clear(lista);
    for (const m of thread.mensagens) {
      const bol = mensagemBolha(m);
      if (bol) lista.appendChild(bol);
    }
    _scrollFim();
  }

  function _renderSugestoes() {
    lista.appendChild(el('div', { class: 'chat-sugestoes' }, [
      el('div', { class: 'chat-sugestoes__titulo' }, ['Algumas perguntas pra começar:']),
      el('div', { class: 'chat-sugestoes__lista' }, SUGESTOES_INICIAIS.map((s) =>
        el('button', {
          class: 'chat-sugestao',
          onclick: () => composer.preencherEEnviar(s),
        }, [s]),
      )),
    ]));
  }

  function _scrollFim() {
    // Pequeno timeout pra após o reflow.
    setTimeout(() => {
      lista.scrollTop = lista.scrollHeight;
    }, 10);
  }

  async function _enviar(texto) {
    if (enviando || !texto.trim()) return;
    enviando = true;
    composer.setEnviando(true);

    // Limpa sugestões iniciais se existirem.
    const sug = lista.querySelector('.chat-sugestoes');
    if (sug) sug.remove();

    // 1. Adiciona mensagem do usuário.
    const msgUser = mensagemBolha({ papel: 'user', conteudo: texto });
    lista.appendChild(msgUser);
    _scrollFim();

    // 2. Cria bolha de resposta em andamento (vazia, será preenchida pelo stream).
    bolhaAssistantAtiva = el('div', { class: 'chat-msg chat-msg--assistant chat-msg--streaming' }, []);
    lista.appendChild(bolhaAssistantAtiva);
    _scrollFim();

    textoEmStream = '';
    textoEl = null;
    tracesAtivas = new Map();
    const api = getApiClient();

    try {
      await api.enviarChatMensagem(thread.id, texto, (evt) => _onEvento(evt));
    } catch (e) {
      bolhaAssistantAtiva.appendChild(el('div', {
        class: 'chat-msg__erro',
      }, [`Erro: ${e.message || e}`]));
    } finally {
      bolhaAssistantAtiva?.classList.remove('chat-msg--streaming');
      enviando = false;
      composer.setEnviando(false);
      composer.focar();
    }
  }

  function _onEvento(evt) {
    const { nome, dados } = evt;
    if (nome === 'start') return;
    if (nome === 'user_salvo') return;

    if (nome === 'tool_call_start') {
      const tEl = toolTrace({
        nome: dados.nome,
        args: dados.args,
        resumo: null,
        finalizada: false,
      });
      tracesAtivas.set(dados.tool_call_id, tEl);
      bolhaAssistantAtiva.appendChild(tEl);
      _scrollFim();
      return;
    }
    if (nome === 'tool_call_end') {
      const antigo = tracesAtivas.get(dados.tool_call_id);
      if (antigo) {
        // Substitui pelo novo (com resumo + finalizada).
        const novo = toolTrace({
          nome: antigo._nomeTool || _inferirNome(antigo),
          args: antigo._args || {},
          resumo: dados.resumido,
          finalizada: true,
        });
        antigo.replaceWith(novo);
        tracesAtivas.set(dados.tool_call_id, novo);
      }
      return;
    }
    if (nome === 'token') {
      textoEmStream += dados.texto || '';
      if (!textoEl) {
        textoEl = el('div', { class: 'chat-msg__corpo chat-msg__corpo--stream' }, [textoEmStream]);
        bolhaAssistantAtiva.appendChild(textoEl);
      } else {
        textoEl.textContent = textoEmStream;
      }
      _scrollFim();
      return;
    }
    if (nome === 'erro') {
      bolhaAssistantAtiva.appendChild(el('div', {
        class: 'chat-msg__erro',
      }, [`⚠️ ${dados.mensagem || 'erro desconhecido'}`]));
      return;
    }
    if (nome === 'titulo') {
      if (onTituloAtualizado) onTituloAtualizado(dados.titulo);
      return;
    }
    if (nome === 'end') {
      // Recarrega o texto final como markdown bonito (substituindo o stream cru)
      // E busca os artefatos (gráficos/CSVs) gerados.
      _finalizarBolha(dados);
      return;
    }
  }

  function _finalizarBolha(dadosEnd) {
    if (!bolhaAssistantAtiva) return;
    // Re-renderiza o texto final com markdown e adiciona artefatos.
    const tcs = dadosEnd.tool_calls || [];
    // Remove o textoEl cru (markdown processado vai entrar).
    if (textoEl) {
      textoEl.remove();
      textoEl = null;
    }
    // Cria msg "fake" pra reaproveitar mensagemBolha — mas insere o conteúdo
    // dentro da bolha já existente (sem duplicar o cabeçalho).
    const final = mensagemBolha({
      papel: 'assistant',
      conteudo: dadosEnd.texto_final,
      // Tool calls já estão renderizadas como traces, não duplica.
      toolCalls: [],
      artefatos: _extrairArtefatosDoLoop(tcs),
    });
    if (final) {
      // Move filhos do "final" pra dentro da bolha ativa.
      while (final.firstChild) bolhaAssistantAtiva.appendChild(final.firstChild);
    }
    _scrollFim();
  }

  function _extrairArtefatosDoLoop(tool_calls) {
    const arts = [];
    for (const tc of tool_calls || []) {
      const r = tc.resultado;
      if (!r || r.erro) continue;
      if (tc.nome === 'gerar_grafico' && (r.tipo === 'histograma' || r.tipo === 'linha_temporal')) {
        arts.push({
          tipo: r.tipo,
          titulo: r.titulo,
          payload: r.payload,
        });
      }
      if (tc.nome === 'exportar_csv' && r.tipo === 'csv') {
        arts.push({
          tipo: 'csv',
          titulo: r.titulo,
          payload: { conteudo: r.conteudo, nLinhas: r.nLinhas },
        });
      }
    }
    return arts;
  }

  function _inferirNome(elTrace) {
    // Fallback: extrai do texto do elemento (não ideal, mas mantém UI consistente).
    return elTrace.querySelector('.chat-trace__nome')?.textContent || '';
  }

  return root;
}

function _renderComposer({ onEnviar }) {
  const textarea = el('textarea', {
    class: 'chat-composer__input',
    placeholder: 'Pergunte algo ao assistente...',
    rows: '2',
  });

  const btnEnviar = el('button', {
    class: 'chat-composer__enviar',
    onclick: () => _disparar(),
  }, ['Enviar']);

  function _disparar() {
    const t = textarea.value;
    if (!t.trim()) return;
    textarea.value = '';
    textarea.style.height = '';
    onEnviar(t);
  }

  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      _disparar();
    }
  });
  textarea.addEventListener('input', () => {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  });

  const elemento = el('div', { class: 'chat-composer' }, [textarea, btnEnviar]);

  return {
    elemento,
    setEnviando: (v) => {
      btnEnviar.disabled = v;
      btnEnviar.textContent = v ? 'Enviando...' : 'Enviar';
      textarea.disabled = v;
    },
    preencherEEnviar: (t) => {
      textarea.value = t;
      _disparar();
    },
    focar: () => textarea.focus(),
  };
}
