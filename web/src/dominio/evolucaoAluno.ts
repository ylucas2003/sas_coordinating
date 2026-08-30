// Séries do gráfico de evolução do aluno — lógica pura, testada em
// evolucaoAluno.test.ts.

import type { PontoEvolucao, SerieEvolucao } from '../componentes/ui/LinhaEvolucao';
import { corteDaMateria, eliminaSozinho, rotuloDoCorte } from './criterios';
import type { FiltroSimulados } from './simulados';
import type { CriterioClassificacao, Simulado } from '../tipos/dominio';

/**
 * Qual linha de corte desenhar, dado o recorte do filtro e a régua em uso.
 *
 * Aqui havia a terceira cópia da regra de corte — `if (inglês && ITA && F1)
 * return 5; return 4` —, sobrevivente da limpeza da Sprint 2 porque ela olhou
 * o Painel e não os gráficos. Os dois números estavam errados: a régua da casa
 * põe o inglês em 4,0 e o ITA pede 5 de 12 (§4.6.2.1), que é 4,17.
 *
 * Esta função não decide mais o corte: ela **escolhe qual** dos cortes que o
 * servidor já resolveu se aplica ao recorte aberto. Com uma matéria só
 * selecionada, o corte é o dela; com várias ou nenhuma, não há linha única
 * honesta a desenhar e cai no corte da média.
 */
export function decidirCorte(
  f: FiltroSimulados,
  criterio?: CriterioClassificacao | null,
): { valor: number; rotulo: string } | null {
  if (!criterio) return null;

  // Três casos, e o do meio é o que estava errado:
  //   nenhuma matéria → as séries são a MÉDIA do aluno por ciclo, e o corte é
  //                     o que a régua exige da média;
  //   uma matéria     → o corte daquela matéria;
  //   várias          → cada série é uma matéria com notas individuais, não
  //                     uma média. Desenhar a exigência de média sobre elas
  //                     põe a linha em 5,0 quando a régua aprova com 4,0.
  //                     O corte comum é o genérico ("qualquer disciplina").
  const materia = f.materias.size === 1 ? [...f.materias][0] : null;
  const valor = f.materias.size === 0
    ? criterio.corteMedia ?? criterio.corteGenerico ?? null
    : corteDaMateria(criterio, materia);
  if (valor == null) return null;

  return { valor, rotulo: rotuloDoCorte(valor, eliminaSozinho(criterio, materia)) };
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

    for (const serie of porMateria.values()) serie.pontos.sort(cronologica);
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

  pontos.sort(cronologica);
  return [{ nome: 'Média do aluno por ciclo', pontos }];
}

/**
 * Do mais antigo para o mais recente.
 *
 * `GET /simulados` devolve `.order("data_aplicacao", desc=True)` — mais NOVO
 * primeiro — e nada entre a API e aqui reordena. O gráfico escapava porque
 * `LinhaEvolucao` ordena por `cicloOrdem` antes de desenhar; quem lia o array
 * cru era a frase da camada leigo, que dizia "subiu de 4,0 para 8,0" acima de
 * uma linha que descia. Ordenar na origem conserta os dois de uma vez.
 */
function cronologica(a: PontoEvolucao, b: PontoEvolucao): number {
  const ordem = (a.cicloOrdem ?? 0) - (b.cicloOrdem ?? 0);
  if (ordem !== 0) return ordem;
  return (a.dataAplicacao ?? '').localeCompare(b.dataAplicacao ?? '');
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
