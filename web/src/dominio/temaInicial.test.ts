import { describe, expect, it } from 'vitest';

import { temaInicial, VERSAO_DA_PREFERENCIA } from './temaInicial';

const nada = { tema: null, temaAntigo: null, versao: null };

describe('o tema com que a visita começa', () => {
  it('quem nunca escolheu entra claro, e não há o que apagar', () => {
    expect(temaInicial(nada)).toEqual({ tema: 'dia', zerar: false });
  });

  it('escuro gravado ANTES desta versão é zerado uma vez', () => {
    // É o caso que motivou a regra: a pessoa clicou na lua em algum momento e
    // continuava vendo escuro depois de o padrão ter virado claro.
    expect(temaInicial({ tema: 'noite', temaAntigo: null, versao: null }))
      .toEqual({ tema: 'dia', zerar: true });
  });

  it('a chave antiga do aluno também é zerada', () => {
    expect(temaInicial({ tema: null, temaAntigo: 'noite', versao: null }))
      .toEqual({ tema: 'dia', zerar: true });
  });

  it('escuro escolhido DEPOIS desta versão vale para sempre', () => {
    expect(temaInicial({ tema: 'noite', temaAntigo: null, versao: VERSAO_DA_PREFERENCIA }))
      .toEqual({ tema: 'noite', zerar: false });
  });

  it('valor estranho na versão atual cai no padrão sem apagar nada', () => {
    expect(temaInicial({ tema: 'roxo', temaAntigo: null, versao: VERSAO_DA_PREFERENCIA }))
      .toEqual({ tema: 'dia', zerar: false });
  });
});
