import type { ColunaTabela, Ordenacao } from './ordenacao';

interface Props<T> {
  colunas: ReadonlyArray<ColunaTabela<T>>;
  ordenacao: Ordenacao | null;
  onOrdenar: (chave: string) => void;
}

/** `<thead>` com cabeçalhos clicáveis e indicação de direção. */
export function TheadOrdenavel<T>({ colunas, ordenacao, onOrdenar }: Props<T>) {
  return (
    <thead>
      <tr>
        {colunas.map((c) => {
          const classes = ['tabela-th', c.classe].filter(Boolean).join(' ');

          if (c.ordenavel === false) {
            return (
              <th key={c.chave} className={classes}>
                {c.label}
              </th>
            );
          }

          const ativa = ordenacao?.chave === c.chave;
          const asc = ordenacao?.dir === 'asc';

          return (
            <th
              key={c.chave}
              className={`${classes}${ativa ? ' is-ordenada' : ''}`}
              aria-sort={ativa ? (asc ? 'ascending' : 'descending') : 'none'}
            >
              <button
                className="tabela-th__btn"
                onClick={() => onOrdenar(c.chave)}
                title={`Ordenar por ${c.label}`}
              >
                {c.label}
                <span className="tabela-th__seta">{ativa ? (asc ? '↑' : '↓') : '↕'}</span>
              </button>
            </th>
          );
        })}
      </tr>
    </thead>
  );
}

/**
 * A ordenação para o CELULAR.
 *
 * ⚠️ Isto existe porque `.data-table--cartoes` esconde o `<thead>` — e o
 * `<thead>` é onde mora o ÚNICO controle de ordenação destas tabelas. Sem esta
 * peça, virar cartão custa a ordenação inteira: em `/provas/simulados` a pessoa
 * perde "a prova mais recente primeiro", em `/provas/ciclos` perde a ordem por
 * período, e em `/banco` perde "o assunto com mais questões". A decisão do
 * sprint foi "trabalhar de verdade" no celular, e uma lista de 153 itens sem
 * ordenação não é trabalhar (revisão de 08/09).
 *
 * `<select>` e não uma faixa de pílulas: são até 14 critérios, e 14 pílulas
 * ocupariam mais altura do que os dois primeiros cartões somados. O seletor
 * nativo abre a roda do sistema, que é o gesto que o celular já ensina.
 *
 * Ele NÃO aparece no desktop — lá o `<thead>` faz o trabalho, e dois controles
 * para a mesma coisa na mesma tela é a fonte de engano que o docs/39 fechou na
 * régua de corte. Quem esconde é `.tabela-ordenar-celular` em `layout.css`.
 */
export function OrdenarNoCelular<T>({ colunas, ordenacao, onOrdenar }: Props<T>) {
  const ordenaveis = colunas.filter((c) => c.ordenavel !== false && c.label);
  if (ordenaveis.length === 0) return null;

  const atual = ordenacao?.chave ?? '';
  const asc = ordenacao?.dir === 'asc';
  // O rótulo da coluna em vigor, para o botão de direção dizer de QUE ordem
  // ele está falando — "crescente" sozinho não diz crescente em quê.
  const rotuloAtual = ordenaveis.find((c) => c.chave === atual)?.label ?? '';

  return (
    <div className="tabela-ordenar-celular">
      <label className="tabela-ordenar-celular__rotulo" htmlFor="ordenar-por">
        Ordenar por
      </label>
      <select
        id="ordenar-por"
        className="tabela-ordenar-celular__campo"
        value={atual}
        onChange={(e) => onOrdenar(e.target.value)}
      >
        {/* Sem coluna escolhida a lista está na ordem que o servidor mandou, e
            dizer isso é mais honesto do que fingir que há um critério. */}
        {!atual && <option value="">ordem padrão</option>}
        {ordenaveis.map((c) => (
          <option key={c.chave} value={c.chave}>{c.label}</option>
        ))}
      </select>

      {/* `onOrdenar` com a MESMA chave inverte a direção — é o contrato que o
          `<thead>` já usa ao ser clicado duas vezes. Reimplementar a inversão
          aqui daria duas regras para a mesma coisa. */}
      {atual && (
        <button
          type="button"
          className="tabela-ordenar-celular__dir"
          onClick={() => onOrdenar(atual)}
          aria-label={`${rotuloAtual}: ${asc ? 'crescente' : 'decrescente'} — tocar para inverter`}
        >
          {asc ? '↑' : '↓'}
        </button>
      )}
    </div>
  );
}
