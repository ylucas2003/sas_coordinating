/**
 * O período de uma exportação — atalhos, seleção no calendário e rótulo
 * (decisão de 14/09).
 *
 * Toda exportação da cantina que tem data abre com uma escolha de período, e a
 * escolha tem três formas, decididas pelo FORMATO e não pela tela:
 *
 *   nenhum     a lista não tem data (alunos com direito, contas);
 *   dia        o formato só faz sentido para um dia (a imagem do cardápio, a
 *              folha do balcão);
 *   intervalo  planilha e relatório, que cobrem quanto tempo se quiser — até o
 *              teto abaixo.
 *
 * Tudo em ISO local (`2026-09-14`), pela mesma armadilha de `dataLocal`:
 * `new Date('2026-09-14')` é meia-noite UTC, e em Fortaleza isso é o dia 13.
 */

import { dataLocal, isoDoDia } from './cantina';

export type ModoDePeriodo = 'nenhum' | 'dia' | 'intervalo';

export interface Periodo {
  de: string;
  ate: string;
}

export type Atalho = 'hoje' | 'semana' | 'mes' | 'mesPassado';

export const ROTULO_DO_ATALHO: Record<Atalho, string> = {
  hoje: 'Hoje',
  semana: 'Esta semana',
  mes: 'Este mês',
  mesPassado: 'Mês passado',
};

/**
 * O maior intervalo que uma exportação aceita.
 *
 * ⚠️ Não é gosto: é a armadilha 2 do CLAUDE.md. Não há paginação em lugar
 * nenhum, e `pedido_refeicao_item` cresce por dia × aluno × item — um "desde
 * sempre" montaria a planilha inteira em memória num processo de uma thread só.
 * Um trimestre cobre o fechamento que a coordenação faz.
 */
export const TETO_DE_DIAS = 93;

/** O período de um atalho, a partir de `hoje`. A semana vai de segunda a domingo. */
export function periodoDoAtalho(atalho: Atalho, hoje: Date = new Date()): Periodo {
  const d = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  switch (atalho) {
    case 'hoje':
      return { de: isoDoDia(d), ate: isoDoDia(d) };
    case 'semana': {
      // `getDay()` é 0 no domingo: sem o ajuste, o domingo abriria a semana
      // SEGUINTE, e "esta semana" num domingo mostraria sete dias no futuro.
      const recuo = (d.getDay() + 6) % 7;
      const segunda = new Date(d.getFullYear(), d.getMonth(), d.getDate() - recuo);
      const domingo = new Date(segunda.getFullYear(), segunda.getMonth(), segunda.getDate() + 6);
      return { de: isoDoDia(segunda), ate: isoDoDia(domingo) };
    }
    case 'mes':
      return {
        de: isoDoDia(new Date(d.getFullYear(), d.getMonth(), 1)),
        ate: isoDoDia(new Date(d.getFullYear(), d.getMonth() + 1, 0)),
      };
    case 'mesPassado':
      return {
        de: isoDoDia(new Date(d.getFullYear(), d.getMonth() - 1, 1)),
        ate: isoDoDia(new Date(d.getFullYear(), d.getMonth(), 0)),
      };
  }
}

/** Início antes do fim, sempre — o clique no calendário pode vir ao contrário. */
export function normalizarPeriodo(p: Periodo): Periodo {
  return p.de <= p.ate ? p : { de: p.ate, ate: p.de };
}

/** Quantos dias o período cobre, contando as duas pontas. */
export function diasNoPeriodo(p: Periodo): number {
  const { de, ate } = normalizarPeriodo(p);
  const ms = dataLocal(ate).getTime() - dataLocal(de).getTime();
  // `round` e não `floor`: a troca de horário de verão faria um dia ter 23 h e
  // a divisão cair para baixo. O Brasil não tem horário de verão hoje; já teve.
  return Math.round(ms / 86_400_000) + 1;
}

/** Por que este período não pode ser exportado — ou `null` se pode. */
export function problemaDoPeriodo(p: Periodo, modo: ModoDePeriodo): string | null {
  if (modo === 'nenhum') return null;
  if (modo === 'dia' && p.de !== p.ate) return 'Este formato é de um dia só. Escolha um dia.';
  if (diasNoPeriodo(p) > TETO_DE_DIAS) {
    return `O período vai até ${TETO_DE_DIAS} dias. Divida em partes menores.`;
  }
  return null;
}

/**
 * O próximo estado da seleção quando alguém clica num dia do calendário.
 *
 * No modo `dia`, o clique É a escolha. No modo `intervalo`, são dois cliques:
 * o primeiro fixa as duas pontas no mesmo dia e passa a esperar o fim; o
 * segundo fecha — em qualquer ordem, porque `normalizarPeriodo` resolve.
 */
export interface Selecao extends Periodo {
  esperandoFim: boolean;
}

export function clicarNoDia(atual: Selecao, iso: string, modo: ModoDePeriodo): Selecao {
  if (modo !== 'intervalo') return { de: iso, ate: iso, esperandoFim: false };
  if (!atual.esperandoFim) return { de: iso, ate: iso, esperandoFim: true };
  return { ...normalizarPeriodo({ de: atual.de, ate: iso }), esperandoFim: false };
}

const MESES = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
];

/**
 * "14 de setembro de 2026", "14 a 20 de setembro de 2026", "setembro de 2026",
 * "28 de agosto a 3 de setembro de 2026".
 *
 * O mês inteiro vira o nome do mês porque é assim que a coordenação fala do
 * fechamento — "o relatório de setembro", e não "de 1 a 30 de setembro".
 */
export function rotuloDoPeriodo(p: Periodo): string {
  const { de, ate } = normalizarPeriodo(p);
  const a = dataLocal(de);
  const b = dataLocal(ate);
  if (de === ate) return `${a.getDate()} de ${MESES[a.getMonth()]} de ${a.getFullYear()}`;

  const mesmoMes = a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear();
  const ultimoDoMes = new Date(b.getFullYear(), b.getMonth() + 1, 0).getDate();
  if (mesmoMes && a.getDate() === 1 && b.getDate() === ultimoDoMes) {
    return `${MESES[a.getMonth()]} de ${a.getFullYear()}`;
  }
  if (mesmoMes) {
    return `${a.getDate()} a ${b.getDate()} de ${MESES[a.getMonth()]} de ${a.getFullYear()}`;
  }
  const anoA = a.getFullYear() === b.getFullYear() ? '' : ` de ${a.getFullYear()}`;
  return `${a.getDate()} de ${MESES[a.getMonth()]}${anoA} a ${b.getDate()} de ${MESES[b.getMonth()]} de ${b.getFullYear()}`;
}
