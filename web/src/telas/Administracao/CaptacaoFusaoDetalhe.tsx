import { useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { LayoutGroup, motion } from 'framer-motion';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { TarjaProcedencia } from '../../componentes/ui/TarjaProcedencia';
import {
  useConcluirRevisao,
  useCriarPerfilNoGrupo,
  useDecidirFusao,
  useFusao,
  useMoverConquista,
  useRemoverCandidatoVazio,
} from '../../hooks/captacao';
import { CaptacaoModalConquista } from './CaptacaoModalConquista';
import type { ConquistaExterna } from '../../tipos/captacao';

import '../../../styles/captacao.css';

// A ficha de UM grupo da fila de fusão (CaptacaoFusoes.tsx) — todo
// candidato_externo com este nome, lado a lado, pra decidir se é a mesma
// pessoa. A decisão é sempre de quem está olhando: o resolver nunca funde
// por nome sozinho (docs/41 §4.1), e esta tela não muda isso — só registra
// o que um humano decidiu.
//
// Dois caminhos, na mesma tela (pedido de 24/09/2026):
//
//   1. O binário de sempre — "São a mesma pessoa" / "Não são" — continua
//      sendo o caminho rápido pros grupos simples (a maioria: 2 candidatos,
//      2 UFs). Ele chama `confirmar`/`rejeitar`, sem mudança nenhuma.
//   2. O MODO AVANÇADO: arrastar cada resultado pro perfil certo, criar um
//      perfil vazio pra separar um homônimo, remover o que sobrar vazio. É
//      pra quando 2 destes 3 candidatos são a mesma pessoa e o terceiro não
//      — o caso que o binário não sabe expressar. Qualquer movimento manual
//      troca o rodapé pro botão único "Concluir revisão", porque rodar o
//      binário em cima de um grupo já editado à mão desfaria o trabalho.
//
// O "cartão-alvo" durante o arraste é achado por HIT-TEST de coordenada
// (`getBoundingClientRect` de cada cartão, refeito a cada `onDrag` — a lane
// rola na horizontal, então a posição muda), não por HTML5 drag-and-drop
// nativo: framer-motion foi escolhido de propósito porque dá suporte a
// TOQUE (tablet/celular), que o DnD nativo do browser não dá sem tratamento
// à parte.

const ID_FANTASMA = '__novo__';

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

export function CaptacaoFusaoDetalhe() {
  const { nome = '' } = useParams();
  const nomeNormalizado = decodeURIComponent(nome);
  const navegar = useNavigate();
  const { data, isPending, isError } = useFusao(nomeNormalizado);
  const decidir = useDecidirFusao(nomeNormalizado);
  const criarPerfil = useCriarPerfilNoGrupo(nomeNormalizado);
  const mover = useMoverConquista(nomeNormalizado);
  const remover = useRemoverCandidatoVazio(nomeNormalizado);
  const concluir = useConcluirRevisao(nomeNormalizado);

  const [erro, setErro] = useState('');
  const [conquistaAberta, setConquistaAberta] = useState<ConquistaExterna | null>(null);
  // Qualquer movimento manual troca o rodapé — ver o comentário de topo.
  const [houveEdicaoManual, setHouveEdicaoManual] = useState(false);
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

  async function confirmar() {
    setErro('');
    try {
      await decidir.mutateAsync('confirmar');
      navegar('/administracao/captacao/fusoes');
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível fundir.');
    }
  }

  async function rejeitar() {
    setErro('');
    try {
      await decidir.mutateAsync('rejeitar');
      navegar('/administracao/captacao/fusoes');
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível registrar a rejeição.');
    }
  }

  async function aoClicarNovoPerfil() {
    setErro('');
    try {
      await criarPerfil.mutateAsync();
      setHouveEdicaoManual(true);
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível criar o perfil.');
    }
  }

  async function aoRemoverVazio(candidatoId: string) {
    setErro('');
    try {
      await remover.mutateAsync(candidatoId);
      setHouveEdicaoManual(true);
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível remover.');
    }
  }

  async function aoConcluir() {
    setErro('');
    try {
      await concluir.mutateAsync();
      navegar('/administracao/captacao/fusoes');
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível concluir.');
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
      setHouveEdicaoManual(true);
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível mover.');
    }
  }

  if (isPending) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao/fusoes" destino="Fila de fusão" />
        <div className="empty-state">Carregando…</div>
      </div>
    );
  }

  if (isError || !data || data.candidatos.length < 2) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao/fusoes" destino="Fila de fusão" />
        <div className="empty-state">
          Não achei mais de um candidato com este nome.
          <div className="empty-state__hint">
            Talvez já tenha sido decidido — volte pra fila pra ver o que sobrou.
          </div>
        </div>
      </div>
    );
  }

  // Confiança da MESMA forma que a lista calcula (v_fusao_candidata): uma
  // UF só entre todo mundo do grupo é o sinal de que provavelmente é a
  // mesma pessoa; mais de uma é o caso real que já apareceu (Antonio
  // Eduardo Rossano — Fortaleza/CE numa conquista, Santa Fé do Sul/SP
  // noutra) — mesmo nome, talvez pessoas diferentes.
  const ufs = new Set(data.candidatos.map((c) => c.uf).filter(Boolean));
  const confiavel = ufs.size <= 1;
  const perfisComResultado = data.candidatos.filter((c) => c.conquistas.length > 0).length;
  const resumoTexto =
    perfisComResultado <= 1
      ? 'Só um perfil vai ficar com resultado — isso equivale a fundir todo mundo num candidato só.'
      : `${perfisComResultado} perfis distintos vão continuar separados, cada um com seus próprios resultados.`;

  return (
    <div className="tela">
      <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao/fusoes" destino="Fila de fusão" />

      <div className="tela-cabecalho">
        <p className="tela-subtitulo">
          {data.candidatos.length} candidatos com este nome.{' '}
          {confiavel
            ? 'Todos na mesma UF — sinal forte de que é a mesma pessoa.'
            : `UFs diferentes entre os candidatos (${[...ufs].join(', ') || '—'}) — pode ser gente diferente com o mesmo nome.`}
        </p>
        <p className="tela-subtitulo fusao-dica">
          Arraste os blocos de resultado entre os perfis pra reorganizar quem é quem, ou crie um
          perfil novo pra separar alguém que não é a mesma pessoa.
        </p>
      </div>

      <LayoutGroup>
        <div className="fusao-pista">
          {data.candidatos.map((c) => (
            <div
              key={c.id}
              ref={(el) => registrarRefCartao(c.id, el)}
              className={`fusao-cartao${alvoValido === c.id ? ' fusao-cartao--alvo' : ''}`}
            >
              <div className="fusao-cartao__cabecalho">
                <h2 className="section__title">{c.escola || '— sem escola —'}</h2>
                <p className="section__subtitle">
                  {[c.cidade, c.uf].filter(Boolean).join(' · ') || 'Sem cidade/UF'} · {c.conquistas.length}{' '}
                  {c.conquistas.length === 1 ? 'resultado' : 'resultados'} · status {c.status_captacao}
                </p>
                {/* Aviso automático (docs/41 §9): nível de ensino conflitante
                    no mesmo ano com outro candidato deste nome. Antes era
                    `<p className="agendar__erro">` (classe emprestada, fora
                    do design system); agora usa o mesmo TarjaProcedencia da
                    fila e da ficha — um vocabulário só pro mesmo sinal. */}
                {c.observacoes && <TarjaProcedencia estado="falhou" fonte={c.observacoes} />}
              </div>

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
                          publica) + o link pra fonte, num modal só — mesmo
                          padrão de CaptacaoFicha.tsx. */}
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
          ))}

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

      <section className="card">
        {houveEdicaoManual ? (
          <>
            <h2 className="section__title">Revisão manual</h2>
            <p className="tela-subtitulo">{resumoTexto}</p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
              <button
                type="button"
                className="btn btn--primary"
                disabled={concluir.isPending}
                onClick={aoConcluir}
              >
                {concluir.isPending ? 'Concluindo…' : 'Concluir revisão'}
              </button>
              {erro && <span className="agendar__erro">{erro}</span>}
            </div>
          </>
        ) : (
          <>
            <h2 className="section__title">É a mesma pessoa?</h2>
            <p className="tela-subtitulo">
              Confirmando, os {data.candidatos.length} candidatos viram UM só — todas as conquistas
              somadas, o retrato (escola/cidade/UF) atualizado pela conquista mais recente. Rejeitando,
              este nome sai da fila e não volta a ser sugerido.
            </p>
            <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
              <button type="button" className="btn btn--primary" disabled={decidir.isPending} onClick={confirmar}>
                {decidir.isPending ? 'Fundindo…' : 'São a mesma pessoa'}
              </button>
              <button type="button" className="btn btn--ghost" disabled={decidir.isPending} onClick={rejeitar}>
                Não são
              </button>
              {erro && <span className="agendar__erro">{erro}</span>}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
