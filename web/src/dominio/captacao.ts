import type { Evidencia, Faixa, Publico } from '../tipos/captacao';

// Regra de negócio da captação externa (docs/41 §2 e §3): a série que um
// candidato deve estar cursando HOJE, calculada na leitura a partir da série
// de referência da conquista mais recente — nunca guardada, porque um número
// gravado envelheceria sozinho a cada 1º de janeiro (a própria razão de
// `candidato_externo.ano_referencia_serie` existir, ver a migration 0056).

export interface FaixaDeSerie {
  min: number;
  max: number;
}

interface ReferenciaDeSerie {
  serie_referencia_min: number | null;
  serie_referencia_max: number | null;
  ano_referencia_serie: number | null;
}

/** 12 = 3º médio, o teto da educação básica que a régua da casa cobre. */
const TETO_EDUCACAO_BASICA = 12;

/**
 * A faixa de série estimada para HOJE, deslocando a faixa de referência pelos
 * anos que passaram desde a conquista. `anoAtual` é parâmetro, e não
 * `new Date().getFullYear()` interno, pra a função continuar pura e testável
 * sem depender do relógio da máquina.
 */
export function serieEstimadaHoje(
  candidato: ReferenciaDeSerie,
  anoAtual: number,
): FaixaDeSerie | null {
  const { serie_referencia_min: min, serie_referencia_max: max, ano_referencia_serie: ano } = candidato;
  if (min == null || max == null || ano == null) return null;
  const decorridos = anoAtual - ano;
  return { min: min + decorridos, max: max + decorridos };
}

const NOME_DA_SERIE: Record<number, string> = {
  6: '6º ano', 7: '7º ano', 8: '8º ano', 9: '9º ano',
  10: '1º médio', 11: '2º médio', 12: '3º médio',
};

/**
 * "8º–9º ano", "1º médio", ou o aviso de que a janela do docs/41 §2 já não
 * cobre esta pessoa — é o "lead frio" que a decisão de recorte temporal
 * previu, em vez de simplesmente inventar um "13º ano" sem sentido.
 */
export function rotuloDaSerie(faixa: FaixaDeSerie | null): string | null {
  if (!faixa) return null;
  if (faixa.min > TETO_EDUCACAO_BASICA) return 'já deve ter saído da educação básica';
  const min = Math.min(faixa.min, TETO_EDUCACAO_BASICA);
  const max = Math.min(faixa.max, TETO_EDUCACAO_BASICA);
  const rotuloMin = NOME_DA_SERIE[min] ?? `${min}º ano`;
  if (min === max) return rotuloMin;
  return `${rotuloMin} – ${NOME_DA_SERIE[max] ?? `${max}º ano`}`;
}

/** Vocabulário livre de `conquista_externa.notas_por_materia` (cada prova usa
 * o próprio) — chave compartilhada entre `CaptacaoModalConquista.tsx` e
 * `CaptacaoConquistas.tsx`, pra não divergir o rótulo de uma mesma chave. */
export const ROTULO_MATERIA: Record<string, string> = {
  mat: 'Matemática',
  fis: 'Física',
  qui: 'Química',
  quim: 'Química',
  port: 'Português',
  por: 'Português',
  ing: 'Inglês',
  ing_obj: 'Inglês (objetiva)',
  ing_disc: 'Inglês (discursiva)',
  red: 'Redação',
  redacao: 'Redação',
  mo: 'Média objetiva',
  media: 'Média',
  media_1fase: 'Média — 1ª fase',
  media_2fase: 'Média — 2ª fase',
  classificacao: 'Classificação',
  total: 'Total',
};

// ─── Busca por conquista — o caminho inverso (docs/41 §20) ─────────────────

/** Rótulo de cada faixa (0068). `classificado_final` é "passou em tudo, sem
 * vaga confirmada" — excedente do IME, reserva da EFOMM/Escola Naval. */
export const ROTULO_FAIXA: Record<Faixa, string> = {
  ouro: 'Ouro',
  prata: 'Prata',
  bronze: 'Bronze',
  mencao: 'Menção honrosa',
  finalista: 'Finalista',
  aprovado: 'Aprovado',
  classificado_final: 'Classificado sem vaga',
  passou_de_fase: 'Passou de fase',
  participou: 'Participou',
  ausente: 'Ausente',
};

/** Que faixas cada categoria de prova produz — a régua de
 * `_captacao_comum.py`: olimpíada só dá medalha/menção/finalista, vestibular
 * só dá a escada de aprovação. */
const FAIXAS_POR_CATEGORIA: Record<string, readonly Faixa[]> = {
  olimpiada: ['ouro', 'prata', 'bronze', 'mencao', 'finalista'],
  vestibular: ['aprovado', 'classificado_final', 'passou_de_fase', 'participou', 'ausente'],
};

const TODAS_AS_FAIXAS = Object.keys(ROTULO_FAIXA) as Faixa[];

/**
 * As faixas que fazem sentido oferecer dado o recorte de provas: sem prova
 * escolhida, todas; com provas escolhidas, só as das categorias delas — pedir
 * "Ouro" no ITA não traria ninguém, e a pílula só confundiria. Categoria que
 * esta versão não conhece libera tudo, em vez de esconder filtro.
 */
export function faixasOferecidas(
  provasEscolhidas: readonly string[],
  provas: ReadonlyArray<{ nome: string; categoria: string }>,
): Faixa[] {
  if (!provasEscolhidas.length) return TODAS_AS_FAIXAS;
  const categorias = new Set(
    provas.filter((p) => provasEscolhidas.includes(p.nome)).map((p) => p.categoria),
  );
  if ([...categorias].some((c) => !(c in FAIXAS_POR_CATEGORIA))) return TODAS_AS_FAIXAS;
  return TODAS_AS_FAIXAS.filter((f) =>
    [...categorias].some((c) => FAIXAS_POR_CATEGORIA[c].includes(f)),
  );
}

export const ROTULO_PUBLICO: Record<Publico, string> = {
  fundamental: 'Fundamental 2',
  medio: 'Médio',
  pre_vestibular: 'Pré-vestibular',
};

/** "Ouro · OBMEP 2025 · Nível 1" — a linha que diz por que o nome entrou. O
 * texto cru da fonte (`resultado`) fica pro título/ficha; aqui vai a faixa,
 * que é o que o filtro escolheu. Vestibular não tem nível. */
export function rotuloEvidencia(e: Evidencia): string {
  return [ROTULO_FAIXA[e.faixa] ?? e.resultado, `${e.prova} ${e.ano}`, e.nivel]
    .filter(Boolean)
    .join(' · ');
}
