import { describe, expect, it } from 'vitest';

import { recorteDaMira } from './mira';

/** A geometria real da tela: caixa 4/3 (`.cant-aovivo__camera`) e mira de 58%. */
function balcao(quadro: { largura: number; altura: number }, caixaLargura = 800) {
  const caixaAltura = (caixaLargura * 3) / 4;
  const ladoDaMira = caixaLargura * 0.58;
  return {
    quadro,
    video: { largura: caixaLargura, altura: caixaAltura },
    mira: {
      x: (caixaLargura - ladoDaMira) / 2,
      y: (caixaAltura - ladoDaMira) / 2,
      largura: ladoDaMira,
      altura: ladoDaMira,
    },
  };
}

const SEM_FOLGA = { folga: 0, ladoMaximo: 4096 };

describe('recorteDaMira', () => {
  it('traduz a mira de 58% da caixa 4/3 para o quadro 16/9 da câmera', () => {
    // `object-fit: cover` mostra só 75% da largura de um quadro 16/9 numa caixa
    // 4/3, então a mira de 58% da CAIXA vale 58% × 75% = 43,5% da largura do
    // QUADRO: 0,435 × 1280 ≈ 557 px, e não 58% de 1280.
    const r = recorteDaMira(balcao({ largura: 1280, altura: 720 }), SEM_FOLGA);
    expect(r).not.toBeNull();
    // A origem desce para o múltiplo de 8 anterior e o tamanho cobre a mira
    // inteira: [360, 919] × [80, 639] contém [361,6, 918,4] × [81,6, 638,4].
    expect(r!.origem).toEqual({ x: 360, y: 80, largura: 559, altura: 559 });
    expect(r!.destino).toEqual({ largura: 559, altura: 559 });
    expect(r!.daMira).toBe(true);
  });

  it('recorta menos de um terço dos pixels do quadro inteiro', () => {
    const r = recorteDaMira(balcao({ largura: 1280, altura: 720 }), { folga: 0.06, ladoMaximo: 4096 })!;
    const doRecorte = r.origem.largura * r.origem.altura;
    expect(doRecorte / (1280 * 720)).toBeLessThan(0.45);
  });

  it('a folga cresce o recorte dos dois lados, sem sair do quadro', () => {
    const semFolga = recorteDaMira(balcao({ largura: 1280, altura: 720 }), SEM_FOLGA)!;
    const comFolga = recorteDaMira(balcao({ largura: 1280, altura: 720 }), { folga: 0.06, ladoMaximo: 4096 })!;
    expect(comFolga.origem.x).toBeLessThan(semFolga.origem.x);
    expect(comFolga.origem.y).toBeLessThan(semFolga.origem.y);
    expect(comFolga.origem.largura).toBeGreaterThan(semFolga.origem.largura);
    expect(comFolga.origem.x + comFolga.origem.largura).toBeLessThanOrEqual(1280);
    expect(comFolga.origem.y + comFolga.origem.altura).toBeLessThanOrEqual(720);
  });

  it('a origem é sempre múltipla de 8 — é ela que fixa a fase do binarizador', () => {
    for (const folga of [0, 0.03, 0.06, 0.11, 0.2]) {
      for (const largura of [640, 1280, 1920, 1440]) {
        const r = recorteDaMira(balcao({ largura, altura: Math.round((largura * 9) / 16) }), {
          folga, ladoMaximo: 4096,
        })!;
        expect(r.origem.x % 8).toBe(0);
        expect(r.origem.y % 8).toBe(0);
      }
    }
  });

  it('o recorte contém a mira inteira, com folga ou sem ela', () => {
    for (const folga of [0, 0.06, 0.2]) {
      const medida = balcao({ largura: 1280, altura: 720 });
      const r = recorteDaMira(medida, { folga, ladoMaximo: 4096 })!;
      // A mira, nos mesmos pixels de quadro: caixa 4/3 sobre quadro 16/9.
      const escala = medida.video.altura / 720;
      const sobraX = (medida.video.largura - 1280 * escala) / 2;
      const miraX = (medida.mira.x - sobraX) / escala;
      const miraLargura = medida.mira.largura / escala;
      expect(r.origem.x).toBeLessThanOrEqual(miraX);
      expect(r.origem.x + r.origem.largura).toBeGreaterThanOrEqual(miraX + miraLargura);
    }
  });

  it('trata a caixa como `cover`, não como `contain`', () => {
    // Se lesse `contain`, a escala seria a MENOR e a mira cairia num pedaço do
    // quadro que a tela nem mostra. O sinal disso é a mira sair do centro.
    const r = recorteDaMira(balcao({ largura: 1280, altura: 720 }), SEM_FOLGA)!;
    const centroX = r.origem.x + r.origem.largura / 2;
    const centroY = r.origem.y + r.origem.altura / 2;
    expect(Math.abs(centroX - 640)).toBeLessThan(8);
    expect(Math.abs(centroY - 360)).toBeLessThan(8);
  });

  it('uma câmera 4/3 não sofre corte nenhum: a mira vale 58% da largura', () => {
    const r = recorteDaMira(balcao({ largura: 640, altura: 480 }), SEM_FOLGA)!;
    // A mira vai de 134,4 a 505,6; a origem desce para 128 e o recorte vai até
    // 506. Nada de corte lateral aqui: quadro e caixa têm a mesma proporção.
    expect(r.origem.x).toBe(128);
    expect(r.origem.largura).toBe(378);
  });

  it('o teto reduz o DESTINO e preserva a origem nativa', () => {
    const r = recorteDaMira(balcao({ largura: 3840, altura: 2160 }), { folga: 0, ladoMaximo: 768 })!;
    expect(r.origem.largura).toBeGreaterThan(1000);
    expect(Math.max(r.destino.largura, r.destino.altura)).toBe(768);
    // Proporção mantida: reduzir só num eixo entortaria o código.
    expect(r.destino.largura / r.destino.altura).toBeCloseTo(r.origem.largura / r.origem.altura, 2);
  });

  it('abaixo do teto não reduz nada — analisar em 1:1 é o ponto do recorte', () => {
    const r = recorteDaMira(balcao({ largura: 1280, altura: 720 }), { folga: 0.06, ladoMaximo: 768 })!;
    expect(r.destino).toEqual({ largura: r.origem.largura, altura: r.origem.altura });
  });

  it('sem mira montada, cai no maior quadrado centrado — e diz que caiu', () => {
    const r = recorteDaMira(
      { quadro: { largura: 1280, altura: 720 }, video: { largura: 800, altura: 600 }, mira: null },
      SEM_FOLGA,
    )!;
    expect(r.daMira).toBe(false);
    expect(r.origem).toEqual({ x: 280, y: 0, largura: 720, altura: 720 });
  });

  it('sem layout do vídeo também cai no recorte de segurança', () => {
    const r = recorteDaMira(
      {
        quadro: { largura: 1280, altura: 720 },
        video: { largura: 0, altura: 0 },
        mira: { x: 0, y: 0, largura: 100, altura: 100 },
      },
      SEM_FOLGA,
    )!;
    expect(r.daMira).toBe(false);
  });

  it('mira maior que o quadro é aparada, nunca lida fora da imagem', () => {
    const r = recorteDaMira(
      {
        quadro: { largura: 1280, altura: 720 },
        video: { largura: 800, altura: 600 },
        mira: { x: -400, y: -400, largura: 1600, altura: 1600 },
      },
      { folga: 0.5, ladoMaximo: 4096 },
    )!;
    expect(r.origem.x).toBe(0);
    expect(r.origem.y).toBe(0);
    expect(r.origem.largura).toBeLessThanOrEqual(1280);
    expect(r.origem.altura).toBeLessThanOrEqual(720);
  });

  it('sem quadro não há o que ler', () => {
    expect(recorteDaMira(balcao({ largura: 0, altura: 0 }), SEM_FOLGA)).toBeNull();
    expect(recorteDaMira(balcao({ largura: 1280, altura: 0 }), SEM_FOLGA)).toBeNull();
  });

  it('mira degenerada não vira recorte de um pixel', () => {
    const r = recorteDaMira(
      {
        quadro: { largura: 1280, altura: 720 },
        video: { largura: 800, altura: 600 },
        mira: { x: 400, y: 300, largura: 0, altura: 0 },
      },
      SEM_FOLGA,
    )!;
    expect(r.daMira).toBe(false);
    expect(r.origem.largura).toBe(720);
    expect(r.origem.x).toBe(280);
  });
});
