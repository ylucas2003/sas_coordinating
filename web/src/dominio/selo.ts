// O selo de nota — como uma nota é DESENHADA contra o corte da régua.
//
// Substitui o semáforo verde/âmbar/vermelho pelas regras R1, R3 e R4 do
// `docs/brief-claude-design-coordenacao.md`:
//
//   R1 · PREENCHIDO É ACIMA, VAZADO É ABAIXO. A varredura deixa de ser leitura
//        de matiz e vira leitura de FORMA — um aluno em risco é uma linha de
//        buracos numa grade cheia, e o olho acha um buraco mais rápido do que
//        acha um vermelho no meio de outros vermelhos. Funciona no daltonismo
//        (~8% dos homens) e funciona impresso em preto e branco, que é como o
//        dossiê do ciclo sai.
//
//   R3 · A INTENSIDADE CARREGA A DISTÂNCIA. Três baldes onde o dado é contínuo
//        fazem 3,9 e 0,4 virarem o mesmo vermelho. Aqui a distância modula a
//        saturação (acima) e a espessura do contorno (abaixo), em escala
//        sequencial de matiz único ancorada NO CORTE — nunca divergente.
//
//   R4 · ALERTA SÓ NA ETIQUETA. O vermelho não pinta célula, linha, cartão nem
//        número; ele diz a distância, e só.
//
// ⚠️ Isto NÃO implementa a régua. O corte vem resolvido do servidor e é lido
// por `dominio/criterios.ts` — reimplementar o encadeamento em TypeScript foi
// o que a Sprint 2 proibiu, depois de a mesma regra existir em três lugares e
// divergir (docs/18 §1.2). O que está aqui é a APRESENTAÇÃO de uma diferença
// que o servidor já decidiu.

import { corteDaMateria } from './criterios';
import type { AlunoClassificado, CriterioClassificacao } from '../tipos/dominio';

/** Como o selo deve ser desenhado. */
export type EstadoDoSelo = 'acima' | 'no-corte' | 'abaixo' | 'sem-dado';

export interface Selo {
  estado: EstadoDoSelo;
  /**
   * 0…1, a distância normalizada até a ponta da escala.
   *
   * Acima do corte, satura o preenchimento; abaixo, engrossa e escurece o
   * contorno. Os dois lados são normalizados pelo espaço que cada um tem —
   * acima sobra `10 − corte`, abaixo sobra `corte` — para que "encostado no
   * corte" pareça igual dos dois lados, que é o que a régua quer dizer.
   */
  intensidade: number;
  /** `nota − corte`. Negativo abaixo. `null` quando não há nota ou não há régua. */
  distancia: number | null;
  /** A etiqueta de distância, só abaixo do corte: "−1,4". Vazia nos demais. */
  etiqueta: string;
}

const SEM_DADO: Selo = { estado: 'sem-dado', intensidade: 0, distancia: null, etiqueta: '' };

/** "−1,4" · o menos é U+2212, não hífen: no numeral tabular o hífen fica curto. */
export function formatarDistancia(distancia: number, casas = 1): string {
  const texto = Math.abs(distancia).toFixed(casas).replace('.', ',');
  return distancia < 0 ? `−${texto}` : `+${texto}`;
}

/**
 * O selo de uma nota contra o corte da matéria.
 *
 * `corte` vem de `criterios.corteDaMateria(...)`. Sem corte não há régua e não
 * há nada honesto a desenhar: o selo fica neutro, e não "aprovado".
 *
 * Estar EXATAMENTE no corte é passar — o corte é o mínimo que a régua exige,
 * e um aluno com 4,0 contra corte 4,0 não está abaixo de nada.
 */
export function seloDaNota(
  nota: number | null | undefined,
  corte: number | null | undefined,
  maximo = 10,
): Selo {
  if (nota == null || !Number.isFinite(nota)) return SEM_DADO;
  if (corte == null || !Number.isFinite(corte)) return SEM_DADO;

  const distancia = nota - corte;

  if (distancia >= 0) {
    // O espaço acima do corte. Um corte de 9,5 deixa só 0,5 de folga, e sem
    // normalizar por ele um 10 pareceria "pouco acima".
    const folga = maximo - corte;
    const intensidade = folga > 0 ? Math.min(1, distancia / folga) : 1;
    return {
      estado: distancia === 0 ? 'no-corte' : 'acima',
      intensidade,
      distancia,
      etiqueta: '',
    };
  }

  const folga = corte;
  const intensidade = folga > 0 ? Math.min(1, -distancia / folga) : 1;
  return {
    estado: 'abaixo',
    intensidade,
    distancia,
    etiqueta: formatarDistancia(distancia),
  };
}

/**
 * A pior distância de um aluno entre as matérias que ele tem nota.
 *
 * É o ordenador da R6 e o número da coluna "Distância". Mede contra o corte DA
 * MATÉRIA, nunca contra um escalar único: um corte só para todas mentiria
 * justamente sobre a matéria que mais elimina — o Inglês da Fase 1 do ITA, que
 * exige 5,0 e é a única eliminatória.
 *
 * `null` quando o aluno não tem nota nenhuma com régua aplicável. Aluno sem
 * dado não é aluno em risco: ele não foi mal, ele não foi medido — e por isso
 * a ordenação o afunda em vez de encabeçar.
 */
export function piorDistancia(
  pares: ReadonlyArray<{ nota: number | null | undefined; corte: number | null | undefined }>,
): number | null {
  let pior: number | null = null;
  for (const { nota, corte } of pares) {
    const { distancia } = seloDaNota(nota, corte);
    if (distancia == null) continue;
    if (pior == null || distancia < pior) pior = distancia;
  }
  return pior;
}


/**
 * A distância do aluno ao corte: a pior das matérias que ele tem nota (R6).
 *
 * É o ordenador padrão de toda tabela de aluno e o número da coluna
 * "Distância". Lê o veredito que o servidor já calculou e a régua em vigor —
 * não recalcula critério nenhum.
 */
export function distanciaAoCorte(
  veredito: AlunoClassificado | undefined,
  criterio: CriterioClassificacao | null | undefined,
): number | null {
  if (!veredito) return null;
  const pares = Object.entries(veredito.notas ?? {}).map(([materia, { nota }]) => ({
    nota,
    corte: corteDaMateria(criterio, materia),
  }));
  return piorDistancia(pares);
}

/**
 * Compara dois alunos pela distância do corte, ASCENDENTE — o pior primeiro.
 *
 * ⚠️ Nulo afunda nos DOIS sentidos, e essa é a regra que a ordenação ingênua
 * erra: um aluno sem nota no ciclo não pode encabeçar a lista de "pior
 * desempenho". Ele não foi mal — ele não foi medido, e colocá-lo no topo
 * mandaria o coordenador conversar com quem não tem problema nenhum enquanto
 * quem está a 3,2 do corte fica na terceira página.
 */
export function compararPorDistancia(
  a: number | null,
  b: number | null,
): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return a - b;
}
