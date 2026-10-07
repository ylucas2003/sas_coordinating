import { describe, expect, it } from 'vitest';
import { faixasOferecidas, rotuloDaSerie, rotuloEvidencia, serieEstimadaHoje } from './captacao';

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

describe('faixasOferecidas', () => {
  const provas = [
    { nome: 'OBMEP', categoria: 'olimpiada' },
    { nome: 'ITA', categoria: 'vestibular' },
  ];

  it('sem prova escolhida, oferece as dez', () => {
    expect(faixasOferecidas([], provas)).toHaveLength(10);
  });

  it('só olimpíada: não oferece "Aprovado", que não traria ninguém', () => {
    expect(faixasOferecidas(['OBMEP'], provas)).toEqual(['ouro', 'prata', 'bronze', 'mencao', 'finalista']);
  });

  it('olimpíada e vestibular juntos: as duas escadas', () => {
    expect(faixasOferecidas(['OBMEP', 'ITA'], provas)).toHaveLength(10);
  });

  it('categoria desconhecida libera tudo em vez de esconder filtro', () => {
    expect(faixasOferecidas(['X'], [{ nome: 'X', categoria: 'concurso_nivel_medio' }])).toHaveLength(10);
  });
});

describe('rotuloEvidencia', () => {
  it('faixa, prova e ano, e nível quando a fonte publica', () => {
    expect(
      rotuloEvidencia({ prova: 'OBMEP', ano: 2025, faixa: 'ouro', resultado: 'Ouro — rede pública', nivel: 'Nível 1' }),
    ).toBe('Ouro · OBMEP 2025 · Nível 1');
  });

  it('vestibular não tem nível', () => {
    expect(
      rotuloEvidencia({ prova: 'IME', ano: 2025, faixa: 'classificado_final', resultado: 'ATIVA — excedente', nivel: null }),
    ).toBe('Classificado sem vaga · IME 2025');
  });
});
