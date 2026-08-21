// Filtragem dos ciclos — lógica pura, testada em ciclos.test.ts.

import type { Ciclo } from '../tipos/dominio';

export interface Periodo {
  inicio: string | null;
  fim: string | null;
}

export interface FiltroCiclos {
  vestibulares: ReadonlySet<string>;
  anos: ReadonlySet<number>;
  periodo: Periodo;
}

export const FILTRO_CICLOS_VAZIO: FiltroCiclos = {
  vestibulares: new Set(),
  anos: new Set(),
  periodo: { inicio: null, fim: null },
};

export function algumFiltroAtivo(f: FiltroCiclos): boolean {
  return f.vestibulares.size + f.anos.size > 0 || !!f.periodo.inicio || !!f.periodo.fim;
}

/**
 * Um ciclo entra no recorte se o período dele ENCOSTA no intervalo — não
 * precisa estar contido. Contenção descartaria um ciclo de 08/02 a 08/03 num
 * filtro de 01/03 a 30/04, que é justamente o caso que interessa ver.
 */
export function intersectaPeriodo(ciclo: Ciclo, periodo: Periodo): boolean {
  if (!periodo.inicio && !periodo.fim) return true;
  // Ciclo sem período não tem como intersectar. Hoje não existe nenhum no
  // banco (o período vem do min/max das datas dos simulados), mas um ciclo
  // criado sem simulado cairia aqui.
  if (!ciclo.periodoInicio || !ciclo.periodoFim) return false;
  if (periodo.fim && ciclo.periodoInicio > periodo.fim) return false;
  if (periodo.inicio && ciclo.periodoFim < periodo.inicio) return false;
  return true;
}

function passa(c: Ciclo, f: FiltroCiclos, ignorada?: 'vestibulares' | 'anos'): boolean {
  if (ignorada !== 'vestibulares' && f.vestibulares.size && !f.vestibulares.has(c.vestibularAlvo as string)) {
    return false;
  }
  if (ignorada !== 'anos' && f.anos.size && !f.anos.has(c.anoLetivo)) return false;
  return intersectaPeriodo(c, f.periodo);
}

export function aplicarFiltros(ciclos: readonly Ciclo[], f: FiltroCiclos): Ciclo[] {
  return ciclos.filter((c) => passa(c, f));
}

export function montarOpcoes(ciclos: readonly Ciclo[]) {
  const vestibulares = [...new Set(ciclos.map((c) => c.vestibularAlvo).filter(Boolean))]
    .sort() as string[];
  const anos = [...new Set(ciclos.map((c) => c.anoLetivo).filter(Boolean))].sort((a, b) => b - a);
  return { vestibulares, anos };
}

/** Contagem por chip ignorando o próprio eixo. O período conta sempre, já que não é uma lista de opções. */
export function contarPorChip(ciclos: readonly Ciclo[], f: FiltroCiclos) {
  const vestibular = new Map<string, number>();
  const ano = new Map<number, number>();

  for (const c of ciclos) {
    if (c.vestibularAlvo && passa(c, f, 'vestibulares')) {
      vestibular.set(c.vestibularAlvo, (vestibular.get(c.vestibularAlvo) ?? 0) + 1);
    }
    if (c.anoLetivo && passa(c, f, 'anos')) {
      ano.set(c.anoLetivo, (ano.get(c.anoLetivo) ?? 0) + 1);
    }
  }
  return { vestibular, ano };
}
