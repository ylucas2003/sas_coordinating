import { describe, expect, it } from 'vitest';
import { analisarMarkdown } from './markdown';
import type { Bloco, Trecho } from './markdown';

/** O texto de um bloco, ignorando a marcação — atalho para as asserções. */
function texto(bloco: Bloco): string {
  const linhas =
    bloco.tipo === 'paragrafo' ? bloco.linhas : bloco.tipo === 'lista' ? bloco.itens : [];
  return linhas.map((l) => l.map(planoDoTrecho).join('')).join(' ⏎ ');
}

function planoDoTrecho(t: Trecho): string {
  return t.tipo === 'formula' ? `⟨${t.tex}⟩` : t.valor;
}

describe('analisarMarkdown', () => {
  it('separa parágrafos por linha em branco e mantém a quebra simples dentro do parágrafo', () => {
    const blocos = analisarMarkdown('Nó D: zero.\nNó F: vinte.\n\nNó A: quarenta.');

    expect(blocos).toHaveLength(2);
    expect(texto(blocos[0])).toBe('Nó D: zero. ⏎ Nó F: vinte.');
    expect(texto(blocos[1])).toBe('Nó A: quarenta.');
  });

  it('reconhece fórmula de linha e de bloco', () => {
    const blocos = analisarMarkdown('A carga é $q=N\\Delta\\Phi$.\n\n$$F=40\\ \\text{kN}$$');

    expect(blocos[0]).toEqual({
      tipo: 'paragrafo',
      linhas: [
        [
          { tipo: 'texto', valor: 'A carga é ' },
          { tipo: 'formula', tex: 'q=N\\Delta\\Phi' },
          { tipo: 'texto', valor: '.' },
        ],
      ],
    });
    expect(blocos[1]).toEqual({ tipo: 'formula', tex: 'F=40\\ \\text{kN}' });
  });

  // A regressão que motivou o arquivo: um renderizador genérico leria `a_1` e
  // `v'_{1y}` como marcação e devolveria LaTeX mutilado ao KaTeX.
  it('não deixa a regra de Markdown tocar no conteúdo da fórmula', () => {
    const blocos = analisarMarkdown('Some $x_1*y_2$ e $\\tfrac12m_1v^2$ com **peso**.');
    const trechos = (blocos[0] as { linhas: Trecho[][] }).linhas[0];

    expect(trechos).toContainEqual({ tipo: 'formula', tex: 'x_1*y_2' });
    expect(trechos).toContainEqual({ tipo: 'formula', tex: '\\tfrac12m_1v^2' });
    expect(trechos).toContainEqual({ tipo: 'negrito', valor: 'peso' });
  });

  it('mantém a barra dupla de quebra do LaTeX, que um remark comeria', () => {
    const blocos = analisarMarkdown('$$a=b\\\\c=d$$');

    expect(blocos[0]).toEqual({ tipo: 'formula', tex: 'a=b\\\\c=d' });
  });

  it('fecha a fórmula de linha na quebra, para um `$` solto não engolir o resto', () => {
    const blocos = analisarMarkdown('Custa $50 reais.\n\nOutro parágrafo.');

    expect(blocos).toHaveLength(2);
    expect(texto(blocos[0])).toBe('Custa $50 reais.');
    expect(texto(blocos[1])).toBe('Outro parágrafo.');
  });

  it('lê lista com marcador e lista numerada, sem confundir com sinal de menos', () => {
    const comMarcador = analisarMarkdown('- primeiro\n- segundo');
    expect(comMarcador[0]).toMatchObject({ tipo: 'lista', ordenada: false });
    expect(texto(comMarcador[0])).toBe('primeiro ⏎ segundo');

    const numerada = analisarMarkdown('1. um\n2. dois');
    expect(numerada[0]).toMatchObject({ tipo: 'lista', ordenada: true });

    const menos = analisarMarkdown('-15a+10b=0');
    expect(menos[0].tipo).toBe('paragrafo');
  });

  it('separa a lista com marcador da numerada em vez de emendar as duas', () => {
    const blocos = analisarMarkdown('- um\n1. dois');

    expect(blocos).toHaveLength(2);
    expect(blocos[0]).toMatchObject({ tipo: 'lista', ordenada: false });
    expect(blocos[1]).toMatchObject({ tipo: 'lista', ordenada: true });
  });

  it('aceita os delimitadores `\\[ \\]` e `\\( \\)`, que aparecem em duas resoluções', () => {
    expect(analisarMarkdown('\\[x=1\\]')[0]).toEqual({ tipo: 'formula', tex: 'x=1' });
    expect(texto(analisarMarkdown('vale \\(x=1\\) sempre')[0])).toBe('vale ⟨x=1⟩ sempre');
  });

  // ── Promoção a painel ───────────────────────────────────────────────────
  // Metade do acervo escreve `$$` e ganha o bloco destacado; a outra metade
  // escreve a mesma conta entre `$`. A regra lê a intenção no comando.

  it('promove a painel a fórmula construída que estava presa na linha', () => {
    const blocos = analisarMarkdown('com constante $K_h=\\dfrac{[HA]}{[A^-]}$. Chamando de $x$ a razão.');

    expect(blocos.map((b) => b.tipo)).toEqual(['paragrafo', 'formula', 'paragrafo']);
    expect(texto(blocos[0])).toBe('com constante');
    // A pontuação da frase fecha a equação, como no livro-texto — e não sobra
    // um parágrafo abrindo com ". Chamando".
    expect(blocos[1]).toEqual({ tipo: 'formula', tex: 'K_h=\\dfrac{[HA]}{[A^-]}.' });
    expect(texto(blocos[2])).toBe('Chamando de ⟨x⟩ a razão.');
  });

  it('respeita o `\\tfrac`, que é o autor pedindo tamanho de linha', () => {
    const blocos = analisarMarkdown('a energia $\\tfrac12 kx^2=mgh(1-\\cos\\theta)$ se conserva.');

    expect(blocos).toHaveLength(1);
    expect(blocos[0].tipo).toBe('paragrafo');
  });

  it('promove operador grande e matriz, que não cabem em linha nenhuma', () => {
    for (const tex of ['\\sum_{i=1}^{n} a_i x_i', '\\int_0^{\\pi} \\sin x\\,dx', '\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}']) {
      const blocos = analisarMarkdown(`vale $${tex}$ sempre`);
      expect(blocos.map((b) => b.tipo)).toEqual(['paragrafo', 'formula', 'paragrafo']);
    }
  });

  it('não promove símbolo curto, que viraria painel de três caracteres', () => {
    const blocos = analisarMarkdown('o valor de $\\lim a_n$ existe.');

    expect(blocos).toHaveLength(1);
  });

  it('não promove dentro de lista, onde o painel quebraria o marcador', () => {
    const blocos = analisarMarkdown('- vale $K=\\dfrac{[HA][OH]}{[A]}$ aqui\n- e aqui');

    expect(blocos).toHaveLength(1);
    expect(blocos[0]).toMatchObject({ tipo: 'lista', ordenada: false });
  });

  it('não deixa parágrafo vazio quando a fórmula era tudo que havia', () => {
    const blocos = analisarMarkdown('$K_h=\\dfrac{[HA]}{[A^-]}$');

    expect(blocos).toEqual([{ tipo: 'formula', tex: 'K_h=\\dfrac{[HA]}{[A^-]}' }]);
  });

  it('não inventa bloco para texto vazio', () => {
    expect(analisarMarkdown('')).toEqual([]);
    expect(analisarMarkdown('\n\n  \n')).toEqual([]);
  });
});
