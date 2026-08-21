import { useId } from 'react';
import type { ReactNode } from 'react';

// Gráficos da área do aluno. Linguagem visual própria (mais "produto", menos
// "planilha") do que a da coordenação — daí não reusarem os componentes de
// `componentes/ui/`.

/** Ícone de traço único, no estilo Feather usado na área do aluno. */
export function Icone({
  d, tamanho = 18, cor = 'currentColor', espessura = 1.8,
}: {
  d: string;
  tamanho?: number;
  cor?: string;
  espessura?: number;
}) {
  return (
    <svg
      width={tamanho} height={tamanho} viewBox="0 0 24 24"
      fill="none" stroke={cor} strokeWidth={espessura}
      strokeLinecap="round" strokeLinejoin="round"
      style={{ display: 'block', flexShrink: 0 }}
    >
      <path d={d} />
    </svg>
  );
}

/** Anel de progresso com conteúdo livre no centro. */
export function Anel({
  pct, tamanho = 84, espessura = 8, cor = '#E6B94E',
  trilha = 'rgba(255,255,255,0.18)', children,
}: {
  pct: number;
  tamanho?: number;
  espessura?: number;
  cor?: string;
  trilha?: string;
  children?: ReactNode;
}) {
  const r = tamanho / 2 - espessura / 2;
  const circunferencia = 2 * Math.PI * r;
  const preenchido = circunferencia * Math.min(1, Math.max(0, pct));

  return (
    <div className="alu-ring" style={{ width: tamanho, height: tamanho, flexShrink: 0 }}>
      <svg width={tamanho} height={tamanho} style={{ display: 'block', transform: 'rotate(-90deg)' }}>
        <circle cx={tamanho / 2} cy={tamanho / 2} r={r} fill="none" stroke={trilha} strokeWidth={espessura} />
        <circle
          cx={tamanho / 2} cy={tamanho / 2} r={r}
          fill="none" stroke={cor} strokeWidth={espessura}
          strokeDasharray={`${preenchido} ${circunferencia}`}
          strokeLinecap="round"
        />
      </svg>
      {children && <div className="alu-ring__inner">{children}</div>}
    </div>
  );
}

export interface MarcadorRange {
  value: number;
  label: string;
  color: string;
  /** O marcador do próprio aluno é maior e ganha bolinha. */
  you?: boolean;
}

/** Barra de posição do aluno entre os grupos da turma. */
export function BarraComparacao({
  min = 0, max = 10, marcadores, largura = 540, altura = 62,
}: {
  min?: number;
  max?: number;
  marcadores: MarcadorRange[];
  largura?: number;
  altura?: number;
}) {
  const idGrad = `alu-rg-${useId()}`;
  const padX = 18;
  const trilhaY = 30;
  const trilhaW = largura - padX * 2;
  const X = (v: number) => padX + ((v - min) / (max - min)) * trilhaW;

  return (
    <svg
      width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`}
      style={{ display: 'block', overflow: 'visible' }}
    >
      <defs>
        <linearGradient id={idGrad} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#F7ECDA" />
          <stop offset="40%" stopColor="#f5f7fb" />
          <stop offset="100%" stopColor="#E2F2EA" />
        </linearGradient>
      </defs>

      <rect x={padX} y={trilhaY - 4} width={trilhaW} height={8} rx={4} fill={`url(#${idGrad})`} />

      {marcadores.map((m) => {
        const x = X(m.value);
        return (
          <g key={m.label}>
            <line
              x1={x} x2={x}
              y1={trilhaY - (m.you ? 14 : 8)} y2={trilhaY + (m.you ? 14 : 8)}
              stroke={m.color} strokeWidth={m.you ? 3 : 2} strokeLinecap="round"
            />
            {m.you && <circle cx={x} cy={trilhaY} r={6} fill={m.color} stroke="#fff" strokeWidth={2} />}
            <text
              x={x} y={m.you ? trilhaY - 20 : altura - 3}
              textAnchor="middle"
              fontSize={m.you ? 11 : 9.5}
              fontWeight={m.you ? 600 : 400}
              fill={m.you ? '#1C2436' : '#9097a8'}
              fontFamily="inherit"
            >
              {m.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export interface SerieLinha {
  values: number[];
  color: string;
  /** Série de referência (média da turma): tracejada, sem área nem ponto. */
  dashed?: boolean;
}

/** Linha de evolução do aluno por ciclo, com área em gradiente. */
export function GraficoLinha({
  series, xLabels, largura = 560, altura = 190, yMin = 4, yMax = 10,
}: {
  series: SerieLinha[];
  xLabels: string[];
  largura?: number;
  altura?: number;
  yMin?: number;
  yMax?: number;
}) {
  const idBase = useId();
  const padL = 28, padR = 14, padT = 12, padB = 26;
  const plotW = largura - padL - padR;
  const plotH = altura - padT - padB;
  const n = xLabels.length;

  if (n < 2) return <div className="alu-loading">Dados insuficientes para o gráfico.</div>;

  const X = (i: number) => padL + (i / (n - 1)) * plotW;
  const Y = (v: number) => padT + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  const suave = (pts: Array<[number, number]>) => {
    if (pts.length < 2) return '';
    let d = `M ${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i];
      const [x1, y1] = pts[i + 1];
      const cx = (x0 + x1) / 2;
      d += ` C ${cx},${y0} ${cx},${y1} ${x1},${y1}`;
    }
    return d;
  };

  return (
    <svg
      width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`}
      style={{ display: 'block', overflow: 'visible' }}
    >
      <defs>
        {series.map((s, si) =>
          s.dashed ? null : (
            <linearGradient key={si} id={`${idBase}-${si}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.14" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0" />
            </linearGradient>
          ),
        )}
      </defs>

      {[0, 0.5, 1].map((t) => (
        <line
          key={t}
          x1={padL} y1={padT + plotH - t * plotH} x2={largura - padR} y2={padT + plotH - t * plotH}
          stroke="rgba(20,30,80,0.06)" strokeWidth={1} strokeDasharray="2 4"
        />
      ))}

      {xLabels.map((lab, i) => (
        <text
          key={i} x={X(i)} y={altura - 6} textAnchor="middle"
          fontSize={10} fill="rgba(26,29,36,0.4)" fontFamily="inherit"
        >
          {lab}
        </text>
      ))}

      {series.map((s, si) => {
        const pts: Array<[number, number]> = s.values.map((v, i) => [X(i), Y(v)]);
        const caminho = suave(pts);
        const ultimo = pts[pts.length - 1];

        return (
          <g key={si}>
            {!s.dashed && (
              <path
                d={`${caminho} L ${ultimo[0]},${padT + plotH} L ${pts[0][0]},${padT + plotH} Z`}
                fill={`url(#${idBase}-${si})`}
              />
            )}
            <path
              d={caminho} fill="none" stroke={s.color}
              strokeWidth={s.dashed ? 1.8 : 2.4}
              strokeDasharray={s.dashed ? '4 4' : undefined}
              opacity={s.dashed ? 0.6 : 1}
            />
            {!s.dashed && (
              <circle cx={ultimo[0]} cy={ultimo[1]} r={4} fill="#fff" stroke={s.color} strokeWidth={2} />
            )}
          </g>
        );
      })}
    </svg>
  );
}
