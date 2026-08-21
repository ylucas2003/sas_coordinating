import { describe, expect, it } from 'vitest';
import {
  FILTRO_VAZIO, aplicarFiltros, contarPorChip, datasDoCalendario, montarOpcoes, rotuloCiclo,
} from './simulados';
import type { FiltroSimulados } from './simulados';
import type { Simulado } from '../tipos/dominio';

function sim(p: Partial<Simulado> & { id: string }): Simulado {
  return {
    nome: p.id, rotuloCurto: p.id, tipo: 'fase_1', materia: null,
    dataAplicacao: '2026-03-01', cicloId: 'C1', cicloOrdem: 1, vestibularAlvo: 'ITA',
    notaMaxima: 10, anulado: false, origem: 'canvas', canvasEstado: 'sincronizado',
    canvasErro: null, media: null, mediana: null, desvioPadrao: null, nPresentes: null,
    ...p,
  } as Simulado;
}

const MAT = { codigo: 'MAT', nome: 'Matemática' };
const FIS = { codigo: 'FIS', nome: 'Física' };

const DADOS: Simulado[] = [
  sim({ id: 'S1', cicloOrdem: 1, materia: MAT, tipo: 'fase_1', vestibularAlvo: 'ITA', dataAplicacao: '2026-03-01' }),
  sim({ id: 'S2', cicloOrdem: 1, materia: FIS, tipo: 'fase_2', vestibularAlvo: 'ITA', dataAplicacao: '2026-03-08' }),
  sim({ id: 'S3', cicloOrdem: 2, materia: MAT, tipo: 'fase_1', vestibularAlvo: 'IME', dataAplicacao: '2026-04-05' }),
];

const filtro = (p: Partial<FiltroSimulados>): FiltroSimulados => ({ ...FILTRO_VAZIO, ...p });
const ids = (ss: Simulado[]) => ss.map((s) => s.id);

describe('aplicarFiltros', () => {
  it('sem filtro devolve tudo', () => {
    expect(ids(aplicarFiltros(DADOS, FILTRO_VAZIO))).toEqual(['S1', 'S2', 'S3']);
  });

  it('faz OR dentro da categoria', () => {
    expect(ids(aplicarFiltros(DADOS, filtro({ materias: new Set(['MAT', 'FIS']) }))))
      .toEqual(['S1', 'S2', 'S3']);
  });

  it('faz AND entre categorias', () => {
    expect(ids(aplicarFiltros(DADOS, filtro({
      materias: new Set(['MAT']),
      vestibulares: new Set(['ITA']),
    })))).toEqual(['S1']);
  });

  it('filtra por data', () => {
    expect(ids(aplicarFiltros(DADOS, filtro({ datas: new Set(['2026-04-05']) })))).toEqual(['S3']);
  });
});

describe('contarPorChip', () => {
  it('conta cada eixo ignorando o próprio filtro', () => {
    // Com ITA marcado, o eixo Vestibular ainda mostra IME — senão o usuário
    // não veria que existe algo a ganhar marcando IME também.
    const c = contarPorChip(DADOS, filtro({ vestibulares: new Set(['ITA']) }));
    expect(c.vestibular.get('ITA')).toBe(2);
    expect(c.vestibular.get('IME')).toBe(1);
    // Já os OUTROS eixos respeitam o filtro de vestibular.
    expect(c.materia.get('MAT')).toBe(1);
    expect(c.materia.get('FIS')).toBe(1);
  });
});

describe('montarOpcoes', () => {
  it('ordena ciclos por ordem e matérias por nome', () => {
    const o = montarOpcoes(DADOS);
    expect(o.ciclos.map((c) => c.label)).toEqual(['C1 · ITA', 'C2 · IME']);
    expect(o.materias.map((m) => m.nome)).toEqual(['Física', 'Matemática']);
    expect(o.vestibulares).toEqual(['IME', 'ITA']);
  });
});

describe('datasDoCalendario', () => {
  // O filtro de data não pode anular a si mesmo: com 05/04 marcado, as outras
  // datas continuam clicáveis, senão não haveria como trocar de seleção.
  it('ignora o próprio filtro de data', () => {
    const datas = datasDoCalendario(DADOS, filtro({ datas: new Set(['2026-04-05']) }));
    expect([...datas].sort()).toEqual(['2026-03-01', '2026-03-08', '2026-04-05']);
  });

  it('respeita os demais filtros', () => {
    const datas = datasDoCalendario(DADOS, filtro({ vestibulares: new Set(['IME']) }));
    expect([...datas]).toEqual(['2026-04-05']);
  });
});

describe('rotuloCiclo', () => {
  it('compõe ordem e vestibular', () => {
    expect(rotuloCiclo(3, 'ITA')).toBe('C3 · ITA');
    expect(rotuloCiclo(3, null)).toBe('C3');
    expect(rotuloCiclo(null, 'ITA')).toBe('Sem ciclo');
  });
});
