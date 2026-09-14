import {
  ESTILO_CORPO, ESTILO_SECAO, ESTILO_SUBTITULO, ESTILO_TITULO, no, regrasDePagina, tabela,
} from './exportar';
import { instrucaoDoBloco, ROTULO_DA_REFEICAO, rotuloDoDia } from '../../dominio/cantina';
import type { AlunoComDireito, BlocoCardapio, CantinaAdmin, CustosDaCantina, LinhaDeCusto, Refeicao } from '../../tipos/cantina';

/**
 * Os geradores do NAVEGADOR para cada tela de cantina (decisão de 14/09).
 *
 * O que sai daqui é o que o navegador faz bem sem biblioteca: CSV, PDF por
 * `window.print` e PNG por canvas. Planilha XLSX sai do servidor
 * (`api/app/cantina_relatorio.py`), porque XLSX não se faz aqui sem ~1 MB.
 *
 * ⚠️ A mesma régua de CSP de `src/exportacao/LEIA-ME.md`: estilo só por CSSOM
 * (`style.cssText`, `insertRule`), nunca `<style>` com texto — a janela aberta
 * herda `style-src 'self'` e o texto seria descartado em silêncio.
 */

// ─── CSV ───────────────────────────────────────────────────────────────

/** Começos que o Excel lê como FÓRMULA — um nome do Canvas com `=` viraria
    célula executável. A mesma guarda de `cantina_relatorio._celula_csv`. */
const INICIO_DE_FORMULA = /^[=+\-@\t\r]/;

function celula(valor: unknown): string {
  if (valor == null) return '';
  let texto = typeof valor === 'number' ? String(valor).replace('.', ',') : String(valor);
  if (INICIO_DE_FORMULA.test(texto)) texto = `'${texto}`;
  return /[;"\n\r]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
}

export function baixarCsv(nome: string, linhas: unknown[][]): void {
  const texto = linhas.map((l) => l.map(celula).join(';')).join('\r\n');
  const url = URL.createObjectURL(new Blob(['\ufeff', texto], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ─── Alunos com direito ────────────────────────────────────────────────

/**
 * ⚠️ **"Tem restrição" é sim ou vazio, nunca o texto** (docs/38 §2.6) — em CSV e
 * em PDF, como na planilha do servidor. A coordenação sabe que existe; revelar
 * o texto é um gesto deliberado na própria tela.
 */
function linhasDeDireitos(alunos: AlunoComDireito[]): string[][] {
  return alunos.map((a) => [
    a.nome, a.matricula ?? '', a.turma ?? '',
    a.direitos.includes('almoco') ? 'sim' : '',
    a.direitos.includes('janta') ? 'sim' : '',
    a.restricaoAlimentar ? 'sim' : '',
  ]);
}

const CABECALHO_DE_DIREITOS = ['Aluno', 'Matrícula', 'Turma', 'Almoço', 'Janta', 'Tem restrição'];

export function csvDeDireitos(alunos: AlunoComDireito[]): void {
  baixarCsv('alunos-com-direito.csv', [CABECALHO_DE_DIREITOS, ...linhasDeDireitos(alunos)]);
}

export function imprimirDireitos(janela: Window, alunos: AlunoComDireito[]): void {
  const doc = prepararDocumento(janela, 'alunos-com-direito');
  const almoco = alunos.filter((a) => a.direitos.includes('almoco')).length;
  const janta = alunos.filter((a) => a.direitos.includes('janta')).length;
  doc.body.append(
    no(doc, 'h1', ESTILO_TITULO, 'Alunos com direito'),
    no(doc, 'p', ESTILO_SUBTITULO,
      `${alunos.length} alunos · ${almoco} almoço · ${janta} janta · gerado em ${new Date().toLocaleString('pt-BR')}`),
    tabela(doc, CABECALHO_DE_DIREITOS, linhasDeDireitos(alunos).map((l) => l.map((texto) => ({ texto })))),
  );
  imprimir(janela);
}

// ─── Administrar cantinas ──────────────────────────────────────────────

/** Uma linha por conta. Sem senha, e não há o que pôr: o hash é de mão única. */
export function csvDeAcesso(cantinas: CantinaAdmin[]): void {
  const linhas: unknown[][] = [[
    'Cantina', 'Ativa', 'Valor almoço', 'Valor janta', 'Conta', 'E-mail', 'Conta ativa',
  ]];
  for (const c of cantinas) {
    const base = [c.nome, c.ativo ? 'sim' : 'não', c.valor_almoco ?? '', c.valor_janta ?? ''];
    if (!c.contas.length) linhas.push([...base, '', '', '']);
    for (const k of c.contas) linhas.push([...base, k.nome, k.email, k.ativo ? 'sim' : 'não']);
  }
  baixarCsv('cantinas-e-contas.csv', linhas);
}

// ─── O cardápio de um dia ──────────────────────────────────────────────

export interface RefeicaoParaImprimir {
  refeicao: Refeicao;
  blocos: BlocoCardapio[];
}

export function imprimirCardapioDoDia(
  janela: Window,
  { data, cantina, refeicoes }: { data: string; cantina: string | null; refeicoes: RefeicaoParaImprimir[] },
): void {
  const doc = prepararDocumento(janela, `cardapio-${data}`);
  doc.body.append(
    no(doc, 'h1', ESTILO_TITULO, `Cardápio · ${rotuloDoDia(data)}`),
    no(doc, 'p', ESTILO_SUBTITULO, [cantina, `gerado em ${new Date().toLocaleString('pt-BR')}`].filter(Boolean).join(' · ')),
  );
  for (const r of refeicoes) {
    doc.body.append(no(doc, 'h2', ESTILO_SECAO, ROTULO_DA_REFEICAO[r.refeicao]));
    const linhas = [...r.blocos]
      .sort((a, b) => a.ordem - b.ordem)
      .map((b) => [
        { texto: b.nome, estilo: 'font-weight: 600;' },
        {
          texto: [...b.opcoes].filter((o) => o.disponivel).sort((a, x) => a.ordem - x.ordem)
            .map((o) => o.nome).join(' · '),
        },
        { texto: instrucaoDoBloco(b) },
      ]);
    doc.body.append(tabela(doc, ['Bloco', 'Opções', 'Regra'], linhas));
  }
  imprimir(janela);
}

// ─── Custos ────────────────────────────────────────────────────────────

function moeda(valor: number): string {
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function imprimirCustos(janela: Window, custos: CustosDaCantina, rotuloDoPeriodo: string): void {
  const doc = prepararDocumento(janela, `custos-${custos.de}-a-${custos.ate}`);
  doc.body.append(
    no(doc, 'h1', ESTILO_TITULO, 'Quanto a cantina custou'),
    no(doc, 'p', ESTILO_SUBTITULO,
      `${rotuloDoPeriodo} · ${moeda(custos.total)} · ${custos.refeicoes} refeições`
      // O buraco vira pergunta também no papel (docs/40 §12.11.2).
      + (custos.semValor ? ` · ${custos.semValor} sem valor registrado, fora da soma` : '')),
  );
  const secoes: Array<[string, string, LinhaDeCusto[]]> = [
    ['Por dia', 'Dia', custos.porDia],
    ['Por turma', 'Turma', custos.porTurma],
    ['Por aluno', 'Aluno', custos.porAluno],
  ];
  if (custos.porCantina.length > 1) secoes.push(['Por cantina', 'Cantina', custos.porCantina]);
  for (const [titulo, coluna, linhas] of secoes) {
    doc.body.append(
      no(doc, 'h2', ESTILO_SECAO, titulo),
      tabela(doc, [coluna, 'Refeições', 'Total'], linhas.map((l) => [
        { texto: l.rotulo }, { texto: String(l.refeicoes) }, { texto: moeda(l.total) },
      ])),
    );
  }
  imprimir(janela);
}

/**
 * O gráfico de custos como imagem — barras horizontais, 1200 de largura.
 *
 * Paleta clara fixa, pelo mesmo motivo da imagem do cardápio: imagem que sai
 * do sistema não tem tema. Sem semáforo: todas as barras no papel de dado, e a
 * diferença que importa é o comprimento.
 */
export async function imagemDoGraficoDeCustos(
  linhas: LinhaDeCusto[], titulo: string, nomeDoArquivo: string,
): Promise<void> {
  const mostradas = linhas.slice(0, 24);
  if (!mostradas.length) throw new Error('Nada neste recorte para desenhar.');
  await document.fonts.ready;
  const familia = getComputedStyle(document.body).fontFamily || 'sans-serif';

  const LARGURA = 1200;
  const MARGEM = 48;
  const LINHA = 44;
  const ALTURA = 130 + mostradas.length * LINHA + 40;
  const canvas = document.createElement('canvas');
  canvas.width = LARGURA;
  canvas.height = ALTURA;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Este navegador não gera imagem.');

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, LARGURA, ALTURA);
  ctx.fillStyle = '#0f1b33';
  ctx.font = `800 34px ${familia}`;
  ctx.fillText(titulo, MARGEM, 70);

  const maior = Math.max(...mostradas.map((l) => l.total), 0.01);
  const COLUNA_ROTULO = 300;
  const COLUNA_VALOR = 150;
  const larguraBarra = LARGURA - MARGEM * 2 - COLUNA_ROTULO - COLUNA_VALOR;
  for (const [i, l] of mostradas.entries()) {
    const y = 120 + i * LINHA;
    ctx.fillStyle = '#5c6883';
    ctx.font = `500 20px ${familia}`;
    let rotulo = l.rotulo;
    while (ctx.measureText(rotulo).width > COLUNA_ROTULO - 16 && rotulo.length > 4) rotulo = `${rotulo.slice(0, -2)}…`;
    ctx.fillText(rotulo, MARGEM, y + 24);
    ctx.fillStyle = '#eaf0fa';
    ctx.fillRect(MARGEM + COLUNA_ROTULO, y + 8, larguraBarra, 22);
    ctx.fillStyle = '#2e6be6';
    ctx.fillRect(MARGEM + COLUNA_ROTULO, y + 8, Math.max(2, (l.total / maior) * larguraBarra), 22);
    ctx.fillStyle = '#16233d';
    ctx.font = `600 20px ${familia}`;
    ctx.fillText(moeda(l.total), MARGEM + COLUNA_ROTULO + larguraBarra + 12, y + 26);
  }

  const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, 'image/png'));
  if (!blob) throw new Error('Não deu para gerar a imagem.');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nomeDoArquivo;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ─── Peças comuns ──────────────────────────────────────────────────────

function prepararDocumento(janela: Window, titulo: string): Document {
  const doc = janela.document;
  doc.title = titulo;
  doc.documentElement.lang = 'pt-BR';
  regrasDePagina(doc);
  doc.body.style.cssText = ESTILO_CORPO;
  return doc;
}

function imprimir(janela: Window): void {
  janela.focus();
  janela.print();
}
