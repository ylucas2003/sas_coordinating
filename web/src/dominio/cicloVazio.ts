import type { Ciclo } from '../tipos/dominio';

// AS DUAS SAÍDAS DE UM CICLO SEM PROVA APLICADA.
//
// Um ciclo pode existir no banco e nunca ter sido usado — "Ciclo 1 · IME ·
// 2022" é o caso real. A tela dele não mostra KPI, campo nem tabela (quatro
// travessões e três cards dizendo "ainda não" são quatro buracos, não
// informação): mostra o que aconteceu e o que fazer.
//
// O "o que fazer" é regra, não desenho, e por isso mora aqui. As duas saídas
// são CONDICIONAIS, e cada condição existe para não prometer o que a tela não
// entrega:
//
//   AGENDAR   o diálogo de agendamento só oferece ciclos do ano letivo mais
//             recente (`componentes/dialogos/AgendarSimulado.tsx`). Levar
//             alguém a um formulário onde este ciclo não aparece na lista é
//             pior que não oferecer o botão.
//   O VIZINHO tem de ter prova — mandar de um ciclo vazio para outro vazio é
//             gastar o clique da pessoa — e, de preferência, ser do MESMO
//             vestibular: ITA e IME correm em paralelo, e trocar de vestibular
//             no meio troca o assunto sem avisar.

export interface SaidasDoCicloVazio {
  /** Dá para agendar uma prova NESTE ciclo? */
  podeAgendar: boolean;
  /** Um ciclo que tem o que mostrar, ou `null` quando não existe nenhum. */
  vizinho: Ciclo | null;
}

export function saidasDoCicloVazio(
  ciclo: Ciclo,
  ciclos: readonly Ciclo[],
): SaidasDoCicloVazio {
  // Sem a lista (ainda carregando, ou consulta falhada) o único ano conhecido
  // é o do próprio ciclo. Assumir que ele é o mais recente é o palpite certo:
  // o erro que ele produz — oferecer "agendar" onde não dá — é um formulário
  // com uma lista sem este ciclo, enquanto o erro contrário esconde a saída
  // justamente de quem está no ciclo do ano corrente.
  const anoMaisRecente = ciclos.length
    ? Math.max(...ciclos.map((c) => c.anoLetivo || 0))
    : ciclo.anoLetivo;

  const comProva = ciclos.filter((c) => c.id !== ciclo.id && c.simuladoIds.length > 0);

  return {
    podeAgendar: ciclo.anoLetivo === anoMaisRecente,
    vizinho: comProva.find((c) => c.vestibularAlvo === ciclo.vestibularAlvo)
      ?? comProva[0]
      ?? null,
  };
}
