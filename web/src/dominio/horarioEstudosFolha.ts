// A folha do horário de estudos — o layout do PDF e do PNG (docs/42).
//
// Esta função NÃO desenha: ela devolve PRIMITIVAS (retângulo, linha, texto,
// imagem) em pontos, numa página A4 deitada. `exportacao/desenharFolha.ts` as
// pinta num canvas, e o PNG é esse canvas; o PDF é o mesmo canvas dentro de uma
// página (`exportacao/pdf.ts`). Por isso os dois sempre saem iguais — e o layout
// se testa sem navegador, injetando um `medir` de mentira.
//
// ⚠️ O DOCUMENTO TEM A CARA DO SITE DO ALUNO, nos DOIS temas, à escolha de quem
// exporta (decisão de 24/10). Os hexadecimais são os de `--dia-*` e `--noite-*` em
// `styles/paleta.css` — e `horarioEstudosFolha.test.ts` LÊ aquele arquivo e falha se
// uma cor daqui divergir dele. É o que impede a exportação de envelhecer sozinha
// quando alguém mexe na paleta. O que vem do site: a fonte, a logo (o mesmo glifo
// branco que o casco pinta por máscara), a grade quadrada de fundo, o cartão com
// borda e raio, a legenda em azul (`.alu-olho`), o número grande em extra-negrito.
//
// ⚠️ A GRADE DO DOCUMENTO NÃO É A DA TELA. A tela é uma lista, porque "a área do
// aluno não deve ter tabela nenhuma" (docs/24 §7). Um horário que se imprime e se
// cola na parede é, por natureza, uma grade: dias nas colunas, tempo nas linhas, e
// o bloco ocupando a altura que dura — é o único jeito de o buraco entre dois
// blocos aparecer como buraco, e o de a página ficar cheia.
//
// ⚠️ UMA PÁGINA, POR CONSTRUÇÃO. Nada aqui quebra página: a grade escala para
// caber, e o texto que não cabe num bloco é cortado (com reticências), nunca
// empurrado para fora. É o que "o PDF em uma página só" quer dizer.

import type { BlocoDeEstudo } from '../tipos/horarioEstudos';
import {
  DIAS_DA_SEMANA,
  duracaoPorExtenso,
  fimDe,
  minutosDe,
  totalDeMinutos,
} from './horarioEstudos';

// ─── Os dois temas ───────────────────────────────────────────────────────

export type TemaDaFolha = 'dia' | 'noite';

export interface Paleta {
  fundo: string;
  /** A grade quadrada de fundo — a mistura JÁ FEITA (a folha não tem transparência). */
  grade: string;
  superficie: string;
  superficie2: string;
  borda: string;
  acao: string;
  acaoTexto: string;
  dado: string;
  dadoClaro: string;
  magnitude: string;
  texto: string;
  texto2: string;
  /** A cor da logo: o casco a pinta de azul-marinho no dia e de branco na noite. */
  marca: string;
}

/** Mistura `cor` (RGB) com opacidade `alfa` sobre `sobre` (#rrggbb) — um hex sólido. */
export function misturar(sobre: string, cor: [number, number, number], alfa: number): string {
  const base = [1, 3, 5].map((i) => Number.parseInt(sobre.slice(i, i + 2), 16));
  return `#${base
    .map((b, i) => Math.round(b * (1 - alfa) + cor[i] * alfa).toString(16).padStart(2, '0'))
    .join('')}`;
}

/**
 * ⚠️ Estes são os valores de `styles/paleta.css`, e o teste os confere contra o
 * arquivo. `grade` é `--dia-grade` (rgba(27, 63, 139, 0.045)) e `--noite-grade`
 * (rgba(127, 182, 255, 0.05)) já misturados com o fundo.
 */
export const PALETAS: Record<TemaDaFolha, Paleta> = {
  dia: {
    fundo: '#ffffff',
    grade: misturar('#ffffff', [27, 63, 139], 0.045),
    superficie: '#f4f7fc',
    superficie2: '#eaf0fa',
    borda: '#dce6f7',
    acao: '#1b3f8b',
    acaoTexto: '#ffffff',
    dado: '#2e6be6',
    dadoClaro: '#7fb6ff',
    magnitude: '#0f1b33',
    texto: '#16233d',
    texto2: '#5c6883',
    marca: '#1b3f8b',
  },
  noite: {
    fundo: '#050a18',
    grade: misturar('#050a18', [127, 182, 255], 0.05),
    superficie: '#0c1530',
    superficie2: '#101c3d',
    borda: '#1b2b57',
    acao: '#ffce3a',
    acaoTexto: '#050a18',
    dado: '#2f6bff',
    dadoClaro: '#7fb6ff',
    magnitude: '#ffffff',
    texto: '#e6edfb',
    texto2: '#6e85b8',
    marca: '#ffffff',
  },
};

// ─── As primitivas ───────────────────────────────────────────────────────

export interface Retangulo {
  tipo: 'retangulo';
  x: number;
  y: number;
  largura: number;
  altura: number;
  raio?: number;
  preenchimento?: string;
  traco?: { cor: string; largura: number };
}

export interface Linha {
  tipo: 'linha';
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  cor: string;
  largura: number;
}

export type Peso = 500 | 600 | 700 | 800;

export interface Texto {
  tipo: 'texto';
  /** Esquerda do texto — o alinhamento (centro, direita) já vem resolvido. */
  x: number;
  /** A LINHA DE BASE, e não o topo: é o que o canvas entende. */
  y: number;
  texto: string;
  tamanho: number;
  peso: Peso;
  cor: string;
  /** Espaço extra entre as letras, em pontos — a legenda em caixa-alta do site. */
  espacamento?: number;
  /** O texto de dentro de um bloco é cortado nesta caixa: nunca vaza para o vizinho. */
  recorte?: { x: number; y: number; largura: number; altura: number };
}

/** A logo do colégio, tingida de `cor` (o glifo é branco com transparência). */
export interface Imagem {
  tipo: 'imagem';
  chave: 'logo';
  x: number;
  y: number;
  largura: number;
  altura: number;
  cor: string;
}

export type Primitiva = Retangulo | Linha | Texto | Imagem;

export interface Folha {
  largura: number;
  altura: number;
  tema: TemaDaFolha;
  primitivas: Primitiva[];
}

/** Largura de um texto, na unidade da folha (pontos). Quem chama escolhe a fonte. */
export type Medir = (texto: string, tamanho: number, peso: Peso) => number;

// ─── A página e as medidas ───────────────────────────────────────────────

/** A4 deitado, em pontos (1 pt = 1/72"). */
export const PAGINA = { largura: 842, altura: 595 } as const;

const MARGEM = 30;
const TOPO_DO_CARTAO = 96;
const BASE_DO_CARTAO = PAGINA.altura - MARGEM - 20;
const ALTURA_DOS_DIAS = 26;
const LARGURA_DAS_HORAS = 38;
const RECUO_DO_CARTAO = 8;
/** O lado do quadrado da grade de fundo: os 24px do `.alu-grade` do site. */
const QUADRADO_DO_FUNDO = 24;

/** Quantas horas a grade mostra, no mínimo. Ver `faixaDeHoras`. */
export const MINIMO_DE_HORAS = 6;

// ─── A faixa de horas ────────────────────────────────────────────────────

/**
 * (hora inicial, hora final) da grade — horas inteiras, no máximo 0..24.
 *
 * O início sai da hora cheia do bloco mais cedo, e o fim da hora cheia seguinte ao
 * bloco mais tarde. Se sobrar pouco, a folga se DIVIDE dos dois lados — quem estuda
 * só às 19h vê 17h–23h, e não 18h–24h com um terço da página vazio no fim — e,
 * batendo na meia-noite (ou no zero), o que sobrou vai para o outro lado.
 *
 * ⚠️ É a MESMA regra de `api/app/horario_estudos_planilha.py::faixa_de_horas`, e a
 * repetição é deliberada: o PDF e o Excel têm de mostrar o mesmo recorte do dia.
 * Os casos de `horarioEstudosFolha.test.ts` são os do teste de lá.
 */
export function faixaDeHoras(blocos: BlocoDeEstudo[]): [number, number] {
  const inicio = Math.floor(Math.min(...blocos.map((b) => minutosDe(b.horaInicio) ?? 0)) / 60);
  let fim = Math.ceil(
    Math.max(...blocos.map((b) => (minutosDe(b.horaInicio) ?? 0) + b.duracaoMinutos)) / 60,
  );
  let comeco = inicio;
  const falta = MINIMO_DE_HORAS - (fim - comeco);
  if (falta > 0) {
    comeco = Math.max(0, inicio - Math.floor(falta / 2));
    fim = Math.min(24, fim + (falta - (inicio - comeco)));
    const sobrou = MINIMO_DE_HORAS - (fim - comeco);
    if (sobrou > 0) comeco = Math.max(0, comeco - sobrou);
  }
  return [comeco, fim];
}

// ─── Quebrar texto ───────────────────────────────────────────────────────

/**
 * Quebra `texto` em linhas que caibam em `largura`, pela medida real da fonte.
 *
 * Passando de `maxLinhas`, a última termina em reticências. Uma palavra maior que a
 * linha inteira (80 caracteres sem espaço) é partida por letra — melhor uma palavra
 * partida do que uma palavra que vaza do bloco.
 */
export function quebrar(
  texto: string,
  largura: number,
  tamanho: number,
  peso: Peso,
  medir: Medir,
  maxLinhas: number,
): string[] {
  if (maxLinhas < 1) return [];
  const cabe = (t: string) => medir(t, tamanho, peso) <= largura;

  const linhas: string[] = [];
  let atual = '';
  for (const palavra of texto.trim().split(/\s+/).filter(Boolean)) {
    const tentativa = atual ? `${atual} ${palavra}` : palavra;
    if (cabe(tentativa)) {
      atual = tentativa;
      continue;
    }
    if (atual) linhas.push(atual);
    atual = '';
    let resto = palavra;
    while (!cabe(resto) && resto.length > 1) {
      let n = resto.length - 1;
      while (n > 1 && !cabe(resto.slice(0, n))) n--;
      linhas.push(resto.slice(0, n));
      resto = resto.slice(n);
    }
    atual = resto;
  }
  if (atual) linhas.push(atual);

  if (linhas.length <= maxLinhas) return linhas;
  const aparadas = linhas.slice(0, maxLinhas);
  let ultima = `${aparadas[maxLinhas - 1]}…`;
  while (ultima.length > 2 && !cabe(ultima)) ultima = `${ultima.slice(0, -2)}…`;
  aparadas[maxLinhas - 1] = ultima;
  return aparadas;
}

// ─── O texto de dentro de um bloco ───────────────────────────────────────

/**
 * Tamanhos do rótulo, do maior ao menor. Os de cima existem para o bloco ALTO: um
 * "Termodinâmica" de 90 minutos numa grade curta ocupa 90pt, e um rótulo de 8,5pt ali
 * é legível na tela e minúsculo no papel.
 */
const TAMANHOS_DO_ROTULO = [11, 9.5, 8.5, 7.5, 6.5, 5.5];
/** Abaixo disto o texto de um horário impresso deixa de ser lido sem esforço. */
const TAMANHO_LEGIVEL = 7.5;
const ALTURA_DA_LINHA = 1.2;

interface TextoDoBloco {
  tamanho: number;
  linhasDoRotulo: string[];
  linhaDaHora: string | null;
  tamanhoDaHora: number;
  espacamentoV: number;
}

/**
 * O que cabe num bloco de `altura` × `largura`.
 *
 * A escolha do tamanho tem TRÊS passadas, e a ordem é a decisão:
 *
 *   1. o MAIOR tamanho legível (≥ 7,5pt) em que o rótulo cabe INTEIRO — é o que faz o
 *      bloco alto ter letra grande;
 *   2. se nenhum comporta o rótulo inteiro, 7,5pt com reticências: mais texto, no menor
 *      tamanho que ainda se lê, vale mais que uma palavra em 11pt e o resto cortado;
 *   3. só então os tamanhos pequenos (6,5 e 5,5pt) — o bloco de 15 minutos numa grade
 *      longa, com 13pt de altura. E se nem 5,5pt couber, o bloco fica sem texto (a hora
 *      está no eixo; o nome, na planilha).
 *
 * Em todas, PRIMEIRO o rótulo (ao menos uma linha), DEPOIS a hora ("19:00–20:30"), e
 * só então mais linhas do rótulo.
 */
function textoDoBloco(
  bloco: BlocoDeEstudo,
  largura: number,
  altura: number,
  medir: Medir,
): TextoDoBloco | null {
  const espacamentoV = altura < 18 ? 1.5 : 3.5;
  const utilV = altura - espacamentoV * 2;

  const tentar = (tamanho: number, exigirInteiro: boolean): TextoDoBloco | null => {
    const linha = tamanho * ALTURA_DA_LINHA;
    if (utilV < linha) return null;

    const tamanhoDaHora = Math.max(5.5, tamanho - 1.5);
    const alturaDaHora = tamanhoDaHora * ALTURA_DA_LINHA;
    // A hora só entra se sobrar espaço DEPOIS de garantir a primeira linha do rótulo.
    const cabeAHora = utilV >= linha + alturaDaHora;
    const linhasDisponiveis = Math.max(1, Math.floor((utilV - (cabeAHora ? alturaDaHora : 0)) / linha));

    // "Inteiro" quer dizer sem reticências E sem palavra partida no meio: a 11pt,
    // "eletromagnetismo" não cabe numa coluna de 89pt e viraria "eletromagneti" / "smo".
    // Tamanho que parte palavra não conta como "cabe" — a passada seguinte tenta um menor.
    if (exigirInteiro && bloco.rotulo.split(/\s+/).some((p) => medir(p, tamanho, 700) > largura)) return null;
    const linhas = quebrar(bloco.rotulo, largura, tamanho, 700, medir, exigirInteiro ? 99 : linhasDisponiveis);
    if (exigirInteiro && linhas.length > linhasDisponiveis) return null;
    return {
      tamanho,
      linhasDoRotulo: linhas,
      linhaDaHora: cabeAHora ? `${bloco.horaInicio}–${fimDe(bloco)}` : null,
      tamanhoDaHora,
      espacamentoV,
    };
  };

  const legiveis = TAMANHOS_DO_ROTULO.filter((t) => t >= TAMANHO_LEGIVEL);
  const pequenos = TAMANHOS_DO_ROTULO.filter((t) => t < TAMANHO_LEGIVEL);

  for (const tamanho of legiveis) {
    const inteiro = tentar(tamanho, true);
    if (inteiro) return inteiro;
  }
  const cortado = tentar(TAMANHO_LEGIVEL, false);
  if (cortado) return cortado;
  for (const tamanho of pequenos) {
    const t = tentar(tamanho, false);
    if (t) return t;
  }
  return null;
}

// ─── Datas e nomes ───────────────────────────────────────────────────────

function dois(n: number): string {
  return String(n).padStart(2, '0');
}

/** "24/10/2026" — pela data LOCAL, e não por `toISOString` (que vira o dia às 21h). */
export function dataPorExtenso(data: Date): string {
  return `${dois(data.getDate())}/${dois(data.getMonth() + 1)}/${data.getFullYear()}`;
}

/**
 * "horario-de-estudos-benny-noite-2026-10-24.pdf". O nome do aluno entra no arquivo
 * para quem tem dois horários salvos no celular saber qual é qual, e o tema para o
 * claro e o escuro do mesmo dia não se sobrescreverem; o nome some se não houver.
 */
export function nomeDoArquivoDoHorario(
  nome: string | null | undefined,
  tema: TemaDaFolha,
  data: Date,
  extensao: string,
): string {
  const slug = (nome ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
    .slice(0, 40)
    .replace(/-+$/g, '');
  const dia = `${data.getFullYear()}-${dois(data.getMonth() + 1)}-${dois(data.getDate())}`;
  return `${['horario-de-estudos', slug, tema, dia].filter(Boolean).join('-')}.${extensao}`;
}

// ─── A folha ─────────────────────────────────────────────────────────────

export interface OpcoesDaFolha {
  blocos: BlocoDeEstudo[];
  nome?: string | null;
  geradoEm: Date;
  tema: TemaDaFolha;
  medir: Medir;
  /** largura ÷ altura da logo, ou `null` se ela não carregou — a folha sai sem ela. */
  proporcaoDaLogo: number | null;
}

/** A folha pronta para desenhar, ou `null` se não há bloco — não há o que exportar. */
export function montarFolha({
  blocos,
  nome,
  geradoEm,
  tema,
  medir,
  proporcaoDaLogo,
}: OpcoesDaFolha): Folha | null {
  if (blocos.length === 0) return null;

  const cor = PALETAS[tema];
  const { largura: L, altura: A } = PAGINA;
  const direita = L - MARGEM;
  const primitivas: Primitiva[] = [];

  /** Largura de um texto contando o espaço entre as letras. */
  const larguraDe = (t: string, tamanho: number, peso: Peso, espacamento = 0) =>
    medir(t, tamanho, peso) + espacamento * Math.max(0, t.length - 1);

  const texto = (
    t: Omit<Texto, 'tipo'> & { alinhar?: 'esquerda' | 'centro' | 'direita'; caixa?: number },
  ) => {
    const { alinhar = 'esquerda', caixa = 0, ...resto } = t;
    const w = larguraDe(t.texto, t.tamanho, t.peso, t.espacamento);
    const x = alinhar === 'direita' ? t.x - w : alinhar === 'centro' ? t.x + (caixa - w) / 2 : t.x;
    primitivas.push({ tipo: 'texto', ...resto, x });
  };

  /** A legenda do site (`.alu-olho`): caixa-alta, pequena, espaçada, em azul. */
  const legenda = (
    t: string,
    x: number,
    y: number,
    cor_: string,
    alinhar: 'esquerda' | 'direita' = 'esquerda',
  ) => texto({ x, y, texto: t.toUpperCase(), tamanho: 6.5, peso: 700, cor: cor_, espacamento: 1.1, alinhar });

  // ── Fundo: a cor da página e a grade quadrada do site ──
  primitivas.push({ tipo: 'retangulo', x: 0, y: 0, largura: L, altura: A, preenchimento: cor.fundo });
  for (let x = 0; x <= L; x += QUADRADO_DO_FUNDO) {
    primitivas.push({ tipo: 'linha', x1: x, y1: 0, x2: x, y2: A, cor: cor.grade, largura: 0.5 });
  }
  for (let y = 0; y <= A; y += QUADRADO_DO_FUNDO) {
    primitivas.push({ tipo: 'linha', x1: 0, y1: y, x2: L, y2: y, cor: cor.grade, largura: 0.5 });
  }

  // ── Cabeçalho: a marca, a legenda "Quando" e o título — como o cartão de Estudar ──
  const alturaDaLogo = 30;
  const larguraDaLogo = proporcaoDaLogo ? alturaDaLogo * proporcaoDaLogo : 0;
  if (proporcaoDaLogo) {
    primitivas.push({
      tipo: 'imagem', chave: 'logo', x: MARGEM, y: MARGEM, largura: larguraDaLogo, altura: alturaDaLogo, cor: cor.marca,
    });
  }
  const area = 'Área do estudante';
  legenda(area, MARGEM, MARGEM + alturaDaLogo + 10, cor.texto2);
  const largArea = larguraDe(area.toUpperCase(), 6.5, 700, 1.1);

  const xTitulo = MARGEM + Math.max(larguraDaLogo, largArea) + 30;
  legenda('Quando', xTitulo, 42, cor.dado);
  texto({ x: xTitulo, y: 64, texto: 'Horário de estudos', tamanho: 22, peso: 800, cor: cor.magnitude });
  const aparado = nome ? quebrar(nome, L - xTitulo - 230, 9, 500, medir, 1)[0] : '';
  if (aparado) texto({ x: xTitulo, y: 78, texto: aparado, tamanho: 9, peso: 500, cor: cor.texto2 });

  legenda('Semana', direita, 42, cor.dado, 'direita');
  texto({
    x: direita,
    y: 64,
    texto: duracaoPorExtenso(totalDeMinutos(blocos)),
    tamanho: 26,
    peso: 800,
    cor: cor.magnitude,
    alinhar: 'direita',
  });
  texto({ x: direita, y: 78, texto: 'planejadas', tamanho: 8, peso: 500, cor: cor.texto2, alinhar: 'direita' });

  // ── O cartão da grade: superfície com borda e raio, como todo cartão do site ──
  const borda = tema === 'dia' ? 1.4 : 1; // o site: 2px no dia, 1px na noite
  primitivas.push({
    tipo: 'retangulo',
    x: MARGEM,
    y: TOPO_DO_CARTAO,
    largura: L - MARGEM * 2,
    altura: BASE_DO_CARTAO - TOPO_DO_CARTAO,
    raio: 14,
    preenchimento: cor.superficie,
    traco: { cor: cor.borda, largura: borda },
  });

  const [inicioH, fimH] = faixaDeHoras(blocos);
  const yDias = TOPO_DO_CARTAO + ALTURA_DOS_DIAS;
  const yTopo = yDias + 10;
  const yBase = BASE_DO_CARTAO - 10;
  const xGrade = MARGEM + LARGURA_DAS_HORAS;
  const xFim = direita - RECUO_DO_CARTAO;
  const larguraDaColuna = (xFim - xGrade) / DIAS_DA_SEMANA.length;
  const pontosPorHora = (yBase - yTopo) / (fimH - inicioH);
  const yDoMinuto = (minutos: number) => yTopo + (minutos / 60 - inicioH) * pontosPorHora;

  DIAS_DA_SEMANA.forEach((dia, i) => {
    texto({
      x: xGrade + i * larguraDaColuna,
      caixa: larguraDaColuna,
      alinhar: 'centro',
      y: TOPO_DO_CARTAO + 16.5,
      texto: dia.secao,
      tamanho: 7.5,
      peso: 800,
      cor: cor.magnitude,
      espacamento: 1.2,
    });
  });
  primitivas.push({
    tipo: 'linha', x1: MARGEM + 1, y1: yDias, x2: direita - 1, y2: yDias, cor: cor.borda, largura: 0.8,
  });

  for (let h = inicioH; h <= fimH; h++) {
    const y = yTopo + (h - inicioH) * pontosPorHora;
    primitivas.push({ tipo: 'linha', x1: xGrade, y1: y, x2: xFim, y2: y, cor: cor.borda, largura: 0.6 });
    texto({
      x: xGrade - 7, y: y + 2.6, texto: `${h}h`, tamanho: 7, peso: 600, cor: cor.texto2, alinhar: 'direita',
    });
  }
  for (let i = 0; i <= DIAS_DA_SEMANA.length; i++) {
    const x = xGrade + i * larguraDaColuna;
    primitivas.push({ tipo: 'linha', x1: x, y1: yDias + 4, x2: x, y2: yBase, cor: cor.borda, largura: 0.5 });
  }

  // ── Os blocos: o cartão do site, com a borda em DADO (o papel de "o que está planejado") ──
  for (const bloco of blocos) {
    const inicio = minutosDe(bloco.horaInicio) ?? 0;
    const coluna = bloco.diaSemana - 1;
    // Folga de 0,75pt em cima e embaixo: dois blocos que se encostam continuam
    // sendo dois retângulos, e não uma mancha só.
    const x = xGrade + coluna * larguraDaColuna + 3;
    const y = yDoMinuto(inicio) + 0.75;
    const largura = larguraDaColuna - 6;
    const altura = Math.max(1, (bloco.duracaoMinutos / 60) * pontosPorHora - 1.5);

    primitivas.push({
      tipo: 'retangulo',
      x,
      y,
      largura,
      altura,
      raio: Math.min(5, altura / 2),
      // Sobre a superfície do cartão da grade, o bloco SOBE: branco no dia, a
      // `superficie-2` na noite. É o que o separa do fundo sem depender só da borda.
      preenchimento: tema === 'dia' ? cor.fundo : cor.superficie2,
      traco: { cor: cor.dado, largura: 1.2 },
    });

    const dentro = textoDoBloco(bloco, largura - 10, altura, medir);
    if (!dentro) continue;
    const recorte = { x: x + 1, y: y + 1, largura: largura - 2, altura: altura - 2 };
    let baseline = y + dentro.espacamentoV + dentro.tamanho * 0.92;
    for (const linha of dentro.linhasDoRotulo) {
      primitivas.push({
        tipo: 'texto', x: x + 5, y: baseline, texto: linha, tamanho: dentro.tamanho,
        peso: 700, cor: cor.magnitude, recorte,
      });
      baseline += dentro.tamanho * ALTURA_DA_LINHA;
    }
    if (dentro.linhaDaHora) {
      primitivas.push({
        tipo: 'texto', x: x + 5, y: baseline - dentro.tamanho * 0.92 + dentro.tamanhoDaHora * 0.92,
        texto: dentro.linhaDaHora, tamanho: dentro.tamanhoDaHora, peso: 600,
        // No dia o azul-DADO; na noite o registro mais claro, que lê melhor em corpo pequeno.
        cor: tema === 'dia' ? cor.dado : cor.dadoClaro, recorte,
      });
    }
  }

  // ── Rodapé ──
  const yRodape = A - MARGEM + 4;
  texto({ x: MARGEM, y: yRodape, texto: 'Colégio Ari de Sá', tamanho: 7, peso: 500, cor: cor.texto2 });
  texto({
    x: direita, y: yRodape, texto: `Gerado em ${dataPorExtenso(geradoEm)}`, tamanho: 7, peso: 500,
    cor: cor.texto2, alinhar: 'direita',
  });

  return { largura: L, altura: A, tema, primitivas };
}
