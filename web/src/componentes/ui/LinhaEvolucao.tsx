import { useLayoutEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fmtDataBR } from '../../util/data';
import { fmtNota } from '../../util/formato';

// Gráfico de linha da evolução do aluno por ciclo.
// Eixo X = ciclos categóricos (C1, C2…). Eixo Y = nota 0–10, fixa.
// Suporta várias séries (uma linha por matéria) e tooltip detalhado.

/** Paleta das séries por matéria — alinhada ao design system. */
const CORES_SERIE = [
  'var(--color-navy)',
  '#c97c2a', // âmbar
  '#1b8a5a', // verde
  '#a23b3b', // vermelho
  '#6b4cb3', // roxo
  '#2a8fb3', // ciano
];

const FASE_LABEL: Record<string, string> = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

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
  cor?: string;
  pontos: PontoEvolucao[];
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

interface EstadoTooltip {
  ponto: PontoEvolucao;
  cor: string;
  x: number;
  y: number;
}

export function LinhaEvolucao({
  series, ciclosEixo, corte, corteRotulo, altura = 320,
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

  function mostrarTooltip(ev: React.MouseEvent, ponto: PontoEvolucao, cor: string) {
    const wrapper = refWrapper.current;
    if (!wrapper) return;
    const rect = wrapper.getBoundingClientRect();
    setTooltip({ ponto, cor, x: ev.clientX - rect.left, y: ev.clientY - rect.top });
  }

  const yCorte = corte != null ? yDe(corte) : null;

  return (
    <div className="linha-evol" ref={refWrapper}>
      {tooltip && <Tooltip ref={refTooltip} {...tooltip} />}

      <svg
        className="linha-evol__svg"
        width="100%"
        viewBox={`0 0 ${larguraTotal} ${altura}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <g className="linha-evol__grid">
          {[0, 2, 4, 6, 8, 10].map((tick) => {
            const y = yDe(tick);
            return (
              <g key={tick}>
                <line
                  x1={margem.left} y1={y} x2={margem.left + plotW} y2={y}
                  stroke="var(--color-border)" strokeWidth={1}
                />
                <text
                  x={margem.left - 6} y={y + 3.5}
                  textAnchor="end" fontSize={10} fill="var(--color-text-tertiary)"
                >
                  {tick}
                </text>
              </g>
            );
          })}
        </g>

        {yCorte != null && (
          <>
            <line
              x1={margem.left} y1={yCorte} x2={margem.left + plotW} y2={yCorte}
              stroke="var(--color-red, #c44)" strokeWidth={1.2} strokeDasharray="4 4" opacity={0.7}
            />
            <text
              x={margem.left + plotW - 6} y={yCorte - 4}
              textAnchor="end" fontSize={10} fill="var(--color-red, #c44)" opacity={0.85}
            >
              {corteRotulo}
            </text>
          </>
        )}

        {ciclosEixo.map((c) => (
          <text
            key={c.ordem}
            x={xDe(c.ordem) ?? 0} y={margem.top + plotH + 18}
            textAnchor="middle" fontSize={11} fill="var(--color-text-secondary)"
          >
            {c.label}
          </text>
        ))}

        {series.map((serie, idx) => {
          const cor = serie.cor || CORES_SERIE[idx % CORES_SERIE.length];
          const ordenados = serie.pontos
            .filter((p) => p.cicloOrdem != null && indicePorOrdem.has(p.cicloOrdem) && p.nota != null)
            .sort((a, b) => indicePorOrdem.get(a.cicloOrdem!)! - indicePorOrdem.get(b.cicloOrdem!)!);

          if (!ordenados.length) return null;

          return (
            <g key={serie.nome || idx}>
              {ordenados.length >= 2 && (
                <path
                  d={caminhoSuave(ordenados.map((p) => [xDe(p.cicloOrdem)!, yDe(p.nota)]))}
                  fill="none" stroke={cor} strokeWidth={2}
                  strokeLinejoin="round" strokeLinecap="round"
                />
              )}
              {ordenados.map((p, i) => (
                <circle
                  key={p.simuladoId ?? `${serie.nome}-${i}`}
                  className="linha-evol__ponto"
                  cx={xDe(p.cicloOrdem)!} cy={yDe(p.nota)} r={4}
                  // Abandono provável vira marcador sólido vermelho, para saltar aos olhos.
                  fill={p.abandonoProvavel ? 'var(--color-red, #c44)' : '#fff'}
                  stroke={p.abandonoProvavel ? '#fff' : cor}
                  strokeWidth={2}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={(ev) => mostrarTooltip(ev, p, cor)}
                  onMouseMove={(ev) => mostrarTooltip(ev, p, cor)}
                  onMouseLeave={() => setTooltip(null)}
                  onClick={() => p.simuladoId && navegar(`/simulados/${p.simuladoId}`)}
                />
              ))}
            </g>
          );
        })}
      </svg>

      {(series.length > 1 || series[0]?.nome) && (
        <div className="linha-evol__legenda">
          {series.map((serie, idx) =>
            serie.pontos.length ? (
              <span key={serie.nome || idx} className="linha-evol__legenda-item">
                <span
                  className="linha-evol__legenda-swatch"
                  style={{ background: serie.cor || CORES_SERIE[idx % CORES_SERIE.length] }}
                />
                {serie.nome}
              </span>
            ) : null,
          )}
        </div>
      )}
    </div>
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
  const toneDelta = delta == null ? '' : delta > 0.1 ? 'tone-verde' : delta < -0.1 ? 'tone-vermelho' : '';

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
          <div className="linha-evol__tt-linha">
            <span className="linha-evol__tt-rot">posição</span>
            <span className={`linha-evol__tt-val ${toneDelta}`}>
              {`${delta! > 0 ? '+' : ''}${delta!.toFixed(1).replace('.', ',')} vs média`}
            </span>
          </div>
        </>
      )}

      {ponto.abandonoProvavel && (
        <div className="linha-evol__tt-aviso">⚠ nota 0 — provável abandono</div>
      )}
    </div>
  );
}
