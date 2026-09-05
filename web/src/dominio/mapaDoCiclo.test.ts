import { describe, expect, it } from 'vitest';

import {
  comSinal, fraseDoBloco, LIMIAR_FORA_DO_PADRAO, MAX_DESTAQUES, montarMapa,
} from './mapaDoCiclo';
import type { RecorteMateria, Simulado } from '../tipos/dominio';

// O que estes testes travam é o que a tela do mapa promete e o olho não
// confere sozinho: o denominador é UM, a ordem é pior-primeiro, e "não sei"
// nunca ocupa o lugar de "está ruim".

function bloco({
  n = 100, media = 5, mediana = 5, contagens = [1, 2, 3], delta = null as number | null,
}) {
  return {
    stats: { n, media, mediana, desvioPadrao: 1 },
    histograma: { largura_bin: 0.5, maximo: 10, contagens },
    // `delta` chega no payload e não está no tipo — ver `BlocoComComparacao`.
    delta: delta == null ? null : { media: delta },
  };
}

function recorte(over: Partial<RecorteMateria> & { materia: { codigo: string; nome: string } }) {
  return {
    corte: 4,
    eliminatoria: false,
    fase1: null,
    fase2: null,
    ...over,
  } as RecorteMateria;
}

function prova(over: Partial<Simulado> & { id: string }): Simulado {
  return {
    nome: 'P1', rotuloCurto: 'P1', tipo: 'fase_1', materia: { codigo: 'FIS', nome: 'Física' },
    dataAplicacao: '2026-08-01', cicloId: 'c4', cicloOrdem: 4, vestibularAlvo: 'ITA',
    notaMaxima: 10, anulado: false, notaConfiavel: true, motivoNotaNaoConfiavel: null,
    origem: 'canvas', canvasEstado: 'sincronizado', canvasErro: null,
    media: 5, mediana: 5, desvioPadrao: 1, nPresentes: 100,
    ...over,
  } as Simulado;
}

describe('montarMapa', () => {
  it('usa um denominador só para as barras dos doze blocos', () => {
    const { pico } = montarMapa({
      recortes: [
        recorte({
          materia: { codigo: 'FIS', nome: 'Física' },
          fase1: bloco({ contagens: [4, 9, 2] }) as never,
        }),
        recorte({
          materia: { codigo: 'MAT', nome: 'Matemática' },
          fase1: bloco({ contagens: [1, 44, 3] }) as never,
        }),
      ],
      ordem: 'distancia',
    });
    // Sem isto cada cartão se normaliza pelo próprio máximo e a comparação
    // que justifica a tela some.
    expect(pico).toBe(44);
  });

  it('não devolve pico quando não há contagem nenhuma', () => {
    const { pico } = montarMapa({ recortes: [], ordem: 'distancia' });
    expect(pico).toBeNull();
  });

  it('ignora a fase sem aluno — bloco vazio não é bloco', () => {
    const { blocos } = montarMapa({
      recortes: [
        recorte({
          materia: { codigo: 'FIS', nome: 'Física' },
          fase1: bloco({ n: 200 }) as never,
          fase2: bloco({ n: 0 }) as never,
        }),
      ],
      ordem: 'distancia',
    });
    expect(blocos.map((b) => b.chave)).toEqual(['FIS-F1']);
  });

  it('ordena por distância do corte, pior primeiro', () => {
    const { blocos } = montarMapa({
      recortes: [
        recorte({ materia: { codigo: 'POR', nome: 'Português' }, fase1: bloco({ media: 6.4 }) as never }),
        recorte({ materia: { codigo: 'FIS', nome: 'Física' }, fase1: bloco({ media: 3.4 }) as never }),
        recorte({ materia: { codigo: 'MAT', nome: 'Matemática' }, fase1: bloco({ media: 4.6 }) as never }),
      ],
      ordem: 'distancia',
    });
    expect(blocos.map((b) => b.materiaCodigo)).toEqual(['FIS', 'MAT', 'POR']);
  });

  it('põe o bloco sem a grandeza em vigor no FIM, nunca no topo', () => {
    // "Não sei" no topo da lista de piores é a mentira que esta tela não pode
    // contar: o coordenador abriria a matéria errada.
    const { blocos } = montarMapa({
      recortes: [
        recorte({
          materia: { codigo: 'RED', nome: 'Redação' },
          corte: null,
          fase1: bloco({ media: 5, delta: null }) as never,
        }),
        recorte({
          materia: { codigo: 'FIS', nome: 'Física' },
          fase1: bloco({ media: 3.4, delta: -1.3 }) as never,
        }),
      ],
      ordem: 'variacao',
    });
    expect(blocos.map((b) => b.materiaCodigo)).toEqual(['FIS', 'RED']);
    expect(blocos[1].variacao).toBeNull();
    expect(blocos[1].distancia).toBeNull();
  });

  it('destaca no máximo dois, e só quem passa do limiar de um bin', () => {
    const { blocos, foraDoPadrao } = montarMapa({
      recortes: ['A', 'B', 'C', 'D'].map((c, i) =>
        recorte({
          materia: { codigo: c, nome: c },
          fase1: bloco({ media: 4, delta: -1 - i }) as never,
        })),
      ordem: 'variacao',
    });
    expect(blocos.filter((b) => b.destaque).length).toBe(MAX_DESTAQUES);
    // Os dois que crescem são os dois piores, que a ordenação já pôs na frente.
    expect(blocos.slice(0, 2).every((b) => b.destaque)).toBe(true);
    expect(foraDoPadrao).toBe(4);
  });

  it('não destaca nada quando o ciclo inteiro está no padrão', () => {
    const { blocos, foraDoPadrao } = montarMapa({
      recortes: [
        recorte({ materia: { codigo: 'FIS', nome: 'Física' }, fase1: bloco({ delta: -0.4 }) as never }),
        recorte({ materia: { codigo: 'MAT', nome: 'Matemática' }, fase1: bloco({ delta: 0.2 }) as never }),
      ],
      ordem: 'variacao',
    });
    expect(blocos.some((b) => b.destaque)).toBe(false);
    expect(foraDoPadrao).toBe(0);
    // Uma grade uniforme É a leitura "está tudo no padrão" — inventar um
    // destaque aqui prometeria uma anomalia que não existe.
    expect(LIMIAR_FORA_DO_PADRAO).toBe(0.5);
  });

  it('só oferece a ordem por variação quando existe com quem comparar', () => {
    const semAnterior = montarMapa({
      recortes: [recorte({ materia: { codigo: 'FIS', nome: 'Física' }, fase1: bloco({}) as never })],
      ordem: 'distancia',
    });
    expect(semAnterior.temVariacao).toBe(false);
  });

  it('vira atalho para a prova só quando o bloco desenha UMA prova', () => {
    const provas = [
      prova({ id: 's1' }),
      prova({ id: 's2', materia: { codigo: 'MAT', nome: 'Matemática' } }),
      prova({ id: 's3', materia: { codigo: 'MAT', nome: 'Matemática' } }),
    ];
    const { blocos } = montarMapa({
      recortes: [
        recorte({ materia: { codigo: 'FIS', nome: 'Física' }, fase1: bloco({}) as never }),
        recorte({ materia: { codigo: 'MAT', nome: 'Matemática' }, fase1: bloco({}) as never }),
      ],
      provas,
      ordem: 'distancia',
    });
    const porChave = Object.fromEntries(blocos.map((b) => [b.chave, b]));
    expect(porChave['FIS-F1'].provaId).toBe('s1');
    expect(porChave['MAT-F1'].provaId).toBeNull();
    expect(porChave['MAT-F1'].provasNoBloco).toBe(2);
  });

  it('não aponta para prova que o agregado não conta', () => {
    // Anulada e fora das estatísticas ficam de fora do bloco no servidor; o
    // atalho abriria uma distribuição diferente da desenhada no cartão.
    const { blocos } = montarMapa({
      recortes: [recorte({ materia: { codigo: 'FIS', nome: 'Física' }, fase1: bloco({}) as never })],
      provas: [prova({ id: 's1', anulado: true }), prova({ id: 's2', notaConfiavel: false })],
      ordem: 'distancia',
    });
    expect(blocos[0].provaId).toBeNull();
    expect(blocos[0].provasNoBloco).toBe(0);
  });
});

describe('fraseDoBloco', () => {
  const base = montarMapa({
    recortes: [
      recorte({
        materia: { codigo: 'FIS', nome: 'Física' },
        fase1: bloco({ media: 3.4, delta: -1.3 }) as never,
      }),
    ],
    ordem: 'variacao',
  }).blocos[0];

  it('relata a grandeza pela qual a grade está ordenada', () => {
    expect(fraseDoBloco(base, 'variacao', 'Ciclo 3')).toBe('−1,3 vs Ciclo 3');
    expect(fraseDoBloco(base, 'distancia', 'Ciclo 3')).toBe('0,6 abaixo do corte');
  });

  it('diz "não sei" em vez de zero quando não há ciclo anterior', () => {
    const orfao = { ...base, variacao: null };
    expect(fraseDoBloco(orfao, 'variacao', null)).toBe('sem o ciclo anterior para comparar');
  });

  it('chama de padrão a diferença menor que um bin', () => {
    expect(fraseDoBloco({ ...base, variacao: -0.3 }, 'variacao', 'Ciclo 3'))
      .toBe('no padrão de Ciclo 3');
  });

  it('não escreve corte onde a régua não exige nota', () => {
    expect(fraseDoBloco({ ...base, distancia: null }, 'distancia', null))
      .toBe('a régua não exige nota nesta matéria');
  });
});

describe('comSinal', () => {
  it('usa o menos de verdade, para a coluna de números não desalinhar', () => {
    expect(comSinal(-1.25)).toBe('−1,3');
    expect(comSinal(0.4)).toBe('+0,4');
    expect(comSinal(0)).toBe('0,0');
  });
});
