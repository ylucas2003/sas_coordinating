import { describe, expect, it } from 'vitest';
import { decidirCorte, montarEixoCiclos, montarSeries } from './evolucaoAluno';
import { FILTRO_VAZIO, rotuloCiclo } from './simulados';
import type { FiltroSimulados } from './simulados';
import type { Simulado } from '../tipos/dominio';

function sim(p: Partial<Simulado> & { id: string }): Simulado {
  return {
    nome: p.id, rotuloCurto: p.id, tipo: 'fase_1', materia: null,
    dataAplicacao: '2026-03-01', cicloId: 'C1', cicloOrdem: 1, vestibularAlvo: 'ITA',
    notaMaxima: 10, anulado: false, origem: 'canvas', canvasEstado: 'sincronizado',
    canvasErro: null, media: 5, mediana: null, desvioPadrao: null, nPresentes: null,
    ...p,
  } as Simulado;
}

const MAT = { codigo: 'matematica', nome: 'Matemática' };
const ING = { codigo: 'ingles', nome: 'Inglês' };

const filtro = (p: Partial<FiltroSimulados>): FiltroSimulados => ({ ...FILTRO_VAZIO, ...p });

describe('decidirCorte', () => {
  // A regra do domínio: Inglês F1 no ITA é eliminatório com corte 5.
  it('usa corte 5 só quando o recorte é exatamente Inglês + ITA + F1', () => {
    expect(decidirCorte(filtro({
      materias: new Set(['ingles']),
      vestibulares: new Set(['ITA']),
      fases: new Set(['fase_1']),
    }))).toEqual({ valor: 5, rotulo: 'corte 5 (eliminatório)' });
  });

  it('usa corte 4 em qualquer outro recorte', () => {
    expect(decidirCorte(FILTRO_VAZIO).valor).toBe(4);
    // Inglês + ITA mas sem recortar a fase: pode incluir F2, que não é eliminatória.
    expect(decidirCorte(filtro({
      materias: new Set(['ingles']),
      vestibulares: new Set(['ITA']),
    })).valor).toBe(4);
    // Inglês + F1 mas incluindo IME.
    expect(decidirCorte(filtro({
      materias: new Set(['ingles']),
      fases: new Set(['fase_1']),
    })).valor).toBe(4);
    // Duas matérias selecionadas.
    expect(decidirCorte(filtro({
      materias: new Set(['ingles', 'matematica']),
      vestibulares: new Set(['ITA']),
      fases: new Set(['fase_1']),
    })).valor).toBe(4);
  });
});

describe('montarSeries', () => {
  const simulados = [
    sim({ id: 'S1', cicloOrdem: 1, materia: MAT, media: 5 }),
    sim({ id: 'S2', cicloOrdem: 1, materia: ING, media: 6 }),
    sim({ id: 'S3', cicloOrdem: 2, materia: MAT, media: 7 }),
  ];
  const notas = new Map([['S1', 4], ['S2', 8], ['S3', 6]]);

  it('sem filtro de matéria agrega numa linha só, média por ciclo', () => {
    const series = montarSeries(simulados, notas, FILTRO_VAZIO);
    expect(series).toHaveLength(1);
    expect(series[0].nome).toBe('Média do aluno por ciclo');
    // Ciclo 1: (4 + 8) / 2 = 6. Ciclo 2: 6.
    expect(series[0].pontos.map((p) => [p.cicloOrdem, p.nota])).toEqual([[1, 6], [2, 6]]);
    // Média da turma agregada igual: (5 + 6) / 2 = 5,5.
    expect(series[0].pontos[0].mediaTurma).toBe(5.5);
  });

  it('com filtro de matéria gera uma linha por matéria, em ordem alfabética', () => {
    const series = montarSeries(simulados, notas, filtro({ materias: new Set(['matematica', 'ingles']) }));
    expect(series.map((s) => s.nome)).toEqual(['Inglês', 'Matemática']);
    expect(series[1].pontos.map((p) => p.nota)).toEqual([4, 6]);
  });

  it('ignora simulados sem nota do aluno', () => {
    const series = montarSeries(simulados, new Map([['S1', 4]]), FILTRO_VAZIO);
    expect(series[0].pontos).toHaveLength(1);
  });

  // Zero com presença marcada é quase sempre abandono, não desempenho.
  it('marca nota 0 como provável abandono nas séries por matéria', () => {
    const series = montarSeries(simulados, new Map([['S1', 0]]), filtro({ materias: new Set(['matematica']) }));
    expect(series[0].pontos[0].abandonoProvavel).toBe(true);
  });

  it('só reporta a fase do ciclo agregado quando ela é única', () => {
    const misto = [
      sim({ id: 'A', cicloOrdem: 1, tipo: 'fase_1' }),
      sim({ id: 'B', cicloOrdem: 1, tipo: 'fase_2' }),
    ];
    const um = montarSeries([misto[0]], new Map([['A', 5]]), FILTRO_VAZIO);
    expect(um[0].pontos[0].tipo).toBe('fase_1');

    const dois = montarSeries(misto, new Map([['A', 5], ['B', 7]]), FILTRO_VAZIO);
    expect(dois[0].pontos[0].tipo).toBeNull();
  });
});

describe('montarEixoCiclos', () => {
  it('ordena por ordem do ciclo e rotula com o vestibular', () => {
    const eixo = montarEixoCiclos(
      [sim({ id: 'S3', cicloOrdem: 3, vestibularAlvo: 'IME' }), sim({ id: 'S1', cicloOrdem: 1, vestibularAlvo: 'ITA' })],
      rotuloCiclo,
    );
    expect(eixo).toEqual([
      { ordem: 1, label: 'C1 · ITA' },
      { ordem: 3, label: 'C3 · IME' },
    ]);
  });
});
