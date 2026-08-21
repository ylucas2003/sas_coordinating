// Filtragem e contagem dos simulados — lógica pura, reusada pela tela de
// Simulados e pela ficha do aluno. Testada em simulados.test.ts.
//
// Os filtros são AND entre categorias e OR dentro de uma categoria.

import type { Simulado, TipoSimulado } from '../tipos/dominio';

export interface FiltroSimulados {
  ciclos: ReadonlySet<number>;
  materias: ReadonlySet<string>;
  fases: ReadonlySet<TipoSimulado>;
  vestibulares: ReadonlySet<string>;
  datas: ReadonlySet<string>;
}

export const FILTRO_VAZIO: FiltroSimulados = {
  ciclos: new Set(),
  materias: new Set(),
  fases: new Set(),
  vestibulares: new Set(),
  datas: new Set(),
};

export function algumFiltroAtivo(f: FiltroSimulados): boolean {
  return f.ciclos.size + f.materias.size + f.fases.size + f.vestibulares.size + f.datas.size > 0;
}

/** Rótulo curto de um ciclo: "C3 · ITA". */
export function rotuloCiclo(ordem: number | null, vestibular: string | null): string {
  if (ordem == null) return 'Sem ciclo';
  return vestibular ? `C${ordem} · ${vestibular}` : `C${ordem}`;
}

/**
 * Um simulado passa se atende a todas as categorias com seleção. `ignorada`
 * pula uma categoria — é o que permite contar sem o filtro anular a si mesmo.
 */
function passa(s: Simulado, f: FiltroSimulados, ignorada?: keyof FiltroSimulados): boolean {
  if (ignorada !== 'ciclos' && f.ciclos.size && !f.ciclos.has(s.cicloOrdem as number)) return false;
  if (ignorada !== 'materias' && f.materias.size && !f.materias.has(s.materia?.codigo as string)) return false;
  if (ignorada !== 'fases' && f.fases.size && !f.fases.has(s.tipo as TipoSimulado)) return false;
  if (ignorada !== 'vestibulares' && f.vestibulares.size && !f.vestibulares.has(s.vestibularAlvo as string)) return false;
  if (ignorada !== 'datas' && f.datas.size && !f.datas.has(s.dataAplicacao)) return false;
  return true;
}

export function aplicarFiltros(simulados: readonly Simulado[], f: FiltroSimulados): Simulado[] {
  return simulados.filter((s) => passa(s, f));
}

export interface OpcoesSimulados {
  ciclos: Array<{ ordem: number; label: string }>;
  materias: Array<{ codigo: string; nome: string }>;
  fases: Array<{ valor: TipoSimulado; label: string }>;
  vestibulares: string[];
}

export function montarOpcoes(simulados: readonly Simulado[]): OpcoesSimulados {
  const ciclosMapa = new Map<number, string | null>();
  for (const s of simulados) {
    if (s.cicloOrdem == null) continue;
    if (!ciclosMapa.has(s.cicloOrdem)) ciclosMapa.set(s.cicloOrdem, s.vestibularAlvo);
  }
  const ciclos = [...ciclosMapa.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([ordem, vest]) => ({ ordem, label: rotuloCiclo(ordem, vest) }));

  const materiasMapa = new Map<string, string>();
  for (const s of simulados) {
    if (s.materia) materiasMapa.set(s.materia.codigo, s.materia.nome);
  }
  const materias = [...materiasMapa.entries()]
    .sort((a, b) => a[1].localeCompare(b[1]))
    .map(([codigo, nome]) => ({ codigo, nome }));

  const vestibulares = [...new Set(simulados.map((s) => s.vestibularAlvo).filter(Boolean))]
    .sort() as string[];

  return {
    ciclos,
    materias,
    fases: [
      { valor: 'fase_1', label: 'Fase 1' },
      { valor: 'fase_2', label: 'Fase 2' },
    ],
    vestibulares,
  };
}

export interface ContagensSimulados {
  ciclo: Map<number, number>;
  materia: Map<string, number>;
  fase: Map<string, number>;
  vestibular: Map<string, number>;
}

/**
 * Contagem por chip. Cada eixo conta ignorando o próprio filtro — senão o
 * número exibido seria sempre o total já selecionado, e o usuário não veria
 * o que ganharia ao marcar outra opção.
 */
export function contarPorChip(
  simulados: readonly Simulado[],
  f: FiltroSimulados,
): ContagensSimulados {
  const ciclo = new Map<number, number>();
  const materia = new Map<string, number>();
  const fase = new Map<string, number>();
  const vestibular = new Map<string, number>();

  for (const s of simulados) {
    if (s.cicloOrdem != null && passa(s, f, 'ciclos')) {
      ciclo.set(s.cicloOrdem, (ciclo.get(s.cicloOrdem) ?? 0) + 1);
    }
    if (s.materia && passa(s, f, 'materias')) {
      materia.set(s.materia.codigo, (materia.get(s.materia.codigo) ?? 0) + 1);
    }
    if (s.tipo && passa(s, f, 'fases')) {
      fase.set(s.tipo, (fase.get(s.tipo) ?? 0) + 1);
    }
    if (s.vestibularAlvo && passa(s, f, 'vestibulares')) {
      vestibular.set(s.vestibularAlvo, (vestibular.get(s.vestibularAlvo) ?? 0) + 1);
    }
  }

  return { ciclo, materia, fase, vestibular };
}

/**
 * Datas que o calendário deve colorir: as dos simulados que passariam por
 * todos os filtros EXCETO o de data — do contrário o filtro de data
 * esconderia as outras datas selecionáveis.
 */
export function datasDoCalendario(
  simulados: readonly Simulado[],
  f: FiltroSimulados,
): Set<string> {
  return new Set(
    aplicarFiltros(simulados, { ...f, datas: new Set() })
      .map((s) => s.dataAplicacao)
      .filter(Boolean),
  );
}
