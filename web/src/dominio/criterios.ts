// Leitura da régua de corte no front.
//
// ⚠️ Isto **não** implementa a regra — implementá-la em TypeScript é
// justamente o que a Sprint 2 proibiu (docs/18 §1.2), depois de a mesma regra
// existir em três lugares e divergir. O servidor resolve `cortes`,
// `corteGenerico`, `corteMedia` e `eliminatorias` em `_descrever_criterio`; o
// que está aqui é a consulta a esse resultado, com o encadeamento de fallback
// num lugar só em vez de repetido em cada tela.

import type { CriterioClassificacao, PredicadoCriterio } from '../tipos/dominio';

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

// ─── "Como esta régua funciona" ──────────────────────────────────────────
//
// O balão do "i" no seletor de régua. É LEITURA dos `predicados` que o servidor
// serializa — `_descrever_criterio` os manda justamente para "legenda,
// tooltip" (api/app/routes/ciclos.py) —, não uma segunda avaliação: quem corta
// quem continua sendo `stats/criterios.py::avaliar`. A frase de "quando corta"
// espelha o `combinador` dele; se o avaliador ganhar um terceiro, o `default`
// abaixo não inventa regra, diz que não sabe explicar.

const NOME_DA_MATERIA: Record<string, string> = {
  matematica: 'Matemática',
  fisica: 'Física',
  quimica: 'Química',
  portugues: 'Português',
  ingles: 'Inglês',
  redacao: 'Redação',
};

/** `'*'` e `null` não são matérias: são "qualquer disciplina" e a média geral. */
function nomeDoAlvo(materia: string | null): string {
  if (materia === null) return 'Média geral';
  if (materia === '*') return 'Qualquer disciplina';
  // A 2ª fase do ITA compõe a média com a nota da 1ª (ITA §4.7).
  if (materia === 'fase_1') return 'Nota da 1ª fase';
  return NOME_DA_MATERIA[materia] ?? materia.charAt(0).toUpperCase() + materia.slice(1);
}

const NOME_DO_OPERADOR: Record<string, string> = {
  '>=': 'pelo menos',
  '>': 'acima de',
  '<=': 'no máximo',
  '<': 'abaixo de',
};

function escreverMinimo(p: PredicadoCriterio): string {
  const operador = NOME_DO_OPERADOR[p.operador] ?? p.operador;
  if (typeof p.minimo === 'object') {
    return `${operador} ${p.minimo.acertos} de ${p.minimo.de} acertos`;
  }
  return `${operador} ${p.minimo.toFixed(1).replace('.', ',')}`;
}

export interface ExigenciaDaRegua {
  /** "Matemática", "Qualquer disciplina", "Média geral". */
  alvo: string;
  /** "pelo menos 5 de 12 acertos", "pelo menos 4,0". */
  minimo: string;
  eliminatorio: boolean;
  /** `true` quando a nota é cobrada mas não entra na média geral. */
  foraDaMedia: boolean;
}

export interface ExplicacaoDaRegua {
  /** O que o servidor diz da régua, palavra por palavra. */
  descricao: string;
  exigencias: ExigenciaDaRegua[];
  /** Uma frase: quantas exigências o aluno precisa falhar para ser cortado. */
  quandoCorta: string;
  /** Desempate por extenso, na ordem de precedência. Vazio = régua sem ordem. */
  desempate: string[];
}

function escreverQuandoCorta(
  combinador: CriterioClassificacao['combinador'],
  exigencias: readonly ExigenciaDaRegua[],
): string {
  const soltas = exigencias.filter((e) => !e.eliminatorio);
  const sozinhas = exigencias.filter((e) => e.eliminatorio).map((e) => e.alvo);
  const excecao = sozinhas.length
    ? ` Em ${sozinhas.join(' e ')}, ficar abaixo do mínimo corta sozinho, sem olhar o resto.`
    : '';

  // Com uma exigência só, "algum" e "todos" dão no mesmo — e "basta UMA das
  // exigências" numa lista de uma linha leria como enigma.
  if (soltas.length <= 1) {
    return `Fica cortado quem não cumpre o mínimo.${excecao}`;
  }
  switch (combinador) {
    case 'algum':
      return `Basta ficar abaixo do mínimo em UMA das exigências para ser cortado.${excecao}`;
    case 'todos':
      return `Só é cortado quem fica abaixo do mínimo em TODAS as exigências ao mesmo tempo.${excecao}`;
    default:
      return excecao.trim();
  }
}

/**
 * A régua em linguagem de coordenador, para o balão do "i".
 *
 * Fora das exigências ficam os predicados sem mínimo nenhum (`fase_1` com 0,0 na
 * 2ª fase do ITA): eles só pesam na média, e listá-los como "pelo menos 0,0"
 * diria que existe uma barreira onde não há.
 */
export function explicarCriterio(criterio: CriterioClassificacao): ExplicacaoDaRegua {
  const exigencias: ExigenciaDaRegua[] = criterio.predicados
    .filter((p) => p.eliminatorio || typeof p.minimo === 'object' || p.minimo > 0)
    .map((p) => ({
      alvo: nomeDoAlvo(p.materia),
      minimo: escreverMinimo(p),
      eliminatorio: p.eliminatorio,
      foraDaMedia: !p.entraNaMedia && p.materia !== null,
    }));

  return {
    descricao: criterio.descricao,
    exigencias,
    quandoCorta: escreverQuandoCorta(criterio.combinador, exigencias),
    desempate: criterio.desempate.map((t) => (t === 'media' ? 'Média geral' : nomeDoAlvo(t))),
  };
}
