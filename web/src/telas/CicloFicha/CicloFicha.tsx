import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Histograma } from '../../componentes/ui/Histograma';
import { InsightsPainel } from '../../componentes/ui/InsightsPainel';
import { LinhaTemporal } from '../../componentes/ui/LinhaTemporal';
import { useCiclo, useEstatisticasCiclo, useSimulados } from '../../hooks/consultas';
import type {
  BlocoFase, EstatisticasCiclo, RecorteMateria, Simulado, StatsRecorte,
} from '../../tipos/dominio';
import { fmtDelta, fmtNota } from '../../util/formato';

// Ficha de ciclo — single-page, sem abas nem filtros de fase.
//
// Hierarquia visual:
//   1. Hero (4 KPIs principais)
//   2. Evolução temporal (F1+F2 cronológicos)
//   3. Leitura prática (insights do LLM, em linguagem acessível)
//   4. Análise conjunta (ciclo todo, F1+F2 agregados por aluno)
//   5. Por matéria (F1 e F2 lado a lado)
//   6. Tabela de simulados
//   7. [▼ dados estatísticos avançados] — KPIs de forma/quantis + leitura técnica

const fmtPct = (v: number | null | undefined) =>
  v == null ? '—' : v.toFixed(1).replace('.', ',');

/** Zona crítica alta é problema: acima de 20% vermelho, acima de 10% âmbar. */
function tonePctCritico(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '';
  if (v >= 20) return 'tone-vermelho';
  if (v >= 10) return 'tone-ambar';
  return 'tone-verde';
}

export function CicloFicha() {
  const { id = '' } = useParams();
  const { data: ciclo, isPending: carregandoCiclo, isError: erroCiclo } = useCiclo(id);
  const { data: todos = [] } = useSimulados();
  const { data: stats, isPending: carregandoStats, isError: erroStats } = useEstatisticasCiclo(id);

  const [avancadoAberto, setAvancadoAberto] = useState(false);

  const doCiclo = useMemo(() => {
    if (!ciclo) return [];
    return todos
      .filter((s) => ciclo.simuladoIds.includes(s.id))
      .sort((a, b) => (a.dataAplicacao || '').localeCompare(b.dataAplicacao || ''));
  }, [ciclo, todos]);

  if (carregandoCiclo) {
    return (
      <main className="app-main">
        <section className="card"><div className="empty-state">Carregando…</div></section>
      </main>
    );
  }

  if (erroCiclo || !ciclo) {
    return (
      <main className="app-main">
        <section className="card">
          <div className="empty-state">
            {`Ciclo ${id} não encontrado.`}
            <div className="empty-state__hint">
              <Link to="/ciclos">← Voltar para a lista</Link>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="app-main">
      <section className="card ciclo-ficha">
        <div className="screen-header">
          <div className="screen-breadcrumb">
            <Link to="/ciclos">Ciclos</Link>
            {' / '}
            {ciclo.id}
          </div>
          <h1 className="screen-title">{ciclo.nome}</h1>
          <p className="screen-subtitle">
            {ciclo.vestibularAlvo && (
              <span className="tag tone-navy" style={{ marginRight: 8 }}>{ciclo.vestibularAlvo}</span>
            )}
            {`Período: ${ciclo.periodoInicio || '—'} → ${ciclo.periodoFim || '—'} · ${doCiclo.length} simulados`}
          </p>
        </div>

        {carregandoStats ? (
          <div className="section">
            <p className="section__subtitle">Calculando estatísticas…</p>
          </div>
        ) : erroStats || !stats ? (
          <div className="section">
            <p className="section__subtitle">
              Erro ao calcular estatísticas. Verifique o backend e tente novamente.
            </p>
          </div>
        ) : (
          <>
            <Hero stats={stats} />
            <Evolucao stats={stats} />

            <div className="section">
              <InsightsPainel
                bullets={stats.conjunta?.insights?.pratico ?? null}
                titulo="Leitura do coordenador"
                legenda="Análise em linguagem acessível, gerada a partir dos números do ciclo."
              />
            </div>

            <Conjunta stats={stats} />
            <PorMateria recortes={stats.porMateria ?? []} />
            <TabelaSimuladosDoCiclo simulados={doCiclo} />

            <div className="ciclo-avancado__toggle">
              <button
                className={`ciclo-avancado__btn ${avancadoAberto ? 'is-aberto' : ''}`}
                onClick={() => setAvancadoAberto((v) => !v)}
              >
                {avancadoAberto ? '▲ Esconder' : '▼ Mostrar'} dados estatísticos avançados
              </button>
            </div>

            {avancadoAberto && <Avancado stats={stats} />}
          </>
        )}
      </section>
    </main>
  );
}

// ─── Hero ────────────────────────────────────────────────────────────────

function Hero({ stats }: { stats: EstatisticasCiclo }) {
  const r = stats.resumo ?? {};
  const delta = r.delta ?? {};
  return (
    <div className="section ciclo-hero">
      <div className="ciclo-hero__grid">
        <HeroCard rotulo="Média geral" valor={fmtNota(r.media)} delta={delta.media} />
        <HeroCard rotulo="% aprovados" valor={fmtPct(r.pctAprovados)} delta={delta.pctAprovados} sufixo="%" />
        <HeroCard rotulo="% zona crítica" valor={fmtPct(r.pctZonaCritica)} sufixo="%" tone={tonePctCritico(r.pctZonaCritica)} />
        <HeroCard rotulo="% excelência" valor={fmtPct(r.pctExcelencia)} delta={delta.pctExcelencia} sufixo="%" />
      </div>
      {stats.cicloAnterior && (
        <p className="ciclo-hero__legenda">
          {`Variações comparam com ${stats.cicloAnterior.nome}.`}
        </p>
      )}
    </div>
  );
}

function HeroCard({
  rotulo, valor, delta, sufixo = '', tone = '',
}: {
  rotulo: string;
  valor: string;
  delta?: number | null;
  sufixo?: string;
  tone?: string;
}) {
  return (
    <div className="ciclo-hero__card">
      <div className="ciclo-hero__rotulo">{rotulo}</div>
      <div className={`ciclo-hero__valor ${tone}`}>
        {valor}
        {sufixo && <span className="ciclo-hero__sufixo">{sufixo}</span>}
      </div>
      {delta != null && (
        <div className={`ciclo-hero__delta ${delta > 0 ? 'tone-verde' : delta < 0 ? 'tone-vermelho' : ''}`}>
          {fmtDelta(delta)}
          {sufixo ? ` ${sufixo}` : ' vs anterior'}
        </div>
      )}
    </div>
  );
}

// ─── Evolução temporal ───────────────────────────────────────────────────

function Evolucao({ stats }: { stats: EstatisticasCiclo }) {
  const navegar = useNavigate();
  const pontos = (stats.evolucaoTemporal ?? []).map((p) => ({
    ...p,
    // Sublinha a fase no rótulo curto — F1 e F2 aparecem na mesma série.
    rotuloCurto: p.rotuloCurto ? `${p.rotuloCurto}${p.fase === 'fase_2' ? ' (F2)' : ''}` : null,
  }));

  return (
    <div className="section">
      <div className="section__title">Evolução temporal</div>
      <div className="section__subtitle">
        Médias dos simulados ao longo do ciclo, do mais antigo ao mais recente.
      </div>
      <LinhaTemporal
        pontos={pontos}
        largura={760}
        altura={220}
        corte={{ valor: 4, eliminatoria: false }}
        onPontoClick={(p) => p.simuladoId && navegar(`/simulados/${p.simuladoId}`)}
      />
    </div>
  );
}

// ─── Análise conjunta ────────────────────────────────────────────────────

function Conjunta({ stats }: { stats: EstatisticasCiclo }) {
  const c = stats.conjunta;
  if (!c?.stats || c.stats.n === 0) {
    return (
      <div className="section">
        <p className="section__subtitle">Sem dados suficientes pra análise conjunta.</p>
      </div>
    );
  }

  return (
    <div className="section">
      <div className="section__title">Visão geral do ciclo</div>
      <div className="section__subtitle">
        {`Distribuição da nota média de cada aluno no ciclo todo (F1 + F2 combinados). n = ${c.stats.n} alunos.`}
      </div>
      <div className="ciclo-conjunta__layout">
        <div className="ciclo-conjunta__grafico">
          <Histograma
            payload={c.histograma}
            largura={480}
            altura={200}
            media={c.stats.media}
            mediana={c.stats.mediana}
            corte={c.corte != null ? { valor: c.corte, eliminatoria: false } : null}
            cicloAnterior={c.anterior?.histograma ?? null}
            kde
          />
        </div>
        <div className="ciclo-conjunta__numeros">
          <MiniCard rotulo="Média" valor={fmtNota(c.stats.media)} />
          <MiniCard rotulo="Mediana" valor={fmtNota(c.stats.mediana)} />
          <MiniCard rotulo="Desvio padrão" valor={fmtNota(c.stats.desvioPadrao)} />
          <MiniCard rotulo="Alunos" valor={String(c.stats.n)} />
        </div>
      </div>
    </div>
  );
}

// ─── Por matéria ─────────────────────────────────────────────────────────

function PorMateria({ recortes }: { recortes: RecorteMateria[] }) {
  if (recortes.length === 0) {
    return (
      <div className="section">
        <div className="section__title">Por matéria</div>
        <p className="section__subtitle">Sem simulados por matéria neste ciclo.</p>
      </div>
    );
  }

  return (
    <div className="section">
      <div className="section__title">Por matéria</div>
      <div className="section__subtitle">
        Cada matéria mostra Fase 1 e Fase 2 lado a lado. As linhas tracejadas verticais marcam o corte.
      </div>
      <div className="ciclo-materias">
        {recortes.map((rec) => (
          <BlocoMateria key={rec.materia.codigo} rec={rec} />
        ))}
      </div>
    </div>
  );
}

function BlocoMateria({ rec }: { rec: RecorteMateria }) {
  return (
    <div className="ciclo-materia">
      <div className="ciclo-materia__cabecalho">
        <h3 className="ciclo-materia__titulo">
          {rec.materia.nome}
          {rec.eliminatoriaF1 && (
            <span className="tag tone-vermelho" style={{ marginLeft: 8 }}>F1 ELIMINATÓRIA</span>
          )}
        </h3>
        <ResumoF1F2 rec={rec} />
      </div>

      <div className="ciclo-materia__graficos">
        {/* Corte 5 na F1 eliminatória (Inglês no ITA); 4 nos demais casos. */}
        <MiniHistogramaFase bloco={rec.fase1} label="Fase 1" corte={rec.eliminatoriaF1 ? 5 : 4} eliminatoria={!!rec.eliminatoriaF1} />
        <MiniHistogramaFase bloco={rec.fase2} label="Fase 2" corte={4} eliminatoria={false} />
      </div>

      <InsightsPainel
        bullets={rec.insights?.pratico ?? null}
        titulo={`Leitura — ${rec.materia.nome}`}
        legenda=""
      />
    </div>
  );
}

function ResumoF1F2({ rec }: { rec: RecorteMateria }) {
  const f1 = rec.fase1?.stats;
  const f2 = rec.fase2?.stats;
  const delta = rec.deltaF1F2;

  return (
    <div className="ciclo-materia__resumo">
      <MiniBadge rotulo="Média F1" valor={f1 ? fmtNota(f1.media) : '—'} />
      <span className="ciclo-materia__seta">→</span>
      <MiniBadge rotulo="Média F2" valor={f2 ? fmtNota(f2.media) : '—'} delta={delta?.media} />
      <MiniBadge rotulo="Aprovados F1" valor={f1 ? `${fmtPct(f1.pctAprovados)}%` : '—'} />
      <span className="ciclo-materia__seta">→</span>
      <MiniBadge
        rotulo="Aprovados F2"
        valor={f2 ? `${fmtPct(f2.pctAprovados)}%` : '—'}
        delta={delta?.pctAprovados}
        sufixo="%"
      />
    </div>
  );
}

function MiniHistogramaFase({
  bloco, label, corte, eliminatoria,
}: {
  bloco: BlocoFase | null;
  label: string;
  corte: number;
  eliminatoria: boolean;
}) {
  if (!bloco || bloco.stats.n === 0) {
    return (
      <div className="ciclo-materia__hist-vazio">
        <div className="ciclo-materia__hist-label">{label}</div>
        <p className="empty-state">{`Sem dados de ${label}.`}</p>
      </div>
    );
  }

  return (
    <div className="ciclo-materia__hist">
      <div className="ciclo-materia__hist-label">
        {label}
        <span className="ciclo-materia__hist-n">{`  n = ${bloco.stats.n}`}</span>
      </div>
      <Histograma
        payload={bloco.histograma}
        largura={320}
        altura={140}
        media={bloco.stats.media}
        mediana={bloco.stats.mediana}
        corte={{ valor: corte, eliminatoria }}
      />
    </div>
  );
}

// ─── Tabela de simulados ─────────────────────────────────────────────────

function TabelaSimuladosDoCiclo({ simulados }: { simulados: Simulado[] }) {
  const navegar = useNavigate();
  return (
    <div className="section">
      <div className="section__title">Simulados no ciclo</div>
      {simulados.length === 0 ? (
        <p className="section__subtitle">Ciclo sem simulados associados.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Simulado</th>
              <th>Data</th>
              <th>Média</th>
              <th>Mediana</th>
              <th>Desvio</th>
              <th>Presentes</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {simulados.map((s) => (
              <tr key={s.id} onClick={() => navegar(`/simulados/${s.id}`)}>
                <td>{s.nome}</td>
                <td>{s.dataAplicacao}</td>
                <td>{fmtNota(s.media)}</td>
                <td>{fmtNota(s.mediana)}</td>
                <td>{fmtNota(s.desvioPadrao)}</td>
                <td>{String(s.nPresentes ?? '—')}</td>
                <td>
                  <Link to={`/simulados/${s.id}`} onClick={(ev) => ev.stopPropagation()}>Ver →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── Dados avançados ─────────────────────────────────────────────────────

function Avancado({ stats }: { stats: EstatisticasCiclo }) {
  return (
    <div className="section ciclo-avancado">
      <div className="section__title">Dados estatísticos avançados</div>
      <div className="section__subtitle">
        Forma da distribuição, quantis e dispersão para cada recorte. Inclui leitura técnica em
        jargão estatístico.
      </div>

      <div className="ciclo-avancado__bloco">
        <h3 className="ciclo-avancado__h">Visão geral do ciclo</h3>
        <GridAvancado stats={stats.conjunta?.stats} />
        <InsightsPainel
          bullets={stats.conjunta?.insights?.tecnico ?? null}
          titulo="Leitura técnica — visão geral"
          legenda="Análise com jargão estatístico."
        />
      </div>

      {(stats.porMateria ?? []).map((rec) => (
        <div key={rec.materia.codigo} className="ciclo-avancado__bloco">
          <h3 className="ciclo-avancado__h">
            {rec.materia.nome}
            {rec.eliminatoriaF1 && (
              <span className="tag tone-vermelho" style={{ marginLeft: 8 }}>F1 ELIM.</span>
            )}
          </h3>
          <div className="ciclo-avancado__fases">
            {rec.fase1 && (
              <div className="ciclo-avancado__fase">
                <div className="ciclo-avancado__fase-label">Fase 1</div>
                <GridAvancado stats={rec.fase1.stats} />
              </div>
            )}
            {rec.fase2 && (
              <div className="ciclo-avancado__fase">
                <div className="ciclo-avancado__fase-label">Fase 2</div>
                <GridAvancado stats={rec.fase2.stats} />
              </div>
            )}
          </div>
          <InsightsPainel
            bullets={rec.insights?.tecnico ?? null}
            titulo={`Leitura técnica — ${rec.materia.nome}`}
            legenda=""
          />
        </div>
      ))}
    </div>
  );
}

function GridAvancado({ stats }: { stats?: StatsRecorte | null }) {
  if (!stats || stats.n === 0) return <p className="section__subtitle">Sem dados.</p>;

  const doisDigitos = (v: number | null | undefined) =>
    v == null ? '—' : v.toFixed(2).replace('.', ',');

  return (
    <div className="ciclo-avancado__grupos">
      <Grupo titulo="Dispersão">
        <MiniCard rotulo="Desvio padrão" valor={fmtNota(stats.desvioPadrao)} />
        <MiniCard rotulo="IQR" valor={fmtNota(stats.iqr)} />
        <MiniCard rotulo="Amplitude" valor={fmtNota(stats.amplitude)} />
        <MiniCard rotulo="Moda" valor={fmtNota(stats.moda)} />
      </Grupo>

      <Grupo titulo="Quantis">
        <MiniCard rotulo="P10" valor={fmtNota(stats.p10)} />
        <MiniCard rotulo="P25" valor={fmtNota(stats.p25)} />
        <MiniCard rotulo="P75" valor={fmtNota(stats.p75)} />
        <MiniCard rotulo="P90" valor={fmtNota(stats.p90)} />
      </Grupo>

      <Grupo titulo="Forma">
        <MiniCard
          rotulo="Assimetria"
          valor={doisDigitos(stats.skewness)}
          tooltip="Skewness. Positivo: cauda à direita. |valor| > 1 = forte assimetria."
        />
        <MiniCard
          rotulo="Curtose"
          valor={doisDigitos(stats.curtose)}
          tooltip="Excesso de curtose. Positivo: caudas pesadas (outliers)."
        />
        <div className="mini-card">
          <div className="mini-card__rotulo">Bimodal?</div>
          <div className={`mini-card__valor ${stats.bimodal ? 'tone-ambar' : 'tone-navy'}`}>
            {stats.bimodal ? 'Sim' : 'Não'}
          </div>
        </div>
      </Grupo>

      <Grupo titulo="Taxas">
        <MiniCard rotulo="% aprovados" valor={`${fmtPct(stats.pctAprovados)}%`} />
        <MiniCard rotulo="% zona crítica" valor={`${fmtPct(stats.pctZonaCritica)}%`} tone={tonePctCritico(stats.pctZonaCritica)} />
        <MiniCard rotulo="% excelência" valor={`${fmtPct(stats.pctExcelencia)}%`} />
      </Grupo>
    </div>
  );
}

// ─── Blocos pequenos ─────────────────────────────────────────────────────

function Grupo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="ciclo-avancado__grupo">
      <div className="ciclo-avancado__grupo-titulo">{titulo}</div>
      <div className="mini-cards">{children}</div>
    </div>
  );
}

function MiniCard({
  rotulo, valor, tooltip, tone = '',
}: {
  rotulo: string;
  valor: string;
  tooltip?: string;
  tone?: string;
}) {
  return (
    <div className="mini-card" title={tooltip || undefined}>
      <div className="mini-card__rotulo">{rotulo}</div>
      <div className={`mini-card__valor ${tone}`}>{valor}</div>
    </div>
  );
}

function MiniBadge({
  rotulo, valor, delta = null, sufixo = '',
}: {
  rotulo: string;
  valor: string;
  delta?: number | null;
  sufixo?: string;
}) {
  return (
    <div className="mini-badge">
      <span className="mini-badge__rotulo">{rotulo}</span>
      <span className="mini-badge__valor">{valor}</span>
      {delta != null && (
        <span className={`mini-badge__delta ${delta > 0 ? 'tone-verde' : delta < 0 ? 'tone-vermelho' : ''}`}>
          {` ${fmtDelta(delta)}${sufixo ? ' ' + sufixo : ''}`}
        </span>
      )}
    </div>
  );
}
