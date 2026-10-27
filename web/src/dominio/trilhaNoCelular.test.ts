import { describe, expect, it } from 'vitest';

import { DEGRAUS_NO_CELULAR, degrauSomeNoCelular } from './trilhaNoCelular';

/** O que a topbar mostra no celular, na ordem da trilha. */
function noCelular(trilha: string[]): string[] {
  return trilha.filter((_, i) => !degrauSomeNoCelular(i, trilha.length));
}

describe('degrauSomeNoCelular', () => {
  it('trilha de um ou dois degraus fica inteira', () => {
    expect(noCelular(['Painel'])).toEqual(['Painel']);
    expect(noCelular(['Administração', 'Conexões de IA'])).toEqual([
      'Administração',
      'Conexões de IA',
    ]);
  });

  it('a de três perde só o primeiro: fica de onde se veio e onde se está', () => {
    // O defeito que a verificação no browser de 26/10 achou: em 390px os dois
    // primeiros degraus enchiam a nav e o atual nascia fora dela. Achado em
    // `/conectar-ia`, que saiu do casco no mesmo dia; valia para toda trilha
    // de três degraus, como a da sincronização de aulas.
    expect(noCelular(['Administração', 'Integrações', 'Sincronização'])).toEqual([
      'Integrações',
      'Sincronização',
    ]);
    expect(noCelular(['Provas', 'Ciclos', 'ITA 2026 · Ciclo 3'])).toEqual([
      'Ciclos',
      'ITA 2026 · Ciclo 3',
    ]);
  });

  it('a de quatro, o dia da cantina, perde os dois primeiros', () => {
    expect(noCelular(['Administração', 'Cantina', 'Cardápios', '9 de setembro'])).toEqual([
      'Cardápios',
      '9 de setembro',
    ]);
  });

  it('o atual e o penúltimo nunca saem, em trilha de qualquer tamanho', () => {
    for (let total = 1; total <= 6; total++) {
      expect(degrauSomeNoCelular(total - 1, total)).toBe(false);
      if (total >= 2) expect(degrauSomeNoCelular(total - 2, total)).toBe(false);
    }
  });

  it('nenhuma trilha mostra mais degraus do que cabem no celular', () => {
    for (let total = 1; total <= 6; total++) {
      const trilha = Array.from({ length: total }, (_, i) => `degrau ${i}`);
      expect(noCelular(trilha).length).toBe(Math.min(total, DEGRAUS_NO_CELULAR));
    }
  });
});
