import { useState } from 'react';
import { CamposNota, EscalaDaNota } from './CamposNota';
import { DialogoComDiff } from './DialogoComDiff';
import type { Mudanca } from './DialogoComDiff';
import { leituraDaNota, useFormularioNota } from './formularioNota';
import type { ValoresNota } from './formularioNota';

interface Props {
  nomeAluno: string;
  nomeSimulado: string;
  pontuacaoAtual: number | null;
  presenteAtual: boolean;
  notaMaxima: number | null;
  /** O corte desta matéria, já resolvido pelo servidor. Sem ele não há régua. */
  corte?: number | null;
  /** A matéria elimina sozinha (Inglês da F1 do ITA). Só muda o rótulo. */
  elimina?: boolean;
  /** `null` = cancelado ou sem alteração. */
  onFechar: (valores: ValoresNota | null) => void;
}

/** Edição de nota: formulário → diff → confirmar. */
export function EdicaoNota({
  nomeAluno, nomeSimulado, pontuacaoAtual, presenteAtual, notaMaxima,
  corte = null, elimina = false, onFechar,
}: Props) {
  const [mudancas, setMudancas] = useState<Mudanca[] | null>(null);
  const [valores, setValores] = useState<ValoresNota | null>(null);

  const form = useFormularioNota({ pontuacaoAtual, presenteAtual, notaMaxima, corte });

  return (
    <DialogoComDiff
      titulo="Editar nota"
      subtitulo={`${nomeAluno} · ${nomeSimulado}`}
      mudancas={mudancas}
      onCancelar={() => onFechar(null)}
      onVoltar={() => setMudancas(null)}
      canvas={{ efeito: 'atualiza a nota da submission do aluno no Canvas.' }}
      onConfirmar={(sincronizarCanvas) => onFechar(valores && { ...valores, sincronizarCanvas })}
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
        mensagem={form.mensagem}
        emFalta={form.emFalta}
        notaMaxima={notaMaxima}
        nota={form.nota}
      />

      {/* A régua entra mesmo sem turma: R2 vale mais aqui do que em qualquer
          tela de leitura, porque este é um dos dois lugares do produto onde
          uma nota é ESCRITA. Sem `corte` a escala não desenha — a peça é
          honesta sobre não ter régua a ancorar. */}
      <EscalaDaNota
        nota={form.nota}
        corte={corte}
        elimina={elimina}
        turma={null}
        leitura={leituraDaNota({ presente: form.presente, nota: form.nota, corte, elimina })}
      />
    </DialogoComDiff>
  );
}
