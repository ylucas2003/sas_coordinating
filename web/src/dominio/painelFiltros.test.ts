import { describe, expect, it } from 'vitest';
import {
  ciclosNoRecorte, cicloPadrao, contagensDoRecorte, recorteCompleto, rotuloDoCiclo,
} from './painelFiltros';
import type { Ciclo, Simulado } from '../tipos/dominio';

function ciclo(p: Partial<Ciclo> & { id: string }): Ciclo {
  return {
    nome: p.id, ordem: 1, anoLetivo: 2026, vestibularAlvo: 'ITA',
    periodoInicio: '2026-02-01', periodoFim: '2026-03-01', simuladoIds: [],
    ...p,
  } as Ciclo;
}

function simulado(p: Partial<Simulado> & { id: string; cicloId: string }): Simulado {
  return {
    nome: p.id, rotuloCurto: null, tipo: 'fase_1', materia: null,
    dataAplicacao: '2026-03-01', cicloOrdem: 1, vestibularAlvo: 'ITA',
    notaMaxima: 10, anulado: false, origem: 'canvas', canvasEstado: 'ok', canvasErro: null,
    ...p,
  } as Simulado;
}

// A fileira real de produção, reduzida: três anos, dois vestibulares, e o
// "Ciclo 1" existindo três vezes (docs/32 §3.1).
const CICLOS = [
  ciclo({ id: 'ime26', ordem: 1, anoLetivo: 2026, vestibularAlvo: 'IME' }),
  ciclo({ id: 'ita27', ordem: 1, anoLetivo: 2027, vestibularAlvo: 'ITA' }),
  ciclo({ id: 'ime25', ordem: 1, anoLetivo: 2025, vestibularAlvo: 'IME' }),
  ciclo({ id: 'ita25', ordem: 2, anoLetivo: 2025, vestibularAlvo: 'ITA' }),
  ciclo({ id: 'ita26a', ordem: 2, anoLetivo: 2026, vestibularAlvo: 'ITA' }),
  ciclo({ id: 'ita26b', ordem: 4, anoLetivo: 2026, vestibularAlvo: 'ITA' }),
];

describe('recorteCompleto', () => {
  it('nasce com todo ano e todo vestibular marcados', () => {
    const r = recorteCompleto(CICLOS);
    expect([...r.anos].sort()).toEqual([2025, 2026, 2027]);
    expect([...r.vestibulares].sort()).toEqual(['IME', 'ITA']);
  });

  it('sem ciclos, não marca nada', () => {
    const r = recorteCompleto([]);
    expect(r.anos.size).toBe(0);
  });
});

describe('ciclosNoRecorte', () => {
  it('agrupa por ano decrescente, depois vestibular e ordem', () => {
    const ids = ciclosNoRecorte(CICLOS, recorteCompleto(CICLOS)).map((c) => c.id);
    expect(ids).toEqual(['ita27', 'ime26', 'ita26a', 'ita26b', 'ime25', 'ita25']);
  });

  it('o ano estreita a fileira', () => {
    const r = { anos: new Set([2026]), vestibulares: new Set(['ITA', 'IME']) };
    expect(ciclosNoRecorte(CICLOS, r).map((c) => c.id)).toEqual(['ime26', 'ita26a', 'ita26b']);
  });

  it('o vestibular estreita o que o ano deixou', () => {
    const r = { anos: new Set([2026]), vestibulares: new Set(['ITA']) };
    expect(ciclosNoRecorte(CICLOS, r).map((c) => c.id)).toEqual(['ita26a', 'ita26b']);
  });

  // A diferença que justifica não reusar `aplicarFiltros` de ciclos.ts: lá,
  // conjunto vazio deixa tudo passar.
  it('desmarcar tudo esvazia a fileira, e não a devolve inteira', () => {
    const r = { anos: new Set<number>(), vestibulares: new Set(['ITA']) };
    expect(ciclosNoRecorte(CICLOS, r)).toEqual([]);
  });

  it('ciclo sem vestibular não entra em recorte nenhum', () => {
    const orfao = ciclo({ id: 'orfao', vestibularAlvo: null });
    expect(ciclosNoRecorte([orfao], recorteCompleto([orfao]))).toEqual([]);
  });
});

describe('contagensDoRecorte', () => {
  it('cada eixo conta ignorando a si mesmo', () => {
    const r = { anos: new Set([2026]), vestibulares: new Set(['ITA']) };
    const { porAno, porVestibular } = contagensDoRecorte(CICLOS, r);
    // Ano conta dentro do vestibular escolhido (ITA), ignorando o filtro de ano.
    expect(porAno.get(2026)).toBe(2);
    expect(porAno.get(2025)).toBe(1);
    // Vestibular conta dentro do ano escolhido (2026), ignorando o de vestibular.
    expect(porVestibular.get('ITA')).toBe(2);
    expect(porVestibular.get('IME')).toBe(1);
  });
});

describe('cicloPadrao', () => {
  const SIMULADOS = [
    simulado({ id: 's1', cicloId: 'ita25', dataAplicacao: '2025-03-10' }),
    simulado({ id: 's2', cicloId: 'ita26a', dataAplicacao: '2026-04-20' }),
    simulado({ id: 's3', cicloId: 'ime26', dataAplicacao: '2026-06-15' }),
    // O ciclo de 2027 tem prova marcada, mas ela ainda não aconteceu.
    simulado({ id: 's4', cicloId: 'ita27', dataAplicacao: '2027-02-01' }),
  ];

  it('abre no ciclo com a aplicação mais recente já ocorrida', () => {
    expect(cicloPadrao(CICLOS, SIMULADOS, '2026-09-03')?.id).toBe('ime26');
  });

  it('ignora simulado agendado para o futuro', () => {
    expect(cicloPadrao(CICLOS, SIMULADOS, '2026-09-03')?.id).not.toBe('ita27');
  });

  it('sem prova aplicada, cai no primeiro da fileira já ordenada', () => {
    const ordenados = ciclosNoRecorte(CICLOS, recorteCompleto(CICLOS));
    expect(cicloPadrao(ordenados, [], '2026-09-03')?.id).toBe('ita27');
  });

  it('sem ciclo nenhum, devolve null em vez de estourar', () => {
    expect(cicloPadrao([], SIMULADOS, '2026-09-03')).toBeNull();
  });
});

describe('rotuloDoCiclo', () => {
  const c = ciclo({ id: 'x', ordem: 4, anoLetivo: 2026, vestibularAlvo: 'ITA' });

  it('com ano e vestibular fixados, a pílula é só o número', () => {
    expect(rotuloDoCiclo(c, { anos: new Set([2026]), vestibulares: new Set(['ITA']) })).toBe('4');
  });

  it('com o recorte aberto, desambigua', () => {
    expect(rotuloDoCiclo(c, recorteCompleto(CICLOS))).toBe('4 · ITA · 2026');
  });

  it('só o vestibular fixado: falta o ano', () => {
    expect(rotuloDoCiclo(c, { anos: new Set([2025, 2026]), vestibulares: new Set(['ITA']) }))
      .toBe('4 · 2026');
  });

  it('só o ano fixado: falta o vestibular', () => {
    expect(rotuloDoCiclo(c, { anos: new Set([2026]), vestibulares: new Set(['ITA', 'IME']) }))
      .toBe('4 · ITA');
  });
});
