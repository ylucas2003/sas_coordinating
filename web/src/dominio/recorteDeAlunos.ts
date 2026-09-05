// O RECORTE NOMEADO da lista de 900 — as quatro perguntas de entrada.
//
// A lista de alunos tem dois estratos de recorte, e eles não são a mesma
// coisa:
//
//   o PENEIRAMENTO  turma, sede, busca. Diz *quem cabe na tela*, não tem
//                   nome, e cada pessoa monta o seu.
//   o RECORTE       "zona de risco", "bottom 30". Tem NOME, responde a uma
//                   pergunta (C1) e é o que sobrevive à entrada na ficha —
//                   por isso ele mora na URL, e não em `useState`.
//
// Isto aqui é o segundo. Está em `dominio/` porque é regra com casos —
// extremos disjuntos, N que acompanha o acervo, nulo que não pode encabeçar
// nada — e regra com casos é o que quebra em silêncio quando mora dentro de
// um componente.
//
// ⚠️ Nada aqui decide corte. A zona vem classificada do servidor, sob a régua
// da casa (`stats/classificacao.py::_classificar_zona_por_materia`, que usa
// `CRITERIO_DA_CASA`); as médias vêm prontas de `GET /alunos`. Reimplementar
// a régua em TypeScript é a proibição registrada da Sprint 2 (docs/18 §1.2).

import type { Aluno } from '../tipos/dominio';

/** As quatro perguntas de entrada, na ordem em que a faixa as oferece. */
export type Recorte = 'risco' | 'sem-nota' | 'bottom' | 'top';

export const RECORTES: readonly Recorte[] = ['risco', 'sem-nota', 'bottom', 'top'];

/** `?recorte=` da URL → recorte, ou `null`. Valor desconhecido não recorta nada. */
export function lerRecorte(valor: string | null | undefined): Recorte | null {
  return RECORTES.includes(valor as Recorte) ? (valor as Recorte) : null;
}

/**
 * A média do ano — o número pelo qual os extremos são medidos.
 *
 * **Sem fallback para `aluno.media` de propósito.** `media` é a média RECENTE
 * da classificação (janela de N simulados, exige duas notas); misturar as duas
 * num mesmo ranking faria vizinhos de linha serem comparados por réguas
 * diferentes, que é a mentira gráfica que a R6 existe para impedir. Sem
 * `medias` o aluno simplesmente não entra em extremo nenhum.
 */
export function mediaDoAno(aluno: Aluno): number | null {
  return aluno.medias?.ano.geral ?? null;
}

/**
 * Não tem nota no ciclo de referência — a pergunta do card "SILÊNCIO".
 *
 * É medido contra o ÚLTIMO ciclo, que é o mesmo para todas as linhas (quem o
 * escolheu foi o servidor). "O último ciclo de cada aluno" faria a coluna
 * comparar provas diferentes entre linhas vizinhas.
 *
 * ⚠️ Aluno sem `medias` devolve `false`, e não `true`: `undefined` quer dizer
 * "este aluno não veio das rotas de coordenação", que é desconhecimento, não
 * ausência de nota. Contá-lo como silêncio mandaria o coordenador procurar um
 * problema que não existe.
 */
export function semNotaNoUltimoCiclo(aluno: Aluno): boolean {
  if (!aluno.medias) return false;
  return aluno.medias.ultimoCiclo.geral == null;
}

/** Os dois extremos da lista por média do ano, e quantos cabem em cada um. */
export interface Extremos {
  /**
   * Quantos entram em cada extremo — o N que os rótulos "Top N"/"Bottom N"
   * leem. `0` quando não há ninguém com média, e aí os dois conjuntos são
   * vazios: um "Top 1" de uma lista sem notas seria um rótulo sem gente.
   */
  n: number;
  /** Ids dos N melhores. */
  top: ReadonlySet<string>;
  /** Ids dos N piores. */
  baixo: ReadonlySet<string>;
}

const SEM_EXTREMOS: Extremos = { n: 0, top: new Set(), baixo: new Set() };

/**
 * Os N melhores e os N piores por média do ano, **disjuntos por construção**.
 *
 * O N não é fixo: ele é no máximo metade dos que têm nota, limitado pelo teto.
 * É a única forma de os dois conjuntos nunca se cruzarem — com 40 alunos e um
 * "top 30" fixo, 20 pessoas estariam nos dois extremos ao mesmo tempo, e a
 * lista diria que o mesmo aluno é o melhor e o pior.
 *
 * Quem não tem média fica de fora dos dois: ele não foi mal nem bem, não foi
 * medido.
 */
export function extremosPorMedia(alunos: readonly Aluno[], teto = 30): Extremos {
  const comNota = alunos
    .map((aluno) => ({ id: aluno.id, media: mediaDoAno(aluno) }))
    .filter((linha): linha is { id: string; media: number } => linha.media != null)
    .sort((a, b) => b.media - a.media);

  const n = Math.min(teto, Math.floor(comNota.length / 2));
  if (n === 0) return SEM_EXTREMOS;

  return {
    n,
    top: new Set(comNota.slice(0, n).map((l) => l.id)),
    baixo: new Set(comNota.slice(-n).map((l) => l.id)),
  };
}

/** O aluno pertence a este recorte? */
export function noRecorte(aluno: Aluno, recorte: Recorte, extremos: Extremos): boolean {
  switch (recorte) {
    case 'risco':
      return aluno.zona === 'risco';
    case 'sem-nota':
      return semNotaNoUltimoCiclo(aluno);
    case 'top':
      return extremos.top.has(aluno.id);
    case 'bottom':
      return extremos.baixo.has(aluno.id);
  }
}

/** A lista recortada. `null` devolve a lista inteira, sem copiar à toa. */
export function aplicarRecorte(
  alunos: readonly Aluno[],
  recorte: Recorte | null,
  extremos: Extremos,
): readonly Aluno[] {
  if (!recorte) return alunos;
  return alunos.filter((aluno) => noRecorte(aluno, recorte, extremos));
}

/**
 * Quantos alunos cada recorte entregaria — o dado vivo dos cards (C2).
 *
 * Contado sobre a lista que o card de fato vai entregar (já peneirada por
 * turma, sede e busca), porque um card que promete 23 e entrega 4 é pior do
 * que um card sem número.
 */
export function contarRecortes(
  alunos: readonly Aluno[],
  extremos: Extremos,
): Record<Recorte, number> {
  return {
    risco: alunos.filter((a) => a.zona === 'risco').length,
    'sem-nota': alunos.filter(semNotaNoUltimoCiclo).length,
    top: extremos.n,
    bottom: extremos.n,
  };
}

/**
 * Quantos, dentro do recorte de risco, ainda estão caindo.
 *
 * É a INTERSEÇÃO, não uma segunda contagem solta: os dois números do subtítulo
 * têm de ser decomposição do mesmo conjunto que o card aplica, senão o card
 * soma duas populações diferentes na mesma frase.
 */
export function contarRiscoCaindo(alunos: readonly Aluno[]): number {
  return alunos.filter((a) => a.zona === 'risco' && a.tendencia === 'caindo').length;
}

/** A média das médias do ano de um conjunto — o número do card de extremo. */
export function mediaDasMedias(alunos: readonly Aluno[]): number | null {
  const valores = alunos.map(mediaDoAno).filter((m): m is number => m != null);
  if (!valores.length) return null;
  return valores.reduce((soma, v) => soma + v, 0) / valores.length;
}
