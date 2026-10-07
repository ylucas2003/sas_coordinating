// Os dois recortes de situação da tabela do ciclo: CORTE (quem a régua cortou)
// e PRESENÇA (quem fez as provas). São eixos diferentes e se combinam — o que
// a coordenação quer achar é "cortado DE VERDADE": cortado e presente.
//
// ⚠️ "Ausente" AQUI é uma definição de PENEIRA, e diverge de propósito da do
// servidor. `stats/computavel.py` só tira um zero da conta quando há evidência
// (quiz inteiro em branco, ou prova marcada à mão em `simulado.zero_e_ausencia`,
// docs/32 §1.4), porque um proxy de "zero = falta" errou 14% onde dava para
// conferir. A coordenação decidiu que, para ENCONTRAR gente, quem zerou conta
// como ausente — e como isto só esconde linhas da tabela, sem escrever nem
// recalcular nada, o princípio da migration 0024 (não destruir o fato do
// Canvas) segue de pé. Consequência que a tela precisa dizer: a régua, os KPIs
// e a coluna Distância continuam contando o zero como nota.

import type { ClassificacaoPorAluno, ColunaPainel, NotasPorAluno } from './painel';
import type { Aluno, Simulado } from '../tipos/dominio';

/** `null` = sem recorte de corte (todos). */
export type FiltroDeCorte = 'cortados' | 'nao-cortados';

/** `null` = sem recorte de presença (todos). */
export type FiltroDePresenca = 'presentes' | 'ausentes';

/**
 * As provas em que dá para dizer se alguém faltou: as da fase em tela, reais,
 * já aplicadas e não anuladas.
 *
 * Prova ainda por aplicar fica de fora — sem isso, num ciclo em andamento
 * TODO aluno seria "ausente" da prova de semana que vem. Coluna virtual (a
 * média) e coluna sem prova no ciclo também não são prova. O teste de "já
 * aplicada" é o mesmo do contador "N de M provas aplicadas" da ficha.
 */
export function provasQueContam(
  colunas: readonly ColunaPainel[],
  hoje: string,
): Simulado[] {
  const provas: Simulado[] = [];
  for (const col of colunas) {
    const sim = col.sim;
    if (col.virtual || !sim || sim.anulado) continue;
    if (!sim.dataAplicacao || sim.dataAplicacao > hoje) continue;
    provas.push(sim);
  }
  return provas;
}

/**
 * Faltou a ALGUMA das provas que contam: sem nota, nota que o SAS não
 * computa, ou zero.
 *
 * `notasAluno` já deixou de fora a nota não computável e a nula (é por isso que
 * a célula sai hachurada), então "não está no mapa" cobre os dois. Zero é o
 * caso que o servidor não converte — ver o cabeçalho.
 */
export function estaAusente(
  alunoId: string,
  provas: readonly Simulado[],
  notasAluno: NotasPorAluno,
): boolean {
  return provas.some((p) => {
    const nota = notasAluno[alunoId]?.[p.id];
    return nota === undefined || nota === 0;
  });
}

/**
 * Aplica os dois recortes. A ordem da lista é preservada — quem ordena é
 * `montarPainel`.
 *
 * Aluno sem veredito da régua (não tem nota nenhuma no ciclo) não é cortado
 * nem "não cortado": `avaliar` devolve "aprovado" para quem não tem dado, e
 * chamá-lo de "não cortado" o contaria como gente que passou. Ele só aparece
 * quando o recorte de corte está desligado — e como ausente, que é o que é.
 *
 * Sem provas que contam, ninguém tem presença definida: as duas opções de
 * presença devolvem vazio, em vez de chamar todo mundo de ausente.
 */
export function filtrarPorSituacao(
  alunos: readonly Aluno[],
  {
    corte, presenca, classificacao, provas, notasAluno,
  }: {
    corte: FiltroDeCorte | null;
    presenca: FiltroDePresenca | null;
    classificacao: ClassificacaoPorAluno;
    provas: readonly Simulado[];
    notasAluno: NotasPorAluno;
  },
): Aluno[] {
  if (!corte && !presenca) return alunos.slice();

  return alunos.filter((aluno) => {
    if (corte) {
      const veredito = classificacao[aluno.id];
      if (!veredito) return false;
      if (veredito.aprovado === (corte === 'cortados')) return false;
    }
    if (presenca) {
      if (provas.length === 0) return false;
      const ausente = estaAusente(aluno.id, provas, notasAluno);
      if (ausente !== (presenca === 'ausentes')) return false;
    }
    return true;
  });
}
