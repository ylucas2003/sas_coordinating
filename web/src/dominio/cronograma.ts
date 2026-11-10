// A proposta de cronograma de 2027 — as contas da tela /cronograma, em função pura.
//
// O desenho da tela é de camadas (Shneiderman: visão geral → recorte → detalhe): cada aba começa com o mínimo e
// cada clique abre um nível. As contas que sustentam cada nível moram aqui:
//
//   assuntosDaMateria   matéria → assuntos, com as aulas de cada professor e os itens com o nome dele
//   blocosDoProfessor   as semanas de um professor → blocos do assunto dominante (o "ano numa tela")
//   etapasDoProfessor   os itens de um professor → uma etapa por assunto, na ordem em que aparece no ano
//
// Um "assunto" é o grupo da taxonomia do SAS, o que deixa somar dois professores; o nome que aparece para o
// coordenador, dentro dele, é o do PROFESSOR (decisão de 09/11/2026: a taxonomia e o edital são a conferência,
// não a divisão da grade).

import type { GrupoDoPlano, ItemDoPlano, PlanoDoAno, ProfessorDoPlano } from '../tipos/cronograma';

/** Códigos que não são conteúdo: revisão de fim de ano, revisão no meio do ano, simulado, plantão… */
export const NAO_CONTEUDO: ReadonlySet<string> = new Set(['REVF', 'REV', 'SIM', 'PLANT', 'APRES', 'VEST', '?']);

/**
 * Em Português, Inglês e Redação o grupo vem da taxonomia PROPOSTA e tem nome de parágrafo ("Literatura brasileira:
 * Realismo-Naturalismo, Parnasianismo e Simbolismo"): ali o bloco leva o nome que o professor usa, que é curto.
 */
const MATERIAS_DE_TEXTO: ReadonlySet<string> = new Set(['Português', 'Inglês', 'Redação']);

export const NOME_DO_MES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

export interface AssuntoDaMateria extends GrupoDoPlano {
  aulas2027: number;
  aulas2026: number;
  /** Professor → aulas de 2027 nesse assunto, de quem dá mais para quem dá menos. */
  porProfessor: [string, number][];
  /** Itens que caem no assunto (peso ≥ 20%, ou o item inteiro). */
  itens: { item: ItemDoPlano; peso: number }[];
}

export interface BlocoDoAno {
  codigo: string;
  de: number;
  ate: number;
  aulas: number;
  semanas: number[];
  /** Nomes que o professor usa no bloco, do que pesa mais para o que pesa menos. */
  itens: string[];
  grupo: string;
  rotulo: string;
}

export interface EtapaDoProfessor {
  codigo: string;
  itens: ItemDoPlano[];
  aulas: number;
  rotulo: string;
  /** Aulas por mês do ano letivo (índice = posição em `mesesDoAno`). */
  meses: number[];
}

export function nomeDoGrupo(plano: PlanoDoAno, materia: string, codigo: string): string {
  return plano.grupos.find((g) => g.materia === materia && g.codigo === codigo)?.nome ?? codigo;
}

export function professoresDaMateria(plano: PlanoDoAno, materia: string): ProfessorDoPlano[] {
  return plano.professores.filter((p) => p.materia === materia).sort((a, b) => b.aulas_2027 - a.aulas_2027);
}

/** Os itens de um professor na ordem de 2026, com a revisão de fim de ano por último. */
export function itensDoProfessor(plano: PlanoDoAno, materia: string, professor: string): ItemDoPlano[] {
  return plano.itens
    .filter((it) => it.materia === materia && it.professor === professor)
    .sort((a, b) => Number('REVF' in a.codigos) - Number('REVF' in b.codigos) || a.ordem - b.ordem);
}

export function ehConteudo(item: ItemDoPlano): boolean {
  return Object.keys(item.codigos).some((c) => !NAO_CONTEUDO.has(c));
}

function codigoPrincipal(item: ItemDoPlano): string {
  return Object.entries(item.codigos).sort((a, b) => b[1] - a[1])[0]?.[0] ?? '?';
}

export function assuntosDaMateria(plano: PlanoDoAno, materia: string): AssuntoDaMateria[] {
  const grupos = new Map<string, AssuntoDaMateria & { prof: Map<string, number> }>();
  for (const item of plano.itens) {
    if (item.materia !== materia) continue;
    const varios = Object.keys(item.codigos).length > 1;
    for (const [codigo, peso] of Object.entries(item.codigos)) {
      let g = grupos.get(codigo);
      if (!g) {
        const base = plano.grupos.find((x) => x.materia === materia && x.codigo === codigo)
          ?? { materia, codigo, nome: codigo, conteudo: !NAO_CONTEUDO.has(codigo), peso_ita: null, peso_ime: null, peso_medio: null };
        g = { ...base, aulas2027: 0, aulas2026: 0, porProfessor: [], itens: [], prof: new Map() };
        grupos.set(codigo, g);
      }
      g.aulas2027 += item.aulas_2027 * peso;
      g.aulas2026 += item.aulas_2026 * peso;
      g.prof.set(item.professor, (g.prof.get(item.professor) ?? 0) + item.aulas_2027 * peso);
      if (peso >= 0.2 || !varios) g.itens.push({ item, peso });
    }
  }
  return [...grupos.values()]
    .map(({ prof, ...g }) => ({ ...g, porProfessor: [...prof.entries()].sort((a, b) => b[1] - a[1]) }))
    .sort((a, b) => (a.conteudo === b.conteudo ? b.aulas2027 - a.aulas2027 : a.conteudo ? -1 : 1));
}

/**
 * As semanas de um professor em blocos do assunto dominante — o "ano numa tela".
 *
 * Um bloco de UMA semana colado a outro some dentro do vizinho com mais aulas: a visão é rápida, e o detalhe semana
 * a semana continua no nível de baixo. A revisão de fim de ano nunca é absorvida nem absorve.
 */
export function blocosDoProfessor(
  plano: PlanoDoAno, materia: string, professor: string, semanasDoAno: readonly number[],
): BlocoDoAno[] {
  const porSemana = new Map<number, Map<string, number>>();
  const nomes = new Map<string, Map<string, number>>();
  for (const item of itensDoProfessor(plano, materia, professor)) {
    for (const [w, n] of Object.entries(item.semanas)) {
      const semana = Number(w);
      const doDia = porSemana.get(semana) ?? new Map<string, number>();
      porSemana.set(semana, doDia);
      for (const [codigo, peso] of Object.entries(item.codigos)) {
        doDia.set(codigo, (doDia.get(codigo) ?? 0) + n * peso);
        const k = `${semana}|${codigo}`;
        const m = nomes.get(k) ?? new Map<string, number>();
        nomes.set(k, m);
        m.set(item.nome, (m.get(item.nome) ?? 0) + n * peso);
      }
    }
  }
  const pos = (w: number) => semanasDoAno.indexOf(w);
  const colado = (a: BlocoDoAno | undefined, b: BlocoDoAno | undefined) => !!a && !!b && pos(b.de) === pos(a.ate) + 1;

  const blocos: BlocoDoAno[] = [];
  for (const semana of semanasDoAno) {
    const doDia = porSemana.get(semana);
    if (!doDia) continue;
    const [codigo, aulas] = [...doDia.entries()].sort((a, b) => b[1] - a[1])[0] as [string, number];
    const ultimo = blocos[blocos.length - 1];
    const novo: BlocoDoAno = { codigo, de: semana, ate: semana, aulas, semanas: [semana], itens: [], grupo: '', rotulo: '' };
    if (ultimo && ultimo.codigo === codigo && colado(ultimo, novo)) {
      ultimo.ate = semana;
      ultimo.aulas += aulas;
      ultimo.semanas.push(semana);
    } else {
      blocos.push(novo);
    }
  }

  const juntarIguais = () => {
    for (let i = blocos.length - 1; i > 0; i--) {
      const a = blocos[i - 1] as BlocoDoAno;
      const b = blocos[i] as BlocoDoAno;
      if (a.codigo === b.codigo && colado(a, b)) {
        a.ate = b.ate;
        a.aulas += b.aulas;
        a.semanas.push(...b.semanas);
        blocos.splice(i, 1);
      }
    }
  };
  // O mais FRACO primeiro, e os iguais se juntam a cada passo: com Trigonometria · Polinômios · Trigonometria em três
  // semanas, quem some é a semana de Polinômios — começar pela esquerda engolia a Trigonometria e o bloco virava
  // "Polinômios".
  for (;;) {
    const candidatos = blocos
      .map((b, i) => ({ b, i }))
      .filter(({ b, i }) => b.semanas.length === 1 && b.codigo !== 'REVF'
        && ((colado(blocos[i - 1], b) && blocos[i - 1]?.codigo !== 'REVF') || (colado(b, blocos[i + 1]) && blocos[i + 1]?.codigo !== 'REVF')))
      .sort((x, y) => x.b.aulas - y.b.aulas);
    const escolhido = candidatos[0];
    if (!escolhido) break;
    const { b, i } = escolhido;
    const antes = colado(blocos[i - 1], b) && blocos[i - 1]?.codigo !== 'REVF' ? blocos[i - 1] : undefined;
    const depois = colado(b, blocos[i + 1]) && blocos[i + 1]?.codigo !== 'REVF' ? blocos[i + 1] : undefined;
    const alvo = (antes && depois ? (antes.aulas >= depois.aulas ? antes : depois) : antes ?? depois) as BlocoDoAno;
    if (alvo === antes) alvo.ate = b.ate;
    else alvo.de = b.de;
    alvo.aulas += b.aulas;
    alvo.semanas.push(...b.semanas);
    blocos.splice(i, 1);
    juntarIguais();
  }
  juntarIguais();

  const deTexto = MATERIAS_DE_TEXTO.has(materia);
  for (const b of blocos) {
    const soma = new Map<string, number>();
    for (const w of b.semanas) {
      for (const [nome, v] of nomes.get(`${w}|${b.codigo}`) ?? []) soma.set(nome, (soma.get(nome) ?? 0) + v);
    }
    b.itens = [...soma.entries()].sort((x, y) => y[1] - x[1]).map(([nome]) => nome);
    b.grupo = nomeDoGrupo(plano, materia, b.codigo);
    const peloProfessor = b.codigo === 'FORA' || b.codigo === '?' || (deTexto && b.codigo !== 'REVF');
    b.rotulo = peloProfessor ? (b.itens[0] ?? b.grupo) : b.grupo;
  }
  return blocos;
}

/**
 * As etapas de um professor: uma por assunto, na ordem em que o assunto aparece no ano. Quem alterna dois assuntos
 * (Marcelo, Geometria analítica e Funções reais) não vira 20 linhas. A revisão de fim de ano é a última.
 */
export function etapasDoProfessor(
  plano: PlanoDoAno, materia: string, professor: string, mesDaSemana: (w: number) => number, mesesDoAno: readonly number[],
): EtapaDoProfessor[] {
  const porCodigo = new Map<string, ItemDoPlano[]>();
  for (const item of itensDoProfessor(plano, materia, professor)) {
    const codigo = 'REVF' in item.codigos ? 'REVF' : codigoPrincipal(item);
    const lista = porCodigo.get(codigo) ?? [];
    porCodigo.set(codigo, lista);
    lista.push(item);
  }
  return [...porCodigo.entries()].map(([codigo, itens]) => {
    const nomes = new Set(itens.map((it) => it.nome));
    const rotulo = codigo === 'REVF'
      ? 'Revisão de fim de ano'
      // um item só (ou assunto sem grupo no SAS): o nome que o professor usa; vários: o nome do assunto
      : codigo === 'FORA' || codigo === '?' || nomes.size === 1
        ? (itens[0] as ItemDoPlano).nome
        : nomeDoGrupo(plano, materia, codigo);
    return {
      codigo,
      itens,
      aulas: itens.reduce((s, it) => s + it.aulas_2027, 0),
      rotulo,
      meses: mesesDoAno.map((mes) => itens.reduce((s, it) => s + aulasNoMes(it, mes, mesDaSemana), 0)),
    };
  });
}

export function aulasNoMes(item: ItemDoPlano, mes: number, mesDaSemana: (w: number) => number): number {
  return Object.entries(item.semanas).reduce((t, [w, n]) => t + (mesDaSemana(Number(w)) === mes ? n : 0), 0);
}

/** O calendário de 2027: semanas, mês de cada semana, recesso e semanas de aula até uma data. */
export function calendarioDoPlano(plano: PlanoDoAno) {
  const { semanas, marcos } = plano.calendario_2027;
  const lista = semanas.map((s) => s.semana);
  const inicio = new Map(semanas.map((s) => [s.semana, s.inicio]));
  const mesDaSemana = (w: number) => Number((inicio.get(w) ?? '2027-01-01').slice(5, 7)) - 1;
  const ehRecesso = (w: number) => marcos.some((m) => m.semana === w && m.tipo === 'recesso');
  const deAula = (w: number) => w >= 3 && w <= 43 && !ehRecesso(w);
  return {
    semanas: lista,
    marcos,
    inicio: (w: number) => inicio.get(w) ?? '',
    mesDaSemana,
    mesesDoAno: [...new Set(lista.map(mesDaSemana))],
    ehRecesso,
    semanasDeAula: lista.filter(deAula).length,
    semanasDeAulaAntes: (w: number | undefined) => (w == null ? 0 : lista.filter((x) => deAula(x) && x < w).length),
    semanaDaProva: (vestibular: 'IME' | 'ITA') =>
      marcos.find((m) => m.tipo === 'prova' && m.rotulo.includes(vestibular))?.semana,
  };
}

export type AbaDoCronograma = 'ano' | 'materias' | 'quem' | 'professor';

export interface PassoDaApresentacao {
  aba: AbaDoCronograma;
  materia?: string;
  professor?: string;
  rotulo: string;
}

/** Os passos da apresentação: o ano; depois, para cada matéria, os assuntos, quem dá, e cada professor. */
export function passosDaApresentacao(plano: PlanoDoAno): PassoDaApresentacao[] {
  const passos: PassoDaApresentacao[] = [{ aba: 'ano', rotulo: 'O ano' }];
  for (const { materia } of plano.materias) {
    passos.push({ aba: 'materias', materia, rotulo: `${materia} · assuntos` });
    passos.push({ aba: 'quem', materia, rotulo: `${materia} · quem dá cada assunto` });
    for (const p of professoresDaMateria(plano, materia)) {
      passos.push({ aba: 'professor', materia, professor: p.professor, rotulo: `${materia} · ${p.professor}` });
    }
  }
  return passos;
}

/** `2027-01-18` → `18/01`. Fatia a string, sem passar por `Date`. */
export function dataCurta(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}
