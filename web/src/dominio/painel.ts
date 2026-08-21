// Lógica do Painel — a tabela alunos × matérias/fases de um ciclo.
//
// Está separada da UI porque é aqui que vivem as regras de negócio do
// domínio: o esquema de colunas de cada vestibular, as fórmulas de média
// (ITA e IME pesam as matérias de formas diferentes) e a definição de "em
// zona de corte". Testada em painel.test.ts.

import type { Aluno, Ciclo, Simulado, TipoSimulado } from '../tipos/dominio';

export interface ColunaPainel {
  id: string;
  label: string;
  /** "1°F", "2°F" ou "Final". */
  fase: string;
  /** Coluna calculada (média), não uma prova. */
  virtual: boolean;
  /** Primeira coluna da 2ª fase — ganha a borda divisória. */
  novaFase: boolean;
  /** Coluna de destaque visual (as médias). */
  destaque: boolean;
  /** Como achar a prova correspondente entre os simulados do ciclo. */
  simKey: { normNome: string; tipo: TipoSimulado } | null;
  /** Preenchido por `resolverColunas`. */
  sim: Simulado | null;
}

type DefColuna = Omit<ColunaPainel, 'sim'>;

function simCol(
  id: string, label: string, fase: string, normNome: string, tipo: TipoSimulado,
  extra: Partial<DefColuna> = {},
): DefColuna {
  return {
    id, label, fase, virtual: false, novaFase: false, destaque: false,
    simKey: { normNome, tipo }, ...extra,
  };
}

function mediaCol(id: string, label: string, fase: string): DefColuna {
  return { id, label, fase, virtual: true, novaFase: false, destaque: true, simKey: null };
}

/**
 * Esquemas de colunas por vestibular.
 *
 * ITA e IME cobram matérias diferentes em cada fase — o ITA tem Inglês na
 * Fase 1 (eliminatória), o IME só na Fase 2. Por isso o esquema é fixo por
 * vestibular em vez de derivado dos simulados: a coluna precisa existir mesmo
 * quando a prova ainda não foi aplicada.
 */
export const ESQUEMA: Record<string, Record<string, DefColuna[]>> = {
  ITA: {
    completo: [
      simCol('MAT_F1', 'Matemática', '1°F', 'matematica', 'fase_1'),
      simCol('FIS_F1', 'Física', '1°F', 'fisica', 'fase_1'),
      simCol('QUI_F1', 'Química', '1°F', 'quimica', 'fase_1'),
      simCol('ING_F1', 'Inglês', '1°F', 'ingles', 'fase_1'),
      mediaCol('MED_F1', 'Média', '1°F'),
      simCol('MAT_F2', 'Matemática', '2°F', 'matematica', 'fase_2', { novaFase: true }),
      simCol('FIS_F2', 'Física', '2°F', 'fisica', 'fase_2'),
      simCol('QUI_F2', 'Química', '2°F', 'quimica', 'fase_2'),
      simCol('RED_F2', 'Redação', '2°F', 'redacao', 'fase_2'),
      simCol('POR_F2', 'Português', '2°F', 'portugues', 'fase_2'),
      mediaCol('MED_FINAL', 'Média', 'Final'),
    ],
    somenteF1: [
      simCol('MAT_F1', 'Matemática', '1°F', 'matematica', 'fase_1'),
      simCol('FIS_F1', 'Física', '1°F', 'fisica', 'fase_1'),
      simCol('QUI_F1', 'Química', '1°F', 'quimica', 'fase_1'),
      simCol('ING_F1', 'Inglês', '1°F', 'ingles', 'fase_1'),
    ],
    somenteF2: [
      simCol('MAT_F2', 'Matemática', '2°F', 'matematica', 'fase_2'),
      simCol('FIS_F2', 'Física', '2°F', 'fisica', 'fase_2'),
      simCol('QUI_F2', 'Química', '2°F', 'quimica', 'fase_2'),
      simCol('RED_F2', 'Redação', '2°F', 'redacao', 'fase_2'),
      simCol('POR_F2', 'Português', '2°F', 'portugues', 'fase_2'),
      mediaCol('MED_FINAL', 'Média', 'Final'),
    ],
  },
  IME: {
    completo: [
      simCol('MAT_F1', 'Matemática', '1°F', 'matematica', 'fase_1'),
      simCol('FIS_F1', 'Física', '1°F', 'fisica', 'fase_1'),
      simCol('QUI_F1', 'Química', '1°F', 'quimica', 'fase_1'),
      simCol('MAT_F2', 'Matemática', '2°F', 'matematica', 'fase_2', { novaFase: true }),
      simCol('FIS_F2', 'Física', '2°F', 'fisica', 'fase_2'),
      simCol('QUI_F2', 'Química', '2°F', 'quimica', 'fase_2'),
      simCol('RED_F2', 'Redação', '2°F', 'redacao', 'fase_2'),
      simCol('POR_F2', 'Português', '2°F', 'portugues', 'fase_2'),
      simCol('ING_F2', 'Inglês', '2°F', 'ingles', 'fase_2'),
      mediaCol('MED_FINAL', 'Média', 'Final'),
    ],
    somenteF1: [
      simCol('MAT_F1', 'Matemática', '1°F', 'matematica', 'fase_1'),
      simCol('FIS_F1', 'Física', '1°F', 'fisica', 'fase_1'),
      simCol('QUI_F1', 'Química', '1°F', 'quimica', 'fase_1'),
      mediaCol('MED_F1', 'Média', '1°F'),
    ],
    somenteF2: [
      simCol('MAT_F2', 'Matemática', '2°F', 'matematica', 'fase_2'),
      simCol('FIS_F2', 'Física', '2°F', 'fisica', 'fase_2'),
      simCol('QUI_F2', 'Química', '2°F', 'quimica', 'fase_2'),
      simCol('RED_F2', 'Redação', '2°F', 'redacao', 'fase_2'),
      simCol('POR_F2', 'Português', '2°F', 'portugues', 'fase_2'),
      simCol('ING_F2', 'Inglês', '2°F', 'ingles', 'fase_2'),
      mediaCol('MED_FINAL', 'Média', 'Final'),
    ],
  },
};

/** "Matemática" → "matematica". Casa o nome da matéria com a chave do esquema. */
export function normMateria(s: string | null | undefined): string {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z]/g, '');
}

export function obterEsquema(
  vestibular: string | null | undefined,
  temF1: boolean,
  temF2: boolean,
): DefColuna[] | null {
  const vest = (vestibular || '').toUpperCase();
  const variante = temF1 && temF2 ? 'completo' : temF2 ? 'somenteF2' : 'somenteF1';
  return ESQUEMA[vest]?.[variante] ?? null;
}

export function encontrarSimulado(
  sims: readonly Simulado[],
  simKey: ColunaPainel['simKey'],
): Simulado | null {
  if (!simKey) return null;
  return (
    sims.find(
      (s) =>
        s.tipo === simKey.tipo &&
        normMateria(s.materia?.nome || s.materia?.codigo || '') === simKey.normNome,
    ) ?? null
  );
}

/**
 * Colunas derivadas dos próprios simulados. Usado quando o ciclo não tem
 * vestibular definido e portanto não casa com nenhum esquema fixo.
 */
export function buildColunasDinamicas(sims: readonly Simulado[]): DefColuna[] {
  const visto = new Set<string>();
  const colunas: DefColuna[] = [];

  for (const s of sims) {
    if (!s.materia) continue;
    const norm = normMateria(s.materia.nome);
    const chave = `${norm}_${s.tipo}`;
    if (visto.has(chave)) continue;
    visto.add(chave);
    colunas.push(
      simCol(chave, s.materia.nome, s.tipo === 'fase_1' ? '1°F' : '2°F', norm, s.tipo as TipoSimulado),
    );
  }
  return colunas;
}

/** Liga cada definição de coluna ao simulado correspondente do ciclo. */
export function resolverColunas(
  defs: readonly DefColuna[],
  sims: readonly Simulado[],
): ColunaPainel[] {
  return defs.map((c) => ({ ...c, sim: c.virtual ? null : encontrarSimulado(sims, c.simKey) }));
}

export interface NotaDoPainel {
  alunoId: string;
  nota: number | null;
  presente?: boolean;
  acertos?: number | null;
  total?: number | null;
}

export type NotasPorSimulado = Record<string, NotaDoPainel[]>;
/** alunoId → simuladoId → nota. */
export type NotasPorAluno = Record<string, Record<string, number>>;

export function buildNotasAluno(
  alunos: readonly Aluno[],
  sims: readonly Simulado[],
  notasPorSim: NotasPorSimulado,
): NotasPorAluno {
  const mapa: NotasPorAluno = {};
  for (const aluno of alunos) mapa[aluno.id] = {};

  for (const sim of sims) {
    for (const { alunoId, nota } of notasPorSim[sim.id] ?? []) {
      if (mapa[alunoId] && nota != null) mapa[alunoId][sim.id] = nota;
    }
  }
  return mapa;
}

/**
 * Média ponderada considerando SÓ os componentes presentes: divide pela soma
 * dos pesos que realmente entraram, não pelo total teórico. `null` quando
 * nenhum componente existe — quem não fez prova nenhuma não tem média.
 */
export function mediaPonderada(pares: Array<[number | null, number]>): number | null {
  let soma = 0;
  let pesos = 0;
  for (const [valor, peso] of pares) {
    if (valor == null) continue;
    soma += valor * peso;
    pesos += peso;
  }
  return pesos > 0 ? soma / pesos : null;
}

export function mediaGeralAluno(
  alunoId: string,
  notasAluno: NotasPorAluno,
  colunas: readonly ColunaPainel[],
): number | null {
  const vals = colunas
    .filter((c) => !c.virtual && c.sim)
    .map((c) => notasAluno[alunoId]?.[c.sim!.id])
    .filter((v): v is number => v != null);

  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/**
 * Valores das colunas virtuais (médias) de um aluno, pelas fórmulas de cada
 * vestibular.
 *
 * Ausência é `null`, NUNCA zero. Tratar "não fez" como 0,0 achatava a média
 * da turma (1,3 contra 5,4/4,9/4,3 por matéria), porque a maioria dos alunos
 * do ciclo não presta cada simulado. A regra: a média de um aluno é sobre as
 * matérias que ele fez, sem exigir mínimo.
 */
export function calcularMediasVirtuais(
  alunoId: string,
  colunas: readonly ColunaPainel[],
  notasAluno: NotasPorAluno,
  vestibular: string | null | undefined,
): Record<string, number | null> {
  const vest = (vestibular || '').toUpperCase();
  const calculado: Record<string, number | null> = {};

  /** Valor de uma coluna, real ou virtual. Ausente = null. */
  function v(colId: string): number | null {
    const col = colunas.find((c) => c.id === colId);
    if (!col) return null;
    if (col.virtual) return calculado[colId] ?? null;
    if (!col.sim) return null;
    return notasAluno[alunoId]?.[col.sim.id] ?? null;
  }

  /** Média simples: todos os componentes com peso 1. */
  const media = (...ids: string[]) => mediaPonderada(ids.map((id) => [v(id), 1]));
  const temColuna = (id: string) => colunas.some((c) => c.id === id);

  if (vest === 'ITA') {
    if (temColuna('MED_F1')) {
      calculado['MED_F1'] = media('MAT_F1', 'FIS_F1', 'QUI_F1');
    }
    if (temColuna('MED_FINAL')) {
      // Redação e Português entram como um bloco único de linguagens.
      const linguagens = media('RED_F2', 'POR_F2');
      calculado['MED_FINAL'] = mediaPonderada([
        [v('MAT_F2'), 1],
        [v('FIS_F2'), 1],
        [v('QUI_F2'), 1],
        [v('MED_F1'), 1],
        [linguagens, 1],
      ]);
    }
  } else if (vest === 'IME') {
    if (temColuna('MED_F1')) {
      calculado['MED_F1'] = media('MAT_F1', 'FIS_F1', 'QUI_F1');
    }
    if (temColuna('MED_FINAL')) {
      // O IME pesa as exatas acima das demais.
      calculado['MED_FINAL'] = mediaPonderada([
        [v('MAT_F2'), 3],
        [v('FIS_F2'), 2.5],
        [v('QUI_F2'), 2.5],
        [v('POR_F2'), 1],
        [v('ING_F2'), 1],
      ]);
    }
  }

  return calculado;
}

/** Colunas exibidas na fase selecionada: matérias da fase + a média geral. */
export function colunasExibidas(
  colunasFull: readonly ColunaPainel[],
  faseSel: '1' | '2',
): ColunaPainel[] {
  const faseLabel = faseSel === '1' ? '1°F' : '2°F';
  const materias = colunasFull.filter((c) => !c.virtual && c.fase === faseLabel);
  const virtuais = colunasFull.filter((c) => c.virtual);
  // A última virtual é MED_FINAL — ou MED_F1 nos ciclos só de 1ª fase.
  const geral = virtuais[virtuais.length - 1] ?? null;
  return geral ? [...materias, geral] : materias;
}

/**
 * Aprovado / cortado / neutro pelo corte por matéria (nota < 5).
 *
 * Julga só as matérias que o aluno fez — mesma regra da média. Aluno sem nota
 * nenhuma é 'neutro', não 'cortado': antes, ausência total contava como corte
 * e inflava o KPI "em zona de corte" (800 de 873) com gente que simplesmente
 * não prestou os simulados.
 */
export function statusAluno(
  alunoId: string,
  colunas: readonly ColunaPainel[],
  notasAluno: NotasPorAluno,
): 'aprovado' | 'cortado' | 'neutro' {
  const notas = colunas
    .filter((c) => !c.virtual && c.sim)
    .map((c) => notasAluno[alunoId]?.[c.sim!.id])
    .filter((n): n is number => n != null);

  if (notas.length === 0) return 'neutro';
  return notas.every((n) => n >= 5) ? 'aprovado' : 'cortado';
}

/** Valor que ordena o ranking: média final, ou da 1ª fase, ou a média simples. */
export function valorOrdenacao(
  alunoId: string,
  mediasVirtuais: Record<string, Record<string, number | null>>,
  notasAluno: NotasPorAluno,
  colunas: readonly ColunaPainel[],
): number {
  const mv = mediasVirtuais[alunoId] ?? {};
  if (mv['MED_FINAL'] != null) return mv['MED_FINAL'];
  if (mv['MED_F1'] != null) return mv['MED_F1'];
  return mediaGeralAluno(alunoId, notasAluno, colunas) ?? -Infinity;
}

export interface ResumoCiclo {
  totalAlunos: number;
  totalSimulados: number;
  mediaGeral: number | null;
  cortados: number;
}

export interface DadosPainel {
  colunasFull: ColunaPainel[];
  colunas: ColunaPainel[];
  notasAluno: NotasPorAluno;
  mediasVirtuais: Record<string, Record<string, number | null>>;
  mediasPorColuna: Record<string, number | null>;
  alunosOrdenados: Aluno[];
  fasesDisponiveis: Array<'1' | '2'>;
  faseSelecionada: '1' | '2';
  resumo: ResumoCiclo | null;
  /** Preenchido quando não há como montar a tabela. */
  erro: string | null;
}

/**
 * Monta tudo o que a tabela precisa: colunas, notas, médias, ordenação e KPIs.
 *
 * As médias são sempre calculadas sobre o conjunto COMPLETO de colunas, mesmo
 * quando só uma fase está visível — a média final do ITA depende da 1ª fase.
 */
export function montarPainel({
  ciclo, simulados, alunos, notasPorSim, fase, ordenacao,
}: {
  ciclo: Ciclo | null;
  simulados: readonly Simulado[];
  alunos: readonly Aluno[];
  notasPorSim: NotasPorSimulado;
  fase: '1' | '2';
  ordenacao: 'ranking' | 'alfabetica';
}): DadosPainel {
  const vazio: DadosPainel = {
    colunasFull: [], colunas: [], notasAluno: {}, mediasVirtuais: {},
    mediasPorColuna: {}, alunosOrdenados: [], fasesDisponiveis: [],
    faseSelecionada: fase, resumo: null, erro: null,
  };

  if (!ciclo) return { ...vazio, erro: 'Selecione um ciclo na barra lateral.' };

  const sims = simulados
    .filter((s) => ciclo.simuladoIds.includes(s.id))
    .sort((a, b) => (a.dataAplicacao || '').localeCompare(b.dataAplicacao || ''));

  const temF1 = sims.some((s) => s.tipo === 'fase_1');
  const temF2 = sims.some((s) => s.tipo === 'fase_2');

  const defs = obterEsquema(ciclo.vestibularAlvo, temF1, temF2) ?? buildColunasDinamicas(sims);
  if (defs.length === 0) {
    return { ...vazio, erro: 'Nenhum simulado com matéria e fase definidos neste ciclo.' };
  }

  const colunasFull = resolverColunas(defs, sims);
  const notasAluno = buildNotasAluno(alunos, sims, notasPorSim);

  const mediasVirtuais: Record<string, Record<string, number | null>> = {};
  for (const aluno of alunos) {
    mediasVirtuais[aluno.id] = calcularMediasVirtuais(
      aluno.id, colunasFull, notasAluno, ciclo.vestibularAlvo,
    );
  }

  const fasesDisponiveis: Array<'1' | '2'> = [];
  if (temF1) fasesDisponiveis.push('1');
  if (temF2) fasesDisponiveis.push('2');
  const faseSelecionada = fasesDisponiveis.includes(fase) ? fase : fasesDisponiveis[0] ?? '1';

  const colunas = colunasExibidas(colunasFull, faseSelecionada);

  const alunosOrdenados = alunos.slice();
  if (ordenacao === 'alfabetica') {
    alunosOrdenados.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  } else {
    alunosOrdenados.sort(
      (a, b) =>
        valorOrdenacao(b.id, mediasVirtuais, notasAluno, colunas) -
        valorOrdenacao(a.id, mediasVirtuais, notasAluno, colunas),
    );
  }

  const media = (vals: number[]) =>
    vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;

  const mediasPorColuna: Record<string, number | null> = {};
  for (const col of colunas) {
    const vals = alunosOrdenados
      .map((a) => (col.virtual
        ? mediasVirtuais[a.id]?.[col.id]
        : col.sim
          ? notasAluno[a.id]?.[col.sim.id]
          : null))
      .filter((v): v is number => v != null);
    mediasPorColuna[col.id] = media(vals);
  }

  const gerais = alunosOrdenados
    .map((a) => {
      const mv = mediasVirtuais[a.id] ?? {};
      if (mv['MED_FINAL'] != null) return mv['MED_FINAL'];
      if (mv['MED_F1'] != null) return mv['MED_F1'];
      return mediaGeralAluno(a.id, notasAluno, colunas);
    })
    .filter((v): v is number => v != null);

  const resumo: ResumoCiclo = {
    totalAlunos: alunosOrdenados.length,
    totalSimulados: sims.length,
    mediaGeral: media(gerais),
    cortados: alunosOrdenados.filter((a) => statusAluno(a.id, colunas, notasAluno) === 'cortado').length,
  };

  return {
    colunasFull, colunas, notasAluno, mediasVirtuais, mediasPorColuna,
    alunosOrdenados, fasesDisponiveis, faseSelecionada, resumo, erro: null,
  };
}

export interface EstatisticasNota {
  posicao: number | null;
  totalPresentes: number;
  nota: number | null;
  media: number;
  maiorNota: number;
  mediaTop15: number;
  mediaBottom15: number;
  mediana: number;
}

/** Comparação do aluno com a turma naquele simulado, para a ficha de nota. */
export function estatisticasDoSimulado(
  notas: readonly NotaDoPainel[],
  alunoId: string,
): EstatisticasNota | null {
  const presentes = notas
    .filter((n) => n.presente && n.nota != null)
    .map((n) => n.nota as number)
    .sort((a, b) => b - a);

  if (!presentes.length) return null;

  const n = presentes.length;
  const nota = notas.find((x) => x.alunoId === alunoId)?.nota ?? null;
  const posicao = nota != null ? presentes.filter((v) => v > nota).length + 1 : null;
  const soma = (xs: number[]) => xs.reduce((a, b) => a + b, 0);

  // Fatia de 15% com pelo menos um aluno — em turma pequena o topo é 1 pessoa.
  const q = Math.max(1, Math.ceil(n * 0.15));

  return {
    posicao,
    totalPresentes: n,
    nota,
    media: soma(presentes) / n,
    maiorNota: presentes[0],
    mediaTop15: soma(presentes.slice(0, q)) / q,
    mediaBottom15: soma(presentes.slice(-q)) / q,
    mediana: n % 2 === 0 ? (presentes[n / 2 - 1] + presentes[n / 2]) / 2 : presentes[Math.floor(n / 2)],
  };
}

/** Posições em que aparece o separador de ranking. */
export const LIMITES_RANKING = [10, 50, 100];

/** Uma linha some quando está abaixo de um limite recolhido. */
export function linhaVisivel(posicao: number, recolhidos: ReadonlySet<number>): boolean {
  return !LIMITES_RANKING.some((l) => l < posicao && recolhidos.has(l));
}

const NOMES_SEDE: Record<string, string> = {
  AD: 'Aldeota',
  MF: 'Major Facundo',
  ONLINE: 'Online',
  PROPOSITO: 'Propósito',
  ONLINE_E_PROPOSITO: 'Online e Propósito',
  PB: 'Parangaba',
  '3O_ITA_MF_E_ONLINE': 'Terceiro Ano ITA',
};

/** O banco guarda a sede em código; a UI mostra o nome legível. */
export function nomeSede(bruto: string): string {
  return NOMES_SEDE[bruto] ?? bruto.replace(/_/g, ' ').replace(/\b3O\b/g, '3°');
}
