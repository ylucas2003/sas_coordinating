// Heatmap matérias × simulados, agrupado por ciclo.
//
// Layout (3 níveis de cabeçalho):
//   [Ciclo 1 · IME]  [Ciclo 2 · IME]  [Ciclo 3 · ITA]
//   [  F1   ][ F2 ]  [F1 ][ F2  ]     [   F1     ]
//   P1 P2    P3 P4   P5  P6 P7         P8 P9 P10
//   09/02   24/03    ...
//
// Bandas verticais alternadas separam ciclos visualmente.

import { seloDaNota } from '../../dominio/selo';

const CELL_W = 50;
const CELL_H = 30;
const LABEL_W = 110;

const FASE_LABEL: Record<string, string> = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

export interface SimuladoHeatmap {
  id: string;
  nome: string;
  rotulo?: string | null;
  dataAplicacao?: string | null;
  cicloId?: string | null;
  cicloOrdem?: number | null;
  cicloNome?: string | null;
  vestibularAlvo?: string | null;
  fase?: string | null;
}

export interface PayloadHeatmap {
  materias: string[];
  simulados: SimuladoHeatmap[];
  celulas: Array<{ materia: string; simuladoId: string; pontuacao: number | null }>;
}

interface Grupo {
  cicloId?: string | null;
  cicloOrdem?: number | null;
  cicloNome?: string | null;
  vestibularAlvo?: string | null;
  faixa: 'A' | 'B';
  fases: Array<{ fase?: string | null; simulados: SimuladoHeatmap[] }>;
}

const fmt = (n: number | null | undefined) => (n == null ? '—' : n.toFixed(1).replace('.', ','));

function dataCurta(iso: string | null | undefined): string {
  if (!iso) return '';
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}` : iso;
}

/**
 * Agrupa sequencialmente: cada mudança de `cicloId` abre um grupo novo, e
 * dentro dele cada mudança de fase abre um subgrupo. Sequencial, e não por
 * chave, porque o backend já entrega ordenado por ciclo/fase/data — e a ordem
 * é o que dá sentido ao eixo.
 */
function agruparPorCiclo(simulados: SimuladoHeatmap[]): Grupo[] {
  const grupos: Grupo[] = [];
  let atual: Grupo | null = null;
  let faixa: 'A' | 'B' = 'A';

  for (const s of simulados) {
    const cId = s.cicloId || `_sem_${s.fase || 'na'}`;
    if (!atual || (atual.cicloId || `_sem_${atual.fases[0]?.fase || 'na'}`) !== cId) {
      atual = {
        cicloId: s.cicloId,
        cicloOrdem: s.cicloOrdem,
        cicloNome: s.cicloNome,
        vestibularAlvo: s.vestibularAlvo,
        faixa,
        fases: [],
      };
      faixa = faixa === 'A' ? 'B' : 'A';
      grupos.push(atual);
    }
    const ultimaFase = atual.fases[atual.fases.length - 1];
    if (!ultimaFase || ultimaFase.fase !== s.fase) {
      atual.fases.push({ fase: s.fase, simulados: [s] });
    } else {
      ultimaFase.simulados.push(s);
    }
  }
  return grupos;
}

/**
 * A célula do heatmap, pelas mesmas regras da tabela (R1 e R3).
 *
 * ⚠️ Substitui um degradê VERMELHO → ÂMBAR → VERDE, que era o último semáforo
 * do app e infringia duas regras de uma vez: era divergente de duas cores
 * quando a escala tem de ser sequencial de matiz único ancorada NO CORTE, e
 * era cor cravada em hexadecimal, que não sobreviveria ao tema escuro.
 *
 * Com corte, a célula é preenchida acima e vazada abaixo, e a distância modula
 * a intensidade. Sem corte não há régua a ancorar: a célula vira uma rampa
 * sequencial de DADO sobre a razão nota/máximo — menos informação, e é honesto
 * que pareça menos.
 */
function estiloDaCelula(
  v: number,
  max: number,
  corte: number | null | undefined,
): React.CSSProperties {
  const selo = seloDaNota(v, corte, max);

  if (selo.estado === 'sem-dado') {
    const razao = Math.max(0, Math.min(1, v / max));
    return {
      background: `color-mix(in srgb, var(--color-dado) ${Math.round(18 + razao * 72)}%, transparent)`,
      color: razao > 0.55 ? 'var(--color-dado-texto-forte)' : 'var(--color-magnitude)',
    };
  }

  if (selo.estado === 'abaixo') {
    const espessura = (1 + selo.intensidade * 1.6).toFixed(1);
    const tinta = Math.round(30 + selo.intensidade * 55);
    return {
      background: 'transparent',
      boxShadow: `inset 0 0 0 ${espessura}px color-mix(in srgb, var(--color-magnitude) ${tinta}%, transparent)`,
      color: 'var(--color-magnitude)',
    };
  }

  const mistura = Math.round(22 + selo.intensidade * 78);
  return {
    background: `color-mix(in srgb, var(--color-dado) ${mistura}%, transparent)`,
    color: selo.intensidade > 0.5 ? 'var(--color-dado-texto-forte)' : 'var(--color-magnitude)',
  };
}

interface Props {
  payload: PayloadHeatmap | null | undefined;
  notaMaxima?: number;
  /** O corte da régua em vigor. Sem ele a célula não tem onde ancorar (R2). */
  corte?: number | null;
}

export function Heatmap({ payload, notaMaxima = 10, corte = null }: Props) {
  if (!payload || !Array.isArray(payload.materias) || payload.materias.length === 0) {
    return <div className="empty-state">Sem notas suficientes para o heatmap.</div>;
  }

  const { materias, simulados, celulas } = payload;
  const indice = new Map(celulas.map((c) => [`${c.materia}|${c.simuladoId}`, c.pontuacao]));
  const grupos = agruparPorCiclo(simulados);

  const classeFaixa = (g: Grupo) => (g.faixa === 'A' ? 'faixa-a' : 'faixa-b');

  return (
    <div className="heatmap__container">
      <table
        className="heatmap heatmap--agrupado"
        style={
          {
            '--cell-w': `${CELL_W}px`,
            '--cell-h': `${CELL_H}px`,
            '--label-w': `${LABEL_W}px`,
          } as React.CSSProperties
        }
      >
        <thead>
          <tr className="heatmap__head heatmap__head-ciclo">
            <th className="heatmap__th-canto" />
            {grupos.map((g, i) => (
              <th
                key={i}
                className={`heatmap__th-ciclo ${classeFaixa(g)}`}
                colSpan={g.fases.reduce((acc, f) => acc + f.simulados.length, 0)}
              >
                {g.cicloOrdem != null ? `Ciclo ${g.cicloOrdem}` : g.cicloNome || 'Sem ciclo'}
                {g.vestibularAlvo && (
                  <span className="heatmap__th-vestibular">{` · ${g.vestibularAlvo}`}</span>
                )}
              </th>
            ))}
          </tr>

          <tr className="heatmap__head heatmap__head-fase">
            <th className="heatmap__th-canto" />
            {grupos.flatMap((g, gi) =>
              g.fases.map((f, fi) => (
                <th
                  key={`${gi}-${fi}`}
                  className={`heatmap__th-fase ${classeFaixa(g)} ${fi > 0 ? 'borda-esq' : ''}`}
                  colSpan={f.simulados.length}
                >
                  {FASE_LABEL[f.fase ?? ''] || '—'}
                </th>
              )),
            )}
          </tr>

          <tr className="heatmap__head heatmap__head-sim">
            <th className="heatmap__th-canto" />
            {grupos.flatMap((g, gi) =>
              g.fases.flatMap((f, fi) =>
                f.simulados.map((s, si) => (
                  <th
                    key={`${gi}-${fi}-${s.id}`}
                    className={`heatmap__th-sim ${classeFaixa(g)} ${fi > 0 && si === 0 ? 'borda-esq' : ''}`}
                    title={`${s.nome} · ${s.dataAplicacao}`}
                  >
                    <div className="heatmap__th-pn">{s.rotulo || s.nome}</div>
                    <div className="heatmap__th-data">{dataCurta(s.dataAplicacao)}</div>
                  </th>
                )),
              ),
            )}
          </tr>
        </thead>

        <tbody>
          {materias.map((m) => (
            <tr key={m}>
              <th className="heatmap__th-mat">{m}</th>
              {grupos.flatMap((g, gi) =>
                g.fases.flatMap((f, fi) =>
                  f.simulados.map((s, si) => {
                    const base = `heatmap__cel ${classeFaixa(g)} ${fi > 0 && si === 0 ? 'borda-esq' : ''}`;
                    const v = indice.get(`${m}|${s.id}`);
                    if (v == null) {
                      return <td key={`${gi}-${fi}-${s.id}`} className={`${base} vazio`} />;
                    }
                    return (
                      <td
                        key={`${gi}-${fi}-${s.id}`}
                        className={base}
                        style={estiloDaCelula(v, notaMaxima, corte)}
                        title={`${m} · ${s.rotulo || s.nome} (${s.dataAplicacao}): ${fmt(v)}`}
                      >
                        {fmt(v)}
                      </td>
                    );
                  }),
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
