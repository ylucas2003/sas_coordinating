import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { BarraFiltros, Busca, PillsUnica } from '../../componentes/ui/filtros/BarraFiltros';
import { resumirTexto } from '../../dominio/filtros';
import { useCandidatos } from '../../hooks/captacao';
import type { FiltrosCaptacao as Filtros, StatusCaptacao } from '../../tipos/captacao';

// Captação externa (docs/41) — candidatos achados FORA do colégio, cruzando
// resultado público de olimpíada/vestibular/concurso. Não tem nada a ver com
// `aluno`: é gente que nunca colocou os pés aqui, e a lista existe pra achar
// quem convidar.
//
// **Paginação de verdade**, ao contrário de `Alunos.tsx` — e isso não é
// inconsistência, é a mesma régua do `Banco` (docs/41 §7.1, CLAUDE.md
// armadilha 2): lá o volume é fixo (~900 alunos, sem teto de propósito); aqui
// é gente de fora, sem teto natural — 26 mil e crescendo a cada fonte nova.
//
// A ordem padrão do servidor é por Nº DE CONQUISTAS, decrescente
// (`routes/captacao.py::listar_candidatos`): quem cruzou premiação em quatro
// anos seguidos é lead mais forte que quem apareceu uma vez, e é essa
// pergunta — "quem já provou que é bom?" — que a tela responde primeiro.

const STATUS_LABEL: Record<StatusCaptacao, string> = {
  novo: 'Novo',
  contatado: 'Contatado',
  interessado: 'Interessado',
  matriculado: 'Matriculado',
  descartado: 'Descartado',
};

const OPCOES_STATUS: Array<{ valor: StatusCaptacao; label: string }> = (
  Object.keys(STATUS_LABEL) as StatusCaptacao[]
).map((valor) => ({ valor, label: STATUS_LABEL[valor] }));

const OPCOES_CONQUISTAS: Array<{ valor: number; label: string }> = [
  { valor: 2, label: '2+ conquistas' },
  { valor: 3, label: '3+ conquistas' },
  { valor: 4, label: '4+ conquistas' },
];

const POR_PAGINA = 20;
const FILTROS_INICIAIS: Filtros = { pagina: 1, por_pagina: POR_PAGINA };

/** Campo vazio é campo ausente — senão `{ uf: '' }` e `{}` viram cache diferente pra mesma pergunta. */
function semVazios(filtros: Filtros): Filtros {
  const limpo: Record<string, unknown> = {};
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor !== undefined && valor !== null && valor !== '') limpo[chave] = valor;
  }
  return limpo as Filtros;
}

function fmtQuando(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function Captacao() {
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_INICIAIS);
  const [ufDigitada, setUfDigitada] = useState('');
  const { data, isPending, isError, isPlaceholderData } = useCandidatos(filtros);

  const candidatos = data?.candidatos ?? [];
  const total = data?.total ?? 0;
  const pagina = data?.pagina ?? filtros.pagina ?? 1;
  const porPagina = data?.por_pagina ?? filtros.por_pagina ?? POR_PAGINA;
  const totalPaginas = Math.max(1, Math.ceil(total / porPagina));

  /** Qualquer mudança de filtro volta pra página 1 — a página 40 do recorte antigo pode nem existir no novo. */
  const filtrar = useCallback((mudanca: Partial<Filtros>) => {
    setFiltros((atual) => semVazios({ ...atual, pagina: 1, ...mudanca }));
  }, []);

  const algumAtivo = Boolean(
    filtros.uf || filtros.status_captacao || filtros.conquistas_min || filtros.busca,
  );

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Captação externa" para="/administracao" destino="Administração" />

      <div className="tela-cabecalho">
        <p className="tela-subtitulo">
          Gente que nunca estudou aqui, achada cruzando listas públicas de premiação de olimpíada e
          vestibular. Abra a ficha pra ver todas as conquistas cruzadas de cada pessoa.
        </p>
      </div>

      <BarraFiltros
        tela="captacao"
        algumAtivo={algumAtivo}
        onLimpar={() => {
          setUfDigitada('');
          setFiltros(FILTROS_INICIAIS);
        }}
        grupos={[
          {
            chave: 'conquistas',
            rotulo: 'Conquistas',
            resumo: filtros.conquistas_min ? `${filtros.conquistas_min}+` : null,
            corpo: (
              <PillsUnica
                opcoes={OPCOES_CONQUISTAS}
                selecionado={filtros.conquistas_min ?? null}
                onSelecionar={(v) =>
                  filtrar({ conquistas_min: filtros.conquistas_min === v ? undefined : v })}
              />
            ),
          },
          {
            chave: 'status',
            rotulo: 'Status',
            resumo: filtros.status_captacao ? STATUS_LABEL[filtros.status_captacao] : null,
            corpo: (
              <PillsUnica
                opcoes={OPCOES_STATUS}
                selecionado={filtros.status_captacao ?? null}
                onSelecionar={(v) =>
                  filtrar({ status_captacao: filtros.status_captacao === v ? undefined : v })}
              />
            ),
          },
          {
            chave: 'uf',
            rotulo: 'UF',
            resumo: filtros.uf ?? null,
            corpo: (
              <input
                className="pill-campo"
                style={{ width: 64, textTransform: 'uppercase' }}
                value={ufDigitada}
                maxLength={2}
                placeholder="ex.: CE"
                aria-label="Filtrar por UF"
                onChange={(e) => setUfDigitada(e.target.value.toUpperCase())}
                onBlur={() => filtrar({ uf: ufDigitada || undefined })}
                onKeyDown={(e) => e.key === 'Enter' && filtrar({ uf: ufDigitada || undefined })}
              />
            ),
          },
          {
            chave: 'busca',
            rotulo: 'Nome',
            resumo: resumirTexto(filtros.busca ?? ''),
            corpo: (
              <Busca
                valor={filtros.busca ?? ''}
                onChange={(v) => filtrar({ busca: v || undefined })}
                placeholder="Nome do candidato…"
                rotulo="Buscar candidato por nome"
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
              : `${total.toLocaleString('pt-BR')} ${total === 1 ? 'candidato' : 'candidatos'} · página ${pagina} de ${totalPaginas}`}
            {isPlaceholderData && ' · atualizando…'}
          </p>
        </div>

        {isError ? (
          <div className="empty-state">Não foi possível carregar os candidatos.</div>
        ) : !isPending && candidatos.length === 0 ? (
          <div className="empty-state">
            Nenhum candidato com esses filtros.
            <div className="empty-state__hint">Tire um filtro ou limpe a busca.</div>
          </div>
        ) : (
          <table className="data-table data-table--cartoes">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Escola</th>
                <th>Cidade/UF</th>
                <th>Conquistas</th>
                <th>Status</th>
                <th>Última atualização</th>
              </tr>
            </thead>
            <tbody>
              {candidatos.map((c) => (
                <tr key={c.id}>
                  <td data-rotulo="Nome" data-titulo>
                    <Link to={`/administracao/captacao/${c.id}`}>{c.nome}</Link>
                  </td>
                  <td data-rotulo="Escola">{c.escola || '—'}</td>
                  <td data-rotulo="Cidade/UF">
                    {[c.cidade, c.uf].filter(Boolean).join(' · ') || '—'}
                  </td>
                  <td data-rotulo="Conquistas">
                    {c.conquistas_total}
                    {c.ano_mais_recente && ` · até ${c.ano_mais_recente}`}
                  </td>
                  <td data-rotulo="Status">{STATUS_LABEL[c.status_captacao]}</td>
                  <td data-rotulo="Última atualização" data-secundario>{fmtQuando(c.atualizado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPaginas > 1 && (
          <nav
            aria-label="Paginação dos candidatos"
            style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px' }}
          >
            <button
              type="button"
              className="btn btn--fino"
              disabled={pagina <= 1}
              onClick={() => setFiltros((f) => ({ ...f, pagina: pagina - 1 }))}
            >
              ← Anterior
            </button>
            <span className="tela-subtitulo">{`${pagina} / ${totalPaginas}`}</span>
            <button
              type="button"
              className="btn btn--fino"
              disabled={pagina >= totalPaginas}
              onClick={() => setFiltros((f) => ({ ...f, pagina: pagina + 1 }))}
            >
              Próxima →
            </button>
          </nav>
        )}
      </section>
    </div>
  );
}
