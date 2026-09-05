import { useCallback, useEffect, useRef, useState } from 'react';

import { Conversa } from '../../../componentes/chat/Conversa';
import { CAPACIDADES_ALUNO, SUGESTOES_ALUNO } from '../../../dados/perfisSugestoes';
import * as api from '../../../servicos/api';
import * as sessao from '../../../servicos/sessao';
import type { ChatThreadDetalhe, ChatThreadResumo } from '../../../tipos/chat';
import { Folha } from '../pecas/Folha';
import { Icone } from '../pecas/Icone';
import { fmtDataCurta } from '../pecas/formato';

// A folha do Tio Léo — bottom sheet no celular, cartão flutuante de 400×620 no
// desktop (a geometria do artboard; o CSS está em aluno-tioleo.css).
//
// A MÁQUINA DE CONVERSA É A MESMA da coordenação (`Conversa`, `agente.py`); o
// que muda é a casca e o perfil, exatamente o que `perfis.py` já faz com
// prompt, tools e modelo (docs/27 §8). Por isso `Conversa` é importada, não
// copiada — dois streamings de SSE seria dois lugares para o mesmo bug.
//
// ⚠️ POR QUE O CARREGAMENTO DAS THREADS ESTÁ DUPLICADO AQUI. Hoje ele mora
// dentro do `ChatLauncher`, que serve à COORDENAÇÃO e precisa continuar
// não-modal (docs/10, docs/27 §8). Extrair um hook de lá mexeria no componente
// que o coordenador usa todo dia, e 40 linhas duplicadas custam menos que uma
// regressão no chat dele. Quando o casco do coordenador for reescrito, o hook
// sai destes dois lugares de uma vez.

interface Props {
  aberta: boolean;
  onFechar: () => void;
}

export function FolhaTioLeo({ aberta, onFechar }: Props) {
  const [threads, setThreads] = useState<ChatThreadResumo[]>([]);
  const [detalhe, setDetalhe] = useState<ChatThreadDetalhe | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');
  const [historicoAberto, setHistoricoAberto] = useState(false);

  // A thread aberta em ref, e não só em estado: `recarregarAtual` precisa dela
  // sem virar dependência de efeito — se virasse, cada troca de conversa
  // dispararia outra busca da mesma conversa.
  const idAtual = useRef<string | null>(null);
  // O FAB aparece em toda tela; buscar conversa no boot seria trabalho para
  // quem talvez nunca abra a folha.
  const jaCarregou = useRef(false);
  const estavaAberta = useRef(false);

  const aplicar = useCallback((thread: ChatThreadDetalhe) => {
    idAtual.current = thread.id;
    setDetalhe(thread);
  }, []);

  const carregarInicial = useCallback(async () => {
    setCarregando(true);
    setErro('');
    try {
      let lista = (await api.listarChatThreads()) as ChatThreadResumo[];
      if (lista.length === 0) lista = [(await api.criarChatThread()) as ChatThreadResumo];
      setThreads(lista);
      aplicar((await api.obterChatThread(lista[0].id)) as ChatThreadDetalhe);
    } catch (e) {
      setErro((e as Error).message || String(e));
    } finally {
      setCarregando(false);
    }
  }, [aplicar]);

  // Fechar a folha desmonta a `Conversa`, e com ela o histórico que só existia
  // em estado local. Reabrir sem recarregar mostraria a conversa truncada no
  // ponto em que ela foi aberta pela primeira vez — daí a releitura silenciosa:
  // se falhar, o que já está na tela continua valendo.
  const recarregarAtual = useCallback(async () => {
    const id = idAtual.current;
    if (!id) return;
    try {
      aplicar((await api.obterChatThread(id)) as ChatThreadDetalhe);
    } catch {
      // Silêncio de propósito: a releitura não foi pedida pelo aluno, e o que
      // já está na tela continua valendo. Errar aqui não é notícia para ele.
    }
  }, [aplicar]);

  useEffect(() => {
    const abriuAgora = aberta && !estavaAberta.current;
    estavaAberta.current = aberta;
    if (!abriuAgora) return;

    if (!jaCarregou.current) {
      jaCarregou.current = true;
      void carregarInicial();
      return;
    }
    void recarregarAtual();
  }, [aberta, carregarInicial, recarregarAtual]);

  async function novaConversa() {
    setHistoricoAberto(false);
    try {
      const nova = (await api.criarChatThread()) as ChatThreadResumo;
      setThreads((atuais) => [nova, ...atuais]);
      aplicar((await api.obterChatThread(nova.id)) as ChatThreadDetalhe);
    } catch (e) {
      setErro((e as Error).message || String(e));
    }
  }

  async function escolher(id: string) {
    setHistoricoAberto(false);
    if (id === idAtual.current) return;
    try {
      aplicar((await api.obterChatThread(id)) as ChatThreadDetalhe);
    } catch (e) {
      setErro((e as Error).message || String(e));
    }
  }

  /** O backend batiza a thread durante o stream; o título tem de acompanhar. */
  function renomear(titulo: string) {
    setDetalhe((d) => (d ? { ...d, titulo } : d));
    setThreads((ts) => ts.map((t) => (t.id === idAtual.current ? { ...t, titulo } : t)));
  }

  const primeiro = sessao.nome().split(' ')[0];

  return (
    <Folha
      aberta={aberta}
      className="alu-tioleo"
      altura="meio"
      onFechar={onFechar}
      titulo="Tio Léo"
      subtitulo="mentor de estudos"
      marca={<Icone nome="faisca" tamanho={20} />}
      acoes={
        <button
          type="button"
          className="alu-folha__botao-icone"
          aria-expanded={historicoAberto}
          onClick={() => setHistoricoAberto((v) => !v)}
        >
          <Icone nome="historico" tamanho={20} />
          <span className="alu-so-leitor">Suas conversas</span>
        </button>
      }
    >
      {historicoAberto ? (
        <Historico
          threads={threads}
          idAtivo={detalhe?.id ?? null}
          onEscolher={escolher}
          onNova={novaConversa}
        />
      ) : erro ? (
        <ErroDeAbertura mensagem={erro} onTentarDeNovo={carregarInicial} />
      ) : carregando || !detalhe ? (
        <Esqueleto />
      ) : (
        <>
          {/* A ABERTURA. Quem desenha as pílulas de sugestão é a própria
              `Conversa`, a partir de `sugestoes` — duplicá-las aqui daria duas
              listas para divergirem. O que falta lá é a saudação, e ela some
              por CSS quando as sugestões somem (`:has(.chat-sugestoes)` em
              aluno-tioleo.css): amarrar as duas por seletor evita repetir, num
              casco que não pode editar a `Conversa`, o estado de "a conversa já
              começou" que só existe dentro dela. */}
          <div className="alu-tioleo__abertura">
            <span className="alu-tioleo__faisca">
              <Icone nome="faisca" tamanho={44} />
            </span>
            <p className="alu-tioleo__saudacao">Oi{primeiro ? `, ${primeiro}` : ''}</p>
            <p className="alu-tioleo__pitch">
              Eu vejo suas notas, seus erros e o que mais cai nas provas.
            </p>
          </div>

          <Conversa
            key={detalhe.id}
            thread={detalhe}
            onTituloAtualizado={renomear}
            sugestoes={SUGESTOES_ALUNO}
            capacidades={CAPACIDADES_ALUNO}
          />
        </>
      )}
    </Folha>
  );
}

// ─── Estados ─────────────────────────────────────────────────────────────

/** Esqueleto com a forma da conversa, nunca um spinner. */
function Esqueleto() {
  return (
    <div className="alu-tioleo__esqueleto" aria-live="polite">
      <span className="alu-so-leitor">Abrindo a conversa</span>
      <span className="alu-tioleo__osso alu-tioleo__osso--curto" />
      <span className="alu-tioleo__osso" />
      <span className="alu-tioleo__osso alu-tioleo__osso--medio" />
    </div>
  );
}

/** Diz o que houve e o que fazer. Sem pedir desculpa e sem ser vago. */
function ErroDeAbertura({
  mensagem,
  onTentarDeNovo,
}: {
  mensagem: string;
  onTentarDeNovo: () => void;
}) {
  return (
    <div className="alu-tioleo__erro">
      <span className="alu-olho alu-olho--quieto">Conversa não abriu</span>
      <p className="alu-vazio">
        O Tio Léo não respondeu agora. Costuma ser conexão — tente de novo em alguns segundos.
      </p>
      <p className="alu-tioleo__erro-tecnico">{mensagem}</p>
      <button type="button" className="alu-tecla alu-tecla--pequena" onClick={onTentarDeNovo}>
        Tentar de novo
      </button>
    </div>
  );
}

// ─── Histórico ───────────────────────────────────────────────────────────

function Historico({
  threads,
  idAtivo,
  onEscolher,
  onNova,
}: {
  threads: ChatThreadResumo[];
  idAtivo: string | null;
  onEscolher: (id: string) => void;
  onNova: () => void;
}) {
  return (
    <div className="alu-tioleo__historico">
      <button type="button" className="alu-tecla alu-tecla--larga" onClick={onNova}>
        <Icone nome="mais" tamanho={17} />
        Nova conversa
      </button>

      {threads.length === 0 ? (
        <p className="alu-vazio">Comece a primeira conversa — pergunte como você foi no último simulado.</p>
      ) : (
        <ul className="alu-tioleo__conversas">
          {threads.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                className={`alu-conta__linha${t.id === idAtivo ? ' is-ativa' : ''}`}
                aria-current={t.id === idAtivo}
                onClick={() => onEscolher(t.id)}
              >
                <span className="alu-tioleo__conversa-titulo">{t.titulo || 'Conversa nova'}</span>
                {/* `ultimaMsgEm` é timestamp e `fmtDataCurta` espera só a data —
                    cortar em 10 reusa o formatador em vez de abrir um segundo. */}
                <span className="alu-tioleo__conversa-data">
                  {fmtDataCurta(t.ultimaMsgEm?.slice(0, 10))}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
