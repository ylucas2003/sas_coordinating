import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Histograma } from '../../componentes/ui/Histograma';
import { Kpi } from '../../componentes/ui/Kpi';
import { EdicaoNota } from '../../componentes/dialogos/EdicaoNota';
import { EdicaoSimulado } from '../../componentes/dialogos/EdicaoSimulado';
import type { PatchSimulado } from '../../componentes/dialogos/EdicaoSimulado';
import {
  useHistogramaSimulado, useNotasSimulado, useSimulado,
  useSimuladoPorMateria, useSimuladoPorSede,
} from '../../hooks/consultas';
import { useEditarNota, useEditarSimulado } from '../../hooks/mutacoes';
import type { NotaSimulado, QuebraSimulado, Simulado } from '../../tipos/dominio';
import { fmtNota } from '../../util/formato';

const FASE_PREFIXO: Record<string, string> = { fase_1: 'Fase 1 · ', fase_2: 'Fase 2 · ' };

/** Ficha de simulado: métricas, distribuição, quebras e notas individuais. */
export function SimuladoFicha() {
  const { id = '' } = useParams();

  const { data: simulado, isPending, isError } = useSimulado(id);
  const { data: hist } = useHistogramaSimulado(id);
  const { data: porMateria = [] } = useSimuladoPorMateria(id);
  const { data: porSede = [] } = useSimuladoPorSede(id);
  const { data: notas = [] } = useNotasSimulado(id);

  const editarSimulado = useEditarSimulado();
  const editarNota = useEditarNota();

  const [editandoSimulado, setEditandoSimulado] = useState(false);
  const [notaEmEdicao, setNotaEmEdicao] = useState<NotaSimulado | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');

  if (isPending) {
    return (
      <main className="app-main">
        <section className="card">
          <div className="empty-state">Carregando…</div>
        </section>
      </main>
    );
  }

  if (isError || !simulado) {
    return (
      <main className="app-main">
        <section className="card">
          <div className="empty-state">
            {`Simulado ${id} não encontrado.`}
            <div className="empty-state__hint">
              <Link to="/simulados">← Voltar para a lista</Link>
            </div>
          </div>
        </section>
      </main>
    );
  }

  async function salvarSimulado(patch: PatchSimulado | null) {
    setEditandoSimulado(false);
    if (!patch) return;
    try {
      await editarSimulado.mutateAsync({ id, corpo: patch });
    } catch (e) {
      setErroSalvar(`Erro ao salvar: ${(e as Error).message}`);
    }
  }

  async function salvarNota(valores: { pontuacao: number | null; presente: boolean } | null) {
    const linha = notaEmEdicao;
    setNotaEmEdicao(null);
    if (!valores || !linha?.alunoId) return;
    try {
      await editarNota.mutateAsync({ alunoId: linha.alunoId, simuladoId: id, corpo: valores });
    } catch (e) {
      setErroSalvar(`Erro ao salvar: ${(e as Error).message}`);
    }
  }

  return (
    <main className="app-main">
      <section className="card">
        <div className="screen-header">
          <div className="screen-breadcrumb">
            <Link to="/simulados">Simulados</Link>
            {' / '}
            {simulado.id}
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <h1 className="screen-title" style={{ margin: 0 }}>{simulado.nome}</h1>
            {simulado.anulado && <span className="tag tone-anulado">Anulado</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
            <p className="screen-subtitle" style={{ margin: 0 }}>
              {`${FASE_PREFIXO[simulado.tipo ?? ''] ?? ''}aplicado em ${simulado.dataAplicacao} · ${simulado.nPresentes ?? '—'} presentes`}
            </p>
            <button className="btn-editar-sim" onClick={() => setEditandoSimulado(true)}>
              ✏ Editar simulado
            </button>
          </div>
        </div>

        {erroSalvar && <div className="agendar__erro">{erroSalvar}</div>}

        <div className="section">
          <div className="section__title">Métricas</div>
          <div className="kpi-grid">
            <Kpi rotulo="Média" valor={fmtNota(simulado.media)} />
            <Kpi rotulo="Mediana" valor={fmtNota(simulado.mediana)} />
            <Kpi rotulo="Desvio padrão" valor={fmtNota(simulado.desvioPadrao)} />
            <Kpi rotulo="Presentes" valor={String(simulado.nPresentes ?? '—')} />
            <Kpi rotulo="Ausentes" valor={String(hist?.nAusentes ?? '—')} />
          </div>
        </div>

        <div className="section">
          <div className="section__title">Distribuição</div>
          <p className="section__subtitle">
            Histograma de notas com bins de 0,5 ponto. Linhas tracejadas: média (vermelho) e
            mediana (âmbar).
          </p>
          <Histograma
            payload={hist}
            media={hist?.media ?? simulado.media}
            mediana={hist?.mediana ?? simulado.mediana}
          />
        </div>

        <QuebraPorMateria linhas={porMateria} />
        <QuebraPorSede linhas={porSede} />

        <div className="section">
          <div className="section__title">{`Notas individuais (${notas.length})`}</div>
          {notas.length === 0 ? (
            <p className="section__subtitle">Sem notas registradas ainda.</p>
          ) : (
            <TabelaNotas notas={notas} onEditar={setNotaEmEdicao} />
          )}
        </div>
      </section>

      {editandoSimulado && (
        <EdicaoSimulado
          nome={simulado.nome}
          rotuloAtual={simulado.rotuloCurto}
          notaMaximaAtual={simulado.notaMaxima}
          anuladoAtual={simulado.anulado}
          onFechar={salvarSimulado}
        />
      )}

      {notaEmEdicao && (
        <EdicaoNota
          nomeAluno={notaEmEdicao.nome}
          nomeSimulado={simulado.rotuloCurto || simulado.nome}
          pontuacaoAtual={pontuacaoBruta(notaEmEdicao, simulado)}
          presenteAtual={notaEmEdicao.presente}
          notaMaxima={simulado.notaMaxima}
          onFechar={salvarNota}
        />
      )}
    </main>
  );
}

/**
 * A linha traz a nota já em escala 0-10 (é o que GET /simulados/{id}/notas
 * devolve), mas o backend espera a pontuação bruta na edição — daí a volta.
 */
function pontuacaoBruta(nota: NotaSimulado, simulado: Simulado): number | null {
  if (!nota.presente || nota.pontuacao == null || !simulado.notaMaxima) return null;
  return Math.round((nota.pontuacao / 10) * simulado.notaMaxima * 100) / 100;
}

function TabelaNotas({
  notas, onEditar,
}: {
  notas: NotaSimulado[];
  onEditar: (n: NotaSimulado) => void;
}) {
  const navegar = useNavigate();
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Aluno</th>
          <th>Pontuação</th>
          <th />
          <th />
        </tr>
      </thead>
      <tbody>
        {notas.map((n, i) => (
          <tr key={n.alunoId ?? i} onClick={() => n.alunoId && navegar(`/alunos/${n.alunoId}`)}>
            <td>{n.nome}</td>
            <td>
              {n.presente ? fmtNota(n.pontuacao) : <span className="tag tone-ambar">Ausente</span>}
            </td>
            <td>
              {n.alunoId && (
                <Link to={`/alunos/${n.alunoId}`} onClick={(ev) => ev.stopPropagation()}>
                  Ver →
                </Link>
              )}
            </td>
            <td onClick={(ev) => ev.stopPropagation()}>
              <button className="btn-editar" onClick={() => onEditar(n)}>Editar</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function QuebraPorMateria({ linhas }: { linhas: QuebraSimulado[] }) {
  const navegar = useNavigate();
  return (
    <div className="section">
      <div className="section__title">Por matéria</div>
      {linhas.length === 0 ? (
        <p className="section__subtitle">Simulado sem irmãos por matéria no mesmo dia.</p>
      ) : (
        <table className="data-table">
          <TheadQuebra primeira="Matéria" />
          <tbody>
            {linhas.map((m, i) => (
              <tr key={m.simuladoId ?? i} onClick={() => m.simuladoId && navegar(`/simulados/${m.simuladoId}`)}>
                <td>{m.materia}</td>
                <CelulasQuebra linha={m} />
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function QuebraPorSede({ linhas }: { linhas: QuebraSimulado[] }) {
  return (
    <div className="section">
      <div className="section__title">Por sede</div>
      {linhas.length === 0 ? (
        <p className="section__subtitle">Métricas por sede ainda não calculadas.</p>
      ) : (
        <table className="data-table">
          <TheadQuebra primeira="Sede" />
          <tbody>
            {linhas.map((s, i) => (
              <tr key={s.sede ?? i}>
                <td>{s.sede}</td>
                <CelulasQuebra linha={s} />
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TheadQuebra({ primeira }: { primeira: string }) {
  return (
    <thead>
      <tr>
        <th>{primeira}</th>
        <th>Média</th>
        <th>Mediana</th>
        <th>Desvio</th>
        <th>Presentes</th>
      </tr>
    </thead>
  );
}

function CelulasQuebra({ linha }: { linha: QuebraSimulado }) {
  return (
    <>
      <td>{fmtNota(linha.media)}</td>
      <td>{fmtNota(linha.mediana)}</td>
      <td>{fmtNota(linha.desvioPadrao)}</td>
      <td>{String(linha.nPresentes ?? '—')}</td>
    </>
  );
}
