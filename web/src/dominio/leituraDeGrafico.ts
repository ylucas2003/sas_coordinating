// A camada "leigo" dos gráficos: uma frase que diz o que o desenho mostra,
// para quem não lê histograma (docs/31 §P5).
//
// É código, e não LLM, de propósito. Três razões, nesta ordem:
//   1. sai dos MESMOS números que o gráfico desenha, então não tem como
//      divergir dele — um bullet gerado pode elogiar uma turma que caiu;
//   2. não custa token nem depende de OPENAI_API_KEY estar configurada;
//   3. é testável. A camada de insight, essa sim, é LLM — e vive em
//      `insight_ciclo`, gerada no backend.
//
// Toda função aqui é pura e devolve `null` quando não há o que dizer com
// honestidade. Frase vazia é melhor que frase inventada.

import type { RespostaHistograma } from '../tipos/dominio';

/** Formata na convenção do produto: uma casa, vírgula decimal. */
function nota(v: number): string {
  return v.toFixed(1).replace('.', ',');
}

function pct(parte: number, total: number): number {
  return Math.round((parte / total) * 100);
}

/**
 * A faixa do meio: onde está a metade central da turma (do 1º ao 3º quartil),
 * lida direto dos bins.
 *
 * A primeira versão procurava a MENOR faixa contígua que juntasse 50% da
 * massa. Dava respostas verdadeiras e inúteis: numa distribuição com dois
 * picos afastados, um dos picos sozinho fecha os 50% e a frase virava "metade
 * ficou entre 1,0 e 2,0" — escondendo justamente que a turma estava partida
 * ao meio. O intervalo interquartil não tem esse defeito: quando a turma se
 * espalha, ele se alarga, que é o que a frase precisa dizer.
 */
function faixaDoMeio(
  contagens: readonly number[],
  larguraBin: number,
): { de: number; ate: number } | null {
  const total = contagens.reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const binDoEnesimo = (k: number): number => {
    let acumulado = 0;
    for (let i = 0; i < contagens.length; i++) {
      acumulado += contagens[i];
      if (acumulado >= k) return i;
    }
    return contagens.length - 1;
  };

  const primeiro = binDoEnesimo(Math.ceil(total * 0.25));
  const terceiro = binDoEnesimo(Math.ceil(total * 0.75));
  return { de: primeiro * larguraBin, ate: (terceiro + 1) * larguraBin };
}

/**
 * Quantos ficaram abaixo do corte, contando pela massa dos bins.
 *
 * O bin ATRAVESSADO pelo corte é rateado, não descartado. Descartá-lo parecia
 * conservador — "não inflar o número de reprovados" — e funcionava enquanto
 * todo corte era 4,0 ou 5,0, múltiplos da largura de 0,5. A P1 acabou com
 * isso: `ita-f1` exige 5 de 12, que é 4,1667, e aí o bin [4,0 ; 4,5) sumia
 * inteiro. Resultado: "Ninguém ficou abaixo do corte" impresso ao lado de um
 * "88% aprovados" calculado sobre as notas exatas, com barra visível à
 * esquerda da tracejada no mesmo cartão.
 *
 * O rateio assume distribuição uniforme dentro do bin — que é a única coisa
 * que se pode assumir quando só se tem o histograma. Continua aproximação,
 * mas erra por pouco em vez de errar por um bin inteiro.
 */
function abaixoDoCorte(
  contagens: readonly number[],
  larguraBin: number,
  corte: number,
): number {
  let soma = 0;
  for (let i = 0; i < contagens.length; i++) {
    const inicio = i * larguraBin;
    const fim = inicio + larguraBin;
    if (fim <= corte) {
      soma += contagens[i];
    } else if (inicio < corte) {
      soma += contagens[i] * ((corte - inicio) / larguraBin);
    }
  }
  return soma;
}

export interface LeituraDeDistribuicao {
  frase: string;
  /** true quando não há massa suficiente para a frase significar algo. */
  poucosDados: boolean;
}

/**
 * A leitura de um histograma de notas, em português de quem não é estatístico.
 *
 * Ex.: "Metade da turma ficou entre 4,0 e 6,0. 31% ficaram abaixo do corte
 * (4,0), e a média (5,2) está acima dele."
 */
export function lerDistribuicao(entrada: {
  histograma: RespostaHistograma | null | undefined;
  media?: number | null;
  corte?: number | null;
  /** Grupo descrito, com preposição: "da turma", "dos presentes". */
  rotuloGrupo?: string;
}): LeituraDeDistribuicao | null {
  const h = entrada.histograma;
  if (!h?.contagens?.length || !h.largura_bin) return null;

  const total = h.contagens.reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  // Frase preposicionada inteira ("da turma", "dos alunos do ciclo"), e não
  // só o substantivo: quem chama sabe a concordância do próprio rótulo.
  const grupo = entrada.rotuloGrupo ?? 'da turma';
  const partes: string[] = [];

  // Com menos de 10 notas, "metade ficou entre X e Y" sugere um padrão que os
  // dados não sustentam. Diz o que dá: quantos são, e onde estão.
  if (total < 10) {
    partes.push(`São apenas ${total} nota${total === 1 ? '' : 's'} — pouco para falar em padrão.`);
  } else {
    const faixa = faixaDoMeio(h.contagens, h.largura_bin);
    if (faixa) {
      partes.push(
        `Metade ${grupo} ficou entre ${nota(faixa.de)} e ${nota(faixa.ate)}.`,
      );
    }
  }

  if (entrada.corte != null) {
    const abaixo = abaixoDoCorte(h.contagens, h.largura_bin, entrada.corte);
    const proporcao = pct(abaixo, total);
    // Os dois extremos do arredondamento precisam de frase própria. Num ciclo
    // de 319 alunos, 1 abaixo do corte dá 0,31% → arredonda para 0, e sairia
    // "0% ficaram abaixo" — exatamente o que o ramo "Ninguém" existe para
    // evitar, com uma barra visível à esquerda da linha. O simétrico afirmava
    // que a turma inteira ficou abaixo com um aluno acima.
    if (abaixo < 0.5) {
      partes.push(`Ninguém ficou abaixo do corte (${nota(entrada.corte)}).`);
    } else if (proporcao === 0) {
      partes.push(`Menos de 1% ficou abaixo do corte (${nota(entrada.corte)}).`);
    } else if (proporcao === 100 && abaixo < total) {
      partes.push(`Quase toda a turma ficou abaixo do corte (${nota(entrada.corte)}).`);
    } else {
      partes.push(
        `${proporcao}% ficaram abaixo do corte (${nota(entrada.corte)}).`,
      );
    }
    if (entrada.media != null) {
      const lado = entrada.media >= entrada.corte ? 'acima' : 'abaixo';
      partes.push(`A média (${nota(entrada.media)}) está ${lado} dele.`);
    }
  } else if (entrada.media != null) {
    partes.push(`A média é ${nota(entrada.media)}.`);
  }

  if (!partes.length) return null;
  return { frase: partes.join(' '), poucosDados: total < 10 };
}

/**
 * A leitura de uma série ao longo do tempo: de onde saiu, onde chegou, e se o
 * movimento é grande o bastante para merecer nome.
 *
 * O limiar de 0,3 ponto é o mesmo espírito do `SLOPE_MINIMO` do backend:
 * abaixo disso a diferença é ruído de calibração de prova, não aprendizado.
 */
export function lerEvolucao(
  valores: ReadonlyArray<number | null | undefined>,
  rotuloGrupo = 'a média',
): string | null {
  const notas = valores.filter((v): v is number => v != null && !Number.isNaN(v));
  if (notas.length < 2) return null;

  const primeira = notas[0];
  const ultima = notas[notas.length - 1];
  const delta = ultima - primeira;
  const quantos = `${notas.length} pontos`;

  if (Math.abs(delta) < 0.3) {
    return `${rotuloGrupo} ficou estável em torno de ${nota(ultima)} ao longo de ${quantos}.`;
  }

  const direcao = delta > 0 ? 'subiu' : 'caiu';
  const maior = Math.max(...notas);
  const menor = Math.min(...notas);
  const oscilou = maior - menor > Math.abs(delta) * 2;

  const base = `${rotuloGrupo} ${direcao} de ${nota(primeira)} para ${nota(ultima)} ao longo de ${quantos}`;
  return oscilou
    ? `${base}, mas com oscilação pelo caminho (de ${nota(menor)} a ${nota(maior)}).`
    : `${base}.`;
}


// ─── Leituras compostas ──────────────────────────────────────────────────
// As duas abaixo vivem aqui, e não na tela, porque têm ramificação de verdade
// (uma série ou várias; uma fase ou duas) — e ramificação sem teste é onde
// nasce a frase que contradiz o gráfico logo abaixo dela.

/** Forma mínima de uma série: só o que a frase precisa saber. */
export interface SerieLida {
  nome: string;
  notas: readonly number[];
}

/**
 * A leitura de um gráfico de várias linhas.
 *
 * Com uma linha, descreve o movimento dela. Com várias, descrever cada uma
 * daria um parágrafo — então aponta onde está o maior movimento para cima e
 * para baixo, que é o que se procura num gráfico de várias linhas.
 */
export function lerSeries(series: readonly SerieLida[]): string | null {
  const comPontos = series.filter((s) => s.notas.length >= 2);
  if (comPontos.length === 0) return null;
  if (comPontos.length === 1) return lerEvolucao(comPontos[0].notas, comPontos[0].nome);

  const variacao = (s: SerieLida) => s.notas[s.notas.length - 1] - s.notas[0];
  const ordenadas = [...comPontos].sort((a, b) => variacao(b) - variacao(a));
  const subiu = ordenadas[0];
  const caiu = ordenadas[ordenadas.length - 1];

  const partes = [`${comPontos.length} matérias no gráfico.`];
  if (variacao(subiu) >= 0.3) partes.push(lerEvolucao(subiu.notas, subiu.nome) ?? '');
  if (caiu !== subiu && variacao(caiu) <= -0.3) partes.push(lerEvolucao(caiu.notas, caiu.nome) ?? '');
  if (partes.length === 1) partes.push('Nenhuma se moveu o bastante para chamar de tendência.');
  return partes.filter(Boolean).join(' ');
}

/**
 * A leitura de uma matéria com Fase 1 e Fase 2 lado a lado.
 *
 * As duas fases são recortes do mesmo assunto, e quem lê quer saber se
 * melhorou de uma para a outra — não duas descrições soltas de distribuição.
 */
export function lerDuasFases(entrada: {
  fase1?: { histograma?: RespostaHistograma | null; media?: number | null } | null;
  fase2?: { histograma?: RespostaHistograma | null; media?: number | null } | null;
  corte?: number | null;
  deltaMedia?: number | null;
}): string | null {
  const partes: string[] = [];
  for (const [rotulo, bloco] of [['Fase 1', entrada.fase1], ['Fase 2', entrada.fase2]] as const) {
    const leitura = lerDistribuicao({
      histograma: bloco?.histograma,
      media: bloco?.media,
      corte: entrada.corte,
      rotuloGrupo: 'da turma',
    });
    if (leitura) partes.push(`${rotulo}: ${leitura.frase}`);
  }

  const delta = entrada.deltaMedia;
  if (delta != null && Math.abs(delta) >= 0.3) {
    const verbo = delta > 0 ? 'subiu' : 'caiu';
    partes.push(`Da Fase 1 para a Fase 2 a média ${verbo} ${nota(Math.abs(delta))}.`);
  }

  return partes.length ? partes.join(' ') : null;
}
