// Datas: o app troca ISO (YYYY-MM-DD) com a API e exibe em pt-BR.

/** "2026-03-08" → "08/03/2026". */
export function fmtDataBR(iso: string | null | undefined): string {
  if (!iso) return '—';
  const [ano, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${ano}`;
}

/** Data local em ISO. `toISOString()` não serve: converte para UTC e vira o dia anterior à noite. */
export function isoDe(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function hojeISO(): string {
  return isoDe(new Date());
}
