// Pinta uma `Folha` (o layout de `dominio/horarioEstudosFolha.ts`) num canvas 2D.
//
// É o ÚNICO desenhista: o PNG é este canvas, e o PDF é este canvas dentro de uma
// página (`pdf.ts`). Nada aqui decide posição, cor ou tamanho — quem decide é a
// `Folha`, e é por isso que ela se testa sem navegador.
//
// ⚠️ Canvas 2D direto, e não SVG → canvas como o gráfico da ficha do aluno
// (`exportacao/exportar-aluno.js`): um SVG rasterizado vira uma imagem isolada, que
// não enxerga as fontes carregadas pela página, e o texto sairia na fonte padrão do
// sistema. O `fillText` do canvas usa as fontes do documento — desde que elas já
// tenham carregado (`prepararFontes`). É o mesmo caminho de `imagemDoCardapio.ts`.

import type { Folha, Imagem, Medir, Peso, Retangulo, Texto } from '../dominio/horarioEstudosFolha';

export interface RecursosDaFolha {
  /** O glifo branco da marca (`ari-logo-branca.png`). Sem ela, a folha sai sem a logo. */
  logo: HTMLImageElement | null;
}

/** Os pesos que a folha usa — o que `prepararFontes` pede ao navegador. */
const PESOS: Peso[] = [500, 600, 700, 800];

/**
 * Espera as fontes do site carregarem, pesos incluídos.
 *
 * `document.fonts.ready` sozinho não basta: o navegador só baixa um peso quando algum
 * texto da PÁGINA o usa, e o canvas não conta. Pedir cada peso com `fonts.load` é o
 * que garante que o 800 do título e o 500 do rodapé existam antes do primeiro
 * `fillText` — sem isso o canvas cairia, em silêncio, numa fonte de sistema.
 */
export async function prepararFontes(familia: string): Promise<void> {
  await document.fonts.ready;
  await Promise.all(PESOS.map((p) => document.fonts.load(`${p} 12px ${familia}`).catch(() => [])));
}

/** A fonte do site, como o corpo da página a resolve (Plus Jakarta Sans). */
export function familiaDoSite(): string {
  return getComputedStyle(document.body).fontFamily || 'sans-serif';
}

/**
 * Mede texto pela fonte REAL, com o canvas.
 *
 * Mede a 10× e divide: o `measureText` de um corpo de 5,5px sofre com o arredondamento
 * da rasterização, e um rótulo que "cabe" a 5,5 pode sobrar 1pt na hora de desenhar.
 */
export function criarMedidor(familia: string): Medir {
  const ctx = document.createElement('canvas').getContext('2d');
  if (!ctx) throw new Error('Este navegador não gera imagem.');
  return (texto, tamanho, peso) => {
    ctx.font = `${peso} ${tamanho * 10}px ${familia}`;
    return ctx.measureText(texto).width / 10;
  };
}

export function carregarImagem(src: string): Promise<HTMLImageElement> {
  return new Promise((ok, falha) => {
    const img = new Image();
    img.onload = () => ok(img);
    img.onerror = () => falha(new Error('Não deu para carregar a marca do colégio.'));
    img.src = src;
  });
}

// ─── Desenho ─────────────────────────────────────────────────────────────

function caminhoArredondado(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, raio: number) {
  // `roundRect` só chegou ao Safari 16; o arco à mão roda em qualquer um.
  const r = Math.max(0, Math.min(raio, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function desenharRetangulo(ctx: CanvasRenderingContext2D, p: Retangulo) {
  if (p.raio) caminhoArredondado(ctx, p.x, p.y, p.largura, p.altura, p.raio);
  else {
    ctx.beginPath();
    ctx.rect(p.x, p.y, p.largura, p.altura);
  }
  if (p.preenchimento) {
    ctx.fillStyle = p.preenchimento;
    ctx.fill();
  }
  if (p.traco) {
    ctx.strokeStyle = p.traco.cor;
    ctx.lineWidth = p.traco.largura;
    ctx.stroke();
  }
}

function desenharTexto(ctx: CanvasRenderingContext2D, p: Texto, familia: string) {
  ctx.font = `${p.peso} ${p.tamanho}px ${familia}`;
  ctx.fillStyle = p.cor;
  ctx.textBaseline = 'alphabetic';
  ctx.textAlign = 'left';

  if (p.recorte) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(p.recorte.x, p.recorte.y, p.recorte.largura, p.recorte.altura);
    ctx.clip();
  }
  if (p.espacamento) {
    // `ctx.letterSpacing` só chegou ao Safari 18: letra por letra roda em qualquer um.
    // O kerning entre pares se perde, e em legenda de caixa-alta ninguém o vê.
    let x = p.x;
    for (const letra of p.texto) {
      ctx.fillText(letra, x, p.y);
      x += ctx.measureText(letra).width + p.espacamento;
    }
  } else {
    ctx.fillText(p.texto, p.x, p.y);
  }
  if (p.recorte) ctx.restore();
}

/**
 * A logo é um glifo BRANCO com transparência — o casco a pinta por máscara CSS, azul-
 * marinho no dia e branca na noite. Aqui o equivalente é `source-in`: desenha o glifo e
 * troca a cor de tudo o que é opaco, mantendo a transparência.
 */
function desenharLogo(ctx: CanvasRenderingContext2D, p: Imagem, logo: HTMLImageElement, escala: number) {
  const aparte = document.createElement('canvas');
  aparte.width = Math.max(1, Math.round(p.largura * escala));
  aparte.height = Math.max(1, Math.round(p.altura * escala));
  const c = aparte.getContext('2d');
  if (!c) return;
  c.drawImage(logo, 0, 0, aparte.width, aparte.height);
  c.globalCompositeOperation = 'source-in';
  c.fillStyle = p.cor;
  c.fillRect(0, 0, aparte.width, aparte.height);
  ctx.drawImage(aparte, p.x, p.y, p.largura, p.altura);
}

/**
 * Desenha a folha inteira. `escala` multiplica os pontos: 2 para o PNG (1684×1190 px) e
 * 3 para a imagem do PDF (2526×1785 px, A4 a ~250 dpi).
 */
export function desenharFolha(
  ctx: CanvasRenderingContext2D,
  folha: Folha,
  escala: number,
  familia: string,
  recursos: RecursosDaFolha,
): void {
  ctx.save();
  ctx.imageSmoothingQuality = 'high';
  ctx.scale(escala, escala);
  ctx.lineCap = 'butt';

  for (const p of folha.primitivas) {
    switch (p.tipo) {
      case 'retangulo':
        desenharRetangulo(ctx, p);
        break;
      case 'linha':
        ctx.beginPath();
        ctx.moveTo(p.x1, p.y1);
        ctx.lineTo(p.x2, p.y2);
        ctx.strokeStyle = p.cor;
        ctx.lineWidth = p.largura;
        ctx.stroke();
        break;
      case 'texto':
        desenharTexto(ctx, p, familia);
        break;
      case 'imagem':
        if (recursos.logo) desenharLogo(ctx, p, recursos.logo, escala);
        break;
    }
  }
  ctx.restore();
}
