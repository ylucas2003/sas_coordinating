import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

// Integridade da pilha de cor: paleta → papéis → alias.
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

const ARQUIVOS = ['paleta.css', 'papeis.css', 'tokens.css', 'aluno-tokens.css', 'documento.css'];

/** `{ '--nome': 'valor' }` de todos os blocos, na ordem em que a cascata os lê. */
function declaracoes(): Map<string, string> {
  const fora = new Map<string, string>();
  for (const arquivo of ARQUIVOS) {
    const css = readFileSync(join(ESTILOS, arquivo), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    for (const [, nome, valor] of css.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
      fora.set(nome, valor.trim());
    }
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
    (n) => n.startsWith('--color-') || n.startsWith('--alu-') || n.startsWith('--sas-'),
  );

  it('declara alias para os três prefixos', () => {
    expect(alias.length).toBeGreaterThan(60);
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

  it('mantém `--color-*` fora do tema enquanto a coordenação não tem seletor', () => {
    // A armadilha que a pilha inteira existe para evitar: `data-tema` já está
    // estampado na raiz em todo boot (`pecas/tema.ts`, escopo de módulo), então
    // um `--color-*` apontando para papel escureceria a coordenação sem
    // seletor e sem aviso. Quando o tema escuro entrar, este teste muda junto —
    // de propósito, para a troca ser uma decisão e não um acidente.
    const paraPapel = [...escopo.entries()].filter(
      ([nome, valor]) => nome.startsWith('--color-') && /var\(--sas-/.test(valor),
    );
    expect(paraPapel).toEqual([]);
  });
});
