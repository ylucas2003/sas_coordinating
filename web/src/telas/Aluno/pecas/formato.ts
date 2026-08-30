// Formatação da área do aluno.
//
// `fmt`, `fmtDataCurta`, `fmtDataLonga` e `fmtDuracao` continuam vindo de
// `util/formatoAluno.ts` — reexportados, não reescritos. O que nasce aqui é o
// que a camada de jogo pede e não existia: milhar com ponto, percentual sem
// casa, dias até uma data, e o sinal explícito do delta.
//
// ⚠️ Número sempre com vírgula decimal. É português do Brasil em tudo, e a
// régua vale para rótulo, arquivo, variável e classe CSS.

export { fmt, fmtDataCurta, fmtDataLonga, fmtDuracao } from '../../../util/formatoAluno';

/** 2850 → "2.850". Milhar com ponto, como se lê em voz alta. */
export function fmtInteiro(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('pt-BR');
}

/** 0.41 → "41%". Sem casa decimal: a precisão que não existe não se mostra. */
export function fmtPercentual(fracao: number | null | undefined): string {
  if (fracao == null) return '—';
  return `${Math.round(fracao * 100)}%`;
}

/** +0.7 → "+0,7"; −0.2 → "−0,2". O sinal é sempre explícito, e o menos é o
 *  U+2212, não o hífen — no numeral tabular o hífen fica curto demais. */
export function fmtDelta(n: number | null | undefined, casas = 1): string {
  if (n == null) return '—';
  const texto = Math.abs(n).toFixed(casas).replace('.', ',');
  return n < 0 ? `−${texto}` : `+${texto}`;
}

/**
 * Dias inteiros de hoje até `iso`. Negativo quando a data já passou.
 *
 * Ambas as pontas são normalizadas para o meio-dia local antes da subtração:
 * sem isso, a diferença entre 23h e 1h do dia seguinte daria zero dia, e a
 * contagem regressiva pularia um número na virada da meia-noite.
 */
export function diasAte(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const alvo = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(alvo.getTime())) return null;
  const hoje = new Date();
  hoje.setHours(12, 0, 0, 0);
  return Math.round((alvo.getTime() - hoje.getTime()) / 86_400_000);
}

/** "faltam 12 dias" · "é amanhã" · "é hoje" · "faltou 1 dia". */
export function fmtContagem(dias: number | null): string {
  if (dias == null) return '—';
  if (dias < 0) return 'já passou';
  if (dias === 0) return 'é hoje';
  if (dias === 1) return 'é amanhã';
  return `faltam ${dias} dias`;
}

/**
 * Quanto do intervalo entre o simulado anterior e o próximo já passou, de 0 a 1.
 * É o que faz a contagem regressiva APERTAR (docs/24 §7.1, regra 3): discreta
 * quando faltam semanas, o elemento mais forte da tela na véspera.
 */
export function fracaoDoIntervalo(
  dataAnterior: string | null,
  dataProxima: string | null,
): number {
  const restam = diasAte(dataProxima);
  const desde = diasAte(dataAnterior);
  if (restam == null || desde == null) return 0;
  const total = restam - desde;
  if (total <= 0) return 1;
  return Math.min(1, Math.max(0, -desde / total));
}

/** "MAT", "FÍS" — o rótulo curto das barras contra o corte. */
const ABREVIACAO: Record<string, string> = {
  Matemática: 'MAT',
  Física: 'FÍS',
  Química: 'QUÍ',
  Português: 'POR',
  Inglês: 'ING',
  Redação: 'RED',
};

export function abreviarMateria(materia: string): string {
  return ABREVIACAO[materia] ?? materia.slice(0, 3).toUpperCase();
}

/**
 * As três matérias que a taxonomia do edital cobre.
 *
 * ⚠️ Português, Inglês e Redação ficaram de fora, e a decisão obriga a tela a
 * DIZER isso onde houver leitura por assunto (docs/24 §3.3). Um plano de
 * revisão que silenciosamente ignora Inglês é pior que nenhum plano, porque o
 * aluno conclui que está coberto — e o Inglês da Fase 1 do ITA é o único
 * eliminatório.
 */
export const MATERIAS_COM_TAXONOMIA = ['Matemática', 'Física', 'Química'] as const;

export const AVISO_DE_COBERTURA =
  'Cobre Matemática, Física e Química. Português, Inglês e Redação ainda não.';
