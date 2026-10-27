// A VOLTA DO LOGIN — para onde a pessoa vai depois de entrar.
//
// Até 24/10 o login mandava todo mundo para `/`, e quem chegava deslogado num
// link perdia o link no caminho. A sessão do SAS mora no `sessionStorage`, que
// é por aba: todo link aberto numa aba NOVA chega sem sessão, e sem a volta a
// pessoa caía no Painel e tinha de achar a tela de novo.
//
// A volta nasceu por causa do consentimento do OAuth (docs/43 §5.3), a tela que
// chegava SEMPRE assim. Desde 26/10 o consentimento é PÚBLICO — a aprovação é
// pelo código mandado ao e-mail da IA (`dominio/conexoesDeIa.ts`) — e não passa
// mais pelo login: a rota dele fica fora da `RotaProtegida` (`App.tsx`). A
// volta ficou pelos outros links, que continuam chegando sem sessão.
//
// ⚠️ É redirecionamento a partir de dado que veio na URL, e por isso aceita só
// caminho INTERNO. Uma URL absoluta aqui é redirecionamento aberto: o link
// `…/login?proximo=https://sas-falso.com` levaria a coordenadora, recém-logada e
// confiando no endereço, para uma cópia do SAS pedindo a senha de novo.

/**
 * Origem de conferência: o caminho é resolvido contra ela e tem de continuar
 * nela. `.invalid` é o domínio reservado para isto (RFC 2606) — nunca resolve.
 */
const ORIGEM_DE_CONFERENCIA = 'https://sas.invalid';

/** As portas de entrada. Voltar para uma delas depois de entrar seria laço. */
const ROTAS_DE_LOGIN = ['/login', '/login-cantina'];

function temCaractereDeControle(texto: string): boolean {
  for (let i = 0; i < texto.length; i++) {
    const codigo = texto.charCodeAt(i);
    if (codigo < 0x20 || codigo === 0x7f) return true;
  }
  return false;
}

/**
 * O caminho do jeito que o ROTEADOR o lê ao casar com as rotas: sem a query,
 * cada segmento decodificado, sem diferenciar maiúscula e sem barra no fim.
 *
 * ⚠️ É o que o react-router 7 faz, e comparar o texto cru não basta.
 * `decodePath` decodifica segmento por segmento e mantém o `/` codificado como
 * `%2F`. `compilePath` monta a expressão com a flag `i` e aceita `\/*$` no
 * fim. Por isso `/LOGIN`, `/%6Cogin` e `/login/` abrem o login, e com o texto
 * cru os três passavam por "não é o login". Era o laço que a regra existe
 * para impedir.
 */
function comoORoteadorLe(caminho: string): string {
  const semQuery = caminho.split(/[?#]/, 1)[0];
  let decodificado = semQuery;
  try {
    decodificado = semQuery
      .split('/')
      .map((segmento) => decodeURIComponent(segmento).replace(/\//g, '%2F'))
      .join('/');
  } catch {
    // Codificação quebrada: o roteador também fica com o texto como veio.
  }
  return decodificado.toLowerCase().replace(/\/+$/, '') || '/';
}

function ehRotaDeLogin(caminho: string): boolean {
  const lido = comoORoteadorLe(caminho);
  return ROTAS_DE_LOGIN.some((rota) => lido === rota || lido.startsWith(`${rota}/`));
}

/**
 * O destino, se ele for um caminho interno do SAS; `null` em qualquer outro caso.
 *
 * As recusas, cada uma por um caminho real de fuga:
 *   - não começa com `/`        → URL absoluta, `javascript:`, texto solto;
 *   - começa com `//`           → URL relativa ao PROTOCOLO, que é outro host;
 *   - tem `\` em qualquer lugar → o parser de URL do browser lê `\` como `/`,
 *                                  e `/\sas-falso.com` vira `//sas-falso.com`;
 *   - tem caractere de controle → o parser descarta tab e quebra de linha, e é
 *                                  assim que `/<tab>/sas-falso.com` vira `//…`.
 * Depois das recusas baratas, a conferência que não depende de eu ter pensado
 * em tudo: resolver contra uma origem fixa e exigir que ela não mude.
 *
 * Nenhum caminho do SAS tem `\` nem caractere de controle, então recusar os
 * dois não custa link legítimo nenhum.
 */
export function destinoInterno(proximo: string | null | undefined): string | null {
  if (!proximo?.startsWith('/')) return null;
  if (proximo.startsWith('//') || proximo.includes('\\') || temCaractereDeControle(proximo)) {
    return null;
  }
  let url: URL;
  try {
    url = new URL(proximo, ORIGEM_DE_CONFERENCIA);
  } catch {
    return null;
  }
  if (url.origin !== ORIGEM_DE_CONFERENCIA) return null;
  // ⚠️ A conferência tem de ser no caminho JÁ NORMALIZADO, e não só na
  // entrada: `/..//sas-falso.com` passa por todas as recusas acima, e o
  // parser, ao resolver o `..`, devolve o caminho `//sas-falso.com` — que,
  // entregue a quem navega, volta a ser URL relativa ao protocolo.
  if (url.pathname.startsWith('//')) return null;
  if (ehRotaDeLogin(url.pathname)) return null;
  return `${url.pathname}${url.search}${url.hash}`;
}

/**
 * O endereço do login que guarda o caminho de volta.
 *
 * `/` não vai junto: é o destino padrão de qualquer forma, e `?proximo=%2F` na
 * barra de endereço só seria ruído. O caminho vai codificado na query string —
 * `?` e `&` do caminho original ficariam ambíguos sem isso, e a query de uma
 * tela com filtro é justamente o que não se pode perder.
 *
 * ⚠️ A PORTA do login não sai do destino, e é de propósito. Até 26/10 o
 * consentimento do OAuth abria direto a porta da coordenação; ele saiu do
 * login, e "toda rota da coordenação" não serve de regra no lugar dele: aluno
 * e coordenação dividem caminhos (`/provas` existe nos dois cascos), e
 * adivinhar a porta pelo resto da URL erraria em silêncio. Abre a do aluno,
 * como sempre (`Porta.tsx`: são ~900 contra uma dúzia).
 */
export function enderecoDoLogin(caminhoAtual: string): string {
  const destino = destinoInterno(caminhoAtual);
  if (!destino || destino === '/') return '/login';
  return `/login?${new URLSearchParams({ proximo: destino }).toString()}`;
}
