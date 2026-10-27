// A TRILHA NO CELULAR — quais degraus da migalha da topbar saem quando a tela
// é estreita.
//
// Em 390px a nav da topbar tem 258px: o resto da faixa é o botão de tema e a
// identidade. Na verificação no browser de 26/10, a trilha de `/conectar-ia`
// ("Administração › Conexões de IA › Pedido de …") gastava 260px só com os
// dois primeiros degraus, e o ATUAL — o título da tela, a única coisa da
// trilha que se lê para saber onde se está — nascia fora da nav, recortado
// por inteiro. Não era defeito daquela tela: medido no mesmo dia com as
// regras de antes, o atual saía recortado em toda trilha de três degraus, com
// 24px à vista em "Integrações › Aulas" e nada no dia da cantina, que tem
// quatro. (O consentimento saiu do casco no mesmo dia — virou página pública,
// sem topbar —, e a regra ficou pelas outras trilhas.)
//
// Quando não cabe, cede o CAMINHO, nunca o destino:
//
//   * FICA o penúltimo, o degrau de onde se veio. É o "voltar um nível", e o
//     rail não o oferece: numa trilha de três degraus ele é tela de dentro de
//     um destino (Conexões de IA, Ciclos, Cardápios), não destino;
//   * SAEM os de antes dele. O primeiro é sempre um destino do rail
//     (Alunos, Provas, Administração), e no celular o rail é a barra
//     inferior, à vista o tempo todo — quem precisa dele não perde nada. No
//     dia da cantina sai também "Cantina", que reaparece um nível acima, na
//     trilha de Cardápios.
//
// O que sobra ainda pode não caber, e aí o penúltimo encolhe com reticências
// antes do atual: essa parte é medida, não regra, e mora no CSS
// (`styles/casco.css`, no bloco de celular da topbar).

/** Quantos degraus a trilha mostra no celular: de onde se veio e onde se está. */
export const DEGRAUS_NO_CELULAR = 2;

/**
 * Se o degrau `indice` (0 = o primeiro) de uma trilha de `total` degraus sai
 * no celular. O atual, que é o último, nunca sai; o penúltimo também não.
 */
export function degrauSomeNoCelular(indice: number, total: number): boolean {
  return indice < total - DEGRAUS_NO_CELULAR;
}
