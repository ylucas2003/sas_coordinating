// Renderiza artefatos do chat: gráficos inline (histograma, linha temporal)
// e botão de download pra CSV.

import { el } from '../../dom.js';
import { histograma } from '../ui/histograma.js';
import { linhaTemporal } from '../ui/linha-temporal.js';

/**
 * @param {object} artefato {tipo, titulo, payload, urlExport}
 */
export function artefatoChat(artefato) {
  if (!artefato || !artefato.tipo) return null;

  const cabec = artefato.titulo
    ? el('div', { class: 'chat-artefato__titulo' }, [artefato.titulo])
    : null;

  if (artefato.tipo === 'histograma' && artefato.payload?.histograma) {
    return el('div', { class: 'chat-artefato chat-artefato--grafico' }, [
      cabec,
      histograma(artefato.payload.histograma, {
        width: 540,
        height: 200,
        media: artefato.payload.media,
        mediana: artefato.payload.mediana,
      }),
      el('div', { class: 'chat-artefato__rodape' }, [
        `n = ${artefato.payload.nPresentes ?? '?'} alunos`,
      ]),
    ]);
  }

  if (artefato.tipo === 'linha_temporal' && Array.isArray(artefato.payload?.pontos)) {
    const pontos = artefato.payload.pontos.map((p) => ({
      simuladoId: p.simuladoId,
      nome: p.rotulo || '',
      rotuloCurto: p.rotulo || '',
      data: p.data,
      media: p.nota,
      materia: p.materia ? { nome: p.materia } : null,
    }));
    return el('div', { class: 'chat-artefato chat-artefato--grafico' }, [
      cabec,
      linhaTemporal(pontos, {
        width: 620,
        height: 220,
        yMax: 10,
        onPontoClick: (p) => {
          if (p.simuladoId) {
            window.location.hash = `#/simulados/${encodeURIComponent(p.simuladoId)}`;
          }
        },
      }),
    ]);
  }

  if (artefato.tipo === 'csv' && artefato.payload?.conteudo) {
    const nLinhas = artefato.payload.nLinhas ?? 0;
    const tituloSeguro = (artefato.titulo || 'export').replace(/[^a-zA-Z0-9_-]/g, '_');
    return el('div', { class: 'chat-artefato chat-artefato--csv' }, [
      cabec,
      el('div', { class: 'chat-artefato__csv-info' }, [`${nLinhas} linha(s) · CSV`]),
      el('button', {
        class: 'chat-artefato__csv-baixar',
        onclick: () => _baixarCsv(artefato.payload.conteudo, `${tituloSeguro}.csv`),
      }, ['↓ Baixar CSV']),
    ]);
  }

  return el('div', { class: 'chat-artefato chat-artefato--erro' }, [
    `Artefato não renderizável (tipo=${artefato.tipo}).`,
  ]);
}

function _baixarCsv(conteudo, nomeArquivo) {
  // Acrescenta BOM pra Excel ler acentos.
  const blob = new Blob(['﻿' + conteudo], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 500);
}
