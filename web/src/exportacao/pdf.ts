// Um PDF de UMA página, com uma imagem JPEG que a preenche inteira.
//
// ⚠️ POR QUE O PDF É UMA IMAGEM, e não texto e vetor. O pedido foi "o PDF em uma
// página só" e "o mesmo design do site do aluno". Texto de verdade num PDF exige
// embutir a fonte do site (Plus Jakarta Sans, que o projeto só serve como WOFF2 — e
// WOFF2 é Brotli, que o navegador não descomprime sem biblioteca); sem embutir, o PDF
// sairia em Helvetica e a cara do site iria embora. Com a imagem, o PDF é o PNG, pixel
// por pixel — mesma fonte, mesma logo, mesmas cores nos dois temas — e a página única
// vem de graça: não há texto que reflua para uma segunda folha.
//
// O custo é conhecido e aceito: o texto não é selecionável nem pesquisável, e o
// arquivo é maior que o vetorial. A 3× (A4 a ~250 dpi) o horário imprime nítido.
//
// ⚠️ Escrito à mão porque é UM objeto de imagem numa página: seis objetos, uma tabela
// de referências cruzadas, e nenhuma biblioteca de ~300 KB para isso. O JPEG vai CRU,
// com `/DCTDecode` — o PDF entende o formato que `canvas.toBlob('image/jpeg')` devolve,
// sem decodificar nem recomprimir nada.

export interface PaginaComImagem {
  /** O JPEG baseline em RGB, como o navegador o devolve. */
  jpeg: Uint8Array;
  larguraPx: number;
  alturaPx: number;
  /** O tamanho da página, em pontos: A4 deitado é 842 × 595. */
  larguraPt: number;
  alturaPt: number;
  titulo: string;
  criadoEm: Date;
}

const ASCII = new TextEncoder();

function dois(n: number): string {
  return String(n).padStart(2, '0');
}

/** Um número de PDF: sem notação científica, e sem zeros de sobra. */
function num(n: number): string {
  return Number(n.toFixed(3)).toString();
}

/**
 * Uma string de PDF em UTF-16BE (`<FEFF…>`). É como o PDF guarda um título com
 * acento ("Horário de estudos") sem depender da codificação do arquivo.
 */
export function textoDePdf(texto: string): string {
  let hex = 'FEFF';
  for (let i = 0; i < texto.length; i++) {
    hex += texto.charCodeAt(i).toString(16).toUpperCase().padStart(4, '0');
  }
  return `<${hex}>`;
}

/** "D:20261024153000Z" — a data de criação, em UTC. */
function dataDePdf(d: Date): string {
  return (
    `D:${d.getUTCFullYear()}${dois(d.getUTCMonth() + 1)}${dois(d.getUTCDate())}` +
    `${dois(d.getUTCHours())}${dois(d.getUTCMinutes())}${dois(d.getUTCSeconds())}Z`
  );
}

export function escreverPdfDeImagem(p: PaginaComImagem): Uint8Array<ArrayBuffer> {
  const conteudo = `q ${num(p.larguraPt)} 0 0 ${num(p.alturaPt)} 0 0 cm /Im0 Do Q\n`;

  // Cada entrada é um objeto INTEIRO, em bytes; o do JPEG é montado à parte.
  const objetos: Uint8Array[] = [
    ASCII.encode('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'),
    ASCII.encode('2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'),
    ASCII.encode(
      `3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${num(p.larguraPt)} ${num(p.alturaPt)}] ` +
        '/Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>\nendobj\n',
    ),
    ASCII.encode(`4 0 obj\n<< /Length ${conteudo.length} >>\nstream\n${conteudo}endstream\nendobj\n`),
    juntar([
      ASCII.encode(
        `5 0 obj\n<< /Type /XObject /Subtype /Image /Width ${p.larguraPx} /Height ${p.alturaPx} ` +
          `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${p.jpeg.length} >>\nstream\n`,
      ),
      p.jpeg,
      ASCII.encode('\nendstream\nendobj\n'),
    ]),
    ASCII.encode(
      `6 0 obj\n<< /Title ${textoDePdf(p.titulo)} /Producer (SAS) /CreationDate (${dataDePdf(p.criadoEm)}) >>\nendobj\n`,
    ),
  ];

  // O comentário binário logo após o cabeçalho avisa programas que leem o arquivo
  // como texto (e-mail, FTP) de que ele tem bytes altos e não pode ser reencodado.
  const cabecalho = juntar([ASCII.encode('%PDF-1.4\n%'), new Uint8Array([0xe2, 0xe3, 0xcf, 0xd3]), ASCII.encode('\n')]);

  const partes: Uint8Array[] = [cabecalho];
  const deslocamentos: number[] = [];
  let posicao = cabecalho.length;
  for (const objeto of objetos) {
    deslocamentos.push(posicao);
    partes.push(objeto);
    posicao += objeto.length;
  }

  let xref = `xref\n0 ${objetos.length + 1}\n0000000000 65535 f \n`;
  for (const d of deslocamentos) xref += `${String(d).padStart(10, '0')} 00000 n \n`;
  xref += `trailer\n<< /Size ${objetos.length + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n${posicao}\n%%EOF\n`;
  partes.push(ASCII.encode(xref));

  return juntar(partes);
}

// `Uint8Array<ArrayBuffer>` e não `Uint8Array`: o TypeScript 7 não aceita como `BlobPart` um
// array que PODE estar sobre um SharedArrayBuffer, e é num `Blob` que este arquivo vai parar.
function juntar(partes: Uint8Array[]): Uint8Array<ArrayBuffer> {
  const saida = new Uint8Array(partes.reduce((soma, p) => soma + p.length, 0));
  let i = 0;
  for (const p of partes) {
    saida.set(p, i);
    i += p.length;
  }
  return saida;
}
