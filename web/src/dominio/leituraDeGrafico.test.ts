import { describe, expect, it } from 'vitest';

import { lerDistribuicao, lerDuasFases, lerEvolucao, lerSeries } from './leituraDeGrafico';
import type { RespostaHistograma } from '../tipos/dominio';

/** Histograma com bins de 1,0 ponto — um número por faixa [i, i+1). */
function hist(contagens: number[]): RespostaHistograma {
  return { largura_bin: 1, maximo: contagens.length, contagens };
}

describe('lerDistribuicao', () => {
  it('sem histograma ou sem massa, não inventa frase', () => {
    expect(lerDistribuicao({ histograma: null })).toBeNull();
    expect(lerDistribuicao({ histograma: hist([0, 0, 0]) })).toBeNull();
  });

  it('descreve a faixa onde a maior parte ficou', () => {
    //         0  1  2  3   4   5  6  7
    const h = hist([0, 0, 0, 2, 20, 20, 2, 0]);
    const r = lerDistribuicao({ histograma: h })!;
    expect(r.frase).toContain('Metade da turma ficou entre 4,0 e 6,0');
    expect(r.poucosDados).toBe(false);
  });

  it('com dois picos, a faixa se alarga em vez de esconder a divisão', () => {
    // 30 alunos em [1,2) e 30 em [8,9): a turma está partida ao meio.
    // Uma "menor faixa que fecha 50%" diria "entre 1,0 e 2,0" — verdade que
    // esconde metade da turma. A faixa do meio atravessa o vale e denuncia.
    const h = hist([0, 30, 0, 0, 0, 0, 0, 0, 30, 0]);
    expect(lerDistribuicao({ histograma: h })!.frase).toContain('entre 1,0 e 9,0');
  });

  it('com poucas notas, diz que são poucas em vez de sugerir padrão', () => {
    const r = lerDistribuicao({ histograma: hist([0, 1, 2, 1]) })!;
    expect(r.poucosDados).toBe(true);
    expect(r.frase).toContain('4 notas');
    expect(r.frase).not.toContain('ficou entre');
  });

  it('conta abaixo do corte pela massa dos bins fechados', () => {
    // corte 4,0: os bins [0,1) … [3,4) contam; o bin [4,5) não.
    const h = hist([1, 1, 1, 1, 16, 0, 0, 0, 0, 0]);
    const r = lerDistribuicao({ histograma: h, corte: 4 })!;
    expect(r.frase).toContain('20% ficaram abaixo do corte (4,0)');
  });

  it('rateia o bin que o corte atravessa em vez de descartá-lo', () => {
    // O corte do ITA F1 é 5 de 12 = 4,1667 — não cai em fronteira de bin.
    // Descartar o bin [4,0;5,0) fazia a frase dizer "ninguém abaixo do corte"
    // ao lado de um "88% aprovados" calculado sobre as notas exatas.
    const h = hist([0, 0, 0, 0, 12, 88]);   // 12 em [4,0;5,0), 88 em [5,0;6,0)
    const r = lerDistribuicao({ histograma: h, corte: 5 / 12 * 10 })!;
    expect(r.frase).not.toContain('Ninguém');
    expect(r.frase).toContain('abaixo do corte (4,2)');
  });

  it('menos de 1% não vira "0%" nem "ninguém"', () => {
    // 1 de 319 = 0,31% → Math.round dá 0.
    const contagens = [0, 0, 0, 0, 1, 318];
    const r = lerDistribuicao({ histograma: hist(contagens), corte: 5 })!;
    expect(r.frase).toContain('Menos de 1% ficou abaixo do corte (5,0)');
  });

  it('quase todos abaixo não vira "100%" quando alguém passou', () => {
    const r = lerDistribuicao({ histograma: hist([0, 0, 0, 0, 318, 1]), corte: 5 })!;
    expect(r.frase).toContain('Quase toda a turma ficou abaixo do corte (5,0)');
  });

  it('quando ninguém fica abaixo, diz isso em vez de "0%"', () => {
    const r = lerDistribuicao({ histograma: hist([0, 0, 0, 0, 10, 10]), corte: 4 })!;
    expect(r.frase).toContain('Ninguém ficou abaixo do corte');
  });

  it('situa a média em relação ao corte', () => {
    const h = hist([0, 0, 0, 0, 10, 10]);
    expect(lerDistribuicao({ histograma: h, corte: 4, media: 5.2 })!.frase)
      .toContain('A média (5,2) está acima dele.');
    expect(lerDistribuicao({ histograma: h, corte: 6, media: 5.2 })!.frase)
      .toContain('A média (5,2) está abaixo dele.');
  });

  it('sem corte, não fala de corte', () => {
    const r = lerDistribuicao({ histograma: hist([0, 0, 0, 0, 10, 10]), media: 5.2 })!;
    expect(r.frase).toBe('Metade da turma ficou entre 4,0 e 6,0. A média é 5,2.');
  });
});

describe('lerEvolucao', () => {
  it('precisa de pelo menos dois pontos', () => {
    expect(lerEvolucao([])).toBeNull();
    expect(lerEvolucao([5])).toBeNull();
    expect(lerEvolucao([5, null, undefined])).toBeNull();
  });

  it('movimento menor que 0,3 ponto é estabilidade, não tendência', () => {
    expect(lerEvolucao([5.0, 5.1, 5.2])).toContain('estável em torno de 5,2');
  });

  it('nomeia a direção quando o movimento é real', () => {
    expect(lerEvolucao([5.0, 5.8, 6.4])).toContain('subiu de 5,0 para 6,4');
    expect(lerEvolucao([7.0, 6.0, 5.0])).toContain('caiu de 7,0 para 5,0');
  });

  it('avisa quando o caminho oscilou mais do que o saldo', () => {
    // Saldo +0,5, mas passou por 2,0 e 9,0 no meio.
    const frase = lerEvolucao([5.0, 9.0, 2.0, 5.5])!;
    expect(frase).toContain('oscilação pelo caminho');
    expect(frase).toContain('de 2,0 a 9,0');
  });
});


describe('lerSeries', () => {
  const serie = (nome: string, notas: number[]) => ({ nome, notas });

  it('ignora séries com menos de dois pontos', () => {
    expect(lerSeries([serie('Matemática', [5])])).toBeNull();
    expect(lerSeries([])).toBeNull();
  });

  it('com uma linha só, descreve o movimento dela', () => {
    expect(lerSeries([serie('Matemática', [5.0, 7.0])]))
      .toBe('Matemática subiu de 5,0 para 7,0 ao longo de 2 pontos.');
  });

  it('com várias, aponta a que mais subiu e a que mais caiu', () => {
    const frase = lerSeries([
      serie('Matemática', [5.0, 8.0]),
      serie('Física', [6.0, 6.1]),
      serie('Química', [7.0, 4.0]),
    ])!;
    expect(frase).toContain('3 matérias no gráfico.');
    expect(frase).toContain('Matemática subiu');
    expect(frase).toContain('Química caiu');
    // A que ficou parada não entra: seria ruído numa frase de resumo.
    expect(frase).not.toContain('Física');
  });

  it('quando nada se move, diz isso em vez de forçar um destaque', () => {
    const frase = lerSeries([
      serie('Matemática', [5.0, 5.1]),
      serie('Física', [6.0, 6.1]),
    ])!;
    expect(frase).toContain('Nenhuma se moveu o bastante');
  });
});

describe('lerDuasFases', () => {
  it('sem nenhuma das fases, não diz nada', () => {
    expect(lerDuasFases({})).toBeNull();
  });

  it('descreve as duas fases e o salto entre elas', () => {
    const frase = lerDuasFases({
      fase1: { histograma: hist([0, 0, 0, 0, 10, 10]), media: 5.0 },
      fase2: { histograma: hist([0, 0, 0, 0, 0, 10, 10]), media: 6.2 },
      corte: 4,
      deltaMedia: 1.2,
    })!;
    expect(frase).toContain('Fase 1:');
    expect(frase).toContain('Fase 2:');
    expect(frase).toContain('a média subiu 1,2');
  });

  it('salto menor que 0,3 não vira frase', () => {
    const frase = lerDuasFases({
      fase1: { histograma: hist([0, 0, 0, 0, 10, 10]), media: 5.0 },
      deltaMedia: 0.2,
    })!;
    expect(frase).not.toContain('a média');
  });
});
