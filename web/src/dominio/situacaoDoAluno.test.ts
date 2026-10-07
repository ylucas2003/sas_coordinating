import { describe, expect, it } from 'vitest';
import { estaAusente, filtrarPorSituacao, provasQueContam } from './situacaoDoAluno';
import type { ClassificacaoPorAluno, ColunaPainel, NotasPorAluno } from './painel';
import type { Aluno, Simulado } from '../tipos/dominio';

const HOJE = '2026-09-30';

function prova(id: string, extra: Partial<Simulado> = {}): Simulado {
  return { id, dataAplicacao: '2026-09-20', anulado: false, ...extra } as Simulado;
}

function coluna(sim: Simulado | null, extra: Partial<ColunaPainel> = {}): ColunaPainel {
  return { id: sim?.id ?? 'x', virtual: false, sim, ...extra } as ColunaPainel;
}

const aluno = (id: string) => ({ id, nome: id }) as Aluno;

const MAT = prova('mat');
const FIS = prova('fis');

describe('provasQueContam', () => {
  it('fica só com prova real, aplicada e não anulada', () => {
    const colunas = [
      coluna(MAT),
      coluna(prova('futura', { dataAplicacao: '2026-10-05' })),
      coluna(prova('anulada', { anulado: true })),
      coluna(prova('semData', { dataAplicacao: '' })),
      coluna(null), // a coluna existe no esquema, a prova não existe no ciclo
      coluna(prova('media'), { virtual: true }),
    ];
    expect(provasQueContam(colunas, HOJE).map((p) => p.id)).toEqual(['mat']);
  });

  // Sem isso, num ciclo em andamento todo aluno seria "ausente" da prova de
  // semana que vem.
  it('a prova de hoje já conta', () => {
    const colunas = [coluna(prova('hoje', { dataAplicacao: HOJE }))];
    expect(provasQueContam(colunas, HOJE)).toHaveLength(1);
  });
});

describe('estaAusente', () => {
  const provas = [MAT, FIS];

  it('quem tem nota acima de zero em todas está presente', () => {
    const notas: NotasPorAluno = { a: { mat: 3.3, fis: 0.8 } };
    expect(estaAusente('a', provas, notas)).toBe(false);
  });

  it('quem zerou é ausente — é a regra da coordenação', () => {
    expect(estaAusente('a', provas, { a: { mat: 5, fis: 0 } })).toBe(true);
  });

  it('nota que não entrou na conta (em branco, não computável) é ausência', () => {
    // `buildNotasAluno` não põe no mapa a nota não computável: a célula sai hachurada.
    expect(estaAusente('a', provas, { a: { mat: 5 } })).toBe(true);
  });

  it('aluno que nem aparece no mapa faltou a tudo', () => {
    expect(estaAusente('fantasma', provas, {})).toBe(true);
  });

  it('nota pequena mas acima de zero é presença, não falta', () => {
    expect(estaAusente('a', provas, { a: { mat: 0.1, fis: 0.1 } })).toBe(false);
  });
});

describe('filtrarPorSituacao', () => {
  const alunos = ['cortadoPresente', 'cortadoZerou', 'passouPresente', 'passouFaltou', 'semNota']
    .map(aluno);

  const classificacao = {
    cortadoPresente: { aprovado: false },
    cortadoZerou: { aprovado: false },
    passouPresente: { aprovado: true },
    passouFaltou: { aprovado: true },
    // `semNota` fica de fora, como no servidor: quem não tem nota não é classificado.
  } as unknown as ClassificacaoPorAluno;

  const notasAluno: NotasPorAluno = {
    cortadoPresente: { mat: 1, fis: 2 },
    cortadoZerou: { mat: 0, fis: 0 },
    passouPresente: { mat: 7, fis: 8 },
    passouFaltou: { mat: 7 },
    semNota: {},
  };

  const base = { classificacao, provas: [MAT, FIS], notasAluno };
  const ids = (lista: Aluno[]) => lista.map((a) => a.id);

  it('sem recorte devolve todo mundo, na mesma ordem', () => {
    expect(ids(filtrarPorSituacao(alunos, { ...base, corte: null, presenca: null }))).toEqual(
      ['cortadoPresente', 'cortadoZerou', 'passouPresente', 'passouFaltou', 'semNota'],
    );
  });

  it('cortados: só quem a régua cortou', () => {
    expect(ids(filtrarPorSituacao(alunos, { ...base, corte: 'cortados', presenca: null }))).toEqual(
      ['cortadoPresente', 'cortadoZerou'],
    );
  });

  // Quem não tem nota não foi "aprovado": a régua só devolve "aprovado" para
  // ele por falta de dado, e contá-lo aqui inflaria a lista de quem passou.
  it('não cortados: só quem tem veredito e passou', () => {
    expect(ids(filtrarPorSituacao(alunos, { ...base, corte: 'nao-cortados', presenca: null }))).toEqual(
      ['passouPresente', 'passouFaltou'],
    );
  });

  it('ausentes: zerou, faltou a alguma ou não tem nota', () => {
    expect(ids(filtrarPorSituacao(alunos, { ...base, corte: null, presenca: 'ausentes' }))).toEqual(
      ['cortadoZerou', 'passouFaltou', 'semNota'],
    );
  });

  it('presentes: fez todas as provas com nota acima de zero', () => {
    expect(ids(filtrarPorSituacao(alunos, { ...base, corte: null, presenca: 'presentes' }))).toEqual(
      ['cortadoPresente', 'passouPresente'],
    );
  });

  // O uso que motiva os dois eixos: quem foi cortado por desempenho, não por faltar.
  it('cortados E presentes isola o corte por desempenho', () => {
    expect(ids(filtrarPorSituacao(alunos, { ...base, corte: 'cortados', presenca: 'presentes' }))).toEqual(
      ['cortadoPresente'],
    );
  });

  it('cortados E ausentes mostra quem o zero cortou', () => {
    expect(ids(filtrarPorSituacao(alunos, { ...base, corte: 'cortados', presenca: 'ausentes' }))).toEqual(
      ['cortadoZerou'],
    );
  });

  it('sem nenhuma prova aplicada, presença não é definida para ninguém', () => {
    const semProvas = { ...base, provas: [] };
    expect(filtrarPorSituacao(alunos, { ...semProvas, corte: null, presenca: 'ausentes' })).toEqual([]);
    expect(filtrarPorSituacao(alunos, { ...semProvas, corte: null, presenca: 'presentes' })).toEqual([]);
  });

  it('não muda a lista recebida', () => {
    const copia = alunos.slice();
    filtrarPorSituacao(alunos, { ...base, corte: 'cortados', presenca: 'presentes' });
    expect(alunos).toEqual(copia);
  });
});
