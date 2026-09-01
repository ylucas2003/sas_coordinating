/**
 * Markdown leve COM FÓRMULA — a gramática que o banco de questões e o Tio Léo
 * realmente escrevem.
 *
 * Por que um analisador próprio em vez de `react-markdown` + `remark-math`:
 * aquela pilha traz ~40 pacotes transitivos para cobrir uma gramática que o
 * corpus não usa. Medido nas 1.500 resoluções do banco em 01/09/2026: 1.246
 * usam `$`, 639 usam `$$`, 366 usam negrito, 107 usam lista — e NENHUMA usa
 * título, tabela, link, imagem ou bloco de código. O front tinha quatro
 * dependências de runtime; não vale trocar isso por uma árvore inteira.
 *
 * ⚠️ A ORDEM É A RAZÃO DE ESTE ARQUIVO EXISTIR. A fórmula sai do texto **antes**
 * de qualquer regra de Markdown. Ao contrário, `a_1` viraria subscrito de
 * Markdown, `2*3*4` viraria itálico e o `\\` de quebra de linha do LaTeX
 * sumiria — é exatamente assim que renderizador genérico estraga LaTeX. Aqui o
 * conteúdo de `$…$` chega ao KaTeX byte a byte como foi escrito.
 *
 * O que NÃO está na gramática, de propósito: HTML, link e imagem. O texto vem
 * de LLM (resolução sugerida do banco, resposta do Tio Léo), e ampliar a
 * gramática ampliaria a superfície de injeção sem ganho para o caso de uso —
 * mesma regra que o `Markdown.tsx` do chat já seguia antes de virar isto.
 */

/** Um pedaço dentro de uma linha: texto corrido, ênfase ou fórmula. */
export type Trecho =
  | { tipo: 'texto'; valor: string }
  | { tipo: 'negrito'; valor: string }
  | { tipo: 'italico'; valor: string }
  | { tipo: 'formula'; tex: string };

/** Um bloco do texto. `formula` aqui é a de display (`$$…$$`), que ocupa linha. */
export type Bloco =
  | { tipo: 'paragrafo'; linhas: Trecho[][] }
  | { tipo: 'lista'; ordenada: boolean; itens: Trecho[][] }
  | { tipo: 'formula'; tex: string };

// `$$…$$` é o delimitador de 99,8% do corpus; `\[…\]` aparece em uma resolução
// só, mas custa uma alternância reconhecer e não custa nada manter.
const RE_FORMULA_BLOCO = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]/g;

// Fórmula de linha não atravessa quebra: sem o `[^$\n]` um `$` solto (moeda, ou
// o `$` desemparelhado que existe em duas resoluções) engoliria parágrafos
// inteiros até achar o próximo.
//
// ⚠️ Limitação conhecida: `$` ANINHADO dentro de `\text{}` — `\text{H$_2$O}` é
// LaTeX legítimo, e aqui o primeiro `$` interno fecha a fórmula cedo demais.
// Duas resoluções tinham isso; as duas foram reescritas sem aninhar (migration
// 0040), porque uma gramática que equilibra chave para achar o delimitador
// custaria mais do que o problema. Se um dia aparecer em quantidade, é AQUI
// que se mexe — não no dado.
const RE_FORMULA_LINHA = /\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g;

const RE_MARCACAO = /(\*\*[^*]+\*\*|\*[^*\n]+\*)/g;

// ── Quando uma fórmula de linha merece virar bloco ───────────────────────
//
// Metade do acervo escreve `$$` e ganha o painel destacado; a outra metade
// escreve a mesma conta entre `$` e some no meio da prosa. Não é diferença de
// conteúdo, é de quem digitou — e o aluno paga, porque o passo da conta fica
// indistinguível da frase que o explica.
//
// A intenção do autor está no comando que ele escolheu, e é isso que a regra lê:
//
//   `\dfrac`  — pede explicitamente tamanho de display. Promove.
//   `\tfrac`  — pede explicitamente tamanho de linha. NUNCA promove.
//   `\sum` `\int` `\prod` `\oint` `\lim` e matriz — não cabem numa linha de
//              texto em tamanho nenhum. Promovem.
//
// `\frac` fica de fora de propósito: em contexto de linha o próprio LaTeX o
// renderiza pequeno, então quem o escreveu não pediu destaque.
//
// Medido no acervo em 01/09/2026: promove 844 de 12.690 fórmulas de linha
// (6,7%), e 402 resoluções ganham painel sem que ninguém reescreva nada.
const RE_CONSTRUIDA = /\\dfrac|\\sum|\\prod|\\int|\\oint|\\lim|\\begin\{[pbvV]?matrix\}/;

// Abaixo disto não é passo de conta, é símbolo: `$\lim a_n$` no meio da frase
// vira um painel ridículo com três caracteres dentro.
const MINIMO_PARA_PROMOVER = 10;

// Pontuação que a fórmula promovida leva junto. Sem isto o parágrafo seguinte
// abre com ". Chamando de…", que parece defeito. É também o que o livro-texto
// faz: a pontuação da frase fecha a equação em display.
const RE_PONTUACAO_A_ABSORVER = /^[\s]*([.,;:])/;

function merecePainel(tex: string): boolean {
  return tex.length >= MINIMO_PARA_PROMOVER && RE_CONSTRUIDA.test(tex);
}

// O espaço depois do marcador é obrigatório, e é ele que separa `- item` de um
// sinal de menos (`-15a_1r`) e `* item` de `*itálico*`.
const RE_ITEM = /^[-*•]\s+(.*)$/;
const RE_ITEM_NUMERADO = /^\d{1,2}[.)]\s+(.*)$/;

/** Quebra o texto em blocos, com a fórmula preservada intacta. */
export function analisarMarkdown(texto: string): Bloco[] {
  const blocos: Bloco[] = [];
  let fim = 0;

  RE_FORMULA_BLOCO.lastIndex = 0;
  for (let m = RE_FORMULA_BLOCO.exec(texto); m; m = RE_FORMULA_BLOCO.exec(texto)) {
    blocosDeTexto(texto.slice(fim, m.index), blocos);
    const tex = (m[1] ?? m[2] ?? '').trim();
    if (tex) blocos.push({ tipo: 'formula', tex });
    fim = m.index + m[0].length;
  }
  blocosDeTexto(texto.slice(fim), blocos);

  return blocos;
}

/**
 * Os blocos de um trecho sem fórmula de display.
 *
 * Linha em branco separa parágrafo; quebra simples é quebra DENTRO do
 * parágrafo. A diferença importa para a resolução: o corpus encadeia passos de
 * conta em linhas seguidas ("Nó D: …\nNó F: …") e separa as etapas do
 * raciocínio com linha em branco. Tratar toda quebra como parágrafo novo — o
 * que o renderizador do chat fazia — espalha os passos como se fossem
 * assuntos diferentes.
 */
function blocosDeTexto(trecho: string, blocos: Bloco[]): void {
  let paragrafo: Trecho[][] = [];
  let itens: Trecho[][] = [];
  let ordenada = false;

  const fecharParagrafo = () => {
    if (!paragrafo.length) return;
    emitirParagrafo(paragrafo, blocos);
    paragrafo = [];
  };
  const fecharLista = () => {
    if (!itens.length) return;
    blocos.push({ tipo: 'lista', ordenada, itens });
    itens = [];
  };

  for (const bruta of trecho.split('\n')) {
    const linha = bruta.trim();
    if (!linha) {
      fecharParagrafo();
      fecharLista();
      continue;
    }

    const numerado = linha.match(RE_ITEM_NUMERADO);
    const marcado = numerado ? null : linha.match(RE_ITEM);
    if (numerado || marcado) {
      fecharParagrafo();
      const querOrdenada = numerado !== null;
      // Trocar de tipo no meio fecha a lista anterior: `<ol>` e `<ul>` são
      // elementos diferentes, não dá para emendar itens de um no outro.
      if (itens.length && ordenada !== querOrdenada) fecharLista();
      ordenada = querOrdenada;
      itens.push(trechosDaLinha((numerado ?? marcado)![1]));
      continue;
    }

    fecharLista();
    paragrafo.push(trechosDaLinha(linha));
  }

  fecharParagrafo();
  fecharLista();
}

/** Tira o espaço solto da ponta de uma linha, quando ela é texto. */
function apararPonta(linha: Trecho[], ponta: 'inicio' | 'fim'): void {
  const i = ponta === 'inicio' ? 0 : linha.length - 1;
  const trecho = linha[i];
  if (trecho?.tipo !== 'texto') return;
  const valor =
    ponta === 'inicio' ? trecho.valor.replace(/^\s+/, '') : trecho.valor.replace(/\s+$/, '');
  linha[i] = { tipo: 'texto', valor };
}

/**
 * Emite o parágrafo, quebrando-o onde uma fórmula merece painel próprio.
 *
 * O parágrafo é a unidade errada para uma conta construída: `$K_h=\dfrac{\ldots}
 * {\ldots}$` no meio da frase estica a linha e some no texto. Aqui ele vira
 * três blocos — o que veio antes, a fórmula em display, o que veio depois — e a
 * resolução passa a ter o mesmo ritmo de quem escreveu `$$` na mão.
 *
 * Dentro de LISTA isto não roda: um bloco de display dentro de `<li>` quebra o
 * alinhamento do marcador, e item de lista já é uma unidade curta o bastante.
 */
function emitirParagrafo(linhas: Trecho[][], blocos: Bloco[]): void {
  let acumuladas: Trecho[][] = [];
  let linha: Trecho[] = [];

  // Sobra de espaço em branco não é parágrafo. Depois de promover uma fórmula,
  // o que vem antes pode ser só o " " que separava a frase dela.
  const temConteudo = (trechos: Trecho[]) =>
    trechos.some((t) => (t.tipo === 'formula' ? true : t.valor.trim() !== ''));

  const fecharLinha = () => {
    if (temConteudo(linha)) acumuladas.push(linha);
    linha = [];
  };
  const fecharBloco = () => {
    fecharLinha();
    if (acumuladas.length) {
      // As pontas do parágrafo: promover uma fórmula deixa para trás o espaço
      // que a separava da frase, e ele viraria recuo de um caractere.
      apararPonta(acumuladas[0], 'inicio');
      apararPonta(acumuladas[acumuladas.length - 1], 'fim');
      blocos.push({ tipo: 'paragrafo', linhas: acumuladas });
    }
    acumuladas = [];
  };

  for (const original of linhas) {
    for (let i = 0; i < original.length; i++) {
      const trecho = original[i];
      if (trecho.tipo !== 'formula' || !merecePainel(trecho.tex)) {
        linha.push(trecho);
        continue;
      }

      // A pontuação que fecharia a frase vai junto com a fórmula.
      const seguinte = original[i + 1];
      let tex = trecho.tex;
      if (seguinte?.tipo === 'texto') {
        const pontuacao = seguinte.valor.match(RE_PONTUACAO_A_ABSORVER);
        if (pontuacao) {
          tex += pontuacao[1];
          original[i + 1] = {
            tipo: 'texto',
            valor: seguinte.valor.slice(pontuacao[0].length),
          };
        }
      }

      fecharBloco();
      blocos.push({ tipo: 'formula', tex });
    }
    fecharLinha();
  }

  fecharBloco();
}

/** Os trechos de uma linha: fórmula primeiro, ênfase só no que sobra. */
function trechosDaLinha(linha: string): Trecho[] {
  const trechos: Trecho[] = [];
  let fim = 0;

  RE_FORMULA_LINHA.lastIndex = 0;
  for (let m = RE_FORMULA_LINHA.exec(linha); m; m = RE_FORMULA_LINHA.exec(linha)) {
    aplicarMarcacao(linha.slice(fim, m.index), trechos);
    const tex = (m[1] ?? m[2] ?? '').trim();
    if (tex) trechos.push({ tipo: 'formula', tex });
    fim = m.index + m[0].length;
  }
  aplicarMarcacao(linha.slice(fim), trechos);

  return trechos;
}

/**
 * Negrito e itálico no texto que não é fórmula.
 *
 * `_sublinhado_` fica de fora por segurança: `_` é subscrito de LaTeX e, numa
 * fórmula que escapou da extração por estar mal delimitada, viraria itálico e
 * comeria a variável.
 */
function aplicarMarcacao(texto: string, trechos: Trecho[]): void {
  if (!texto) return;

  for (const pedaco of texto.split(RE_MARCACAO)) {
    if (!pedaco) continue;
    if (pedaco.startsWith('**') && pedaco.endsWith('**') && pedaco.length > 4) {
      trechos.push({ tipo: 'negrito', valor: pedaco.slice(2, -2) });
    } else if (pedaco.startsWith('*') && pedaco.endsWith('*') && pedaco.length > 2) {
      trechos.push({ tipo: 'italico', valor: pedaco.slice(1, -1) });
    } else {
      trechos.push({ tipo: 'texto', valor: pedaco });
    }
  }
}
