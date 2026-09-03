import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { GraficoEmCamadas } from '../../componentes/ui/GraficoEmCamadas';
import { Histograma } from '../../componentes/ui/Histograma';
import { corteDaMateria, eliminaSozinho } from '../../dominio/criterios';
import { lerDistribuicao } from '../../dominio/leituraDeGrafico';
import { Kpi } from '../../componentes/ui/Kpi';
import { EdicaoNota } from '../../componentes/dialogos/EdicaoNota';
import type { ValoresNota } from '../../componentes/dialogos/formularioNota';
import { EdicaoSimulado } from '../../componentes/dialogos/EdicaoSimulado';
import { SeloCanvas } from '../../componentes/ui/SeloCanvas';
import type { PatchSimulado } from '../../componentes/dialogos/EdicaoSimulado';
import {
  useCriteriosDisponiveis, useHistogramaSimulado, useNotasSimulado, useSimulado,
  useSimuladoPorMateria, useSimuladoPorSede,
} from '../../hooks/consultas';
import { useCancelarSimulado, useEditarNota, useEditarSimulado, useRetrySimuladoCanvas } from '../../hooks/mutacoes';
import { DialogoComDiff } from '../../componentes/dialogos/DialogoComDiff';
import type { NotaSimulado, QuebraSimulado, Simulado } from '../../tipos/dominio';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
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
  const enviarCanvas = useRetrySimuladoCanvas();
  const cancelar = useCancelarSimulado();
  const navegar = useNavigate();
  const [desmarcando, setDesmarcando] = useState(false);
  const editarNota = useEditarNota();

  // A régua da casa: esta ficha não escolhe critério, e o corte da matéria do
  // simulado é o que o gráfico precisa desenhar.
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const regua = criterios.find((c) => c.slug === 'tio-leo') ?? criterios[0] ?? null;
  const corte = corteDaMateria(regua, simulado?.materia?.codigo);
  const elimina = eliminaSozinho(regua, simulado?.materia?.codigo);

  const [editandoSimulado, setEditandoSimulado] = useState(false);
  const [notaEmEdicao, setNotaEmEdicao] = useState<NotaSimulado | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');

  // Antes de qualquer return: hook não pode ficar atrás de saída antecipada.
  useTituloDaTela(simulado?.nome);

  if (isPending) {
    return (
      <div className="tela">
        <section className="card">
          <div className="empty-state">Carregando…</div>
        </section>
      </div>
    );
  }

  if (isError || !simulado) {
    return (
      <div className="tela">
        <section className="card">
          <div className="empty-state">
            {`Simulado ${id} não encontrado.`}
            <div className="empty-state__hint">
              <Link to="/provas?aba=simulados">← Voltar para a lista</Link>
            </div>
          </div>
        </section>
      </div>
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

  async function salvarNota(valores: ValoresNota | null) {
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
    <div className="tela">
      <section className="card">
        <div className="screen-header">
          <div className="screen-breadcrumb">{simulado.id}</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <h1 className="screen-title" style={{ margin: 0 }}>
              {simulado.nome}
              {simulado.origem === 'sas' && (
                <span style={{ marginLeft: 10, verticalAlign: 'middle' }}>
                  <SeloCanvas estado={simulado.canvasEstado} erro={simulado.canvasErro} />
                </span>
              )}
            </h1>
            {simulado.anulado && <span className="tag tone-anulado">Anulado</span>}
            {!simulado.notaConfiavel && (
              <span className="tag tone-ambar">Fora das estatísticas</span>
            )}
          </div>

          {/* A ressalva inteira, e não só a etiqueta: quem abre esta prova
              precisa saber que a média mostrada em outros lugares NÃO a
              inclui, e por quê. Esconder a prova seria pior — o aluno de 2023
              não perde o histórico dele (docs/32 §1.5, item 6). */}
          {!simulado.notaConfiavel && (
            <p className="tela-subtitulo" style={{ marginTop: 8 }}>
              <b>Esta prova não entra nas médias, nos histogramas nem nos alertas.</b>{' '}
              {simulado.motivoNotaNaoConfiavel
                || 'As notas dela não representam desempenho.'}{' '}
              As notas individuais continuam abaixo, e continuam no histórico de cada aluno.
            </p>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
            <p className="screen-subtitle" style={{ margin: 0 }}>
              {`${FASE_PREFIXO[simulado.tipo ?? ''] ?? ''}aplicado em ${simulado.dataAplicacao} · ${simulado.nPresentes ?? '—'} presentes`}
            </p>
            <button className="btn-editar-sim" onClick={() => setEditandoSimulado(true)}>
              ✏ Editar simulado
            </button>
            {/* O único caminho que tira um simulado de 'divergente' — o retry
                automático nunca faz isso (docs/18 §2.5). Vale também para
                'falhou', como "tentar de novo". */}
            {simulado.origem === 'sas' && (simulado.canvasEstado === 'divergente' || simulado.canvasEstado === 'falhou') && (
              <button
                className="btn-editar-sim"
                disabled={enviarCanvas.isPending}
                onClick={async () => {
                  setErroSalvar('');
                  try {
                    await enviarCanvas.mutateAsync(simulado.id);
                  } catch (e) {
                    setErroSalvar((e as Error).message || 'Falha ao enviar ao Canvas.');
                  }
                }}
              >
                {enviarCanvas.isPending ? 'Enviando…' : simulado.canvasEstado === 'divergente' ? '↑ Enviar ao Canvas' : '↻ Tentar de novo no Canvas'}
              </button>
            )}
            {/* Só simulado do SAS sem nota se desmarca; com nota, anula (a API
                devolve 409). Mesmo diálogo da lista de Agendados. */}
            {simulado.origem === 'sas' && !simulado.nPresentes && (
              <button className="btn-editar-sim" onClick={() => setDesmarcando(true)}>
                ✕ Desmarcar
              </button>
            )}
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
          <GraficoEmCamadas
            titulo="Distribuição"
            legenda="Histograma de notas com bins de 0,5 ponto. Linhas tracejadas: média (vermelho) e mediana (âmbar)."
            frase={lerDistribuicao({
              histograma: hist,
              media: hist?.media ?? simulado.media,
              corte,
              rotuloGrupo: 'de quem fez',
            })?.frase ?? null}
            grafico={(camada) => (
              <Histograma
                payload={hist}
                media={hist?.media ?? simulado.media}
                mediana={hist?.mediana ?? simulado.mediana}
                // Esta ficha desenhava a distribuição SEM linha de corte
                // nenhuma — o número existia na régua e não chegava aqui.
                corte={corte != null ? { valor: corte, eliminatoria: elimina } : null}
                kde={camada === 'estatistica'}
                eixoYAbsoluto={camada === 'estatistica' ? {} : null}
              />
            )}
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

      {desmarcando && (
        <DialogoComDiff
          titulo="Desmarcar simulado"
          subtitulo={simulado.nome}
          mudancas={[{ campo: 'Simulado', de: 'agendado', para: 'desmarcado' }]}
          canvas={
            simulado.canvasEstado === 'sincronizado'
              ? { efeito: 'apaga o Assignment no Canvas, com as submissions dos alunos.', irreversivel: true }
              : undefined
          }
          onCancelar={() => setDesmarcando(false)}
          onVoltar={() => setDesmarcando(false)}
          onSalvar={() => undefined}
          onConfirmar={async (sincronizarCanvas) => {
            setDesmarcando(false);
            setErroSalvar('');
            try {
              await cancelar.mutateAsync({ id: simulado.id, sincronizarCanvas });
              navegar('/simulados');
            } catch (e) {
              setErroSalvar((e as Error).message || 'Falha ao desmarcar.');
            }
          }}
        >
          {null}
        </DialogoComDiff>
      )}

      {editandoSimulado && (
        <EdicaoSimulado
          nome={simulado.nome}
          rotuloAtual={simulado.rotuloCurto}
          notaMaximaAtual={simulado.notaMaxima}
          anuladoAtual={simulado.anulado}
          origemSas={simulado.origem === 'sas'}
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
    </div>
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
