import { afterEach, describe, expect, it, vi } from 'vitest';

import { recarregarUmaVezSeChunkSumiu } from './recuperacaoDeChunk';

// A defesa contra "tela branca depois de F5 resolver": uma aba com o
// `index.html` de uma build anterior tentando um `import()` dinâmico que já
// não existe mais no servidor. `window`/`sessionStorage` não existem em
// node — mesmo empréstimo de `http.test.ts`.

function comBrowser() {
  const listeners: Record<string, Array<() => void>> = {};
  const location = { reload: vi.fn() };
  vi.stubGlobal('window', {
    addEventListener: (nome: string, fn: () => void) => {
      if (!listeners[nome]) listeners[nome] = [];
      listeners[nome].push(fn);
    },
    location,
  });
  return {
    location,
    disparar(nome: string) {
      for (const fn of listeners[nome] ?? []) fn();
    },
  };
}

function comSessionStorage(inicial: Record<string, string> = {}) {
  const armazenamento = new Map(Object.entries(inicial));
  vi.stubGlobal('sessionStorage', {
    getItem: (k: string) => armazenamento.get(k) ?? null,
    setItem: (k: string, v: string) => void armazenamento.set(k, v),
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('recarregarUmaVezSeChunkSumiu', () => {
  it('recarrega quando o Vite avisa que um chunk sumiu', () => {
    comSessionStorage();
    const janela = comBrowser();

    recarregarUmaVezSeChunkSumiu();
    janela.disparar('vite:preloadError');

    expect(janela.location.reload).toHaveBeenCalledOnce();
  });

  it('não recarrega de novo na mesma sessão — evita loop se o 404 for por outro motivo', () => {
    comSessionStorage({ 'sas:recarregou-apos-chunk-perdido': '1' });
    const janela = comBrowser();

    recarregarUmaVezSeChunkSumiu();
    janela.disparar('vite:preloadError');

    expect(janela.location.reload).not.toHaveBeenCalled();
  });
});
