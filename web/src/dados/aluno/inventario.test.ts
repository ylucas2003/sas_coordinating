// O inventário do docs/30 tem de estar em dia com o registro.
//
// Este arquivo faz DUAS coisas, e faz de propósito:
//
//   npm test          confere que o miolo gerado do docs/30 é exatamente o que
//                     o `registro.ts` produz hoje. Se alguém ligar uma fonte e
//                     esquecer de regerar, o teste avisa — em vez de o próximo a
//                     mexer descobrir sozinho que a tabela mente.
//   npm run inventario  ESCREVE o miolo (a variável GERAR_INVENTARIO liga).
//
// ⚠️ Sim, é um teste que escreve arquivo quando pedido, e isso normalmente é
// cheiro. Aqui é a opção mais barata que existe: o Vitest é a única coisa no
// projeto que resolve import de TypeScript sem extensão, e usá-lo evita uma
// dependência nova (`tsx`/`vite-node`) e evita afrouxar o tsconfig do projeto
// inteiro com `allowImportingTsExtensions` só por causa de um script. E, como o
// escritor e o conferidor são o MESMO caminho de código, é impossível os dois
// divergirem.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { MARCA_FIM, MARCA_INICIO, aplicarNoDocumento, gerarInventario } from './inventario';

const DOC = join(
  dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  '..',
  '..',
  'docs',
  '30-estado-da-implementacao.md',
);

const GERANDO = process.env.GERAR_INVENTARIO === '1';

describe('docs/30-estado-da-implementacao.md', () => {
  it('tem as marcas do bloco gerado', () => {
    const documento = readFileSync(DOC, 'utf8');
    expect(documento).toContain(MARCA_INICIO);
    expect(documento).toContain(MARCA_FIM);
  });

  it('está em sincronia com o registro (rode `npm run inventario` se falhar)', () => {
    const documento = readFileSync(DOC, 'utf8');
    const inventario = gerarInventario();

    if (GERANDO) {
      writeFileSync(DOC, aplicarNoDocumento(documento, inventario), 'utf8');
      return;
    }

    const i = documento.indexOf(MARCA_INICIO);
    const f = documento.indexOf(MARCA_FIM) + MARCA_FIM.length;
    expect(documento.slice(i, f)).toBe(inventario);
  });

  it('mantém a prosa fora do bloco gerado', () => {
    // O documento não é só as tabelas: ele fecha com "o que fazer a seguir",
    // que sai das tabelas 2 e 3 mas é escrito por gente. Se essa seção sumir, o
    // inventário deixou de ser um plano e virou um relatório.
    expect(readFileSync(DOC, 'utf8').toLowerCase()).toContain('o que fazer a seguir');
  });
});
