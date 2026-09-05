import { useId } from 'react';

// Linha temporal "rica" — substitui o sparkline na ficha do ciclo.
//
// Difere do sparkline em três pontos críticos para o coordenador:
//   1. Eixo Y numerado em escala absoluta (0–10), fixa e não normalizada, para
//      que notas sejam comparáveis entre gráficos.
//   2. Eixo X com datas (ou rótulos curtos) marcadas.
//   3. Pontos com tooltip (data + nome + média) e clicáveis.
//
// Aceita uma série secundária ("ciclo anterior") tracejada para comparação.

export interface PontoTemporal {
  simuladoId?: string;
  nome: string;
  rotuloCurto?: string | null;
  data?: string | null;
  media: number;
  cicloAnteriorMedia?: number | null;
  nPresentes?: number | null;
  materia?: string;
}

interface Props {
  pontos: PontoTemporal[];
  largura?: number;
  altura?: number;
  yMax?: number;
  /** Linha horizontal de referência. */
  corte?: { valor: number; label?: string; eliminatoria?: boolean } | null;
  onPontoClick?: ((ponto: PontoTemporal) => void) | null;
  /** Desenha a série tracejada se algum ponto trouxer `cicloAnteriorMedia`. */
  mostrarCicloAnterior?: boolean;
  /**
   * Como a série se chama na legenda e no tooltip. O default é do caso de
   * origem (evolução de ciclo), mas o banco de questões reusa o mesmo desenho
   * para "questões por ano" — e ali "Ciclo atual"/"Média" seriam mentira
   * (docs/22 §P4). Aditivo: quem já chamava continua igual.
   */
  rotuloSerie?: string;
  rotuloValor?: string;
}

const um = (n: number) => n.toFixed(1).replace('.', ',');

/** Curva suave (Bézier) — mesmo algoritmo dos demais gráficos. */
function caminhoSuave(pts: Array<[number, number]>): string {
  if (pts.length < 2) return '';
  let d = `M ${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const cx = (x0 + x1) / 2;
    d += ` C ${cx.toFixed(1)},${y0.toFixed(1)} ${cx.toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`;
  }
  return d;
}

/** "2026-03-08" → "08/03". */
function dataCurta(iso: string | null | undefined): string {
  if (!iso) return '—';
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}` : iso;
}

export function LinhaTemporal({
  pontos,
  largura = 720,
  altura = 220,
  yMax = 10,
  corte = null,
  onPontoClick = null,
  mostrarCicloAnterior = true,
  rotuloSerie = 'Ciclo atual',
  rotuloValor = 'Média',
}: Props) {
  const idGradiente = `linha-temporal-${useId()}`;

  if (!Array.isArray(pontos) || pontos.length === 0) {
    return <div className="empty-state">Sem dados suficientes pra mostrar evolução.</div>;
  }

  const padLeft = 40;
  const padRight = 16;
  const padTop = 14;
  const padBottom = 36;
  const plotW = largura - padLeft - padRight;
  const plotH = altura - padTop - padBottom;

  const n = pontos.length;
  const stepX = n > 1 ? plotW / (n - 1) : 0;
  const xDe = (i: number) => (n > 1 ? padLeft + i * stepX : padLeft + plotW / 2);
  const yDe = (v: number) => padTop + plotH - (v / yMax) * plotH;

  const pontosAtual: Array<[number, number]> = pontos.map((p, i) => [xDe(i), yDe(p.media)]);
  const caminho = caminhoSuave(pontosAtual);
  const ultimo = pontosAtual[pontosAtual.length - 1];

  const temAnterior = mostrarCicloAnterior && pontos.some((p) => p.cicloAnteriorMedia != null);
  const pontosAnterior = temAnterior
    ? (pontos
        .map((p, i) => (p.cicloAnteriorMedia != null ? [xDe(i), yDe(p.cicloAnteriorMedia)] : null))
        .filter(Boolean) as Array<[number, number]>)
    : [];

  const passoRotulo = Math.max(1, Math.ceil(n / 8));

  return (
    <div className="linha-temporal__container">
      <svg className="linha-temporal" width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`}>
        <defs>
          <linearGradient id={idGradiente} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-navy)" stopOpacity="0.16" />
            <stop offset="100%" stopColor="var(--color-navy)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Grid horizontal + rótulos do eixo Y. */}
        {[0, 2, 4, 6, 8, 10].map((t) => {
          const y = yDe(t);
          return (
            <g key={t}>
              <line
                x1={padLeft} x2={padLeft + plotW} y1={y.toFixed(1)} y2={y.toFixed(1)}
                stroke="var(--color-border)" strokeWidth="1"
                strokeDasharray={t !== 0 ? '2,3' : undefined}
              />
              <text
                x={padLeft - 6} y={(y + 3).toFixed(1)}
                textAnchor="end" fontSize="10" fill="var(--color-text-tertiary)"
              >
                {t}
              </text>
            </g>
          );
        })}

        {corte?.valor != null && (
          <line
            x1={padLeft} x2={padLeft + plotW}
            y1={yDe(corte.valor).toFixed(1)} y2={yDe(corte.valor).toFixed(1)}
            stroke={corte.eliminatoria ? 'var(--color-red)' : 'var(--color-amber)'}
            strokeWidth="1.5" strokeDasharray="6,3"
          >
            <title>{`Corte: ${um(corte.valor)}${corte.eliminatoria ? ' (eliminatória)' : ''}`}</title>
          </line>
        )}

        {pontosAnterior.length >= 2 && (
          <path
            d={caminhoSuave(pontosAnterior)}
            fill="none" stroke="var(--color-text-tertiary)"
            strokeWidth="1.5" strokeDasharray="4,3" opacity="0.7"
          />
        )}

        <path
          d={`${caminho} L ${ultimo[0].toFixed(1)},${(padTop + plotH).toFixed(1)} L ${pontosAtual[0][0].toFixed(1)},${(padTop + plotH).toFixed(1)} Z`}
          fill={`url(#${idGradiente})`}
        />
        <path
          d={caminho}
          fill="none" stroke="var(--color-navy)" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round"
        />

        {pontos.map((p, i) => {
          const [x, y] = pontosAtual[i];
          const tooltip = [
            p.rotuloCurto || p.nome,
            // Sem data não é "data vazia", é série que não tem eixo de data
            // (recorrência por ano, docs/22 §P4). Linha ausente diz isso melhor.
            p.data ? `Data: ${p.data}` : null,
            `${rotuloValor}: ${p.media.toFixed(2).replace('.', ',')}`,
            p.cicloAnteriorMedia != null
              ? `Ciclo anterior: ${p.cicloAnteriorMedia.toFixed(2).replace('.', ',')}`
              : null,
            p.nPresentes != null ? `Presentes: ${p.nPresentes}` : null,
          ].filter(Boolean).join('\n');

          return (
            <g
              key={p.simuladoId ?? i}
              className="linha-temporal__ponto"
              style={onPontoClick ? { cursor: 'pointer' } : undefined}
              onClick={onPontoClick ? () => onPontoClick(p) : undefined}
            >
              <circle
                cx={x.toFixed(1)} cy={y.toFixed(1)} r="4"
                fill="var(--color-surface)" stroke="var(--color-navy)" strokeWidth="2"
              />
              <title>{tooltip}</title>
            </g>
          );
        })}

        {pontos.map((p, i) => {
          if (i % passoRotulo !== 0 && i !== n - 1) return null;
          return (
            <g key={`rot-${i}`}>
              <text
                x={xDe(i).toFixed(1)} y={(padTop + plotH + 16).toFixed(1)}
                textAnchor="middle" fontSize="10" fill="var(--color-text-tertiary)"
              >
                {p.rotuloCurto || dataCurta(p.data)}
              </text>
              {/* Segunda linha com a data quando o rótulo curto ocupou a primeira. */}
              {p.rotuloCurto && p.data && (
                <text
                  x={xDe(i).toFixed(1)} y={(padTop + plotH + 28).toFixed(1)}
                  textAnchor="middle" fontSize="9" fill="var(--color-text-tertiary)" opacity="0.7"
                >
                  {dataCurta(p.data)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div className="linha-temporal__legenda">
        <ItemLegenda cor="var(--color-navy)" texto={rotuloSerie} />
        {temAnterior && <ItemLegenda cor="var(--color-text-tertiary)" texto="Ciclo anterior" tracejado />}
        {corte?.valor != null && (
          <ItemLegenda
            cor={corte.eliminatoria ? 'var(--color-red)' : 'var(--color-amber)'}
            texto={`Corte ${um(corte.valor)}${corte.eliminatoria ? ' (eliminatória)' : ''}`}
            tracejado
          />
        )}
      </div>
    </div>
  );
}

function ItemLegenda({ cor, texto, tracejado = false }: { cor: string; texto: string; tracejado?: boolean }) {
  return (
    <span className="linha-temporal__legenda-item">
      <span
        className="linha-temporal__legenda-marca"
        style={{
          background: tracejado ? 'transparent' : cor,
          border: `2px ${tracejado ? 'dashed' : 'solid'} ${cor}`,
        }}
      />
      {texto}
    </span>
  );
}
