import { useId } from 'react';

interface Props {
  valores: number[];
  largura?: number;
  altura?: number;
  cor?: string;
}

/** Curva suave por Bézier entre os pontos, sem eixos. */
function caminhoSuave(pontos: Array<[number, number]>): string {
  if (pontos.length < 2) return '';
  let d = `M ${pontos[0][0]},${pontos[0][1]}`;
  for (let i = 0; i < pontos.length - 1; i++) {
    const [x0, y0] = pontos[i];
    const [x1, y1] = pontos[i + 1];
    const cx = (x0 + x1) / 2;
    d += ` C ${cx},${y0} ${cx},${y1} ${x1},${y1}`;
  }
  return d;
}

/**
 * Sparkline SVG: curva suave com preenchimento em gradiente e ponto final
 * branco. Mesmo estilo visual dos gráficos da área do aluno.
 */
export function Sparkline({ valores, largura = 90, altura = 32, cor = 'currentColor' }: Props) {
  // `useId` no lugar do contador global que a versão anterior mantinha: cada
  // instância precisa de um id de gradiente único, e o React já garante isso.
  const idGradiente = `spark-${useId()}`;

  if (!valores || valores.length < 2) return <span />;

  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const amplitude = max - min || 1;
  const passoX = largura / (valores.length - 1);

  const pontos: Array<[number, number]> = valores.map((v, i) => [
    i * passoX,
    altura - ((v - min) / amplitude) * altura,
  ]);

  const caminho = caminhoSuave(pontos);
  const [ultimoX, ultimoY] = pontos[pontos.length - 1];
  const area = `${caminho} L ${ultimoX.toFixed(1)},${altura} L ${pontos[0][0].toFixed(1)},${altura} Z`;

  return (
    <svg className="sparkline" width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`}>
      <defs>
        <linearGradient id={idGradiente} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={cor} stopOpacity="0.35" />
          <stop offset="100%" stopColor={cor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${idGradiente})`} />
      <path
        d={caminho}
        fill="none"
        stroke={cor}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* Marca o último ponto — dot branco com contorno na cor da série. */}
      <circle
        cx={ultimoX.toFixed(1)}
        cy={ultimoY.toFixed(1)}
        r="2.5"
        fill="var(--color-surface)"
        stroke={cor}
        strokeWidth="1.5"
      />
    </svg>
  );
}
