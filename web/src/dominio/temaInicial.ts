/**
 * Qual tema uma visita começa, dado o que o navegador tem guardado.
 *
 * Função pura, e fora de `servicos/tema.ts`, para a regra poder ser TESTADA: o
 * serviço mexe em `localStorage` e no `<html>`, e a decisão do meio é o que
 * importa acertar.
 *
 * ⚠️ **A escolha gravada é zerada UMA vez** (decisão de 14/09). O tema claro já
 * era o padrão desde 09/09 (docs/40 §12.10), mas quem tinha clicado na lua em
 * algum momento — inclusive quando o escuro era o que o próprio aparelho
 * mostrava — continuava entrando escuro, e a percepção era de que "o padrão
 * não mudou". A partir desta versão todo mundo entra claro uma vez; o que a
 * pessoa escolher DEPOIS disso vale para sempre.
 *
 * O mecanismo é uma versão da preferência, e não uma data: comparar data
 * dependeria do relógio do aparelho, que é exatamente o que não se controla.
 */

export type Tema = 'dia' | 'noite';

/** Suba este número para zerar as escolhas de todo mundo de novo. */
export const VERSAO_DA_PREFERENCIA = '2';

export interface Guardado {
  tema: string | null;
  /** A chave de quando o tema era só do aluno. */
  temaAntigo: string | null;
  versao: string | null;
}

export interface Decisao {
  tema: Tema;
  /** Verdadeiro quando o que estava guardado deve ser apagado agora. */
  zerar: boolean;
}

export function temaInicial(guardado: Guardado, padrao: Tema = 'dia'): Decisao {
  if (guardado.versao !== VERSAO_DA_PREFERENCIA) {
    // Guardado de antes desta versão: não é uma escolha feita sob a regra
    // atual. Some, e a visita começa no padrão.
    const haviaAlgo = guardado.tema != null || guardado.temaAntigo != null || guardado.versao != null;
    return { tema: padrao, zerar: haviaAlgo };
  }
  const v = guardado.tema;
  if (v === 'dia' || v === 'noite') return { tema: v, zerar: false };
  return { tema: padrao, zerar: false };
}
