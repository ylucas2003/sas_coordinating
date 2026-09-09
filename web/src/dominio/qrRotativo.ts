/**
 * O código do QR, derivado NO APARELHO a cada 10 segundos (docs/40 §12.9.2).
 *
 * ⚠️ **Nada aqui vai à rede.** O servidor entrega a semente uma vez, junto do
 * token, e este módulo produz um código novo a cada janela sem pedir nada a
 * ninguém. É o que torna os 10 segundos possíveis: pelo caminho direto —
 * baixar a validade do token para 10 s — cada renovação seria uma requisição e
 * uma escrita, seis por minuto por aluno na fila, numa API de uma thread só.
 * E, pior, uma falha de rede no corredor deixaria o aluno sem QR na frente do
 * balcão.
 *
 * ⚠️ **A semente nunca entra no QR.** Se entrasse, um print carregaria o
 * material para derivar as janelas seguintes, e a rotação seria decoração.
 *
 * ⚠️ **O relógio do aparelho não entra na conta.** A janela inicial vem do
 * servidor, e daqui em diante conta-se o tempo DECORRIDO (`performance.now`,
 * que é monotônico e não anda para trás quando o sistema acerta a hora). Um
 * celular adiantado em três minutos gera o código certo.
 */

/** O que o servidor manda junto do token, uma vez a cada dois minutos. */
export interface SementeDoQr {
  pedidoId: string;
  semente: string;
  /** A janela no relógio DO SERVIDOR, no instante da resposta. */
  janela: number;
  segundosDaJanela: number;
}

/** Quantos caracteres do HMAC entram no código. Espelha `TAMANHO_DO_CODIGO`
    de `api/app/cantina_token.py` — mudou lá, muda aqui. */
const TAMANHO_DO_CODIGO = 10;

/**
 * A janela AGORA, contada a partir da que o servidor mandou.
 *
 * `decorridoMs` é medido pelo chamador com um relógio monotônico. Passar a hora
 * do sistema aqui reintroduziria exatamente o problema que este desenho evita.
 */
export function janelaAtual(seed: SementeDoQr, decorridoMs: number): number {
  const passadas = Math.floor(decorridoMs / (seed.segundosDaJanela * 1000));
  // `max(0, …)` porque `performance.now` pode devolver um valor menor em
  // situações de suspensão do processo; uma janela ANTES da inicial nunca é
  // aceita pelo servidor, e não vale gerar um código que já nasce recusado.
  return seed.janela + Math.max(0, passadas);
}

/** Quantos ms faltam para a janela virar — o intervalo do próximo redesenho. */
export function msAteAProximaJanela(seed: SementeDoQr, decorridoMs: number): number {
  const passo = seed.segundosDaJanela * 1000;
  const dentro = decorridoMs % passo;
  return passo - dentro;
}

/**
 * `HMAC-SHA256(semente, janela)`, truncado — o mesmo cálculo do servidor.
 *
 * Assíncrono porque a Web Crypto é assíncrona. Não há versão síncrona possível
 * no navegador, e escrever um HMAC à mão para evitar o `await` seria trocar uma
 * primitiva auditada por código nosso no lugar mais sensível da tela.
 */
export async function codigoDaJanela(semente: string, janela: number): Promise<string> {
  const chave = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(semente),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const assinatura = await crypto.subtle.sign(
    'HMAC', chave, new TextEncoder().encode(String(janela)),
  );
  return [...new Uint8Array(assinatura)]
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, TAMANHO_DO_CODIGO);
}

/** O conteúdo do QR: `pedido.janela.codigo`. */
export function montarQr(pedidoId: string, janela: number, codigo: string): string {
  return `${pedidoId}.${janela}.${codigo}`;
}
