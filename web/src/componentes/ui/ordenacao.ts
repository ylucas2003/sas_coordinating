// Ordenação das tabelas de lista — lógica pura, testada em ordenacao.test.ts.
//
// Ordena no cliente: os volumes são pequenos (centenas de linhas) e já vêm
// inteiros para o browser, sem paginação — a API não precisa saber de ordenação.
//
// Duas regras que a ordenação ingênua erra e que são o motivo deste módulo
// existir:
//
//  1. Nulos afundam nos DOIS sentidos. Aluno sem média não pode encabeçar o
//     "pior desempenho" — ele não foi mal, ele não tem dado.
//  2. Coluna categórica tem ordem semântica, não alfabética. Zona é
//     Risco → Cinzenta → Top; ordenar por alfabeto ("Cinzenta, Risco, Top")
//     não significa nada. Use `tipo: 'ordinal'` com a lista `ordem`.

export type TipoColuna = 'texto' | 'numero' | 'ordinal';

export interface ColunaTabela<T> {
  /** Identificador da coluna. */
  chave: string;
  label: string;
  /** Default `true`; `false` para colunas de sparkline ou de ação. */
  ordenavel?: boolean;
  /** Extrai o valor de ordenação. */
  valor?: (item: T) => unknown;
  tipo?: TipoColuna;
  /** Para `tipo: 'ordinal'`: a ordem semântica dos valores. */
  ordem?: readonly unknown[];
  /** Classe extra no `<th>`. */
  classe?: string;
}

export interface Ordenacao {
  chave: string;
  dir: 'asc' | 'desc';
}

/** Sentinelas de vazio: não invertem com a direção, afundam sempre. */
const VAZIO_DEPOIS = Number.POSITIVE_INFINITY;
const VAZIO_ANTES = Number.NEGATIVE_INFINITY;

function comparar<T>(coluna: ColunaTabela<T>, a: T, b: T): number {
  const va = coluna.valor ? coluna.valor(a) : null;
  const vb = coluna.valor ? coluna.valor(b) : null;

  const vazioA = va == null || va === '';
  const vazioB = vb == null || vb === '';
  if (vazioA && vazioB) return 0;
  if (vazioA) return VAZIO_DEPOIS;
  if (vazioB) return VAZIO_ANTES;

  if (coluna.tipo === 'numero') return Number(va) - Number(vb);
  if (coluna.tipo === 'ordinal') {
    const ordem = coluna.ordem ?? [];
    return ordem.indexOf(va) - ordem.indexOf(vb);
  }
  return String(va).localeCompare(String(vb), 'pt-BR', { numeric: true });
}

/** Cópia ordenada. Sem ordenação ativa, devolve a ordem original. */
export function ordenarLinhas<T>(
  itens: readonly T[],
  colunas: ReadonlyArray<ColunaTabela<T>>,
  ordenacao: Ordenacao | null,
): T[] {
  if (!ordenacao?.chave) return itens.slice();

  const coluna = colunas.find((c) => c.chave === ordenacao.chave);
  if (!coluna || coluna.ordenavel === false) return itens.slice();

  const sinal = ordenacao.dir === 'desc' ? -1 : 1;
  return itens.slice().sort((a, b) => {
    const r = comparar(coluna, a, b);
    if (r === VAZIO_DEPOIS) return 1;
    if (r === VAZIO_ANTES) return -1;
    return r * sinal;
  });
}

/**
 * Alterna a ordenação de uma coluna: asc → desc → asc. Clicar numa coluna
 * diferente começa em asc.
 */
export function proximaOrdenacao(ordenacao: Ordenacao | null, chave: string): Ordenacao {
  if (ordenacao?.chave !== chave) return { chave, dir: 'asc' };
  return { chave, dir: ordenacao.dir === 'asc' ? 'desc' : 'asc' };
}
