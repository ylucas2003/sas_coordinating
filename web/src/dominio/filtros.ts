// O resumo do que está ativo numa faixa de filtros — lógica pura.
//
// Existe por causa de uma regra que a `BarraFiltros` não pode quebrar: quando
// a faixa colapsa, **nenhum filtro em vigor pode ficar invisível**. Um recorte
// que o usuário não enxerga é um recorte que ele não sabe desmarcar, e a
// tabela abaixo passa a mentir em silêncio. O resumo é o que paga o colapso.
//
// A junção mora aqui, e não no componente, porque é regra com casos (zero, um,
// muitos; plural; ordem) — e regra com casos é o que `src/dominio/` guarda,
// com teste ao lado.

/** Um grupo, do ponto de vista do resumo: o que ele tem de ativo, se tem. */
export interface GrupoResumivel {
  chave: string;
  resumo?: string | null;
}

/**
 * `Ciclo 4 · ITA · 2026 · 2 turmas` — na ordem em que os grupos aparecem na
 * faixa, para o resumo se ler como a faixa se lia.
 *
 * Devolve string vazia quando nada está ativo; quem chama decide o que dizer
 * nesse caso (a faixa diz "nenhum filtro ativo", que é informação, não vazio).
 */
export function resumirFiltros(grupos: readonly GrupoResumivel[]): string {
  return grupos
    .map((g) => g.resumo)
    .filter((r): r is string => typeof r === 'string' && r.trim() !== '')
    .join(' · ');
}

/**
 * O resumo de um grupo de seleção múltipla.
 *
 * Com um item selecionado o rótulo dele é mais útil que a contagem — "Sobral"
 * diz mais que "1 sede". A partir de dois, a contagem é mais curta e mais
 * legível que a lista inteira, que é justamente o que não cabia na linha.
 */
export function resumirSelecao<V>(
  selecionados: ReadonlySet<V>,
  opcoes: ReadonlyArray<{ valor: V; label: string }>,
  singular: string,
  plural: string,
): string | null {
  if (selecionados.size === 0) return null;
  // Tudo marcado não é recorte: é o estado neutro, e anunciá-lo gastaria a
  // linha do resumo para dizer que não há nada a dizer.
  if (opcoes.length > 0 && selecionados.size === opcoes.length) return null;
  if (selecionados.size === 1) {
    const unico = opcoes.find((o) => selecionados.has(o.valor));
    if (unico) return unico.label;
  }
  return `${selecionados.size} ${selecionados.size === 1 ? singular : plural}`;
}

/** O resumo de um grupo de seleção única. */
export function resumirUnica<V>(
  selecionado: V | null | undefined,
  opcoes: ReadonlyArray<{ valor: V; label: string }>,
): string | null {
  if (selecionado == null) return null;
  return opcoes.find((o) => o.valor === selecionado)?.label ?? null;
}

/** O resumo de um campo de texto — entre aspas, para não virar rótulo. */
export function resumirTexto(valor: string, prefixo = ''): string | null {
  const limpo = valor.trim();
  if (!limpo) return null;
  return `${prefixo}“${limpo}”`;
}

/** O resumo de um intervalo de datas. Extremo vazio = aberto daquele lado. */
export function resumirPeriodo(
  inicio: string | null,
  fim: string | null,
  formatar: (iso: string) => string = (iso) => iso,
): string | null {
  if (!inicio && !fim) return null;
  if (inicio && fim) return `${formatar(inicio)} → ${formatar(fim)}`;
  if (inicio) return `desde ${formatar(inicio)}`;
  return `até ${formatar(fim as string)}`;
}
