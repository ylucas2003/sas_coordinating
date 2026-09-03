// O recorte do Painel — ano e vestibular estreitando a fileira de ciclos.
//
// O problema que este módulo existe para resolver (docs/32 §3.1): a fileira
// mostra os 23 ciclos do banco na ordem que a API devolve, e a API ordena só
// por `ordem`. O resultado é `Ciclo 1 · IME · 2026`, `Ciclo 1 · ITA · 2027`,
// `Ciclo 1 · IME · 2025`, `Ciclo 2 · ITA · 2025`… — três anos e dois
// vestibulares intercalados, com "Ciclo 7" aparecendo duas vezes.
//
// ⚠️ Por que NÃO reusa `aplicarFiltros` de `ciclos.ts`, que filtra os mesmos
// dois eixos: lá conjunto vazio significa "sem filtro" e deixa tudo passar,
// porque a tela de /provas nasce sem nada marcado. Aqui os dois eixos nascem
// com TUDO marcado (decisão do Yan, 03/09), e nesse modelo desmarcar o último
// ano tem de esvaziar a fileira — não fazer os três voltarem. É a mesma
// operação com a semântica invertida, e compartilhar o predicado faria uma das
// duas telas mentir.

import type { Ciclo, Simulado } from '../tipos/dominio';

export interface RecortePainel {
  anos: ReadonlySet<number>;
  vestibulares: ReadonlySet<string>;
}

/** Antes de os ciclos chegarem não há o que marcar. */
export const RECORTE_VAZIO: RecortePainel = { anos: new Set(), vestibulares: new Set() };

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
 * Contagem por pílula ignorando o próprio eixo — senão cada número viraria
 * sempre o total já selecionado. Mesmo cuidado de `Alunos.tsx`.
 */
export function contagensDoRecorte(ciclos: readonly Ciclo[], recorte: RecortePainel) {
  const porAno = new Map<number, number>();
  const porVestibular = new Map<string, number>();

  for (const c of ciclos) {
    const vest = c.vestibularAlvo;
    if (c.anoLetivo && vest != null && recorte.vestibulares.has(vest)) {
      porAno.set(c.anoLetivo, (porAno.get(c.anoLetivo) ?? 0) + 1);
    }
    if (vest != null && recorte.anos.has(c.anoLetivo)) {
      porVestibular.set(vest, (porVestibular.get(vest) ?? 0) + 1);
    }
  }
  return { porAno, porVestibular };
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

/**
 * O que a pílula do ciclo escreve. Quanto mais o recorte já fixou, menos a
 * pílula precisa repetir: com 2026 e ITA escolhidos, "4" basta — era o pedido
 * do áudio de 29/08 ("quebrar esses filtros em mais abas"). Com o recorte
 * aberto, o rótulo tem de desambiguar, senão duas pílulas dizem "7".
 */
export function rotuloDoCiclo(ciclo: Ciclo, recorte: RecortePainel): string {
  const umAno = recorte.anos.size === 1;
  const umVestibular = recorte.vestibulares.size === 1;
  const partes: string[] = [String(ciclo.ordem || '—')];
  if (!umVestibular && ciclo.vestibularAlvo) partes.push(ciclo.vestibularAlvo);
  if (!umAno && ciclo.anoLetivo) partes.push(String(ciclo.anoLetivo));
  return partes.join(' · ');
}
