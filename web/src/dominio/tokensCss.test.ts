import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

// Integridade da pilha de cor: paleta → papéis → alias do aluno.
//
// A pilha tinha um quarto degrau, `tokens.css`, que traduzia os papéis para um
// alias próprio da coordenação. Ele morreu na fase 0 do docs/39 — a coordenação
// passou a ler o papel direto — e o que este teste cobre agora é o que sobrou.
//
// Este teste existe por um erro real. Ao aposentar sete entradas de
// `--coord-*`, um `*/` foi junto e comentou o bloco seguinte — sete tokens
// sumiram e `npm run build` passou, porque CSS com `var()` indefinido não é
// erro de build: a propriedade é descartada em silêncio e a tela perde a cor
// sem nada aparecer no console.
//
// O que ele cobre é a cadeia inteira: todo alias tem de chegar num literal.
// Não cobre aparência — para isso é o browser.

const AQUI = dirname(fileURLToPath(import.meta.url));
const ESTILOS = join(AQUI, '..', '..', 'styles');

const ARQUIVOS = ['paleta.css', 'papeis.css', 'aluno-tokens.css', 'documento.css'];

/**
 * Remove blocos `@media` inteiros, contando chaves.
 *
 * Sem isto o `@media print` de `documento.css` — que remapeia a paleta para
 * `--doc-*` de propósito — apareceria achatado junto com o resto e venceria,
 * porque é o último arquivo lido. O remapeamento de impressão tem teste
 * próprio, mais abaixo.
 */
function semMediaQueries(css: string): string {
  let fora = '';
  let i = 0;
  while (i < css.length) {
    const inicio = css.indexOf('@media', i);
    if (inicio < 0) return fora + css.slice(i);
    fora += css.slice(i, inicio);
    let j = css.indexOf('{', inicio);
    if (j < 0) return fora;
    let profundidade = 0;
    for (; j < css.length; j++) {
      if (css[j] === '{') profundidade++;
      else if (css[j] === '}' && --profundidade === 0) break;
    }
    i = j + 1;
  }
  return fora;
}

/** `{ '--nome': 'valor' }` de todos os blocos, na ordem em que a cascata os lê. */
function declaracoes(comMedia = false): Map<string, string> {
  const fora = new Map<string, string>();
  for (const arquivo of ARQUIVOS) {
    let css = readFileSync(join(ESTILOS, arquivo), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    if (!comMedia) css = semMediaQueries(css);
    for (const [, nome, valor] of css.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
      fora.set(nome, valor.trim());
    }
  }
  return fora;
}

/** Só as declarações do `@media print` de `documento.css`. */
function declaracoesDeImpressao(): Map<string, string> {
  const css = readFileSync(join(ESTILOS, 'documento.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  const inicio = css.indexOf('@media print');
  const fora = new Map<string, string>();
  for (const [, nome, valor] of css.slice(inicio).matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    fora.set(nome, valor.trim());
  }
  return fora;
}

/** Segue a cadeia de `var(--x)` até um literal. */
function resolver(nome: string, escopo: Map<string, string>, vistos = new Set<string>()): string {
  if (vistos.has(nome)) return `<ciclo:${nome}>`;
  vistos.add(nome);
  const valor = escopo.get(nome);
  if (valor === undefined) return `<indefinido:${nome}>`;
  const so = /^var\((--[\w-]+)\)$/.exec(valor);
  return so ? resolver(so[1], escopo, vistos) : valor;
}

describe('a pilha de tokens de cor', () => {
  const escopo = declaracoes();
  const alias = [...escopo.keys()].filter(
    (n) => n.startsWith('--alu-') || n.startsWith('--sas-'),
  );

  it('declara os papéis e o alias do aluno', () => {
    // 26 papéis e 29 nomes do aluno. O piso é frouxo de propósito: o que ele
    // pega é o bloco inteiro sumir por um comentário mal fechado, que foi o
    // erro real que fez este arquivo existir.
    expect(alias.length).toBeGreaterThan(50);
  });

  it('não deixa nenhum alias apontando para token inexistente', () => {
    const quebrados = alias
      .map((n) => [n, resolver(n, escopo)] as const)
      .filter(([, v]) => v.startsWith('<indefinido:'));
    expect(quebrados).toEqual([]);
  });

  it('não tem ciclo na cadeia de alias', () => {
    const ciclos = alias
      .map((n) => [n, resolver(n, escopo)] as const)
      .filter(([, v]) => v.startsWith('<ciclo:'));
    expect(ciclos).toEqual([]);
  });

  it('liga cada papel à paleta, para a coordenação seguir o tema', () => {
    // O bloco padrão de `papeis.css` é o DIA, e é o único que este escopo lê
    // (as media queries saem em `semMediaQueries`). O que o teste trava é o
    // acoplamento não se desfazer por acidente: um papel que passasse a ter
    // hexadecimal próprio aqui deixaria de responder ao seletor de tema.
    const papeis = ['--sas-fundo', '--sas-superficie', '--sas-texto', '--sas-borda'];
    for (const nome of papeis) {
      expect(escopo.get(nome), nome).toMatch(/var\(--dia-/);
    }
  });

  it('declara os dois tons de letra e o fio forte nos dois temas', () => {
    // `--sas-valor-texto` e `--sas-alerta-texto` existem porque a cor de TRAÇO
    // reprova em AA quando vira letra sobre fundo claro. Se um deles sumir de
    // um dos temas, o `var()` é descartado em silêncio e o texto herda a cor
    // de quem está em volta — que é justamente o que ninguém percebe.
    const comMedia = declaracoes(true);
    for (const nome of ['--sas-valor-texto', '--sas-alerta-texto', '--sas-fio-forte']) {
      expect(resolver(nome, escopo), `${nome} · dia`).toMatch(/^#|^rgba?\(/);
      expect(resolver(nome, comMedia), `${nome} · noite`).toMatch(/^#|^rgba?\(/);
    }
  });

  it('não deixa o alias do aluno apontando direto para a paleta crua', () => {
    // Apontar para `--dia-*` congela o token no tema claro. Quem precisa disso
    // é `--doc-*`, que é paleta de documento e vive em `documento.css`.
    const congelados = [...escopo.entries()].filter(
      ([nome, valor]) => nome.startsWith('--alu-') && /var\(--(dia|noite|coord)-/.test(valor),
    );
    expect(congelados).toEqual([]);
  });

  it('congela a paleta na impressão, para o dossiê não sair preto à noite', () => {
    // O contrário da regra acima, e é o ponto: documento impresso NÃO tem
    // tema. Dois caminhos de exportação herdam o CSS da página viva — o PDF da
    // ficha e o `.panorama` —, então sem este remapeamento quem trabalha à
    // noite mandaria para a impressora um dossiê preto, sem erro e sem aviso.
    //
    // Depois que o alias da coordenação morreu, a lista de baixo é a ÚNICA
    // proteção: o que a tela lê no papel é papel, e papel responde a tema.
    const print = declaracoesDeImpressao();
    // Duas exceções, cada uma por um motivo. `--sas-borda-l` é LARGURA, não
    // cor — o bloco de impressão a fixa em 1px e está certo. `--sas-hachura`
    // é um `repeating-linear-gradient` e nunca foi remapeado: a dívida é
    // anterior a este trabalho e o traço da hachura no papel sai no tom do
    // tema em vigor.
    const foraDaRegra = new Set(['--sas-borda-l', '--sas-hachura']);
    const papeis = [...escopo.keys()].filter((n) => n.startsWith('--sas-') && !foraDaRegra.has(n));
    for (const nome of papeis) {
      expect(print.get(nome), nome).toMatch(/var\(--doc-|^#|^rgba?\(|^transparent$/);
    }
    // E nada no bloco de impressão pode voltar a apontar para papel.
    const vazamentos = [...print.entries()].filter(([, v]) => /var\(--sas-/.test(v));
    expect(vazamentos).toEqual([]);
  });
});
