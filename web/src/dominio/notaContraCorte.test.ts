import { describe, expect, it } from 'vitest';

import { LEGENDA_DAS_NOTAS, NOME_DA_MEDIA_DA_ZONA, notasContraCorte } from './notaContraCorte';

// A régua de `/me/zona`: o corte e a nota QUE CONTA NA RÉGUA, por matéria.
const REGUA = [
  { materia: 'Física', nota: 4.6, corte: 4, eliminatoria: false },
  { materia: 'Matemática', nota: 4.75, corte: 4, eliminatoria: false },
  { materia: 'Inglês', nota: 6, corte: 5, eliminatoria: true },
];

describe('notasContraCorte', () => {
  it('com a evolução, mostra a nota do último simulado, com esse nome', () => {
    // O caso visto no browser em 26/10: Física 4,3 e Matemática 5,0 no último
    // ciclo, contra 4,6 e 4,75 na régua.
    const { materias, notas } = notasContraCorte(REGUA, {
      materias: {
        'Física': { aluno: [5.1, null, 4.3] },
        'Matemática': { aluno: [3.9, 5, null] },
        'Inglês': { aluno: [7, 6.5, 8] },
      },
    });
    expect(notas).toBe('ultimo-simulado');
    expect(materias.map((m) => [m.materia, m.nota])).toEqual([
      ['Física', 4.3],
      ['Matemática', 5],
      ['Inglês', 8],
    ]);
  });

  it('o corte e a eliminatória continuam os da régua: só a nota muda de fonte', () => {
    const { materias } = notasContraCorte(REGUA, { materias: { 'Inglês': { aluno: [4] } } });
    expect(materias).toEqual([{ materia: 'Inglês', nota: 4, corte: 5, eliminatoria: true }]);
  });

  it('matéria sem nota na evolução sai, em vez de cair na nota da régua', () => {
    // Misturar as duas notas sob o nome "no último simulado" é o defeito que a
    // regra existe para evitar.
    const { materias, notas } = notasContraCorte(REGUA, {
      materias: { 'Física': { aluno: [null, 4.3] }, 'Matemática': { aluno: [null, null] } },
    });
    expect(notas).toBe('ultimo-simulado');
    expect(materias.map((m) => m.materia)).toEqual(['Física']);
  });

  it('sem a evolução, mostra a lista da régua como veio, e com o nome DELA', () => {
    for (const ausente of [undefined, null]) {
      const { materias, notas } = notasContraCorte(REGUA, ausente);
      expect(notas).toBe('regua');
      expect(materias).toEqual(REGUA);
    }
  });

  it('não mexe na lista que recebeu', () => {
    const copia = REGUA.map((m) => ({ ...m }));
    notasContraCorte(REGUA, { materias: { 'Física': { aluno: [1] } } });
    expect(REGUA).toEqual(copia);
  });

  it('sem a régua, não há barra', () => {
    expect(notasContraCorte(undefined, { materias: {} }).materias).toEqual([]);
  });

  it('cada nota diz o que é, com o nome decidido em 26/10', () => {
    expect(LEGENDA_DAS_NOTAS['ultimo-simulado']).toBe('Notas no último simulado');
    expect(LEGENDA_DAS_NOTAS.regua).toBe('Notas que contam na régua');
  });

  it('a média da zona leva o nome das notas da régua, e não o do último simulado', () => {
    // A média de `/me/zona` sai das mesmas notas que o cartão do Tio Léo
    // mostra: os dois nomes andam juntos.
    expect(NOME_DA_MEDIA_DA_ZONA).toBe('média que conta na régua');
    expect(NOME_DA_MEDIA_DA_ZONA).toContain('na régua');
    expect(LEGENDA_DAS_NOTAS.regua).toContain('na régua');
    expect(NOME_DA_MEDIA_DA_ZONA).not.toContain('último simulado');
  });
});
