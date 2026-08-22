import { describe, expect, it } from 'vitest';
import {
  buildColunasDinamicas, buildNotasAluno, calcularMediasVirtuais, colunasExibidas,
  estatisticasDoSimulado, linhaVisivel, mediaGeralAluno, mediaPonderada, montarPainel,
  nomeSede, normMateria, obterEsquema, resolverColunas,
} from './painel';
import type { ColunaPainel, NotasPorSimulado } from './painel';
import type { Aluno, Ciclo, Simulado } from '../tipos/dominio';

// ─── Fábricas ────────────────────────────────────────────────────────────

function sim(id: string, materia: string, tipo: 'fase_1' | 'fase_2', data = '2026-03-01'): Simulado {
  return {
    id, nome: id, rotuloCurto: id, tipo,
    materia: { codigo: materia.slice(0, 3).toUpperCase(), nome: materia },
    dataAplicacao: data, cicloId: 'C1', cicloOrdem: 1, vestibularAlvo: 'ITA',
    notaMaxima: 20, anulado: false, origem: 'canvas', canvasEstado: 'sincronizado',
    canvasErro: null, media: null, mediana: null, desvioPadrao: null, nPresentes: null,
  } as Simulado;
}

function aluno(id: string, nome: string): Aluno {
  return {
    id, nome, turmaId: 'T1', sedeId: 'SD1', vestibularesAlvo: ['ITA'], ativo: true,
    email: null, perfil: 'regular', tendencia: 'estavel', zona: 'cinzenta',
    media: null, sparkline: [],
  } as Aluno;
}

function ciclo(vestibular: string | null, simuladoIds: string[]): Ciclo {
  return {
    id: 'C1', nome: 'Ciclo 1', anoLetivo: 2026,
    vestibularAlvo: vestibular as Ciclo['vestibularAlvo'],
    periodoInicio: '2026-03-01', periodoFim: '2026-03-31', simuladoIds,
  };
}

const coluna = (p: Partial<ColunaPainel> & { id: string }): ColunaPainel => ({
  label: p.id, fase: '1°F', virtual: false, novaFase: false, destaque: false,
  simKey: null, sim: null, ...p,
});

// ─── Helpers ─────────────────────────────────────────────────────────────

describe('normMateria', () => {
  it('remove acento, caixa e pontuação', () => {
    expect(normMateria('Matemática')).toBe('matematica');
    expect(normMateria('  FÍSICA ')).toBe('fisica');
    expect(normMateria('Língua Portuguesa')).toBe('linguaportuguesa');
    expect(normMateria(null)).toBe('');
  });
});

describe('obterEsquema', () => {
  it('escolhe a variante pela presença de cada fase', () => {
    expect(obterEsquema('ITA', true, true)!.map((c) => c.id)).toContain('MED_FINAL');
    expect(obterEsquema('ITA', true, false)!.map((c) => c.id)).toEqual(
      ['MAT_F1', 'FIS_F1', 'QUI_F1', 'ING_F1'],
    );
    expect(obterEsquema('IME', false, true)!.map((c) => c.id)).toContain('ING_F2');
  });

  // Inglês F1 é do ITA; no IME a língua só aparece na 2ª fase.
  it('ITA tem Inglês na F1 e IME não', () => {
    expect(obterEsquema('ITA', true, true)!.some((c) => c.id === 'ING_F1')).toBe(true);
    expect(obterEsquema('IME', true, true)!.some((c) => c.id === 'ING_F1')).toBe(false);
    expect(obterEsquema('IME', true, true)!.some((c) => c.id === 'ING_F2')).toBe(true);
  });

  it('aceita o vestibular em qualquer caixa e devolve null para desconhecido', () => {
    expect(obterEsquema('ita', true, true)).not.toBeNull();
    expect(obterEsquema('AFA', true, true)).toBeNull();
    expect(obterEsquema(null, true, true)).toBeNull();
  });

  it('marca a primeira coluna da 2ª fase com a borda divisória', () => {
    const comp = obterEsquema('ITA', true, true)!;
    expect(comp.filter((c) => c.novaFase).map((c) => c.id)).toEqual(['MAT_F2']);
  });
});

describe('resolverColunas', () => {
  it('liga a coluna ao simulado da mesma matéria e fase', () => {
    const sims = [sim('S1', 'Matemática', 'fase_1'), sim('S2', 'Matemática', 'fase_2')];
    const cols = resolverColunas(obterEsquema('ITA', true, true)!, sims);
    expect(cols.find((c) => c.id === 'MAT_F1')!.sim!.id).toBe('S1');
    expect(cols.find((c) => c.id === 'MAT_F2')!.sim!.id).toBe('S2');
    // Coluna sem prova aplicada continua existindo, só que vazia.
    expect(cols.find((c) => c.id === 'FIS_F1')!.sim).toBeNull();
    expect(cols.find((c) => c.virtual)!.sim).toBeNull();
  });
});

describe('buildColunasDinamicas', () => {
  it('deriva colunas dos simulados quando não há esquema, sem duplicar', () => {
    const cols = buildColunasDinamicas([
      sim('S1', 'Redação', 'fase_2'),
      sim('S2', 'Redação', 'fase_2'),
      sim('S3', 'Redação', 'fase_1'),
    ]);
    expect(cols.map((c) => c.id)).toEqual(['redacao_fase_2', 'redacao_fase_1']);
    expect(cols.map((c) => c.fase)).toEqual(['2°F', '1°F']);
  });
});

// ─── Médias ──────────────────────────────────────────────────────────────

describe('mediaPonderada', () => {
  // A regra central: divide pelos pesos PRESENTES, não pelo total teórico.
  it('ignora ausentes e divide pelos pesos presentes', () => {
    expect(mediaPonderada([[8, 3], [null, 2], [6, 1]])).toBe((8 * 3 + 6) / 4);
  });

  it('devolve null quando nada está presente', () => {
    expect(mediaPonderada([[null, 3], [null, 1]])).toBeNull();
  });

  // Zero é nota, ausência não é: o zero precisa puxar a média para baixo.
  it('trata 0 como nota, não como ausência', () => {
    expect(mediaPonderada([[0, 1], [10, 1]])).toBe(5);
  });
});

describe('calcularMediasVirtuais', () => {
  const sims = [
    sim('MF1', 'Matemática', 'fase_1'), sim('FF1', 'Física', 'fase_1'),
    sim('QF1', 'Química', 'fase_1'), sim('IF1', 'Inglês', 'fase_1'),
    sim('MF2', 'Matemática', 'fase_2'), sim('FF2', 'Física', 'fase_2'),
    sim('QF2', 'Química', 'fase_2'), sim('RF2', 'Redação', 'fase_2'),
    sim('PF2', 'Português', 'fase_2'), sim('IF2', 'Inglês', 'fase_2'),
  ];

  it('ITA: média da F1 é a das três exatas, sem Inglês', () => {
    const cols = resolverColunas(obterEsquema('ITA', true, true)!, sims);
    const notas = { A1: { MF1: 6, FF1: 8, QF1: 7, IF1: 2 } };
    const mv = calcularMediasVirtuais('A1', cols, notas, 'ITA');
    // Se Inglês entrasse, a média cairia para 5,75.
    expect(mv['MED_F1']).toBe(7);
  });

  it('ITA: a final pesa MAT/FIS/QUI da F2, a média da F1, e linguagens como um bloco', () => {
    const cols = resolverColunas(obterEsquema('ITA', true, true)!, sims);
    const notas = { A1: { MF1: 6, FF1: 6, QF1: 6, MF2: 8, FF2: 8, QF2: 8, RF2: 4, PF2: 6 } };
    const mv = calcularMediasVirtuais('A1', cols, notas, 'ITA');
    // Linguagens = (4+6)/2 = 5. Final = (8 + 8 + 8 + 6 + 5) / 5 = 7.
    expect(mv['MED_FINAL']).toBe(7);
  });

  it('IME: a final pesa as exatas acima das demais', () => {
    const cols = resolverColunas(obterEsquema('IME', true, true)!, sims);
    const notas = { A1: { MF2: 10, FF2: 5, QF2: 5, PF2: 0, IF2: 0 } };
    const mv = calcularMediasVirtuais('A1', cols, notas, 'IME');
    // (10*3 + 5*2.5 + 5*2.5 + 0 + 0) / 10 = 5,5. Média simples daria 4.
    expect(mv['MED_FINAL']).toBe(5.5);
  });

  it('aluno sem nenhuma nota não tem média', () => {
    const cols = resolverColunas(obterEsquema('ITA', true, true)!, sims);
    const mv = calcularMediasVirtuais('A1', cols, { A1: {} }, 'ITA');
    expect(mv['MED_F1']).toBeNull();
    expect(mv['MED_FINAL']).toBeNull();
  });

  it('a final usa só o que existe quando o aluno fez parte das provas', () => {
    const cols = resolverColunas(obterEsquema('ITA', true, true)!, sims);
    const mv = calcularMediasVirtuais('A1', cols, { A1: { MF2: 8 } }, 'ITA');
    expect(mv['MED_FINAL']).toBe(8);
  });

  it('vestibular sem fórmula não gera médias', () => {
    const cols = resolverColunas(buildColunasDinamicas(sims), sims);
    expect(calcularMediasVirtuais('A1', cols, { A1: { MF1: 7 } }, null)).toEqual({});
  });
});

describe('mediaGeralAluno', () => {
  it('média simples das colunas reais preenchidas', () => {
    const cols = [
      coluna({ id: 'a', sim: sim('S1', 'Matemática', 'fase_1') }),
      coluna({ id: 'b', sim: sim('S2', 'Física', 'fase_1') }),
      coluna({ id: 'med', virtual: true }),
    ];
    expect(mediaGeralAluno('A1', { A1: { S1: 4, S2: 8 } }, cols)).toBe(6);
    expect(mediaGeralAluno('A1', { A1: {} }, cols)).toBeNull();
  });
});

// ─── Status e exibição ───────────────────────────────────────────────────

// A regra de corte saiu daqui: é testada em api/tests/test_criterios.py
// contra os editais (docs/18 §1.2).

describe('colunasExibidas', () => {
  it('mostra as matérias da fase escolhida mais a média geral', () => {
    const cols = resolverColunas(obterEsquema('ITA', true, true)!, []);
    expect(colunasExibidas(cols, '1').map((c) => c.id))
      .toEqual(['MAT_F1', 'FIS_F1', 'QUI_F1', 'ING_F1', 'MED_FINAL']);
    expect(colunasExibidas(cols, '2').map((c) => c.id))
      .toEqual(['MAT_F2', 'FIS_F2', 'QUI_F2', 'RED_F2', 'POR_F2', 'MED_FINAL']);
  });

  it('em ciclo só de 1ª fase, a geral é a média da própria fase', () => {
    const cols = resolverColunas(obterEsquema('IME', true, false)!, []);
    expect(colunasExibidas(cols, '1').map((c) => c.id))
      .toEqual(['MAT_F1', 'FIS_F1', 'QUI_F1', 'MED_F1']);
  });
});

describe('linhaVisivel', () => {
  it('esconde quem está abaixo de um limite recolhido', () => {
    const recolhidos = new Set([10]);
    expect(linhaVisivel(10, recolhidos)).toBe(true);
    expect(linhaVisivel(11, recolhidos)).toBe(false);
    expect(linhaVisivel(11, new Set())).toBe(true);
  });
});

describe('nomeSede', () => {
  it('traduz os códigos conhecidos e humaniza o resto', () => {
    expect(nomeSede('AD')).toBe('Aldeota');
    expect(nomeSede('3O_ITA_MF_E_ONLINE')).toBe('Terceiro Ano ITA');
    expect(nomeSede('NOVA_SEDE')).toBe('NOVA SEDE');
  });
});

// ─── Montagem completa ───────────────────────────────────────────────────

describe('montarPainel', () => {
  const sims = [
    sim('MF1', 'Matemática', 'fase_1', '2026-03-01'),
    sim('FF1', 'Física', 'fase_1', '2026-03-02'),
    sim('QF1', 'Química', 'fase_1', '2026-03-03'),
    sim('IF1', 'Inglês', 'fase_1', '2026-03-04'),
  ];
  const alunos = [aluno('A1', 'Bruno'), aluno('A2', 'Ana'), aluno('A3', 'Caio')];
  const notasPorSim: NotasPorSimulado = {
    MF1: [
      { alunoId: 'A1', nota: 4, presente: true },
      { alunoId: 'A2', nota: 9, presente: true },
    ],
    FF1: [
      { alunoId: 'A1', nota: 6, presente: true },
      { alunoId: 'A2', nota: 8, presente: true },
    ],
    QF1: [], IF1: [],
  };

  // O veredito vem do servidor (docs/18 §1.2). Aqui ele é um dado de entrada:
  // A2 aprovado em 1º, A1 cortado em 2º, A3 sem nota (fora da classificação).
  const classificacao = {
    A2: { alunoId: 'A2', nome: 'Ana', turmaId: null, posicao: 1, aprovado: true, motivo: null, media: 8.5, notas: {} },
    A1: { alunoId: 'A1', nome: 'Bruno', turmaId: null, posicao: 2, aprovado: false, motivo: 'Matematica 4,0 — mínimo 5,0', media: 5, notas: {} },
  };

  const base = {
    ciclo: ciclo('ITA', ['MF1', 'FF1', 'QF1', 'IF1']),
    simulados: sims, alunos, notasPorSim, classificacao,
    fase: '1' as const, ordenacao: 'ranking' as const,
  };

  it('ordena pela posição do servidor, com quem não está classificado no fim', () => {
    const d = montarPainel(base);
    expect(d.alunosOrdenados.map((a) => a.id)).toEqual(['A2', 'A1', 'A3']);
  });

  it('sem classificação ainda, o ranking cai em ordem alfabética estável', () => {
    const d = montarPainel({ ...base, classificacao: {} });
    expect(d.alunosOrdenados.map((a) => a.nome)).toEqual(['Ana', 'Bruno', 'Caio']);
    expect(d.resumo?.cortados).toBeNull();
  });

  it('ordena alfabeticamente em pt-BR quando pedido', () => {
    const d = montarPainel({ ...base, ordenacao: 'alfabetica' });
    expect(d.alunosOrdenados.map((a) => a.nome)).toEqual(['Ana', 'Bruno', 'Caio']);
  });

  it('só oferece as fases que o ciclo tem', () => {
    expect(montarPainel(base).fasesDisponiveis).toEqual(['1']);
    // Fase pedida que não existe cai na disponível.
    expect(montarPainel({ ...base, fase: '2' }).faseSelecionada).toBe('1');
  });

  it('média da turma por coluna ignora quem não fez', () => {
    const d = montarPainel(base);
    const colMat = d.colunas.find((c) => c.id === 'MAT_F1')!;
    // (4 + 9) / 2 — o A3 não entra.
    expect(d.mediasPorColuna[colMat.id]).toBe(6.5);
  });

  it('KPIs contam alunos, simulados e os cortados segundo o servidor', () => {
    const d = montarPainel(base);
    expect(d.resumo).toMatchObject({ totalAlunos: 3, totalSimulados: 4, cortados: 1 });
    // A1 veio cortado, A2 aprovado, A3 não está na classificação (sem nota).
  });

  it('reporta erro em vez de tabela quando não há ciclo', () => {
    const d = montarPainel({ ...base, ciclo: null });
    expect(d.erro).toBe('Selecione um ciclo na barra lateral.');
    expect(d.colunas).toEqual([]);
  });

  it('reporta erro quando o ciclo não tem simulado com matéria e fase', () => {
    const d = montarPainel({ ...base, ciclo: ciclo(null, []), simulados: [] });
    expect(d.erro).toBe('Nenhum simulado com matéria e fase definidos neste ciclo.');
  });
});

describe('buildNotasAluno', () => {
  it('indexa por aluno e ignora nota nula e aluno de fora da lista', () => {
    const mapa = buildNotasAluno(
      [aluno('A1', 'Ana')],
      [sim('S1', 'Matemática', 'fase_1')],
      { S1: [{ alunoId: 'A1', nota: 7 }, { alunoId: 'A1', nota: null }, { alunoId: 'ZZ', nota: 5 }] },
    );
    expect(mapa).toEqual({ A1: { S1: 7 } });
  });
});

describe('estatisticasDoSimulado', () => {
  const notas = [
    { alunoId: 'A1', nota: 9, presente: true },
    { alunoId: 'A2', nota: 7, presente: true },
    { alunoId: 'A3', nota: 5, presente: true },
    { alunoId: 'A4', nota: 3, presente: true },
    { alunoId: 'A5', nota: null, presente: false },
  ];

  it('calcula posição, média e mediana só entre presentes', () => {
    const e = estatisticasDoSimulado(notas, 'A2')!;
    expect(e.totalPresentes).toBe(4);
    expect(e.posicao).toBe(2);
    expect(e.media).toBe(6);
    expect(e.mediana).toBe(6);
    expect(e.maiorNota).toBe(9);
  });

  it('a fatia de 15% tem pelo menos um aluno', () => {
    const e = estatisticasDoSimulado(notas, 'A1')!;
    expect(e.mediaTop15).toBe(9);
    expect(e.mediaBottom15).toBe(3);
  });

  it('sem presentes não há estatística', () => {
    expect(estatisticasDoSimulado([{ alunoId: 'A1', nota: null, presente: false }], 'A1')).toBeNull();
  });

  it('aluno ausente não tem posição, mas a turma continua tendo estatística', () => {
    const e = estatisticasDoSimulado(notas, 'A5')!;
    expect(e.posicao).toBeNull();
    expect(e.totalPresentes).toBe(4);
  });
});
