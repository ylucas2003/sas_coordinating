import { describe, expect, it } from 'vitest';
import {
  corteDaMateria, eliminaSozinho, REGUA_DA_CASA, reguaDaCasa, rotuloDoCorte,
} from './criterios';
import type { CriterioClassificacao } from '../tipos/dominio';

function regua(p: Partial<CriterioClassificacao> & { slug: string }): CriterioClassificacao {
  return {
    nome: p.slug, descricao: '', fase: null, combinador: 'todos',
    desempate: [], predicados: [], cortes: {}, corteGenerico: null,
    corteMedia: null, eliminatorias: [],
    ...p,
  };
}

const CASA = regua({
  slug: REGUA_DA_CASA,
  nome: 'Tio Leo',
  cortes: { matematica: 4, ingles: 5 },
  corteGenerico: 4,
  corteMedia: 5,
  eliminatorias: ['ingles'],
});

const OUTRA = regua({ slug: 'ita-f1', nome: 'ITA — Fase 1', fase: 1 });

describe('reguaDaCasa', () => {
  it('acha a régua da casa em qualquer posição da lista', () => {
    expect(reguaDaCasa([OUTRA, CASA])?.slug).toBe(REGUA_DA_CASA);
  });

  // O resto honesto: sem ele um slug renomeado no servidor deixaria a tela
  // sem corte nenhum — e tela sem corte é pior que tela com o corte de outra
  // régua, porque as duas telas escrevem o nome do que encontraram.
  it('sem a régua da casa, cai na primeira disponível', () => {
    expect(reguaDaCasa([OUTRA])?.slug).toBe('ita-f1');
  });

  it('lista vazia devolve null, não estoura', () => {
    expect(reguaDaCasa([])).toBeNull();
  });
});

describe('corteDaMateria', () => {
  it('sem régua não há linha honesta a desenhar', () => {
    expect(corteDaMateria(null, 'matematica')).toBeNull();
  });

  it('o mínimo da matéria vence o genérico', () => {
    expect(corteDaMateria(CASA, 'ingles')).toBe(5);
  });

  it('matéria que a régua não menciona cai no genérico', () => {
    expect(corteDaMateria(CASA, 'redacao')).toBe(4);
  });

  // Sem matéria o eixo é a MÉDIA do aluno, e o que vale é o que a régua exige
  // dela — 5,0 aqui, contra os 4,0 por matéria.
  it('sem matéria, e sem genérico, sobra a exigência da média', () => {
    expect(corteDaMateria(regua({ slug: 'x', corteMedia: 5 }), null)).toBe(5);
  });

  it('régua que não cobra nada aplicável devolve null', () => {
    expect(corteDaMateria(regua({ slug: 'x' }), 'fisica')).toBeNull();
  });
});

describe('eliminaSozinho', () => {
  it('o Inglês da casa elimina', () => {
    expect(eliminaSozinho(CASA, 'ingles')).toBe(true);
  });

  it('matéria fora da lista não elimina', () => {
    expect(eliminaSozinho(CASA, 'matematica')).toBe(false);
  });

  it('sem matéria não há o que eliminar', () => {
    expect(eliminaSozinho(CASA, null)).toBe(false);
  });
});

describe('rotuloDoCorte', () => {
  it('vírgula decimal, uma casa', () => {
    expect(rotuloDoCorte(4, false)).toBe('corte 4,0');
  });

  it('a eliminatória diz que elimina', () => {
    expect(rotuloDoCorte(5, true)).toBe('corte 5,0 (eliminatório)');
  });
});
