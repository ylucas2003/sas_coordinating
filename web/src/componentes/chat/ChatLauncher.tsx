import { useCallback, useEffect, useState } from 'react';
import { Conversa } from './Conversa';
import { ListaThreads } from './ListaThreads';
import * as api from '../../servicos/api';
import type { ChatThreadDetalhe, ChatThreadResumo, GrupoSugestoes } from '../../tipos/chat';

// Botão flutuante (FAB) + painel lateral que convive com a página.
//
// Não-modal de propósito: não há overlay bloqueando o fundo, então dá para
// navegar pelo site com a conversa aberta. Por isso clique-fora não fecha, e
// o Esc só fecha quando o foco está dentro do painel — do contrário o Esc de
// um dropdown qualquer da página derrubaria a conversa.

interface Props {
  rotuloFab?: string;
  tituloDrawer?: string;
  sugestoes: GrupoSugestoes[];
  capacidades: string[];
}

export function ChatLauncher({
  rotuloFab = 'Assistente',
  tituloDrawer = 'Assistente',
  sugestoes,
  capacidades,
}: Props) {
  const [aberto, setAberto] = useState(false);
  const [listaAberta, setListaAberta] = useState(false);
  const [threads, setThreads] = useState<ChatThreadResumo[]>([]);
  const [detalhe, setDetalhe] = useState<ChatThreadDetalhe | null>(null);
  const [carregou, setCarregou] = useState(false);
  const [erro, setErro] = useState('');

  const carregarInicial = useCallback(async () => {
    try {
      let lista = (await api.listarChatThreads()) as ChatThreadResumo[];
      if (lista.length === 0) {
        const nova = (await api.criarChatThread()) as ChatThreadResumo;
        lista = [nova];
      }
      setThreads(lista);
      setDetalhe((await api.obterChatThread(lista[0].id)) as ChatThreadDetalhe);
    } catch (e) {
      setErro(`Falha carregando conversas: ${(e as Error).message}`);
    }
  }, []);

  // Carrega as conversas só na primeira abertura — o FAB aparece em toda
  // tela, e buscar threads no boot seria trabalho para quem talvez nem abra.
  useEffect(() => {
    if (!aberto || carregou) return;
    setCarregou(true);
    void carregarInicial();
  }, [aberto, carregou, carregarInicial]);

  // A classe no <body> é o que empurra o conteúdo da página para o lado.
  useEffect(() => {
    document.body.classList.toggle('chat-aberto', aberto);
    return () => document.body.classList.remove('chat-aberto');
  }, [aberto]);

  useEffect(() => {
    function aoTeclar(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setAberto((a) => !a);
        return;
      }
      if (e.key === 'Escape' && aberto) {
        const drawer = document.querySelector('.chat-drawer');
        if (drawer?.contains(document.activeElement)) setAberto(false);
      }
    }
    document.addEventListener('keydown', aoTeclar);
    return () => document.removeEventListener('keydown', aoTeclar);
  }, [aberto]);

  async function novaThread() {
    setListaAberta(false);
    try {
      const nova = (await api.criarChatThread()) as ChatThreadResumo;
      setThreads((t) => [nova, ...t]);
      setDetalhe((await api.obterChatThread(nova.id)) as ChatThreadDetalhe);
    } catch (e) {
      setErro(`Falha ao criar conversa: ${(e as Error).message}`);
    }
  }

  async function selecionar(id: string) {
    setListaAberta(false);
    if (id === detalhe?.id) return;
    setDetalhe((await api.obterChatThread(id)) as ChatThreadDetalhe);
  }

  async function apagar(id: string) {
    try {
      await api.apagarChatThread(id);
    } catch (e) {
      setErro(`Falha ao apagar: ${(e as Error).message}`);
      return;
    }

    const restantes = threads.filter((t) => t.id !== id);
    setThreads(restantes);

    if (detalhe?.id !== id) return;
    // Apagou a conversa aberta: cai na próxima, ou cria uma se acabaram.
    if (restantes.length === 0) return void novaThread();
    setDetalhe((await api.obterChatThread(restantes[0].id)) as ChatThreadDetalhe);
  }

  function renomear(titulo: string) {
    setDetalhe((d) => (d ? { ...d, titulo } : d));
    setThreads((ts) => ts.map((t) => (t.id === detalhe?.id ? { ...t, titulo } : t)));
  }

  return (
    <>
      <button
        className="chat-fab"
        title={`Conversar com o ${rotuloFab.toLowerCase()}`}
        onClick={() => setAberto((a) => !a)}
      >
        <span className="chat-fab__icone">💬</span>
        <span className="chat-fab__label">{rotuloFab}</span>
      </button>

      <aside
        className={`chat-drawer${aberto ? ' is-aberto' : ''}`}
        role="complementary"
        aria-label="Chat com o assistente"
      >
        {aberto && (
          <>
            <div className="chat-drawer__header">
              <div className="chat-drawer__header-info">
                <button
                  className="chat-drawer__btn-threads"
                  title="Suas conversas"
                  onClick={() => setListaAberta((v) => !v)}
                >
                  ☰
                </button>
                <div className="chat-drawer__titulo-bloco">
                  <div className="chat-drawer__pequeno">{tituloDrawer}</div>
                  <h2 className="chat-drawer__titulo">{detalhe?.titulo || 'Conversa'}</h2>
                </div>
              </div>
              <div className="chat-drawer__header-acoes">
                <button className="chat-drawer__btn-icone" title="Nova conversa" onClick={novaThread}>
                  +
                </button>
                <button className="chat-drawer__btn-icone" title="Fechar" onClick={() => setAberto(false)}>
                  ×
                </button>
              </div>
            </div>

            {erro && <div className="chat-msg__erro">{erro}</div>}

            {listaAberta && (
              <div className="chat-drawer__threads-overlay">
                <ListaThreads
                  threads={threads}
                  threadAtivaId={detalhe?.id ?? null}
                  onNovaThread={novaThread}
                  onSelecionar={selecionar}
                  onApagar={apagar}
                />
              </div>
            )}

            {detalhe && (
              <Conversa
                key={detalhe.id}
                thread={detalhe}
                onTituloAtualizado={renomear}
                sugestoes={sugestoes}
                capacidades={capacidades}
              />
            )}
          </>
        )}
      </aside>
    </>
  );
}
