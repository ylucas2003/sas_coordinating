import { Fragment } from 'react';
import type { ReactNode } from 'react';

import { Artefato } from './Artefato';
import { Markdown } from '../ui/Markdown';
import { ToolTrace } from './ToolTrace';
import type { EscopoDaConversa } from '../../dominio/chatStream';
import type { ArtefatoChat, MensagemChat } from '../../tipos/chat';

/**
 * Quem desenha cada artefato da conversa.
 *
 * Prop, e não import fixo, porque a MESMA conversa serve dois cascos (docs/27
 * §8): a coordenação desenha com `Artefato`, e a folha do aluno com
 * `ArtefatoAluno`, que fala a língua visual dele e conhece os tipos do
 * catálogo do aluno (docs/43 §4.1, defeito 6).
 */
export type RenderArtefato = (artefato: ArtefatoChat) => ReactNode;

/** O desenho de quando ninguém passa renderizador — o da coordenação. */
export const renderArtefatoPadrao: RenderArtefato = (artefato) => <Artefato artefato={artefato} />;

/**
 * Uma mensagem da conversa. Os papéis 'system' e 'tool' ficam ocultos: estão
 * no histórico, mas não são conversa do ponto de vista do usuário.
 */
export function Mensagem({
  msg,
  renderArtefato = renderArtefatoPadrao,
  escopo = 'coordenacao',
}: {
  msg: MensagemChat;
  renderArtefato?: RenderArtefato;
  /** De quem é a conversa — decide o que os traces mostram dos argumentos. */
  escopo?: EscopoDaConversa;
}) {
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
          escopo={escopo}
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

      {artefatos.map((art, i) => <Fragment key={i}>{renderArtefato(art)}</Fragment>)}
    </div>
  );
}
