import { describe, expect, it } from 'vitest';
import {
  corteDaMateria, eliminaSozinho, explicarCriterio, REGUA_DA_CASA, reguaDaCasa, rotuloDoCorte,
} from './criterios';
import type { CriterioClassificacao, PredicadoCriterio } from '../tipos/dominio';

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

// Os predicados abaixo são os de `stats/criterios.py`, como o servidor os
// serializa — a explicação é leitura deles, então o teste parte do dado real.
function predicado(p: Partial<PredicadoCriterio>): PredicadoCriterio {
  return {
    materia: null, operador: '>=', minimo: 4, eliminatorio: false,
    entraNaMedia: true, peso: 1, fonte: '', ...p,
  };
}

const TIO_LEO = regua({
  slug: REGUA_DA_CASA,
  nome: 'Tio Leo',
  descricao: 'A régua pedagógica do Ari. Corta com E, não com OU.',
  combinador: 'todos',
  desempate: ['media', 'matematica', 'ingles'],
  predicados: [
    predicado({ materia: '*', minimo: 4, fonte: 'régua do colégio: 40% da prova' }),
    predicado({ materia: null, minimo: 5, fonte: 'régua do colégio: 50% da média' }),
    predicado({ materia: 'ingles', minimo: 4, eliminatorio: true, entraNaMedia: false }),
  ],
});

const ITA_F1 = regua({
  slug: 'ita-f1',
  nome: 'ITA — Fase 1',
  fase: 1,
  combinador: 'algum',
  predicados: [
    predicado({ materia: 'matematica', minimo: { acertos: 5, de: 12 }, fonte: 'ITA §4.6.2.1' }),
    predicado({ materia: 'ingles', minimo: { acertos: 5, de: 12 }, entraNaMedia: false }),
    predicado({ materia: null, minimo: 5 }),
  ],
});

describe('explicarCriterio', () => {
  it('traduz "qualquer disciplina", média geral e acertos para o que o coordenador lê', () => {
    const e = explicarCriterio(TIO_LEO);
    expect(e.exigencias.map((x) => `${x.alvo}: ${x.minimo}`)).toEqual([
      'Qualquer disciplina: pelo menos 4,0',
      'Média geral: pelo menos 5,0',
      'Inglês: pelo menos 4,0',
    ]);
    expect(explicarCriterio(ITA_F1).exigencias[0].minimo).toBe('pelo menos 5 de 12 acertos');
  });

  it('carrega a descrição do servidor sem reescrevê-la', () => {
    expect(explicarCriterio(TIO_LEO).descricao).toBe('A régua pedagógica do Ari. Corta com E, não com OU.');
  });

  // É a diferença que a descrição do Tio Leo chama de "E, não OU" — e o que um
  // coordenador precisa ler para não supor que a régua dele corta como o edital.
  it('"todos" só corta quando falha em todas; "algum" corta com uma', () => {
    expect(explicarCriterio(TIO_LEO).quandoCorta).toContain('TODAS');
    expect(explicarCriterio(ITA_F1).quandoCorta).toContain('UMA');
  });

  it('a eliminatória aparece como exceção, com o nome da matéria', () => {
    const e = explicarCriterio(TIO_LEO);
    expect(e.exigencias[2].eliminatorio).toBe(true);
    expect(e.quandoCorta).toContain('Em Inglês, ficar abaixo do mínimo corta sozinho');
    expect(explicarCriterio(ITA_F1).quandoCorta).not.toContain('sozinho');
  });

  it('marca o que é cobrado mas não entra na média', () => {
    const e = explicarCriterio(ITA_F1);
    expect(e.exigencias.find((x) => x.alvo === 'Inglês')?.foraDaMedia).toBe(true);
    // A média geral não "entra na média": a flag dela não quer dizer nada.
    expect(e.exigencias.find((x) => x.alvo === 'Média geral')?.foraDaMedia).toBe(false);
  });

  // `fase_1` com mínimo 0,0 só pesa na média do ITA F2. Listar "pelo menos 0,0"
  // anunciaria uma barreira que não existe.
  it('predicado sem mínimo nenhum não vira exigência', () => {
    const e = explicarCriterio(regua({
      slug: 'x',
      combinador: 'algum',
      predicados: [
        predicado({ materia: 'fisica', minimo: 4 }),
        predicado({ materia: 'fase_1', minimo: 0 }),
      ],
    }));
    expect(e.exigencias.map((x) => x.alvo)).toEqual(['Física']);
  });

  it('uma exigência só dispensa a comparação entre "uma" e "todas"', () => {
    const e = explicarCriterio(regua({
      slug: 'x', combinador: 'algum', predicados: [predicado({ materia: 'fisica', minimo: 4 })],
    }));
    expect(e.quandoCorta).toBe('Fica cortado quem não cumpre o mínimo.');
  });

  it('o desempate sai por extenso, com a média como "Média geral"', () => {
    expect(explicarCriterio(TIO_LEO).desempate).toEqual(['Média geral', 'Matemática', 'Inglês']);
  });

  it('matéria que o front não conhece aparece com a primeira letra maiúscula, não some', () => {
    const e = explicarCriterio(regua({
      slug: 'x', predicados: [predicado({ materia: 'geografia', minimo: 4 })],
    }));
    expect(e.exigencias[0].alvo).toBe('Geografia');
  });
});
