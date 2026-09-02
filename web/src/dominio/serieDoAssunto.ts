// A série anual de um assunto do edital, por vestibular — e a frase que a lê.
//
// É o que a ficha do assunto desenha e o que o ranking usa para dizer a
// tendência. Função pura, sem React e sem I/O, testada em `serieDoAssunto.test.ts`.
//
// A FRASE SAI DAQUI, E NUNCA DE LLM. Mesma razão de `leituraDeGrafico.ts`:
// ela sai dos MESMOS números que o gráfico desenha, então não tem como divergir
// dele; não custa token; e é testável. Devolve `null` quando não há o que dizer
// com honestidade — frase vazia é melhor que frase inventada.
//
// ─── As quatro armadilhas que este módulo existe para não cair ────────────
//
// 1. OS ZEROS NÃO ESTÃO NO PAYLOAD. `porAno` só traz o ano com ocorrência.
//    Plotar as chaves do dicionário comprime o tempo e some com o buraco — que
//    é justamente a informação. A série é preenchida contra `anos`.
//
// 2. AUSÊNCIA DE PROVA NÃO É ZERO. O acervo do IME começa em 1996 e o do ITA
//    em 2008 (migration 0031). A linha do ITA COMEÇA em 2008: desenhá-la em
//    zero antes disso AFIRMA que o assunto não caía no ITA, quando a verdade é
//    que não temos a prova. O domínio de cada série sai do `anos` da RESPOSTA
//    DELA — nunca de um ano cravado aqui, porque o acervo cresce.
//
// 3. CONTAGEM BRUTA NÃO COMPARA BANCAS. ITA e IME têm número de questões
//    diferente por ano, e o formato do ITA muda em 2019. O eixo padrão é
//    PERCENTUAL da prova daquela banca naquele ano, e o denominador é
//    `questoesPorAno` — que vem pronto do servidor porque somar os tópicos
//    superestima: questão mista soma nos dois de propósito (docs/22 §1.5).
//
// 4. UMA PROVA POR ANO DÁ SÉRIE RUIDOSA. A média móvel de três anos vem ligada
//    por padrão (decisão do usuário). O valor CRU continua em cada ponto: é ele
//    que o rótulo do ponto mostra, senão o número que o aluno lê ao tocar não é
//    o número que existe.

import type { EstatisticasBanco, RecorrenciaTopico, VestibularBanco } from '../tipos/banco';

export type EixoDaSerie = 'percentual' | 'contagem';

export interface PontoDaSerie {
  ano: number;
  /** Questões do tópico naquele ano. Sempre cru. */
  contagem: number;
  /** Questões da banca naquele ano — o denominador de "% da prova". */
  questoesNoAno: number;
  /** O valor do eixo antes de suavizar. É o que o rótulo do ponto mostra. */
  bruto: number;
  /** O valor plotado: igual a `bruto`, ou a média móvel quando suavizado. */
  valor: number;
}

export interface SerieDoAssunto {
  vestibular: VestibularBanco;
  eixo: EixoDaSerie;
  /** Do primeiro ao último ano COM ACERVO desta banca. Nunca antes disso. */
  pontos: PontoDaSerie[];
  /** Soma das ocorrências no domínio inteiro. */
  total: number;
}

export interface OpcoesDaSerie {
  eixo?: EixoDaSerie;
  suavizar?: boolean;
}

/** A janela das duas pontas que a frase compara. Cinco anos de cada lado. */
const ANOS_DA_JANELA = 5;

/**
 * Abaixo disto não há tendência a afirmar, só ruído: com quatro anos de acervo,
 * duas janelas de cinco se sobrepõem e a comparação não significa nada.
 */
const ANOS_MINIMOS_PARA_TENDENCIA = ANOS_DA_JANELA * 2;

/**
 * A série de um assunto numa banca.
 *
 * `resposta` tem de ser a de UM vestibular (`estatisticasBanco(materia, 'ITA')`):
 * é dela que sai o domínio de anos e o denominador. Passar a resposta agregada
 * das duas bancas produziria uma série com o eixo do ITA e o denominador dos
 * dois somados — errada, e sem nada na tela parecendo errado.
 *
 * Devolve `null` quando a resposta não tem ano nenhum: é "não há acervo desta
 * banca neste recorte", e a tela declara isso em palavras em vez de desenhar
 * uma linha reta em zero.
 */
export function serieDoAssunto(
  topico: RecorrenciaTopico | undefined,
  resposta: Pick<EstatisticasBanco, 'anos' | 'questoesPorAno'>,
  vestibular: VestibularBanco,
  { eixo = 'percentual', suavizar = true }: OpcoesDaSerie = {},
): SerieDoAssunto | null {
  const anos = [...resposta.anos].sort((a, b) => a - b);
  if (anos.length === 0) return null;

  // `topico` ausente é tópico do edital sem ocorrência nesta banca — série de
  // zeros, e não série vazia. "Não caiu em dezoito anos" é informação de estudo.
  const porAno = topico?.porAno ?? {};

  const brutos = anos.map((ano) => {
    const contagem = porAno[ano] ?? 0;
    const questoesNoAno = resposta.questoesPorAno[ano] ?? 0;
    // Denominador zero não deveria acontecer — `anos` sai das mesmas questões
    // que `questoesPorAno` —, mas dividir por ele daria Infinity na tela.
    const bruto =
      eixo === 'contagem' ? contagem : questoesNoAno > 0 ? (contagem / questoesNoAno) * 100 : 0;
    return { ano, contagem, questoesNoAno, bruto };
  });

  const suavizados = suavizar
    ? mediaMovel(brutos.map((p) => ({ ano: p.ano, valor: p.bruto })))
    : brutos.map((p) => p.bruto);

  return {
    vestibular,
    eixo,
    pontos: brutos.map((p, i) => ({ ...p, valor: suavizados[i] })),
    total: brutos.reduce((soma, p) => soma + p.contagem, 0),
  };
}

/**
 * Média móvel de três ANOS, centrada, com as pontas encurtadas.
 *
 * ⚠️ A janela é de anos, e não de posições no array — a diferença importa
 * porque o acervo tem BURACOS. O do IME pula 1997, 2000, 2001 e 2003; uma
 * janela de três posições sobre [1996, 1998, 1999] mediria um intervalo de
 * quatro anos e chamaria isso de "média de três anos". O ano ausente
 * simplesmente não entra na conta: não temos a prova, e inventá-la como zero é
 * a mesma mentira que a linha se parte para não contar.
 *
 * Encurtar as pontas em vez de repetir o valor da borda: repetir inventaria um
 * ano que não existe, e a linha ganharia uma inclinação que o dado não tem.
 */
function mediaMovel(pontos: { ano: number; valor: number }[]): number[] {
  return pontos.map((ponto) => {
    const vizinhos = pontos.filter((outro) => Math.abs(outro.ano - ponto.ano) <= 1);
    return vizinhos.reduce((soma, v) => soma + v.valor, 0) / vizinhos.length;
  });
}

export type Tendencia = 'subindo' | 'caindo' | 'estavel';

export interface LeituraDaTendencia {
  tendencia: Tendencia;
  /** Média do eixo nos anos recentes e nos anteriores, na mesma unidade. */
  recente: number;
  anterior: number;
}

/**
 * Compara as duas pontas da série: os cinco anos mais recentes contra os cinco
 * anteriores.
 *
 * `null` quando o acervo é curto demais para a comparação significar algo — e
 * também quando o assunto nunca caiu, porque "estável em zero" é uma frase
 * verdadeira e inútil que a tela já diz melhor com outras palavras.
 *
 * ⚠️ Compara os valores BRUTOS, nunca os suavizados: a média móvel já é uma
 * média, e comparar médias de médias esconde justamente a virada recente que a
 * pergunta quer enxergar.
 */
export function tendenciaDaSerie(serie: SerieDoAssunto | null): LeituraDaTendencia | null {
  if (!serie || serie.total === 0) return null;
  if (serie.pontos.length < ANOS_MINIMOS_PARA_TENDENCIA) return null;

  const media = (pontos: PontoDaSerie[]) =>
    pontos.reduce((soma, p) => soma + p.bruto, 0) / pontos.length;

  const recentes = serie.pontos.slice(-ANOS_DA_JANELA);
  const anteriores = serie.pontos.slice(-ANOS_DA_JANELA * 2, -ANOS_DA_JANELA);
  const recente = media(recentes);
  const anterior = media(anteriores);

  // Arredondado à casa que a tela mostra: uma diferença que o aluno não
  // consegue ver no número não pode virar uma seta que diz "subiu".
  const arredondar = (v: number) => Math.round(v * 10) / 10;
  const dr = arredondar(recente);
  const da = arredondar(anterior);

  return {
    tendencia: dr > da ? 'subindo' : dr < da ? 'caindo' : 'estavel',
    recente,
    anterior,
  };
}

function pct(v: number): string {
  return `${Math.round(v)}%`;
}

function inteiro(v: number): string {
  return String(Math.round(v));
}

/**
 * A frase de leitura da ficha do assunto.
 *
 * Recebe só as séries que CARREGARAM: série ausente por erro é declarada
 * separadamente na tela e não pode virar zero aqui — se ela entrasse, a frase
 * afirmaria que o assunto não cai naquela banca.
 *
 * Devolve `null` quando não há o que afirmar com honestidade:
 *   * nenhuma série carregou;
 *   * o assunto não apareceu em nenhuma prova do acervo — a tela tem um texto
 *     próprio para esse caso, que explica que o vazio é ausência de ocorrência
 *     e não falha de consulta.
 */
export function lerSerieDoAssunto(nome: string, series: (SerieDoAssunto | null)[]): string | null {
  const carregadas = series.filter((s): s is SerieDoAssunto => s !== null);
  if (carregadas.length === 0) return null;
  if (carregadas.every((s) => s.total === 0)) return null;

  // A frase fala da banca com mais ocorrências: é a que tem base para sustentar
  // a afirmação. Empate desempata pelo nome, para a frase não dançar entre
  // renderizações do mesmo dado.
  const principal = [...carregadas].sort(
    (a, b) => b.total - a.total || a.vestibular.localeCompare(b.vestibular),
  )[0];

  const unidade = principal.eixo === 'percentual' ? pct : inteiro;
  const sufixo = principal.eixo === 'percentual' ? ' das provas' : ' questões por prova';
  const leitura = tendenciaDaSerie(principal);

  const primeiro = principal.pontos[0]?.ano;
  const ultimo = principal.pontos[principal.pontos.length - 1]?.ano;

  if (!leitura) {
    // Acervo curto demais para tendência. O que ainda dá para dizer com
    // segurança é o tamanho: quantas questões, em quantos anos de prova.
    const anos = principal.pontos.length;
    return (
      `No ${principal.vestibular}, ${nome} aparece em ${principal.total} ` +
      `${principal.total === 1 ? 'questão' : 'questões'} do acervo, ` +
      `em ${anos} ${anos === 1 ? 'ano' : 'anos'} de prova (${primeiro}–${ultimo}).`
    );
  }

  const inicioAnterior = principal.pontos[principal.pontos.length - ANOS_DA_JANELA * 2].ano;
  const inicioRecente = principal.pontos[principal.pontos.length - ANOS_DA_JANELA].ano;

  if (leitura.tendencia === 'estavel') {
    return (
      `No ${principal.vestibular}, ${nome} fica perto de ` +
      `${unidade(leitura.recente)}${sufixo} desde ${inicioAnterior}.`
    );
  }

  const verbo = leitura.tendencia === 'subindo' ? 'subiu para' : 'caiu para';
  return (
    `No ${principal.vestibular}, ${nome} saía em ${unidade(leitura.anterior)}${sufixo} ` +
    `entre ${inicioAnterior} e ${inicioRecente - 1}, e ${verbo} ` +
    `${unidade(leitura.recente)} de ${inicioRecente} para cá.`
  );
}

/**
 * O rótulo do eixo em palavras, para o `aria-label` do SVG.
 *
 * Todo gráfico precisa de um: um `role="img"` sem rótulo é um retângulo mudo
 * para quem usa leitor de tela, e aqui o desenho é a informação inteira.
 */
export function rotuloDaSerie(nome: string, series: (SerieDoAssunto | null)[]): string {
  const carregadas = series.filter((s): s is SerieDoAssunto => s !== null);
  if (carregadas.length === 0) return `Incidência de ${nome} por ano — nenhuma série carregou.`;

  const eixo =
    carregadas[0].eixo === 'percentual' ? 'percentual da prova' : 'número de questões';
  const bancas = carregadas
    .map((s) => {
      const primeiro = s.pontos[0]?.ano;
      const ultimo = s.pontos[s.pontos.length - 1]?.ano;
      return `${s.vestibular}, ${s.total} ${s.total === 1 ? 'questão' : 'questões'} entre ${primeiro} e ${ultimo}`;
    })
    .join('; ');

  return `Incidência de ${nome} por ano, em ${eixo}. ${bancas}.`;
}
