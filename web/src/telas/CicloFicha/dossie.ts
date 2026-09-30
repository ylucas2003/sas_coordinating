import logoBranca from '../../../assets/ari-logo-branca.png';
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
// ⚠️ **O gráfico entra rasterizado, e o SVG PRECISA LEVAR O ESTILO CONSIGO.**
// Nenhum dos dois motores de exportação sabia levar SVG: o PDF sai da janela de
// impressão e o `.doc` é HTML do Word. O caminho é serializar o `<svg>` que já
// está na árvore, desenhar num canvas e embutir como `data:` URI — que a CSP
// **permite** (`img-src 'self' data: blob:`).
//
// O que quebrou o dossiê inteiro na primeira versão: o SVG serializado, solto,
// vira um documento à parte SEM a folha de estilo do site. Os gráficos pintam
// com `var(--sas-*)` e `color-mix(...)`; fora da página as variáveis não
// existem, o preenchimento cai no padrão do SVG (PRETO) e o contorno some — e
// como a barra ABAIXO do corte é só contorno (R3, "vazado"), metade do
// histograma desaparecia. Por isso `inlinarEstilos` copia o estilo COMPUTADO
// (já sem `var()`) para cada nó antes de serializar, e `fonteEmbutida` leva a
// Plus Jakarta Sans junto, em base64: um SVG-imagem não carrega a fonte da
// página.
//
// ⚠️ **Papel é tema dia.** A fonte dos gráficos (`.ciclo-dossie-fonte`) força a
// paleta do dia em CSS (layout.css), senão quem exportava com o tema escuro
// ligado recebia tinta clara sobre papel branco.
//
// ⚠️ **O `.doc` não sabe `flex` nem `grid`.** O Word é um motor de HTML de 2003:
// tudo que é lado a lado aqui é `<table>`. Foi isso que deixou o `.doc` da
// primeira versão com os KPIs empilhados e sem forma.

// ─── Paleta ──────────────────────────────────────────────────────────────

/** Os papéis do design system que o documento usa (papeis.css, bloco do dia). */
interface Paleta {
  acao: string;
  acaoBase: string;
  valor: string;
  valorTexto: string;
  magnitude: string;
  texto: string;
  texto2: string;
  referencia: string;
  borda: string;
  superficie: string;
  superficie2: string;
}

/** O bloco de dia de papeis.css, para o caso de a fonte dos gráficos não existir. */
const PALETA_DO_DIA: Paleta = {
  acao: '#1b3f8b',
  acaoBase: '#12275a',
  valor: '#f2c94c',
  valorTexto: '#b07d12',
  magnitude: '#0f1b33',
  texto: '#16233d',
  texto2: '#5c6883',
  referencia: '#8a93a8',
  borda: '#dce6f7',
  superficie: '#f4f7fc',
  superficie2: '#eaf0fa',
};

const TOKENS: Record<keyof Paleta, string> = {
  acao: '--sas-acao',
  acaoBase: '--sas-acao-base',
  valor: '--sas-valor',
  valorTexto: '--sas-valor-texto',
  magnitude: '--sas-magnitude',
  texto: '--sas-texto',
  texto2: '--sas-texto-2',
  referencia: '--sas-referencia',
  borda: '--sas-borda',
  superficie: '--sas-superficie',
  superficie2: '--sas-superficie-2',
};

/**
 * Lê a paleta no lugar onde ela vale (a fonte dos gráficos, que é tema dia) em
 * vez de repetir os hexadecimais aqui: quando o design system mudar um papel, o
 * documento acompanha. Sem a fonte, cai na constante.
 */
function lerPaleta(referencia: Element | null): Paleta {
  if (!referencia) return PALETA_DO_DIA;
  const sonda = document.createElement('span');
  referencia.appendChild(sonda);
  const lida = { ...PALETA_DO_DIA };
  for (const [papel, token] of Object.entries(TOKENS) as Array<[keyof Paleta, string]>) {
    sonda.style.color = `var(${token})`;
    const cor = getComputedStyle(sonda).color;
    if (cor) lida[papel] = cor;
  }
  sonda.remove();
  return lida;
}

const FONTE = '"Plus Jakarta Sans", -apple-system, "Segoe UI", Roboto, Arial, sans-serif';

// ─── Utilidades de DOM ───────────────────────────────────────────────────

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

// ─── SVG → PNG ───────────────────────────────────────────────────────────

/** O que o SVG pinta por CSS e que precisa viajar como valor já resolvido. */
const PROPRIEDADES_DO_SVG = [
  'fill', 'fill-opacity', 'fill-rule', 'stroke', 'stroke-width', 'stroke-opacity',
  'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap', 'stroke-linejoin', 'opacity',
  'font-family', 'font-size', 'font-weight', 'font-style', 'letter-spacing', 'text-anchor',
  'dominant-baseline', 'text-transform', 'paint-order', 'visibility', 'display',
] as const;

/**
 * Copia o estilo COMPUTADO de cada nó do original para o clone.
 *
 * `getComputedStyle` já devolve `var()` e `color-mix()` resolvidos, então o
 * clone deixa de depender da folha de estilo da página — que é exatamente o que
 * o SVG-imagem não tem. Os dois percursos andam em paralelo: `cloneNode(true)`
 * preserva a ordem da árvore.
 */
function inlinarEstilos(original: SVGSVGElement, clone: SVGSVGElement): void {
  const de = [original, ...Array.from(original.querySelectorAll('*'))];
  const para = [clone, ...Array.from(clone.querySelectorAll('*'))];
  de.forEach((noOriginal, i) => {
    const alvo = para[i] as SVGElement | undefined;
    if (!alvo) return;
    const calculado = getComputedStyle(noOriginal);
    for (const propriedade of PROPRIEDADES_DO_SVG) {
      alvo.style.setProperty(propriedade, calculado.getPropertyValue(propriedade));
    }
  });
}

let promessaDaFonte: Promise<string | null> | null = null;

/**
 * A Plus Jakarta Sans como `@font-face` em base64, ou `null` se não achar.
 *
 * O arquivo é o mesmo que a página já baixou (fontes.css), então é cache. A
 * fonte é variável (200–800): um arquivo por subset, e o `latin` cobre o
 * português inteiro.
 */
function fonteEmbutida(): Promise<string | null> {
  promessaDaFonte ??= (async () => {
    try {
      for (const folha of Array.from(document.styleSheets)) {
        let regras: CSSRuleList;
        try {
          regras = folha.cssRules;
        } catch {
          continue; // folha de outra origem
        }
        for (const regra of Array.from(regras)) {
          if (!(regra instanceof CSSFontFaceRule)) continue;
          const familia = regra.style.getPropertyValue('font-family');
          const faixa = regra.style.getPropertyValue('unicode-range');
          if (!familia.includes('Plus Jakarta Sans') || !faixa.includes('U+0000-00FF')) continue;
          const bruto = /url\(["']?([^"')]+)["']?\)/.exec(regra.style.getPropertyValue('src'))?.[1];
          if (!bruto) continue;
          const resposta = await fetch(new URL(bruto, folha.href ?? document.baseURI));
          if (!resposta.ok) continue;
          const bytes = new Uint8Array(await resposta.arrayBuffer());
          let binario = '';
          for (let i = 0; i < bytes.length; i += 0x8000) {
            binario += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
          }
          return (
            "@font-face{font-family:'Plus Jakarta Sans';font-weight:200 800;font-style:normal;"
            + `src:url(data:font/woff2;base64,${btoa(binario)}) format('woff2');}`
          );
        }
      }
    } catch {
      // Sem a fonte o gráfico sai na sans-serif do sistema — feio, não quebrado.
    }
    return null;
  })();
  return promessaDaFonte;
}

/** A imagem, com a mesma `data:` URI servindo o logo e os gráficos. */
async function carregarImagem(url: string): Promise<HTMLImageElement> {
  const imagem = new Image();
  await new Promise<void>((resolve, reject) => {
    imagem.onload = () => resolve();
    imagem.onerror = () => reject(new Error('imagem não carregou'));
    imagem.src = url;
  });
  return imagem;
}

/** Um gráfico já rasterizado, com a proporção do desenho original. */
interface GraficoPronto {
  url: string;
  largura: number;
  altura: number;
}

/** Largura, em pixels, em que o gráfico é rasterizado: nítido no papel sem pesar. */
const LARGURA_DO_PNG = 1600;

/**
 * SVG da tela → PNG em `data:` URI.
 *
 * Devolve `null` em vez de estourar: um gráfico que não rasterizou não pode
 * impedir o documento de sair.
 */
async function svgParaImagem(svg: SVGSVGElement | null): Promise<GraficoPronto | null> {
  if (!svg) return null;
  try {
    // A proporção é a do `viewBox`, que é a do desenho. `clientHeight` mede a
    // caixa CSS, que pode esticar.
    const caixa = svg.viewBox.baseVal;
    const largura = caixa.width || svg.clientWidth || 640;
    const altura = caixa.height || svg.clientHeight || 240;

    const clone = svg.cloneNode(true) as SVGSVGElement;
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', String(largura));
    clone.setAttribute('height', String(altura));
    inlinarEstilos(svg, clone);

    const fonte = await fonteEmbutida();
    if (fonte) {
      const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      const estilo = document.createElementNS('http://www.w3.org/2000/svg', 'style');
      estilo.textContent = fonte;
      defs.appendChild(estilo);
      clone.insertBefore(defs, clone.firstChild);
    }

    // Fundo branco explícito: o gráfico na tela herda o fundo do cartão, e no
    // papel ele sairia sobre transparência (= preto, em alguns leitores).
    const fundo = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    fundo.setAttribute('width', '100%');
    fundo.setAttribute('height', '100%');
    fundo.setAttribute('fill', '#ffffff');
    clone.insertBefore(fundo, clone.firstChild?.nextSibling ?? null);

    const textoSvg = new XMLSerializer().serializeToString(clone);
    const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(textoSvg)}`;
    const imagem = await carregarImagem(url);
    // A fonte em base64 dentro de um SVG-imagem carrega DEPOIS do `load`; sem
    // este respiro o primeiro desenho saía na fonte do sistema.
    await new Promise((r) => setTimeout(r, 60));

    const escala = LARGURA_DO_PNG / largura;
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(largura * escala);
    canvas.height = Math.round(altura * escala);
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(imagem, 0, 0, canvas.width, canvas.height);
    return { url: canvas.toDataURL('image/png'), largura, altura };
  } catch {
    return null;
  }
}

// ─── O documento ─────────────────────────────────────────────────────────

export interface DadosDossie {
  ciclo: Ciclo;
  stats: EstatisticasCiclo;
  simulados: readonly Simulado[];
  nomeCriterio: string | null;
  /** Os `<svg>` que estão na tela, na ordem em que devem entrar no documento. */
  graficos: Array<{ titulo: string; svg: SVGSVGElement | null }>;
}

/** Onde o documento vai parar — decide o que o motor de destino aguenta. */
type Destino = 'pdf' | 'word';

/** Largura útil da página em pixels: A4 com margens de ~14 mm. */
const LARGURA_UTIL = { pdf: 688, word: 664 } as const;

const ROTULO = (p: Paleta) =>
  `font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: ${p.texto2}; margin: 0;`;

/**
 * Uma tabela de cartões lado a lado usa `border-spacing` para o vão entre eles,
 * e o vão vale TAMBÉM nas bordas — os cartões ficavam recuados da margem do
 * resto do documento. O `<div>` com margem negativa devolve esse recuo: um
 * bloco com margem lateral negativa cresce para os lados, e a tabela de 100%
 * dentro dele passa a ter a largura útil MAIS o vão. Funciona no Word, que não
 * entende `calc()`.
 */
function compensarEspacamento(
  doc: Document, tabela: HTMLElement, vao: number, abaixo: string,
): HTMLElement {
  const envoltorio = no(doc, 'div', `margin: 0 -${vao}px ${abaixo};`);
  envoltorio.appendChild(tabela);
  return envoltorio;
}

/** Um cartão com filete: onde mora um gráfico ou uma leitura. */
function cartao(doc: Document, p: Paleta, conteudo: HTMLElement[]): HTMLElement {
  const tabela = no(
    doc,
    'table',
    'width: 100%; border-collapse: separate; border-spacing: 0; margin: 0 0 14px;'
      + 'break-inside: avoid; page-break-inside: avoid;',
  );
  const linha = doc.createElement('tr');
  const celula = no(
    doc,
    'td',
    `padding: 12px 14px; border: 1px solid ${p.borda}; border-radius: 12px; background: #ffffff;`
      + 'vertical-align: top;',
  );
  celula.append(...conteudo);
  linha.appendChild(celula);
  tabela.appendChild(linha);
  return tabela;
}

function secao(doc: Document, p: Paleta, titulo: string): HTMLElement {
  return no(
    doc,
    'h2',
    `font-size: 15px; font-weight: 700; color: ${p.acaoBase}; margin: 22px 0 10px;`
      + `padding: 2px 0 2px 10px; border-left: 4px solid ${p.valor};`
      + 'break-after: avoid; page-break-after: avoid;',
    titulo,
  );
}

function imagemDoGrafico(
  doc: Document, grafico: GraficoPronto, titulo: string, larguraPx: number,
): HTMLImageElement {
  const img = no(doc, 'img', 'display: block; max-width: 100%; height: auto; margin: 0 auto;') as HTMLImageElement;
  img.src = grafico.url;
  img.alt = titulo;
  // O atributo, além do CSS: o Word ignora `max-width` e respeita `width`.
  img.width = Math.round(larguraPx);
  img.height = Math.round((larguraPx * grafico.altura) / grafico.largura);
  return img;
}

/** O logo do colégio já branco, para a faixa azul. */
async function logoDoColegio(): Promise<{ url: string; largura: number; altura: number } | null> {
  try {
    const imagem = await carregarImagem(logoBranca);
    const canvas = document.createElement('canvas');
    canvas.width = imagem.naturalWidth;
    canvas.height = imagem.naturalHeight;
    canvas.getContext('2d')?.drawImage(imagem, 0, 0);
    return { url: canvas.toDataURL('image/png'), largura: canvas.width, altura: canvas.height };
  } catch {
    return null;
  }
}

/** Monta o corpo do dossiê num documento qualquer (a janela nova, ou o atual). */
async function montarCorpo(
  doc: Document, dados: DadosDossie, destino: Destino, p: Paleta,
): Promise<HTMLElement[]> {
  const { ciclo, stats, simulados, nomeCriterio } = dados;
  const nos: HTMLElement[] = [];
  const util = LARGURA_UTIL[destino];

  // ── A faixa de abertura ──
  const logo = await logoDoColegio();
  const faixa = no(
    doc,
    'table',
    'width: 100%; border-collapse: separate; border-spacing: 0; margin: 0 0 16px;',
  );
  const linhaFaixa = doc.createElement('tr');
  const esquerda = no(doc, 'td', `padding: 22px 8px 20px 26px; background: ${p.acaoBase}; vertical-align: middle; border-radius: 18px 0 0 18px;`);
  esquerda.appendChild(
    no(
      doc,
      'p',
      `font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: ${p.valor}; margin: 0 0 6px;`,
      'Colégio Ari de Sá · Coordenação ITA/IME',
    ),
  );
  esquerda.appendChild(
    no(doc, 'h1', 'font-size: 26px; font-weight: 700; color: #ffffff; margin: 0 0 6px; line-height: 1.15;', `Dossiê — ${ciclo.nome}`),
  );
  esquerda.appendChild(
    no(
      doc,
      'p',
      'font-size: 12px; color: #c9d5ee; margin: 0;',
      `${ciclo.periodoInicio || '—'} a ${ciclo.periodoFim || '—'} · ${simulados.length} simulados`
        + `${nomeCriterio ? ` · régua: ${nomeCriterio}` : ''}`
        + ` · gerado em ${new Date().toLocaleDateString('pt-BR')}`,
    ),
  );
  linhaFaixa.appendChild(esquerda);
  if (logo) {
    const direita = no(doc, 'td', `padding: 20px 26px 20px 8px; background: ${p.acaoBase}; vertical-align: middle; text-align: right; width: 120px; border-radius: 0 18px 18px 0;`);
    const img = no(doc, 'img', 'display: block; margin-left: auto;') as HTMLImageElement;
    img.src = logo.url;
    img.alt = 'Colégio Ari de Sá';
    img.width = 96;
    img.height = Math.round((96 * logo.altura) / logo.largura);
    direita.appendChild(img);
    linhaFaixa.appendChild(direita);
  }
  faixa.appendChild(linhaFaixa);
  nos.push(faixa);

  // ── Os números do topo: uma tabela, porque o Word não conhece `flex` ──
  const resumo = stats.resumo ?? {};
  const kpis = no(doc, 'table', 'width: 100%; border-collapse: separate; border-spacing: 8px 0; table-layout: fixed;');
  const linhaKpis = doc.createElement('tr');
  for (const [rotulo, valor] of [
    ['Média do ciclo', resumo.media == null ? '—' : fmtNota(resumo.media)],
    ['Acima do corte', pct(resumo.pctAprovados)],
    ['Zona crítica', pct(resumo.pctZonaCritica)],
    ['Excelência', pct(resumo.pctExcelencia)],
  ] as Array<[string, string]>) {
    const celula = no(
      doc,
      'td',
      `padding: 12px 14px 11px; background: ${p.superficie}; border: 1px solid ${p.borda}; border-radius: 12px; vertical-align: top;`,
    );
    celula.appendChild(no(doc, 'p', ROTULO(p), rotulo));
    celula.appendChild(no(doc, 'p', `font-size: 28px; font-weight: 700; color: ${p.magnitude}; margin: 4px 0 0; line-height: 1.1;`, valor));
    linhaKpis.appendChild(celula);
  }
  kpis.appendChild(linhaKpis);
  nos.push(compensarEspacamento(doc, kpis, 8, '6px'));

  // ── A leitura, em linguagem de gente ──
  //
  // É o texto que o §4.4 do docs/25 pedia, e ele já existe: `insights.pratico`
  // vem cacheado por hash do payload, então o dossiê não paga LLM nenhum.
  const leitura = stats.conjunta?.insights?.pratico ?? [];
  if (leitura.length > 0) {
    nos.push(secao(doc, p, 'Leitura do ciclo'));
    const lista = no(doc, 'ul', `font-size: 13px; color: ${p.texto}; margin: 0 0 8px; padding-left: 20px; line-height: 1.55;`);
    for (const bullet of leitura) lista.appendChild(no(doc, 'li', 'margin: 0 0 5px;', bullet));
    nos.push(cartao(doc, p, [lista]));
  }

  // ── Os gráficos ──
  //
  // Os grandes (evolução, visão geral) entram em largura cheia, com o título
  // da seção. Os mini-histogramas por matéria entram em duas colunas, sob um
  // único título, porque são a mesma peça em N recortes e a comparação é o
  // assunto — dois lado a lado se leem, dez empilhados se rolam.
  const prontos: Array<{ titulo: string; grafico: GraficoPronto; pequeno: boolean }> = [];
  for (const { titulo, svg } of dados.graficos) {
    const grafico = await svgParaImagem(svg);
    if (!grafico) continue;
    const pequeno = !!svg?.closest('.ciclo-materia__hist, .ciclo-materia__hist-vazio');
    prontos.push({ titulo, grafico, pequeno });
  }

  let indice = 0;
  while (indice < prontos.length) {
    const atual = prontos[indice] as (typeof prontos)[number];
    if (!atual.pequeno) {
      nos.push(secao(doc, p, atual.titulo));
      nos.push(
        cartao(doc, p, [imagemDoGrafico(doc, atual.grafico, atual.titulo, util - 30)]),
      );
      indice += 1;
      continue;
    }

    const grupo: typeof prontos = [];
    while (indice < prontos.length && (prontos[indice] as (typeof prontos)[number]).pequeno) {
      grupo.push(prontos[indice] as (typeof prontos)[number]);
      indice += 1;
    }
    nos.push(secao(doc, p, 'Distribuição por matéria'));
    const grade = no(doc, 'table', 'width: 100%; border-collapse: separate; border-spacing: 8px 8px; table-layout: fixed;');
    for (let i = 0; i < grupo.length; i += 2) {
      const linha = doc.createElement('tr');
      for (const item of grupo.slice(i, i + 2)) {
        const celula = no(
          doc,
          'td',
          `padding: 10px 12px; border: 1px solid ${p.borda}; border-radius: 12px; vertical-align: top;`
            + 'break-inside: avoid; page-break-inside: avoid;',
        );
        celula.appendChild(no(doc, 'p', `font-size: 12px; font-weight: 700; color: ${p.magnitude}; margin: 0 0 6px;`, item.titulo));
        celula.appendChild(imagemDoGrafico(doc, item.grafico, item.titulo, (util - 8) / 2 - 32));
        linha.appendChild(celula);
      }
      if (grupo.slice(i, i + 2).length === 1) linha.appendChild(no(doc, 'td', 'border: 0;'));
      grade.appendChild(linha);
    }
    nos.push(compensarEspacamento(doc, grade, 8, '6px'));
  }

  // ── A tabela por matéria ──
  const porMateria = (stats.porMateria ?? []).filter(Boolean) as RecorteMateria[];
  if (porMateria.length > 0) {
    nos.push(secao(doc, p, 'Por matéria'));
    nos.push(
      tabela(
        doc,
        p,
        ['Matéria', 'Corte', 'Média F1', 'Acima do corte F1', 'Média F2', 'Acima do corte F2'],
        porMateria.map((m) => [
          m.materia.nome + (m.eliminatoria ? ' (eliminatória)' : ''),
          m.corte == null ? '—' : fmtNota(m.corte),
          m.fase1?.stats.media == null ? '—' : fmtNota(m.fase1.stats.media),
          pct(m.fase1?.stats.pctAprovados),
          m.fase2?.stats.media == null ? '—' : fmtNota(m.fase2.stats.media),
          pct(m.fase2?.stats.pctAprovados),
        ]),
        [false, true, true, true, true, true],
      ),
    );
  }

  // ── A tabela de simulados ──
  if (simulados.length > 0) {
    nos.push(secao(doc, p, 'Simulados do ciclo'));
    nos.push(
      tabela(
        doc,
        p,
        ['Prova', 'Matéria', 'Data', 'Média', 'Presentes'],
        simulados.map((s) => [
          s.rotuloCurto || s.nome,
          s.materia?.nome ?? '—',
          s.dataAplicacao || '—',
          s.media == null ? '—' : fmtNota(s.media),
          s.nPresentes == null ? '—' : String(s.nPresentes),
        ]),
        [false, false, false, true, true],
      ),
    );
  }

  nos.push(
    no(
      doc,
      'p',
      `font-size: 10.5px; color: ${p.texto2}; margin: 26px 0 0; padding-top: 10px; border-top: 1px solid ${p.borda};`,
      'Gerado pelo SAS — Colégio Ari de Sá. Os percentuais seguem a régua de corte indicada no '
        + 'topo; trocar a régua muda os números.',
    ),
  );
  return nos;
}

/** `alinhaDireita[i]` diz se a coluna `i` é numérica — número à direita, texto à esquerda. */
function tabela(
  doc: Document, p: Paleta, cabecalho: string[], linhas: string[][], alinhaDireita: boolean[],
): HTMLElement {
  const lado = (i: number) => (alinhaDireita[i] ? 'right' : 'left');
  const t = no(
    doc,
    'table',
    `width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; margin: 0 0 14px;`
      + `border: 1px solid ${p.borda}; border-radius: 12px;`,
  );
  const thead = doc.createElement('thead');
  const trCab = doc.createElement('tr');
  cabecalho.forEach((c, i) => {
    // Os cantos de cima da tabela são do primeiro e do último `th`: o fundo do
    // cabeçalho pinta por cima do raio da borda e o deixaria quadrado.
    const canto =
      i === 0 ? 'border-top-left-radius: 11px;'
        : i === cabecalho.length - 1 ? 'border-top-right-radius: 11px;'
          : '';
    trCab.appendChild(
      no(
        doc,
        'th',
        `text-align: ${lado(i)}; padding: 8px 10px; background: ${p.superficie2}; color: ${p.texto2};`
          + `font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;`
          + `border-bottom: 1px solid ${p.borda}; ${canto}`,
        c,
      ),
    );
  });
  thead.appendChild(trCab);
  t.appendChild(thead);

  const tbody = doc.createElement('tbody');
  linhas.forEach((linha, n) => {
    const tr = no(doc, 'tr', 'break-inside: avoid; page-break-inside: avoid;');
    linha.forEach((celula, i) => {
      tr.appendChild(
        no(
          doc,
          'td',
          `text-align: ${lado(i)}; padding: 7px 10px; color: ${p.texto};`
            + `${i === 0 ? 'font-weight: 600;' : ''}`
            + `${n < linhas.length - 1 ? `border-bottom: 1px solid ${p.borda};` : ''}`
            + (alinhaDireita[i] ? 'font-variant-numeric: tabular-nums;' : ''),
          celula,
        ),
      );
    });
    tbody.appendChild(tr);
  });
  t.appendChild(tbody);
  return t;
}

// ─── PDF ─────────────────────────────────────────────────────────────────

/**
 * `@page` só existe em folha de estilo — não há atributo equivalente.
 *
 * ⚠️ `margin: 0`, e a margem de verdade vem de espaçadores no documento
 * (`envolverNaFolha`). É o único jeito de o navegador NÃO imprimir, nas bordas
 * de cada página, a data, o "about:blank" e o número da página — o navegador só
 * os desenha dentro da margem da página, e sem margem eles não têm onde ir.
 * Ninguém quer "about:blank" no rodapé de um documento que vai à reunião.
 */
function aplicarRegrasDePagina(doc: Document): void {
  const folha = doc.createElement('style');
  doc.head.appendChild(folha);
  try {
    folha.sheet?.insertRule('@page { size: A4; margin: 0; }', 0);
  } catch {
    // Navegador que recuse a regra imprime com a margem padrão — perde-se o
    // A4 exato, não o documento.
  }
}

/** Leva a Plus Jakarta Sans para a janela nova, que nasce sem nenhuma folha. */
function copiarFontesParaJanela(doc: Document): void {
  const folha = doc.createElement('style');
  doc.head.appendChild(folha);
  for (const original of Array.from(document.styleSheets)) {
    let regras: CSSRuleList;
    try {
      regras = original.cssRules;
    } catch {
      continue;
    }
    for (const regra of Array.from(regras)) {
      if (!(regra instanceof CSSFontFaceRule)) continue;
      if (!regra.style.getPropertyValue('font-family').includes('Plus Jakarta Sans')) continue;
      try {
        // A URL do `src` é relativa à folha de origem; a janela nova é
        // `about:blank`, então a absoluta precisa ser escrita por extenso.
        const src = regra.style
          .getPropertyValue('src')
          .replace(/url\(["']?([^"')]+)["']?\)/g, (_, u: string) =>
            `url("${new URL(u, original.href ?? document.baseURI).href}")`);
        folha.sheet?.insertRule(
          `@font-face { font-family: "Plus Jakarta Sans"; font-style: normal; `
            + `font-weight: ${regra.style.getPropertyValue('font-weight') || '400'}; `
            + `unicode-range: ${regra.style.getPropertyValue('unicode-range') || 'U+0-10FFFF'}; `
            + `src: ${src}; }`,
          folha.sheet.cssRules.length,
        );
      } catch {
        // Uma regra que o navegador recuse não pode derrubar as outras.
      }
    }
  }
}

/**
 * Margem de página feita de espaçadores: a tabela repete `thead` e `tfoot` em
 * cada folha impressa, e é isso que dá 12 mm em cima e embaixo de TODAS elas
 * com `@page { margin: 0 }`. Ver `aplicarRegrasDePagina`.
 */
function envolverNaFolha(doc: Document, conteudo: HTMLElement[]): HTMLElement {
  const folha = no(doc, 'table', 'width: 100%; border-collapse: collapse; border: 0;');
  const espacador = (tag: 'thead' | 'tfoot') => {
    const bloco = doc.createElement(tag);
    const linha = doc.createElement('tr');
    linha.appendChild(no(doc, 'td', 'height: 12mm; padding: 0; border: 0;'));
    bloco.appendChild(linha);
    return bloco;
  };
  folha.appendChild(espacador('thead'));
  const corpo = doc.createElement('tbody');
  const linha = doc.createElement('tr');
  const celula = no(doc, 'td', 'padding: 0 14mm; border: 0; vertical-align: top;');
  celula.append(...conteudo);
  linha.appendChild(celula);
  corpo.appendChild(linha);
  folha.appendChild(corpo);
  folha.appendChild(espacador('tfoot'));
  return folha;
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

  const paleta = lerPaleta(dados.graficos.find((g) => g.svg)?.svg?.closest('.ciclo-dossie-fonte') ?? null);
  const doc = janela.document;
  doc.title = `Dossiê — ${dados.ciclo.nome}`;
  doc.documentElement.lang = 'pt-BR';
  aplicarRegrasDePagina(doc);
  copiarFontesParaJanela(doc);
  // `print-color-adjust: exact` é o que faz o navegador IMPRIMIR os fundos: por
  // padrão ele os descarta para poupar tinta, e a faixa azul, os cartões e o
  // cabeçalho das tabelas saíam brancos — "preto e branco".
  doc.body.style.cssText =
    `margin: 0; background: #ffffff; font-family: ${FONTE}; color: ${paleta.texto}; line-height: 1.5;`
    + '-webkit-print-color-adjust: exact; print-color-adjust: exact;';
  doc.body.replaceChildren(envolverNaFolha(doc, await montarCorpo(doc, dados, 'pdf', paleta)));

  // As imagens são `data:` URI — já estão prontas, sem rede. A fonte, não: sem
  // esperá-la o diálogo de impressão abria com a fonte do sistema.
  try {
    await doc.fonts.load('400 12px "Plus Jakarta Sans"');
    await doc.fonts.load('700 12px "Plus Jakarta Sans"');
    await doc.fonts.ready;
  } catch {
    // Sem `document.fonts` o documento sai na fonte de reserva — não é erro.
  }
  janela.setTimeout(() => {
    try {
      janela.focus();
      janela.print();
    } catch {
      // Janela fechada pelo usuário antes da hora — não é erro do app.
    }
  }, 250);
}

// ─── Word ────────────────────────────────────────────────────────────────

/**
 * Word, sem dependência nenhuma — o mesmo envelope de `telas/Banco/exportar.ts`.
 *
 * ⚠️ Sai `.doc` (HTML que o Word abre e edita), não `.docx` (OOXML zipado). O
 * botão diz "Word" para o rótulo não prometer o que não entrega.
 *
 * Aqui o `style` inline é obrigatório e seguro: o arquivo sai do navegador, a
 * CSP não o alcança, e é o que o Word entende. Pelo mesmo motivo o `@page`
 * pode ir num `<style>` de verdade.
 */
export async function exportarDossieWord(dados: DadosDossie): Promise<void> {
  const paleta = lerPaleta(dados.graficos.find((g) => g.svg)?.svg?.closest('.ciclo-dossie-fonte') ?? null);
  const corpo = document.createElement('div');
  corpo.append(...(await montarCorpo(document, dados, 'word', paleta)));

  const html =
    '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
    + 'xmlns:w="urn:schemas-microsoft-com:office:word" '
    + 'xmlns="http://www.w3.org/TR/REC-html40">'
    + '<head><meta charset="utf-8">'
    + `<title>Dossiê — ${dados.ciclo.nome}</title>`
    + '<style>@page Secao1 { size: 21cm 29.7cm; margin: 1.6cm 1.6cm 1.6cm 1.6cm; } '
    + 'div.Secao1 { page: Secao1; }</style></head>'
    + `<body style="font-family: ${FONTE.replace(/"/g, "'")}; color: ${paleta.texto}; line-height: 1.5; margin: 0;">`
    + `<div class="Secao1">${corpo.innerHTML}</div></body></html>`;

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
