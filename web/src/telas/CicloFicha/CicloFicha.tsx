import { useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { BlocoPendenciasCanvas } from './PendenciasCanvas';
import { exportarDossiePdf, exportarDossieWord } from './dossie';
import { Histograma } from '../../componentes/ui/Histograma';
import { GraficoEmCamadas } from '../../componentes/ui/GraficoEmCamadas';
import { InsightsPainel } from '../../componentes/ui/InsightsPainel';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { LinhaTemporal } from '../../componentes/ui/LinhaTemporal';
import { lerDistribuicao, lerDuasFases, lerEvolucao } from '../../dominio/leituraDeGrafico';
import { useCiclo, useCriteriosDisponiveis, useEstatisticasCiclo, useSimulados } from '../../hooks/consultas';
import { useRecorteDaTela, useTituloDaTela } from '../../componentes/layout/migalhas';
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
  // A régua escolhida decide TODOS os cortes desta tela — a linha vertical de
  // cada histograma, a da evolução e o pctAprovados. Antes eram números
  // escritos aqui (4 e 5), então trocar a régua no Painel não mexia em nada
  // aqui (docs/31 §0.4).
  const [criterio, setCriterio] = useState('tio-leo');
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const { data: stats, isPending: carregandoStats, isError: erroStats } = useEstatisticasCiclo(id, criterio);

  const [avancadoAberto, setAvancadoAberto] = useState(false);
  const [erroDossie, setErroDossie] = useState('');
  const [gerandoDossie, setGerandoDossie] = useState(false);
  // A raiz da ficha: é dela que o dossiê colhe os `<svg>` que já estão
  // desenhados. Redesenhá-los fora da árvore para exportar seria manter dois
  // desenhos do mesmo gráfico, e eles divergiriam no primeiro ajuste.
  const refFicha = useRef<HTMLDivElement>(null);

  const doCiclo = useMemo(() => {
    if (!ciclo) return [];
    return todos
      .filter((s) => ciclo.simuladoIds.includes(s.id))
      .sort((a, b) => (a.dataAplicacao || '').localeCompare(b.dataAplicacao || ''));
  }, [ciclo, todos]);

  // Antes de qualquer return: hook não pode ficar atrás de saída antecipada.
  useTituloDaTela(ciclo?.nome);
  useRecorteDaTela(useMemo(() => ({ cicloId: id, criterio }), [id, criterio]));

  if (carregandoCiclo) {
    return (
      <div className="tela">
        <section className="card"><div className="empty-state">Carregando…</div></section>
      </div>
    );
  }

  if (erroCiclo || !ciclo) {
    return (
      <div className="tela">
        <section className="card">
          <div className="empty-state">
            {`Ciclo ${id} não encontrado.`}
            <div className="empty-state__hint">
              <Link to="/provas">← Voltar para a lista</Link>
            </div>
          </div>
        </section>
      </div>
    );
  }

  async function gerarDossie(formato: 'pdf' | 'word') {
    if (!stats || !ciclo) return;
    setErroDossie('');
    setGerandoDossie(true);
    try {
      // Todos os `<svg>` da ficha, na ordem em que aparecem. Os títulos vêm do
      // cabeçalho de seção mais próximo acima de cada um — o documento herda a
      // narrativa da tela em vez de inventar uma.
      const svgs = Array.from(refFicha.current?.querySelectorAll('svg') ?? []);
      const graficos = svgs.map((svg) => ({
        titulo: tituloDoGrafico(svg),
        svg: svg as SVGSVGElement,
      }));
      const dados = {
        ciclo,
        stats,
        simulados: doCiclo,
        nomeCriterio: criterios.find((c) => c.slug === criterio)?.nome ?? criterio,
        graficos,
      };
      if (formato === 'pdf') await exportarDossiePdf(dados);
      else await exportarDossieWord(dados);
    } catch (e) {
      setErroDossie((e as Error).message || 'Não consegui gerar o dossiê.');
    } finally {
      setGerandoDossie(false);
    }
  }

  return (
    <div className="tela" ref={refFicha}>
      <section className="card ciclo-ficha">
        <div className="screen-header">
          <div className="screen-breadcrumb">{ciclo.id}</div>
          <h1 className="screen-title">{ciclo.nome}</h1>
          <p className="screen-subtitle">
            {ciclo.vestibularAlvo && (
              <span className="tag tone-navy" style={{ marginRight: 8 }}>{ciclo.vestibularAlvo}</span>
            )}
            {`Período: ${ciclo.periodoInicio || '—'} → ${ciclo.periodoFim || '—'} · ${doCiclo.length} simulados`}
          </p>
          <div className="ciclo-ficha__regua">
            <span className="ciclo-ficha__regua-rotulo">Régua de corte</span>
            <SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />
            {/* O dossiê é o mesmo conteúdo da tela em documento — texto,
                gráfico e tabela — para levar à reunião (docs/33 §5). Fica
                junto da régua porque ela decide os números que ele carrega. */}
            {stats && (
              <>
                <button
                  className="btn-editar-sim"
                  disabled={gerandoDossie}
                  onClick={() => gerarDossie('pdf')}
                >
                  {gerandoDossie ? 'Gerando…' : 'Dossiê PDF'}
                </button>
                <button
                  className="btn-editar-sim"
                  disabled={gerandoDossie}
                  onClick={() => gerarDossie('word')}
                >
                  Dossiê Word
                </button>
              </>
            )}
          </div>
          {erroDossie && <div className="agendar__erro">{erroDossie}</div>}
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

            {/* A "Leitura do coordenador" solta saiu daqui: são os mesmos
                bullets do `conjunta.insights.pratico`, que agora aparecem na
                camada "Leitura" do gráfico a que se referem. Soltos no meio
                da página, eles falavam de um recorte que o leitor tinha de
                adivinhar (docs/31 §P5). */}
            <Conjunta stats={stats} />
            <PorMateria recortes={stats.porMateria ?? []} />
            <BlocoPendenciasCanvas cicloId={ciclo.id} canvasEstado={ciclo.canvasEstado} />
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
    </div>
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
  // A linha do corte sai da régua que gerou o payload. Era `valor: 4` escrito
  // aqui — a mesma regra-como-código que a Sprint 2 tirou do Painel e que
  // tinha sobrevivido nos gráficos (docs/31 §0.4).
  const corteMedia = stats.conjunta?.corte;
  const pontos = (stats.evolucaoTemporal ?? []).map((p) => ({
    ...p,
    // Sublinha a fase no rótulo curto — F1 e F2 aparecem na mesma série.
    rotuloCurto: p.rotuloCurto ? `${p.rotuloCurto}${p.fase === 'fase_2' ? ' (F2)' : ''}` : null,
  }));

  return (
    <div className="section">
      <GraficoEmCamadas
        titulo="Evolução temporal"
        legenda="Médias dos simulados ao longo do ciclo, do mais antigo ao mais recente."
        frase={lerEvolucao(pontos.map((p) => p.media), 'A média do ciclo')}
        insight={stats.conjunta?.insights?.pratico ?? null}
        insightTecnico={stats.conjunta?.insights?.tecnico ?? null}
        grafico={() => (
          <LinhaTemporal
            pontos={pontos}
            largura={760}
            altura={220}
            corte={corteMedia != null ? { valor: corteMedia, eliminatoria: false } : null}
            onPontoClick={(p) => p.simuladoId && navegar(`/simulados/${p.simuladoId}`)}
          />
        )}
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

  const leitura = lerDistribuicao({
    histograma: c.histograma,
    media: c.stats.media,
    corte: c.corte,
    rotuloGrupo: 'dos alunos do ciclo',
  });

  return (
    <div className="section">
      <GraficoEmCamadas
        titulo="Visão geral do ciclo"
        legenda={`Distribuição da nota média de cada aluno no ciclo todo (F1 + F2 combinados). n = ${c.stats.n} alunos.`}
        frase={leitura?.frase ?? null}
        insight={c.insights?.pratico ?? null}
        insightTecnico={c.insights?.tecnico ?? null}
        grafico={(camada) => {
          // Comparação com o ciclo anterior, curva de densidade e eixo Y
          // absoluto são leitura de quem já sabe ler histograma. Na camada
          // leigo seriam três elementos a mais sem explicação nenhuma.
          const fundo = camada === 'estatistica';
          return (
          <div className="ciclo-conjunta__layout">
            <div className="ciclo-conjunta__grafico">
              <Histograma
                payload={c.histograma}
                largura={480}
                altura={200}
                media={c.stats.media}
                mediana={c.stats.mediana}
                corte={c.corte != null ? { valor: c.corte, eliminatoria: false } : null}
                cicloAnterior={fundo ? c.anterior?.histograma ?? null : null}
                kde={fundo}
                eixoYAbsoluto={fundo ? {} : null}
              />
            </div>
            <div className="ciclo-conjunta__numeros">
              <MiniCard rotulo="Média" valor={fmtNota(c.stats.media)} />
              <MiniCard rotulo="Mediana" valor={fmtNota(c.stats.mediana)} />
              <MiniCard rotulo="Desvio padrão" valor={fmtNota(c.stats.desvioPadrao)} />
              <MiniCard rotulo="Alunos" valor={String(c.stats.n)} />
            </div>
          </div>
          );
        }}
        estatistica={<GridAvancado stats={c.stats} />}
      />
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
        Cada matéria mostra Fase 1 e Fase 2 lado a lado. As linhas tracejadas verticais marcam o corte que a régua em uso exige naquela matéria.
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
          {rec.eliminatoria && (
            <span className="tag tone-vermelho" style={{ marginLeft: 8 }}>ELIMINATÓRIA</span>
          )}
        </h3>
        <ResumoF1F2 rec={rec} />
      </div>

      <GraficoEmCamadas
        frase={lerDuasFases({
          fase1: { histograma: rec.fase1?.histograma, media: rec.fase1?.stats.media },
          fase2: { histograma: rec.fase2?.histograma, media: rec.fase2?.stats.media },
          corte: rec.corte,
          deltaMedia: rec.deltaF1F2?.media,
        })}
        insight={rec.insights?.pratico ?? null}
        insightTecnico={rec.insights?.tecnico ?? null}
        grafico={(camada) => (
          <div className="ciclo-materia__graficos">
            {/* Corte e "elimina sozinho" vêm da régua, por matéria. */}
            <MiniHistogramaFase bloco={rec.fase1} label="Fase 1" corte={rec.corte} eliminatoria={!!rec.eliminatoria} kde={camada === 'estatistica'} />
            <MiniHistogramaFase bloco={rec.fase2} label="Fase 2" corte={rec.corte} eliminatoria={!!rec.eliminatoria} kde={camada === 'estatistica'} />
          </div>
        )}
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
  bloco, label, corte, eliminatoria, kde = false,
}: {
  bloco: BlocoFase | null;
  label: string;
  corte?: number | null;
  eliminatoria: boolean;
  /** Curva de densidade — só na camada estatística. */
  kde?: boolean;
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
        corte={corte != null ? { valor: corte, eliminatoria } : null}
        kde={kde}
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
            {rec.eliminatoria && (
              <span className="tag tone-vermelho" style={{ marginLeft: 8 }}>ELIM.</span>
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


/**
 * O título de um gráfico, para o dossiê: o cabeçalho de seção mais próximo
 * acima dele na árvore. Assim o documento herda a narrativa da tela em vez de
 * inventar rótulos que divergiriam no primeiro ajuste de layout.
 */
/**
 * O rótulo da própria peça, quando ela tem um — hoje "Fase 1" / "Fase 2" dos
 * mini-histogramas por matéria.
 *
 * ⚠️ Ele mora num `<div>` IRMÃO do `<svg>` (ver `MiniHistogramaFase`), e o
 * dossiê converte só o `<svg>`. Sem isto, uma matéria com duas fases vira dois
 * `<h2>Física</h2>` seguidos, com gráficos DIFERENTES e nada que diga qual é
 * qual. Na tela ninguém nota — o rótulo está logo acima do desenho; no papel
 * não há hover nem rolagem para conferir. Achado verificando o dossiê gerado.
 */
function rotuloDaPeca(svg: SVGSVGElement): string {
  const caixa = svg.closest('.ciclo-materia__hist, .ciclo-materia__hist-vazio');
  const rotulo = caixa?.querySelector('.ciclo-materia__hist-label');
  // Só o primeiro nó de texto: o `n = 287` vem num <span> ao lado e é ruído
  // num título — ele já aparece dentro do próprio gráfico.
  return rotulo?.firstChild?.textContent?.trim() ?? '';
}

function tituloDoGrafico(svg: SVGSVGElement): string {
  const secao = secaoDoGrafico(svg);
  const peca = rotuloDaPeca(svg);
  if (!peca) return secao;
  return secao === 'Gráfico' ? peca : `${secao} · ${peca}`;
}

/**
 * ⚠️ `textContent` COLA os filhos: um `<h2>Inglês<span>ELIMINATÓRIA</span></h2>`
 * — o selo de matéria que elimina sozinho — virava o título "InglêsELIMINATÓRIA"
 * no dossiê impresso. Juntar nó a nó com espaço e colapsar o resto resolve sem
 * depender de o cabeçalho ter uma estrutura específica.
 */
function textoDoCabecalho(titulo: Element | null | undefined): string {
  if (!titulo) return '';
  return Array.from(titulo.childNodes)
    .map((no) => no.textContent?.trim() ?? '')
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function secaoDoGrafico(svg: SVGSVGElement): string {
  let no: Element | null = svg;
  while (no) {
    const anterior: Element | null = no.previousElementSibling;
    if (anterior) {
      const titulo = anterior.matches('h1, h2, h3, .section__title, .camadas__titulo')
        ? anterior
        : anterior.querySelector('h1, h2, h3, .section__title, .camadas__titulo');
      const texto = textoDoCabecalho(titulo);
      if (texto) return texto;
    }
    no = no.parentElement;
    if (no?.classList.contains('ciclo-ficha')) break;
  }
  return 'Gráfico';
}
