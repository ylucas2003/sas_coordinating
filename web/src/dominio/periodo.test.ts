import { describe, expect, it } from 'vitest';

import {
  clicarNoDia, diasNoPeriodo, normalizarPeriodo, periodoDoAtalho, problemaDoPeriodo,
  rotuloDoPeriodo, TETO_DE_DIAS,
} from './periodo';

// Segunda-feira, 14 de setembro de 2026.
const SEGUNDA = new Date(2026, 8, 14);

describe('os atalhos de período', () => {
  it('hoje é um dia só', () => {
    expect(periodoDoAtalho('hoje', SEGUNDA)).toEqual({ de: '2026-09-14', ate: '2026-09-14' });
  });

  it('a semana vai de segunda a domingo', () => {
    expect(periodoDoAtalho('semana', SEGUNDA)).toEqual({ de: '2026-09-14', ate: '2026-09-20' });
  });

  it('num DOMINGO, "esta semana" é a que está terminando, não a próxima', () => {
    // `getDay()` é 0 no domingo — sem o ajuste, a semana começaria amanhã.
    const domingo = new Date(2026, 8, 20);
    expect(periodoDoAtalho('semana', domingo)).toEqual({ de: '2026-09-14', ate: '2026-09-20' });
  });

  it('este mês e mês passado cobrem o mês inteiro', () => {
    expect(periodoDoAtalho('mes', SEGUNDA)).toEqual({ de: '2026-09-01', ate: '2026-09-30' });
    expect(periodoDoAtalho('mesPassado', SEGUNDA)).toEqual({ de: '2026-08-01', ate: '2026-08-31' });
  });

  it('mês passado em janeiro volta para dezembro do ano anterior', () => {
    expect(periodoDoAtalho('mesPassado', new Date(2027, 0, 10)))
      .toEqual({ de: '2026-12-01', ate: '2026-12-31' });
  });
});

describe('o período escolhido', () => {
  it('conta as duas pontas', () => {
    expect(diasNoPeriodo({ de: '2026-09-14', ate: '2026-09-14' })).toBe(1);
    expect(diasNoPeriodo({ de: '2026-09-01', ate: '2026-09-30' })).toBe(30);
  });

  it('clique ao contrário vira o período certo', () => {
    expect(normalizarPeriodo({ de: '2026-09-20', ate: '2026-09-14' }))
      .toEqual({ de: '2026-09-14', ate: '2026-09-20' });
  });

  it('formato de um dia recusa intervalo, e diz por quê', () => {
    expect(problemaDoPeriodo({ de: '2026-09-14', ate: '2026-09-15' }, 'dia')).toMatch(/um dia/);
    expect(problemaDoPeriodo({ de: '2026-09-14', ate: '2026-09-14' }, 'dia')).toBeNull();
  });

  it('recusa passar do teto — é a armadilha 2 do CLAUDE.md', () => {
    const longo = { de: '2026-01-01', ate: '2026-12-31' };
    expect(problemaDoPeriodo(longo, 'intervalo')).toMatch(String(TETO_DE_DIAS));
    expect(problemaDoPeriodo(longo, 'nenhum')).toBeNull();
  });
});

describe('clicar no calendário', () => {
  const vazio = { de: '2026-09-14', ate: '2026-09-14', esperandoFim: false };

  it('no modo dia, o clique já é a escolha', () => {
    expect(clicarNoDia(vazio, '2026-09-18', 'dia'))
      .toEqual({ de: '2026-09-18', ate: '2026-09-18', esperandoFim: false });
  });

  it('no modo intervalo, são dois cliques em qualquer ordem', () => {
    const primeiro = clicarNoDia(vazio, '2026-09-20', 'intervalo');
    expect(primeiro.esperandoFim).toBe(true);
    expect(clicarNoDia(primeiro, '2026-09-10', 'intervalo'))
      .toEqual({ de: '2026-09-10', ate: '2026-09-20', esperandoFim: false });
  });
});

describe('o rótulo do período', () => {
  it('um dia, um trecho do mês, o mês inteiro e dois meses', () => {
    expect(rotuloDoPeriodo({ de: '2026-09-14', ate: '2026-09-14' })).toBe('14 de setembro de 2026');
    expect(rotuloDoPeriodo({ de: '2026-09-14', ate: '2026-09-20' })).toBe('14 a 20 de setembro de 2026');
    expect(rotuloDoPeriodo({ de: '2026-09-01', ate: '2026-09-30' })).toBe('setembro de 2026');
    expect(rotuloDoPeriodo({ de: '2026-08-28', ate: '2026-09-03' }))
      .toBe('28 de agosto a 3 de setembro de 2026');
  });

  it('atravessando o ano, os dois anos aparecem', () => {
    expect(rotuloDoPeriodo({ de: '2026-12-28', ate: '2027-01-03' }))
      .toBe('28 de dezembro de 2026 a 3 de janeiro de 2027');
  });
});
