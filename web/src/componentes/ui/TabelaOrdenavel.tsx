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
