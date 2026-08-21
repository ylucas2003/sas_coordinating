import type { ChatThreadResumo } from '../../tipos/chat';

const FORMATADOR = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
});

function formatarData(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    return FORMATADOR.format(new Date(iso));
  } catch {
    return '';
  }
}

interface Props {
  threads: ChatThreadResumo[];
  threadAtivaId: string | null;
  onNovaThread: () => void;
  onSelecionar: (id: string) => void;
  onApagar: (id: string) => void;
}

/** Lista de conversas do usuário: criar, escolher e apagar. */
export function ListaThreads({
  threads, threadAtivaId, onNovaThread, onSelecionar, onApagar,
}: Props) {
  return (
    <aside className="chat-threads">
      <div className="chat-threads__header">
        <span className="chat-threads__titulo">Conversas</span>
        <button className="chat-threads__nova" onClick={onNovaThread} title="Nova conversa">
          + Nova
        </button>
      </div>

      {threads.length === 0 ? (
        <div className="chat-threads__vazio">Nenhuma conversa ainda. Crie a primeira.</div>
      ) : (
        <ul className="chat-threads__lista">
          {threads.map((t) => (
            <li
              key={t.id}
              className={`chat-threads__item ${t.id === threadAtivaId ? 'is-ativa' : ''}`}
              onClick={() => onSelecionar(t.id)}
            >
              <div className="chat-threads__item-titulo">{t.titulo || 'Nova conversa'}</div>
              <div className="chat-threads__item-rodape">
                <span className="chat-threads__item-data">{formatarData(t.ultimaMsgEm)}</span>
                <button
                  className="chat-threads__item-apagar"
                  title="Apagar conversa"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(`Apagar a conversa "${t.titulo}"?`)) onApagar(t.id);
                  }}
                >
                  ×
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
