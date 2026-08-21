// Séries do gráfico de evolução do aluno — lógica pura, testada em
// evolucaoAluno.test.ts.

import type { PontoEvolucao, SerieEvolucao } from '../componentes/ui/LinhaEvolucao';
import type { FiltroSimulados } from './simulados';
import type { Simulado } from '../tipos/dominio';

/**
 * Corte adaptativo. Inglês na Fase 1 do ITA é eliminatório com corte 5; nas
 * demais matérias o corte de avaliação é 4. Quando o filtro recorta
 * exatamente esse caso, mostramos o corte correspondente.
 */
export function decidirCorte(f: FiltroSimulados): { valor: number; rotulo: string } {
  const soIngles = f.materias.size === 1 && f.materias.has('ingles');
  const soITA = f.vestibulares.size === 1 && f.vestibulares.has('ITA');
  const soF1 = f.fases.size === 1 && f.fases.has('fase_1');

  if (soIngles && soITA && soF1) return { valor: 5, rotulo: 'corte 5 (eliminatório)' };
  return { valor: 4, rotulo: 'corte 4' };
}

/**
 * Monta as séries do gráfico a partir dos simulados filtrados e das notas do
 * aluno.
 *
 * Com matéria selecionada, gera uma linha por matéria; sem, agrega numa linha
 * única (média do aluno por ciclo). Assim é o próprio filtro que decide o
 * nível de detalhe, em vez de um controle separado.
 */
export function montarSeries(
  simuladosFiltrados: readonly Simulado[],
  notasPorSimulado: ReadonlyMap<string, number>,
  filtro: FiltroSimulados,
): SerieEvolucao[] {
  const visiveis = simuladosFiltrados.filter((s) => notasPorSimulado.has(s.id));

  if (filtro.materias.size > 0) {
    const porMateria = new Map<string, SerieEvolucao>();

    for (const s of visiveis) {
      const codigo = s.materia?.codigo;
      if (!codigo) continue;
      if (!porMateria.has(codigo)) {
        porMateria.set(codigo, { nome: s.materia!.nome, pontos: [] });
      }
      const nota = notasPorSimulado.get(s.id)!;
      porMateria.get(codigo)!.pontos.push({
        cicloOrdem: s.cicloOrdem,
        vestibularAlvo: s.vestibularAlvo,
        nota,
        mediaTurma: s.media,
        simulado: s.nome,
        simuladoId: s.id,
        dataAplicacao: s.dataAplicacao,
        tipo: s.tipo,
        materia: s.materia!.nome,
        // Zero com presença marcada é quase sempre abandono, não desempenho.
        abandonoProvavel: nota === 0,
      });
    }

    return [...porMateria.values()].sort((a, b) => a.nome.localeCompare(b.nome));
  }

  // Sem filtro de matéria: uma linha só, agregando por ciclo.
  interface Acumulador {
    cicloOrdem: number;
    vestibularAlvo: string | null;
    notas: number[];
    medias: number[];
    simulados: string[];
    datas: string[];
    tipos: Set<string>;
  }

  const porCiclo = new Map<number, Acumulador>();

  for (const s of visiveis) {
    if (s.cicloOrdem == null) continue;
    const nota = notasPorSimulado.get(s.id);
    if (nota == null) continue;

    if (!porCiclo.has(s.cicloOrdem)) {
      porCiclo.set(s.cicloOrdem, {
        cicloOrdem: s.cicloOrdem,
        vestibularAlvo: s.vestibularAlvo,
        notas: [], medias: [], simulados: [], datas: [], tipos: new Set(),
      });
    }
    const ag = porCiclo.get(s.cicloOrdem)!;
    ag.notas.push(nota);
    if (s.media != null) ag.medias.push(s.media);
    ag.simulados.push(s.rotuloCurto || s.nome);
    ag.datas.push(s.dataAplicacao);
    if (s.tipo) ag.tipos.add(s.tipo);
  }

  const media = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

  const pontos: PontoEvolucao[] = [...porCiclo.values()].map((ag) => ({
    cicloOrdem: ag.cicloOrdem,
    vestibularAlvo: ag.vestibularAlvo,
    nota: media(ag.notas),
    mediaTurma: ag.medias.length ? media(ag.medias) : null,
    simulado: `${ag.simulados.length} simulado(s) do ciclo`,
    simuladoId: null,
    dataAplicacao: [...ag.datas].sort()[0],
    // Fase só faz sentido no tooltip se o ciclo inteiro for de uma fase só.
    tipo: ag.tipos.size === 1 ? [...ag.tipos][0] : null,
    materia: 'Média do aluno',
    abandonoProvavel: false,
  }));

  return [{ nome: 'Média do aluno por ciclo', pontos }];
}

/** Eixo X do gráfico: os ciclos presentes no recorte, em ordem. */
export function montarEixoCiclos(
  simuladosFiltrados: readonly Simulado[],
  rotulo: (ordem: number, vestibular: string | null) => string,
): Array<{ ordem: number; label: string }> {
  const vestPorOrdem = new Map<number, string | null>();
  for (const s of simuladosFiltrados) {
    if (s.cicloOrdem != null && !vestPorOrdem.has(s.cicloOrdem)) {
      vestPorOrdem.set(s.cicloOrdem, s.vestibularAlvo);
    }
  }
  return [...vestPorOrdem.keys()]
    .sort((a, b) => a - b)
    .map((ordem) => ({ ordem, label: rotulo(ordem, vestPorOrdem.get(ordem) ?? null) }));
}
