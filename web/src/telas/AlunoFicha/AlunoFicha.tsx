import { useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Avatar } from '../../componentes/ui/Avatar';
import { GraficoEmCamadas } from '../../componentes/ui/GraficoEmCamadas';
import { Heatmap } from '../../componentes/ui/Heatmap';
import { BarraCorte } from '../Aluno/pecas/BarraCorte';
import { corteDaMateria, eliminaSozinho } from '../../dominio/criterios';
import { Kpi } from '../../componentes/ui/Kpi';
import { LinhaEvolucao } from '../../componentes/ui/LinhaEvolucao';
import { SimFiltros } from '../../componentes/simulados/SimFiltros';
import { TabelaSimulados } from '../../componentes/simulados/TabelaSimulados';
import { EdicaoNota } from '../../componentes/dialogos/EdicaoNota';
import type { ValoresNota } from '../../componentes/dialogos/formularioNota';
import { AcessoDoAluno } from './AcessoDoAluno';
import { MenuExportar } from './MenuExportar';
import {
  FILTRO_VAZIO, aplicarFiltros, contarPorChip, montarOpcoes, rotuloCiclo,
} from '../../dominio/simulados';
import type { FiltroSimulados } from '../../dominio/simulados';
import { decidirCorte, montarEixoCiclos, montarSeries } from '../../dominio/evolucaoAluno';
import { lerSeries } from '../../dominio/leituraDeGrafico';
import {
  useAluno, useAlunosSimilares, useCriteriosDisponiveis, useHeatmapAluno, useMaterias, useSedes,
  useSimulados, useTrajetoriaAluno, useTurmas,
} from '../../hooks/consultas';
import { useEditarNota } from '../../hooks/mutacoes';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import type { AlunoSimilar, Simulado } from '../../tipos/dominio';
import { fmtNota } from '../../util/formato';

import {
  exportarCSVHistorico, exportarPDFFicha, exportarPNGGrafico,
  exportarPanoramaPDF, exportarPanoramaPNG,
} from '../../exportacao/exportar-aluno.js';

const PERFIL_LABEL: Record<string, string> = { ancora: 'Âncora', misterio: 'Mistério', regular: 'Regular' };
const TENDENCIA_LABEL: Record<string, string> = { subindo: '↑ Subindo', estavel: '→ Estável', caindo: '↓ Caindo' };
const ZONA_LABEL: Record<string, string> = { top: 'Zona Top', cinzenta: 'Zona Cinzenta', risco: 'Zona de Risco' };
const ZONA_TONE: Record<string, string> = { top: 'tone-verde', cinzenta: 'tone-ambar', risco: 'tone-vermelho' };
const TENDENCIA_TONE: Record<string, string> = { subindo: 'tone-verde', estavel: 'tone-navy', caindo: 'tone-vermelho' };

/** Ficha individual do aluno: classificações, evolução, histórico, heatmap e similares. */
export function AlunoFicha() {
  const { id = '' } = useParams();

  const { data: aluno, isPending, isError } = useAluno(id);
  const { data: turmas = [] } = useTurmas();
  const { data: sedes = [] } = useSedes();
  const { data: materias = [] } = useMaterias();
  const { data: trajetoria = [] } = useTrajetoriaAluno(id);
  const { data: heat } = useHeatmapAluno(id);
  const { data: similares = [] } = useAlunosSimilares(id);
  const { data: todosSimulados = [] } = useSimulados();

  const editarNota = useEditarNota();

  const [filtro, setFiltro] = useState<FiltroSimulados>(FILTRO_VAZIO);
  const [emEdicao, setEmEdicao] = useState<{ simulado: Simulado; nota: number | null } | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');

  // O exportador de PNG precisa do SVG vivo do gráfico, não de uma re-render.
  const refGrafico = useRef<HTMLDivElement>(null);

  const notasPorSimulado = useMemo(() => {
    const m = new Map<string, number>();
    for (const n of trajetoria) {
      if (n.simuladoId != null && n.pontuacao != null) m.set(n.simuladoId, n.pontuacao);
    }
    return m;
  }, [trajetoria]);

  const simuladosDoAluno = useMemo(
    () => todosSimulados.filter((s) => notasPorSimulado.has(s.id)),
    [todosSimulados, notasPorSimulado],
  );

  const opcoes = useMemo(() => montarOpcoes(simuladosDoAluno), [simuladosDoAluno]);
  const filtrados = useMemo(() => aplicarFiltros(simuladosDoAluno, filtro), [simuladosDoAluno, filtro]);
  const contagens = useMemo(() => contarPorChip(simuladosDoAluno, filtro), [simuladosDoAluno, filtro]);

  const series = useMemo(
    () => montarSeries(filtrados, notasPorSimulado, filtro),
    [filtrados, notasPorSimulado, filtro],
  );
  const ciclosEixo = useMemo(() => montarEixoCiclos(filtrados, rotuloCiclo), [filtrados]);
  // A régua é a da casa: esta ficha não tem seletor próprio, e o gráfico de
  // evolução mistura ciclos de ITA e de IME — escolher um edital aqui seria
  // desenhar o corte errado em metade dos pontos.
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const corte = decidirCorte(filtro, criterios.find((c) => c.slug === 'tio-leo') ?? criterios[0]);

  // A BARRA DE CORTE do aluno, reusada literalmente (brief §4): as mesmas
  // matérias contra a mesma linha de ouro que o próprio aluno vê de si. É onde
  // a coerência entre os dois produtos fica evidente.
  //
  // ⚠️ O heatmap traz matéria por NOME e a régua guarda o corte por CÓDIGO, e
  // é o mapa abaixo que evita o erro caro: sem ele, `corteDaMateria` cairia no
  // corte genérico e o Inglês eliminatório da F1 do ITA — o único com 5,0 —
  // seria lido contra 4,0, mentindo justamente sobre a matéria que mais
  // elimina (R2).
  const codigoPorNome = useMemo(
    () => new Map(materias.map((m) => [m.nome, m.codigo])),
    [materias],
  );
  const reguaAtiva = criterios.find((c) => c.slug === 'tio-leo') ?? criterios[0] ?? null;
  const materiasContraCorte = useMemo(() => {
    if (!heat?.materias?.length) return [];
    // A prova mais recente de cada matéria: o corte compara a situação ATUAL,
    // não a média de tudo que já foi feito.
    const ordem = new Map(heat.simulados.map((sim, i) => [sim.id, i]));
    const ultima = new Map<string, { nota: number; pos: number }>();
    for (const c of heat.celulas) {
      if (c.pontuacao == null) continue;
      const pos = ordem.get(c.simuladoId) ?? -1;
      const atual = ultima.get(c.materia);
      if (!atual || pos > atual.pos) ultima.set(c.materia, { nota: c.pontuacao, pos });
    }
    return heat.materias.flatMap((nome) => {
      const achado = ultima.get(nome);
      if (!achado) return [];
      const codigo = codigoPorNome.get(nome) ?? nome;
      const corteDela = corteDaMateria(reguaAtiva, codigo);
      if (corteDela == null) return [];
      return [{
        materia: nome,
        nota: achado.nota,
        corte: corteDela,
        eliminatoria: eliminaSozinho(reguaAtiva, codigo),
      }];
    });
  }, [heat, codigoPorNome, reguaAtiva]);

  const turma = turmas.find((t) => t.id === aluno?.turmaId);
  const sede = sedes.find((s) => s.id === aluno?.sedeId);

  // Antes de qualquer return: hook não pode ficar atrás de saída antecipada.
  useTituloDaTela(aluno?.nome);

  if (isPending) {
    return (
      <div className="tela">
        <section className="card"><div className="empty-state">Carregando…</div></section>
      </div>
    );
  }

  if (isError || !aluno) {
    return (
      <div className="tela">
        <section className="card">
          <div className="empty-state">
            {`Aluno ${id} não encontrado.`}
            <div className="empty-state__hint">
              <Link to="/alunos">← Voltar para a lista</Link>
            </div>
          </div>
        </section>
      </div>
    );
  }

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

  async function salvarNota(valores: ValoresNota | null) {
    const alvo = emEdicao;
    setEmEdicao(null);
    if (!valores || !alvo) return;
    try {
      await editarNota.mutateAsync({ alunoId: id, simuladoId: alvo.simulado.id, corpo: valores });
    } catch (e) {
      setErroSalvar(`Erro ao salvar: ${(e as Error).message}`);
    }
  }

  // O panorama mostra o histórico TOTAL do aluno, não a visão filtrada da tela.
  const dadosPanorama = () => ({
    aluno, turma, sede, simuladosDoAluno, notasPorSimulado, heat, similares,
  });

  const alvos = aluno.vestibularesAlvo.length > 0 ? aluno.vestibularesAlvo.join(', ') : '—';
  const totalPontos = series.reduce((acc, s) => acc + s.pontos.length, 0);

  return (
    // A ficha é TELA DE LEITURA, e por isso ganha a coluna lateral de 320px
    // com o contexto que vivia espalhado pelo cabeçalho: a régua em vigor,
    // onde o aluno está contra ela, as classificações e as ações. As telas de
    // VARREDURA — painel, alunos, banco — não têm: lá a tabela tem 14 colunas,
    // e 320px do lado direito saem direto da tarefa mais frequente do dia
    // (docs/brief-claude-design-coordenacao.md §A arquitetura).
    <div className="tela ficha-duas-colunas">
      <div className="screen-stack ficha-coluna">
        <section className="card">
          <div className="aluno-ficha__header">
            <div className="aluno-ficha__header-info" style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <Avatar tipo="aluno" id={aluno.id} nome={aluno.nome} temFoto={aluno.temFoto} className="avatar avatar--grande" />
              <div>
                <div className="screen-breadcrumb">{aluno.id}</div>
                <h1 className="screen-title">{aluno.nome}</h1>
                <p className="screen-subtitle">
                  {`${turma?.nome ?? '—'} · ${sede?.nome ?? '—'} · alvos: ${alvos}`}
                </p>
              </div>
            </div>

            {/* As ações mudaram de lugar — ver a coluna lateral. */}
            <MenuExportar
              onPanoramaPDF={() => exportarPanoramaPDF(dadosPanorama())}
              onPanoramaPNG={() =>
                exportarPanoramaPNG(dadosPanorama()).catch(() => {
                  setErroSalvar(
                    'Não consegui gerar o PNG do panorama. Tente o PDF, ou veja o console pra detalhes.',
                  );
                })
              }
              onPNG={() => exportarPNGGrafico(refGrafico.current?.querySelector('svg'), aluno)}
              onCSV={() => exportarCSVHistorico(filtrados, notasPorSimulado, aluno)}
              onPDF={() => exportarPDFFicha()}
            />
          </div>

          {erroSalvar && <div className="agendar__erro">{erroSalvar}</div>}

          <SimFiltros
            opcoes={opcoes}
            filtro={filtro}
            contagens={contagens}
            onToggle={alternar}
            onLimpar={() => setFiltro(FILTRO_VAZIO)}
          />
        </section>

        <section className="card">
          <div className="section">
            <GraficoEmCamadas
              titulo="Evolução do aluno"
              legenda={filtro.materias.size > 0
                ? `${series.length} matéria(s), ${totalPontos} ponto(s) no gráfico — passe o mouse pra detalhes.`
                : 'Linha agregada: média do aluno por ciclo. Filtre por matéria pra ver linhas separadas.'}
              frase={lerSeries(series.map((s) => ({ nome: s.nome, notas: s.pontos.map((p) => p.nota) })))}
              grafico={() => (
                <div ref={refGrafico}>
                  <LinhaEvolucao
                    series={series}
                    ciclosEixo={ciclosEixo}
                    corte={corte?.valor}
                    corteRotulo={corte?.rotulo}
                  />
                </div>
              )}
            />
          </div>
        </section>

        <section className="card">
          <div className="section">
            <div className="section__title">Histórico de simulados</div>
            <div className="section__subtitle">
              {`${filtrados.length} de ${simuladosDoAluno.length} simulados feitos pelo aluno`}
            </div>
            <div className="section">
              <TabelaSimulados
                simulados={filtrados}
                notasAluno={notasPorSimulado}
                compacto
                onEditarNota={(simulado, nota) => setEmEdicao({ simulado, nota })}
              />
            </div>
          </div>
        </section>

        <section className="card aluno-ficha__nao-imprimir">
          <div className="section">
            <GraficoEmCamadas
              titulo="Heatmap matérias × simulados"
              legenda="Célula cheia = acima do corte, e quanto mais forte, mais folga; célula vazada = abaixo. Cobre todo o histórico do aluno (independente dos filtros acima)."
              // O heatmap não tem insight de LLM por trás — não existe recorte
              // em `insight_ciclo` que corresponda a "este aluno, todas as
              // matérias". A camada aparece vazia, com a mensagem que o
              // `InsightsPainel` já dá nesse caso, em vez de sumir: o degrau
              // sumindo em um gráfico e não em outro é pior que o degrau vazio.
              frase={null}
              grafico={() => <Heatmap payload={heat} notaMaxima={10} corte={corte?.valor ?? null} />}
            />
          </div>
        </section>

      </div>

      {/* A COLUNA LATERAL, 320px. O contexto que estava espalhado pelo
          cabeçalho e pelo fim da rolagem: onde o aluno está contra a régua,
          as classificações como PALAVRA, e o acesso. */}
      <aside className="ficha-lateral aluno-ficha__nao-imprimir">
        <section className="card">
          <div className="section">
            <div className="section__title">Onde ele está</div>
            <div className="section__subtitle">
              {reguaAtiva ? `régua ${reguaAtiva.nome}` : 'régua indisponível'}
            </div>
            {/* A MESMA peça que o aluno vê de si mesmo, e é de propósito: é
                aqui que a coerência entre os dois produtos fica evidente. */}
            <BarraCorte materias={materiasContraCorte} />
          </div>
        </section>

        <section className="card">
          <div className="section">
            <div className="section__title">Classificações</div>
            {/* Perfil e tendência como PALAVRAS, não como cores (R4/R7): o que
                a tag diz é a categoria, e o desenho dela é contorno. */}
            <div className="ficha-lateral__tags">
              <span className="tag tone-navy">{PERFIL_LABEL[aluno.perfil] || aluno.perfil}</span>
              <span className={`tag ${TENDENCIA_TONE[aluno.tendencia] ?? ''}`}>
                {TENDENCIA_LABEL[aluno.tendencia] || aluno.tendencia}
              </span>
              <span className={`tag ${ZONA_TONE[aluno.zona] ?? ''}`}>
                {ZONA_LABEL[aluno.zona] || aluno.zona}
              </span>
            </div>
          </div>
        </section>

        <PerfisSemelhantes similares={similares} />

        <section className="card">
          <div className="section">
            <div className="section__title">Métricas internas</div>
            <div className="kpi-grid">
              <Kpi rotulo="Média recente" valor={fmtNota(aluno.media)} />
              <Kpi rotulo="Notas no histórico" valor={String(trajetoria.length)} />
              <Kpi rotulo="Janela" valor={String(aluno.sparkline?.length || 0)} />
            </div>
          </div>
        </section>

        <AcessoDoAluno aluno={aluno} />
      </aside>

      {emEdicao && (
        <EdicaoNota
          nomeAluno={aluno.nome}
          nomeSimulado={emEdicao.simulado.rotuloCurto || emEdicao.simulado.nome}
          pontuacaoAtual={pontuacaoBruta(emEdicao.nota, emEdicao.simulado)}
          presenteAtual={emEdicao.nota != null}
          notaMaxima={emEdicao.simulado.notaMaxima}
          onFechar={salvarNota}
        />
      )}
    </div>
  );
}

/** A tabela mostra a nota em escala 0-10; o backend espera a pontuação bruta. */
function pontuacaoBruta(nota: number | null, simulado: Simulado): number | null {
  if (nota == null || !simulado.notaMaxima) return null;
  return Math.round((nota / 10) * simulado.notaMaxima * 100) / 100;
}

function PerfisSemelhantes({ similares }: { similares: AlunoSimilar[] }) {
  const navegar = useNavigate();

  return (
    <section className="card aluno-ficha__nao-imprimir">
      <div className="section">
        <div className="section__title">Perfis semelhantes</div>
        <div className="section__subtitle">
          {`kNN por vetor de features (média por matéria + desvio + tendência). ${similares.length} resultados.`}
        </div>

        {similares.length === 0 ? (
          <p className="section__subtitle">
            Sem similares — aluno ainda não tem features suficientes.
          </p>
        ) : (
          <table className="tabela-similares">
            <thead>
              <tr>
                <th>Aluno</th>
                <th>Distância</th>
                <th>Perfil</th>
                <th>Tendência</th>
                <th>Zona</th>
                <th>Média</th>
              </tr>
            </thead>
            <tbody>
              {similares.map((s) => (
                <tr key={s.alunoId} onClick={() => navegar(`/alunos/${s.alunoId}`)}>
                  <td>{s.nome}</td>
                  <td>{s.distancia.toFixed(2).replace('.', ',')}</td>
                  <td>{s.perfil ? PERFIL_LABEL[s.perfil] || s.perfil : '—'}</td>
                  <td>
                    {s.tendencia ? (
                      <span className={`tag ${TENDENCIA_TONE[s.tendencia] ?? ''}`}>
                        {TENDENCIA_LABEL[s.tendencia] || s.tendencia}
                      </span>
                    ) : '—'}
                  </td>
                  <td>
                    {s.zona ? (
                      <span className={`tag ${ZONA_TONE[s.zona] ?? ''}`}>
                        {ZONA_LABEL[s.zona] || s.zona}
                      </span>
                    ) : '—'}
                  </td>
                  <td>{fmtNota(s.media)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
