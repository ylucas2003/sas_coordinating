// Em que ciclo o Painel abre, e em que ordem os ciclos são lidos.
//
// O problema que este módulo existe para resolver (docs/32 §3.1): a API
// devolve os 23 ciclos ordenados só por `ordem`. O resultado é
// `Ciclo 1 · IME · 2026`, `Ciclo 1 · ITA · 2027`, `Ciclo 1 · IME · 2025`,
// `Ciclo 2 · ITA · 2025`… — três anos e dois vestibulares intercalados, com
// "Ciclo 7" aparecendo duas vezes. Sem uma ordem estável não há "o ciclo em
// foco", e o Painel abriria num ciclo que ninguém escolheu.
//
// ⚠️ O RECORTE MORREU, a ORDEM ficou. Este arquivo nasceu para as pílulas de
// ano e vestibular do Painel; a fase 2 do docs/39 tirou a faixa de filtros da
// tela, e com ela foram `RECORTE_VAZIO`, `contagensDoRecorte` (o número de
// cada pílula) e `rotuloDoCiclo` (o que a pílula escrevia). `RecortePainel`
// sobrevive como o parâmetro de `ciclosNoRecorte`, que o Painel chama com
// `recorteCompleto(ciclos)` — ou seja, com "todos": o que se aproveita dele
// hoje é o `.sort()`, não o `.filter()`.

import type { Ciclo, Simulado } from '../tipos/dominio';

export interface RecortePainel {
  anos: ReadonlySet<number>;
  vestibulares: ReadonlySet<string>;
}

/** O estado inicial: todo ano e todo vestibular que a fileira conhece. */
export function recorteCompleto(ciclos: readonly Ciclo[]): RecortePainel {
  const anos = new Set<number>();
  const vestibulares = new Set<string>();
  for (const c of ciclos) {
    if (c.anoLetivo) anos.add(c.anoLetivo);
    if (c.vestibularAlvo) vestibulares.add(c.vestibularAlvo);
  }
  return { anos, vestibulares };
}

function dentro(c: Ciclo, recorte: RecortePainel): boolean {
  if (!recorte.anos.has(c.anoLetivo)) return false;
  return c.vestibularAlvo != null && recorte.vestibulares.has(c.vestibularAlvo);
}

/**
 * Os ciclos que sobram, agrupados por ano (mais recente primeiro) e, dentro do
 * ano, por vestibular e ordem. Ordenar só por `ordem` — o que a API faz — é o
 * que produz a fileira intercalada.
 */
export function ciclosNoRecorte(ciclos: readonly Ciclo[], recorte: RecortePainel): Ciclo[] {
  return ciclos
    .filter((c) => dentro(c, recorte))
    .sort(
      (a, b) =>
        b.anoLetivo - a.anoLetivo ||
        (a.vestibularAlvo ?? '').localeCompare(b.vestibularAlvo ?? '') ||
        a.ordem - b.ordem,
    );
}

/**
 * O ciclo em que o Painel abre.
 *
 * Hoje ele abre em `ciclos[0]`, que é o primeiro dos três ciclos com
 * `ordem = 1` — e como o `.order()` da rota tem uma coluna só e nenhum
 * desempate, **qual dos três não está definido**. O Painel abre num ciclo que
 * ninguém escolheu, e amanhã pode abrir noutro sem nada ter mudado.
 *
 * A regra: o ciclo com a aplicação de simulado mais recente que já aconteceu.
 * Um ciclo futuro (2027, sem prova aplicada) não é onde o coordenador quer
 * cair. `hoje` entra por parâmetro para o teste não depender do relógio.
 */
export function cicloPadrao(
  ciclos: readonly Ciclo[],
  simulados: readonly Simulado[],
  hoje: string = new Date().toISOString().slice(0, 10),
): Ciclo | null {
  const ultimaAplicacao = new Map<string, string>();
  for (const s of simulados) {
    if (!s.dataAplicacao || s.dataAplicacao > hoje) continue;
    const atual = ultimaAplicacao.get(s.cicloId);
    if (!atual || s.dataAplicacao > atual) ultimaAplicacao.set(s.cicloId, s.dataAplicacao);
  }

  let melhor: Ciclo | null = null;
  let melhorData = '';
  for (const c of ciclos) {
    const data = ultimaAplicacao.get(c.id);
    if (data == null || data <= melhorData) continue;
    melhor = c;
    melhorData = data;
  }
  // Nenhum ciclo com prova aplicada (banco novo, ou recorte só de futuros):
  // o primeiro da fileira já ordenada é melhor que nada.
  return melhor ?? ciclos[0] ?? null;
}
