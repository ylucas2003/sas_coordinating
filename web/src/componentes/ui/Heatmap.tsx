// Heatmap matérias × simulados, agrupado por ciclo.
//
// Layout (3 níveis de cabeçalho):
//   [Ciclo 1 · IME]  [Ciclo 2 · IME]  [Ciclo 3 · ITA]
//   [  F1   ][ F2 ]  [F1 ][ F2  ]     [   F1     ]
//   P1 P2    P3 P4   P5  P6 P7         P8 P9 P10
//   09/02   24/03    ...
//
// Bandas verticais alternadas separam ciclos visualmente.

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

function hexParaRgb(h: string): [number, number, number] {
  const x = h.replace('#', '');
  return [
    parseInt(x.slice(0, 2), 16),
    parseInt(x.slice(2, 4), 16),
    parseInt(x.slice(4, 6), 16),
  ];
}

function misturar(hexA: string, hexB: string, t: number): string {
  const a = hexParaRgb(hexA);
  const b = hexParaRgb(hexB);
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

/** Degradê vermelho → âmbar → verde sobre a razão nota/máximo. */
function corPorNota(v: number, max: number): string {
  const razao = Math.max(0, Math.min(1, v / max));
  return razao < 0.5
    ? misturar('#d9354a', '#e89b2a', razao / 0.5)
    : misturar('#e89b2a', '#2e8c5a', (razao - 0.5) / 0.5);
}

interface Props {
  payload: PayloadHeatmap | null | undefined;
  notaMaxima?: number;
}

export function Heatmap({ payload, notaMaxima = 10 }: Props) {
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
                        style={{ background: corPorNota(v, notaMaxima), color: '#fff' }}
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
