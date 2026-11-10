import { describe, expect, it } from 'vitest';

import {
  assuntosDaMateria, blocosDoProfessor, calendarioDoPlano, etapasDoProfessor, passosDaApresentacao,
} from './cronograma';
import type { ItemDoPlano, PlanoDoAno } from '../tipos/cronograma';

function item(parcial: Partial<ItemDoPlano>): ItemDoPlano {
  return {
    materia: 'Matemática', professor: 'Ana', ordem: 1, nome: 'Item', ref: '', origem: 'título', de: '2026-01-12',
    ate: '2026-01-12', aulas_2026: 2, aulas_2027: 2, codigos: { '9.1': 1 }, meses_2026: [], semanas: {}, ...parcial,
  };
}

function plano(itens: ItemDoPlano[]): PlanoDoAno {
  return {
    gerado_em: '2026-11-10', minutos_por_aula: 50, total_horas: 1220, total_aulas: 1464,
    materias: [{ materia: 'Matemática', aulas_2024: 0, aulas_2025: 0, aulas_2026: 0, parte_media_pct: 100, aulas_2027: 10, horas_2027: 8 }],
    professores: [
      { materia: 'Matemática', professor: 'Ana', frentes: 'Mat 1', aulas_2026: 6, aulas_2027: 6, parte_media_pct: 60, revisao_2027: 0, formato_2026: [6, 0, 0] },
      { materia: 'Matemática', professor: 'Bia', frentes: 'Mat 2', aulas_2026: 4, aulas_2027: 4, parte_media_pct: 40, revisao_2027: 0, formato_2026: [4, 0, 0] },
    ],
    grupos: [
      { materia: 'Matemática', codigo: '9.1', nome: 'Trigonometria', conteudo: true, peso_ita: 16.9, peso_ime: 12.7, peso_medio: 14.8 },
      { materia: 'Matemática', codigo: '5.1', nome: 'Polinômios', conteudo: true, peso_ita: 12.7, peso_ime: 11.5, peso_medio: 12.1 },
    ],
    itens,
    calendario_2027: {
      semanas: [3, 4, 5, 6, 7].map((w) => ({ semana: w, inicio: `2027-0${w < 6 ? 1 : 2}-${String(w * 3).padStart(2, '0')}` })),
      marcos: [{ semana: 5, rotulo: 'Recesso', tipo: 'recesso', confirmado: false }],
    },
  };
}

describe('assuntosDaMateria', () => {
  it('soma as aulas de cada professor no assunto, repartindo o item pelos códigos', () => {
    const p = plano([
      item({ professor: 'Ana', aulas_2027: 4, codigos: { '9.1': 0.5, '5.1': 0.5 } }),
      item({ professor: 'Bia', aulas_2027: 3, codigos: { '9.1': 1 } }),
    ]);
    const trig = assuntosDaMateria(p, 'Matemática').find((a) => a.codigo === '9.1');
    expect(trig?.aulas2027).toBe(5);
    expect(trig?.porProfessor).toEqual([['Bia', 3], ['Ana', 2]]);
  });

  it('põe os assuntos de conteúdo antes da revisão, mesmo quando a revisão tem mais aulas', () => {
    const p = plano([
      item({ aulas_2027: 1, codigos: { '9.1': 1 } }),
      item({ ordem: 2, aulas_2027: 9, codigos: { REVF: 1 } }),
    ]);
    expect(assuntosDaMateria(p, 'Matemática').map((a) => a.codigo)).toEqual(['9.1', 'REVF']);
  });
});

describe('blocosDoProfessor', () => {
  const semanas = [3, 4, 5, 6, 7];

  it('junta semanas vizinhas do mesmo assunto num bloco só', () => {
    const p = plano([item({ semanas: { 3: 2, 4: 2 } })]);
    const blocos = blocosDoProfessor(p, 'Matemática', 'Ana', semanas);
    expect(blocos).toHaveLength(1);
    expect(blocos[0]).toMatchObject({ codigo: '9.1', de: 3, ate: 4, rotulo: 'Trigonometria' });
  });

  it('absorve um bloco de uma semana no vizinho, para a visão rápida', () => {
    const p = plano([
      item({ ordem: 1, semanas: { 3: 3, 5: 3 }, codigos: { '9.1': 1 } }),
      item({ ordem: 2, nome: 'Polinômios', semanas: { 4: 1 }, codigos: { '5.1': 1 } }),
    ]);
    const blocos = blocosDoProfessor(p, 'Matemática', 'Ana', semanas);
    expect(blocos.map((b) => [b.codigo, b.de, b.ate])).toEqual([['9.1', 3, 5]]);
  });

  it('não absorve a revisão de fim de ano', () => {
    const p = plano([
      item({ ordem: 1, semanas: { 3: 3, 4: 3 } }),
      item({ ordem: 2, nome: 'Revisão', semanas: { 5: 1 }, codigos: { REVF: 1 } }),
    ]);
    expect(blocosDoProfessor(p, 'Matemática', 'Ana', semanas).map((b) => b.codigo)).toEqual(['9.1', 'REVF']);
  });

  it('nomeia o bloco sem grupo no SAS pelo nome que o professor usa', () => {
    const p = plano([item({ nome: 'Desigualdades', semanas: { 3: 2, 4: 2 }, codigos: { FORA: 1 } })]);
    expect(blocosDoProfessor(p, 'Matemática', 'Ana', semanas)[0]?.rotulo).toBe('Desigualdades');
  });
});

describe('etapasDoProfessor', () => {
  it('faz uma etapa por assunto, mesmo quando o professor alterna entre dois', () => {
    const p = plano([
      item({ ordem: 1, nome: 'Seno', codigos: { '9.1': 1 } }),
      item({ ordem: 2, nome: 'Raízes', codigos: { '5.1': 1 } }),
      item({ ordem: 3, nome: 'Cosseno', codigos: { '9.1': 1 } }),
    ]);
    const cal = calendarioDoPlano(p);
    const etapas = etapasDoProfessor(p, 'Matemática', 'Ana', cal.mesDaSemana, cal.mesesDoAno);
    expect(etapas.map((e) => [e.codigo, e.itens.length])).toEqual([['9.1', 2], ['5.1', 1]]);
    // com um item só, a etapa leva o nome que o professor usa; com vários, o do assunto
    expect(etapas.map((e) => e.rotulo)).toEqual(['Trigonometria', 'Raízes']);
  });
});

describe('calendarioDoPlano e passosDaApresentacao', () => {
  it('não conta o recesso como semana de aula', () => {
    expect(calendarioDoPlano(plano([])).semanasDeAula).toBe(4);
  });

  it('passa pelo ano, pela matéria e por cada professor, nessa ordem', () => {
    expect(passosDaApresentacao(plano([])).map((p) => p.aba)).toEqual(['ano', 'materias', 'quem', 'professor', 'professor']);
  });
});
