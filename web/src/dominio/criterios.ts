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
