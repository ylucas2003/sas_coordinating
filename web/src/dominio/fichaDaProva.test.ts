import { describe, expect, it } from 'vitest';

import {
  acertosEmPalavras,
  condicoesDaProva,
  contextoDaProva,
  dataPorExtenso,
  fichaVazia,
  identidadeDaProva,
  pontuacaoBruta,
} from './fichaDaProva';
import type { NotaSimulado, Simulado } from '../tipos/dominio';

const HOJE = '2026-09-05';

function prova(patch: Partial<Simulado> = {}): Simulado {
  return {
    id: 'S1',
    nome: 'C4_P8 - Física - 2026-09-04',
    rotuloCurto: 'P8',
    tipo: 'fase_1',
    materia: { codigo: 'FIS', nome: 'Física' },
    dataAplicacao: '2026-09-04',
    cicloId: 'C4',
    cicloOrdem: 4,
    vestibularAlvo: 'ITA',
    notaMaxima: 20,
    anulado: false,
    notaConfiavel: true,
    motivoNotaNaoConfiavel: null,
    origem: 'canvas',
    canvasEstado: 'sincronizado',
    canvasErro: null,
    media: 4.2,
    mediana: 4,
    desvioPadrao: 1.4,
    nPresentes: 380,
    ...patch,
  };
}

function nota(patch: Partial<NotaSimulado> = {}): NotaSimulado {
  return { alunoId: 'A1', nome: 'Ana Beatriz Correia', pontuacao: 4.5, presente: true, ...patch };
}

describe('dataPorExtenso', () => {
  it('não passa por Date — o fuso negativo devolveria o dia anterior', () => {
    expect(dataPorExtenso('2026-09-04')).toBe('04/09/2026');
  });
});

describe('identidadeDaProva', () => {
  it('monta das colunas estruturadas, não do nome do Canvas', () => {
    expect(identidadeDaProva(prova())).toBe('P8 · Física · Fase 1');
  });

  it('cai no nome do Canvas quando não há coluna nenhuma', () => {
    const p = prova({ rotuloCurto: null, materia: null, tipo: null, nome: 'Prova avulsa' });
    expect(identidadeDaProva(p)).toBe('Prova avulsa');
  });
});

describe('contextoDaProva', () => {
  it('omite o que o servidor não disse, em vez de escrever zero', () => {
    const texto = contextoDaProva(prova({ nPresentes: null }), null, HOJE);
    expect(texto).toBe('Ciclo 4 · ITA · aplicado em 04/09/2026');
    expect(texto).not.toContain('0 ausentes');
  });

  it('conjuga o verbo pela data: o que ainda não aconteceu é previsto', () => {
    const p = prova({ dataAplicacao: '2026-09-19', nPresentes: null });
    expect(contextoDaProva(p, null, HOJE)).toContain('previsto para 19/09/2026');
  });

  it('conta ausentes quando o histograma sabe quantos são', () => {
    expect(contextoDaProva(prova(), 12, HOJE)).toContain('380 presentes · 12 ausentes');
  });
});

describe('pontuacaoBruta e acertosEmPalavras', () => {
  it('desfaz a escala 0–10 contra o número de questões', () => {
    expect(pontuacaoBruta(nota({ pontuacao: 4.5 }), 20)).toBe(9);
    expect(acertosEmPalavras(nota({ pontuacao: 4.5 }), 20)).toBe('9 de 20');
  });

  it('não inventa zero para quem faltou nem para prova sem nota máxima', () => {
    expect(pontuacaoBruta(nota({ presente: false, pontuacao: null }), 20)).toBeNull();
    expect(acertosEmPalavras(nota(), null)).toBeNull();
  });
});

describe('condicoesDaProva', () => {
  it('prova vinda do Canvas não tem nada a enviar de volta', () => {
    expect(condicoesDaProva(prova({ origem: 'canvas', canvasEstado: 'divergente' }))).toEqual([]);
  });

  it('divergente oferece enviar, e isso não é falha', () => {
    const [c] = condicoesDaProva(prova({ origem: 'sas', canvasEstado: 'divergente' }));
    expect(c.acao).toBe('enviar-canvas');
    expect(c.falha).toBe(false);
  });

  it('falhou é a única condição em alerta, e usa o erro do servidor como motivo', () => {
    const p = prova({ origem: 'sas', canvasEstado: 'falhou', canvasErro: 'Assignment 404.' });
    const [c] = condicoesDaProva(p);
    expect(c.acao).toBe('tentar-canvas');
    expect(c.falha).toBe(true);
    expect(c.motivo).toBe('Assignment 404.');
  });

  it('desmarcar só aparece na prova do SAS que ninguém fez', () => {
    const semNinguem = condicoesDaProva(prova({ origem: 'sas', nPresentes: 0 }));
    expect(semNinguem.map((c) => c.acao)).toEqual(['desmarcar']);
    expect(condicoesDaProva(prova({ origem: 'sas', nPresentes: 380 }))).toEqual([]);
  });

  it('empilha as condições que coincidem, em vez de escolher uma', () => {
    const p = prova({ origem: 'sas', canvasEstado: 'falhou', nPresentes: 0 });
    expect(condicoesDaProva(p).map((c) => c.acao)).toEqual(['tentar-canvas', 'desmarcar']);
  });
});

describe('fichaVazia', () => {
  it('cala quando há dado', () => {
    expect(fichaVazia(prova(), [nota()], HOJE)).toBeNull();
  });

  it('a prova de semana que vem não teve nota "não chegada"', () => {
    const p = prova({ dataAplicacao: '2026-09-19', media: null, nPresentes: null });
    expect(fichaVazia(p, [], HOJE)?.olho).toBe('Prova agendada');
  });

  it('separa "ninguém lançou" de "todo mundo faltou"', () => {
    const p = prova({ media: null, nPresentes: 0 });
    const ausentes = [nota({ presente: false, pontuacao: null })];
    expect(fichaVazia(p, ausentes, HOJE)?.olho).toBe('Só ausências');
    expect(fichaVazia(p, [], HOJE)?.olho).toBe('Sem nota lançada');
  });

  it('a média sozinha já prova que há dado, mesmo sem a lista de notas', () => {
    expect(fichaVazia(prova({ media: 4.2 }), [], HOJE)).toBeNull();
  });
});
