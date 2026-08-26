// Matemática do recorte de foto de perfil (docs/sprints.html · SPRINT FOTO).
// Puro de propósito: nenhuma das três funções toca canvas, File nem DOM —
// é o que faz o editor (componentes/perfil/LembreteFotoPerfil.tsx) delegar
// aqui em vez de reimplementar a conta cada vez que zoom ou arrasto mudam.
//
// O modelo é "cover, como object-fit": em zoom 1 a foto cobre o viewport
// inteiro sem sobrar borda vazia, e o zoom só amplia a partir daí — nunca
// existe estado em que o círculo mostra fundo em vez de foto.

export interface Dimensoes {
  w: number;
  h: number;
}

export interface Offset {
  x: number;
  y: number;
}

/** Tamanho de exibição da imagem dentro de um viewport quadrado de `unidade`
 * px, no modo cover, no zoom dado. */
export function calcularExibicao(
  dim: Dimensoes, zoom: number, unidade: number
): { largura: number; altura: number } {
  const baseScale = Math.max(unidade / dim.w, unidade / dim.h);
  return { largura: dim.w * baseScale * zoom, altura: dim.h * baseScale * zoom };
}

/** Prende o arrasto para a imagem nunca descolar do viewport — o excedente
 * de cada lado é `(tamanho exibido − viewport) / 2`, nunca negativo. */
export function clampOffset(offset: Offset, dim: Dimensoes, zoom: number, viewport: number): Offset {
  const { largura, altura } = calcularExibicao(dim, zoom, viewport);
  const maxX = Math.max(0, (largura - viewport) / 2);
  const maxY = Math.max(0, (altura - viewport) / 2);
  return {
    // `|| 0` normaliza o -0 que `Math.max(-0, ...)` produz quando maxX/maxY
    // é 0 (imagem sem excedente) — mesmo valor pro CSS/canvas, mas -0 !== 0
    // para `Object.is` (e para `toEqual` do teste ao lado).
    x: Math.min(maxX, Math.max(-maxX, offset.x)) || 0,
    y: Math.min(maxY, Math.max(-maxY, offset.y)) || 0,
  };
}

/**
 * Onde e em que tamanho desenhar a imagem original num canvas de saída
 * `saida`×`saida`, para reproduzir exatamente o que o viewport (tamanho
 * `viewport`) mostrava — mesmo zoom, mesmo arrasto, escalados para a
 * resolução final.
 */
export function retanguloDeRecorte(
  dim: Dimensoes, zoom: number, offset: Offset, viewport: number, saida: number
): { x: number; y: number; largura: number; altura: number } {
  const escala = saida / viewport;
  const { largura, altura } = calcularExibicao(dim, zoom, saida);
  return {
    x: saida / 2 + offset.x * escala - largura / 2,
    y: saida / 2 + offset.y * escala - altura / 2,
    largura,
    altura,
  };
}
