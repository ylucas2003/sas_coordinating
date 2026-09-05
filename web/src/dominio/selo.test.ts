import { describe, expect, it } from 'vitest';

import { formatarDistancia, piorDistancia, seloDaNota } from './selo';

describe('seloDaNota', () => {
  it('preenche acima do corte e vaza abaixo (R1)', () => {
    expect(seloDaNota(8.7, 4).estado).toBe('acima');
    expect(seloDaNota(3.6, 4).estado).toBe('abaixo');
  });

  it('trata a nota exatamente no corte como aprovada', () => {
    // O corte é o MÍNIMO que a régua exige. 4,0 contra corte 4,0 passou.
    const selo = seloDaNota(4, 4);
    expect(selo.estado).toBe('no-corte');
    expect(selo.etiqueta).toBe('');
    expect(selo.intensidade).toBe(0);
  });

  it('cresce a intensidade com a distância, nos dois sentidos (R3)', () => {
    // É o que devolve o contínuo que os três baldes jogavam fora: 3,9 e 0,4
    // eram o mesmo vermelho.
    expect(seloDaNota(3.9, 4).intensidade).toBeLessThan(seloDaNota(0.4, 4).intensidade);
    expect(seloDaNota(5.2, 4).intensidade).toBeLessThan(seloDaNota(8.7, 4).intensidade);
  });

  it('normaliza cada lado pelo espaço que ele tem', () => {
    // Corte 4: acima sobram 6 pontos, abaixo sobram 4. Encostar no corte tem
    // de parecer igual dos dois lados.
    expect(seloDaNota(10, 4).intensidade).toBe(1);
    expect(seloDaNota(0, 4).intensidade).toBe(1);
    expect(seloDaNota(4.6, 4).intensidade).toBeCloseTo(0.1, 5);
    expect(seloDaNota(3.6, 4).intensidade).toBeCloseTo(0.1, 5);
  });

  it('satura em 1 e não passa disso', () => {
    expect(seloDaNota(12, 4).intensidade).toBe(1);
    expect(seloDaNota(-2, 4).intensidade).toBe(1);
  });

  it('respeita o corte eliminatório de 5,0 do Inglês da F1 do ITA (R2)', () => {
    // A mesma nota, lida contra duas réguas: 4,6 passa no corte genérico e
    // reprova no Inglês. Um escalar único mentiria sobre a matéria que mais
    // elimina.
    expect(seloDaNota(4.6, 4).estado).toBe('acima');
    expect(seloDaNota(4.6, 5).estado).toBe('abaixo');
    expect(seloDaNota(4.6, 5).etiqueta).toBe('−0,4');
  });

  it('etiqueta só abaixo do corte, e é o único vermelho da tela (R4)', () => {
    expect(seloDaNota(3.6, 4).etiqueta).toBe('−0,4');
    expect(seloDaNota(8.7, 4).etiqueta).toBe('');
  });

  it('fica sem dado quando falta a nota ou falta a régua', () => {
    // Sem corte não há régua, e não há nada honesto a desenhar. Neutro, nunca
    // "aprovado".
    expect(seloDaNota(null, 4).estado).toBe('sem-dado');
    expect(seloDaNota(undefined, 4).estado).toBe('sem-dado');
    expect(seloDaNota(7, null).estado).toBe('sem-dado');
    expect(seloDaNota(Number.NaN, 4).estado).toBe('sem-dado');
    expect(seloDaNota(null, 4).distancia).toBeNull();
  });

  it('não confunde zero com ausência de nota', () => {
    // No domínio são coisas diferentes, e a interface nunca pode misturá-las.
    expect(seloDaNota(0, 4).estado).toBe('abaixo');
    expect(seloDaNota(0, 4).distancia).toBe(-4);
    expect(seloDaNota(null, 4).estado).toBe('sem-dado');
  });
});

describe('formatarDistancia', () => {
  it('usa vírgula decimal e o menos U+2212', () => {
    expect(formatarDistancia(-1.4)).toBe('−1,4');
    expect(formatarDistancia(-1.4).charCodeAt(0)).toBe(0x2212);
  });

  it('põe sinal explícito também no positivo', () => {
    expect(formatarDistancia(2)).toBe('+2,0');
    expect(formatarDistancia(0)).toBe('+0,0');
  });
});

describe('piorDistancia', () => {
  it('devolve a matéria mais abaixo do corte', () => {
    expect(
      piorDistancia([
        { nota: 8.7, corte: 4 },
        { nota: 2.4, corte: 4 },
        { nota: 5.0, corte: 4 },
      ]),
    ).toBeCloseTo(-1.6, 5);
  });

  it('mede contra o corte DE CADA MATÉRIA, não contra o majoritário', () => {
    // Inglês 4,6 contra corte 5,0 é −0,4 e é o pior do aluno, embora seja a
    // maior nota da lista contra o corte genérico de 4,0.
    expect(
      piorDistancia([
        { nota: 4.5, corte: 4 },
        { nota: 4.6, corte: 5 },
      ]),
    ).toBeCloseTo(-0.4, 5);
  });

  it('é positiva quando o aluno passou em tudo', () => {
    const d = piorDistancia([
      { nota: 6, corte: 4 },
      { nota: 9, corte: 4 },
    ]);
    expect(d).toBeCloseTo(2, 5);
  });

  it('ignora matéria sem nota em vez de contá-la como zero', () => {
    expect(
      piorDistancia([
        { nota: null, corte: 4 },
        { nota: 6, corte: 4 },
      ]),
    ).toBeCloseTo(2, 5);
  });

  it('devolve null quando não há nenhuma nota com régua', () => {
    // Aluno sem dado não é aluno em risco: ele não foi mal, não foi medido.
    expect(piorDistancia([])).toBeNull();
    expect(piorDistancia([{ nota: null, corte: 4 }])).toBeNull();
    expect(piorDistancia([{ nota: 7, corte: null }])).toBeNull();
  });
});
