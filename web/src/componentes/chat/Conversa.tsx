import { Fragment, useEffect, useRef, useState } from 'react';

import { useContextoDaTela } from '../layout/migalhas';
import { Markdown } from '../ui/Markdown';
import { Mensagem, renderArtefatoPadrao } from './Mensagem';
import type { RenderArtefato } from './Mensagem';
import { ToolTrace } from './ToolTrace';
import {
  ESTADO_INICIAL, artefatosNaResposta, mensagemDaResposta, reduzirEvento,
} from '../../dominio/chatStream';
import type { EscopoDaConversa, EstadoStream } from '../../dominio/chatStream';
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
  /**
   * Quem desenha os artefatos, os do histórico e os da resposta ao vivo. Sem
   * ele, o `Artefato` da coordenação — que é o que o `ChatLauncher` usa, por
   * não passar nada. A folha do aluno passa o `ArtefatoAluno`.
   */
  renderArtefato?: RenderArtefato;
  /**
   * De quem é a conversa (docs/43 §3.1). Sem ele, a coordenação — que é o que o
   * `ChatLauncher` usa, por não passar nada. Hoje decide o que os traces
   * mostram dos argumentos: no aluno, identificador cru não aparece.
   */
  escopo?: EscopoDaConversa;
}

/**
 * O histórico que a conversa desenha a partir da thread persistida.
 *
 * ⚠️ O servidor pendura cada artefato na mensagem `tool` que o produziu, e
 * `Mensagem` não desenha `tool`: sem a passagem por `artefatosNaResposta`, o
 * gráfico, o CSV, o link de `navegar_para` e os cartões do Tio Léo sumiam
 * toda vez que a conversa era reaberta (docs/43 §4.1, defeito 6). Aqui, na
 * entrada da `Conversa`, vale para os dois cascos sem que nenhum precise
 * lembrar — até 25/10 só a folha do aluno a fazia. A função é idempotente.
 *
 * `?? []` porque uma thread sem `mensagens` (payload inesperado da API) não
 * pode derrubar o componente — o chat abre vazio, e não quebrado.
 */
function historicoDaThread(mensagens: MensagemChat[] | null | undefined): MensagemChat[] {
  return artefatosNaResposta(mensagens ?? []);
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
  renderArtefato = renderArtefatoPadrao,
  escopo = 'coordenacao',
}: Props) {
  const contexto = useContextoDaTela();
  const [historico, setHistorico] = useState<MensagemChat[]>(() => historicoDaThread(thread.mensagens));
  const [stream, setStream] = useState<EstadoStream | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState('');

  const refLista = useRef<HTMLDivElement>(null);
  const refTextarea = useRef<HTMLTextAreaElement>(null);

  // Thread trocou: o histórico é outro e o streaming anterior não vale mais.
  // `thread.id` é o gatilho da troca, não uma leitura: sem ele, duas threads
  // cujo `mensagens` chegasse com o mesmo conteúdo não reiniciariam o stream.
  // biome-ignore lint/correctness/useExhaustiveDependencies: gatilho, não leitura
  useEffect(() => {
    setHistorico(historicoDaThread(thread.mensagens));
    setStream(null);
    setErroEnvio('');
  }, [thread.id, thread.mensagens]);

  // O backend batiza a thread durante o stream. Avisar o pai só quando o
  // título muda, e num efeito: chamar o setState dele de dentro do updater
  // deste componente seria atualizar um componente durante o render de outro.
  const titulo = stream?.titulo;
  // `onTituloAtualizado` é recriada a cada render do pai; incluí-la reavisaria
  // o pai a cada render, e só o título importa.
  // biome-ignore lint/correctness/useExhaustiveDependencies: só o título importa
  useEffect(() => {
    if (titulo) onTituloAtualizado(titulo);
  }, [titulo]);

  // Cola no fim a cada mudança — é o comportamento esperado de um chat.
  // `historico` e `stream` são o gatilho do scroll, não valores lidos no corpo.
  // biome-ignore lint/correctness/useExhaustiveDependencies: gatilho, não leitura
  useEffect(() => {
    const lista = refLista.current;
    if (lista) lista.scrollTop = lista.scrollHeight;
  }, [historico, stream]);

  async function enviar(texto: string) {
    if (enviando || !texto.trim()) return;

    // A resposta anterior ainda está em `stream`, e `setStream(ESTADO_INICIAL)`
    // abaixo a apagaria: é aqui que ela passa para o histórico. Fazer no mesmo
    // lote da pergunta nova mantém a ordem (resposta, pergunta) sem um quadro
    // em que a resposta some.
    const respostaAnterior = stream ? mensagemDaResposta(stream) : null;

    setEnviando(true);
    setErroEnvio('');
    setHistorico((h) => [
      ...h,
      ...(respostaAnterior ? [respostaAnterior] : []),
      { papel: 'user', conteudo: texto },
    ]);
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
        {historico.map((m, i) => (
          <Mensagem key={i} msg={m} renderArtefato={renderArtefato} escopo={escopo} />
        ))}

        {stream && (
          <BolhaStream
            stream={stream}
            emAndamento={enviando}
            erroEnvio={erroEnvio}
            renderArtefato={renderArtefato}
            escopo={escopo}
          />
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
  stream, emAndamento, erroEnvio, renderArtefato, escopo,
}: {
  stream: EstadoStream;
  emAndamento: boolean;
  erroEnvio: string;
  renderArtefato: RenderArtefato;
  escopo: EscopoDaConversa;
}) {
  return (
    <div className={`chat-msg chat-msg--assistant${emAndamento ? ' chat-msg--streaming' : ''}`}>
      {stream.traces.map((t) => <ToolTrace key={t.id} trace={t} escopo={escopo} />)}

      {stream.final ? (
        <>
          {/* Sem corpo vazio: a resposta que acabou em erro antes de qualquer
              texto mostra só o erro, embaixo. */}
          {stream.final.texto && (
            <div className="chat-msg__corpo">
              <Markdown texto={stream.final.texto} />
            </div>
          )}
          {stream.final.artefatos.map((art, i) => (
            <Fragment key={i}>{renderArtefato(art)}</Fragment>
          ))}
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
        placeholder="Pergunte algo ao Tio Léo..."
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
