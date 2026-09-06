import { describe, expect, it } from 'vitest';
import {
  diasAte, estadoDoCiclo, resumirCiclos, resumirProvas, subtituloDeCiclos, subtituloDeProvas,
} from './provas';
import type { Ciclo, Simulado } from '../tipos/dominio';

function ciclo(p: Partial<Ciclo> & { id: string }): Ciclo {
  return {
    nome: p.id, ordem: 1, anoLetivo: 2026, vestibularAlvo: 'ITA',
    periodoInicio: '2026-08-14', periodoFim: '2026-09-26', simuladoIds: ['s1'],
    canvasEstado: null, canvasErro: null,
    ...p,
  } as Ciclo;
}

function prova(p: Partial<Simulado> & { id: string }): Simulado {
  return {
    nome: p.id, rotuloCurto: p.id, tipo: 'fase_1', materia: null,
    dataAplicacao: '2026-08-28', cicloId: 'C4', cicloOrdem: 4, vestibularAlvo: 'ITA',
    notaMaxima: 20, anulado: false, notaConfiavel: true, motivoNotaNaoConfiavel: null,
    origem: 'canvas', canvasEstado: 'sincronizado', canvasErro: null,
    media: 4.2, mediana: 4.1, desvioPadrao: 2.4, nPresentes: 380,
    ...p,
  } as Simulado;
}

const HOJE = '2026-09-05';

describe('diasAte', () => {
  it('conta dias de calendário, não fusos', () => {
    expect(diasAte('2026-09-11', HOJE)).toBe(6);
    expect(diasAte(HOJE, HOJE)).toBe(0);
    expect(diasAte('2026-09-01', HOJE)).toBe(-4);
  });

  // O motivo de `Date.UTC`: no domingo da virada do horário de verão um dos
  // dias tem 23 horas, e a divisão ingênua truncaria "7 dias" para 6.
  it('atravessa a virada do horário de verão sem perder um dia', () => {
    expect(diasAte('2026-10-25', '2026-10-18')).toBe(7);
  });
});

describe('estadoDoCiclo', () => {
  it('diz o prazo do ciclo aberto', () => {
    expect(estadoDoCiclo(ciclo({ id: 'C4' }), HOJE)).toBe('em andamento · fecha em 21 dias');
    expect(estadoDoCiclo(ciclo({ id: 'C4', periodoFim: '2026-09-05' }), HOJE))
      .toBe('em andamento · fecha hoje');
    expect(estadoDoCiclo(ciclo({ id: 'C4', periodoFim: '2026-09-06' }), HOJE))
      .toBe('em andamento · fecha amanhã');
  });

  it('separa encerrado de ainda por começar', () => {
    expect(estadoDoCiclo(
      ciclo({ id: 'C3', periodoInicio: '2026-06-02', periodoFim: '2026-07-18' }), HOJE,
    )).toBe('encerrado');
    expect(estadoDoCiclo(
      ciclo({ id: 'C5', periodoInicio: '2026-10-01', periodoFim: '2026-11-01' }), HOJE,
    )).toBe('começa em 26 dias');
  });

  it('ciclo sem prova nenhuma não finge ter prazo', () => {
    expect(estadoDoCiclo(ciclo({ id: 'C1', simuladoIds: [] }), HOJE)).toBe('sem prova');
  });

  // Ciclo sem período existe: o período vem do min/max das provas, e um ciclo
  // recém-criado ainda não tem nenhuma. Dizer "encerrado" ali seria afirmar o
  // que ninguém mediu.
  it('ciclo sem período devolve vazio, não um estado inventado', () => {
    expect(estadoDoCiclo(ciclo({ id: 'C0', periodoInicio: '', periodoFim: '' }), HOJE)).toBe('');
  });
});

describe('resumirCiclos + subtituloDeCiclos', () => {
  it('entre dois ciclos abertos, o que fecha primeiro é o que decide', () => {
    const r = resumirCiclos([
      ciclo({ id: 'ITA', periodoFim: '2026-09-26' }),
      ciclo({ id: 'IME', periodoFim: '2026-09-11' }),
    ], HOJE);
    expect(r.emAndamento?.id).toBe('IME');
    expect(r.diasParaFechar).toBe(6);
    expect(subtituloDeCiclos(r)).toBe('2 ciclos · IME em andamento, fecha em 6 dias');
  });

  it('sem ciclo aberto, confessa em vez de omitir', () => {
    const r = resumirCiclos([ciclo({ id: 'C3', periodoInicio: '2026-06-02', periodoFim: '2026-07-18' })], HOJE);
    expect(subtituloDeCiclos(r)).toBe('1 ciclo · nenhum em andamento');
  });

  // `null` é o estado VAZIO do card, não "0 ciclos": zero escrito parece
  // defeito de carregamento, e o card tem frase própria para o começo do ano.
  it('sem nenhum ciclo devolve null, nunca "0 ciclos"', () => {
    expect(subtituloDeCiclos(resumirCiclos([], HOJE))).toBeNull();
  });
});

describe('resumirProvas + subtituloDeProvas', () => {
  it('separa aplicada de agendada e conta as pendências', () => {
    const r = resumirProvas([
      prova({ id: 'P10' }),
      prova({ id: 'P11', media: null, mediana: null, nPresentes: 392 }),
      prova({ id: 'P12', canvasEstado: 'falhou' }),
      prova({ id: 'P13', dataAplicacao: '2026-09-12' }),
    ], HOJE);
    expect(r).toEqual({ total: 3, semNotaLancada: 1, falhouNoCanvas: 1, agendadas: 1 });
    expect(subtituloDeProvas(r))
      .toBe('3 provas · 1 agendada · 1 sem nota lançada · 1 falhou no Canvas');
  });

  // 'divergente' é ESCOLHA do coordenador, não falha — contá-la aqui encheria
  // o hub de um número que ninguém vai resolver (docs/18 §2.5).
  it('divergente não conta como falha no Canvas', () => {
    const r = resumirProvas([prova({ id: 'P9', canvasEstado: 'divergente' })], HOJE);
    expect(r.falhouNoCanvas).toBe(0);
    expect(subtituloDeProvas(r)).toBe('1 prova');
  });

  it('a prova do próprio dia já é aplicada', () => {
    expect(resumirProvas([prova({ id: 'P20', dataAplicacao: HOJE })], HOJE).total).toBe(1);
  });

  it('sem prova nenhuma devolve null', () => {
    expect(subtituloDeProvas(resumirProvas([], HOJE))).toBeNull();
  });

  // Colégio no começo do ano com a primeira prova já marcada: o card não pode
  // cair no vazio "nenhuma prova agendada nem aplicada", que seria falso.
  it('só agendadas ainda é dado vivo', () => {
    const r = resumirProvas([prova({ id: 'P1', dataAplicacao: '2026-09-30' })], HOJE);
    expect(subtituloDeProvas(r)).toBe('1 agendada');
  });
});
