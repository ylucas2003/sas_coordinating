import { ehDissertativa, rotuloQuestao, temGabarito } from '../../dominio/banco';
import type { Lista, QuestaoVestibular } from '../../tipos/banco';

// Exportação da lista de questões (docs/22 §5.3).
//
// ⚠️ O estilo NÃO vai por atributo `style` nem por `<style>` com conteúdo.
// A CSP de produção é `style-src 'self'`, sem 'unsafe-inline'
// (infra/vps/nginx.conf), e a janela aberta por `window.open('')` herda a CSP
// de quem a abriu. Atributo inline seria descartado em silêncio — o PDF sairia
// sem cor e sem margem, e ninguém veria erro no console do app. Foi
// exatamente o que mordeu o gerador da ficha do aluno (docs/16 §Bugs), e a
// saída de lá é a daqui: aplicar `style` por CSSOM (`.style.cssText`), que a
// CSP não intercepta. Ver `src/exportacao/dom.js`.
//
// O `<style>` que carrega `@page` é criado VAZIO e recebe as regras por
// `insertRule`: sem conteúdo inline, não há o que bloquear.
//
// ⚠️ Testar em PRODUÇÃO, não só no dev — a CSP do dev é mais frouxa
// (docs/22 §8, risco 7).

/** Teto de espera pelas imagens do S3 antes de imprimir assim mesmo. */
const TETO_ESPERA_IMAGENS_MS = 6000;

const ESTILO_CORPO =
  'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;' +
  'color: #1a1d24; line-height: 1.5; margin: 0; padding: 24px; max-width: 760px;';
const ESTILO_TITULO = 'font-size: 22px; font-weight: 600; margin: 0 0 4px;';
const ESTILO_SUBTITULO = 'font-size: 12px; color: #5a5d65; margin: 0 0 24px;';
// `break-inside: avoid` para a questão não rachar entre duas páginas do PDF.
const ESTILO_QUESTAO =
  'margin: 0 0 22px; padding: 0 0 18px; border-bottom: 1px solid #e0e3eb; break-inside: avoid;';
const ESTILO_REFERENCIA = 'font-size: 12px; font-weight: 600; color: #1b3f8b; margin: 0 0 8px;';
const ESTILO_ENUNCIADO = 'font-size: 13px; white-space: pre-wrap; margin: 0 0 8px;';
const ESTILO_IMAGEM = 'max-width: 100%; height: auto; display: block; margin: 0 0 8px;';
const ESTILO_ALTERNATIVA = 'font-size: 13px; margin: 0 0 3px;';
const ESTILO_TOPICOS = 'font-size: 11px; color: #73757d; margin: 6px 0 0;';
const ESTILO_GABARITO_TITULO = 'font-size: 15px; font-weight: 600; margin: 24px 0 8px;';
const ESTILO_GABARITO_LINHA = 'font-size: 12px; font-family: monospace; margin: 0 0 3px;';

/** Cria um nó já estilizado por CSSOM. `texto` vai como texto, nunca como HTML. */
function no(doc: Document, tag: string, estilo: string, texto?: string): HTMLElement {
  const elemento = doc.createElement(tag);
  if (estilo) elemento.style.cssText = estilo;
  if (texto != null) elemento.textContent = texto;
  return elemento;
}

function dataDeHoje(): string {
  return new Date().toLocaleDateString('pt-BR');
}

function blocoQuestao(doc: Document, questao: QuestaoVestibular, posicao: number): HTMLElement {
  const secao = no(doc, 'section', ESTILO_QUESTAO);

  const referencia = ehDissertativa(questao)
    ? `${posicao}. ${rotuloQuestao(questao)} · discursiva`
    : `${posicao}. ${rotuloQuestao(questao)}`;
  secao.appendChild(no(doc, 'div', ESTILO_REFERENCIA, referencia));

  // Mesma regra da tela: a imagem é o enunciado de verdade (preserva fórmula e
  // figura); o texto extraído é o reserva, e traz sujeira de OCR junto.
  if (questao.usaImagemNoRender && questao.imagemUrl) {
    const imagem = no(doc, 'img', ESTILO_IMAGEM) as HTMLImageElement;
    imagem.src = questao.imagemUrl;
    imagem.alt = rotuloQuestao(questao);
    secao.appendChild(imagem);
  } else {
    secao.appendChild(no(doc, 'p', ESTILO_ENUNCIADO, questao.enunciadoMd));
    for (const [letra, texto] of Object.entries(questao.alternativas ?? {})) {
      secao.appendChild(no(doc, 'p', ESTILO_ALTERNATIVA, `${letra}) ${texto}`));
    }
  }

  if (questao.topicos.length > 0) {
    const nomes = questao.topicos.map((t) => `${t.codigo} · ${t.nome}`).join('   |   ');
    secao.appendChild(no(doc, 'p', ESTILO_TOPICOS, nomes));
  }

  return secao;
}

/** `@page` só existe em folha de estilo — não há atributo equivalente. */
function aplicarRegrasDePagina(doc: Document): void {
  const folha = doc.createElement('style');
  doc.head.appendChild(folha);
  const regras = ['@page { size: A4; margin: 18mm; }'];
  try {
    for (const regra of regras) folha.sheet?.insertRule(regra, folha.sheet.cssRules.length);
  } catch {
    // Navegador que recuse a regra imprime com a margem padrão — perde-se o
    // A4 exato, não o documento.
  }
}

/**
 * As imagens vêm do S3 e chegam depois do `document`. Imprimir antes delas
 * gera um PDF de retângulos vazios — daí esperar o `load` de cada uma, com
 * teto: em produção a CSP (`img-src 'self'`) pode barrá-las, e aí o que chega
 * é `error`, que também conta como resolvida.
 */
function imprimirQuandoAsImagensCarregarem(janela: Window): void {
  let jaImprimiu = false;
  const imprimir = () => {
    if (jaImprimiu) return;
    jaImprimiu = true;
    try {
      janela.focus();
      janela.print();
    } catch {
      // Janela fechada pelo usuário antes da hora — não é erro do app.
    }
  };

  const imagens = Array.from(janela.document.images);
  let pendentes = imagens.filter((img) => !img.complete).length;
  if (pendentes === 0) {
    janela.setTimeout(imprimir, 300);
    return;
  }

  const contar = () => {
    pendentes -= 1;
    if (pendentes <= 0) janela.setTimeout(imprimir, 150);
  };
  for (const imagem of imagens) {
    if (imagem.complete) continue;
    imagem.addEventListener('load', contar, { once: true });
    imagem.addEventListener('error', contar, { once: true });
  }

  janela.setTimeout(imprimir, TETO_ESPERA_IMAGENS_MS);
}

/**
 * PDF pela impressão do navegador, como o resto do projeto faz
 * (`exportacao/exportar-aluno.js`): não entra dependência de geração de PDF
 * para um documento que o próprio browser já sabe paginar.
 *
 * Lança em vez de devolver `false` para a tela poder dizer o que houve — pop-up
 * bloqueado é a causa mais comum e tem conserto do lado do usuário.
 */
export function exportarPdf(lista: Lista): void {
  if (lista.questoes.length === 0) {
    throw new Error('Adicione pelo menos uma questão à lista antes de exportar.');
  }

  const janela = window.open('', '_blank');
  if (!janela) {
    throw new Error(
      'O navegador bloqueou a janela de impressão. Permita pop-ups para este site e tente de novo.',
    );
  }

  const doc = janela.document;
  doc.title = lista.titulo;
  doc.documentElement.lang = 'pt-BR';
  aplicarRegrasDePagina(doc);

  const corpo = doc.body;
  corpo.style.cssText = ESTILO_CORPO;

  const nos: HTMLElement[] = [
    no(doc, 'h1', ESTILO_TITULO, lista.titulo),
    no(
      doc,
      'p',
      ESTILO_SUBTITULO,
      `${lista.questoes.length} ${lista.questoes.length === 1 ? 'questão' : 'questões'} · gerado em ${dataDeHoje()}`,
    ),
    ...lista.questoes.map((questao, i) => blocoQuestao(doc, questao, i + 1)),
  ];

  // Gabarito no fim, e não junto de cada questão: a lista é para resolver.
  // Só as que têm letra — 469 das 934 não têm, quase todas discursivas de 2ª
  // fase, e é o esperado (docs/22 §8, risco 4).
  const comGabarito = lista.questoes
    .map((questao, i) => ({ questao, posicao: i + 1 }))
    .filter(({ questao }) => temGabarito(questao));

  if (comGabarito.length > 0) {
    nos.push(no(doc, 'h2', ESTILO_GABARITO_TITULO, 'Gabarito'));
    for (const { questao, posicao } of comGabarito) {
      nos.push(no(doc, 'p', ESTILO_GABARITO_LINHA, `${posicao}. ${questao.gabarito}`));
    }
  }

  corpo.replaceChildren(...nos);
  imprimirQuandoAsImagensCarregarem(janela);
}

/**
 * Word, sem dependência nenhuma.
 *
 * O caminho previsto em docs/22 §3.4 era trazer `html-docx-js` como dependência
 * npm. Não trouxe, por duas razões: o pacote está parado desde 2022, e o que
 * ele faz por baixo é justamente isto — embrulhar HTML num envelope que o Word
 * reconhece. Fazer aqui custa ~30 linhas e nenhuma superfície de terceiro num
 * projeto que trata dado de menores (CLAUDE.md, regra 6).
 *
 * ⚠️ Sai `.doc` (HTML que o Word abre e edita), não `.docx` (OOXML zipado). Um
 * `.docx` de verdade exigiria montar um ZIP, e o ganho seria formato, não
 * capacidade: o Word, o LibreOffice e o Google Docs abrem e editam os dois. O
 * botão diz "Word" e não "DOCX" para o rótulo não prometer o que não entrega.
 *
 * As imagens seguem por URL do S3, como no PDF: o Word as busca ao abrir, então
 * o arquivo precisa de rede na primeira abertura. Embutir em base64 deixaria o
 * arquivo em dezenas de MB.
 */
export function exportarWord(lista: Lista): void {
  if (lista.questoes.length === 0) {
    throw new Error('Adicione pelo menos uma questão à lista antes de exportar.');
  }

  // Montado no documento ATUAL e serializado — o mesmo `blocoQuestao` do PDF,
  // para as duas saídas não divergirem. Aqui o `style` inline é obrigatório (o
  // arquivo sai do navegador e a CSP não o alcança), e é o que o Word entende.
  const corpo = document.createElement('div');
  corpo.appendChild(no(document, 'h1', ESTILO_TITULO, lista.titulo));
  corpo.appendChild(
    no(
      document,
      'p',
      ESTILO_SUBTITULO,
      `${lista.questoes.length} questões · Banco ITA · IME · ${dataDeHoje()}`,
    ),
  );
  lista.questoes.forEach((questao, i) => {
    corpo.appendChild(blocoQuestao(document, questao, i + 1));
  });

  const documento =
    '<html xmlns:o="urn:schemas-microsoft-com:office:office" ' +
    'xmlns:w="urn:schemas-microsoft-com:office:word" ' +
    'xmlns="http://www.w3.org/TR/REC-html40">' +
    '<head><meta charset="utf-8">' +
    `<title>${lista.titulo.replace(/[<>&]/g, '')}</title>` +
    // Diz ao Word para abrir em modo de impressão com página A4 — sem isto ele
    // abre em "layout web", sem margem e sem quebra de página.
    '<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View>' +
    '<w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->' +
    '<style>@page { size: A4; margin: 18mm; }</style>' +
    `</head><body style="${ESTILO_CORPO}">${corpo.innerHTML}</body></html>`;

  const arquivo = new Blob(['\ufeff', documento], { type: 'application/msword' });
  const url = URL.createObjectURL(arquivo);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${nomeDeArquivo(lista.titulo)}.doc`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revogar na hora corta o download em alguns navegadores; um tick basta.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** "Ondas para a prova" → "ondas-para-a-prova". */
function nomeDeArquivo(titulo: string): string {
  const limpo = titulo
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return limpo || 'lista-de-questoes';
}
