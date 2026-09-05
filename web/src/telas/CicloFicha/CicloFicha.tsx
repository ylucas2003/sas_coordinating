import { useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';

import { CartaoDeCampo, EloQuieto } from '../../componentes/ui/Campo';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { exportarDossiePdf, exportarDossieWord } from './dossie';
import {
  Avancado, Conjunta, Evolucao, Hero, PorMateria, TabelaSimuladosDoCiclo, tituloDoGrafico,
} from './pecas';
import {
  useCiclo, useClassificacaoCiclo, useCriteriosDisponiveis, useEstatisticasCiclo,
  usePendenciasCanvas, useSimulados,
} from '../../hooks/consultas';
import { useRecorteDaTela, useTituloDaTela } from '../../componentes/layout/migalhas';

// FICHA DE CICLO — a entrada, e três campos.
//
// Era a tela mais densa do produto e a que mais sofria da doença que o padrão
// de campo cura: empilhava numa rolagem só seis matérias × duas fases ×
// histograma × média × mediana × desvio × percentis × delta entre fases — com
// um toggle "avançado" que já era uma tentativa pobre de esconder metade.
//
// Aplicando C1, são três PERGUNTAS e três telas
// (docs/brief-claude-design-coordenacao.md §5):
//
//   CALIBRAÇÃO  "A prova estava boa?"       — e o avançado deixa de precisar
//                                             de toggle, porque a tela é dele
//   RÉGUA       "Quem passou?"
//   COMPARAÇÃO  "Onde estamos diferentes?"
//
// Na entrada fica só a identidade do ciclo, três KPIs em MAGNITUDE, os três
// campos e o elo quieto das pendências. Nada mais.
//
// ⚠️ O DOSSIÊ CONTINUA SENDO UM DOCUMENTO COM TUDO. Os campos dividem a
// leitura na tela, não o documento impresso — e isso obrigou uma solução: o
// dossiê colhe os `<svg>` JÁ DESENHADOS da árvore, e a entrada não desenha
// mais quase nenhum. Em vez de redesenhar os gráficos num segundo lugar (dois
// desenhos do mesmo gráfico divergem no primeiro ajuste), a fonte é montada
// fora da tela só enquanto o dossiê é gerado, com as MESMAS peças.

export function CicloFicha() {
  const { id = '' } = useParams();
  const { data: ciclo, isPending: carregandoCiclo, isError: erroCiclo } = useCiclo(id);
  const { data: todos = [] } = useSimulados();
  // A régua escolhida decide TODOS os cortes desta tela e das três de campo.
  const [criterio, setCriterio] = useState('tio-leo');
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const { data: stats, isPending: carregandoStats } = useEstatisticasCiclo(id, criterio);
  const { data: classificacao, isPending: carregandoClass } = useClassificacaoCiclo(
    id || null,
    criterio,
  );
  const { data: pendencias } = usePendenciasCanvas(id || null);

  const [erroDossie, setErroDossie] = useState('');
  const [gerandoDossie, setGerandoDossie] = useState(false);
  // Só fica montado enquanto o dossiê é gerado. Ver a nota do cabeçalho.
  const [montandoFonte, setMontandoFonte] = useState(false);
  const refFonte = useRef<HTMLDivElement>(null);

  useTituloDaTela(ciclo?.nome ?? null);
  useRecorteDaTela(null);

  const doCiclo = useMemo(
    () => todos.filter((s) => s.cicloId === id),
    [todos, id],
  );

  async function gerarDossie(formato: 'pdf' | 'word') {
    if (!stats || !ciclo) return;
    setErroDossie('');
    setGerandoDossie(true);
    setMontandoFonte(true);
    try {
      // Dois quadros para o React montar a fonte e o layout resolver: sem
      // isso os `<svg>` existem mas ainda não têm dimensão, e o dossiê sai com
      // gráficos de tamanho zero.
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const svgs = Array.from(refFonte.current?.querySelectorAll('svg') ?? []);
      const graficos = svgs.map((svg) => ({
        titulo: tituloDoGrafico(svg as SVGSVGElement),
        svg: svg as SVGSVGElement,
      }));
      const dados = {
        ciclo,
        stats,
        simulados: doCiclo,
        nomeCriterio: criterios.find((c) => c.slug === criterio)?.nome ?? criterio,
        graficos,
      };
      if (formato === 'pdf') await exportarDossiePdf(dados);
      else await exportarDossieWord(dados);
    } catch (e) {
      setErroDossie((e as Error).message || 'Não consegui gerar o dossiê.');
    } finally {
      setMontandoFonte(false);
      setGerandoDossie(false);
    }
  }

  if (carregandoCiclo) {
    return <div className="tela"><section className="card"><div className="empty-state">Carregando…</div></section></div>;
  }
  if (erroCiclo || !ciclo) {
    return (
      <div className="tela">
        <section className="card"><div className="empty-state">Ciclo não encontrado.</div></section>
      </div>
    );
  }

  const nMaterias = stats?.porMateria?.length ?? 0;
  // "Fora do padrão" aqui é o que o payload de fato permite dizer: matéria com
  // zona crítica alta. NÃO é comparação com o histórico — essa o servidor não
  // devolve por matéria, e escrever "2 fora do padrão histórico" sem ter o
  // histórico seria inventar o número que o card existe para relatar (C2).
  const materiasCriticas = (stats?.porMateria ?? []).filter(
    (r) => (r.fase1?.stats?.pctZonaCritica ?? 0) >= 20 || (r.fase2?.stats?.pctZonaCritica ?? 0) >= 20,
  ).length;

  const subCalibracao = !stats || nMaterias === 0
    ? null
    : materiasCriticas
      ? `${nMaterias} matérias · ${materiasCriticas} com zona crítica acima de 20%`
      : `${nMaterias} matérias · nenhuma com zona crítica alta`;

  const subRegua = !classificacao
    ? null
    : `${classificacao.cortados} de ${classificacao.total} cortados · régua ${classificacao.criterio.nome}`;

  const nPontos = stats?.evolucaoTemporal?.length ?? 0;
  const anterior = stats?.cicloAnterior?.nome ?? null;
  const subComparacao = !stats || nPontos === 0
    ? null
    : anterior
      ? `${nPontos} provas · contra ${anterior}`
      : `${nPontos} provas · sem ciclo anterior para comparar`;

  // `total` já é a contagem do payload. `undefined` cobre os dois casos em
  // que o elo deve sumir — sem pendência e consulta falhada —, e é por isso
  // que o `?? null` não vira `?? 0`.
  const nPendencias = pendencias?.total ?? null;

  return (
    <div className="tela">
      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">{ciclo.nome}</h1>
          <p className="tela-subtitulo">
            {ciclo.vestibularAlvo && <span className="tag tone-navy" style={{ marginRight: 8 }}>{ciclo.vestibularAlvo}</span>}
            {`${ciclo.periodoInicio || '—'} → ${ciclo.periodoFim || '—'} · ${doCiclo.length} simulados`}
          </p>
        </div>
      </div>

      <div className="ciclo-ficha__regua">
        <span className="ciclo-ficha__regua-rotulo">Régua de corte</span>
        <SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />
        {/* O dossiê é o mesmo conteúdo em documento, para levar à reunião
            (docs/33 §5). Fica junto da régua porque ela decide os números que
            ele carrega — e continua UM documento com tudo. */}
        {stats && (
          <>
            <button className="btn-editar-sim" disabled={gerandoDossie} onClick={() => gerarDossie('pdf')}>
              {gerandoDossie ? 'Gerando…' : 'Dossiê PDF'}
            </button>
            <button className="btn-editar-sim" disabled={gerandoDossie} onClick={() => gerarDossie('word')}>
              Dossiê Word
            </button>
          </>
        )}
      </div>
      {erroDossie && <div className="agendar__erro">{erroDossie}</div>}

      {carregandoStats ? (
        <section className="card"><div className="empty-state">Calculando estatísticas…</div></section>
      ) : stats ? (
        <Hero stats={stats} />
      ) : (
        <section className="card">
          <div className="empty-state">Erro ao calcular estatísticas. Verifique o backend.</div>
        </section>
      )}

      <div className="campo-grade">
        <CartaoDeCampo
          olho="Calibração"
          titulo="A prova estava boa?"
          para={`/ciclos/${id}/calibracao`}
          carregando={carregandoStats}
          subtitulo={subCalibracao}
          vazio="Nenhuma prova com nota lançada neste ciclo ainda."
          glifo={
            <>
              <path d="M14 52V30M26 52V18M38 52V36M50 52V24" />
              <path d="M10 58h50" />
            </>
          }
        />
        <CartaoDeCampo
          olho="Régua"
          titulo="Quem passou?"
          para={`/ciclos/${id}/regua`}
          carregando={carregandoClass}
          subtitulo={subRegua}
          vazio="A classificação ainda não pode ser calculada para este ciclo."
          glifo={
            <>
              <path d="M12 34h46" />
              <path d="M16 26v16M30 26v16M44 26v16M58 26v16" />
            </>
          }
        />
        <CartaoDeCampo
          olho="Comparação"
          titulo="Onde estamos diferentes?"
          para={`/ciclos/${id}/comparacao`}
          carregando={carregandoStats}
          subtitulo={subComparacao}
          vazio="Ainda não há provas suficientes para comparar."
          glifo={
            <>
              <path d="M20 50V22a8 8 0 0 1 16 0v28M36 50V30a8 8 0 0 1 16 0v20" />
              <path d="M12 58h48" />
            </>
          }
        />
      </div>

      {/* C5 · o elo quieto. Some quando não há pendência — e some também
          quando a consulta falha, porque "0 pendências" para quem tem 3 é a
          mentira mais cara da tela. `usePendenciasCanvas` devolve `undefined`
          nos dois casos, e `null` faz o elo não aparecer. */}
      <div className="campo-elos">
        <EloQuieto para={`/ciclos/${id}/regua`} texto="Pendências do ciclo" contagem={nPendencias} />
      </div>

      {/* A fonte do dossiê. Fora da tela, montada só enquanto gera. */}
      {montandoFonte && stats && (
        <div className="ciclo-dossie-fonte" ref={refFonte} aria-hidden="true">
          <Evolucao stats={stats} />
          <Conjunta stats={stats} />
          <PorMateria recortes={stats.porMateria ?? []} />
          <TabelaSimuladosDoCiclo simulados={doCiclo} />
          <Avancado stats={stats} />
        </div>
      )}
    </div>
  );
}
