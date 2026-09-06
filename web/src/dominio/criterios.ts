// Leitura da régua de corte no front.
//
// ⚠️ Isto **não** implementa a regra — implementá-la em TypeScript é
// justamente o que a Sprint 2 proibiu (docs/18 §1.2), depois de a mesma regra
// existir em três lugares e divergir. O servidor resolve `cortes`,
// `corteGenerico`, `corteMedia` e `eliminatorias` em `_descrever_criterio`; o
// que está aqui é a consulta a esse resultado, com o encadeamento de fallback
// num lugar só em vez de repetido em cada tela.

import type { CriterioClassificacao } from '../tipos/dominio';

/**
 * A régua que vale quando ninguém escolheu — `stats/criterios.py::CRITERIO_DA_CASA`.
 *
 * ⚠️ O slug estava CRAVADO em oito lugares, e a varredura de consistência do
 * docs/39 achou dois nomes para ele criados na mesma refatoração:
 * `REGUA_DA_CASA` em `telas/Alunos` e `REGUA_DO_PAINEL` em `telas/Painel`, com
 * o mesmo valor. Dois nomes para uma constante é a porta de entrada de duas
 * telas passarem a discordar sobre qual régua está em vigor — e a régua é
 * exatamente o que não pode divergir entre telas (docs/18 §1.2).
 */
export const REGUA_DA_CASA = 'tio-leo';

/**
 * A régua da casa entre as disponíveis, com o resto honesto.
 *
 * `criterios[0]` existe para o caso de a régua da casa ter sido renomeada no
 * servidor: sem ele a tela ficaria sem corte nenhum por causa de um slug, e
 * "sem corte" é pior que "corte de outra régua, dito por extenso" — as telas
 * que chamam isto escrevem o nome do que encontraram ao lado do dado.
 */
export function reguaDaCasa(
  criterios: readonly CriterioClassificacao[],
): CriterioClassificacao | null {
  return criterios.find((c) => c.slug === REGUA_DA_CASA) ?? criterios[0] ?? null;
}

/**
 * O mínimo que a régua exige nesta matéria, em 0–10.
 *
 * A cascata é a mesma do backend: mínimo da matéria → mínimo de "qualquer
 * disciplina" → exigência da média. `null` quando a régua não pede nada que
 * se aplique — e aí não há linha honesta a desenhar.
 */
export function corteDaMateria(
  criterio: CriterioClassificacao | null | undefined,
  materia: string | null | undefined,
): number | null {
  if (!criterio) return null;
  if (materia) {
    const especifico = criterio.cortes?.[materia];
    if (especifico != null) return especifico;
  }
  return criterio.corteGenerico ?? criterio.corteMedia ?? null;
}

/** A régua elimina sozinho quem falha nesta matéria? */
export function eliminaSozinho(
  criterio: CriterioClassificacao | null | undefined,
  materia: string | null | undefined,
): boolean {
  if (!criterio || !materia) return false;
  return (criterio.eliminatorias ?? []).includes(materia);
}

/** "corte 4,0" / "corte 4,2 (eliminatório)" — o rótulo que vai no gráfico. */
export function rotuloDoCorte(valor: number, elimina: boolean): string {
  const numero = valor.toFixed(1).replace('.', ',');
  return elimina ? `corte ${numero} (eliminatório)` : `corte ${numero}`;
}
