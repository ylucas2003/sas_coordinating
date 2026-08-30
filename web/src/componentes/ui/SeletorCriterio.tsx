import type { CriterioClassificacao } from '../../tipos/dominio';

/**
 * Qual régua de corte está em uso — a do colégio ou a de um edital.
 *
 * Saiu de dentro do Painel quando a ficha do ciclo passou a precisar dele: os
 * gráficos de lá desenhavam a linha de corte com um `4` escrito no TSX, e a
 * troca de régua tem que mover a tabela do Painel e o gráfico da ficha do
 * mesmo jeito (docs/31 §P1).
 *
 * A classe segue sendo `.painel-criterio` de propósito — é a pílula do casco,
 * já definida em `styles/painel.css`, e renomeá-la só para o componente ter
 * mudado de pasta trocaria CSS por nada.
 */
/** Valor sentinela do item "Criar régua…". Nunca é um slug de verdade. */
export const CRIAR_REGUA = '__criar__';

export function SeletorCriterio({
  criterios, valor, onEscolher, onCriar, rotulo = 'Critério de classificação',
}: {
  criterios: CriterioClassificacao[];
  valor: string;
  onEscolher: (slug: string) => void;
  /** Quando presente, o seletor oferece "Criar régua…" no fim da lista. */
  onCriar?: () => void;
  rotulo?: string;
}) {
  if (!criterios.length) return null;

  // Embutidas e criadas em grupos separados: uma régua do edital e uma régua
  // que alguém digitou na terça não têm o mesmo peso, e a lista precisa dizer
  // isso sem legenda.
  const embutidas = criterios.filter((c) => c.embutido !== false);
  const minhas = criterios.filter((c) => c.embutido === false);

  return (
    <select
      className="painel-criterio"
      aria-label={rotulo}
      value={valor}
      onChange={(ev) => {
        if (ev.target.value === CRIAR_REGUA) onCriar?.();
        else onEscolher(ev.target.value);
      }}
    >
      {embutidas.map((c) => (
        <option key={c.slug} value={c.slug}>{c.nome}</option>
      ))}

      {minhas.length > 0 && (
        <optgroup label="Minhas réguas">
          {minhas.map((c) => (
            <option key={c.slug} value={c.slug}>{c.nome}</option>
          ))}
        </optgroup>
      )}

      {onCriar && <option value={CRIAR_REGUA}>+ Criar régua…</option>}
    </select>
  );
}
