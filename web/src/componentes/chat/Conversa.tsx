import { useEffect, useRef, useState } from 'react';

import { Artefato } from './Artefato';
import { useContextoDaTela } from '../layout/migalhas';
import { Markdown } from '../ui/Markdown';
import { Mensagem } from './Mensagem';
import { ToolTrace } from './ToolTrace';
import { ESTADO_INICIAL, reduzirEvento } from '../../dominio/chatStream';
import type { EstadoStream } from '../../dominio/chatStream';
import * as api from '../../servicos/api';
import type { ContextoDaTela } from '../../dominio/contextoDaTela';
import type { ChatThreadDetalhe, GrupoSugestoes, MensagemChat } from '../../tipos/chat';

interface Props {
  thread: ChatThreadDetalhe;
  onTituloAtualizado: (titulo: string) => void;
  sugestoes: GrupoSugestoes[];
  capacidades: string[];
  /** Quando presente, as sugestões passam a depender da tela aberta. */
  derivarSugestoes?: (ctx: ContextoDaTela) => GrupoSugestoes[];
}

/**
 * Área de conversa: histórico + composer + a resposta em streaming.
 *
 * A resposta em andamento é estado (`stream`), não DOM remendado: os eventos
 * do SSE passam pelo reducer e o React desenha. Quando o `end` chega, o texto
 * cru dá lugar ao markdown final e aos artefatos.
 */
export function Conversa({
  thread, onTituloAtualizado, sugestoes, capacidades, derivarSugestoes,
}: Props) {
  const contexto = useContextoDaTela();
  // `?? []` porque uma thread sem `mensagens` (payload inesperado da API) não
  // pode derrubar o componente — o chat abre vazio, e não quebrado.
  const [historico, setHistorico] = useState<MensagemChat[]>(thread.mensagens ?? []);
  const [stream, setStream] = useState<EstadoStream | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState('');

  const refLista = useRef<HTMLDivElement>(null);
  const refTextarea = useRef<HTMLTextAreaElement>(null);

  // Thread trocou: o histórico é outro e o streaming anterior não vale mais.
  useEffect(() => {
    setHistorico(thread.mensagens ?? []);
    setStream(null);
    setErroEnvio('');
  }, [thread.id, thread.mensagens]);

  // O backend batiza a thread durante o stream. Avisar o pai só quando o
  // título muda, e num efeito: chamar o setState dele de dentro do updater
  // deste componente seria atualizar um componente durante o render de outro.
  const titulo = stream?.titulo;
  useEffect(() => {
    if (titulo) onTituloAtualizado(titulo);
    // `onTituloAtualizado` é recriada a cada render do pai; só o título importa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titulo]);

  // Cola no fim a cada mudança — é o comportamento esperado de um chat.
  useEffect(() => {
    const lista = refLista.current;
    if (lista) lista.scrollTop = lista.scrollHeight;
  }, [historico, stream]);

  async function enviar(texto: string) {
    if (enviando || !texto.trim()) return;

    setEnviando(true);
    setErroEnvio('');
    setHistorico((h) => [...h, { papel: 'user', conteudo: texto }]);
    setStream(ESTADO_INICIAL);

    try {
      // O contexto é lido AGORA, e não na montagem: o painel não bloqueia a
      // navegação, então a tela pode ter mudado desde que a conversa abriu.
      await api.enviarChatMensagem(thread.id, texto, (evento) => {
        setStream((atual) => reduzirEvento(atual ?? ESTADO_INICIAL, evento));
      }, contexto);
    } catch (e) {
      setErroEnvio((e as Error).message || String(e));
    } finally {
      setEnviando(false);
      refTextarea.current?.focus();
    }
  }

  // As sugestões seguem a tela: abrir o chat na ficha do Ciclo 6 tem que
  // oferecer perguntas sobre o Ciclo 6 (docs/31 §2.5). Quem passa a lista fixa
  // (o Tio Léo do aluno) continua vendo a dele — `derivar` só existe no
  // launcher da coordenação.
  const grupos = derivarSugestoes ? derivarSugestoes(contexto) : sugestoes;
  const mostrarSugestoes = historico.length === 0 && grupos.length > 0 && !stream;

  return (
    <section className="chat-conversa">
      <div className="chat-conversa__lista" ref={refLista}>
        {historico.map((m, i) => <Mensagem key={i} msg={m} />)}

        {stream && (
          <BolhaStream stream={stream} emAndamento={enviando} erroEnvio={erroEnvio} />
        )}

        {mostrarSugestoes && (
          <Sugestoes grupos={grupos} capacidades={capacidades} onEscolher={enviar} />
        )}
      </div>

      <Composer ref={refTextarea} enviando={enviando} onEnviar={enviar} />
    </section>
  );
}

/** A resposta em andamento: traces, texto em stream e, no fim, o markdown. */
function BolhaStream({
  stream, emAndamento, erroEnvio,
}: {
  stream: EstadoStream;
  emAndamento: boolean;
  erroEnvio: string;
}) {
  return (
    <div className={`chat-msg chat-msg--assistant${emAndamento ? ' chat-msg--streaming' : ''}`}>
      {stream.traces.map((t) => <ToolTrace key={t.id} trace={t} />)}

      {stream.final ? (
        <>
          <div className="chat-msg__corpo">
            <Markdown texto={stream.final.texto} />
          </div>
          {stream.final.artefatos.map((art, i) => <Artefato key={i} artefato={art} />)}
        </>
      ) : (
        stream.texto && (
          <div className="chat-msg__corpo chat-msg__corpo--stream">{stream.texto}</div>
        )
      )}

      {stream.erros.map((e, i) => (
        <div key={i} className="chat-msg__erro">{`⚠️ ${e}`}</div>
      ))}
      {erroEnvio && <div className="chat-msg__erro">{`Erro: ${erroEnvio}`}</div>}
    </div>
  );
}

/**
 * Abertura da conversa. Os exemplos mostram o FORMATO das perguntas; a lista
 * recolhida de capacidades mostra o ALCANCE — por isso são blocos separados.
 */
function Sugestoes({
  grupos, capacidades, onEscolher,
}: {
  grupos: GrupoSugestoes[];
  capacidades: string[];
  onEscolher: (texto: string) => void;
}) {
  const [aberto, setAberto] = useState(false);

  return (
    <div className="chat-sugestoes">
      <div className="chat-sugestoes__titulo">Por onde começar</div>

      {grupos.map((g) => (
        <div key={g.grupo} className="chat-sugestoes__grupo">
          <div className="chat-sugestoes__grupo-titulo">{g.grupo}</div>
          <div className="chat-sugestoes__lista">
            {g.exemplos.map((texto) => (
              <button key={texto} className="chat-sugestao" onClick={() => onEscolher(texto)}>
                {texto}
              </button>
            ))}
          </div>
        </div>
      ))}

      {capacidades.length > 0 && (
        <div className="chat-capacidades">
          <button className="chat-capacidades__toggle" onClick={() => setAberto((a) => !a)}>
            <span className="chat-capacidades__seta">{aberto ? '▾' : '▸'}</span>
            O que mais você sabe fazer?
          </button>
          <ul className="chat-capacidades__lista" style={{ display: aberto ? '' : 'none' }}>
            {capacidades.map((c) => <li key={c}>{c}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function Composer({
  ref, enviando, onEnviar,
}: {
  ref: React.Ref<HTMLTextAreaElement>;
  enviando: boolean;
  onEnviar: (texto: string) => void;
}) {
  const [texto, setTexto] = useState('');

  function disparar() {
    if (!texto.trim()) return;
    onEnviar(texto);
    setTexto('');
  }

  return (
    <div className="chat-composer">
      <textarea
        ref={ref}
        className="chat-composer__input"
        placeholder="Pergunte algo ao assistente..."
        rows={2}
        value={texto}
        disabled={enviando}
        onChange={(e) => {
          setTexto(e.target.value);
          // Cresce com o conteúdo até um teto, para não engolir a conversa.
          e.target.style.height = 'auto';
          e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            disparar();
          }
        }}
      />
      <button className="chat-composer__enviar" disabled={enviando} onClick={disparar}>
        {enviando ? 'Enviando...' : 'Enviar'}
      </button>
    </div>
  );
}
