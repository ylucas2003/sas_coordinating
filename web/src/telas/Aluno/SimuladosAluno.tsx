import { Link, useNavigate, useParams } from 'react-router-dom';
import { Anel, BarraComparacao, Icone } from '../../componentes/aluno/graficos';
import { useQuestoesMe, useSimuladoMe, useSimuladosMe } from '../../hooks/aluno';
import type { QuestoesDoSimulado, SimuladoDoAluno } from '../../tipos/aluno';
import {
  CHIP_MATERIA, CHIP_VESTIBULAR, fmt, fmtDataLonga, fmtDuracao,
} from '../../util/formatoAluno';

const D_DOC = 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M9 13h6 M9 17h4';
const D_CHEVRON = 'M9 18l6-6-6-6';
const D_VOLTAR = 'M19 12H5 M12 19l-7-7 7-7';

function Chip({ label, bg, fg }: { label: string; bg: string; fg: string }) {
  return <span className="alu-sim-chip" style={{ background: bg, color: fg }}>{label}</span>;
}

/** Chips de contexto: matéria (colorida), vestibular e ciclo. */
function ChipsContexto({
  materia, vestibular, cicloOrdem,
}: {
  materia?: string | null;
  vestibular?: string | null;
  cicloOrdem?: number | null;
}) {
  const cm = materia ? CHIP_MATERIA[materia] : undefined;
  const cv = vestibular ? CHIP_VESTIBULAR[vestibular] : undefined;
  return (
    <>
      {materia && <Chip label={materia} bg={cm?.bg ?? '#E7EDF8'} fg={cm?.fg ?? '#16356A'} />}
      {vestibular && <Chip label={vestibular} bg={cv?.bg ?? '#E7EDF8'} fg={cv?.fg ?? '#16356A'} />}
      {cicloOrdem != null && (
        <Chip label={`Ciclo ${cicloOrdem}`} bg="var(--color-surface-inset)" fg="var(--color-text-secondary)" />
      )}
    </>
  );
}

// ─── Lista ───────────────────────────────────────────────────────────────

export function ListaSimuladosAluno() {
  const { data: simulados = [], isPending } = useSimuladosMe();

  if (isPending) return <div className="alu-loading">Carregando…</div>;

  if (!simulados.length) {
    return (
      <div className="alu-empty">
        Nenhum simulado corrigido ainda.
        <div className="alu-empty__sub">
          As notas aparecem assim que o coordenador lançar os resultados.
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{
            fontSize: 22, fontWeight: 700, letterSpacing: '-0.4px',
            color: 'var(--color-text-primary)', lineHeight: 1.2,
          }}>
            Meus Simulados
          </div>
          <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginTop: 2 }}>
            {`${simulados.length} resultado${simulados.length !== 1 ? 's' : ''} corrigidos`}
          </div>
        </div>
      </div>

      <div className="alu-sim-list">
        {simulados.map((s) => <CardSimulado key={s.id} sim={s} />)}
      </div>
    </div>
  );
}

function CardSimulado({ sim }: { sim: SimuladoDoAluno }) {
  const navegar = useNavigate();
  const delta = sim.deltaSelf;
  const classeDelta = delta == null ? 'alu-delta--neutral' : delta >= 0 ? 'alu-delta--up' : 'alu-delta--down';

  const corNota =
    sim.nota >= 7 ? 'var(--alu-up-deep)'
      : sim.nota >= 5 ? 'var(--color-text-primary)'
        : 'var(--alu-calm-deep)';

  return (
    <div className="alu-sim-card" onClick={() => navegar(`/simulados/${sim.id}`)}>
      <div className="alu-sim-icon">
        <Icone d={D_DOC} tamanho={20} cor="var(--color-navy)" espessura={1.7} />
      </div>

      <div className="alu-sim-info">
        <div className="alu-sim-nome">
          {sim.rotulo || sim.nome || '—'}
          {sim.novo && <span className="alu-sim-novo">NOVO</span>}
        </div>
        <div className="alu-sim-chips">
          <ChipsContexto materia={sim.materia} vestibular={sim.vestibularAlvo} cicloOrdem={sim.cicloOrdem} />
          {sim.dataAplicacao && <span className="alu-sim-date">{fmtDataLonga(sim.dataAplicacao)}</span>}
        </div>
      </div>

      <div className="alu-sim-nota-wrap">
        <div className="alu-sim-nota" style={{ color: corNota }}>{fmt(sim.nota)}</div>
        <div className={`alu-delta ${classeDelta}`} style={{ justifyContent: 'flex-end', marginTop: 3 }}>
          {delta == null ? '—' : `${delta >= 0 ? '+' : ''}${fmt(delta)}`}
        </div>
        {sim.mediaGeral != null && (
          <div className="alu-sim-date" style={{ textAlign: 'right', marginTop: 2 }}>
            {`turma ${fmt(sim.mediaGeral)}`}
          </div>
        )}
      </div>

      <Icone d={D_CHEVRON} tamanho={18} cor="var(--color-text-tertiary)" espessura={2} />
    </div>
  );
}

// ─── Detalhe ─────────────────────────────────────────────────────────────

export function DetalheSimuladoAlunoTela() {
  const { id } = useParams();
  const { data: detalhe, isPending } = useSimuladoMe(id);
  const { data: questoes } = useQuestoesMe(id);

  if (isPending) return <div className="alu-loading">Carregando…</div>;
  if (!detalhe) return <div className="alu-empty">Simulado não encontrado.</div>;

  const pct = detalhe.total > 1 ? 1 - (detalhe.posicao - 1) / detalhe.total : 0.5;
  const g = detalhe.grupos;

  const estatisticas = [
    { r: 'Posição', v: `${detalhe.posicao}º de ${detalhe.total}` },
    { r: 'Percentil', v: `${detalhe.percentil}%` },
    { r: 'Média da turma', v: fmt(g?.geral) },
    ...(questoes?.duracaoMediaSegundos != null
      ? [{ r: 'Tempo médio da turma', v: fmtDuracao(questoes.duracaoMediaSegundos) ?? '—' }]
      : []),
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <Link className="alu-back-link" to="/simulados">
        <Icone d={D_VOLTAR} tamanho={15} espessura={2} />
        Todos os simulados
      </Link>

      <div className="alu-sim-detail__header">
        <div className="alu-sim-detail__titulo">{detalhe.rotulo || detalhe.nome || '—'}</div>
        <div className="alu-sim-chips" style={{ marginTop: 8 }}>
          <ChipsContexto materia={detalhe.materia} vestibular={detalhe.vestibularAlvo} />
          {detalhe.dataAplicacao && (
            <span className="alu-sim-date">{fmtDataLonga(detalhe.dataAplicacao)}</span>
          )}
        </div>
      </div>

      <div
        className="alu-card"
        style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}
      >
        <Anel
          pct={pct} tamanho={78} espessura={7}
          cor={pct > 0.5 ? 'var(--alu-up)' : 'var(--alu-calm)'}
          trilha="var(--color-border)"
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <div style={{
              fontSize: 48, fontWeight: 700, letterSpacing: '-1.5px',
              fontVariantNumeric: 'tabular-nums', lineHeight: 0.9, color: 'var(--color-navy-deep)',
            }}>
              {fmt(detalhe.nota)}
            </div>
            <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>nota geral · 0–10</div>
          </div>

          <div style={{
            display: 'flex', gap: 18, flexWrap: 'wrap', marginTop: 14, paddingTop: 14,
            borderTop: '1px solid var(--color-border)',
          }}>
            {estatisticas.map((x) => (
              <div key={x.r}>
                <div style={{
                  fontSize: 10.5, color: 'var(--color-text-tertiary)',
                  marginBottom: 2, whiteSpace: 'nowrap',
                }}>
                  {x.r}
                </div>
                <div style={{
                  fontSize: 15, fontWeight: 600, color: 'var(--color-text-primary)',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {x.v}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {g && <ComparacaoTurma grupos={g} />}
      <QuestaoAQuestao questoes={questoes ?? null} />
    </div>
  );
}

function ComparacaoTurma({ grupos }: { grupos: NonNullable<import('../../tipos/aluno').GruposComparacao> }) {
  const valores = [grupos.bottom15, grupos.geral, grupos.voce, grupos.top15]
    .filter((v): v is number => v != null);
  const min = Math.max(0, Math.min(...valores) - 0.5);
  const max = Math.min(10, Math.max(...valores) + 0.5);

  const marcadores = [
    { value: grupos.bottom15, label: 'Inferior-15', color: 'var(--alu-calm)', you: false },
    { value: grupos.geral, label: 'Média geral', color: 'var(--color-text-secondary)', you: false },
    { value: grupos.voce, label: `Você · ${fmt(grupos.voce)}`, color: 'var(--alu-up)', you: true },
    { value: grupos.top15, label: 'Top-15', color: 'var(--color-navy)', you: false },
  ].filter((m): m is { value: number; label: string; color: string; you: boolean } => m.value != null);

  return (
    <div className="alu-card">
      <div className="alu-section-title">Comparação com a turma</div>
      <div style={{ overflowX: 'auto' }}>
        <BarraComparacao min={min} max={max} marcadores={marcadores} largura={500} altura={62} />
      </div>
    </div>
  );
}

const CLASSE_DOT: Record<string, string> = {
  correta: 'correct',
  errada: 'wrong',
  em_branco: 'blank',
};

/**
 * Resultado questão a questão. Só aparece com dados reais do Canvas — sem
 * gabarito sincronizado, mostra um aviso limpo em vez de um grid vazio.
 */
function QuestaoAQuestao({ questoes }: { questoes: QuestoesDoSimulado | null }) {
  if (!questoes?.temGabarito || !questoes.temMinhasRespostas) {
    return (
      <div className="alu-card">
        <div className="alu-section-title">Resultado questão a questão</div>
        <div className="alu-empty" style={{ padding: '24px 0' }}>
          {questoes?.temGabarito
            ? 'Suas respostas deste simulado ainda não foram sincronizadas.'
            : 'Detalhe questão a questão disponível apenas para simulados aplicados online.'}
        </div>
      </div>
    );
  }

  const paraRevisar = questoes.questoes.filter(
    (q) => q.resultado === 'errada' || q.resultado === 'em_branco',
  );

  const legenda = (bg: string, borda: string, label: string) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{
        width: 10, height: 10, borderRadius: 3, background: bg,
        display: 'inline-block', border: `1px solid ${borda}`,
      }} />
      {label}
    </div>
  );

  return (
    <div className="alu-sim-detail__grid">
      <div className="alu-card">
        <div className="alu-section-title">Resultado questão a questão</div>
        <div className="alu-dot-grid">
          {questoes.questoes.map((q, i) => (
            <div
              key={q.posicao ?? i}
              className={`alu-dot alu-dot--${CLASSE_DOT[q.resultado] ?? 'blank'}`}
              title={q.textoResumo || ''}
            >
              {q.posicao ?? ''}
            </div>
          ))}
        </div>
        <div style={{
          display: 'flex', gap: 14, marginTop: 4, fontSize: 12,
          color: 'var(--color-text-secondary)', flexWrap: 'wrap',
        }}>
          {legenda('var(--alu-up-soft)', 'var(--alu-up)', `${questoes.acertos} corretas`)}
          {legenda('var(--alu-calm-soft)', 'var(--alu-calm)', `${questoes.erros} erradas`)}
          {!!questoes.emBranco &&
            legenda('var(--color-surface-inset)', 'var(--color-border-strong)', `${questoes.emBranco} em branco`)}
        </div>
      </div>

      <div className="alu-card">
        <div className="alu-section-title">{`Para revisar (${paraRevisar.length})`}</div>
        {!paraRevisar.length ? (
          <div className="alu-empty" style={{ padding: '24px 0' }}>
            Nenhuma questão errada? Perfeito!
          </div>
        ) : (
          <div className="alu-revisar-list">
            {paraRevisar.slice(0, 12).map((q, i) => (
              <div key={q.posicao ?? i} className="alu-revisar-item">
                <div className="alu-revisar-item__num">{q.posicao ?? ''}</div>
                <div className="alu-revisar-item__info">
                  <div className="alu-revisar-item__assunto">
                    {q.assunto || q.textoResumo || `Questão ${q.posicao}`}
                  </div>
                  <div className="alu-revisar-item__hint">
                    {q.resultado === 'em_branco'
                      ? 'Deixada em branco'
                      : q.alternativaCorreta
                        ? `Correta: ${q.alternativaCorreta}`
                        : 'Análise por assunto em breve'}
                  </div>
                </div>
              </div>
            ))}
            {paraRevisar.length > 12 && (
              <div style={{
                fontSize: 12, color: 'var(--color-text-tertiary)',
                textAlign: 'center', paddingTop: 6,
              }}>
                {`+ ${paraRevisar.length - 12} mais`}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
