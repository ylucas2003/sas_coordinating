import { useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';

/** Uma alteração pendente, mostrada na tela de confirmação. */
export interface Mudanca {
  campo: string;
  de: string;
  para: string;
}

/**
 * A pergunta "e no Canvas?". Toda alteração que fosse chamar uma rota de
 * escrita no Canvas passa por aqui: o coordenador decide, a cada ação, se a
 * mudança sobe ou fica só no site (docs/18 §2.1). Sem esta prop, o diálogo
 * não toca no Canvas — e é a rota que exige a escolha, sem default.
 */
export interface OpcaoCanvas {
  /** O que a mudança faz lá, em uma linha: "atualiza a nota da submission". */
  efeito: string;
  /** `true` marca a operação como irreversível (apagar leva as submissions). */
  irreversivel?: boolean;
  /** Escolha inicial. Default: enviar. */
  padrao?: boolean;
}

interface Props {
  titulo: string;
  subtitulo?: string;
  /** Card mais largo (usado pela ficha de nota, que traz KPIs). */
  largo?: boolean;
  /** `null` = modo formulário; lista = modo confirmação. */
  mudancas: Mudanca[] | null;
  canvas?: OpcaoCanvas;
  onCancelar: () => void;
  onSalvar: () => void;
  onVoltar: () => void;
  /** Recebe a escolha do Canvas (`false` quando a prop `canvas` não foi dada). */
  onConfirmar: (sincronizarCanvas: boolean) => void;
  children: ReactNode;
}

/**
 * Diálogo de edição em dois passos: formulário → diff → confirmar.
 *
 * O passo do diff existe porque toda edição aqui altera nota de aluno ou
 * metadado de prova — coisas que se propagam para estatísticas e ranking. Ver
 * o que exatamente vai mudar antes de confirmar é o que evita o erro de digitação
 * silencioso.
 */
export function DialogoComDiff({
  titulo, subtitulo, largo = false, mudancas, canvas,
  onCancelar, onSalvar, onVoltar, onConfirmar, children,
}: Props) {
  const confirmando = mudancas !== null;
  const [sincronizar, setSincronizar] = useState(canvas?.padrao ?? true);

  return createPortal(
    <div
      className="dialog-overlay"
      onClick={(ev) => {
        if (ev.target === ev.currentTarget) onCancelar();
      }}
    >
      <div className={`dialog${largo ? ' dialog--largo' : ''}`}>
        <div className="dialog__header">
          <div className="dialog__titulo">{titulo}</div>
          {subtitulo && <div className="dialog__subtitulo">{subtitulo}</div>}
        </div>

        {confirmando ? (
          <div className="dialog__body dialog__confirmacao">
            <p className="dialog__confirmacao-titulo">Confirmar as seguintes alterações?</p>
            <div className="dialog__diff">
              {mudancas.map((m, i) => (
                <div key={i} className="dialog__diff-linha">
                  <span className="dialog__diff-campo">{m.campo}</span>
                  <span className="dialog__diff-de">{m.de}</span>
                  <span className="dialog__diff-seta"> → </span>
                  <span className="dialog__diff-para">{m.para}</span>
                </div>
              ))}
            </div>

            {canvas && (
              <fieldset className={`dialog__canvas${canvas.irreversivel ? ' dialog__canvas--perigo' : ''}`}>
                <legend className="dialog__canvas-titulo">E no Canvas?</legend>
                <label className="dialog__canvas-opcao">
                  <input
                    type="radio"
                    name="sincronizar-canvas"
                    checked={sincronizar}
                    onChange={() => setSincronizar(true)}
                  />
                  <span>
                    <strong>Enviar agora</strong>
                    {` — ${canvas.efeito}`}
                    {canvas.irreversivel && (
                      <em className="dialog__canvas-aviso"> Irreversível.</em>
                    )}
                  </span>
                </label>
                <label className="dialog__canvas-opcao">
                  <input
                    type="radio"
                    name="sincronizar-canvas"
                    checked={!sincronizar}
                    onChange={() => setSincronizar(false)}
                  />
                  <span>
                    <strong>Deixar só no site</strong>
                    {' — o Canvas fica diferente, e isso aparece marcado aqui.'}
                  </span>
                </label>
              </fieldset>
            )}
          </div>
        ) : (
          <div className="dialog__body">{children}</div>
        )}

        <div className="dialog__footer">
          {confirmando ? (
            <>
              <button className="btn btn--ghost" onClick={onVoltar}>← Voltar</button>
              <button
                className={`btn btn--primary${canvas?.irreversivel && sincronizar ? ' btn--perigo' : ''}`}
                onClick={() => onConfirmar(canvas ? sincronizar : false)}
              >
                {canvas ? (sincronizar ? 'Confirmar e enviar ao Canvas' : 'Confirmar só no site') : 'Confirmar'}
              </button>
            </>
          ) : (
            <>
              <button className="btn btn--ghost" onClick={onCancelar}>Cancelar</button>
              <button className="btn btn--primary" onClick={onSalvar}>Salvar</button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
