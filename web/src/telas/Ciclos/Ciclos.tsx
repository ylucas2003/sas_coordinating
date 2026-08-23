import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { TheadOrdenavel } from '../../componentes/ui/TabelaOrdenavel';
import { ordenarLinhas, proximaOrdenacao } from '../../componentes/ui/ordenacao';
import type { ColunaTabela, Ordenacao } from '../../componentes/ui/ordenacao';
import { BarraFiltros, Pills, RangeDatas } from '../../componentes/ui/filtros/BarraFiltros';
import type { GrupoFiltro } from '../../componentes/ui/filtros/BarraFiltros';
import { CriarCiclo } from '../../componentes/dialogos/CriarCiclo';
import {
  FILTRO_CICLOS_VAZIO, algumFiltroAtivo, aplicarFiltros, contarPorChip, montarOpcoes,
} from '../../dominio/ciclos';
import type { FiltroCiclos } from '../../dominio/ciclos';
import { useCiclos } from '../../hooks/consultas';
import type { Ciclo } from '../../tipos/dominio';
import { fmtDataBR } from '../../util/data';

const COLUNAS: Array<ColunaTabela<Ciclo>> = [
  { chave: 'nome', label: 'Ciclo', valor: (c) => c.nome },
  { chave: 'vestibular', label: 'Vestibular', valor: (c) => c.vestibularAlvo },
  { chave: 'periodo', label: 'Período', valor: (c) => c.periodoInicio },
  { chave: 'simulados', label: 'Simulados', valor: (c) => (c.simuladoIds ?? []).length, tipo: 'numero' },
  { chave: 'acao', label: '', ordenavel: false },
];

/** Lista de ciclos com filtros laterais (vestibular, ano letivo, período). */
export function Ciclos() {
  const navegar = useNavigate();
  const { data: ciclos = [], isPending, isError, error } = useCiclos();

  const [filtro, setFiltro] = useState<FiltroCiclos>(FILTRO_CICLOS_VAZIO);
  const [ordenacao, setOrdenacao] = useState<Ordenacao | null>(null);
  const [dialogoAberto, setDialogoAberto] = useState(false);

  const opcoes = useMemo(() => montarOpcoes(ciclos), [ciclos]);
  const filtrados = useMemo(() => aplicarFiltros(ciclos, filtro), [ciclos, filtro]);
  const contagens = useMemo(() => contarPorChip(ciclos, filtro), [ciclos, filtro]);
  const linhas = useMemo(() => ordenarLinhas(filtrados, COLUNAS, ordenacao), [filtrados, ordenacao]);

  function alternarChip<K extends 'vestibulares' | 'anos'>(grupo: K, valor: FiltroCiclos[K] extends ReadonlySet<infer V> ? V : never) {
    setFiltro((f) => {
      const novo = new Set(f[grupo] as ReadonlySet<typeof valor>);
      if (novo.has(valor)) novo.delete(valor);
      else novo.add(valor);
      return { ...f, [grupo]: novo };
    });
  }

  const grupos: Array<GrupoFiltro | null> = [
    {
      chave: 'vestibular',
      rotulo: 'Vestibular',
      corpo: (
        <Pills
          opcoes={opcoes.vestibulares.map((v) => ({ valor: v, label: v, contagem: contagens.vestibular.get(v) ?? 0 }))}
          selecionados={filtro.vestibulares}
          onToggle={(v) => alternarChip('vestibulares', v)}
        />
      ),
    },
    // Ano só aparece se houver mais de um (senão é redundante).
    opcoes.anos.length > 1
      ? {
          chave: 'ano',
          rotulo: 'Ano letivo',
          corpo: (
            <Pills
              opcoes={opcoes.anos.map((a) => ({ valor: a, label: String(a), contagem: contagens.ano.get(a) ?? 0 }))}
              selecionados={filtro.anos}
              onToggle={(v) => alternarChip('anos', v)}
            />
          ),
        }
      : null,
    {
      chave: 'periodo',
      rotulo: 'Período',
      corpo: (
        <RangeDatas
          inicio={filtro.periodo.inicio}
          fim={filtro.periodo.fim}
          onChange={(periodo) => setFiltro((f) => ({ ...f, periodo }))}
        />
      ),
    },
  ];

  return (
    <>
      <BarraFiltros
        grupos={grupos}
        algumAtivo={algumFiltroAtivo(filtro)}
        onLimpar={() => setFiltro(FILTRO_CICLOS_VAZIO)}
      />

      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">Ciclos do ano letivo</h1>
          <p className="tela-subtitulo">
            {isPending ? 'Carregando…' : `${filtrados.length} de ${ciclos.length} ciclos`}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setDialogoAberto(true)}>
          + Novo ciclo
        </button>
      </div>

      <section className="card">
        {isError ? (
          <div className="empty-state">
            Não foi possível carregar os ciclos.
            <div className="empty-state__hint">{(error as Error)?.message}</div>
          </div>
        ) : isPending ? (
          <div className="empty-state">Carregando…</div>
        ) : linhas.length === 0 ? (
          <div className="empty-state">Nenhum ciclo bate com os filtros.</div>
        ) : (
          <table className="data-table">
            <TheadOrdenavel
              colunas={COLUNAS}
              ordenacao={ordenacao}
              onOrdenar={(chave) => setOrdenacao((o) => proximaOrdenacao(o, chave))}
            />
            <tbody>
              {linhas.map((c) => (
                <tr key={c.id} onClick={() => navegar(`/ciclos/${c.id}`)}>
                  <td>{c.nome}</td>
                  <td>
                    {c.vestibularAlvo ? (
                      <span className="tag tone-navy">{c.vestibularAlvo}</span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>{`${fmtDataBR(c.periodoInicio)} → ${fmtDataBR(c.periodoFim)}`}</td>
                  <td>{(c.simuladoIds ?? []).length}</td>
                  <td>
                    <Link to={`/ciclos/${c.id}`} onClick={(ev) => ev.stopPropagation()}>
                      Ver →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {dialogoAberto && <CriarCiclo onFechar={() => setDialogoAberto(false)} />}
    </>
  );
}
