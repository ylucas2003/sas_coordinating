interface Props {
  rotulo: string;
  valor: string | number | null | undefined;
  /** tone-verde | tone-ambar | tone-vermelho | tone-navy */
  tone?: string;
  sufixo?: string;
}

/** KPI compacto: rótulo em cima, valor grande embaixo. */
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
