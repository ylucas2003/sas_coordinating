import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Sidebar } from '../../componentes/layout/Sidebar';
import { CalendarioAnual } from '../../componentes/ui/CalendarioAnual';
import { CorpoChips, PainelFiltros } from '../../componentes/ui/filtros/PainelFiltros';
import type { SecaoFiltro } from '../../componentes/ui/filtros/PainelFiltros';
import { proximaOrdenacao } from '../../componentes/ui/ordenacao';
import type { Ordenacao } from '../../componentes/ui/ordenacao';
import { TabelaSimulados } from '../../componentes/simulados/TabelaSimulados';
import { AgendarSimulado } from '../../componentes/dialogos/AgendarSimulado';
import {
  FILTRO_VAZIO, algumFiltroAtivo, aplicarFiltros, contarPorChip, datasDoCalendario,
  montarOpcoes, rotuloCiclo,
} from '../../dominio/simulados';
import type { FiltroSimulados } from '../../dominio/simulados';
import { useCiclos, useSimulados } from '../../hooks/consultas';
import { useCancelarSimulado, useRetrySimuladoCanvas } from '../../hooks/mutacoes';
import type { Simulado } from '../../tipos/dominio';
import { fmtDataBR, hojeISO } from '../../util/data';

const TIPO_LABEL: Record<string, string> = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

/** Lista de simulados com filtros laterais e calendário anual. */
export function Simulados() {
  const { data: todos = [], isPending, isError, error } = useSimulados();
  const { data: ciclos = [] } = useCiclos();

  const [filtro, setFiltro] = useState<FiltroSimulados>(FILTRO_VAZIO);
  const [ordenacao, setOrdenacao] = useState<Ordenacao | null>(null);
  const [abertas, setAbertas] = useState<ReadonlySet<string>>(
    new Set(['vestibular', 'fase', 'ciclo', 'disciplina']),
  );
  // Calendário começa oculto: o usuário decide quando mostrar.
  const [calendarioVisivel, setCalendarioVisivel] = useState(false);
  const [dialogoAberto, setDialogoAberto] = useState(false);

  // Split agendado/aplicado: prova futura não tem métrica e vive na seção
  // própria — misturá-la na tabela principal pareceria defeito (docs/11 §6).
  const { agendados, simulados } = useMemo(() => {
    const hoje = hojeISO();
    return {
      agendados: todos.filter((s) => s.dataAplicacao > hoje),
      simulados: todos.filter((s) => s.dataAplicacao <= hoje),
    };
  }, [todos]);

  const opcoes = useMemo(() => montarOpcoes(simulados), [simulados]);
  const filtrados = useMemo(() => aplicarFiltros(simulados, filtro), [simulados, filtro]);
  const contagens = useMemo(() => contarPorChip(simulados, filtro), [simulados, filtro]);
  const datasCalendario = useMemo(() => datasDoCalendario(simulados, filtro), [simulados, filtro]);

  function alternar<K extends keyof FiltroSimulados>(
    grupo: K,
    valor: FiltroSimulados[K] extends ReadonlySet<infer V> ? V : never,
  ) {
    setFiltro((f) => {
      const novo = new Set(f[grupo] as ReadonlySet<typeof valor>);
      if (novo.has(valor)) novo.delete(valor);
      else novo.add(valor);
      return { ...f, [grupo]: novo };
    });
  }

  const secoes: SecaoFiltro[] = [
    {
      chave: 'vestibular', rotulo: 'Vestibular', icone: 'vestibular',
      corpo: (
        <CorpoChips
          opcoes={opcoes.vestibulares.map((v) => ({ valor: v, label: v, contagem: contagens.vestibular.get(v) ?? 0 }))}
          selecionados={filtro.vestibulares}
          onToggle={(v) => alternar('vestibulares', v)}
        />
      ),
    },
    {
      chave: 'fase', rotulo: 'Fase', icone: 'fase',
      corpo: (
        <CorpoChips
          opcoes={opcoes.fases.map((f) => ({ valor: f.valor, label: f.label, contagem: contagens.fase.get(f.valor) ?? 0 }))}
          selecionados={filtro.fases}
          onToggle={(v) => alternar('fases', v)}
        />
      ),
    },
    {
      chave: 'ciclo', rotulo: 'Ciclo', icone: 'ciclos',
      corpo: (
        <CorpoChips
          opcoes={opcoes.ciclos.map((c) => ({ valor: c.ordem, label: c.label, contagem: contagens.ciclo.get(c.ordem) ?? 0 }))}
          selecionados={filtro.ciclos}
          onToggle={(v) => alternar('ciclos', v)}
        />
      ),
    },
    {
      chave: 'disciplina', rotulo: 'Disciplina', icone: 'disciplina',
      corpo: (
        <CorpoChips
          opcoes={opcoes.materias.map((m) => ({ valor: m.codigo, label: m.nome, contagem: contagens.materia.get(m.codigo) ?? 0 }))}
          selecionados={filtro.materias}
          onToggle={(v) => alternar('materias', v)}
        />
      ),
    },
  ];

  return (
    <>
      <Sidebar rotulo="Filtros">
        <PainelFiltros
          secoes={secoes}
          abertas={abertas}
          onToggleSecao={(chave) =>
            setAbertas((a) => {
              const novo = new Set(a);
              if (novo.has(chave)) novo.delete(chave);
              else novo.add(chave);
              return novo;
            })
          }
          algumAtivo={algumFiltroAtivo(filtro)}
          onLimpar={() => setFiltro(FILTRO_VAZIO)}
        />
      </Sidebar>

      <main className="app-main">
        <div className="screen-stack">
          <section className="card">
            <div className="screen-header agendar__header">
              <div>
                <div className="screen-breadcrumb">Simulados</div>
                <h1 className="screen-title">Simulados aplicados</h1>
                <p className="screen-subtitle">
                  {isPending ? 'Carregando…' : `${filtrados.length} de ${simulados.length} simulados`}
                </p>
              </div>
              <button
                className="btn btn--primary agendar__botao-novo"
                onClick={() => setDialogoAberto(true)}
              >
                + Novo simulado
              </button>
            </div>

            <div>
              <button
                className={`sim-calendario-toggle${calendarioVisivel ? ' is-aberto' : ''}`}
                onClick={() => setCalendarioVisivel((v) => !v)}
              >
                <span className="sim-calendario-toggle__seta">{calendarioVisivel ? '▾' : '▸'}</span>
                {calendarioVisivel
                  ? 'Ocultar calendário'
                  : `Mostrar calendário · ${datasCalendario.size} dia(s)`}
              </button>
              {calendarioVisivel && (
                <CalendarioAnual
                  datasComSimulado={datasCalendario}
                  datasSelecionadas={filtro.datas}
                  onToggleData={(iso) => alternar('datas', iso)}
                />
              )}
            </div>
          </section>

          {agendados.length > 0 && <SecaoAgendados agendados={agendados} />}

          <section className="card">
            <div className="section">
              {isError ? (
                <div className="empty-state">
                  Não foi possível carregar os simulados.
                  <div className="empty-state__hint">{(error as Error)?.message}</div>
                </div>
              ) : isPending ? (
                <div className="empty-state">Carregando…</div>
              ) : (
                <TabelaSimulados
                  simulados={filtrados}
                  ordenacao={ordenacao}
                  onOrdenar={(chave) => setOrdenacao((o) => proximaOrdenacao(o, chave))}
                />
              )}
            </div>
          </section>
        </div>
      </main>

      {dialogoAberto && (
        <AgendarSimulado ciclos={ciclos} onFechar={() => setDialogoAberto(false)} />
      )}
    </>
  );
}

/**
 * Provas com data futura ficam FORA da tabela principal: não têm métricas, e
 * misturá-las pareceria defeito. Tabela própria, enxuta, com o estado do
 * Canvas e a ação de desmarcar.
 */
function SecaoAgendados({ agendados }: { agendados: readonly Simulado[] }) {
  const navegar = useNavigate();
  const cancelar = useCancelarSimulado();
  const retry = useRetrySimuladoCanvas();
  const [erro, setErro] = useState('');

  async function aoCancelar(s: Simulado) {
    if (!window.confirm(`Desmarcar ${s.nome}? O Assignment será apagado do Canvas.`)) return;
    try {
      await cancelar.mutateAsync(s.id);
    } catch (e) {
      setErro((e as Error).message || 'Falha ao desmarcar.');
    }
  }

  async function aoRetry(s: Simulado) {
    try {
      await retry.mutateAsync(s.id);
    } catch (e) {
      setErro((e as Error).message || 'Falha no retry.');
    }
  }

  return (
    <section className="card">
      <div className="screen-header">
        <h2 className="screen-title agendar__titulo-secao">{`Agendados (${agendados.length})`}</h2>
      </div>

      {erro && <div className="agendar__erro">{erro}</div>}

      <table className="data-table sim-tabela">
        <thead>
          <tr>
            {['Pn', 'Matéria', 'Fase', 'Ciclo', 'Data', 'Questões', 'Canvas', ''].map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {agendados.map((s) => {
            const emLimbo = s.canvasEstado !== 'sincronizado';
            return (
              <tr key={s.id} onClick={() => navegar(`/simulados/${s.id}`)}>
                <td className="sim-tabela__pn">{s.rotuloCurto || '—'}</td>
                <td>{s.materia?.nome || '—'}</td>
                <td>{TIPO_LABEL[s.tipo ?? ''] || '—'}</td>
                <td>{rotuloCiclo(s.cicloOrdem, s.vestibularAlvo)}</td>
                <td className="sim-tabela__data">{fmtDataBR(s.dataAplicacao)}</td>
                <td>{String(s.notaMaxima || '—')}</td>
                <td>
                  {emLimbo ? (
                    <span className="sim-selo-canvas" title={s.canvasErro || ''}>
                      não está no Canvas
                    </span>
                  ) : (
                    <span className="sim-selo-ok">no Canvas</span>
                  )}
                </td>
                <td onClick={(ev) => ev.stopPropagation()}>
                  {emLimbo && s.origem === 'sas' && (
                    <button className="btn-editar" onClick={() => aoRetry(s)}>
                      Tentar de novo
                    </button>
                  )}
                  {s.origem === 'sas' && (
                    <button className="btn-editar" onClick={() => aoCancelar(s)}>
                      Desmarcar
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
