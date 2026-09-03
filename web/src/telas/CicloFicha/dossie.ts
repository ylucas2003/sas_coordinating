import { fmtNota } from '../../util/formato';
import type { Ciclo, EstatisticasCiclo, RecorteMateria, Simulado } from '../../tipos/dominio';

// O dossiê de ciclo — texto, gráfico e tabela num documento que se salva e se
// leva para a reunião (docs/33 §5).
//
// **A casa dele é a ficha, não o chat.** O que o pedido descreve — "produção de
// conteúdo denso para a coordenação" — a `CicloFicha` já desenha inteiro: KPIs,
// evolução, a leitura do LLM em linguagem acessível (cacheada em
// `insight_ciclo`), histogramas por matéria e a tabela de simulados. Faltava
// tirar isso da tela em papel. O coordenador já está aqui quando quer o
// documento, e nada disto precisa de LLM na hora: os insights vêm prontos de
// `GET /ciclos/{id}/estatisticas?com_insights=true`.
//
// ⚠️ **O estilo vai por CSSOM, nunca por atributo `style` nem por `<style>` com
// conteúdo.** A CSP de produção é `style-src 'self'`, sem 'unsafe-inline'
// (infra/vps/nginx.conf), e a janela aberta por `window.open('')` herda a CSP
// de quem a abriu. Atributo inline seria descartado **em silêncio** — o PDF
// sairia sem cor e sem margem, e ninguém veria erro no console. Já mordeu duas
// vezes: o gerador da ficha do aluno (docs/16 §Bugs) e o da lista de questões
// (docs/22 §8, risco 7). **Testar em produção, não só no dev**, onde a CSP é
// mais frouxa.
//
// ⚠️ **O gráfico entra rasterizado, e é por isso que ele entra.** Nenhum dos
// dois motores de exportação do projeto sabia levar SVG. O caminho é serializar
// o `<svg>` que já está na árvore, desenhar num canvas e embutir como `data:`
// URI — que a CSP **permite** (`img-src 'self' data: blob:`). No `.doc` isso
// tem um ganho extra: o arquivo não precisa de rede para mostrar o gráfico,
// diferente das imagens do S3 da lista de questões.

const ESTILO_CORPO =
  'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;' +
  'color: #1a1d24; line-height: 1.5; margin: 0; padding: 24px; max-width: 820px;';
const ESTILO_TITULO = 'font-size: 24px; font-weight: 600; margin: 0 0 4px;';
const ESTILO_SUBTITULO = 'font-size: 12px; color: #5a5d65; margin: 0 0 24px;';
const ESTILO_SECAO = 'font-size: 16px; font-weight: 600; margin: 26px 0 10px; break-after: avoid;';
const ESTILO_LISTA = 'font-size: 13px; margin: 0 0 12px; padding-left: 20px;';
const ESTILO_ITEM = 'margin: 0 0 4px;';
const ESTILO_TABELA =
  'width: 100%; border-collapse: collapse; font-size: 12px; margin: 0 0 16px;' +
  'break-inside: avoid;';
const ESTILO_TH =
  'text-align: left; padding: 6px 8px; border-bottom: 2px solid #1b3f8b; font-weight: 600;';
const ESTILO_TD = 'padding: 6px 8px; border-bottom: 1px solid #e0e3eb;';
const ESTILO_KPIS = 'display: flex; gap: 28px; flex-wrap: wrap; margin: 0 0 18px;';
const ESTILO_KPI_VALOR = 'font-size: 22px; font-weight: 600; margin: 0;';
const ESTILO_KPI_ROTULO = 'font-size: 11px; color: #5a5d65; margin: 0;';
const ESTILO_IMAGEM = 'max-width: 100%; height: auto; display: block; margin: 0 0 16px;';
const ESTILO_RODAPE = 'font-size: 11px; color: #73757d; margin: 28px 0 0;';

/** Cria um nó já estilizado por CSSOM. `texto` vai como texto, nunca como HTML. */
function no(doc: Document, tag: string, estilo: string, texto?: string): HTMLElement {
  const elemento = doc.createElement(tag);
  if (estilo) elemento.style.cssText = estilo;
  if (texto != null) elemento.textContent = texto;
  return elemento;
}

function pct(v: number | null | undefined): string {
  return v == null ? '—' : `${v.toFixed(1).replace('.', ',')}%`;
}

/**
 * SVG da tela → PNG em `data:` URI.
 *
 * Devolve `null` em vez de estourar: um gráfico que não rasterizou não pode
 * impedir o documento de sair. Sem `await` de rede — o SVG dos gráficos do SAS
 * é desenhado em coordenadas, sem imagem externa.
 */
async function svgParaImagem(svg: SVGSVGElement | null): Promise<string | null> {
  if (!svg) return null;
  try {
    const largura = svg.clientWidth || svg.viewBox.baseVal.width || 640;
    const altura = svg.clientHeight || svg.viewBox.baseVal.height || 240;

    const clone = svg.cloneNode(true) as SVGSVGElement;
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', String(largura));
    clone.setAttribute('height', String(altura));
    // Fundo branco explícito: o gráfico na tela herda o fundo do cartão, e no
    // papel ele sairia sobre transparência (= preto, em alguns leitores).
    const fundo = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    fundo.setAttribute('width', '100%');
    fundo.setAttribute('height', '100%');
    fundo.setAttribute('fill', '#ffffff');
    clone.insertBefore(fundo, clone.firstChild);

    const textoSvg = new XMLSerializer().serializeToString(clone);
    const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(textoSvg)}`;

    const imagem = new Image();
    await new Promise<void>((resolve, reject) => {
      imagem.onload = () => resolve();
      imagem.onerror = () => reject(new Error('svg não carregou'));
      imagem.src = url;
    });

    // 2× para o gráfico não sair borrado no PDF.
    const canvas = document.createElement('canvas');
    canvas.width = largura * 2;
    canvas.height = altura * 2;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(imagem, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/png');
  } catch {
    return null;
  }
}

export interface DadosDossie {
  ciclo: Ciclo;
  stats: EstatisticasCiclo;
  simulados: readonly Simulado[];
  nomeCriterio: string | null;
  /** Os `<svg>` que estão na tela, na ordem em que devem entrar no documento. */
  graficos: Array<{ titulo: string; svg: SVGSVGElement | null }>;
}

/** Monta o corpo do dossiê num documento qualquer (a janela nova, ou o atual). */
async function montarCorpo(doc: Document, dados: DadosDossie): Promise<HTMLElement[]> {
  const { ciclo, stats, simulados, nomeCriterio } = dados;
  const nos: HTMLElement[] = [];

  nos.push(no(doc, 'h1', ESTILO_TITULO, `Dossiê — ${ciclo.nome}`));
  nos.push(
    no(
      doc,
      'p',
      ESTILO_SUBTITULO,
      `${ciclo.periodoInicio || '—'} a ${ciclo.periodoFim || '—'} · ${simulados.length} simulados`
        + `${nomeCriterio ? ` · régua: ${nomeCriterio}` : ''}`
        + ` · gerado em ${new Date().toLocaleDateString('pt-BR')}`,
    ),
  );

  // ── Os números do topo ──
  const resumo = stats.resumo ?? {};
  const kpis = no(doc, 'div', ESTILO_KPIS);
  for (const [rotulo, valor] of [
    ['Média do ciclo', resumo.media == null ? '—' : fmtNota(resumo.media)],
    ['Acima do corte', pct(resumo.pctAprovados)],
    ['Zona crítica', pct(resumo.pctZonaCritica)],
    ['Excelência', pct(resumo.pctExcelencia)],
  ] as Array<[string, string]>) {
    const bloco = no(doc, 'div', '');
    bloco.appendChild(no(doc, 'p', ESTILO_KPI_VALOR, valor));
    bloco.appendChild(no(doc, 'p', ESTILO_KPI_ROTULO, rotulo));
    kpis.appendChild(bloco);
  }
  nos.push(kpis);

  // ── A leitura, em linguagem de gente ──
  //
  // É o texto que o §4.4 do docs/25 pedia, e ele já existe: `insights.pratico`
  // vem cacheado por hash do payload, então o dossiê não paga LLM nenhum.
  const leitura = stats.conjunta?.insights?.pratico ?? [];
  if (leitura.length > 0) {
    nos.push(no(doc, 'h2', ESTILO_SECAO, 'Leitura do ciclo'));
    const lista = no(doc, 'ul', ESTILO_LISTA);
    for (const bullet of leitura) lista.appendChild(no(doc, 'li', ESTILO_ITEM, bullet));
    nos.push(lista);
  }

  // ── Os gráficos ──
  for (const { titulo, svg } of dados.graficos) {
    const imagem = await svgParaImagem(svg);
    if (!imagem) continue;
    nos.push(no(doc, 'h2', ESTILO_SECAO, titulo));
    const img = no(doc, 'img', ESTILO_IMAGEM) as HTMLImageElement;
    img.src = imagem;
    img.alt = titulo;
    nos.push(img);
  }

  // ── A tabela por matéria ──
  const porMateria = (stats.porMateria ?? []).filter(Boolean) as RecorteMateria[];
  if (porMateria.length > 0) {
    nos.push(no(doc, 'h2', ESTILO_SECAO, 'Por matéria'));
    nos.push(
      tabela(
        doc,
        ['Matéria', 'Corte', 'Média F1', 'Acima do corte F1', 'Média F2', 'Acima do corte F2'],
        porMateria.map((m) => [
          m.materia.nome + (m.eliminatoria ? ' (eliminatória)' : ''),
          m.corte == null ? '—' : fmtNota(m.corte),
          m.fase1?.stats.media == null ? '—' : fmtNota(m.fase1.stats.media),
          pct(m.fase1?.stats.pctAprovados),
          m.fase2?.stats.media == null ? '—' : fmtNota(m.fase2.stats.media),
          pct(m.fase2?.stats.pctAprovados),
        ]),
      ),
    );
  }

  // ── A tabela de simulados ──
  if (simulados.length > 0) {
    nos.push(no(doc, 'h2', ESTILO_SECAO, 'Simulados do ciclo'));
    nos.push(
      tabela(
        doc,
        ['Prova', 'Matéria', 'Data', 'Média', 'Presentes'],
        simulados.map((s) => [
          s.rotuloCurto || s.nome,
          s.materia?.nome ?? '—',
          s.dataAplicacao || '—',
          s.media == null ? '—' : fmtNota(s.media),
          s.nPresentes == null ? '—' : String(s.nPresentes),
        ]),
      ),
    );
  }

  nos.push(
    no(
      doc,
      'p',
      ESTILO_RODAPE,
      'Gerado pelo SAS — Colégio Ari de Sá. Os percentuais seguem a régua de corte indicada no '
        + 'topo; trocar a régua muda os números.',
    ),
  );
  return nos;
}

function tabela(doc: Document, cabecalho: string[], linhas: string[][]): HTMLElement {
  const t = no(doc, 'table', ESTILO_TABELA);
  const thead = doc.createElement('thead');
  const trCab = doc.createElement('tr');
  for (const c of cabecalho) trCab.appendChild(no(doc, 'th', ESTILO_TH, c));
  thead.appendChild(trCab);
  t.appendChild(thead);

  const tbody = doc.createElement('tbody');
  for (const linha of linhas) {
    const tr = doc.createElement('tr');
    for (const celula of linha) tr.appendChild(no(doc, 'td', ESTILO_TD, celula));
    tbody.appendChild(tr);
  }
  t.appendChild(tbody);
  return t;
}

/** `@page` só existe em folha de estilo — não há atributo equivalente. */
function aplicarRegrasDePagina(doc: Document): void {
  const folha = doc.createElement('style');
  doc.head.appendChild(folha);
  try {
    folha.sheet?.insertRule('@page { size: A4; margin: 16mm; }', 0);
  } catch {
    // Navegador que recuse a regra imprime com a margem padrão — perde-se o
    // A4 exato, não o documento.
  }
}

/**
 * PDF pela impressão do navegador, como o resto do projeto faz. Lança em vez
 * de devolver `false` para a tela poder dizer o que houve — pop-up bloqueado é
 * a causa mais comum e tem conserto do lado do usuário.
 */
export async function exportarDossiePdf(dados: DadosDossie): Promise<void> {
  const janela = window.open('', '_blank');
  if (!janela) {
    throw new Error(
      'O navegador bloqueou a janela de impressão. Permita pop-ups para este site e tente de novo.',
    );
  }

  const doc = janela.document;
  doc.title = `Dossiê — ${dados.ciclo.nome}`;
  doc.documentElement.lang = 'pt-BR';
  aplicarRegrasDePagina(doc);
  doc.body.style.cssText = ESTILO_CORPO;
  doc.body.replaceChildren(...(await montarCorpo(doc, dados)));

  // As imagens são `data:` URI — já estão prontas, sem rede. O tique é só para
  // o layout assentar antes do diálogo de impressão.
  janela.setTimeout(() => {
    try {
      janela.focus();
      janela.print();
    } catch {
      // Janela fechada pelo usuário antes da hora — não é erro do app.
    }
  }, 250);
}

/**
 * Word, sem dependência nenhuma — o mesmo envelope de `telas/Banco/exportar.ts`.
 *
 * ⚠️ Sai `.doc` (HTML que o Word abre e edita), não `.docx` (OOXML zipado). O
 * botão diz "Word" para o rótulo não prometer o que não entrega.
 *
 * Aqui o `style` inline é obrigatório e seguro: o arquivo sai do navegador, a
 * CSP não o alcança, e é o que o Word entende.
 */
export async function exportarDossieWord(dados: DadosDossie): Promise<void> {
  const corpo = document.createElement('div');
  corpo.append(...(await montarCorpo(document, dados)));

  const html =
    '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
    + 'xmlns:w="urn:schemas-microsoft-com:office:word" '
    + 'xmlns="http://www.w3.org/TR/REC-html40">'
    + '<head><meta charset="utf-8"></head>'
    + `<body style="${ESTILO_CORPO}">${corpo.innerHTML}</body></html>`;

  const blob = new Blob(['﻿', html], { type: 'application/msword' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `dossie-${dados.ciclo.nome.replace(/[^a-zA-Z0-9]+/g, '-').toLowerCase()}.doc`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
