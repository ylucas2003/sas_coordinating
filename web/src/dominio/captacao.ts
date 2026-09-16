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
