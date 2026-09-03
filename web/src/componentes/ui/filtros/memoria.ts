// A escolha de aberta/colapsada, lembrada por SUPERFÍCIE de filtro.
//
// Não fica em `dominio/` porque não é regra: é acesso a `localStorage`, com
// efeito. O precedente da casa é `telas/Aluno/pecas/tema.ts`.
//
// ⚠️ Por superfície, não por rota. `/provas` tem DUAS faixas — Ciclos e
// Simulados, conforme `?aba=` — e uma chave por rota faria as duas dividirem
// um estado, abrindo a segunda no que o usuário decidiu para a primeira.
//
// ⚠️ `localStorage` sobrevive à sessão de propósito: quem trabalha no Painel
// todo dia não quer reabrir a mesma faixa toda manhã. É preferência de
// interface, sem nada de pessoal — a regra 6 do CLAUDE.md não é tocada.

const PREFIXO = 'sas.filtros.';

/** `null` = a pessoa nunca escolheu; a faixa decide sozinha, pelo tamanho. */
export function lerEscolha(tela: string): boolean | null {
  try {
    const v = localStorage.getItem(PREFIXO + tela);
    return v === null ? null : v === '1';
  } catch {
    // Safari em janela privada, storage bloqueado: a faixa funciona igual,
    // só não lembra. Nunca é motivo para a tela não abrir.
    return null;
  }
}

export function gravarEscolha(tela: string, aberta: boolean): void {
  try {
    localStorage.setItem(PREFIXO + tela, aberta ? '1' : '0');
  } catch {
    // idem.
  }
}
