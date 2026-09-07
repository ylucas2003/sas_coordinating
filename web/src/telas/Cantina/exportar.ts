import {
  contagemPorModo, escolhasDaLinha, fraseDaQuebra, marcaDoModo, presencialDoCardapio,
  quebraDaContagem, ROTULO_DA_REFEICAO, rotuloDaContagem, rotuloDoDia,
} from '../../dominio/cantina';
import type { ContagemDeOpcao, PedidoDeAluno, Refeicao } from '../../tipos/cantina';

// Exportação dos pedidos de um dia — CSV e PDF, para a cantina e para a
// coordenação.
//
// ⚠️ **A folha impressa é o documento de trabalho do balcão** (docs/38 §8.2),
// não um anexo: ela vale a mesma régua da tela. Por isso as duas saídas leem o
// vocabulário de `dominio/cantina.ts` em vez de escrever o seu — o total das
// duas portas chamado de "pedidos" no papel é o mesmo chamado de bug que a
// quebra da contagem existe para matar, só que sem ninguém para corrigir de
// viva voz (docs/40 §10.1).
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
// A nota que explica por que duas contagens da mesma folha não batem. Colada na
// tabela de cima, e não solta: é resposta a ela.
const ESTILO_NOTA = 'font-size: 12px; color: #5a5d65; margin: 8px 0 0;';

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

/** Reais para o OLHO (a folha impressa), com separador de milhar — a mesma
    `Intl` que `moeda` usa na tela. O CSV não passa por aqui: lá o consumidor é
    planilha, e ponto de milhar é ruído para quem vai somar a coluna. */
function moeda(valor: number): string {
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

/** `;` como separador e vírgula decimal: é o que o Excel em pt-BR abre sem
    perguntar nada. Aspas duplicadas conforme o RFC. */
function escapar(valor: unknown): string {
  const texto = valor == null ? '' : String(valor);
  return /[";\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
}

export function exportarPedidosCSV(dia: DiaExportavel): void {
  const comRestricao = dia.incluirRestricao ?? false;
  const contagem = contagemPorModo(dia.pedidos);
  const quebra = quebraDaContagem(contagem);

  // A coluna `modo` entra só no dia em que há retirada na hora. É a mesma regra
  // da quebra na tela: acréscimo que aparece sempre vira ruído na planilha de
  // quem nunca ligou a feature — e, no dia em que ele diz algo, é ele que
  // separa quem tem prato de quem só aparece.
  const colunas = ['aluno', 'turma', ...(quebra ? ['modo'] : []), 'escolhas', 'pedido_em'];
  if (comRestricao) colunas.splice(2, 0, 'restricao_alimentar');
  const linhas = [colunas.join(';')];
  for (const pedido of dia.pedidos) {
    const celulas = [
      pedido.nome ?? '',
      pedido.turma ?? '',
      ...(quebra ? [marcaDoModo(pedido)] : []),
      escolhasDaLinha(pedido, ' | '),
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

  // ⚠️ A quebra é bloco PRÓPRIO, e não uma variação do bloco de dinheiro.
  // Ela estava presa a `dia.valor != null` — e `valor_almoco`/`valor_janta`
  // nascem nulos (docs/38 §8.2: "NULL é 'ninguém disse ainda'"), então a
  // cantina recém-cadastrada, que é o caso PADRÃO, recebia uma planilha com 47
  // linhas de aluno sobre uma contagem que soma 44 e nenhuma explicação. O
  // preço de tabela não tem relação nenhuma com a pergunta "por que os dois
  // números não batem".
  if (quebra) {
    linhas.push('', ['refeicoes', 'com_pedido', 'retirada_na_hora'].join(';'));
    linhas.push([dia.pedidos.length, quebra.comPedido, quebra.presenciais].map(escapar).join(';'));
  }

  if (dia.valor != null) {
    // ⚠️ FORMA FIXA, sempre três colunas, com `total` sempre na terceira.
    // Este é o único bloco que existe para ser consolidado: quem empilha os
    // CSVs do mês tem fórmula apontando para uma posição, e um bloco que muda
    // de largura conforme o dia teve ou não retirada na hora devolveria uma
    // contagem de pessoas onde vinha um valor em reais — sem erro, sem aviso.
    // A quebra, que era o motivo de ele mudar de forma, mora no bloco acima.
    //
    // `refeicoes` e não `pedidos`: a coluna conta as duas portas desde a Fase 1
    // (retirada na hora soma no mesmo valor de tabela, docs/40 §14), e o nome
    // antigo afirmava que 47 pessoas pediram quando 3 não pediram nada.
    linhas.push('', ['valor_unitario', 'refeicoes', 'total'].join(';'));
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
  const contagem = contagemPorModo(dia.pedidos);
  const quebra = quebraDaContagem(contagem);
  // O mesmo "há retirada na hora nesta folha?" que decide a nota e a coluna de
  // modo — e, quando há, os dois números que a nota precisa dizer.
  const presencial = presencialDoCardapio(undefined, dia.pedidos);
  const resumo = [
    // "47 pedidos" com 3 retiradas na hora dentro é a folha contradizendo a
    // tabela "O que cozinhar" logo abaixo, que soma 44 — e no papel ninguém
    // pode perguntar. A quebra vem colada no número, como na tela.
    `${dia.pedidos.length} ${rotuloDaContagem(contagem)}`,
    quebra ? fraseDaQuebra(quebra) : null,
    // ⚠️ `Intl` e não `toFixed`, igual à tela (`moeda` em PedidosDoDia): sem o
    // separador de milhar a folha diz "R$ 1800,00" onde a tela diz
    // "R$ 1.800,00", e quem confere uma contra a outra tem de contar dígitos
    // para saber se não é 18000. O CSV logo acima segue sem separador de
    // propósito — lá o consumidor é planilha, não olho.
    total != null ? `total ${moeda(total)}` : null,
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
    // A linha à parte da tela, no papel: sem ela, um dia com doze retiradas na
    // hora imprime uma tabela de cozinhar vazia — ou curta — ao lado de uma
    // lista cheia, e quem lê conclui que a folha veio truncada. Some quando não
    // há ninguém pegando na hora, como na tela.
    ...(presencial
      ? [no(doc, 'p', ESTILO_NOTA,
          `Retirada na hora: ${presencial.retirados} já retiraram`
          + ` · ${presencial.pendentes} com código ainda não lido.`
          + ' Sem prato escolhido — não entram na contagem acima.')]
      : []),
    no(doc, 'h2', ESTILO_SECAO, 'O que servir'),
    tabela(
      doc,
      [
        'Aluno', 'Turma',
        // A coluna de modo só existe no dia em que ela diz algo — e aí ela é o
        // que separa, de longe, quem tem prato de quem chega com o código.
        ...(presencial ? ['Modo'] : []),
        'Escolhas',
        ...(dia.incluirRestricao ? ['Restrição'] : []),
      ],
      dia.pedidos.map((pedido) => {
        const celulas: Array<{ texto: string; estilo?: string }> = [
          { texto: pedido.nome ?? '—' },
          { texto: pedido.turma ?? '—' },
          ...(presencial ? [{ texto: marcaDoModo(pedido) }] : []),
          // Nunca um traço numa linha de retirada na hora: "João Silva · 3ºA ·
          // —" faz quem serve procurar um prato que não existe (docs/40 §10.1).
          { texto: escolhasDaLinha(pedido) || '—' },
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
