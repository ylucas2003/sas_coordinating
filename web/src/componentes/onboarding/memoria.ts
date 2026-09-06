// O "já vi o tour", gravado por pessoa.
//
// Não fica em `dominio/` porque não é regra: é acesso a `localStorage`, com
// efeito. O precedente da casa é `servicos/tema.ts` e
// `componentes/ui/filtros/memoria.ts` — a regra pura (como a chave é formada,
// e por que ela é por pessoa) mora em `dominio/tour.ts`, com teste ao lado.
//
// ⚠️ `localStorage` e não o servidor: isto não vale uma coluna, uma migration
// nem uma ida à API no caminho crítico da home. É preferência de leitura, sem
// nada de pessoal além do nome que a própria sessão já guarda — a regra 6 do
// CLAUDE.md (dados de menores) não é tocada.
//
// ⚠️ E não `sessionStorage`, que é o que a folha "por que a prova vem inteira"
// usa do lado do aluno. Lá a repetição é o desenho: o aluno volta em setembro
// sem lembrar por que a prova vem inteira. Aqui é o oposto — o coordenador
// abre o Painel toda manhã, e um tour que voltasse a cada aba nova ensinaria
// a fechar sobreposição sem ler, que queima a próxima que importar.

import { chaveDoTour } from '../../dominio/tour';

export function jaViuOTour(quem: string): boolean {
  try {
    return localStorage.getItem(chaveDoTour(quem)) === '1';
  } catch {
    // Janela privada e "bloquear dados de site" fazem o acessor LANÇAR, não
    // devolver null. Sem memória o tour aparece de novo — incomoda, mas nunca
    // derruba a tela por causa de uma preferência.
    return false;
  }
}

export function marcarTourVisto(quem: string): void {
  try {
    localStorage.setItem(chaveDoTour(quem), '1');
  } catch {
    // idem: a visita vale só para esta sessão.
  }
}
