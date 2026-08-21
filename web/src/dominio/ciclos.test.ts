import { describe, expect, it } from 'vitest';
import { FILTRO_CICLOS_VAZIO, aplicarFiltros, contarPorChip, intersectaPeriodo } from './ciclos';
import type { Ciclo } from '../tipos/dominio';

function ciclo(p: Partial<Ciclo> & { id: string }): Ciclo {
  return {
    nome: p.id, anoLetivo: 2026, vestibularAlvo: 'ITA',
    periodoInicio: '2026-02-01', periodoFim: '2026-03-01', simuladoIds: [],
    ...p,
  } as Ciclo;
}

describe('intersectaPeriodo', () => {
  const c = ciclo({ id: 'C1', periodoInicio: '2026-02-08', periodoFim: '2026-03-08' });

  it('sem intervalo, tudo passa', () => {
    expect(intersectaPeriodo(c, { inicio: null, fim: null })).toBe(true);
  });

  // A regra que motiva a função: encostar basta, não precisa estar contido.
  it('aceita ciclo que apenas ENCOSTA no intervalo', () => {
    expect(intersectaPeriodo(c, { inicio: '2026-03-01', fim: '2026-04-30' })).toBe(true);
  });

  it('recusa ciclo inteiramente antes ou depois', () => {
    expect(intersectaPeriodo(c, { inicio: '2026-04-01', fim: '2026-04-30' })).toBe(false);
    expect(intersectaPeriodo(c, { inicio: '2026-01-01', fim: '2026-01-31' })).toBe(false);
  });

  it('aceita intervalo aberto de um lado', () => {
    expect(intersectaPeriodo(c, { inicio: '2026-03-01', fim: null })).toBe(true);
    expect(intersectaPeriodo(c, { inicio: null, fim: '2026-01-01' })).toBe(false);
  });

  it('recusa ciclo sem período quando há intervalo', () => {
    const semPeriodo = ciclo({ id: 'C2', periodoInicio: '', periodoFim: '' });
    expect(intersectaPeriodo(semPeriodo, { inicio: '2026-01-01', fim: '2026-12-31' })).toBe(false);
  });
});

describe('aplicarFiltros', () => {
  const dados = [
    ciclo({ id: 'C1', vestibularAlvo: 'ITA', anoLetivo: 2026 }),
    ciclo({ id: 'C2', vestibularAlvo: 'IME', anoLetivo: 2026 }),
    ciclo({ id: 'C3', vestibularAlvo: 'ITA', anoLetivo: 2025 }),
  ];

  it('combina vestibular e ano', () => {
    const r = aplicarFiltros(dados, {
      ...FILTRO_CICLOS_VAZIO,
      vestibulares: new Set(['ITA']),
      anos: new Set([2026]),
    });
    expect(r.map((c) => c.id)).toEqual(['C1']);
  });
});

describe('contarPorChip', () => {
  it('cada eixo ignora o próprio filtro', () => {
    const dados = [
      ciclo({ id: 'C1', vestibularAlvo: 'ITA', anoLetivo: 2026 }),
      ciclo({ id: 'C2', vestibularAlvo: 'IME', anoLetivo: 2026 }),
    ];
    const c = contarPorChip(dados, { ...FILTRO_CICLOS_VAZIO, vestibulares: new Set(['ITA']) });
    expect(c.vestibular.get('IME')).toBe(1);
    expect(c.ano.get(2026)).toBe(1);
  });
});
