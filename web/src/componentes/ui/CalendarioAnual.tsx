import { isoDe } from '../../util/data';

const NOMES_MES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

// Semana começa na segunda-feira (convenção BR).
const DIAS_SEMANA = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'];

interface Props {
  datasComSimulado: ReadonlySet<string>;
  datasSelecionadas: ReadonlySet<string>;
  onToggleData: (iso: string) => void;
  /** Default: deduzido das datas. */
  ano?: number;
}

/** Ano mais frequente nas datas dadas. Empate ou vazio ⇒ ano atual. */
function deduzirAno(datas: ReadonlySet<string>): number {
  if (!datas.size) return new Date().getFullYear();
  const contagem = new Map<number, number>();
  for (const iso of datas) {
    const ano = Number(iso.slice(0, 4));
    contagem.set(ano, (contagem.get(ano) ?? 0) + 1);
  }
  return [...contagem.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

/** Calendário anual em grid de 12 mini-meses; clicar num dia com prova filtra. */
export function CalendarioAnual({ datasComSimulado, datasSelecionadas, onToggleData, ano }: Props) {
  const anoAlvo = ano ?? deduzirAno(datasComSimulado);
  const hoje = isoDe(new Date());

  return (
    <div className="calendario">
      <div className="calendario__cabecalho">
        <div className="calendario__titulo">{`Calendário · ${anoAlvo}`}</div>
        <div className="calendario__resumo">
          {`${datasComSimulado.size} dia(s) com simulado · ${datasSelecionadas.size} selecionada(s)`}
        </div>
      </div>
      <div className="calendario__grid">
        {NOMES_MES.map((_, mesIdx) => (
          <Mes
            key={mesIdx}
            mesIdx={mesIdx}
            ano={anoAlvo}
            hoje={hoje}
            comSimulado={datasComSimulado}
            selecionadas={datasSelecionadas}
            onToggle={onToggleData}
          />
        ))}
      </div>
    </div>
  );
}

function Mes({
  mesIdx, ano, hoje, comSimulado, selecionadas, onToggle,
}: {
  mesIdx: number;
  ano: number;
  hoje: string;
  comSimulado: ReadonlySet<string>;
  selecionadas: ReadonlySet<string>;
  onToggle: (iso: string) => void;
}) {
  // Posição do dia 1 (0=domingo … 6=sábado), convertida para base segunda=0.
  const offsetSegunda = (new Date(ano, mesIdx, 1).getDay() + 6) % 7;
  const diasNoMes = new Date(ano, mesIdx + 1, 0).getDate();

  const vazios = Array.from({ length: offsetSegunda }, (_, i) => (
    <div key={`vazio-${i}`} className="calendario__dia calendario__dia--vazio" />
  ));

  const dias = Array.from({ length: diasNoMes }, (_, i) => {
    const dia = i + 1;
    const iso = `${ano}-${String(mesIdx + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
    const temSimulado = comSimulado.has(iso);
    const selecionada = selecionadas.has(iso);

    const classes = [
      'calendario__dia',
      temSimulado && 'calendario__dia--com-simulado',
      selecionada && 'is-selecionada',
      iso === hoje && 'is-hoje',
    ].filter(Boolean).join(' ');

    return (
      <div
        key={iso}
        className={classes}
        title={temSimulado ? `${iso} · ${selecionada ? 'selecionada' : 'clique pra filtrar'}` : iso}
        onClick={temSimulado ? () => onToggle(iso) : undefined}
      >
        {dia}
      </div>
    );
  });

  return (
    <div className="calendario__mes">
      <div className="calendario__mes-titulo">{NOMES_MES[mesIdx]}</div>
      <div className="calendario__semanas">
        {DIAS_SEMANA.map((d, i) => (
          <div key={i} className="calendario__dia-semana">{d}</div>
        ))}
      </div>
      <div className="calendario__semanas">
        {vazios}
        {dias}
      </div>
    </div>
  );
}
