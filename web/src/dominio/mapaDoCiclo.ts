// O MAPA da calibração — quais blocos, em que ordem, e quais crescem.
//
// A tela "A prova estava boa?" põe as doze aplicações do ciclo (seis matérias
// × duas fases) lado a lado na MESMA escala. Duas decisões dela são regra, não
// desenho, e por isso moram aqui com teste ao lado:
//
//   1. o PICO COMPARTILHADO — o denominador único das doze barras;
//   2. a ORDEM e o DESTAQUE — R6: sem cor semântica, quem entrega a prova
//      estranha é a ordenação, e o ordenador é visível e nomeado.
//
// Nada aqui calcula corte: o corte de cada matéria chega pronto no payload,
// resolvido pela régua no servidor (`criterios.corte_da_materia`). O que estas
// funções fazem com ele é subtração, que é a mesma conta da coluna "Distância"
// da tabela — não é reimplementar a régua, é ler o buraco que ela abriu.

import type {
  BlocoFase, RecorteMateria, RespostaHistograma, Simulado, StatsRecorte, TipoSimulado,
} from '../tipos/dominio';

/**
 * O que ordena o mapa. Os dois nomes são as duas perguntas que "a prova estava
 * boa?" pode significar, e elas não têm a mesma resposta:
 *
 *   `variacao`   esta aplicação saiu diferente do MESMO recorte do ciclo
 *                anterior — é a pergunta sobre o instrumento;
 *   `distancia`  esta aplicação está longe do que a régua exige — é a
 *                pergunta sobre o grupo.
 *
 * Uma matéria legitimamente difícil fica sempre abaixo do corte sem que a
 * prova tenha nada de errado; é por isso que `variacao` é o padrão quando há
 * ciclo anterior para comparar.
 */
export type OrdemDoMapa = 'variacao' | 'distancia';

/**
 * Meio ponto é a largura de um bin do histograma (`LARGURA_BIN` em
 * `api/app/stats/ciclo_estatisticas.py`). Abaixo disso a diferença não desloca
 * o desenho, e destacar um cartão por algo que o olho não vê no cartão é
 * prometer uma anomalia que não está lá.
 */
export const LIMIAR_FORA_DO_PADRAO = 0.5;

/**
 * Quantos blocos podem crescer.
 *
 * Destaque é escassez: se oito dos doze cartões ficam grandes, nenhum se
 * destaca e a grade só perde o alinhamento. Dois é o que a prancheta desenha
 * (`multiplos`, artboard Provas) e é também o que fecha a primeira linha da
 * grade de seis colunas.
 */
export const MAX_DESTAQUES = 2;

export type FaseCurta = 'F1' | 'F2';

export interface BlocoDoMapa {
  /** Estável entre renderizações e entre réguas: código da matéria + fase. */
  chave: string;
  materia: string;
  materiaCodigo: string;
  fase: FaseCurta;
  eliminatoria: boolean;
  /** O que a régua exige nesta matéria. `null` = a régua não exige nada aqui. */
  corte: number | null;
  n: number;
  media: number | null;
  mediana: number | null;
  histograma: RespostaHistograma | null;
  /**
   * Média desta aplicação menos a média do MESMO recorte no ciclo anterior.
   * `null` quando não há ciclo anterior — e `null` não é zero: zero é "igual",
   * `null` é "não sei".
   */
  variacao: number | null;
  /** Média menos corte. Negativo é abaixo. `null` quando falta um dos dois. */
  distancia: number | null;
  /** Cresce na grade — por tamanho e posição, nunca por cor. */
  destaque: boolean;
  /**
   * A prova que este bloco desenha, quando o ciclo tem UMA só da matéria
   * naquela fase. Duas provas viram um agregado, e não há ficha de agregado
   * para abrir — ver `provasNoBloco`.
   */
  provaId: string | null;
  provasNoBloco: number;
}

export interface Mapa {
  blocos: BlocoDoMapa[];
  /**
   * O maior bin de todos os blocos — o denominador único. Sem ele cada cartão
   * se normaliza pelo próprio máximo, a barra mais alta de Física fica do
   * tamanho da de Português, e morre a comparação que é o motivo da tela.
   * `null` quando não há contagem nenhuma.
   */
  pico: number | null;
  /** Se algum bloco tem com quem se comparar — habilita a ordem `variacao`. */
  temVariacao: boolean;
  /** Quantos blocos passaram do limiar na ordem em vigor. */
  foraDoPadrao: number;
}

/**
 * `delta` e `anterior` existem em CADA bloco de fase do payload de
 * `GET /ciclos/{id}/estatisticas` — quem os põe lá é o `_resumir` do
 * `ciclo_estatisticas.py`, que compara o recorte com o mesmo recorte do ciclo
 * anterior. `tipos/dominio.ts` ainda não os declara.
 *
 * A leitura fica aqui, num lugar só e nomeado, em vez de espalhar um `as` pela
 * tela: quando o tipo ganhar os campos, some este bloco e nada mais muda.
 */
interface BlocoComComparacao extends BlocoFase {
  delta?: { media?: number | null } | null;
  anterior?: { stats?: StatsRecorte | null } | null;
}

const FASES: ReadonlyArray<{ curta: FaseCurta; campo: 'fase1' | 'fase2'; tipo: TipoSimulado }> = [
  { curta: 'F1', campo: 'fase1', tipo: 'fase_1' },
  { curta: 'F2', campo: 'fase2', tipo: 'fase_2' },
];

/**
 * As provas do ciclo que este bloco de fato agrega.
 *
 * O recorte espelha o do servidor (`_carregar_simulados`): prova anulada e
 * prova fora das estatísticas não entram no agregado. Um atalho para uma prova
 * que não está no desenho abriria uma distribuição diferente da que o cartão
 * mostra — e ninguém desconfiaria, porque as duas são histogramas da mesma
 * matéria.
 */
function provasDoBloco(
  provas: readonly Simulado[],
  materiaCodigo: string,
  tipo: TipoSimulado,
): Simulado[] {
  return provas.filter(
    (p) =>
      p.materia?.codigo === materiaCodigo &&
      p.tipo === tipo &&
      !p.anulado &&
      p.notaConfiavel,
  );
}

function blocoDaFase(
  recorte: RecorteMateria,
  fase: (typeof FASES)[number],
  provas: readonly Simulado[],
): BlocoDoMapa | null {
  const bruto = recorte[fase.campo] as BlocoComComparacao | null;
  if (!bruto || bruto.stats.n === 0) return null;

  const corte = recorte.corte ?? null;
  const media = bruto.stats.media;
  const candidatas = provasDoBloco(provas, recorte.materia.codigo, fase.tipo);

  return {
    chave: `${recorte.materia.codigo}-${fase.curta}`,
    materia: recorte.materia.nome,
    materiaCodigo: recorte.materia.codigo,
    fase: fase.curta,
    eliminatoria: !!recorte.eliminatoria,
    corte,
    n: bruto.stats.n,
    media,
    mediana: bruto.stats.mediana,
    histograma: bruto.histograma,
    variacao: bruto.delta?.media ?? null,
    distancia: media != null && corte != null ? Number((media - corte).toFixed(2)) : null,
    destaque: false,
    provaId: candidatas.length === 1 ? candidatas[0].id : null,
    provasNoBloco: candidatas.length,
  };
}

function grandezaDaOrdem(bloco: BlocoDoMapa, ordem: OrdemDoMapa): number | null {
  return ordem === 'variacao' ? bloco.variacao : bloco.distancia;
}

/**
 * Monta os blocos, ordena e marca o destaque.
 *
 * A ordem é sempre PIOR PRIMEIRO, e o bloco sem a grandeza em vigor vai para o
 * fim — não para o começo: "não sei" nunca deve ocupar o lugar de "está ruim".
 * O desempate é alfabético por matéria e depois F1 antes de F2, para a grade
 * não embaralhar sozinha quando dois blocos empatam.
 */
export function montarMapa({
  recortes,
  provas = [],
  ordem,
}: {
  recortes: readonly RecorteMateria[];
  provas?: readonly Simulado[];
  ordem: OrdemDoMapa;
}): Mapa {
  const blocos: BlocoDoMapa[] = [];
  for (const recorte of recortes) {
    for (const fase of FASES) {
      const bloco = blocoDaFase(recorte, fase, provas);
      if (bloco) blocos.push(bloco);
    }
  }

  blocos.sort((a, b) => {
    const va = grandezaDaOrdem(a, ordem);
    const vb = grandezaDaOrdem(b, ordem);
    if (va == null && vb == null) return desempate(a, b);
    if (va == null) return 1;
    if (vb == null) return -1;
    if (va !== vb) return va - vb;
    return desempate(a, b);
  });

  let destacados = 0;
  let foraDoPadrao = 0;
  for (const bloco of blocos) {
    const valor = grandezaDaOrdem(bloco, ordem);
    if (valor == null || valor > -LIMIAR_FORA_DO_PADRAO) continue;
    foraDoPadrao += 1;
    if (destacados < MAX_DESTAQUES) {
      bloco.destaque = true;
      destacados += 1;
    }
  }

  const contagens = blocos.flatMap((b) => b.histograma?.contagens ?? []);
  const pico = contagens.length ? Math.max(...contagens) : null;

  return {
    blocos,
    pico: pico && pico > 0 ? pico : null,
    temVariacao: blocos.some((b) => b.variacao != null),
    foraDoPadrao,
  };
}

function desempate(a: BlocoDoMapa, b: BlocoDoMapa): number {
  return a.materia.localeCompare(b.materia, 'pt-BR') || a.fase.localeCompare(b.fase);
}

/** "1,3" com vírgula — o formato de nota do produto. */
function abs1(valor: number): string {
  return Math.abs(valor).toFixed(1).replace('.', ',');
}

/**
 * O número com sinal, como a prancheta escreve: "−1,3", "+0,4".
 *
 * O sinal é o MENOS de verdade (U+2212), não o hífen: no tabular-nums o hífen
 * tem largura de hífen e a coluna de números desalinha.
 */
export function comSinal(valor: number): string {
  if (valor > 0) return `+${abs1(valor)}`;
  if (valor < 0) return `−${abs1(valor)}`;
  return '0,0';
}

/**
 * A linha de baixo do cartão: o que o ordenador em vigor mede ali, em
 * palavras.
 *
 * Ela troca com o ordenador de propósito — o cartão relata a grandeza pela
 * qual a grade está ordenada, e não uma segunda grandeza que ninguém pediu.
 * Sem isso o coordenador lê "no padrão" num cartão que está no topo da lista.
 */
export function fraseDoBloco(
  bloco: BlocoDoMapa,
  ordem: OrdemDoMapa,
  nomeDoCicloAnterior: string | null,
): string {
  const anterior = nomeDoCicloAnterior ?? 'o ciclo anterior';

  if (ordem === 'variacao') {
    if (bloco.variacao == null) return `sem ${anterior} para comparar`;
    if (Math.abs(bloco.variacao) < LIMIAR_FORA_DO_PADRAO) return `no padrão de ${anterior}`;
    return `${comSinal(bloco.variacao)} vs ${anterior}`;
  }

  if (bloco.distancia == null) return 'a régua não exige nota nesta matéria';
  if (bloco.distancia === 0) return 'exatamente no corte';
  return bloco.distancia < 0
    ? `${abs1(bloco.distancia)} abaixo do corte`
    : `${abs1(bloco.distancia)} acima do corte`;
}

/** O nome do ordenador, para a faixa que o declara (R6). */
export function nomeDaOrdem(ordem: OrdemDoMapa, nomeDoCicloAnterior: string | null): string {
  return ordem === 'variacao'
    ? `variação contra ${nomeDoCicloAnterior ?? 'o ciclo anterior'}, pior primeiro`
    : 'distância do corte, pior primeiro';
}
