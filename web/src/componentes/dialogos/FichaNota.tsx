import { useState } from 'react';
import { CamposNota } from './CamposNota';
import { DialogoComDiff } from './DialogoComDiff';
import type { Mudanca } from './DialogoComDiff';
import { useFormularioNota } from './formularioNota';
import type { ValoresNota } from './formularioNota';
import { fmtNota } from '../../util/formato';

export interface StatsNota {
  posicao: number | null;
  totalPresentes: number;
  nota: number | null;
  media: number | null;
  maiorNota?: number | null;
  mediaTop15: number | null;
  mediaBottom15: number | null;
  mediana?: number | null;
}

interface Props {
  nomeAluno: string;
  nomeSimulado: string;
  pontuacaoAtual: number | null;
  presenteAtual: boolean;
  notaMaxima: number | null;
  stats: StatsNota | null;
  onFechar: (valores: ValoresNota | null) => void;
}

function toneNota(v: number | null | undefined): string {
  if (v == null) return '';
  return v >= 7 ? ' tone-verde' : v >= 5 ? ' tone-ambar' : ' tone-vermelho';
}

function KpiDialogo({ rotulo, valor, tone = '' }: { rotulo: string; valor: string; tone?: string }) {
  return (
    <div className="dialog__kpi">
      <div className="dialog__kpi-rotulo">{rotulo}</div>
      <div className={`dialog__kpi-valor${tone}`}>{valor}</div>
    </div>
  );
}

/**
 * Ficha de nota: comparação com a turma e edição na mesma view.
 * Fluxo: view única → Salvar → diff → Confirmar.
 */
export function FichaNota({
  nomeAluno, nomeSimulado, pontuacaoAtual, presenteAtual, notaMaxima, stats, onFechar,
}: Props) {
  const [mudancas, setMudancas] = useState<Mudanca[] | null>(null);
  const [valores, setValores] = useState<ValoresNota | null>(null);

  const form = useFormularioNota({
    pontuacaoAtual,
    presenteAtual,
    notaMaxima,
    // Aqui o diff mostra a pontuação BRUTA (nº de acertos), não a nota 0-10.
    formatarPontuacao: (n) => (n != null ? String(n) : '—'),
  });

  const temKpis = stats && stats.totalPresentes > 0;

  return (
    <DialogoComDiff
      titulo={nomeSimulado}
      subtitulo={nomeAluno}
      largo
      mudancas={mudancas}
      onCancelar={() => onFechar(null)}
      onVoltar={() => setMudancas(null)}
      canvas={{ efeito: 'atualiza a nota da submission do aluno no Canvas.' }}
      onConfirmar={(sincronizarCanvas) => onFechar(valores && { ...valores, sincronizarCanvas })}
      onSalvar={() => {
        const r = form.validar();
        if (r.tipo === 'invalido') return;
        if (r.tipo === 'sem-mudancas') return onFechar(null);
        setValores(r.valores);
        setMudancas(r.mudancas);
      }}
    >
      {presenteAtual === false && (
        <p className="dialog__hint dialog__hint--ambar" style={{ marginBottom: 2 }}>
          Aluno marcado como ausente.
        </p>
      )}

      {temKpis && <BlocoKpis stats={stats} pontuacaoAtual={pontuacaoAtual} notaMaxima={notaMaxima} />}
      {temKpis && <div className="dialog__sep" />}

      <CamposNota
        presente={form.presente}
        onPresenteChange={form.alterarPresenca}
        texto={form.texto}
        onTextoChange={form.setTexto}
        erro={form.erro}
        notaMaxima={notaMaxima}
      />
    </DialogoComDiff>
  );
}

function BlocoKpis({
  stats, pontuacaoAtual, notaMaxima,
}: {
  stats: StatsNota;
  pontuacaoAtual: number | null;
  notaMaxima: number | null;
}) {
  const { posicao, totalPresentes, nota, media, mediaTop15, mediaBottom15 } = stats;

  // Faixas do ranking: top 15% em verde, metade superior em âmbar, resto em vermelho.
  const tonePosicao =
    posicao == null
      ? ''
      : posicao <= Math.ceil(totalPresentes * 0.15)
        ? ' tone-verde'
        : posicao <= Math.ceil(totalPresentes * 0.5)
          ? ' tone-ambar'
          : ' tone-vermelho';

  const acertos =
    pontuacaoAtual != null && notaMaxima != null
      ? `${pontuacaoAtual} / ${notaMaxima}`
      : pontuacaoAtual != null
        ? String(pontuacaoAtual)
        : '—';

  return (
    <div className="dialog__kpi-grid">
      <KpiDialogo
        rotulo="Posição"
        valor={posicao != null ? `#${posicao} / ${totalPresentes}` : `— / ${totalPresentes}`}
        tone={tonePosicao}
      />
      <KpiDialogo rotulo="Nota" valor={fmtNota(nota)} tone={toneNota(nota)} />
      <KpiDialogo rotulo="Acertos" valor={acertos} />
      <KpiDialogo rotulo="Média" valor={fmtNota(media)} tone={toneNota(media)} />
      <KpiDialogo rotulo="Top 15%" valor={fmtNota(mediaTop15)} />
      <KpiDialogo rotulo="Bottom 15%" valor={fmtNota(mediaBottom15)} />
    </div>
  );
}
