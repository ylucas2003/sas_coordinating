interface Props {
  rotulo: string;
  valor: string | number | null | undefined;
  /** tone-verde | tone-ambar | tone-vermelho | tone-navy */
  tone?: string;
  sufixo?: string;
}

/**
 * KPI: o OLHO em cima, a MAGNITUDE embaixo.
 *
 * O rótulo é o olho — maiúscula pequena espaçada de 10px, aplicada pelo CSS
 * (`text-transform`), então passe o texto em sentence case normal. O valor é
 * o numeral em peso 800 com tracking negativo e tabular; ele é o herói do
 * cartão, e o que lhe dá hierarquia é o peso, não a cor.
 */
export function Kpi({ rotulo, valor, tone = '', sufixo = '' }: Props) {
  return (
    <div className="kpi">
      <div className="kpi__rotulo">{rotulo}</div>
      <div className={`kpi__valor ${tone}`}>
        {String(valor ?? '—')}
        {sufixo && <span className="kpi__sufixo">{sufixo}</span>}
      </div>
    </div>
  );
}
