import { useState } from 'react';
import { Link } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { BarraFiltros, PillsUnica } from '../../componentes/ui/filtros/BarraFiltros';
import { useFusoes } from '../../hooks/captacao';

// A fila de fusão de baixa confiança (docs/41 §8, item 1). O resolver só
// funde candidato_externo por nome+escola EXATOS (§4.1) — de propósito,
// pra nunca juntar duas pessoas diferentes por engano. Isso deixa cada
// conquista de fonte sem escola (OBM, ITA, IME) como candidato PRÓPRIO,
// mesmo quando é a mesma pessoa que a OBMEP/OBF já resolveram.
//
// Esta tela é o segundo nível: nome sozinho, cidade/UF como confiança
// extra — mais barato de achar, mais arriscado de confiar. Por isso NUNCA
// funde sozinho: só lista, e a decisão (mesma pessoa ou não) é sempre de
// quem está olhando, na ficha de cada grupo (CaptacaoFusaoDetalhe.tsx).

const POR_PAGINA = 20;

export function CaptacaoFusoes() {
  const [pagina, setPagina] = useState(1);
  const [ufIncerta, setUfIncerta] = useState<boolean | null>(null);
  const { data, isPending, isError, isPlaceholderData } = useFusoes({
    ufIncerta: ufIncerta ?? undefined,
    pagina,
    porPagina: POR_PAGINA,
  });

  const grupos = data?.grupos ?? [];
  const total = data?.total ?? 0;
  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Fila de fusão" para="/administracao/captacao" destino="Captação externa" />

      <div className="tela-cabecalho">
        <p className="tela-subtitulo">
          Nomes que aparecem em mais de um candidato — a mesma pessoa, possivelmente, cruzada de
          fontes sem escola (OBM, ITA, IME) que nunca se juntam sozinhas. Ordenada da mais confiável
          (mesma UF em todo mundo do grupo) pra menos. Ninguém é fundido sem alguém confirmar.
        </p>
      </div>

      <BarraFiltros
        tela="captacao-fusoes"
        algumAtivo={ufIncerta === true}
        onLimpar={() => { setUfIncerta(null); setPagina(1); }}
        grupos={[
          {
            chave: 'confianca',
            rotulo: 'Confiança',
            resumo: ufIncerta ? 'só incertos' : null,
            corpo: (
              <PillsUnica
                opcoes={[
                  { valor: 'todos', label: 'Todos' },
                  { valor: 'incertos', label: 'Só incertos (UF divergente)' },
                ]}
                selecionado={ufIncerta ? 'incertos' : 'todos'}
                onSelecionar={(v) => { setUfIncerta(v === 'incertos'); setPagina(1); }}
              />
            ),
          },
        ]}
      />

      <section className="card">
        <div className="tela-cabecalho" style={{ padding: '10px 16px 0' }}>
          <p className="tela-subtitulo">
            {isPending
              ? 'Carregando…'
              : `${total.toLocaleString('pt-BR')} ${total === 1 ? 'nome' : 'nomes'} na fila · página ${pagina} de ${totalPaginas}`}
            {isPlaceholderData && ' · atualizando…'}
          </p>
        </div>

        {isError ? (
          <div className="empty-state">Não foi possível carregar a fila.</div>
        ) : !isPending && grupos.length === 0 ? (
          <div className="empty-state">
            Fila vazia.
            <div className="empty-state__hint">
              {ufIncerta ? 'Nenhum grupo incerto sobrando — tire o filtro pra ver o resto.' : 'Nada pra revisar agora.'}
            </div>
          </div>
        ) : (
          <table className="data-table data-table--cartoes">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Candidatos</th>
                <th>Confiança</th>
              </tr>
            </thead>
            <tbody>
              {grupos.map((g) => (
                <tr key={g.nome_normalizado}>
                  <td data-rotulo="Nome" data-titulo>
                    <Link to={`/administracao/captacao/fusoes/${encodeURIComponent(g.nome_normalizado)}`}>
                      {g.nome_normalizado}
                    </Link>
                  </td>
                  <td data-rotulo="Candidatos">{g.candidatos}</td>
                  <td data-rotulo="Confiança">
                    {g.ufs_distintas <= 1 ? 'Mesma UF' : `${g.ufs_distintas} UFs diferentes`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPaginas > 1 && (
          <nav
            aria-label="Paginação da fila de fusão"
            style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px' }}
          >
            <button
              type="button"
              className="btn btn--fino"
              disabled={pagina <= 1}
              onClick={() => setPagina((p) => p - 1)}
            >
              ← Anterior
            </button>
            <span className="tela-subtitulo">{`${pagina} / ${totalPaginas}`}</span>
            <button
              type="button"
              className="btn btn--fino"
              disabled={pagina >= totalPaginas}
              onClick={() => setPagina((p) => p + 1)}
            >
              Próxima →
            </button>
          </nav>
        )}
      </section>
    </div>
  );
}
