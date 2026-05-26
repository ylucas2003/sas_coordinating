// Renderiza uma mensagem da conversa.
// Papéis 'system' e 'tool' ficam ocultos no MVP — só user e assistant aparecem.
// Mensagens do assistant podem ter:
//   - tool_calls (renderizamos como traces)
//   - artefatos (gráficos/CSVs)
//   - conteudo (texto em markdown leve)

import { el } from '../../dom.js';
import { artefatoChat } from './artefato.js';
import { toolTrace } from './tool-trace.js';

export function mensagemBolha(msg) {
  if (msg.papel === 'user') {
    return el('div', { class: 'chat-msg chat-msg--user' }, [
      el('div', { class: 'chat-msg__corpo' }, [msg.conteudo || '']),
    ]);
  }
  if (msg.papel === 'assistant') {
    const tcs = Array.isArray(msg.toolCalls) ? msg.toolCalls : [];
    const filhos = [];
    for (const tc of tcs) {
      filhos.push(toolTrace({
        nome: tc.name || tc.nome,
        args: tc.arguments || tc.args || {},
        resumo: null,
        finalizada: true,
      }));
    }
    if (msg.conteudo) {
      filhos.push(el('div', { class: 'chat-msg__corpo' }, _renderMarkdown(msg.conteudo)));
    }
    for (const art of (msg.artefatos || [])) {
      const elArt = artefatoChat(art);
      if (elArt) filhos.push(elArt);
    }
    if (filhos.length === 0) return null;
    return el('div', { class: 'chat-msg chat-msg--assistant' }, filhos);
  }
  // 'tool' / 'system' não renderizam (ficam no histórico mas o user não vê).
  return null;
}

// ── Markdown leve: negrito, listas, parágrafos. Sem links/imagens/HTML. ──

const RE_NEGRITO = /\*\*([^*]+)\*\*/g;
const RE_ITALICO = /\*([^*]+)\*/g;

function _renderMarkdown(texto) {
  const linhas = texto.split('\n');
  const filhos = [];
  let bufferLista = null;

  const fecharLista = () => {
    if (bufferLista) {
      filhos.push(el('ul', { class: 'chat-md-list' }, bufferLista));
      bufferLista = null;
    }
  };

  for (const linha of linhas) {
    const trim = linha.trim();
    if (!trim) { fecharLista(); continue; }
    const itemMatch = trim.match(/^[-•]\s+(.*)$/);
    if (itemMatch) {
      if (!bufferLista) bufferLista = [];
      bufferLista.push(el('li', {}, _inline(itemMatch[1])));
    } else {
      fecharLista();
      filhos.push(el('p', { class: 'chat-md-p' }, _inline(trim)));
    }
  }
  fecharLista();
  return filhos;
}

function _inline(texto) {
  // Tokeniza muito simples: separa por **bold** e *itálico* e devolve nodes.
  // Markdown completo sai do escopo do MVP.
  const nodes = [];
  let resto = texto;

  while (resto.length > 0) {
    const mB = resto.match(RE_NEGRITO);
    const mI = resto.match(RE_ITALICO);
    const idxB = mB ? resto.indexOf(mB[0]) : -1;
    const idxI = mI ? resto.indexOf(mI[0]) : -1;

    let usa = null;
    if (idxB >= 0 && (idxI < 0 || idxB <= idxI)) usa = { tipo: 'b', match: mB[0], idx: idxB };
    else if (idxI >= 0) usa = { tipo: 'i', match: mI[0], idx: idxI };

    if (!usa) { nodes.push(resto); break; }
    if (usa.idx > 0) nodes.push(resto.slice(0, usa.idx));
    const conteudo = usa.match.replace(/^\*+|\*+$/g, '');
    nodes.push(el(usa.tipo === 'b' ? 'strong' : 'em', {}, [conteudo]));
    resto = resto.slice(usa.idx + usa.match.length);
  }
  return nodes;
}
