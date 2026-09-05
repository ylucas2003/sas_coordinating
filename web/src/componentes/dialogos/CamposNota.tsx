import { useEffect, useRef } from 'react';

interface Props {
  presente: boolean;
  onPresenteChange: (v: boolean) => void;
  texto: string;
  onTextoChange: (v: string) => void;
  erro: boolean;
  notaMaxima: number | null;
}

/** Checkbox de presença + campo de pontuação. Igual nos dois diálogos de nota. */
export function CamposNota({
  presente, onPresenteChange, texto, onTextoChange, erro, notaMaxima,
}: Props) {
  const refPontuacao = useRef<HTMLInputElement>(null);
  const refPresente = useRef<HTMLInputElement>(null);

  // Foca o campo que o usuário provavelmente quer mexer: a pontuação quando
  // o aluno está presente, a presença quando não está.
  // Só na montagem: com `presente` na lista, cada toggle roubaria o foco de
  // quem está digitando.
  // biome-ignore lint/correctness/useExhaustiveDependencies: só na montagem
  useEffect(() => {
    if (presente) refPontuacao.current?.focus();
    else refPresente.current?.focus();
  }, []);

  // Campo inválido: devolve o foco para quem precisa ser corrigido.
  useEffect(() => {
    if (erro) refPontuacao.current?.focus();
  }, [erro]);

  return (
    <>
      <div className="dialog__campo">
        <label className="dialog__checkbox-row">
          <input
            ref={refPresente}
            type="checkbox"
            checked={presente}
            onChange={(e) => onPresenteChange(e.target.checked)}
          />
          <span className="dialog__checkbox-label">Presente na prova</span>
        </label>
      </div>

      <div className="dialog__campo">
        <span className="dialog__label">Pontuação</span>
        <input
          ref={refPontuacao}
          type="number"
          className={`dialog__input${erro ? ' dialog__input--erro' : ''}`}
          min="0"
          max={notaMaxima ?? undefined}
          step="0.5"
          placeholder="ex.: 14"
          disabled={!presente}
          value={texto}
          onChange={(e) => onTextoChange(e.target.value)}
        />
        <span className="dialog__hint">
          {notaMaxima != null ? `de ${notaMaxima} questões` : 'pontuação bruta'}
        </span>
      </div>
    </>
  );
}
