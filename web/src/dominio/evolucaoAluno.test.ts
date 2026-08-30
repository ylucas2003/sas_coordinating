import { describe, expect, it } from 'vitest';
import { decidirCorte, montarEixoCiclos, montarSeries } from './evolucaoAluno';
import { FILTRO_VAZIO, rotuloCiclo } from './simulados';
import type { FiltroSimulados } from './simulados';
import type { CriterioClassificacao, Simulado } from '../tipos/dominio';

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

/**
 * A régua vem do servidor. Este bloco testava a regra em si — "Inglês F1 no
 * ITA é corte 5" — e por isso guardava dois números errados: a régua da casa
 * põe o inglês em 4,0 e o ITA pede 5 de 12, que é 4,17. O que se testa agora é
 * a ESCOLHA: qual dos cortes que o servidor resolveu se aplica ao recorte.
 */
const REGUA_DA_CASA: CriterioClassificacao = {
  slug: 'tio-leo', nome: 'Tio Leo', descricao: '', fase: null,
  combinador: 'todos', desempate: [], predicados: [],
  cortes: { matematica: 4, fisica: 4, quimica: 4, portugues: 4, ingles: 4, redacao: 4 },
  corteGenerico: 4, corteMedia: 5, eliminatorias: ['ingles'],
};

const REGUA_ITA_F1: CriterioClassificacao = {
  slug: 'ita-f1', nome: 'ITA — Fase 1', descricao: '', fase: 1,
  combinador: 'algum', desempate: [], predicados: [],
  cortes: { matematica: 5 / 12 * 10, fisica: 5 / 12 * 10, ingles: 5 / 12 * 10 },
  corteGenerico: null, corteMedia: 5, eliminatorias: [],
};

describe('decidirCorte', () => {
  it('sem régua carregada não desenha linha nenhuma', () => {
    expect(decidirCorte(FILTRO_VAZIO, null)).toBeNull();
  });

  it('com uma matéria selecionada, usa o corte daquela matéria', () => {
    const r = decidirCorte(filtro({ materias: new Set(['ingles']) }), REGUA_DA_CASA);
    expect(r).toEqual({ valor: 4, rotulo: 'corte 4,0 (eliminatório)' });
  });

  it('marca eliminatório só onde a régua diz que é', () => {
    expect(decidirCorte(filtro({ materias: new Set(['matematica']) }), REGUA_DA_CASA)!.rotulo)
      .toBe('corte 4,0');
    // A mesma matéria, sob outra régua, não é eliminatória.
    expect(decidirCorte(filtro({ materias: new Set(['ingles']) }), REGUA_ITA_F1)!.rotulo)
      .toBe('corte 4,2');
  });

  it('sem matéria nenhuma, as séries são médias por ciclo — corte da média', () => {
    expect(decidirCorte(FILTRO_VAZIO, REGUA_DA_CASA)!.valor).toBe(5);
  });

  it('com VÁRIAS matérias, o corte é o genérico e não o da média', () => {
    // Cada série é uma matéria com notas individuais, não uma média: desenhar
    // a exigência de média (5,0) sobre elas põe abaixo do corte um 4,5 que a
    // régua aprova. A primeira versão desta função fazia isso, e este teste
    // consagrava o erro em vez de pegá-lo.
    expect(decidirCorte(
      filtro({ materias: new Set(['ingles', 'matematica']) }), REGUA_DA_CASA,
    )!.valor).toBe(4);
  });

  it('matéria que a régua não cobra cai no genérico, e depois na média', () => {
    expect(decidirCorte(filtro({ materias: new Set(['redacao']) }), REGUA_DA_CASA)!.valor).toBe(4);
    // A régua do ITA F1 não tem Português nem predicado "qualquer disciplina".
    expect(decidirCorte(filtro({ materias: new Set(['portugues']) }), REGUA_ITA_F1)!.valor).toBe(5);
  });

  it('a régua manda: trocar de critério move a linha', () => {
    const casa = decidirCorte(filtro({ materias: new Set(['matematica']) }), REGUA_DA_CASA)!;
    const ita = decidirCorte(filtro({ materias: new Set(['matematica']) }), REGUA_ITA_F1)!;
    expect(casa.valor).toBe(4);
    expect(ita.valor).toBeCloseTo(4.1667, 3);
  });
});

describe('montarSeries · ordem cronológica', () => {
  // `GET /simulados` ordena por data DESCENDENTE. O gráfico escapava porque
  // `LinhaEvolucao` reordena por cicloOrdem antes de desenhar; a frase da
  // camada leigo lia o array cru e dizia "subiu" quando o aluno caiu.
  const desc = [
    sim({ id: 'S3', cicloOrdem: 3, materia: MAT, dataAplicacao: '2026-05-01' }),
    sim({ id: 'S2', cicloOrdem: 2, materia: MAT, dataAplicacao: '2026-04-01' }),
    sim({ id: 'S1', cicloOrdem: 1, materia: MAT, dataAplicacao: '2026-03-01' }),
  ];
  const notas = new Map([['S3', 4], ['S2', 6], ['S1', 8]]);

  it('ordena por ciclo mesmo recebendo do mais novo para o mais antigo', () => {
    const [serie] = montarSeries(desc, notas, filtro({ materias: new Set(['matematica']) }));
    expect(serie.pontos.map((p) => p.cicloOrdem)).toEqual([1, 2, 3]);
    expect(serie.pontos.map((p) => p.nota)).toEqual([8, 6, 4]);
  });

  it('a linha agregada também sai em ordem', () => {
    const [serie] = montarSeries(desc, notas, FILTRO_VAZIO);
    expect(serie.pontos.map((p) => p.cicloOrdem)).toEqual([1, 2, 3]);
  });

  it('empate de ciclo desempata pela data', () => {
    const mesmoCiclo = [
      sim({ id: 'B', cicloOrdem: 1, materia: MAT, dataAplicacao: '2026-03-20' }),
      sim({ id: 'A', cicloOrdem: 1, materia: MAT, dataAplicacao: '2026-03-01' }),
    ];
    const [serie] = montarSeries(
      mesmoCiclo, new Map([['B', 5], ['A', 9]]),
      filtro({ materias: new Set(['matematica']) }),
    );
    expect(serie.pontos.map((p) => p.simuladoId)).toEqual(['A', 'B']);
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
