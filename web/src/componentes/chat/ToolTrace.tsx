import { nomeLegivelDaTool, resumirArgumentos } from '../../dominio/chatStream';
import type { EscopoDaConversa, TraceTool } from '../../dominio/chatStream';

// Trace de uma tool call durante o streaming — a bolha menor que mostra
// "Buscando ciclo 2026/1…" enquanto a chamada roda.
//
// O nome legível e o resumo dos argumentos são regra, e moram em
// `dominio/chatStream.ts` com teste: a lista de nomes é conferida contra as
// tools do backend, e o que o aluno pode ler nos argumentos depende do escopo.

export function ToolTrace({
  trace,
  escopo = 'coordenacao',
}: {
  trace: TraceTool;
  /** De quem é a conversa: no aluno, identificador cru não aparece. */
  escopo?: EscopoDaConversa;
}) {
  const args = resumirArgumentos(trace.args, escopo) || null;

  return (
    <div className={`chat-trace ${trace.finalizada ? 'is-finalizada' : 'is-rodando'}`}>
      <span className="chat-trace__icone">{trace.finalizada ? '✓' : '⋯'}</span>
      <span className="chat-trace__nome">{nomeLegivelDaTool(trace.nome)}</span>
      {args && <span className="chat-trace__args">{args}</span>}
      {trace.resumo && <span className="chat-trace__resumo">{`→ ${trace.resumo}`}</span>}
    </div>
  );
}
