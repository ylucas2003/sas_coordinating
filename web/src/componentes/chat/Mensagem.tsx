import { Artefato } from './Artefato';
import { Markdown } from './Markdown';
import { ToolTrace } from './ToolTrace';
import type { MensagemChat } from '../../tipos/chat';

/**
 * Uma mensagem da conversa. Os papéis 'system' e 'tool' ficam ocultos: estão
 * no histórico, mas não são conversa do ponto de vista do usuário.
 */
export function Mensagem({ msg }: { msg: MensagemChat }) {
  if (msg.papel === 'user') {
    return (
      <div className="chat-msg chat-msg--user">
        <div className="chat-msg__corpo">{msg.conteudo || ''}</div>
      </div>
    );
  }

  if (msg.papel !== 'assistant') return null;

  const toolCalls = Array.isArray(msg.toolCalls) ? msg.toolCalls : [];
  const artefatos = msg.artefatos ?? [];
  if (!toolCalls.length && !msg.conteudo && !artefatos.length) return null;

  return (
    <div className="chat-msg chat-msg--assistant">
      {toolCalls.map((tc, i) => (
        <ToolTrace
          key={i}
          trace={{
            id: String(i),
            nome: tc.name ?? tc.nome ?? '',
            args: (tc.arguments ?? tc.args ?? {}) as Record<string, unknown>,
            resumo: null,
            finalizada: true,
          }}
        />
      ))}

      {msg.conteudo && (
        <div className="chat-msg__corpo">
          <Markdown texto={msg.conteudo} />
        </div>
      )}

      {artefatos.map((art, i) => <Artefato key={i} artefato={art} />)}
    </div>
  );
}
