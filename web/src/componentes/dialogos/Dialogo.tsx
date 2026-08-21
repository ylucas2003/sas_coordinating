import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';

interface Props {
  titulo: string;
  subtitulo?: string;
  onFechar: () => void;
  children: ReactNode;
  /** Botões do rodapé. */
  rodape: ReactNode;
}

/**
 * Overlay + card de diálogo. Portal para o `<body>`, como o overlay imperativo
 * antigo fazia — assim o diálogo não herda `overflow` nem `z-index` da tela
 * que o abriu.
 *
 * Reusa as classes `.dialog*` de styles/edicao.css.
 */
export function Dialogo({ titulo, subtitulo, onFechar, children, rodape }: Props) {
  return createPortal(
    <div
      className="dialog-overlay"
      onClick={(ev) => {
        // Só o clique no fundo fecha; clique dentro do card não borbulha daqui.
        if (ev.target === ev.currentTarget) onFechar();
      }}
    >
      <div className="dialog">
        <div className="dialog__header">
          <div className="dialog__titulo">{titulo}</div>
          {subtitulo && <div className="dialog__subtitulo">{subtitulo}</div>}
        </div>
        <div className="dialog__body">{children}</div>
        <div className="dialog__footer">{rodape}</div>
      </div>
    </div>,
    document.body,
  );
}

/** Campo rotulado do formulário de diálogo. */
export function Campo({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="dialog__campo">
      <span className="dialog__label">{label}</span>
      {children}
    </div>
  );
}

/** Duas colunas lado a lado dentro do corpo do diálogo. */
export function Linha2({ children }: { children: ReactNode }) {
  return <div className="agendar__linha2">{children}</div>;
}
