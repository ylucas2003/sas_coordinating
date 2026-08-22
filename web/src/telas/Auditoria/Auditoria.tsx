import { useMemo, useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import { Sidebar } from '../../componentes/layout/Sidebar';
import { CorpoChips, PainelFiltros } from '../../componentes/ui/filtros/PainelFiltros';
import * as api from '../../servicos/api';
import type { CanalAuditoria, EventoAuditoria } from '../../tipos/dominio';

// A linha do tempo que a coordenação pediu: "puxar todas as alterações que
// foram feitas… para rodar algum script depois caso alguém faça merda"
// (21/08, 19h06). Lê `evento_auditoria` por canal (docs/18 §3).
//
// O que se mostra aqui é NARRATIVA — quem, quando, qual decisão. A
// reversibilidade não mora no log: mora na linha (`nota.pontuacao_canvas`),
// porque o log é melhor-esforço e um INSERT que falhou em silêncio não pode
// produzir um script de reversão incompleto e confiante (docs/18 §3.4).

const CANAL_LABEL: Record<CanalAuditoria, string> = {
  acesso: 'Acesso',
  nota: 'Notas',
  simulado: 'Simulados',
  ciclo: 'Ciclos',
  canvas: 'Canvas',
};

const ACAO_LABEL: Record<string, string> = {
  login_ok: 'entrou',
  login_falhou: 'falhou ao entrar',
  primeiro_acesso_bloqueado: 'tentou primeiro acesso (bloqueado)',
  acesso_resetado: 'zerou a senha de um aluno',
  nota_editada: 'editou uma nota',
  simulado_criado: 'agendou um simulado',
  simulado_editado: 'editou um simulado',
  simulado_removido: 'desmarcou um simulado',
  ciclo_criado: 'criou um ciclo',
  enviado_ao_canvas: 'enviou ao Canvas',
};

function fmtQuando(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

/** Link para o objeto, quando o recurso aponta para algo navegável. */
function LinkRecurso({ recurso }: { recurso: string | null }) {
  if (!recurso) return null;
  const [tipo, id] = recurso.split('/');
  const destino =
    tipo === 'aluno' ? `/alunos/${id}`
    : tipo === 'simulado' ? `/simulados/${id}`
    : tipo === 'ciclo' ? `/ciclos/${id}`
    : tipo === 'nota' ? `/alunos/${id}`
    : null;
  if (!destino) return <code className="auditoria__recurso">{recurso}</code>;
  return <Link className="auditoria__recurso" to={destino}>{recurso}</Link>;
}

/**
 * A decisão, em uma linha. É o que distingue "escolheu não mandar" de
 * "tentou e falhou" — a diferença que o estado `divergente` existe para
 * marcar (docs/18 §3.3).
 */
function Decisao({ detalhe, quem }: { detalhe: Record<string, unknown> | null; quem: string }) {
  if (!detalhe) return null;
  const partes: string[] = [];
  if ('valor_antes' in detalhe || 'valor_depois' in detalhe) {
    partes.push(`${String(detalhe.valor_antes ?? '—')} → ${String(detalhe.valor_depois ?? '—')}`);
  }
  if (typeof detalhe.aluno === 'string') partes.push(detalhe.aluno);
  if (typeof detalhe.nome === 'string' && detalhe.nome !== quem) partes.push(detalhe.nome);
  if ('sincronizar_canvas' in detalhe) {
    if (detalhe.sincronizar_canvas === false) partes.push('só no site');
    else if (detalhe.canvas_ok === true || detalhe.canvas_estado === 'sincronizado') partes.push('enviado ao Canvas');
    else if (detalhe.canvas_ok === false) partes.push(`Canvas falhou: ${String(detalhe.canvas_erro ?? '')}`);
    else if (detalhe.canvas_estado) partes.push(`Canvas: ${String(detalhe.canvas_estado)}`);
  }
  if (typeof detalhe.motivo === 'string') partes.push(detalhe.motivo);
  if (!partes.length) return null;
  return <span className="auditoria__decisao">{partes.join(' · ')}</span>;
}

export function Auditoria() {
  const [canais, setCanais] = useState<ReadonlySet<string>>(new Set());
  // Só criações e alterações por padrão — login não muda nada (22/08).
  const [incluirLogins, setIncluirLogins] = useState(false);
  const [abertas, setAbertas] = useState<ReadonlySet<string>>(new Set(['canal']));
  // Paginação por cursor: cada "carregar mais" empilha uma página.
  const [cursores, setCursores] = useState<Array<number | undefined>>([undefined]);

  const canal = canais.size === 1 ? [...canais][0] : undefined;
  const paginas = cursores.map((antes_de_id) => ({ canal, limite: 100, antes_de_id, incluir_logins: incluirLogins }));

  // Uma query por página, num hook só — o número de páginas varia e a regra
  // dos hooks não aceita `map(useQuery)`. A trilha só cresce, então o que
  // já carregou não muda: 30 s de staleTime evita refetch a cada volta.
  const consultas = useQueries({
    queries: paginas.map((filtro) => ({
      queryKey: ['auditoria', filtro],
      queryFn: () => api.listarAuditoria(filtro),
      staleTime: 30 * 1000,
    })),
  });

  const eventos = useMemo(() => {
    const todas = consultas.flatMap((q) => q.data?.eventos ?? []);
    // Vários canais marcados = filtra no cliente (a API filtra um só).
    return canais.size > 1 ? todas.filter((e) => e.canal && canais.has(e.canal)) : todas;
  }, [consultas, canais]);

  const primeira = consultas[0];
  const proximo = consultas[consultas.length - 1]?.data?.proximo_antes_de_id ?? null;

  function alternar(valor: string) {
    setCanais((s) => {
      const novo = new Set(s);
      if (novo.has(valor)) novo.delete(valor);
      else novo.add(valor);
      return novo;
    });
    setCursores([undefined]);
  }

  return (
    <>
      <Sidebar rotulo="Filtros">
        <PainelFiltros
          abertas={abertas}
          onToggleSecao={(chave) => setAbertas((a) => {
            const novo = new Set(a);
            if (novo.has(chave)) novo.delete(chave);
            else novo.add(chave);
            return novo;
          })}
          algumAtivo={canais.size > 0 || incluirLogins}
          onLimpar={() => { setCanais(new Set()); setIncluirLogins(false); setCursores([undefined]); }}
          secoes={[
            {
              chave: 'canal', rotulo: 'Canal', icone: 'ciclos',
              corpo: (
                <CorpoChips
                  opcoes={(Object.keys(CANAL_LABEL) as CanalAuditoria[]).map((c) => ({ valor: c, label: CANAL_LABEL[c] }))}
                  selecionados={canais}
                  onToggle={alternar}
                />
              ),
            },
            {
              chave: 'incluir', rotulo: 'Incluir também', icone: 'turmas',
              corpo: (
                <CorpoChips
                  opcoes={[{ valor: 'logins', label: 'Entradas no sistema' }]}
                  selecionados={new Set<string>(incluirLogins ? ['logins'] : [])}
                  onToggle={() => { setIncluirLogins((v) => !v); setCursores([undefined]); }}
                />
              ),
            },
          ]}
        />
      </Sidebar>

      <main className="app-main">
        <section className="card">
          <div className="screen-header">
            <div>
              <div className="screen-breadcrumb">Auditoria</div>
              <h1 className="screen-title">Linha do tempo</h1>
              <p className="screen-subtitle">
                {incluirLogins
                  ? 'Tudo que foi criado, alterado — e quem entrou no sistema.'
                  : 'Tudo que foi criado ou alterado, e o que cada um escolheu fazer no Canvas.'}
              </p>
            </div>
          </div>

          {primeira.isPending ? (
            <div className="section"><p className="section__subtitle">Carregando…</p></div>
          ) : eventos.length === 0 ? (
            <div className="empty-state">Nenhum evento registrado com esses filtros.</div>
          ) : (
            <ol className="auditoria">
              {eventos.map((e) => <Evento key={e.id} evento={e} />)}
            </ol>
          )}

          {proximo != null && (
            <div className="auditoria__mais">
              <button className="btn btn--ghost" onClick={() => setCursores((c) => [...c, proximo])}>
                Carregar mais antigos
              </button>
            </div>
          )}
        </section>
      </main>
    </>
  );
}

function Evento({ evento: e }: { evento: EventoAuditoria }) {
  const quem = e.ator_nome || e.ator_id || (e.ator_tipo ? `(${e.ator_tipo})` : '—');
  return (
    <li className={`auditoria__evento auditoria__evento--${e.canal ?? 'outro'}`}>
      <time className="auditoria__quando" dateTime={e.ocorrido_em}>{fmtQuando(e.ocorrido_em)}</time>
      <span className={`auditoria__canal auditoria__canal--${e.canal ?? 'outro'}`}>
        {e.canal ? CANAL_LABEL[e.canal] : '—'}
      </span>
      <span className="auditoria__texto">
        <strong>{quem}</strong>
        {` ${ACAO_LABEL[e.acao] ?? e.acao} `}
        <LinkRecurso recurso={e.recurso} />
        <Decisao detalhe={e.detalhe} quem={quem} />
      </span>
      {e.request_id && (
        <code className="auditoria__request" title="X-Request-Id — costura com os logs do servidor">
          {e.request_id.slice(0, 8)}
        </code>
      )}
    </li>
  );
}
