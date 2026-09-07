import { ROTULO_DA_REFEICAO, rotuloDoDia } from '../../dominio/cantina';
import type { ContagemDeOpcao, PedidoDeAluno, Refeicao } from '../../tipos/cantina';

// Exportação dos pedidos de um dia — CSV e PDF, para a cantina e para a
// coordenação.
//
// ⚠️ **Estilo NUNCA por `<style>` com conteúdo nem por atributo `style` no
// HTML.** A CSP de produção é `style-src 'self'`, sem `unsafe-inline`, e a
// janela aberta por `window.open('')` herda a CSP de quem a abriu: o estilo
// inline seria descartado **em silêncio**, e o PDF sairia sem cor e sem margem
// sem nenhum erro no console. Aplique por CSSOM — `element.style.cssText` e
// `sheet.insertRule` —, que é o que `telas/Banco/exportar.ts` já faz e o
// `src/exportacao/LEIA-ME.md` documenta.
//
// Duas saídas porque são dois usos: o CSV vai para a planilha de quem fecha a
// conta do mês; o PDF é a folha que desce impressa para o balcão.

const ESTILO_CORPO =
  'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;'
  + 'color: #1a1d24; line-height: 1.5; margin: 0; padding: 24px; max-width: 820px;';
const ESTILO_TITULO = 'font-size: 22px; font-weight: 600; margin: 0 0 4px;';
const ESTILO_SUBTITULO = 'font-size: 12px; color: #5a5d65; margin: 0 0 22px;';
const ESTILO_SECAO = 'font-size: 15px; font-weight: 600; margin: 22px 0 8px;';
const ESTILO_TABELA =
  'width: 100%; border-collapse: collapse; font-size: 12px; break-inside: auto;';
const ESTILO_TH =
  'text-align: left; padding: 6px 8px; border-bottom: 2px solid #1a1d24; font-weight: 600;';
const ESTILO_TD = 'padding: 6px 8px; border-bottom: 1px solid #e0e3eb; vertical-align: top;';
// `break-inside: avoid` para a linha do aluno não rachar entre duas páginas.
const ESTILO_TR = 'break-inside: avoid;';
const ESTILO_RESTRICAO = 'color: #8a5a00; font-weight: 600;';

export interface DiaExportavel {
  data: string;
  refeicao: Refeicao;
  cantina?: string | null;
  pedidos: PedidoDeAluno[];
  contagem: ContagemDeOpcao[];
  /** Preço de tabela da refeição, quando a coordenação informou. */
  valor?: number | null;
  /**
   * Leva o TEXTO da restrição alimentar.
   *
   * ⚠️ Verdadeiro só para a CANTINA, que precisa dele para montar o prato.
   * A coordenação vê apenas a marca "tem restrição alimentar" na tela, com a
   * revelação do texto deliberada noutra superfície — e um CSV que o levasse
   * contornaria essa decisão pelo caminho mais fácil. É dado de saúde de menor
   * (docs/38 §2.6).
   */
  incluirRestricao?: boolean;
}

function titulo(dia: DiaExportavel): string {
  const base = `${ROTULO_DA_REFEICAO[dia.refeicao]} · ${rotuloDoDia(dia.data)}`;
  return dia.cantina ? `${base} · ${dia.cantina}` : base;
}

function nomeDeArquivo(dia: DiaExportavel, extensao: string): string {
  return `pedidos-${dia.data}-${dia.refeicao}.${extensao}`;
}

/** `;` como separador e vírgula decimal: é o que o Excel em pt-BR abre sem
    perguntar nada. Aspas duplicadas conforme o RFC. */
function escapar(valor: unknown): string {
  const texto = valor == null ? '' : String(valor);
  return /[";\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
}

export function exportarPedidosCSV(dia: DiaExportavel): void {
  const comRestricao = dia.incluirRestricao ?? false;
  const colunas = ['aluno', 'turma', 'escolhas', 'pedido_em'];
  if (comRestricao) colunas.splice(2, 0, 'restricao_alimentar');
  const linhas = [colunas.join(';')];
  for (const pedido of dia.pedidos) {
    const celulas = [
      pedido.nome ?? '',
      pedido.turma ?? '',
      pedido.escolhas.join(' | '),
      pedido.pedidoEm ? new Date(pedido.pedidoEm).toLocaleString('pt-BR') : '',
    ];
    if (comRestricao) celulas.splice(2, 0, pedido.restricaoAlimentar ?? '');
    linhas.push(celulas.map(escapar).join(';'));
  }

  // A contagem entra no MESMO arquivo, depois de uma linha em branco: quem
  // fecha a conta do mês quer as duas coisas, e dois downloads para um dia só
  // é atrito sem ganho.
  linhas.push('', ['bloco', 'opcao', 'quantos'].join(';'));
  for (const linha of dia.contagem) {
    linhas.push([linha.bloco, linha.opcao, linha.quantos].map(escapar).join(';'));
  }

  if (dia.valor != null) {
    linhas.push('', ['valor_unitario', 'pedidos', 'total'].join(';'));
    const total = dia.valor * dia.pedidos.length;
    linhas.push([
      dia.valor.toFixed(2).replace('.', ','),
      dia.pedidos.length,
      total.toFixed(2).replace('.', ','),
    ].map(escapar).join(';'));
  }

  // BOM para o Excel reconhecer UTF-8 — sem ele, todo "ç" vira sujeira.
  const blob = new Blob(['﻿', linhas.join('\n')], { type: 'text/csv;charset=utf-8' });
  baixar(blob, nomeDeArquivo(dia, 'csv'));
}

function baixar(blob: Blob, nome: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = nome;
  link.click();
  // Revogar na hora corta o download em alguns navegadores; um tick basta.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function no(doc: Document, tag: string, estilo: string, texto?: string): HTMLElement {
  const elemento = doc.createElement(tag);
  if (estilo) elemento.style.cssText = estilo;
  if (texto != null) elemento.textContent = texto;
  return elemento;
}

/** `@page` só existe em folha de estilo — não há atributo equivalente. */
function regrasDePagina(doc: Document): void {
  const folha = doc.createElement('style');
  doc.head.appendChild(folha);
  try {
    folha.sheet?.insertRule('@page { size: A4; margin: 16mm; }', 0);
  } catch {
    // Navegador que recuse a regra imprime com a margem padrão — perde-se o
    // A4 exato, não o documento.
  }
}

function tabela(
  doc: Document,
  cabecalho: string[],
  linhas: Array<Array<{ texto: string; estilo?: string }>>,
): HTMLElement {
  const tab = no(doc, 'table', ESTILO_TABELA);
  const thead = doc.createElement('thead');
  const trCabeca = doc.createElement('tr');
  for (const titulo of cabecalho) trCabeca.appendChild(no(doc, 'th', ESTILO_TH, titulo));
  thead.appendChild(trCabeca);
  tab.appendChild(thead);

  const tbody = doc.createElement('tbody');
  for (const linha of linhas) {
    const tr = no(doc, 'tr', ESTILO_TR);
    for (const celula of linha) {
      tr.appendChild(no(doc, 'td', `${ESTILO_TD}${celula.estilo ?? ''}`, celula.texto));
    }
    tbody.appendChild(tr);
  }
  tab.appendChild(tbody);
  return tab;
}

export function exportarPedidosPDF(dia: DiaExportavel): void {
  const janela = window.open('', '_blank');
  if (!janela) {
    throw new Error(
      'O navegador bloqueou a janela de impressão. Permita pop-ups para este site e tente de novo.',
    );
  }

  const doc = janela.document;
  doc.title = nomeDeArquivo(dia, 'pdf');
  doc.documentElement.lang = 'pt-BR';
  regrasDePagina(doc);
  doc.body.style.cssText = ESTILO_CORPO;

  const total = dia.valor != null ? dia.valor * dia.pedidos.length : null;
  const resumo = [
    `${dia.pedidos.length} ${dia.pedidos.length === 1 ? 'pedido' : 'pedidos'}`,
    total != null ? `total R$ ${total.toFixed(2).replace('.', ',')}` : null,
    `gerado em ${new Date().toLocaleString('pt-BR')}`,
  ].filter(Boolean).join(' · ');

  doc.body.append(
    no(doc, 'h1', ESTILO_TITULO, titulo(dia)),
    no(doc, 'p', ESTILO_SUBTITULO, resumo),
    // A CONTAGEM vem primeiro: é o que se lê de manhã, com a mão na panela. A
    // lista por aluno é do balcão, ao meio-dia.
    no(doc, 'h2', ESTILO_SECAO, 'O que cozinhar'),
    tabela(
      doc,
      ['Bloco', 'Opção', 'Quantos'],
      dia.contagem.map((linha) => [
        { texto: linha.bloco },
        { texto: linha.opcao + (linha.disponivel ? '' : ' (acabou)') },
        { texto: String(linha.quantos) },
      ]),
    ),
    no(doc, 'h2', ESTILO_SECAO, 'O que servir'),
    tabela(
      doc,
      dia.incluirRestricao
        ? ['Aluno', 'Turma', 'Escolhas', 'Restrição']
        : ['Aluno', 'Turma', 'Escolhas'],
      dia.pedidos.map((pedido) => {
        const celulas: Array<{ texto: string; estilo?: string }> = [
          { texto: pedido.nome ?? '—' },
          { texto: pedido.turma ?? '—' },
          { texto: pedido.escolhas.join(' · ') || '—' },
        ];
        // A restrição em destaque, e não numa coluna qualquer: é a informação
        // que muda o que sai do balcão — e por isso só vai na folha de quem
        // monta o prato.
        if (dia.incluirRestricao) {
          celulas.push({ texto: pedido.restricaoAlimentar ?? '', estilo: ESTILO_RESTRICAO });
        }
        return celulas;
      }),
    ),
  );

  // Sem imagem nem fonte externa, então não há o que esperar carregar — ao
  // contrário do exportador do Banco, que aguarda o `load` de cada figura.
  janela.focus();
  janela.print();
}
