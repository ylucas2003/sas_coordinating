// As três tabelas de `docs/30-estado-da-implementacao.md`, geradas a partir do
// `registro.ts`.
//
// Função pura, sem I/O: quem escreve o arquivo e quem confere que ele está em
// dia é o mesmo `inventario.test.ts` (`npm run inventario` escreve, `npm test`
// confere). Manter a geração aqui, sem tocar em disco, é o que permite testá-la.
//
// O documento é gerado, e não escrito à mão, por um motivo operacional: um
// inventário mantido à mão envelhece em silêncio, e um inventário que esconde
// buraco é pior que nenhum — o próximo a mexer confia nele. Aqui, ligar uma
// fonte é trocar uma linha do registro; ou o documento acompanha, ou o teste
// quebra.

import { FONTES } from './registro';
import type { Fonte } from './registro';

export const MARCA_INICIO = '<!-- INVENTARIO:INICIO -->';
export const MARCA_FIM = '<!-- INVENTARIO:FIM -->';

/** Célula de tabela Markdown: `|` escapa e quebra de linha vira espaço. */
function celula(texto: string | undefined): string {
  return (texto ?? '—').replace(/\|/g, '\\|').replace(/\s*\n\s*/g, ' ').trim();
}

const PESO: Record<string, number> = { P: 0, M: 1, G: 2 };

/**
 * Ordena por esforço crescente, e é a única ordenação que este arquivo impõe.
 * A tabela 2 é uma LISTA DE TAREFAS, não um relatório: a linha mais barata tem
 * de estar em cima. Empate desempata pela chave, para a ordem não dançar entre
 * gerações e sujar o diff do documento.
 */
function porEsforco(a: Fonte, b: Fonte): number {
  return (
    (PESO[a.esforco ?? 'G'] ?? 3) - (PESO[b.esforco ?? 'G'] ?? 3) ||
    a.chave.localeCompare(b.chave, 'pt-BR')
  );
}

function notas(fontes: Fonte[]): string {
  const comNota = fontes.filter((f) => f.observacao);
  if (!comNota.length) return '';
  return `\n${comNota.map((f) => `- **\`${f.chave}\`** — ${celula(f.observacao)}`).join('\n')}\n`;
}

function tabela(cabecalho: string[], linhas: string[][]): string {
  return [
    `| ${cabecalho.join(' | ')} |`,
    `|${cabecalho.map(() => '---').join('|')}|`,
    ...linhas.map((l) => `| ${l.join(' | ')} |`),
  ].join('\n');
}

export function gerarInventario(): string {
  const reais = FONTES.filter((f) => f.estado === 'real');
  const semRota = FONTES.filter((f) => f.estado === 'sem-rota').sort(porEsforco);
  const mocks = FONTES.filter((f) => f.estado === 'mock').sort(porEsforco);

  const t1 = tabela(
    ['Fonte', 'O que é', 'Rota que alimenta', 'Em que telas aparece'],
    reais.map((f) => [
      `\`${f.chave}\``,
      celula(f.descricao),
      `\`${celula(f.rotaFutura)}\``,
      celula(f.telas.join(', ')),
    ]),
  );

  const t2 = tabela(
    ['Esforço', 'Fonte', 'O que é', 'Onde o dado JÁ está no servidor', 'Rota que a desmockaria', 'Telas'],
    semRota.map((f) => [
      f.esforco ?? '?',
      `\`${f.chave}\``,
      celula(f.descricao),
      celula(f.origemDoDado),
      `\`${celula(f.rotaFutura)}\``,
      celula(f.telas.join(', ')),
    ]),
  );

  const t3 = tabela(
    ['Esforço', 'Fonte', 'O que é', 'Especificada em', 'Depende de', 'Telas'],
    mocks.map((f) => [
      f.esforco ?? '?',
      `\`${f.chave}\``,
      celula(f.descricao),
      celula(f.doc),
      celula(f.depende),
      celula(f.telas.join(', ')),
    ]),
  );

  return `${MARCA_INICIO}
<!-- Gerado por web/src/dados/aluno/inventario.ts a partir de
     web/src/dados/aluno/registro.ts. NÃO EDITE ENTRE AS MARCAS À MÃO:
     \`npm test\` falha se esta seção divergir do registro. Para mudar,
     mude o registro e rode \`npm run inventario\` dentro de web/. -->

## 1 · LIGADO — ${reais.length} fontes

O endpoint existe e a tela consome de verdade. Nada aqui é mock.
${notas(reais)}
${t1}

## 2 · DADO EXISTE, ROTA NÃO — ${semRota.length} fontes

O servidor já sabe a resposta; só não há rota que a devolva. **Ordenada por
esforço crescente, porque esta tabela é a lista de tarefas mais barata do
projeto**: desmockar qualquer linha daqui é escrever uma rota curta sobre dado
que já está no Postgres, não inventar produto.

${t2}
${notas(semRota)}
## 3 · MOCK PURO — ${mocks.length} fontes

Não existe nem dado. Desmockar é decisão de produto, migration, ou as duas.

${t3}
${notas(mocks)}
${MARCA_FIM}`;
}

/** Troca o miolo entre as marcas, preservando a prosa em volta. */
export function aplicarNoDocumento(documento: string, inventario: string): string {
  const i = documento.indexOf(MARCA_INICIO);
  const f = documento.indexOf(MARCA_FIM);
  if (i === -1 || f === -1 || f < i) {
    throw new Error(
      `docs/30 precisa conter ${MARCA_INICIO} e ${MARCA_FIM}, nesta ordem — o gerador só troca o miolo.`,
    );
  }
  return documento.slice(0, i) + inventario + documento.slice(f + MARCA_FIM.length);
}
