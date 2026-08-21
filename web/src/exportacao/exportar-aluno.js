// Exportação do histórico do aluno em PNG / CSV / PDF.

import { fmtDataBR, rotuloCiclo } from '../components/tabela-simulados.js';

const TIPO_LABEL = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

function nomeArquivo(aluno, ext) {
  const slug = (aluno.nome || aluno.id || 'aluno')
    .toString()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
    .slice(0, 60);
  const hoje = new Date().toISOString().slice(0, 10);
  return `${slug || 'aluno'}-${hoje}.${ext}`;
}

function dispararDownload(blob, nome) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ─── PNG ────────────────────────────────────────────────────────────────
// Serializa o SVG do gráfico e rasteriza num canvas.
export function exportarPNGGrafico(svgElement, aluno) {
  if (!svgElement) return;

  // Clona o SVG e injeta as variáveis CSS resolvidas como valores absolutos —
  // o SVG fora do DOM não herda o computed style.
  const clone = svgElement.cloneNode(true);
  const computado = getComputedStyle(svgElement);
  clone.style.fontFamily = computado.fontFamily;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');

  // Resolve variáveis CSS comuns substituindo pelo valor real.
  const variaveisResolvidas = {
    'var(--color-border)': computado.getPropertyValue('--color-border') || '#e0e3eb',
    'var(--color-text-tertiary)': '#73757d',
    'var(--color-text-secondary)': '#5a5d65',
    'var(--color-navy)': '#1b3f8b',
    'var(--color-red, #c44)': '#d9354a',
  };
  let svgStr = new XMLSerializer().serializeToString(clone);
  for (const [from, to] of Object.entries(variaveisResolvidas)) {
    svgStr = svgStr.split(from).join(to);
  }

  const viewBox = svgElement.getAttribute('viewBox') || '0 0 760 320';
  const [, , vbW, vbH] = viewBox.split(/\s+/).map(Number);
  const escala = 2; // 2x pra qualidade retina
  const canvas = document.createElement('canvas');
  canvas.width = vbW * escala;
  canvas.height = vbH * escala;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const img = new Image();
  const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);

  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => {
      if (blob) dispararDownload(blob, nomeArquivo(aluno, 'png'));
    }, 'image/png');
  };
  img.onerror = (e) => {
    console.error('Falha ao renderizar PNG do gráfico:', e);
    URL.revokeObjectURL(url);
  };
  img.src = url;
}

// ─── CSV ────────────────────────────────────────────────────────────────
function escaparCSV(valor) {
  if (valor == null) return '';
  const s = String(valor);
  if (/[",;\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function exportarCSVHistorico(simulados, notasAluno, aluno) {
  const colunas = [
    'simulado', 'materia', 'fase', 'vestibular', 'ciclo',
    'data_aplicacao', 'sua_nota', 'media_turma', 'delta',
    'mediana_turma', 'desvio_padrao', 'n_presentes',
  ];

  const linhas = [colunas.join(';')];
  for (const s of simulados) {
    const nota = notasAluno.get(s.id);
    const delta = nota != null && s.media != null ? (nota - s.media).toFixed(2) : '';
    const linha = [
      s.rotuloCurto || s.nome || '',
      s.materia?.nome || '',
      TIPO_LABEL[s.tipo] || '',
      s.vestibularAlvo || '',
      rotuloCiclo(s.cicloOrdem, s.vestibularAlvo),
      s.dataAplicacao || '',
      nota != null ? nota.toFixed(2) : '',
      s.media != null ? s.media.toFixed(2) : '',
      delta,
      s.mediana != null ? s.mediana.toFixed(2) : '',
      s.desvioPadrao != null ? s.desvioPadrao.toFixed(2) : '',
      s.nPresentes != null ? s.nPresentes : '',
    ].map(escaparCSV).join(';');
    linhas.push(linha);
  }

  // BOM pra Excel reconhecer UTF-8.
  const blob = new Blob(['﻿' + linhas.join('\n')], { type: 'text/csv;charset=utf-8' });
  dispararDownload(blob, nomeArquivo(aluno, 'csv'));
}

// ─── PDF da ficha completa (modo print) ─────────────────────────────────
// Imprime a ficha inteira do aluno. CSS @media print esconde sidebar/topbar.
export function exportarPDFFicha() {
  window.print();
}


// ─── Panorama: PDF rico (impressão dedicada) ─────────────────────────────
// Insere o nó do panorama no body, marca o body com a classe `imprimindo-panorama`
// (o CSS de print esconde tudo exceto `.panorama`), dispara o print, depois
// remove. Não usa janela nova — funciona até em popup-blocker.
import { montarPanorama } from './panorama-aluno.js';

export function exportarPanoramaPDF(dados) {
  const panorama = montarPanorama(dados);
  document.body.appendChild(panorama);
  document.body.classList.add('imprimindo-panorama');

  // Espera 2 ticks pro layout aplicar antes do print.
  setTimeout(() => {
    const limpar = () => {
      document.body.classList.remove('imprimindo-panorama');
      panorama.remove();
      window.removeEventListener('afterprint', limpar);
    };
    window.addEventListener('afterprint', limpar);
    window.print();
  }, 100);
}


// ─── Panorama: PNG (snapshot do panorama renderizado fora da tela) ───────
// Renderiza o nó do panorama dentro de um foreignObject SVG, serializa,
// e rasteriza num canvas. Imagens e cores básicas funcionam; fontes
// dependem do sistema. Suficiente pra um "snapshot pra compartilhar".
export async function exportarPanoramaPNG(dados) {
  const panorama = montarPanorama(dados);
  // Render off-screen pra medir as dimensões reais.
  panorama.style.cssText = `
    position: fixed; top: -10000px; left: 0;
    width: 900px; background: white; padding: 32px;
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    color: #1a1d24;
  `;
  document.body.appendChild(panorama);

  // Aguarda layout.
  await new Promise((r) => requestAnimationFrame(r));
  const altura = panorama.offsetHeight;
  const largura = panorama.offsetWidth;

  // Injeta estilos críticos inline antes de serializar (já que o SVG não
  // tem acesso ao stylesheet externo).
  _embarcarEstilosPanorama(panorama);

  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('xmlns', svgNS);
  svg.setAttribute('width', String(largura));
  svg.setAttribute('height', String(altura));

  const fo = document.createElementNS(svgNS, 'foreignObject');
  fo.setAttribute('x', '0');
  fo.setAttribute('y', '0');
  fo.setAttribute('width', String(largura));
  fo.setAttribute('height', String(altura));

  // O conteúdo dentro de foreignObject precisa ter um xmlns explícito.
  panorama.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
  fo.appendChild(panorama.cloneNode(true));
  svg.appendChild(fo);

  const svgStr = new XMLSerializer().serializeToString(svg);
  const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);

  try {
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
      img.src = url;
    });

    const canvas = document.createElement('canvas');
    canvas.width = largura * 2;   // 2x pra retina
    canvas.height = altura * 2;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(2, 2);
    ctx.drawImage(img, 0, 0);

    await new Promise((resolve) => {
      canvas.toBlob((blob) => {
        if (blob) dispararDownload(blob, nomeArquivo(dados.aluno, 'png'));
        resolve();
      }, 'image/png');
    });
  } finally {
    URL.revokeObjectURL(url);
    panorama.remove();
  }
}


// Injeta inline as variáveis CSS / cores básicas pra o foreignObject
// renderizar parecido com o que aparece na tela.
function _embarcarEstilosPanorama(no) {
  const cores = {
    '--color-text-primary': '#1a1d24',
    '--color-text-secondary': 'rgba(26, 29, 36, 0.65)',
    '--color-text-tertiary': 'rgba(26, 29, 36, 0.45)',
    '--color-navy': '#1b3f8b',
    '--color-bg': '#eef1f7',
    '--color-surface-inset': '#f5f7fb',
    '--color-border': 'rgba(20, 30, 80, 0.06)',
    '--color-border-strong': 'rgba(20, 30, 80, 0.12)',
    '--color-red': '#d9354a',
    '--color-green': '#2e8c5a',
    '--color-amber': '#e89b2a',
  };
  const style = Object.entries(cores).map(([k, v]) => `${k}:${v}`).join(';');
  no.setAttribute('style', `${no.getAttribute('style') || ''};${style}`);
}
