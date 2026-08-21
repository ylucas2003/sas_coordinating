import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';

/** Uma alteração pendente, mostrada na tela de confirmação. */
export interface Mudanca {
  campo: string;
  de: string;
  para: string;
}

interface Props {
  titulo: string;
  subtitulo?: string;
  /** Card mais largo (usado pela ficha de nota, que traz KPIs). */
  largo?: boolean;
  /** `null` = modo formulário; lista = modo confirmação. */
  mudancas: Mudanca[] | null;
  onCancelar: () => void;
  onSalvar: () => void;
  onVoltar: () => void;
  onConfirmar: () => void;
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
  titulo, subtitulo, largo = false, mudancas,
  onCancelar, onSalvar, onVoltar, onConfirmar, children,
}: Props) {
  const confirmando = mudancas !== null;

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
          </div>
        ) : (
          <div className="dialog__body">{children}</div>
        )}

        <div className="dialog__footer">
          {confirmando ? (
            <>
              <button className="btn btn--ghost" onClick={onVoltar}>← Voltar</button>
              <button className="btn btn--primary" onClick={onConfirmar}>Confirmar</button>
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
