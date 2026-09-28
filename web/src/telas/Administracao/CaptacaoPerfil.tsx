import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { LayoutGroup, motion } from 'framer-motion';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { rotuloDaSerie, serieEstimadaHoje } from '../../dominio/captacao';
import {
  useAtualizarCandidato,
  useCriarPerfil,
  useMoverConquista,
  usePerfisDoNome,
  useRemoverCandidatoVazio,
} from '../../hooks/captacao';
import { CaptacaoModalConquista } from './CaptacaoModalConquista';
import type { ConquistaExterna, PerfilDoNome, StatusCaptacao } from '../../tipos/captacao';

import '../../../styles/captacao.css';

// A ficha de QUALQUER nome da captação (docs/41, simplificação de
// 25/09/2026) — não só "casos em disputa". Todo `candidato_externo` nasce
// 1:1 com uma conquista (`resolver_candidatos_externos.py` não agrupa mais
// nada sozinho); a maioria dos nomes tem exatamente 1 perfil, e esta tela
// abre pra ele do mesmo jeito. Quando um nome tem mais de um (homônimo raro,
// ou fonte sem escola que nunca cruzou sozinha com o resto), o coordenador
// arrasta os blocos de resultado entre os cartões pra reorganizar quem é
// quem — cada arraste já persiste na hora, sozinho. Não existe "concluir":
// não há decisão permanente nenhuma pra registrar (era exatamente esse
// mecanismo — um nome "decidido" ficava escondido pra sempre — que causou o
// bug achado em produção com "Yan Lucas Freitas de Araújo").
//
// O "cartão-alvo" durante o arraste é achado por HIT-TEST de coordenada
// (`getBoundingClientRect` de cada cartão, refeito a cada `onDrag` — a lane
// rola na horizontal, então a posição muda), não por HTML5 drag-and-drop
// nativo: framer-motion foi escolhido de propósito porque dá suporte a
// TOQUE (tablet/celular), que o DnD nativo do browser não dá sem tratamento
// à parte.

const ID_FANTASMA = '__novo__';

const STATUS_LABEL: Record<StatusCaptacao, string> = {
  novo: 'Novo',
  contatado: 'Contatado',
  interessado: 'Interessado',
  matriculado: 'Matriculado',
  descartado: 'Descartado',
};

function coordenadasDoEvento(evento: MouseEvent | TouchEvent | PointerEvent): { x: number; y: number } {
  if ('clientX' in evento) return { x: evento.clientX, y: evento.clientY };
  const toque = evento.touches[0] ?? evento.changedTouches[0];
  return { x: toque?.clientX ?? 0, y: toque?.clientY ?? 0 };
}

function GripDoBloco() {
  return (
    <svg width="10" height="16" viewBox="0 0 10 16" fill="none" aria-hidden="true" className="fusao-bloco__grip">
      <circle cx="2.5" cy="2.5" r="1.4" fill="currentColor" />
      <circle cx="7.5" cy="2.5" r="1.4" fill="currentColor" />
      <circle cx="2.5" cy="8" r="1.4" fill="currentColor" />
      <circle cx="7.5" cy="8" r="1.4" fill="currentColor" />
      <circle cx="2.5" cy="13.5" r="1.4" fill="currentColor" />
      <circle cx="7.5" cy="13.5" r="1.4" fill="currentColor" />
    </svg>
  );
}

/**
 * O funil manual (status + observações) de UM cartão — reaproveita
 * `PATCH /captacao/candidatos/{id}`, que não mudou. Status salva no
 * `onChange` (valor único, baixo risco — mesmo padrão imediato das pills de
 * filtro que já existem no app). Observações fica atrás de um disclosure
 * fechado por padrão (protege o espaço do cartão, que existe pra arrastar) e
 * salva em autosave DEBOUNCED (~800ms) + flush no blur — um blur puro seria
 * frágil aqui especificamente: o gesto principal da tela é arrastar, e um
 * clique de arraste solto em outro canto do cartão dispara blur no meio de
 * uma frase.
 */
function FunilDoCartao({ candidato, nomeNormalizado }: { candidato: PerfilDoNome; nomeNormalizado: string }) {
  const atualizar = useAtualizarCandidato(candidato.id, nomeNormalizado);
  const [observacoes, setObservacoes] = useState(candidato.observacoes ?? '');
  const [abertoObs, setAbertoObs] = useState(false);
  const [estado, setEstado] = useState<'ocioso' | 'salvando' | 'salvo' | 'erro'>('ocioso');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setObservacoes(candidato.observacoes ?? '');
  }, [candidato.observacoes]);

  function salvarObservacoes(valor: string) {
    setEstado('salvando');
    atualizar.mutate(
      { observacoes: valor },
      { onSuccess: () => setEstado('salvo'), onError: () => setEstado('erro') },
    );
  }

  function aoDigitar(valor: string) {
    setObservacoes(valor);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => salvarObservacoes(valor), 800);
  }

  function aoSairDoCampo() {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (observacoes !== (candidato.observacoes ?? '')) salvarObservacoes(observacoes);
  }

  return (
    <div className="fusao-funil">
      <select
        className="fusao-funil__status"
        value={candidato.status_captacao}
        disabled={atualizar.isPending}
        onChange={(e) => atualizar.mutate({ status_captacao: e.target.value as StatusCaptacao })}
      >
        {(Object.keys(STATUS_LABEL) as StatusCaptacao[]).map((v) => (
          <option key={v} value={v}>{STATUS_LABEL[v]}</option>
        ))}
      </select>
      <button type="button" className="fusao-funil__toggle" onClick={() => setAbertoObs((v) => !v)}>
        {abertoObs ? '▾' : '▸'} Observações
      </button>
      {abertoObs && (
        <div className="fusao-funil__obs">
          <textarea
            value={observacoes}
            onChange={(e) => aoDigitar(e.target.value)}
            onBlur={aoSairDoCampo}
            placeholder="Anotações da coordenação sobre este perfil…"
          />
          <span className="fusao-funil__estado">
            {estado === 'salvando' && 'Salvando…'}
            {estado === 'salvo' && 'Salvo'}
            {estado === 'erro' && 'Não foi possível salvar'}
          </span>
        </div>
      )}
    </div>
  );
}

export function CaptacaoPerfil() {
  const { nome = '' } = useParams();
  const nomeNormalizado = decodeURIComponent(nome);
  const { data, isPending, isError } = usePerfisDoNome(nomeNormalizado);
  const criarPerfil = useCriarPerfil(nomeNormalizado);
  const mover = useMoverConquista(nomeNormalizado);
  const remover = useRemoverCandidatoVazio(nomeNormalizado);

  const [erro, setErro] = useState('');
  const [conquistaAberta, setConquistaAberta] = useState<ConquistaExterna | null>(null);
  const [arrastandoId, setArrastandoId] = useState<string | null>(null);
  const [alvoValido, setAlvoValido] = useState<string | null>(null);
  const refsCartao = useRef(new Map<string, HTMLElement>());

  function registrarRefCartao(id: string, el: HTMLElement | null): void {
    if (el) refsCartao.current.set(id, el);
    else refsCartao.current.delete(id);
  }

  function cartaoNoPonto(x: number, y: number): string | null {
    for (const [id, el] of refsCartao.current) {
      const r = el.getBoundingClientRect();
      if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return id;
    }
    return null;
  }

  async function aoClicarNovoPerfil() {
    setErro('');
    try {
      await criarPerfil.mutateAsync();
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível criar o perfil.');
    }
  }

  async function aoRemoverVazio(candidatoId: string) {
    setErro('');
    try {
      await remover.mutateAsync(candidatoId);
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível remover.');
    }
  }

  async function aoSoltarBloco(
    evento: MouseEvent | TouchEvent | PointerEvent,
    conquistaId: string,
    origemId: string,
  ) {
    const { x, y } = coordenadasDoEvento(evento);
    const alvo = cartaoNoPonto(x, y);
    setArrastandoId(null);
    setAlvoValido(null);
    if (!alvo || alvo === origemId) return;

    setErro('');
    try {
      const candidatoDestino = alvo === ID_FANTASMA ? (await criarPerfil.mutateAsync()).id : alvo;
      await mover.mutateAsync({ conquistaId, candidatoId: candidatoDestino });
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível mover.');
    }
  }

  if (isPending) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao" destino="Captação externa" />
        <div className="empty-state">Carregando…</div>
      </div>
    );
  }

  if (isError || !data || data.candidatos.length < 1) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao" destino="Captação externa" />
        <div className="empty-state">Não achei nenhum candidato com este nome.</div>
      </div>
    );
  }

  const anoAtual = new Date().getFullYear();

  return (
    <div className="tela">
      <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao" destino="Captação externa" />

      <div className="tela-cabecalho">
        <p className="tela-subtitulo">
          {data.candidatos.length} {data.candidatos.length === 1 ? 'perfil' : 'perfis'} com este nome.
          {data.candidatos.length > 1 &&
            ' Arraste os blocos de resultado entre eles pra reorganizar quem é quem, ou crie um perfil novo pra separar alguém que não é a mesma pessoa.'}
        </p>
        {erro && <p className="agendar__erro">{erro}</p>}
      </div>

      <LayoutGroup>
        <div className="fusao-pista">
          {data.candidatos.map((c) => {
            const rotulo = rotuloDaSerie(serieEstimadaHoje(c, anoAtual));
            return (
              <div
                key={c.id}
                ref={(el) => registrarRefCartao(c.id, el)}
                className={`fusao-cartao${alvoValido === c.id ? ' fusao-cartao--alvo' : ''}`}
              >
                <div className="fusao-cartao__cabecalho">
                  <h2 className="section__title">{c.escola || '— sem escola —'}</h2>
                  <p className="section__subtitle">
                    {[c.cidade, c.uf].filter(Boolean).join(' · ') || 'Sem cidade/UF'} · {c.conquistas.length}{' '}
                    {c.conquistas.length === 1 ? 'resultado' : 'resultados'}
                  </p>
                  {rotulo && <p className="fusao-cartao__serie">{rotulo}</p>}
                </div>

                <FunilDoCartao candidato={c} nomeNormalizado={nomeNormalizado} />

                <div className="fusao-cartao__lista">
                  {c.conquistas.map((q) => (
                    <motion.div
                      key={q.id}
                      layout
                      layoutId={q.id}
                      drag
                      dragSnapToOrigin
                      dragElastic={0.15}
                      whileDrag={{ scale: 1.03, zIndex: 30 }}
                      onDragStart={() => setArrastandoId(q.id)}
                      onDrag={(evento) => {
                        const { x, y } = coordenadasDoEvento(evento);
                        const alvo = cartaoNoPonto(x, y);
                        setAlvoValido(alvo && alvo !== c.id ? alvo : null);
                      }}
                      onDragEnd={(evento) => aoSoltarBloco(evento, q.id, c.id)}
                      className="fusao-bloco"
                      style={{ opacity: arrastandoId === q.id ? 0.35 : 1 }}
                    >
                      <GripDoBloco />
                      <div className="fusao-bloco__texto">
                        <span className="fusao-bloco__linha1">
                          <span style={{ fontVariantNumeric: 'tabular-nums' }}>{q.ano}</span>
                          <span className="fusao-bloco__prova">{q.prova_nome}</span>
                        </span>
                        {/* Clicar expande nota por matéria (quando a fonte
                            publica) + o link pra fonte, num modal só. */}
                        <button type="button" className="link-botao" onClick={() => setConquistaAberta(q)}>
                          {q.resultado}
                        </button>
                      </div>
                    </motion.div>
                  ))}

                  {c.conquistas.length === 0 && (
                    <div className="fusao-vazio">
                      <p>Sem resultados — arraste um bloco pra cá.</p>
                      <button type="button" className="link-botao" onClick={() => aoRemoverVazio(c.id)}>
                        Remover perfil vazio
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          <button
            type="button"
            ref={(el) => registrarRefCartao(ID_FANTASMA, el)}
            className={`fusao-fantasma${alvoValido === ID_FANTASMA ? ' fusao-cartao--alvo' : ''}`}
            onClick={aoClicarNovoPerfil}
            disabled={criarPerfil.isPending}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M10 3v14M3 10h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <span className="fusao-fantasma__titulo">Novo perfil</span>
            <span className="fusao-fantasma__dica">pra separar alguém que não é a mesma pessoa</span>
          </button>
        </div>
      </LayoutGroup>

      {conquistaAberta && (
        <CaptacaoModalConquista conquista={conquistaAberta} onFechar={() => setConquistaAberta(null)} />
      )}
    </div>
  );
}
