interface Props {
  rotulo: string;
  valor: string | number | null | undefined;
  /**
   * @deprecated Resíduo do semáforo. O desenho IGNORA este valor: o numeral de
   * KPI é sempre magnitude (R7 — uma escala semântica por tela). A prop
   * continua aceita para não quebrar chamador antigo e sai quando o último
   * deles parar de passá-la (hoje: `telas/Administracao/Contas.tsx`).
   */
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
export function Kpi({ rotulo, valor, sufixo = '' }: Props) {
  return (
    <div className="kpi">
      <div className="kpi__rotulo">{rotulo}</div>
      <div className="kpi__valor">
        {String(valor ?? '—')}
        {sufixo && <span className="kpi__sufixo">{sufixo}</span>}
      </div>
    </div>
  );
}
