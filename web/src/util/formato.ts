// Formatação compartilhada pela UI. Convenção do design system (ver docs/03).

/** "7,2" — uma casa decimal, vírgula decimal. `null` vira travessão. */
export function fmtNota(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toFixed(1).replace('.', ',');
}

/** Delta com seta e sinal: "↑ 0,4". */
export function fmtDelta(d: number | null | undefined): string {
  if (d == null) return '';
  const seta = d > 0 ? '↑' : d < 0 ? '↓' : '→';
  return `${seta} ${Math.abs(d).toFixed(1).replace('.', ',')}`;
}

/** Remove acentos e caixa — para busca e comparação insensível. */
export function normalizar(s: string): string {
  return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}
