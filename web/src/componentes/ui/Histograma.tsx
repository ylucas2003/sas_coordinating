import { useId } from 'react';

// Histograma SVG — recebe `{ largura_bin, maximo, contagens }` direto da rota
// /simulados/{id}/histograma.
//
// Opções avançadas (opt-in):
//   - eixoYAbsoluto  → eixo Y numerado com escala fixa, o que permite comparar
//                      histogramas de recortes de tamanhos diferentes.
//   - corte          → linha vertical do corte + sombreamento da zona reprovada.
//   - cicloAnterior  → overlay tracejado para comparação.
//   - kde            → curva de densidade gaussiana sobre as barras.

export interface PayloadHistograma {
  largura_bin: number;
  maximo: number;
  contagens: number[];
}

export interface Corte {
  valor: number;
  label?: string;
  eliminatoria?: boolean;
}

interface Props {
  payload: PayloadHistograma | null | undefined;
  largura?: number;
  altura?: number;
  cor?: string;
  media?: number | null;
  mediana?: number | null;
  eixoYAbsoluto?: { max?: number; ticks?: number } | null;
  corte?: Corte | null;
  cicloAnterior?: { contagens: number[]; maximo?: number } | null;
  kde?: boolean;
}

const fmt = (n: number | null | undefined) => (n == null ? '—' : n.toFixed(1).replace('.', ','));

/** Curva suave (Bézier) — mesmo algoritmo dos demais gráficos, para unificar a linguagem visual. */
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

/**
 * Curva de densidade gaussiana. Usa as contagens como pontos discretos e
 * aplica o kernel sobre o eixo X, com largura de banda pela regra de Silverman.
 */
function pontosKde(contagens: number[], larguraBin: number): Array<[number, number]> | null {
  const nBins = contagens.length;
  const total = contagens.reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const centros = contagens.map((_, i) => (i + 0.5) * larguraBin);
  const media = centros.reduce((acc, c, i) => acc + c * contagens[i], 0) / total;
  const variancia =
    centros.reduce((acc, c, i) => acc + contagens[i] * (c - media) ** 2, 0) / total;
  const desvio = Math.sqrt(variancia) || larguraBin;
  const h = 1.06 * desvio * Math.pow(total, -1 / 5);

  const passos = 60;
  const xMax = nBins * larguraBin;
  const pontos: Array<[number, number]> = [];
  let maxDensidade = 0;

  for (let i = 0; i <= passos; i += 1) {
    const x = (i / passos) * xMax;
    let d = 0;
    for (let j = 0; j < nBins; j += 1) {
      const u = (x - centros[j]) / h;
      d += contagens[j] * Math.exp(-0.5 * u * u);
    }
    d /= total * h * Math.sqrt(2 * Math.PI);
    pontos.push([x, d]);
    if (d > maxDensidade) maxDensidade = d;
  }

  if (maxDensidade === 0) return null;
  return pontos.map(([x, d]) => [x / xMax, d / maxDensidade]);
}

export function Histograma({
  payload,
  largura = 480,
  altura = 180,
  cor = 'var(--color-navy)',
  media = null,
  mediana = null,
  eixoYAbsoluto = null,
  corte = null,
  cicloAnterior = null,
  kde = false,
}: Props) {
  const idGradiente = `hist-${useId()}`;

  if (!payload || !Array.isArray(payload.contagens) || payload.contagens.length === 0) {
    return <div className="empty-state">Sem dados de histograma ainda.</div>;
  }

  const { largura_bin: larguraBin, maximo, contagens } = payload;
  const nBins = contagens.length;

  // Por padrão normaliza pelo máximo local; com `eixoYAbsoluto` usa escala fixa.
  const maxLocal = Math.max(...contagens, 1);
  const maxAnterior = cicloAnterior ? Math.max(...(cicloAnterior.contagens ?? []), 1) : 0;
  const maxContagem = eixoYAbsoluto?.max ?? Math.max(maxLocal, maxAnterior);

  const padLeft = eixoYAbsoluto ? 36 : 28;
  const padBottom = 22;
  const padTop = 8;
  const padRight = 8;
  const plotW = largura - padLeft - padRight;
  const plotH = altura - padTop - padBottom;
  const binW = plotW / nBins;

  const xDe = (valor: number) => padLeft + (valor / maximo) * plotW;

  const passoRotulo = Math.max(1, Math.ceil(nBins / 6));
  const rotulosX = [];
  for (let i = 0; i <= nBins; i += passoRotulo) rotulosX.push(i);

  const kdePts = kde ? pontosKde(contagens, larguraBin) : null;

  return (
    <div className="histograma__container">
      <svg className="histograma" width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`}>
        <defs>
          {/* Gradiente vertical das barras: topo mais opaco que a base. */}
          <linearGradient id={idGradiente} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={cor} stopOpacity="0.95" />
            <stop offset="100%" stopColor={cor} stopOpacity="0.6" />
          </linearGradient>
        </defs>

        {/* Sombreamento da zona reprovada, atrás das barras. */}
        {corte?.valor != null && (
          <rect
            x={padLeft}
            y={padTop}
            width={(xDe(corte.valor) - padLeft).toFixed(1)}
            height={plotH}
            fill={'var(--color-gold)'}
            opacity="0.08"
          />
        )}

        <line
          x1={padLeft} x2={padLeft + plotW}
          y1={padTop + plotH} y2={padTop + plotH}
          stroke="var(--color-border-strong)"
        />

        {eixoYAbsoluto &&
          Array.from({ length: (eixoYAbsoluto.ticks ?? 4) + 1 }, (_, i) => {
            const nTicks = eixoYAbsoluto.ticks ?? 4;
            const y = padTop + plotH - (i / nTicks) * plotH;
            return (
              <g key={i}>
                <line x1={padLeft - 3} x2={padLeft} y1={y.toFixed(1)} y2={y.toFixed(1)} stroke="var(--color-border-strong)" />
                <text
                  x={padLeft - 5} y={(y + 3).toFixed(1)}
                  textAnchor="end" fontSize="10" fill="var(--color-text-tertiary)"
                >
                  {Math.round((maxContagem * i) / nTicks)}
                </text>
              </g>
            );
          })}

        {contagens.map((c, i) => {
          const h = (c / maxContagem) * plotH;
          const larguraBarra = Math.max(1, binW - 2);
          return (
            <rect
              key={i}
              x={(padLeft + i * binW + 1).toFixed(1)}
              y={(padTop + plotH - h).toFixed(1)}
              width={larguraBarra.toFixed(1)}
              height={h.toFixed(1)}
              rx={Math.min(3, larguraBarra / 2).toFixed(1)}
              fill={`url(#${idGradiente})`}
            >
              <title>{`[${(i * larguraBin).toFixed(1)} – ${((i + 1) * larguraBin).toFixed(1)}): ${c} alunos`}</title>
            </rect>
          );
        })}

        {cicloAnterior?.contagens?.length === nBins && (
          <path
            d={caminhoSuave(
              cicloAnterior.contagens.map((c, i) => [
                padLeft + (i + 0.5) * binW,
                padTop + plotH - (c / maxContagem) * plotH,
              ]),
            )}
            fill="none"
            stroke="var(--color-text-tertiary)"
            strokeWidth="1.5"
            strokeDasharray="4,3"
            opacity="0.7"
          >
            <title>Distribuição do ciclo anterior</title>
          </path>
        )}

        {kdePts && (
          <polyline
            points={kdePts
              // A densidade é escalada para a altura do bin máximo — estética:
              // a curva acompanha as barras em vez de flutuar sobre elas.
              .map(([x, d]) =>
                `${(padLeft + x * plotW).toFixed(1)},${(padTop + plotH - d * plotH * 0.95).toFixed(1)}`)
              .join(' ')}
            fill="none"
            stroke="var(--color-navy)"
            strokeWidth="1.5"
            opacity="0.45"
          />
        )}

        {rotulosX.map((i) => (
          <text
            key={i}
            x={(padLeft + i * binW).toFixed(1)}
            y={(padTop + plotH + 14).toFixed(1)}
            textAnchor="middle" fontSize="10" fill="var(--color-text-tertiary)"
          >
            {(i * larguraBin).toFixed(1).replace('.', ',')}
          </text>
        ))}

        <LinhaVertical x={media == null ? null : xDe(media)} y={padTop} altura={plotH} cor="var(--color-red)" rotulo="Média" valor={media} />
        <LinhaVertical x={mediana == null ? null : xDe(mediana)} y={padTop} altura={plotH} cor="var(--color-amber)" rotulo="Mediana" valor={mediana} />
        {corte?.valor != null && (
          <LinhaVertical
            x={xDe(corte.valor)} y={padTop} altura={plotH}
            cor={'var(--color-gold)'}
            rotulo={`Corte${corte.label ? ' ' + corte.label : ''}`}
            valor={corte.valor}
            tracejado={false}
            larguraExtra
          />
        )}
      </svg>

      <div className="histograma__legenda">
        <ItemLegenda cor="var(--color-red)" texto={`Média: ${fmt(media)}`} />
        <ItemLegenda cor="var(--color-amber)" texto={`Mediana: ${fmt(mediana)}`} />
        {corte?.valor != null && (
          <ItemLegenda
            cor={'var(--color-gold)'}
            texto={`Corte: ${fmt(corte.valor)}${corte.eliminatoria ? ' (eliminatória)' : ''}`}
          />
        )}
        {cicloAnterior && (
          <ItemLegenda cor="var(--color-text-tertiary)" texto="Ciclo anterior (tracejado)" />
        )}
      </div>
    </div>
  );
}

function LinhaVertical({
  x, y, altura, cor, rotulo, valor, tracejado = true, larguraExtra = false,
}: {
  x: number | null;
  y: number;
  altura: number;
  cor: string;
  rotulo: string;
  valor: number | null;
  tracejado?: boolean;
  larguraExtra?: boolean;
}) {
  if (x == null || valor == null) return null;
  return (
    <line
      x1={x.toFixed(1)} x2={x.toFixed(1)} y1={y} y2={y + altura}
      stroke={cor}
      strokeDasharray={tracejado ? '3,3' : undefined}
      strokeWidth={larguraExtra ? 2 : 1.5}
    >
      <title>{`${rotulo}: ${fmt(valor)}`}</title>
    </line>
  );
}

function ItemLegenda({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span className="histograma__legenda-item">
      <span className="histograma__legenda-marca" style={{ background: cor }} />
      {texto}
    </span>
  );
}
