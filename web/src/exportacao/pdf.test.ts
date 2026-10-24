import { describe, expect, it } from 'vitest';

import { escreverPdfDeImagem, textoDePdf } from './pdf';

// Um "JPEG" de mentira, mas com os bytes que importam: começa em FFD8, termina em FFD9
// e tem bytes altos (inclusive um 0x0A e um 0x0D — os que um PDF lido como texto estraga).
const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0x0a, 0x0d, 0x80, 0xfe, 0x00, 0xff, 0xd9]);

const pagina = {
  jpeg: JPEG,
  larguraPx: 2526,
  alturaPx: 1785,
  larguraPt: 842,
  alturaPt: 595,
  titulo: 'Horário de estudos',
  criadoEm: new Date(Date.UTC(2026, 9, 24, 15, 30, 5)),
};

/** O arquivo como texto latin-1: cada byte vira UM caractere, e os deslocamentos continuam valendo. */
function comoTexto(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return s;
}

describe('escreverPdfDeImagem', () => {
  const bytes = escreverPdfDeImagem(pagina);
  const texto = comoTexto(bytes);

  it('é um PDF: cabeçalho, comentário binário e fim de arquivo', () => {
    expect(texto.startsWith('%PDF-1.4\n%')).toBe(true);
    // O comentário binário é o que impede um programa de ler o arquivo como texto e o reencodar.
    expect(bytes[10]).toBeGreaterThan(127);
    expect(texto.endsWith('%%EOF\n')).toBe(true);
  });

  it('⚠️ UMA PÁGINA: o documento declara exatamente uma', () => {
    expect(texto).toContain('/Count 1');
    expect(texto.match(/\/Type \/Page /g)).toHaveLength(1);
    expect(texto).toContain('/Kids [3 0 R]');
  });

  it('a página é A4 deitada, e a imagem a preenche inteira', () => {
    expect(texto).toContain('/MediaBox [0 0 842 595]');
    expect(texto).toContain('q 842 0 0 595 0 0 cm /Im0 Do Q');
  });

  it('a imagem leva as dimensões em pixels e o filtro JPEG', () => {
    expect(texto).toContain('/Width 2526 /Height 1785');
    expect(texto).toContain('/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode');
  });

  it('⚠️ o JPEG vai INTEIRO e SEM alteração — inclusive os bytes que um texto estragaria', () => {
    const achou = indiceDe(bytes, JPEG);
    expect(achou).toBeGreaterThan(0);
    expect([...bytes.slice(achou, achou + JPEG.length)]).toEqual([...JPEG]);
    // e o `/Length` do objeto é o tamanho real do JPEG
    expect(texto).toContain(`/Length ${JPEG.length} >>\nstream\n`);
    expect(comoTexto(bytes.slice(achou + JPEG.length, achou + JPEG.length + 10))).toBe('\nendstream');
  });

  it('⚠️ a tabela de referências aponta para o byte exato de cada objeto', () => {
    const inicio = Number(/startxref\n(\d+)\n/.exec(texto)?.[1]);
    expect(texto.slice(inicio, inicio + 4)).toBe('xref');

    const linhas = texto.slice(inicio).split('\n');
    const total = Number(linhas[1].split(' ')[1]);
    expect(total).toBe(7); // o objeto 0 (livre) e os seis de verdade
    expect(linhas[2]).toBe('0000000000 65535 f ');
    for (let n = 1; n < total; n++) {
      const deslocamento = Number(linhas[2 + n].slice(0, 10));
      expect(texto.slice(deslocamento, deslocamento + `${n} 0 obj`.length), `objeto ${n}`).toBe(`${n} 0 obj`);
    }
  });

  it('o /Length do fluxo de conteúdo bate com o conteúdo', () => {
    const m = /4 0 obj\n<< \/Length (\d+) >>\nstream\n([\s\S]*?)endstream/.exec(texto);
    expect(Number(m?.[1])).toBe(m?.[2].length);
  });

  it('o título com acento vai em UTF-16BE, e a data em UTC', () => {
    expect(texto).toContain(`/Title ${textoDePdf('Horário de estudos')}`);
    expect(texto).toContain('/CreationDate (D:20261024153005Z)');
    expect(textoDePdf('á')).toBe('<FEFF00E1>');
  });

  it('é determinístico: a mesma entrada dá o mesmo arquivo', () => {
    expect([...escreverPdfDeImagem(pagina)]).toEqual([...bytes]);
  });

  it('o tamanho da página não vira notação científica nem casas de sobra', () => {
    const t = comoTexto(escreverPdfDeImagem({ ...pagina, larguraPt: 841.8900001, alturaPt: 595.28 }));
    expect(t).toContain('/MediaBox [0 0 841.89 595.28]');
    expect(t).not.toMatch(/e[+-]\d/);
  });
});

function indiceDe(tudo: Uint8Array, trecho: Uint8Array): number {
  busca: for (let i = 0; i <= tudo.length - trecho.length; i++) {
    for (let j = 0; j < trecho.length; j++) if (tudo[i + j] !== trecho[j]) continue busca;
    return i;
  }
  return -1;
}
