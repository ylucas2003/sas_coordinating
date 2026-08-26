import { describe, expect, it } from 'vitest';
import { calcularExibicao, clampOffset, retanguloDeRecorte } from './fotoPerfil';

describe('calcularExibicao', () => {
  it('cobre o viewport pela dimensão que sobra menos (retrato)', () => {
    // 100×200 num viewport 240×240: a largura precisa esticar mais (2.4x) que
    // a altura (1.2x) para não sobrar fundo vazio nas laterais.
    expect(calcularExibicao({ w: 100, h: 200 }, 1, 240)).toEqual({ largura: 240, altura: 480 });
  });

  it('cobre o viewport pela dimensão que sobra menos (paisagem)', () => {
    expect(calcularExibicao({ w: 200, h: 100 }, 1, 240)).toEqual({ largura: 480, altura: 240 });
  });

  it('zoom escala linearmente a partir do cover', () => {
    expect(calcularExibicao({ w: 240, h: 240 }, 1, 240)).toEqual({ largura: 240, altura: 240 });
    expect(calcularExibicao({ w: 240, h: 240 }, 2, 240)).toEqual({ largura: 480, altura: 480 });
  });
});

describe('clampOffset', () => {
  it('imagem quadrada do tamanho do viewport não pode se mover (zoom 1)', () => {
    // Em zoom 1 o cover já preenche exatamente — qualquer arrasto revelaria
    // fundo vazio, então o limite é zero nos dois eixos.
    expect(clampOffset({ x: 50, y: -30 }, { w: 240, h: 240 }, 1, 240)).toEqual({ x: 0, y: 0 });
  });

  it('deixa passar um arrasto dentro do excedente do zoom', () => {
    // zoom 2 numa imagem 240×240 exibe 480×480 — 240px de sobra, 120 de cada lado.
    expect(clampOffset({ x: 50, y: -50 }, { w: 240, h: 240 }, 2, 240)).toEqual({ x: 50, y: -50 });
  });

  it('prende no limite quando o arrasto passa do excedente', () => {
    expect(clampOffset({ x: 200, y: -200 }, { w: 240, h: 240 }, 2, 240)).toEqual({ x: 120, y: -120 });
  });
});

describe('retanguloDeRecorte', () => {
  it('sem arrasto, a imagem quadrada preenche o canvas de saída inteiro', () => {
    const r = retanguloDeRecorte({ w: 240, h: 240 }, 1, { x: 0, y: 0 }, 240, 512);
    expect(r.x).toBeCloseTo(0);
    expect(r.y).toBeCloseTo(0);
    expect(r.largura).toBeCloseTo(512);
    expect(r.altura).toBeCloseTo(512);
  });

  it('o arrasto do viewport escala para o tamanho de saída', () => {
    // offset em px de viewport (240) precisa virar px de saída (512) —
    // multiplicado pela mesma razão 512/240 que escala a imagem inteira.
    const r = retanguloDeRecorte({ w: 240, h: 240 }, 1, { x: 50, y: -20 }, 240, 512);
    const escala = 512 / 240;
    expect(r.x).toBeCloseTo(50 * escala);
    expect(r.y).toBeCloseTo(-20 * escala);
  });
});
