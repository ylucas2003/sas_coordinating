// "Alunos com desempenho parecido", em português.
//
// A seção existe há muito tempo e é informação de verdade — ver quem está no
// mesmo lugar deste aluno ajuda a decidir quem chamar para conversar. O que
// estava errado era a LÍNGUA: o subtítulo dizia "kNN por vetor de features
// (média por matéria + desvio + tendência)" e a primeira coluna era
// "Distância: 0,42". Ninguém nesta escola sabe o que é kNN, e 0,42 não decide
// nada (docs/39 §3 · fase 4, defeito 1).
//
// ⚠️ O que esta leitura NÃO pode virar: recomendação. "Alunos parecidos com
// ele" é uma afirmação sobre os números; "faça o que funcionou com eles" é
// causalidade que este produto não mede e não deve insinuar.
//
// A distância continua existindo e continua mandando — ela é a ORDEM da lista
// (R6). O que sai é só a exibição do número, que não significa nada para quem
// lê: quem está mais acima é mais parecido, e isso a ordenação já diz.

import type { Perfil, Tendencia, Zona } from '../tipos/dominio';

/** O que se compara entre dois alunos — o que a ficha e a lista têm à mão. */
export interface TracoDoAluno {
  perfil: Perfil | null;
  tendencia: Tendencia | null;
  zona: Zona | null;
  media: number | null;
}

/** Uma casa, vírgula decimal — a convenção do produto. */
function nota(v: number): string {
  return v.toFixed(1).replace('.', ',');
}

/**
 * Em que este aluno se parece com o outro, em uma linha curta.
 *
 * Só afirma o que os dois campos mostram lado a lado: mesma zona, mesma
 * tendência, mesmo perfil, e a distância entre as médias. **Sem nada em comum,
 * devolve string vazia** — e quem chama esconde a linha. Frase de enchimento
 * ("perfil semelhante") num par que não tem nada semelhante é exatamente o
 * tipo de número inventado que o resto desta tela passou a recusar.
 *
 * No máximo dois traços, e nesta ordem de utilidade: a zona é o que decide se
 * o coordenador age, a tendência é para onde a coisa anda, o perfil é o mais
 * sutil dos três. Listar os três faz uma linha que ninguém termina de ler.
 */
export function descreverSemelhanca(alvo: TracoDoAluno, parecido: TracoDoAluno): string {
  const tracos: string[] = [];

  if (alvo.zona && parecido.zona === alvo.zona) tracos.push('mesma zona');
  if (alvo.tendencia && parecido.tendencia === alvo.tendencia) {
    tracos.push('a nota anda no mesmo sentido');
  }
  if (alvo.perfil && parecido.perfil === alvo.perfil) tracos.push('oscila do mesmo jeito');

  const partes = tracos.slice(0, 2);

  if (alvo.media != null && parecido.media != null) {
    const d = Math.round((parecido.media - alvo.media) * 10) / 10;
    if (d === 0) partes.push('mesma média');
    else partes.push(`média ${nota(Math.abs(d))} ${d > 0 ? 'acima' : 'abaixo'}`);
  }

  return partes.join(' · ');
}
