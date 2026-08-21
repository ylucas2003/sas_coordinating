import { useState } from 'react';
import { CamposNota } from './CamposNota';
import { DialogoComDiff } from './DialogoComDiff';
import type { Mudanca } from './DialogoComDiff';
import { useFormularioNota } from './formularioNota';
import type { ValoresNota } from './formularioNota';
import { fmtNota } from '../../util/formato';

interface Props {
  nomeAluno: string;
  nomeSimulado: string;
  pontuacaoAtual: number | null;
  presenteAtual: boolean;
  notaMaxima: number | null;
  /** `null` = cancelado ou sem alteração. */
  onFechar: (valores: ValoresNota | null) => void;
}

/** Edição de nota: formulário → diff → confirmar. */
export function EdicaoNota({
  nomeAluno, nomeSimulado, pontuacaoAtual, presenteAtual, notaMaxima, onFechar,
}: Props) {
  const [mudancas, setMudancas] = useState<Mudanca[] | null>(null);
  const [valores, setValores] = useState<ValoresNota | null>(null);

  const form = useFormularioNota({
    pontuacaoAtual,
    presenteAtual,
    notaMaxima,
    formatarPontuacao: (n) => (n != null ? fmtNota(n) : '—'),
  });

  return (
    <DialogoComDiff
      titulo="Editar nota"
      subtitulo={`${nomeAluno} · ${nomeSimulado}`}
      mudancas={mudancas}
      onCancelar={() => onFechar(null)}
      onVoltar={() => setMudancas(null)}
      onConfirmar={() => onFechar(valores)}
      onSalvar={() => {
        const r = form.validar();
        // Inválido: fica no formulário com o campo marcado. Sem mudanças:
        // fecha sem chamar a API, como a versão anterior fazia.
        if (r.tipo === 'invalido') return;
        if (r.tipo === 'sem-mudancas') return onFechar(null);
        setValores(r.valores);
        setMudancas(r.mudancas);
      }}
    >
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
