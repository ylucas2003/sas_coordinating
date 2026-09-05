import { useLayoutEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fmtDataBR } from '../../util/data';
import { fmtDelta, fmtNota } from '../../util/formato';

// Gráfico de linha da evolução do aluno por ciclo.
// Eixo X = ciclos categóricos (C1, C2…). Eixo Y = nota 0–10, fixa.
// Suporta várias séries (uma linha por matéria) e tooltip detalhado.

/** A forma do marcador. Quatro formas que, com cheio e vazado, dão os cinco. */
type Marcador = 'circulo' | 'quadrado' | 'losango' | 'triangulo';

interface TracoDaSerie {
  cor: string;
  /** `undefined` = traço cheio. */
  tracejado?: string;
  marcador: Marcador;
  /** Marcador cheio ou vazado. Só a primeira série é cheia. */
  preenchido: boolean;
}

/**
 * Como cada série é desenhada: cor, tracejado E marcador.
 *
 * ⚠️ Aqui havia uma paleta categórica de matizes cravados — seis, depois
 * cinco `--serie-*`. Ela morria de duas maneiras: quem não distingue matiz
 * (~8% dos homens) via cinco linhas iguais, e a cor deixava de ser PAPEL para
 * virar rótulo de matéria, que é exatamente o que este produto abandonou.
 *
 * A prancheta resolve por FORMA ALÉM DE COR: um matiz só, o DADO, derivado
 * por `color-mix`, e o que separa uma série da outra é o traço — cheio,
 * tracejado, pontilhado — somado ao marcador. Duas séries quaisquer diferem
 * em pelo menos duas dimensões, e nenhuma delas depende de enxergar matiz.
 * As três primeiras são as da prancheta, valor por valor; as duas últimas
 * seguem a mesma gramática.
 *
 * São CINCO, que é o teto do brief. Passando disso o traço se repete, e a
 * repetição é o sinal de que quem devia estar trabalhando é o filtro, não o
 * gráfico (R6 · a ordenação faz o trabalho que a cor fazia).
 */
const TRACOS_SERIE: readonly TracoDaSerie[] = [
  { cor: 'var(--sas-dado)', marcador: 'circulo', preenchido: true },
  { cor: 'var(--sas-dado-claro)', tracejado: '6 4', marcador: 'circulo', preenchido: false },
  {
    cor: 'color-mix(in srgb, var(--sas-dado) 60%, var(--sas-superficie))',
    tracejado: '2 3',
    marcador: 'quadrado',
    preenchido: false,
  },
  { cor: 'var(--sas-dado)', tracejado: '10 4 2 4', marcador: 'losango', preenchido: false },
  { cor: 'var(--sas-dado-claro)', tracejado: '1 4', marcador: 'triangulo', preenchido: false },
];

const FASE_LABEL: Record<string, string> = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

/** Raio do marcador em repouso e sob o ponteiro. */
const R_MARCA = 3.6;
const R_MARCA_ATIVA = 5.4;

export interface PontoEvolucao {
  cicloOrdem: number | null;
  vestibularAlvo?: string | null;
  nota: number;
  mediaTurma?: number | null;
  simulado?: string;
  simuladoId?: string | null;
  dataAplicacao?: string | null;
  tipo?: string | null;
  materia?: string;
  /** Nota 0 com presença marcada — provável abandono, não desempenho. */
  abandonoProvavel?: boolean;
}

export interface SerieEvolucao {
  nome: string;
  pontos: PontoEvolucao[];
}

/**
 * A faixa em que a turma se distribuiu naquele ciclo — o mínimo e o máximo.
 *
 * Opcional, e o desenho degrada sem ela: hoje nenhuma consulta devolve a
 * envoltória, e inventá-la a partir da média seria desenhar uma dispersão que
 * ninguém mediu. Quando o servidor passar a mandar, a faixa entra como
 * REFERÊNCIA (R5) — cinza fraco, atrás de tudo.
 */
export interface FaixaDaTurma {
  cicloOrdem: number;
  minimo: number;
  maximo: number;
}

interface Props {
  series: SerieEvolucao[];
  ciclosEixo: Array<{ ordem: number; label: string }>;
  /**
   * Linha de corte. Ausente = nenhuma linha — sem régua carregada não há
   * corte honesto a desenhar. O default era `4`, que virava a régua de fato
   * em qualquer chamada que esquecesse de passar o valor (docs/31 §P1).
   */
  corte?: number | null;
  corteRotulo?: string;
  faixaTurma?: readonly FaixaDaTurma[];
  altura?: number;
}

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
 * O marcador da série — a metade da identidade que sobrevive ao daltonismo e
 * à impressão em preto e branco do dossiê.
 *
 * `pointerEvents: none` porque quem escuta o ponteiro é o alvo transparente
 * desenhado por cima: com marcador de 3,6px o acerto dependia de pontaria, e
 * a marca de uma série ficava por cima do alvo da série de baixo.
 */
function MarcaDaSerie({ traco, x, y, r }: { traco: TracoDaSerie; x: number; y: number; r: number }) {
  const comum = {
    fill: traco.preenchido ? traco.cor : 'var(--sas-superficie)',
    stroke: traco.cor,
    strokeWidth: 1.8,
    style: { pointerEvents: 'none' as const },
  };

  if (traco.marcador === 'quadrado') {
    return <rect x={x - r} y={y - r} width={r * 2} height={r * 2} rx={1} {...comum} />;
  }
  if (traco.marcador === 'losango') {
    const d = r * 1.3;
    const [cx, cy, e, o] = [x.toFixed(1), y.toFixed(1), (x + d).toFixed(1), (x - d).toFixed(1)];
    return (
      <path
        d={`M${cx},${(y - d).toFixed(1)}L${e},${cy}L${cx},${(y + d).toFixed(1)}L${o},${cy}Z`}
        {...comum}
      />
    );
  }
  if (traco.marcador === 'triangulo') {
    const alto = r * 1.35;
    const largo = r * 1.25;
    return (
      <path
        d={`M${x},${(y - alto).toFixed(1)}L${(x + largo).toFixed(1)},${(y + alto * 0.7).toFixed(1)}L${(x - largo).toFixed(1)},${(y + alto * 0.7).toFixed(1)}Z`}
        {...comum}
      />
    );
  }
  return <circle cx={x} cy={y} r={r} {...comum} />;
}

interface EstadoTooltip {
  ponto: PontoEvolucao;
  cor: string;
  x: number;
  y: number;
}

export function LinhaEvolucao({
  series, ciclosEixo, corte, corteRotulo, faixaTurma, altura = 320,
}: Props) {
  const navegar = useNavigate();
  const refWrapper = useRef<HTMLDivElement>(null);
  const refTooltip = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<EstadoTooltip | null>(null);

  // Clampa o tooltip nas bordas do gráfico. Só dá para fazer depois do
  // render, quando o tamanho real do balão é conhecido.
  useLayoutEffect(() => {
    const balao = refTooltip.current;
    const wrapper = refWrapper.current;
    if (!tooltip || !balao || !wrapper) return;

    const areaW = wrapper.clientWidth;
    const areaH = wrapper.clientHeight;
    const { width, height } = balao.getBoundingClientRect();

    let left = tooltip.x + 14;
    let top = tooltip.y + 14;
    if (left + width > areaW) left = tooltip.x - width - 14;
    if (top + height > areaH) top = tooltip.y - height - 14;

    balao.style.left = `${Math.max(0, left)}px`;
    balao.style.top = `${Math.max(0, top)}px`;
  }, [tooltip]);

  const vazio =
    !ciclosEixo.length || !series.length || series.every((s) => !s.pontos.length);
  if (vazio) {
    return (
      <div className="linha-evol">
        <div className="linha-evol__vazio">Sem dados pra plotar com os filtros atuais.</div>
      </div>
    );
  }

  const margem = { top: 18, right: 24, bottom: 36, left: 42 };
  const larguraTotal = 760;
  const plotW = larguraTotal - margem.left - margem.right;
  const plotH = altura - margem.top - margem.bottom;

  const indicePorOrdem = new Map(ciclosEixo.map((c, i) => [c.ordem, i]));
  const xDe = (ordem: number | null) => {
    const i = ordem == null ? undefined : indicePorOrdem.get(ordem);
    if (i == null) return null;
    if (ciclosEixo.length === 1) return margem.left + plotW / 2;
    return margem.left + (i / (ciclosEixo.length - 1)) * plotW;
  };
  const yDe = (nota: number) => margem.top + plotH - (nota / 10) * plotH;
  const ordemNoEixo = (p: PontoEvolucao) => indicePorOrdem.get(p.cicloOrdem!)!;

  function mostrarTooltip(ev: React.MouseEvent, ponto: PontoEvolucao, cor: string) {
    const wrapper = refWrapper.current;
    if (!wrapper) return;
    const rect = wrapper.getBoundingClientRect();
    setTooltip({ ponto, cor, x: ev.clientX - rect.left, y: ev.clientY - rect.top });
  }

  const yCorte = corte != null ? yDe(corte) : null;

  // A envoltória da turma, quando existe: R5, a comparação é cinza e fica
  // ATRÁS do dado. Menos de dois ciclos não fecham polígono nenhum.
  const pontosDaFaixa = (faixaTurma ?? [])
    .map((f) => ({ x: xDe(f.cicloOrdem), minimo: f.minimo, maximo: f.maximo }))
    .filter((f): f is { x: number; minimo: number; maximo: number } => f.x != null)
    .sort((a, b) => a.x - b.x);
  const caminhoFaixa = pontosDaFaixa.length >= 2
    ? `${pontosDaFaixa
        .map((f, i) => `${i ? 'L' : 'M'}${f.x.toFixed(1)},${yDe(f.maximo).toFixed(1)}`)
        .join(' ')} ${[...pontosDaFaixa]
        .reverse()
        .map((f) => `L${f.x.toFixed(1)},${yDe(f.minimo).toFixed(1)}`)
        .join(' ')} Z`
    : '';

  // A média da turma já viajava em cada ponto e só aparecia no tooltip. Com
  // uma série ela vira a linha de referência que dá sentido à do aluno; com
  // várias, seriam cinco cinzas atrás de cinco azuis — R7, silêncio.
  const pontosDaMedia = series.length === 1
    ? series[0].pontos
        .filter((p) => p.mediaTurma != null && p.cicloOrdem != null && indicePorOrdem.has(p.cicloOrdem))
        .sort((a, b) => ordemNoEixo(a) - ordemNoEixo(b))
    : [];
  const caminhoMedia = pontosDaMedia.length >= 2
    ? caminhoSuave(pontosDaMedia.map((p) => [xDe(p.cicloOrdem)!, yDe(p.mediaTurma!)]))
    : '';

  return (
    <div className="linha-evol" ref={refWrapper}>
      {tooltip && <Tooltip ref={refTooltip} {...tooltip} />}

      <svg
        className="linha-evol__svg"
        width="100%"
        viewBox={`0 0 ${larguraTotal} ${altura}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {caminhoFaixa && <path d={caminhoFaixa} fill="var(--sas-referencia-fraca)" />}

        <g className="linha-evol__grid">
          {[0, 2, 4, 6, 8, 10].map((tick) => {
            const y = yDe(tick);
            return (
              <g key={tick}>
                <line
                  x1={margem.left} y1={y} x2={margem.left + plotW} y2={y}
                  stroke="var(--sas-borda)" strokeWidth={1}
                />
                <text
                  x={margem.left - 6} y={y + 3.5}
                  textAnchor="end" fontSize={10} fill="var(--sas-referencia)"
                >
                  {tick}
                </text>
              </g>
            );
          })}
        </g>

        {caminhoMedia && (
          <path
            d={caminhoMedia}
            fill="none" stroke="var(--sas-referencia)" strokeWidth={1.4}
            strokeLinejoin="round"
          />
        )}

        {yCorte != null && (
          <>
            <line
              x1={margem.left} y1={yCorte} x2={margem.left + plotW} y2={yCorte}
              stroke="var(--sas-valor)" strokeWidth={1.6} strokeDasharray="5 4"
            />
            <text
              x={margem.left + plotW - 6} y={yCorte - 6}
              textAnchor="end" fontSize={10} fontWeight={700} fill="var(--sas-valor-texto)"
            >
              {(corteRotulo ?? '').toUpperCase()}
            </text>
          </>
        )}

        {ciclosEixo.map((c) => (
          <text
            key={c.ordem}
            x={xDe(c.ordem) ?? 0} y={margem.top + plotH + 18}
            textAnchor="middle" fontSize={11} fill="var(--sas-texto-2)"
          >
            {c.label}
          </text>
        ))}

        {series.map((serie, idx) => {
          const traco = TRACOS_SERIE[idx % TRACOS_SERIE.length];
          const ordenados = serie.pontos
            .filter((p) => p.cicloOrdem != null && indicePorOrdem.has(p.cicloOrdem) && p.nota != null)
            .sort((a, b) => ordemNoEixo(a) - ordemNoEixo(b));

          if (!ordenados.length) return null;

          return (
            <g key={serie.nome || idx}>
              {ordenados.length >= 2 && (
                <path
                  d={caminhoSuave(ordenados.map((p) => [xDe(p.cicloOrdem)!, yDe(p.nota)]))}
                  fill="none" stroke={traco.cor} strokeWidth={2}
                  strokeDasharray={traco.tracejado}
                  strokeLinejoin="round" strokeLinecap="round"
                />
              )}
              {ordenados.map((p, i) => {
                const x = xDe(p.cicloOrdem)!;
                const y = yDe(p.nota);
                // R4 · o vermelho aqui não é desempenho ruim, é dado suspeito:
                // presença marcada com nota 0 é falha de lançamento até prova
                // em contrário. A FORMA da série é preservada, para não
                // perder de que matéria o ponto é.
                const tracoDoPonto = p.abandonoProvavel
                  ? { ...traco, cor: 'var(--sas-alerta)', preenchido: true }
                  : traco;
                return (
                  <g key={p.simuladoId ?? `${serie.nome}-${i}`}>
                    <MarcaDaSerie
                      traco={tracoDoPonto}
                      x={x} y={y}
                      r={tooltip?.ponto === p ? R_MARCA_ATIVA : R_MARCA}
                    />
                    {/* Alvo do ponteiro, 20px: o marcador desenhado é pequeno
                        demais para servir de alvo, e engordá-lo apagaria a
                        distinção entre as formas.

                        Sem a classe `linha-evol__ponto` de propósito: o
                        `:hover { r: 6 }` dela ENCOLHERIA este alvo assim que o
                        ponteiro entrasse, e o ponteiro a 8px cairia fora do
                        que acabou de virar 6px — entra e sai em laço. Quem dá
                        o retorno visual agora é o marcador, que cresce por
                        estado do React. */}
                    <circle
                      cx={x} cy={y} r={10}
                      fill="transparent"
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={(ev) => mostrarTooltip(ev, p, traco.cor)}
                      onMouseMove={(ev) => mostrarTooltip(ev, p, traco.cor)}
                      onMouseLeave={() => setTooltip(null)}
                      onClick={() => p.simuladoId && navegar(`/simulados/${p.simuladoId}`)}
                    />
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>

      {(series.length > 1 || series[0]?.nome) && (
        <div className="linha-evol__legenda">
          {series.map((serie, idx) =>
            serie.pontos.length ? (
              <span key={serie.nome || idx} className="linha-evol__legenda-item">
                <AmostraDoTraco traco={TRACOS_SERIE[idx % TRACOS_SERIE.length]} />
                {serie.nome}
              </span>
            ) : null,
          )}
          {caminhoFaixa && (
            <span className="linha-evol__legenda-item">
              <svg width="22" height="10" aria-hidden="true">
                <rect x="0" y="2" width="22" height="6" fill="var(--sas-referencia-fraca)" />
              </svg>
              faixa da turma
            </span>
          )}
          {caminhoMedia && (
            <span className="linha-evol__legenda-item">
              <svg width="22" height="10" aria-hidden="true">
                <line x1="0" y1="5" x2="22" y2="5" stroke="var(--sas-referencia)" strokeWidth={1.4} />
              </svg>
              média da turma
            </span>
          )}
        </div>
      )}
    </div>
  );
}

/** A amostra da legenda: o mesmo traço e o mesmo marcador, em miniatura. */
function AmostraDoTraco({ traco }: { traco: TracoDaSerie }) {
  return (
    <svg width="22" height="10" aria-hidden="true">
      <line
        x1="0" y1="5" x2="22" y2="5"
        stroke={traco.cor} strokeWidth={2} strokeDasharray={traco.tracejado}
      />
      <MarcaDaSerie traco={traco} x={11} y={5} r={3} />
    </svg>
  );
}

function Tooltip({
  ref, ponto, cor,
}: {
  ref: React.Ref<HTMLDivElement>;
  ponto: PontoEvolucao;
  cor: string;
  x: number;
  y: number;
}) {
  const delta = ponto.mediaTurma != null ? ponto.nota - ponto.mediaTurma : null;

  const linhas: Array<[string, string]> = [
    ['simulado', ponto.simulado || '—'],
    ['ciclo', ponto.vestibularAlvo ? `C${ponto.cicloOrdem} · ${ponto.vestibularAlvo}` : `C${ponto.cicloOrdem}`],
    ['fase', FASE_LABEL[ponto.tipo ?? ''] || '—'],
    ['data', fmtDataBR(ponto.dataAplicacao)],
  ];

  return (
    <div className="linha-evol__tooltip" ref={ref} style={{ opacity: 1 }}>
      <div className="linha-evol__tt-cab" style={{ borderColor: cor }}>
        {ponto.materia || 'Aluno'}
      </div>
      {linhas.map(([rotulo, valor]) => (
        <div key={rotulo} className="linha-evol__tt-linha">
          <span className="linha-evol__tt-rot">{rotulo}</span>
          <span className="linha-evol__tt-val">{valor}</span>
        </div>
      ))}

      <div className="linha-evol__tt-sep" />
      <div className="linha-evol__tt-linha">
        <span className="linha-evol__tt-rot">sua nota</span>
        <span className="linha-evol__tt-val linha-evol__tt-nota">{fmtNota(ponto.nota)}</span>
      </div>

      {ponto.mediaTurma != null && (
        <>
          <div className="linha-evol__tt-linha">
            <span className="linha-evol__tt-rot">média turma</span>
            <span className="linha-evol__tt-val">{fmtNota(ponto.mediaTurma)}</span>
          </div>
          {/* A seta diz a direção; a cor saiu. O delta era verde subindo e
              vermelho descendo, e CAIR NÃO É RUIM — é informação: uma queda
              de 8,4 para 7,9 pintava de vermelho quem está dois pontos acima
              do corte (R4, o vermelho é só a etiqueta de distância). */}
          <div className="linha-evol__tt-linha">
            <span className="linha-evol__tt-rot">posição</span>
            <span className="linha-evol__tt-val">{`${fmtDelta(delta)} vs média`}</span>
          </div>
        </>
      )}

      {ponto.abandonoProvavel && (
        <div className="linha-evol__tt-aviso">⚠ nota 0 — provável abandono</div>
      )}
    </div>
  );
}
