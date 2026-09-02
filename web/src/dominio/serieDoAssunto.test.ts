import { describe, expect, it } from 'vitest';

import type { EstatisticasBanco, RecorrenciaTopico } from '../tipos/banco';
import {
  lerSerieDoAssunto,
  rotuloDaSerie,
  serieDoAssunto,
  tendenciaDaSerie,
} from './serieDoAssunto';

// O que estes testes travam são as quatro armadilhas do módulo — todas do tipo
// que quebra a tela EM SILÊNCIO, com um número plausível no lugar do certo.

function topico(porAno: Record<number, number>): RecorrenciaTopico {
  const total = Object.values(porAno).reduce((s, v) => s + v, 0);
  return {
    codigo: '1.1',
    nome: 'Trigonometria',
    blocoNome: 'Geometria',
    total,
    porAno,
    porFase: {},
    porVestibular: {},
  };
}

/** Uma resposta de `/banco/estatisticas` já recortada por vestibular. */
function resposta(anos: number[], questoesPorAno: number): Pick<
  EstatisticasBanco,
  'anos' | 'questoesPorAno'
> {
  return {
    anos,
    questoesPorAno: Object.fromEntries(anos.map((a) => [a, questoesPorAno])),
  };
}

const de = (inicio: number, fim: number) =>
  Array.from({ length: fim - inicio + 1 }, (_, i) => inicio + i);

describe('serieDoAssunto', () => {
  // ── Armadilha 1 · os zeros não estão no payload ────────────────────────

  it('preenche o ano sem ocorrência com zero, em vez de pulá-lo', () => {
    const serie = serieDoAssunto(
      topico({ 2019: 3, 2021: 2 }),
      resposta([2019, 2020, 2021], 20),
      'ITA',
      { suavizar: false },
    );

    expect(serie?.pontos.map((p) => p.ano)).toEqual([2019, 2020, 2021]);
    expect(serie?.pontos.map((p) => p.contagem)).toEqual([3, 0, 2]);
  });

  it('não comprime o tempo: três anos de domínio dão três pontos', () => {
    // A leitura errada seria desenhar dois pontos (2019 e 2021) lado a lado, e
    // a curva diria "caiu todo ano" onde o certo é "não caiu em 2020".
    const serie = serieDoAssunto(
      topico({ 2019: 3, 2021: 2 }),
      resposta([2019, 2020, 2021], 20),
      'ITA',
    );
    expect(serie?.pontos).toHaveLength(3);
  });

  // ── Armadilha 2 · ausência de prova não é zero ─────────────────────────

  it('a série começa no primeiro ano COM ACERVO da banca, não num ano fixo', () => {
    const ita = serieDoAssunto(topico({ 2019: 2 }), resposta(de(2008, 2025), 20), 'ITA');
    const ime = serieDoAssunto(topico({ 1998: 1 }), resposta(de(1996, 2025), 10), 'IME');

    expect(ita?.pontos[0].ano).toBe(2008);
    expect(ime?.pontos[0].ano).toBe(1996);
  });

  it('devolve null quando não há acervo nenhum no recorte', () => {
    // É "não temos prova desta banca aqui", e a tela declara isso em palavras.
    // Uma série vazia viraria uma linha reta em zero, que AFIRMA que o assunto
    // não cai — a mentira mais cara deste gráfico.
    expect(serieDoAssunto(topico({}), resposta([], 20), 'ITA')).toBeNull();
  });

  it('tópico ausente da resposta vira série de zeros, e não série vazia', () => {
    // "Está no edital e nunca caiu" é informação de estudo: o gráfico existe,
    // e é chapado no zero de propósito.
    const serie = serieDoAssunto(undefined, resposta([2019, 2020], 20), 'ITA');

    expect(serie?.pontos.map((p) => p.contagem)).toEqual([0, 0]);
    expect(serie?.total).toBe(0);
  });

  // ── Armadilha 3 · contagem bruta não compara bancas ────────────────────

  it('o eixo percentual divide pelo tamanho da prova daquele ano', () => {
    // Duas questões valem 10% numa prova de 20 e 20% numa de 10. É exatamente
    // por isso que o eixo padrão não é contagem.
    const ita = serieDoAssunto(topico({ 2019: 2 }), resposta([2019], 20), 'ITA', {
      suavizar: false,
    });
    const ime = serieDoAssunto(topico({ 2019: 2 }), resposta([2019], 10), 'IME', {
      suavizar: false,
    });

    expect(ita?.pontos[0].bruto).toBeCloseTo(10);
    expect(ime?.pontos[0].bruto).toBeCloseTo(20);
  });

  it('o denominador é questoesPorAno, e não a soma dos tópicos', () => {
    // A soma dos tópicos passa do total porque questão mista soma nos dois
    // (docs/22 §1.5). O ponto guarda o denominador que de fato usou, para o
    // teste — e a tela — poderem conferir de onde o percentual saiu.
    const serie = serieDoAssunto(topico({ 2019: 6 }), resposta([2019], 30), 'ITA', {
      suavizar: false,
    });

    expect(serie?.pontos[0].questoesNoAno).toBe(30);
    expect(serie?.pontos[0].bruto).toBeCloseTo(20);
  });

  it('o eixo de contagem devolve a contagem crua', () => {
    const serie = serieDoAssunto(topico({ 2019: 6 }), resposta([2019], 30), 'ITA', {
      eixo: 'contagem',
      suavizar: false,
    });
    expect(serie?.pontos[0].bruto).toBe(6);
  });

  // ── Armadilha 4 · suavizar não pode apagar o número real ───────────────

  it('suaviza o valor plotado e preserva o bruto no mesmo ponto', () => {
    const serie = serieDoAssunto(
      topico({ 2019: 0, 2020: 3, 2021: 0 }),
      resposta([2019, 2020, 2021], 10),
      'ITA',
      { suavizar: true },
    );

    // Bruto: 0%, 30%, 0%. Suavizado: 15%, 10%, 15%.
    expect(serie?.pontos.map((p) => p.bruto)).toEqual([0, 30, 0]);
    expect(serie?.pontos[1].valor).toBeCloseTo(10);
    // O rótulo do ponto mostra o BRUTO — o número que existe, não a média.
    expect(serie?.pontos[1].bruto).toBe(30);
  });

  it('a média móvel é de ANOS, e pula o ano sem prova', () => {
    // O acervo do IME pula 1997: uma janela de três POSIÇÕES sobre
    // [1996, 1998, 1999] mediria quatro anos e chamaria isso de "média de
    // três". 1996 só tem 1998 como vizinho de ano — 1997 não existe.
    const serie = serieDoAssunto(
      topico({ 1996: 2, 1998: 0, 1999: 0 }),
      { anos: [1996, 1998, 1999], questoesPorAno: { 1996: 10, 1998: 10, 1999: 10 } },
      'IME',
      { suavizar: true },
    );

    // 1996 (20%) tem só a si mesmo — 1997 não está no acervo, e 1998 está a
    // dois anos de distância. A média dele é ele próprio.
    expect(serie?.pontos[0].valor).toBeCloseTo(20);
    // 1998 e 1999 são contíguos: média de 0% e 0%.
    expect(serie?.pontos[1].valor).toBeCloseTo(0);
  });

  it('sem suavizar, valor e bruto são o mesmo', () => {
    const serie = serieDoAssunto(
      topico({ 2019: 2, 2020: 4 }),
      resposta([2019, 2020], 20),
      'ITA',
      { suavizar: false },
    );
    for (const ponto of serie?.pontos ?? []) expect(ponto.valor).toBe(ponto.bruto);
  });
});

describe('tendenciaDaSerie', () => {
  it('compara as duas janelas de cinco anos', () => {
    const porAno: Record<number, number> = {};
    for (const ano of de(2016, 2020)) porAno[ano] = 1;
    for (const ano of de(2021, 2025)) porAno[ano] = 4;

    const serie = serieDoAssunto(topico(porAno), resposta(de(2016, 2025), 20), 'ITA');
    const leitura = tendenciaDaSerie(serie);

    expect(leitura?.tendencia).toBe('subindo');
    expect(leitura?.anterior).toBeCloseTo(5);
    expect(leitura?.recente).toBeCloseTo(20);
  });

  it('acervo curto demais não produz tendência nenhuma', () => {
    // Com quatro anos, duas janelas de cinco se sobrepõem: a comparação mediria
    // o mesmo dado contra si mesmo.
    const serie = serieDoAssunto(topico({ 2022: 2 }), resposta(de(2022, 2025), 20), 'ITA');
    expect(tendenciaDaSerie(serie)).toBeNull();
  });

  it('assunto que nunca caiu não tem tendência', () => {
    // "Estável em zero" é verdadeiro e inútil; a tela diz isso melhor com
    // outras palavras.
    const serie = serieDoAssunto(topico({}), resposta(de(2008, 2025), 20), 'ITA');
    expect(tendenciaDaSerie(serie)).toBeNull();
  });

  it('compara o bruto, e não o suavizado', () => {
    // A média móvel já é uma média; comparar médias de médias achataria
    // justamente a virada recente que a pergunta quer enxergar.
    const porAno: Record<number, number> = {};
    for (const ano of de(2016, 2020)) porAno[ano] = 0;
    for (const ano of de(2021, 2025)) porAno[ano] = 5;

    const suave = serieDoAssunto(topico(porAno), resposta(de(2016, 2025), 20), 'ITA', {
      suavizar: true,
    });
    const cru = serieDoAssunto(topico(porAno), resposta(de(2016, 2025), 20), 'ITA', {
      suavizar: false,
    });

    expect(tendenciaDaSerie(suave)).toEqual(tendenciaDaSerie(cru));
  });

  it('série nula não quebra', () => {
    expect(tendenciaDaSerie(null)).toBeNull();
  });
});

describe('lerSerieDoAssunto', () => {
  const anosITA = de(2008, 2025);

  function serieCom(porAno: Record<number, number>) {
    return serieDoAssunto(topico(porAno), resposta(anosITA, 20), 'ITA');
  }

  it('devolve null quando nenhuma série carregou', () => {
    expect(lerSerieDoAssunto('Trigonometria', [null, null])).toBeNull();
  });

  it('devolve null quando o assunto nunca caiu', () => {
    // A tela tem texto próprio para este caso, e ele explica que o vazio é
    // ausência de ocorrência, não falha de consulta.
    expect(lerSerieDoAssunto('Logaritmos', [serieCom({})])).toBeNull();
  });

  it('nomeia a banca e as duas janelas quando o assunto subiu', () => {
    const porAno: Record<number, number> = {};
    for (const ano of de(2016, 2020)) porAno[ano] = 1;
    for (const ano of de(2021, 2025)) porAno[ano] = 4;

    const frase = lerSerieDoAssunto('Trigonometria', [serieCom(porAno)]);

    expect(frase).toContain('No ITA');
    expect(frase).toContain('Trigonometria');
    expect(frase).toContain('subiu para');
    expect(frase).toContain('2016');
    expect(frase).toContain('2021');
  });

  it('não afirma tendência quando o acervo é curto', () => {
    const serie = serieDoAssunto(topico({ 2023: 2 }), resposta(de(2022, 2025), 20), 'ITA');
    const frase = lerSerieDoAssunto('Trigonometria', [serie]);

    expect(frase).toContain('2 questões');
    expect(frase).not.toContain('subiu');
    expect(frase).not.toContain('caiu para');
  });

  it('fala da banca com mais ocorrências, e nunca de uma série que não carregou', () => {
    // O IME não carregou (null). A frase não pode citá-lo — citá-lo seria
    // afirmar algo sobre uma série que ninguém leu.
    const porAno: Record<number, number> = {};
    for (const ano of de(2016, 2025)) porAno[ano] = 2;

    const frase = lerSerieDoAssunto('Trigonometria', [serieCom(porAno), null]);

    expect(frase).toContain('No ITA');
    expect(frase).not.toContain('IME');
  });
});

describe('rotuloDaSerie', () => {
  it('diz a leitura em palavras, com banca e período', () => {
    const serie = serieDoAssunto(
      topico({ 2019: 2, 2020: 1 }),
      resposta(de(2019, 2020), 20),
      'ITA',
    );
    const rotulo = rotuloDaSerie('Trigonometria', [serie]);

    expect(rotulo).toContain('Trigonometria');
    expect(rotulo).toContain('percentual da prova');
    expect(rotulo).toContain('ITA, 3 questões entre 2019 e 2020');
  });

  it('declara quando nenhuma série carregou', () => {
    expect(rotuloDaSerie('Trigonometria', [null])).toContain('nenhuma série carregou');
  });
});
