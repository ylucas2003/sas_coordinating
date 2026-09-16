import { describe, expect, it } from 'vitest';
import { rotuloDaSerie, serieEstimadaHoje } from './captacao';

describe('serieEstimadaHoje', () => {
  it('desloca a faixa pelos anos decorridos desde a referência', () => {
    // Nível 2 da OBMEP em 2024 (8º-9º) — dois anos depois já seria 10º-11º.
    const faixa = serieEstimadaHoje(
      { serie_referencia_min: 8, serie_referencia_max: 9, ano_referencia_serie: 2024 },
      2026,
    );
    expect(faixa).toEqual({ min: 10, max: 11 });
  });

  it('sem referência completa, não estima nada', () => {
    expect(
      serieEstimadaHoje({ serie_referencia_min: null, serie_referencia_max: null, ano_referencia_serie: null }, 2026),
    ).toBeNull();
  });
});

describe('rotuloDaSerie', () => {
  it('faixa de um nível vira intervalo por extenso', () => {
    expect(rotuloDaSerie({ min: 8, max: 9 })).toBe('8º ano – 9º ano');
  });

  it('série única não repete o mesmo rótulo duas vezes', () => {
    expect(rotuloDaSerie({ min: 10, max: 10 })).toBe('1º médio');
  });

  it('passou do 3º médio: lead frio, não uma série inventada', () => {
    expect(rotuloDaSerie({ min: 13, max: 14 })).toBe('já deve ter saído da educação básica');
  });

  it('sem faixa, sem rótulo', () => {
    expect(rotuloDaSerie(null)).toBeNull();
  });
});
