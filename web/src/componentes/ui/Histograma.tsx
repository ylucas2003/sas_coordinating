import type { CSSProperties } from 'react';

import { seloDaNota } from '../../dominio/selo';

// Histograma SVG — recebe `{ largura_bin, maximo, contagens }` direto da rota
// /simulados/{id}/histograma.
//
// É UMA peça em dois tamanhos: grande na ficha da prova, pequena nos doze
// múltiplos da calibração do ciclo. A prancheta insiste nisso — se não for
// reconhecidamente o mesmo desenho, o coordenador acha que são dois dados
// diferentes —, e por isso qualquer conserto aqui conserta as duas telas.
//
// Opções avançadas (opt-in):
//   - eixoYAbsoluto     → eixo Y numerado com escala fixa, o que permite
//                         comparar histogramas de recortes de tamanhos
//                         diferentes.
//   - corte             → o traço de ouro da régua, tracejado e rotulado (R2).
//   - picoCompartilhado → normaliza as barras por um pico externo (ver abaixo).
//   - cicloAnterior     → overlay tracejado para comparação.
//   - kde               → curva de densidade gaussiana atrás das barras.

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
  media?: number | null;
  mediana?: number | null;
  eixoYAbsoluto?: { max?: number; ticks?: number } | null;
  corte?: Corte | null;
  /**
   * O pico pelo qual as barras normalizam, no lugar do máximo local.
   *
   * É o que faz os doze múltiplos da calibração serem COMPARÁVEIS: sem ele
   * cada cartão se normaliza pelo próprio máximo, a barra mais alta de Física
   * fica do tamanho da de Português, e a comparação que é o motivo daquela
   * tela existir some. Histograma sozinho continua no pico local (a prancheta,
   * `hist(...)` da tela de Provas).
   */
  picoCompartilhado?: number | null;
  cicloAnterior?: { contagens: number[]; maximo?: number } | null;
  kde?: boolean;
  /**
   * O rótulo `CORTE 4,0` desenhado ao lado do traço de ouro. Sai só onde a
   * própria moldura já diz o corte em palavras — é o caso do cartão do
   * múltiplo, que o imprime no rodapé.
   */
  rotularCorte?: boolean;
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

interface TracoDaBarra {
  preenchimento: string;
  contorno: string;
  espessura: number;
  abaixo: boolean;
}

/**
 * Como uma barra é DESENHADA contra o corte — R1 e R3 da prancheta.
 *
 * A nota da barra é o CENTRO do bin: é a única nota que a faixa inteira
 * representa, e é contra ela que a régua decide. Acima do corte a barra é
 * preenchida e a saturação cresce com a distância; abaixo ela é VAZADA, e o
 * que cresce é a espessura e a tinta do contorno. Os números são os mesmos de
 * `selo` no Kit de peças e de `Heatmap.tsx` — a peça só é reconhecível como a
 * mesma se a escala for literalmente a mesma.
 *
 * Sem corte não há régua a ancorar, e a única coisa honesta é não fingir
 * distância nenhuma: todas as barras saem no mesmo tom de DADO. É o caso do
 * artefato do chat, que chega sem critério.
 */
function tracoDaBarra(
  centro: number,
  corte: number | null | undefined,
  maximo: number,
): TracoDaBarra {
  const selo = seloDaNota(centro, corte, maximo);

  if (selo.estado === 'sem-dado') {
    return {
      preenchimento: 'color-mix(in srgb, var(--sas-dado) 62%, transparent)',
      contorno: 'none',
      espessura: 0,
      abaixo: false,
    };
  }

  if (selo.estado === 'abaixo') {
    return {
      preenchimento: 'none',
      contorno: `color-mix(in srgb, var(--sas-magnitude) ${Math.round(30 + selo.intensidade * 55)}%, transparent)`,
      espessura: Number((1 + selo.intensidade * 1.6).toFixed(1)),
      abaixo: true,
    };
  }

  return {
    preenchimento: `color-mix(in srgb, var(--sas-dado) ${Math.round(22 + selo.intensidade * 78)}%, transparent)`,
    contorno: 'none',
    espessura: 0,
    abaixo: false,
  };
}

export function Histograma({
  payload,
  largura = 480,
  altura = 180,
  media = null,
  mediana = null,
  eixoYAbsoluto = null,
  corte = null,
  picoCompartilhado = null,
  cicloAnterior = null,
  kde = false,
  rotularCorte = true,
}: Props) {
  if (!payload || !Array.isArray(payload.contagens) || payload.contagens.length === 0) {
    return <div className="empty-state">Sem dados de histograma ainda.</div>;
  }

  const { largura_bin: larguraBin, maximo, contagens } = payload;
  const nBins = contagens.length;

  // Normaliza pelo máximo local; `picoCompartilhado` troca isso por um pico
  // externo e VENCE o `eixoYAbsoluto.max` quando os dois chegam juntos — o
  // eixo numera a escala que as barras usam, e numerar outra seria rotular uma
  // régua que ninguém desenhou.
  const maxLocal = Math.max(...contagens, 1);
  const maxAnterior = cicloAnterior ? Math.max(...(cicloAnterior.contagens ?? []), 1) : 0;
  const picoValido = picoCompartilhado != null && picoCompartilhado > 0 ? picoCompartilhado : null;
  const maxContagem = picoValido ?? eixoYAbsoluto?.max ?? Math.max(maxLocal, maxAnterior);

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

  const corteX = corte?.valor != null ? xDe(corte.valor) : null;
  // Perto da borda direita o rótulo sairia do quadro; ali ele troca de lado.
  const rotuloADireita = corteX == null || corteX < padLeft + plotW * 0.72;

  return (
    <div className="histograma__container">
      <svg className="histograma" width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`}>
        {/* A REFERÊNCIA vai atrás do dado (R5): a curva do ciclo anterior e a
            densidade são contexto, não medida, e as barras passam por cima. */}
        {cicloAnterior?.contagens?.length === nBins && (
          <path
            d={caminhoSuave(
              cicloAnterior.contagens.map((c, i) => [
                padLeft + (i + 0.5) * binW,
                padTop + plotH - (c / maxContagem) * plotH,
              ]),
            )}
            fill="none"
            stroke="var(--sas-referencia)"
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
            // Era `--sas-acao`, o papel do que se APERTA — e uma curva não se
            // aperta. A prancheta desenha a densidade em referência.
            stroke="var(--sas-referencia)"
            strokeWidth="1.5"
            opacity="0.6"
          />
        )}

        <line
          x1={padLeft} x2={padLeft + plotW}
          y1={padTop + plotH} y2={padTop + plotH}
          stroke="var(--sas-borda)"
        />

        {eixoYAbsoluto &&
          Array.from({ length: (eixoYAbsoluto.ticks ?? 4) + 1 }, (_, i) => {
            const nTicks = eixoYAbsoluto.ticks ?? 4;
            const y = padTop + plotH - (i / nTicks) * plotH;
            return (
              <g key={i}>
                <line x1={padLeft - 3} x2={padLeft} y1={y.toFixed(1)} y2={y.toFixed(1)} stroke="var(--sas-borda)" />
                <text
                  x={padLeft - 5} y={(y + 3).toFixed(1)}
                  textAnchor="end" fontSize="10" fill="var(--sas-referencia)"
                >
                  {Math.round((maxContagem * i) / nTicks)}
                </text>
              </g>
            );
          })}

        {contagens.map((c, i) => {
          const h = (c / maxContagem) * plotH;
          if (h <= 0) return null;
          const centro = (i + 0.5) * larguraBin;
          const traco = tracoDaBarra(centro, corte?.valor, maximo);
          const larguraBarra = Math.max(1, binW - 2);
          // O traço do SVG monta EM CIMA da borda, metade para cada lado. Sem
          // encolher a barra pela espessura, o contorno da barra vazada
          // transborda para o bin vizinho e cruza a linha do eixo — e num bin
          // quase vazio ele cruzaria o eixo inteiro, virando um risco solto
          // por baixo do gráfico. Daí o contorno nunca ser mais grosso que a
          // própria barra: a caixa encolhe pela metade da espessura e a base
          // fica exatamente sobre o eixo.
          const espessura = Math.min(traco.espessura, h);
          const meia = espessura / 2;
          const larguraFinal = Math.max(0.5, larguraBarra - espessura);
          const alturaFinal = Math.max(0.4, h - espessura);
          const faixa = `[${(i * larguraBin).toFixed(1)} – ${((i + 1) * larguraBin).toFixed(1)})`;
          return (
            <rect
              key={i}
              x={(padLeft + i * binW + 1 + meia).toFixed(1)}
              y={(padTop + plotH - meia - alturaFinal).toFixed(1)}
              width={larguraFinal.toFixed(1)}
              height={alturaFinal.toFixed(1)}
              rx={Math.min(3, larguraFinal / 2).toFixed(1)}
              fill={traco.preenchimento}
              stroke={traco.contorno}
              strokeWidth={espessura}
            >
              {/* A forma da barra é informação (R1); o título é o que a
                  entrega a quem não a vê. */}
              <title>
                {`${faixa}: ${c} alunos${traco.abaixo ? ' · abaixo do corte' : ''}`}
              </title>
            </rect>
          );
        })}

        {rotulosX.map((i) => (
          <text
            key={i}
            x={(padLeft + i * binW).toFixed(1)}
            y={(padTop + plotH + 14).toFixed(1)}
            textAnchor="middle" fontSize="10" fill="var(--sas-referencia)"
          >
            {(i * larguraBin).toFixed(1).replace('.', ',')}
          </text>
        ))}

        {/* Média e mediana eram VERMELHO e ÂMBAR — o último semáforo do
            produto. Média não é alerta, é REFERÊNCIA (R5), e o vermelho está
            reservado à etiqueta de distância e à falha (R4): do jeito que
            estava, o olho lia a média como problema. As duas passam a cinza,
            atrás do dado, e o que as distingue é a FORMA — cheia e tracejada. */}
        <LinhaVertical x={media == null ? null : xDe(media)} y={padTop} altura={plotH} cor="var(--sas-referencia)" rotulo="Média" valor={media} tracejado={false} />
        <LinhaVertical x={mediana == null ? null : xDe(mediana)} y={padTop} altura={plotH} cor="var(--sas-referencia)" rotulo="Mediana" valor={mediana} />

        {/* A régua é OURO e está sempre desenhada (R2). O sombreado da zona
            reprovada saiu daqui: quem carrega "abaixo" agora é o vazado das
            barras, e duas coisas dizendo a mesma coisa é o que a R7 proíbe. */}
        {corte?.valor != null && corteX != null && (
          <>
            <LinhaVertical
              x={corteX} y={padTop} altura={plotH}
              cor="var(--sas-valor)"
              rotulo={`Corte${corte.label ? ` ${corte.label}` : ''}${corte.eliminatoria ? ' (eliminatória)' : ''}`}
              valor={corte.valor}
              larguraExtra
            />
            {rotularCorte && (
              <text
                x={(rotuloADireita ? corteX + 4 : corteX - 4).toFixed(1)}
                y={padTop + 9}
                textAnchor={rotuloADireita ? 'start' : 'end'}
                fontSize="10" fontWeight="700" letterSpacing=".06em"
                // O ouro de TRAÇO reprova em contraste quando vira letra; o de
                // letra é `--sas-valor-texto` (papeis.css).
                fill="var(--sas-valor-texto)"
              >
                {`CORTE ${fmt(corte.valor)}`}
              </text>
            )}
          </>
        )}
      </svg>

      <div className="histograma__legenda">
        <ItemLegenda cor="var(--sas-referencia)" texto={`Média: ${fmt(media)}`} />
        <ItemLegenda cor="var(--sas-referencia)" tracejado texto={`Mediana: ${fmt(mediana)}`} />
        {corte?.valor != null && (
          // "abaixo é vazado" vai grudado no corte, e não numa quarta entrada
          // com amostra vazada como o Kit de peças desenha: a forma virou a
          // informação e precisa ser nomeada uma vez, mas `.histograma__legenda`
          // é um flex sem `wrap`, e uma quarta entrada esmagaria a legenda do
          // múltiplo de 320px. É o corte que define o "abaixo", então é dele
          // que a frase fala.
          <ItemLegenda
            cor="var(--sas-valor)"
            tracejado
            texto={`Corte: ${fmt(corte.valor)}${corte.eliminatoria ? ' (eliminatória)' : ''} · abaixo é vazado`}
          />
        )}
        {cicloAnterior && (
          <ItemLegenda cor="var(--sas-referencia)" tracejado texto="Ciclo anterior" />
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

/**
 * Uma entrada da legenda.
 *
 * A marca deixou de ser só cor porque as cores deixaram de ser distintas:
 * média e mediana são o MESMO cinza de referência, e o que as separa no
 * desenho é o traço cheio contra o tracejado. Uma legenda que mostrasse dois
 * riscos iguais mentiria sobre um gráfico honesto.
 */
function ItemLegenda({
  cor, texto, tracejado = false,
}: {
  cor: string;
  texto: string;
  tracejado?: boolean;
}) {
  const marca: CSSProperties = {
    background: tracejado
      ? `repeating-linear-gradient(90deg, ${cor} 0 3px, transparent 3px 6px)`
      : cor,
  };
  return (
    <span className="histograma__legenda-item">
      <span className="histograma__legenda-marca" style={marca} />
      {texto}
    </span>
  );
}
