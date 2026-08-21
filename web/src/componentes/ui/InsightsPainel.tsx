interface Props {
  /**
   * - lista com itens → renderiza
   * - lista vazia → estado "indisponível" (LLM não configurado, ou erro)
   * - `null` → esqueleto de carregamento
   */
  bullets: string[] | null;
  titulo?: string;
  legenda?: string;
}

/** Insights gerados por LLM — leitura coordenacional do recorte. */
export function InsightsPainel({
  bullets,
  titulo = 'Leitura do coordenador',
  legenda = 'Geradas automaticamente a partir das estatísticas deste recorte.',
}: Props) {
  if (bullets == null) {
    return (
      <div className="insights-painel insights-painel--loading">
        <div className="insights-painel__header">
          <h3 className="insights-painel__titulo">{titulo}</h3>
        </div>
        <div className="insights-painel__skeleton">
          <div className="insights-painel__skeleton-linha" />
          <div className="insights-painel__skeleton-linha" />
          <div className="insights-painel__skeleton-linha" />
        </div>
      </div>
    );
  }

  if (!Array.isArray(bullets) || bullets.length === 0) {
    return (
      <div className="insights-painel insights-painel--vazio">
        <div className="insights-painel__header">
          <h3 className="insights-painel__titulo">{titulo}</h3>
        </div>
        <p className="insights-painel__indisponivel">
          Análise textual indisponível para este recorte. As estatísticas acima já contêm
          todos os números relevantes.
        </p>
      </div>
    );
  }

  return (
    <div className="insights-painel">
      <div className="insights-painel__header">
        <h3 className="insights-painel__titulo">{titulo}</h3>
        <p className="insights-painel__legenda">{legenda}</p>
      </div>
      <ul className="insights-painel__bullets">
        {bullets.map((b, i) => (
          <li key={i} className="insights-painel__bullet">{b}</li>
        ))}
      </ul>
    </div>
  );
}
