interface Props {
  valores: number[];
  largura?: number;
  altura?: number;
  cor?: string;
  /** Domínio vertical, em unidades do dado. Padrão: a escala da nota. */
  dominio?: readonly [number, number];
  /** Corte da régua. Sem ele, o fio de ouro não é desenhado. */
  corte?: number;
  /** Rótulo do fio de ouro, quando há largura para ele (ex.: `CORTE 4,0`). */
  rotuloCorte?: string;
  /** Leitura em palavras para quem não enxerga o desenho. Sem ela, é decorativo. */
  descricao?: string;
}

/**
 * A escala da nota. É o domínio certo para todo consumidor de hoje: o que o
 * backend manda em `sparkline` é sempre nota ou média de nota — nunca contagem
 * (`app/stats/alertas.py`, `app/stats/classificacao.py::sparkline_por_aluno`).
 */
const DOMINIO_NOTA: readonly [number, number] = [0, 10];

/** Folga interna: o ponto final e os extremos do domínio não podem vazar da caixa. */
const MARGEM = 3;

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
 * Sparkline SVG: curva suave, área chapada de referência e ponto final marcado.
 *
 * A escala é COMPARTILHADA — o domínio é fixo, não o min/max da própria série.
 * Normalizando por série, quem oscilou entre 2,0 e 2,4 desenhava exatamente a
 * mesma curva de quem subiu de 6,0 para 8,0; na coluna "Trajetória" de
 * `/alunos` isso são 900 linhas de uma forma que parece comparável e não é
 * (docs/39 §3 · fase 1, e a prancheta, que chama o defeito pelo nome). O
 * domínio continua sendo prop porque nem toda série que chegar aqui um dia
 * será nota.
 */
export function Sparkline({
  valores,
  largura = 90,
  altura = 32,
  cor = 'currentColor',
  dominio = DOMINIO_NOTA,
  corte,
  rotuloCorte,
  descricao,
}: Props) {
  if (!valores || valores.length < 2) return <span />;

  const [minimo, maximo] = dominio;
  const amplitude = maximo - minimo || 1;
  const larguraUtil = largura - MARGEM * 2;
  const alturaUtil = altura - MARGEM * 2;

  // Valor fora do domínio é achatado na borda em vez de esticar a escala: uma
  // série só desenha comparável com as outras se a régua não se mexer por ela.
  const y = (valor: number): number => {
    const limitado = Math.min(maximo, Math.max(minimo, valor));
    return MARGEM + (1 - (limitado - minimo) / amplitude) * alturaUtil;
  };

  const passoX = larguraUtil / (valores.length - 1);
  const pontos: Array<[number, number]> = valores.map((v, i) => [MARGEM + i * passoX, y(v)]);

  const caminho = caminhoSuave(pontos);
  const [ultimoX, ultimoY] = pontos[pontos.length - 1];
  const area = `${caminho} L ${ultimoX.toFixed(1)},${altura} L ${pontos[0][0].toFixed(1)},${altura} Z`;

  // O corte não é sempre 4,0 — o Inglês da Fase 1 do ITA é 5,0 e eliminatório —,
  // por isso ele entra por prop, vindo de `dominio/criterios.ts`, e nunca é
  // literal aqui. Fora do domínio ele simplesmente não é desenhado: encostá-lo
  // na borda diria que o corte é o fim da escala, que é outra mentira gráfica.
  const desenhaCorte = corte != null && corte >= minimo && corte <= maximo;
  const corteY = desenhaCorte ? y(corte) : 0;
  // Perto do topo o rótulo sairia da caixa; então ele desce para baixo do fio.
  const rotuloY = corteY < 12 ? corteY + 9 : corteY - 4;

  return (
    <svg
      className="sparkline"
      width={largura}
      height={altura}
      viewBox={`0 0 ${largura} ${altura}`}
      role={descricao ? 'img' : undefined}
      aria-label={descricao}
      aria-hidden={descricao ? undefined : true}
    >
      {/* A área em gradiente virou preenchimento chapado de REFERÊNCIA (R5): a
          mancha atrás da curva é contexto, não um segundo dado — e gradiente
          colorido está fora por restrição do brief. Sem gradiente não há mais
          `<defs>`, e com ele foi embora o `useId` que dava id único por
          instância. */}
      <path d={area} fill="var(--sas-referencia-fraca)" />
      {/* R2 · nunca se lê uma nota sem a régua ao lado. O fio de ouro fica
          ATRÁS da curva: régua é referência, o dado passa por cima. */}
      {desenhaCorte && (
        <>
          <line
            x1="0"
            y1={corteY.toFixed(1)}
            x2={largura}
            y2={corteY.toFixed(1)}
            stroke="var(--sas-valor)"
            strokeWidth="1.2"
            strokeDasharray="3 2"
          />
          {rotuloCorte && (
            <text
              x={largura - MARGEM}
              y={rotuloY.toFixed(1)}
              textAnchor="end"
              fontSize="8"
              fontWeight="700"
              fill="var(--sas-valor-texto)"
            >
              {rotuloCorte}
            </text>
          )}
        </>
      )}
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
        fill="var(--sas-superficie)"
        stroke={cor}
        strokeWidth="1.5"
      />
    </svg>
  );
}
