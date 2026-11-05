import { describe, expect, it } from 'vitest';

import {
  caminhoAoTrocarDeBloco,
  caminhoNoBloco,
  daSerie,
  nomeCurtoDoCiclo,
  destinoDoCaminho,
  ehListaDoBloco,
  rotuloDoBloco,
  semPrefixoDoBloco,
  serieDoCaminho,
} from './blocos';

describe('serieDoCaminho', () => {
  it('endereço sem prefixo é 3º e cursinho, porque link salvo e e-mail apontam para ele', () => {
    expect(serieDoCaminho('/alunos')).toBe(3);
    expect(serieDoCaminho('/provas/simulados')).toBe(3);
    expect(serieDoCaminho('/')).toBe(3);
  });

  it('o prefixo diz o bloco', () => {
    expect(serieDoCaminho('/1ano/alunos')).toBe(1);
    expect(serieDoCaminho('/2ano')).toBe(2);
  });

  it('prefixo só vale inteiro', () => {
    expect(serieDoCaminho('/1anoalgo/alunos')).toBe(3);
  });
});

describe('semPrefixoDoBloco e caminhoNoBloco', () => {
  it('tira o prefixo', () => {
    expect(semPrefixoDoBloco('/2ano/provas/ciclos')).toBe('/provas/ciclos');
    expect(semPrefixoDoBloco('/alunos')).toBe('/alunos');
    expect(semPrefixoDoBloco('/1ano')).toBe('/');
  });

  it('põe o prefixo, mantendo a query string', () => {
    expect(caminhoNoBloco(1, '/provas?aba=simulados')).toBe('/1ano/provas?aba=simulados');
  });

  it('não muda o endereço de sempre do 3º', () => {
    expect(caminhoNoBloco(3, '/provas')).toBe('/provas');
  });
});

describe('destinoDoCaminho', () => {
  it('acende o item do bloco', () => {
    expect(destinoDoCaminho('/1ano/painel')).toBe('painel');
    expect(destinoDoCaminho('/alunos/abc')).toBe('alunos');
    expect(destinoDoCaminho('/2ano/provas/simulados')).toBe('provas');
  });

  it('as fichas de ciclo e de prova acendem Provas', () => {
    expect(destinoDoCaminho('/ciclos/abc')).toBe('provas');
    expect(destinoDoCaminho('/simulados/abc')).toBe('provas');
  });

  it('o que vale para todas as turmas fica fora dos blocos', () => {
    expect(destinoDoCaminho('/banco')).toBeNull();
    expect(destinoDoCaminho('/administracao/contas')).toBeNull();
    expect(destinoDoCaminho('/cantina')).toBeNull();
  });
});

describe('troca de bloco', () => {
  it('ficha não é lista: pertence a uma coisa só', () => {
    expect(ehListaDoBloco('/1ano/alunos')).toBe(true);
    expect(ehListaDoBloco('/alunos/abc')).toBe(false);
    expect(ehListaDoBloco('/banco')).toBe(false);
  });

  it('continua na mesma tela do outro bloco', () => {
    expect(caminhoAoTrocarDeBloco('/1ano/alunos', 2)).toBe('/2ano/alunos');
    expect(caminhoAoTrocarDeBloco('/2ano/provas/ciclos', 3)).toBe('/provas/ciclos');
    expect(caminhoAoTrocarDeBloco('/provas', 1)).toBe('/1ano/provas');
  });

  it('quem estava fora de uma lista cai no Painel do bloco escolhido', () => {
    expect(caminhoAoTrocarDeBloco('/banco', 1)).toBe('/1ano/painel');
    expect(caminhoAoTrocarDeBloco('/', 2)).toBe('/2ano/painel');
  });
});

describe('daSerie', () => {
  it('fica só com o que é do bloco', () => {
    const lista = [{ id: 'a', serie: 1 }, { id: 'b', serie: 2 }, { id: 'c', serie: 1 }] as const;
    expect(daSerie(lista, 1).map((i) => i.id)).toEqual(['a', 'c']);
  });

  it('1º e 2º nunca se misturam', () => {
    expect(daSerie([{ serie: 1 }], 2)).toEqual([]);
  });

  it('item sem série é do 3º, como todo dado era antes de a coluna existir', () => {
    const antigos: { id: string; serie?: 1 | 2 | 3 }[] = [{ id: 'antigo' }];
    expect(daSerie(antigos, 3)).toHaveLength(1);
    expect(daSerie(antigos, 1)).toHaveLength(0);
  });
});

describe('nomeCurtoDoCiclo', () => {
  it('no 3º é o ciclo de sempre', () => {
    expect(nomeCurtoDoCiclo(11, 3)).toBe('Ciclo 11');
    expect(nomeCurtoDoCiclo(4, undefined)).toBe('Ciclo 4');
  });

  it('no 1º e no 2º ano é a etapa, com AP antes de AG', () => {
    expect(nomeCurtoDoCiclo(1, 1)).toBe('1ª etapa · AP');
    expect(nomeCurtoDoCiclo(2, 2)).toBe('1ª etapa · AG');
    expect(nomeCurtoDoCiclo(6, 2)).toBe('3ª etapa · AG');
  });
});

describe('rotuloDoBloco', () => {
  it('nomeia como a coordenação fala', () => {
    expect(rotuloDoBloco(3)).toBe('3º e cursinho');
    expect(rotuloDoBloco(1)).toBe('1º ano');
    expect(rotuloDoBloco(2)).toBe('2º ano');
  });
});
