// Formatação da área do aluno. Difere da coordenação em dois pontos: o número
// de casas é configurável e a data sai curta ("12 mar"), não em dd/mm/aaaa.

export function fmt(n: number | null | undefined, casas = 1): string {
  if (n == null) return '—';
  return Number(n).toFixed(casas).replace('.', ',');
}

/**
 * "2026-03-12" → "12 mar". O T12:00:00 evita o clássico off-by-one: sem hora,
 * o browser interpreta a data como UTC e mostra o dia anterior em fusos
 * negativos como o do Brasil.
 */
export function fmtDataCurta(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(`${iso}T12:00:00`)
    .toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
    .replace(/\./g, '');
}

/** "12 mar 2026". */
export function fmtDataLonga(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(`${iso}T12:00:00`)
    .toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })
    .replace(/\./g, '');
}

/** Segundos → "45 min" ou "1h30". */
export function fmtDuracao(segundos: number | null | undefined): string | null {
  if (segundos == null) return null;
  const min = Math.round(segundos / 60);
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)}h${String(min % 60).padStart(2, '0')}`;
}

/** Cor da linha de cada matéria no gráfico de evolução. */
const COR_MATERIA: Record<string, string> = {
  'Matemática': '#234C8B',
  'Física': '#4E79B5',
  'Química': '#3E9B73',
  'Português': '#C99A57',
  'Inglês': '#7B5EA7',
};

export function corMateria(materia: string): string {
  return COR_MATERIA[materia] ?? '#234C8B';
}

/** Fundo e texto do chip de matéria. */
export const CHIP_MATERIA: Record<string, { bg: string; fg: string }> = {
  'Matemática': { bg: '#E7EDF8', fg: '#16356A' },
  'Física': { bg: '#EAF0F9', fg: '#2E5490' },
  'Química': { bg: '#E2F2EA', fg: '#2C7355' },
  'Português': { bg: '#F7ECDA', fg: '#9A6F32' },
  'Inglês': { bg: '#F0EBF9', fg: '#5C3591' },
};

export const CHIP_VESTIBULAR: Record<string, { bg: string; fg: string }> = {
  ITA: { bg: '#E7EDF8', fg: '#16356A' },
  IME: { bg: '#EDE8F7', fg: '#4A2880' },
};
