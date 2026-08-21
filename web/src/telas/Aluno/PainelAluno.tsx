import { useState } from 'react';
import { Anel, BarraComparacao, GraficoLinha, Icone } from '../../componentes/aluno/graficos';
import type { SerieLinha } from '../../componentes/aluno/graficos';
import { useEvolucaoMe, useInsightMe, useSimuladosMe, useStreakMe, useSimuladoMe } from '../../hooks/aluno';
import type { DetalheSimuladoAluno, EvolucaoAluno, SimuladoDoAluno, Streak } from '../../tipos/aluno';
import { corMateria, fmt, fmtDataCurta } from '../../util/formatoAluno';

// Painel do aluno: saudação + streak, hero (último simulado), comparação com
// a turma, evolução por matéria, insight de IA e conquistas.

const D_CHAMA = 'M12 2c1 4 5 5 5 9a5 5 0 0 1-10 0c0-1.5.6-2.6 1.3-3.5C9 9 9.5 8 9 6c2 1 2.5 2.8 3 4 .8-1 1-2.5 0-8z';

export function PainelAluno({ nome }: { nome: string }) {
  const { data: streak = { count: 0, label: '' } } = useStreakMe();
  const { data: simulados = [], isPending } = useSimuladosMe();
  const { data: evolucao } = useEvolucaoMe();

  // Detalhe do simulado mais recente — traz ranking e comparação com grupos.
  const { data: detalhe } = useSimuladoMe(simulados[0]?.id);

  if (isPending) return <div className="alu-loading">Carregando…</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <Saudacao nome={nome} streak={streak} />
      <Hero detalhe={detalhe ?? null} />

      <div className="alu-painel__grid">
        <div className="alu-painel__col">
          <Evolucao evolucao={evolucao ?? null} />
          <Comparacao detalhe={detalhe ?? null} />
        </div>
        <div className="alu-painel__col">
          <CardIA />
          {(simulados.length > 0 || streak.count > 0) && (
            <Conquistas streak={streak} simulados={simulados} detalhe={detalhe ?? null} />
          )}
        </div>
      </div>
    </div>
  );
}

function Saudacao({ nome, streak }: { nome: string; streak: Streak }) {
  return (
    <div className="alu-greeting">
      <div>
        <div className="alu-greeting__nome">{`Olá, ${nome || 'aluno'}`}</div>
        <div className="alu-greeting__sub">
          Acompanhe sua evolução e identifique onde melhorar.
        </div>
      </div>
      {streak.count > 0 && (
        <div className="alu-streak">
          <Icone d={D_CHAMA} tamanho={15} cor="var(--alu-calm-deep)" espessura={1.5} />
          {`${streak.count} ciclos no fôlego`}
        </div>
      )}
    </div>
  );
}

function Hero({ detalhe }: { detalhe: DetalheSimuladoAluno | null }) {
  if (!detalhe) {
    return (
      <div className="alu-hero">
        <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 14 }}>
          Nenhum simulado corrigido ainda.
        </div>
      </div>
    );
  }

  const { nota, deltaSelf, posicao, total, percentil, nome, rotulo, dataAplicacao, materia, grupos } = detalhe;
  const delta = deltaSelf ?? 0;
  const pct = total > 1 ? 1 - (posicao - 1) / total : 0.5;

  const estatisticas = grupos
    ? [
        { r: 'Aplicado', v: fmtDataCurta(dataAplicacao) },
        { r: 'Matéria', v: materia || '—' },
        { r: 'Percentil', v: percentil != null ? `${percentil}%` : '—' },
        {
          r: 'Acima da média',
          v: grupos.voce != null && grupos.geral != null ? `+${fmt(grupos.voce - grupos.geral)}` : '—',
        },
      ]
    : null;

  return (
    <div className="alu-hero">
      <div className="alu-hero__inner">
        <div className="alu-hero__left">
          <div className="alu-hero__label">
            <span className="alu-hero__label-line" />
            {`${rotulo || nome || '—'} · ${fmtDataCurta(dataAplicacao)}`}
          </div>

          <div className="alu-hero__nota-row">
            <div className="alu-hero__nota">{fmt(nota)}</div>
            <div className="alu-hero__nota-meta">
              <div className="alu-hero__delta">
                <Icone
                  d={delta >= 0 ? 'M12 19V5 M5 12l7-7 7 7' : 'M12 5v14 M19 12l-7 7-7-7'}
                  tamanho={12} cor="#fff" espessura={2.4}
                />
                {`${delta >= 0 ? '+' : ''}${fmt(delta)} vs. seu padrão`}
              </div>
              <div className="alu-hero__escala">nota geral · escala 0–10</div>
            </div>
          </div>

          {estatisticas && (
            <div className="alu-hero__stats">
              {estatisticas.map((x) => (
                <div key={x.r} className="alu-hero__stat">
                  <div className="alu-hero__stat-rotulo">{x.r}</div>
                  <div className="alu-hero__stat-valor">{x.v}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="alu-ring-wrap">
          <Anel pct={pct} tamanho={84} espessura={8} cor="var(--color-gold)">
            <div style={{ textAlign: 'center', color: '#fff' }}>
              <div className="alu-ring__pos">{`${posicao}º`}</div>
              <div className="alu-ring__total">{`de ${total}`}</div>
            </div>
          </Anel>
          <div className="alu-ring__desc">
            <div className="alu-ring__label">Sua posição na turma</div>
            <div className="alu-ring__sub">
              {percentil != null ? `Melhor que ${percentil}% da turma.` : ''}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Comparacao({ detalhe }: { detalhe: DetalheSimuladoAluno | null }) {
  const g = detalhe?.grupos;
  if (!g) return null;

  const valores = [g.bottom15, g.geral, g.voce, g.top15].filter((v): v is number => v != null);
  const min = Math.max(0, Math.min(...valores) - 0.5);
  const max = Math.min(10, Math.max(...valores) + 0.5);

  const marcadores = [
    { value: g.bottom15, label: 'Inferior-15', color: 'var(--alu-calm)', you: false },
    { value: g.geral, label: 'Média geral', color: 'var(--color-text-secondary)', you: false },
    { value: g.voce, label: `Você · ${fmt(g.voce)}`, color: 'var(--alu-up)', you: true },
    { value: g.top15, label: 'Top-15', color: 'var(--color-navy)', you: false },
  ].filter((m): m is { value: number; label: string; color: string; you: boolean } => m.value != null);

  return (
    <div className="alu-card">
      <div className="alu-section-title">Onde você está na turma</div>
      <div style={{ overflowX: 'auto' }}>
        <BarraComparacao min={min} max={max} marcadores={marcadores} largura={540} altura={62} />
      </div>
      <div className="alu-range-legend">
        {g.voce != null && g.geral != null && (
          <div className="alu-range-kpi alu-range-kpi--up">
            <span className="alu-range-kpi__value">{`+${fmt(g.voce - g.geral)}`}</span>
            acima da média geral
          </div>
        )}
        {g.top15 != null && g.voce != null && (
          <div className="alu-range-kpi alu-range-kpi--calm">
            <span className="alu-range-kpi__value">{`−${fmt(g.top15 - g.voce)}`}</span>
            para o top-15
          </div>
        )}
      </div>
    </div>
  );
}

function Evolucao({ evolucao }: { evolucao: EvolucaoAluno | null }) {
  const materias = evolucao ? Object.keys(evolucao.materias) : [];
  const [materiaSel, setMateriaSel] = useState<string | null>(null);

  if (!evolucao?.ciclos?.length) {
    return (
      <div className="alu-card">
        <div className="alu-section-title">Minha evolução</div>
        <div className="alu-empty">Sem dados de evolução ainda.</div>
      </div>
    );
  }
  if (!materias.length) return null;

  const materia = materiaSel && materias.includes(materiaSel) ? materiaSel : materias[0];
  const dados = evolucao.materias[materia] ?? { aluno: [], turma: [] };

  // Só entram ciclos em que o aluno tem nota — buraco no meio da linha
  // sugeriria queda, quando na verdade é ausência de dado.
  const labels: string[] = [];
  const valoresAluno: number[] = [];
  const valoresTurma: Array<number | null> = [];

  evolucao.ciclos.forEach((c, i) => {
    const a = dados.aluno[i];
    if (a == null) return;
    labels.push(c.label);
    valoresAluno.push(a);
    valoresTurma.push(dados.turma[i] ?? null);
  });

  const series: SerieLinha[] = [];
  const turmaPresente = valoresTurma.filter((v): v is number => v != null);
  if (turmaPresente.length) {
    series.push({ values: turmaPresente, color: 'rgba(20,30,80,0.2)', dashed: true });
  }
  series.push({ values: valoresAluno, color: corMateria(materia) });

  return (
    <div className="alu-card">
      <div className="alu-section-title">
        Minha evolução
        <span className="alu-section-title__action">{`${evolucao.ciclos.length} ciclos`}</span>
      </div>

      <div className="alu-mat-chips">
        {materias.map((m) => (
          <div
            key={m}
            className={`alu-mat-chip${m === materia ? ' is-active' : ''}`}
            onClick={() => setMateriaSel(m)}
          >
            <span className="alu-mat-dot" style={{ background: corMateria(m) }} />
            {m}
          </div>
        ))}
      </div>

      <div style={{ overflowX: 'auto' }}>
        {valoresAluno.length < 2 ? (
          <div className="alu-empty" style={{ padding: '32px 0' }}>
            Dados insuficientes para esta matéria.
          </div>
        ) : (
          <GraficoLinha series={series} xLabels={labels} largura={500} altura={185} />
        )}
      </div>

      <div className="alu-chart-legend">
        <span className="alu-chart-legend-item">
          <span className="alu-chart-legend-line" style={{ background: corMateria(materia), height: '2.4px' }} />
          Você
        </span>
        <span className="alu-chart-legend-item">
          <span
            className="alu-chart-legend-line"
            style={{ background: 'rgba(20,30,80,0.2)', height: 0, borderTop: '2px dashed rgba(20,30,80,0.25)' }}
          />
          Média da turma
        </span>
      </div>
    </div>
  );
}

function CardIA() {
  const { data: insight, isPending, isError } = useInsightMe();
  const temBullets = insight?.disponivel && !!insight.bullets?.length;

  return (
    <div className="alu-ai-card">
      <div className="alu-ai-card__header">
        <div className="alu-ai-card__badge">
          <Icone d="M12 3l1.6 4.3L18 9l-4.4 1.7L12 15l-1.6-4.3L6 9l4.4-1.7z" tamanho={12} cor="#fff" />
          IA · Insight do ciclo
        </div>
        <span className="alu-ai-card__soon">
          {isPending ? 'analisando…' : temBullets ? insight!.cicloNome || '' : 'em breve, automático'}
        </span>
      </div>

      <div className="alu-ai-card__title">
        {temBullets ? 'O que o seu ciclo mostra:' : 'Análise personalizada do seu desempenho.'}
      </div>

      <div className="alu-ai-card__body">
        {isPending && !isError ? (
          'Analisando seu ciclo…'
        ) : temBullets ? (
          <ul className="alu-ai-card__bullets">
            {insight!.bullets.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
        ) : (
          'Em breve o assistente identificará automaticamente onde você pode melhorar mais com menos esforço — e vai sugerir o que revisar antes do próximo simulado.'
        )}
      </div>
    </div>
  );
}

const TONS_BADGE: Record<string, [string, string, string]> = {
  gold: ['#E6B94E', '#FAF0D6', '#A6822C'],
  up: ['#3E9B73', '#E2F2EA', '#2C7355'],
  calm: ['#C99A57', '#F7ECDA', '#9A6F32'],
  navy: ['#234C8B', '#E7EDF8', '#16356A'],
};

const D_ICONES: Record<string, string> = {
  flame: D_CHAMA,
  star: 'M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z',
  trophy: 'M6 9a6 6 0 0 0 12 0V3H6z M6 5H3v2a3 3 0 0 0 3 3 M18 5h3v2a3 3 0 0 1-3 3 M9 21h6 M12 15v6',
  medal: 'M12 15a6 6 0 1 0 0-12 6 6 0 0 0 0 12z M8.5 13L7 22l5-3 5 3-1.5-9',
  lock: 'M5 11h14v10H5z M8 11V7a4 4 0 0 1 8 0v4',
};

interface Badge {
  id: string;
  icon: string;
  label: string;
  sub: string;
  unlocked: boolean;
  tone: string;
  progress?: number;
}

function Conquistas({
  streak, simulados, detalhe,
}: {
  streak: Streak;
  simulados: SimuladoDoAluno[];
  detalhe: DetalheSimuladoAluno | null;
}) {
  const temNota8 = simulados.some((s) => s.nota >= 8);
  const noTop15 = !!detalhe && detalhe.total > 1 && detalhe.posicao <= Math.ceil(detalhe.total * 0.15);
  const count = streak.count ?? 0;

  const badges: Badge[] = [
    {
      id: 'streak3', icon: 'flame', label: '3 ciclos no fôlego',
      sub: 'Acima da média 3 ciclos seguidos',
      unlocked: count >= 3, tone: 'calm', progress: count >= 3 ? 1 : count / 3,
    },
    {
      id: 'first8', icon: 'star', label: 'Primeiro 8,0',
      sub: 'Nota 8+ em alguma matéria', unlocked: temNota8, tone: 'gold',
    },
    {
      id: 'top15', icon: 'trophy', label: 'Top 15',
      sub: 'Top 15% da turma em um simulado', unlocked: noTop15, tone: 'up',
    },
    {
      id: 'sim10', icon: 'medal', label: '10 simulados',
      sub: 'Completou 10 simulados', unlocked: simulados.length >= 10,
      tone: 'navy', progress: Math.min(1, simulados.length / 10),
    },
  ];

  return (
    <div className="alu-card">
      <div className="alu-section-title">Conquistas</div>
      <div className="alu-badge-grid">
        {badges.map((b) => <ChipBadge key={b.id} badge={b} />)}
      </div>
    </div>
  );
}

function ChipBadge({ badge }: { badge: Badge }) {
  const [cor, suave, profundo] = TONS_BADGE[badge.tone] ?? TONS_BADGE.navy;
  const d = D_ICONES[badge.unlocked ? badge.icon : 'lock'] ?? '';

  return (
    <div
      className={`alu-badge${badge.unlocked ? '' : ' alu-badge--locked'}`}
      style={{
        background: badge.unlocked ? suave : 'var(--color-surface-inset)',
        borderColor: badge.unlocked ? 'transparent' : 'var(--color-border)',
      }}
    >
      <div
        className="alu-badge__icon"
        style={{ background: badge.unlocked ? cor : 'var(--color-text-tertiary)' }}
      >
        <Icone d={d} tamanho={18} cor="#fff" espessura={1.8} />
      </div>
      <div className="alu-badge__label">{badge.label}</div>
      <div className="alu-badge__sub">{badge.sub}</div>

      {!badge.unlocked && badge.progress != null && (
        <div className="alu-badge-progress">
          <div className="alu-badge-progress__bar">
            <div
              className="alu-badge-progress__fill"
              style={{ width: `${Math.round(badge.progress * 100)}%`, background: profundo }}
            />
          </div>
          <div className="alu-badge-progress__pct">{`${Math.round(badge.progress * 100)}%`}</div>
        </div>
      )}
    </div>
  );
}
