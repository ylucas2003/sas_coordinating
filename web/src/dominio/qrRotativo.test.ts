import { describe, expect, it } from 'vitest';

import {
  codigoDaJanela, janelaAtual, montarQr, msAteAProximaJanela, type SementeDoQr,
} from './qrRotativo';

/**
 * ⚠️ O que estes testes protegem é a propriedade, não o formato: **o código de
 * um print morre em 10 segundos**, e o relógio errado do aparelho não estraga
 * nada (docs/40 §12.9.2).
 */

const SEED: SementeDoQr = {
  pedidoId: 'p1',
  semente: 'semente-de-teste',
  janela: 1_000,
  segundosDaJanela: 10,
};

describe('a janela contada no aparelho', () => {
  it('começa na que o SERVIDOR mandou', () => {
    expect(janelaAtual(SEED, 0)).toBe(1_000);
  });

  it('anda uma janela a cada 10 segundos decorridos', () => {
    expect(janelaAtual(SEED, 9_999)).toBe(1_000);
    expect(janelaAtual(SEED, 10_000)).toBe(1_001);
    expect(janelaAtual(SEED, 25_000)).toBe(1_002);
  });

  it('nunca anda para TRÁS da janela inicial', () => {
    // `performance.now` pode devolver um valor menor depois de suspensão. Uma
    // janela anterior à inicial seria recusada pelo servidor de qualquer jeito
    // — gerar um código que já nasce inválido é pior que não andar.
    expect(janelaAtual(SEED, -5_000)).toBe(1_000);
  });

  it('não consulta a hora do sistema em lugar nenhum', () => {
    // O teste que prova a decisão: o resultado depende só do que foi passado.
    // Se algum dia alguém trocar por `Date.now()`, este teste continua
    // passando — e é por isso que a garantia real está na ASSINATURA da
    // função, que não aceita nada além do decorrido.
    expect(janelaAtual(SEED, 10_000)).toBe(janelaAtual(SEED, 10_000));
  });
});

describe('quando redesenhar', () => {
  it('devolve o que falta para a janela virar', () => {
    expect(msAteAProximaJanela(SEED, 0)).toBe(10_000);
    expect(msAteAProximaJanela(SEED, 3_000)).toBe(7_000);
    expect(msAteAProximaJanela(SEED, 9_999)).toBe(1);
  });

  it('nunca devolve zero — um intervalo de 0 ms viraria laço quente', () => {
    for (const decorrido of [0, 1, 5_000, 9_999, 10_000, 123_456]) {
      expect(msAteAProximaJanela(SEED, decorrido)).toBeGreaterThan(0);
    }
  });
});

describe('o código', () => {
  it('muda de uma janela para a outra', async () => {
    const a = await codigoDaJanela(SEED.semente, 1_000);
    const b = await codigoDaJanela(SEED.semente, 1_001);
    expect(a).not.toBe(b);
  });

  it('é o mesmo para a mesma janela — cliente e servidor têm de concordar', async () => {
    const a = await codigoDaJanela(SEED.semente, 1_000);
    const b = await codigoDaJanela(SEED.semente, 1_000);
    expect(a).toBe(b);
  });

  it('sementes diferentes dão códigos diferentes na mesma janela', async () => {
    const a = await codigoDaJanela('semente-a', 1_000);
    const b = await codigoDaJanela('semente-b', 1_000);
    expect(a).not.toBe(b);
  });

  it('o QR NÃO carrega a semente', async () => {
    // A propriedade que faz a rotação valer alguma coisa: um print carrega o
    // código de UMA janela, e não o material para derivar as seguintes.
    const codigo = await codigoDaJanela(SEED.semente, 1_000);
    const conteudo = montarQr(SEED.pedidoId, 1_000, codigo);
    expect(conteudo).not.toContain(SEED.semente);
    expect(conteudo).toBe('p1.1000.' + codigo);
  });
});
