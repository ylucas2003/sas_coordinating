import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { CartaoDeCampo } from '../../componentes/ui/Campo';
import { FichaNota } from '../../componentes/dialogos/FichaNota';
import type { ValoresNota } from '../../componentes/dialogos/formularioNota';
import { BarraFiltros, Busca, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { BlocoPendenciasCanvas } from './PendenciasCanvas';
import { TabelaDoCiclo } from './TabelaDoCiclo';
import { exportarDossiePdf, exportarDossieWord } from './dossie';
import {
  Avancado, Conjunta, Evolucao, Kpis, PorMateria, TabelaSimuladosDoCiclo, tituloDoGrafico,
} from './pecas';
import { isoDoDia } from '../../dominio/cantina';
import { saidasDoCicloVazio } from '../../dominio/cicloVazio';
import { corteDaMateria, eliminaSozinho, REGUA_DA_CASA } from '../../dominio/criterios';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import {
  estatisticasDoSimulado, montarPainel, nomeSede, normMateria,
} from '../../dominio/painel';
import type { ClassificacaoPorAluno, OrdenacaoPainel } from '../../dominio/painel';
import {
  useAlunos, useCiclo, useCiclos, useClassificacaoCiclo, useCriteriosDisponiveis,
  useEstatisticasCiclo, useNotasDoCiclo, usePendenciasCanvas, useSedes, useSimulados, useTurmas,
} from '../../hooks/consultas';
import { useEditarNota } from '../../hooks/mutacoes';
import { useRecorteDaTela, useTituloDaTela } from '../../componentes/layout/migalhas';
import type { Aluno, AlunoClassificado, Ciclo } from '../../tipos/dominio';

// FICHA DE CICLO — a chegada, dois campos e a varredura, numa rolagem só.
//
// ⚠️ ESTA TELA TEM DUAS ESCALAS DE ATENÇÃO NA MESMA ROLAGEM, e isso é
// intencional — decisão do dono do produto, contra o padrão de campo. A tabela
// de 900 alunos PERTENCE ao ciclo; escondê-la atrás de um terceiro card foi
// proposto e recusado, porque a varredura é a tarefa dominante do dia e ela já
// pagou um clique quando saiu do Painel (docs/39 §PRECEDÊNCIA).
//
// O que sobra, então, é fazer o bloco de chegada deixar de ser OBSTÁCULO sem
// escondê-lo. A prancheta resolve com quatro movimentos, e os quatro estão
// aqui (prancheta de Provas, telas `ciclo` e `rolado`):
//
//   1. Os quatro KPIs deixam a fileira larga e viram GRADE 2×2, dividindo a
//      faixa com os campos. Nenhum número foi tirado; eles só pararam de
//      ocupar a largura inteira.
//   2. Os campos viram uma FAIXA FINA de 520px ao lado dos KPIs — cards
//      ainda, porque são perguntas que o coordenador não sabe que quer fazer,
//      mas horizontais e de 19px em vez de monumentais. Todo o bloco antes da
//      tabela cabe numa faixa só, e o cabeçalho da tabela aparece na chegada.
//   3. Ao ROLAR, a régua e os campos encolhem para uma tira grudada no topo.
//      Eles nunca viram rodapé: a régua continua visível enquanto se varre,
//      que é a única forma de o coordenador saber contra o que está lendo.
//   4. A RÉGUA sai da faixa de filtros e vai para a linha da identidade, numa
//      moldura de ouro rotulada. Ela é LENTE, não recorte — decide o corte da
//      tabela E dos dois campos —, e precisa parecer isso. Os filtros da
//      tabela (sede, turma, busca, fase, ordem) ficam colados na tabela,
//      porque pertencem a ela e não à tela.
//
// ⚠️ O DOSSIÊ CONTINUA SENDO UM DOCUMENTO COM TUDO. Os campos dividem a
// leitura na tela, não o documento impresso — e isso obrigou uma solução: o
// dossiê colhe os `<svg>` JÁ DESENHADOS da árvore, e a chegada não desenha
// nenhum. Em vez de redesenhar os gráficos num segundo lugar (dois desenhos do
// mesmo gráfico divergem no primeiro ajuste), a fonte é montada fora da tela
// só enquanto o dossiê é gerado, com as MESMAS peças.
//
// ⚠️ AS PENDÊNCIAS DO CANVAS MUDARAM DE CASA junto com a resposta.
// Elas viviam dentro da Régua com um motivo bom — "quem passou não tem
// resposta honesta enquanto houver prova sem nota lançada" —, e a Régua foi
// absorvida pela tabela. O argumento veio junto, mas partido em dois, porque
// as duas metades têm público e tamanho diferentes:
//
//   a RESSALVA  é um elo quieto na faixa de chegada, com a contagem. Ela
//               precisa ser lida ANTES da tabela, e custa uma linha.
//   a TAREFA    (a lista item a item e o envio em lote) fica DEPOIS da tabela,
//               no destino do elo. Ela pode ter dezenas de linhas, e pô-la
//               antes da tabela seria exatamente a doença que esta tela já
//               aceita uma vez e não pode aceitar duas.
//
// O elo é um `<a href="#…">` de verdade, e não `EloQuieto`: o destino está
// nesta mesma página, e `<Link>` do roteador não rola até fragmento nenhum —
// seria um elo que não vai a lugar algum, que é a promessa quebrada mais
// barata de escrever e a mais cara de descobrir.

/**
 * Onde a tira compacta gruda, e a folga que impede o vai-e-vem.
 *
 * `--topbar-h` vale 72px (`styles/forma.css`). A tira mede 66px e, somada ao
 * vão de 20px da coluna, empurra 86px de conteúdo para baixo ao aparecer.
 *
 * ⚠️ É por isso que a folga existe. Se o gatilho fosse a borda da topbar,
 * montar a tira empurraria a faixa de chegada 86px para baixo, ela voltaria ao
 * campo de visão, a tira sumiria, o conteúdo subiria — e a tela piscaria para
 * sempre. A folga é maior que o empurrão de propósito.
 */
const ALTURA_DA_TOPBAR = 72;
const FOLGA_DA_TIRA = 120;

/** O traço dos dois glifos, compartilhado pelo card e pelo botão da tira. */
const GLIFO_CALIBRACAO = 'M14 52V30M26 52V18M38 52V36M50 52V24M10 58h50';
const GLIFO_COMPARACAO = 'M20 50V22a8 8 0 0 1 16 0v28M36 50V30a8 8 0 0 1 16 0v20M12 58h48';

/** As 24 casas vazias do calendário do estado vazio — 6 colunas × 4 semanas. */
const CASAS_DO_CALENDARIO = Array.from({ length: 24 }, (_, i) => ({
  x: 34 + (i % 6) * 39,
  y: 80 + Math.floor(i / 6) * 32,
}));

/** O nome do ordenador, curto, para a faixa de filtros colapsada (R6). */
const ROTULO_ORDEM_CURTO: Record<OrdenacaoPainel, string> = {
  distancia: 'pior primeiro',
  ranking: 'ranking',
  alfabetica: 'A–Z',
};

function alternarConjunto<V>(set: ReadonlySet<V>, valor: V): ReadonlySet<V> {
  const novo = new Set(set);
  if (novo.has(valor)) novo.delete(valor);
  else novo.add(valor);
  return novo;
}

export function CicloFicha() {
  const { id = '' } = useParams();
  // O dia, recalculado a cada render: a aba fica aberta a manhã inteira, e
  // congelar `hoje` faria a virada da meia-noite passar sem a tela perceber.
  const hoje = isoDoDia(new Date());

  const { data: ciclo, isPending: carregandoCiclo, isError: erroCiclo } = useCiclo(id);
  const { data: ciclos = [] } = useCiclos();
  const { data: todos = [], isPending: carregandoSimulados } = useSimulados();
  const { data: alunos = [] } = useAlunos();
  const { data: sedes = [] } = useSedes();
  const { data: turmas = [] } = useTurmas();

  // A régua escolhida decide TODOS os cortes desta tela: os dois campos, os
  // KPIs e cada célula da tabela. É por isso que ela não é um grupo da faixa
  // de filtros — um recorte peneira linhas, uma lente muda o que elas dizem.
  const [criterio, setCriterio] = useState<string>(REGUA_DA_CASA);
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const { data: stats, isPending: carregandoStats } = useEstatisticasCiclo(id, criterio);

  // ─── O estado da tabela ────────────────────────────────────────────────
  const [sedeIds, setSedeIds] = useState<ReadonlySet<string>>(new Set());
  const [turmaIds, setTurmaIds] = useState<ReadonlySet<string>>(new Set());
  const [busca, setBusca] = useState('');
  const [fase, setFase] = useState<'1' | '2'>('1');
  // R6 · a tabela ABRE pela distância do corte, ascendente — o pior primeiro.
  // É o que substitui a cor como mecanismo de varredura, e por isso é o padrão
  // e não mais uma opção na lista.
  const [ordenacao, setOrdenacao] = useState<OrdenacaoPainel>('distancia');
  const [recolhidos, setRecolhidos] = useState<ReadonlySet<number>>(new Set());
  const [emEdicao, setEmEdicao] = useState<{ alunoId: string; simuladoId: string } | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');

  const { data: notasPorSim = {}, isPending: carregandoNotas } = useNotasDoCiclo(ciclo, todos);
  // Veredito, motivo, cor e posição vêm do servidor (docs/18 §1.2). A fase
  // exibida manda: a régua do colégio vale para qualquer fase; as do edital já
  // sabem a sua.
  const { data: classificacaoResp } = useClassificacaoCiclo(
    id || null, criterio, fase === '1' ? 1 : 2,
  );
  const { data: pendencias } = usePendenciasCanvas(id || null);
  const editarNota = useEditarNota();

  // ─── O dossiê ──────────────────────────────────────────────────────────
  const [erroDossie, setErroDossie] = useState('');
  const [gerandoDossie, setGerandoDossie] = useState(false);
  // Só fica montado enquanto o dossiê é gerado. Ver a nota do cabeçalho.
  const [montandoFonte, setMontandoFonte] = useState(false);
  const refFonte = useRef<HTMLDivElement>(null);
  const refTabela = useRef<HTMLElement>(null);

  // ─── A tira: rolou, ou ainda está na chegada? ──────────────────────────
  // O nó vem por callback de ref e não por `useRef`, porque a faixa de chegada
  // não existe em todos os estados da tela (carregando, ciclo vazio) — e um
  // efeito com `[]` de dependência observaria `null` para sempre.
  const [noDaChegada, setNoDaChegada] = useState<HTMLElement | null>(null);
  const [rolado, setRolado] = useState(false);

  useTituloDaTela(ciclo?.nome ?? null);

  useEffect(() => {
    if (!noDaChegada || typeof IntersectionObserver === 'undefined') return;
    const observador = new IntersectionObserver(
      ([entrada]) => setRolado(!entrada.isIntersecting),
      { rootMargin: `-${ALTURA_DA_TOPBAR + FOLGA_DA_TIRA}px 0px 0px 0px`, threshold: 0 },
    );
    observador.observe(noDaChegada);
    return () => observador.disconnect();
  }, [noDaChegada]);

  const doCiclo = useMemo(
    () => todos.filter((s) => s.cicloId === id),
    [todos, id],
  );

  const classificacao = useMemo<ClassificacaoPorAluno>(() => {
    const porAluno: Record<string, AlunoClassificado> = {};
    for (const a of classificacaoResp?.alunos ?? []) porAluno[a.alunoId] = a;
    return porAluno;
  }, [classificacaoResp]);

  const alunosFiltrados = useMemo(() => {
    const q = normMateria(busca.trim());
    return alunos.filter((a) => {
      if (sedeIds.size && !sedeIds.has(a.sedeId)) return false;
      if (turmaIds.size && !turmaIds.has(a.turmaId)) return false;
      if (q && !normMateria(a.nome).includes(q)) return false;
      return true;
    });
  }, [alunos, sedeIds, turmaIds, busca]);

  const dados = useMemo(
    () => montarPainel({
      ciclo: ciclo ?? null,
      simulados: todos,
      alunos: alunosFiltrados,
      notasPorSim,
      fase,
      ordenacao,
      classificacao,
      criterio: classificacaoResp?.criterio ?? null,
    }),
    [
      ciclo, todos, alunosFiltrados, notasPorSim, fase, ordenacao, classificacao,
      classificacaoResp?.criterio,
    ],
  );

  // A fase escolhida pode não existir neste ciclo — segue a que sobrou.
  useEffect(() => {
    if (dados.faseSelecionada !== fase) setFase(dados.faseSelecionada);
  }, [dados.faseSelecionada, fase]);

  const turmaPorId = useMemo(
    () => new Map(turmas.map((t) => [t.id, t])),
    [turmas],
  );
  const nomeDaTurma = useMemo(
    () => (a: Aluno) => turmaPorId.get(a.turmaId)?.nome ?? null,
    [turmaPorId],
  );

  // O que o assistente precisa para "e a Física?" ter referente. O ciclo vem
  // da rota; o resto vive em `useState` e só esta tela sabe.
  useRecorteDaTela(useMemo(() => ({
    cicloId: id,
    fase: fase === '1' ? (1 as const) : (2 as const),
    criterio,
    sedeIds: [...sedeIds],
    turmaIds: [...turmaIds],
  }), [id, fase, criterio, sedeIds, turmaIds]));

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
      // `documento`, e não `dados`: a tela já tem um `dados` — o da tabela —, e
      // dois nomes iguais em escopos aninhados é o tipo de coisa que sobrevive
      // até alguém mexer no `await` do meio.
      const documento = {
        ciclo,
        stats,
        simulados: doCiclo,
        nomeCriterio: criterios.find((c) => c.slug === criterio)?.nome ?? criterio,
        graficos,
      };
      if (formato === 'pdf') await exportarDossiePdf(documento);
      else await exportarDossieWord(documento);
    } catch (e) {
      setErroDossie((e as Error).message || 'Não consegui gerar o dossiê.');
    } finally {
      setMontandoFonte(false);
      setGerandoDossie(false);
    }
  }

  async function salvarNota(valores: ValoresNota | null) {
    const alvo = emEdicao;
    setEmEdicao(null);
    if (!valores || !alvo) return;
    try {
      await editarNota.mutateAsync({
        alunoId: alvo.alunoId,
        simuladoId: alvo.simuladoId,
        corpo: valores,
      });
    } catch (e) {
      setErroSalvar(`Erro ao salvar: ${(e as Error).message}`);
    }
  }

  function rolarAteATabela() {
    const suave = !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    refTabela.current?.scrollIntoView({ behavior: suave ? 'smooth' : 'auto', block: 'start' });
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

  // ─── O ciclo sem nenhuma prova ────────────────────────────────────────
  // Só depois de os simulados chegarem: uma lista ainda vazia por estar
  // carregando não é um ciclo sem prova, e piscar o estado vazio é dizer que
  // não há dado para quem só esperou meio segundo.
  if (!carregandoSimulados && doCiclo.length === 0 && ciclo.simuladoIds.length === 0) {
    return <CicloSemProva ciclo={ciclo} ciclos={ciclos} />;
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

  const nPontos = stats?.evolucaoTemporal?.length ?? 0;
  const anterior = stats?.cicloAnterior?.nome ?? null;
  const subComparacao = !stats || nPontos === 0
    ? null
    : anterior
      ? `${nPontos} provas · contra ${anterior}`
      : `${nPontos} provas · sem ciclo anterior para comparar`;

  // Os mesmos dois campos, na medida da tira: um par de palavras cada, porque
  // ali eles competem com a tabela e não podem ganhar.
  const resumoCalibracao = !stats || nMaterias === 0
    ? null
    : materiasCriticas
      ? `${materiasCriticas} em zona crítica`
      : `${nMaterias} matérias`;
  const resumoComparacao = !stats || nPontos === 0
    ? null
    : anterior
      ? `contra ${anterior}`
      : `${nPontos} provas`;

  // `total` já é a contagem do payload. `undefined` cobre os dois casos em que
  // a ressalva deve sumir — sem pendência e consulta falhada —, e é por isso
  // que o `?? null` não vira `?? 0`: "0 pendências" para quem tem 3 é a mentira
  // mais cara da tela.
  const nPendencias = pendencias?.total ?? null;

  const nomeDaRegua = classificacaoResp?.criterio.nome
    ?? criterios.find((c) => c.slug === criterio)?.nome
    ?? null;

  const aplicadas = doCiclo.filter((s) => s.dataAplicacao && s.dataAplicacao <= hoje).length;
  const previstas = ciclo.simuladoIds.length || doCiclo.length;

  const algumFiltroAtivo = sedeIds.size > 0 || turmaIds.size > 0 || busca.trim() !== '';

  return (
    <div className="tela">
      {/* A TIRA · rolado. Carrega o nome do ciclo, a régua em vigor e os dois
          campos como botões compactos com o número vivo. Os campos ENCOLHEM,
          não descem: virar rodapé seria escondê-los, e eles são perguntas que
          o coordenador não sabe que quer fazer. */}
      {rolado && (
        <div className="ciclo-tira">
          <span className="ciclo-tira__nome">{ciclo.nome}</span>
          {nomeDaRegua && (
            <span className="ciclo-tira__regua">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" strokeDasharray="3 2" aria-hidden="true">
                <path d="M4 12h16" />
              </svg>
              {`Régua ${nomeDaRegua}`}
            </span>
          )}
          <div className="ciclo-tira__campos">
            <CampoCompacto
              para={`/ciclos/${id}/calibracao`}
              glifo={GLIFO_CALIBRACAO}
              titulo="A prova estava boa?"
              resumo={resumoCalibracao}
            />
            <CampoCompacto
              para={`/ciclos/${id}/comparacao`}
              glifo={GLIFO_COMPARACAO}
              titulo="Onde estamos diferentes?"
              resumo={resumoComparacao}
            />
          </div>
        </div>
      )}

      {/* A FAIXA DE CHEGADA — identidade, régua, dossiê, KPIs e campos. Tudo o
          que vem antes da tabela cabe aqui, e é essa contenção que faz o
          cabeçalho da tabela aparecer sem rolagem. */}
      <div className="ciclo-chegada" ref={setNoDaChegada}>
        <div className="ciclo-identidade">
          <div className="ciclo-identidade__texto">
            <div className="ciclo-identidade__linha">
              <h1 className="ciclo-identidade__nome">{ciclo.nome}</h1>
              {ciclo.vestibularAlvo && (
                <span className="ciclo-identidade__vestibular">{ciclo.vestibularAlvo}</span>
              )}
            </div>
            <div className="ciclo-identidade__meta">
              <span>{`${ciclo.periodoInicio || '—'} → ${ciclo.periodoFim || '—'}`}</span>
              <span aria-hidden="true">·</span>
              <span>{`${aplicadas} de ${previstas} provas aplicadas`}</span>
              {previstas > 0 && (
                // A barra é o mesmo número em forma — e é ela que diz, sem
                // ler, se o ciclo está no começo ou fechando. Decorativa: o
                // texto ao lado já carrega a informação.
                <span className="ciclo-progresso" aria-hidden="true">
                  <span
                    className="ciclo-progresso__feito"
                    style={{ width: `${Math.min(100, (aplicadas / previstas) * 100)}%` }}
                  />
                </span>
              )}
            </div>
          </div>

          <div className="ciclo-identidade__acoes">
            {/* R2 · A RÉGUA É LENTE, NÃO FILTRO. Moldura de ouro na linha da
                identidade, rotulada com o alcance dela — longe da faixa de
                pílulas da tabela, que peneira linhas. Trocá-la muda quem está
                cortado, os KPIs e os dois campos ao mesmo tempo. */}
            <div className="ciclo-lente">
              <span className="ciclo-lente__olho">Régua de corte · toda a tela</span>
              <SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />
            </div>
            {/* O dossiê é o mesmo conteúdo em documento, para levar à reunião
                (docs/33 §5). Fica junto da régua porque ela decide os números
                que ele carrega — e continua UM documento com tudo. */}
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
        </div>

        {erroDossie && <div className="agendar__erro">{erroDossie}</div>}

        <div className="ciclo-faixa">
          {carregandoStats ? (
            <div className="ciclo-kpis ciclo-kpis--esqueleto" aria-hidden="true">
              <div className="ciclo-kpi" /><div className="ciclo-kpi" />
              <div className="ciclo-kpi" /><div className="ciclo-kpi" />
            </div>
          ) : stats ? (
            <Kpis stats={stats} />
          ) : (
            <div className="ciclo-kpis-erro">
              Não consegui calcular as estatísticas deste ciclo. A tabela abaixo continua valendo —
              ela não depende delas.
            </div>
          )}

          {/* OS CAMPOS · faixa fina, não card grande. Perdem o glifo de 70px e
              o título de 27px, e ganham presença permanente: se ocupassem meia
              tela, a varredura pagaria a conta todo dia (prancheta, §custos). */}
          <div className="ciclo-campos">
            <CartaoDeCampo
              olho="Calibração"
              titulo="A prova estava boa?"
              para={`/ciclos/${id}/calibracao`}
              carregando={carregandoStats}
              subtitulo={subCalibracao}
              vazio="Nenhuma prova com nota lançada neste ciclo ainda."
              glifo={<path d={GLIFO_CALIBRACAO} />}
            />
            <CartaoDeCampo
              olho="Comparação"
              titulo="Onde estamos diferentes?"
              para={`/ciclos/${id}/comparacao`}
              carregando={carregandoStats}
              subtitulo={subComparacao}
              vazio="Ainda não há provas suficientes para comparar."
              glifo={<path d={GLIFO_COMPARACAO} />}
            />
          </div>
        </div>

        <div className="ciclo-rodape-chegada">
          {/* A ressalva, e só ela: a tarefa está lá embaixo. */}
          {nPendencias != null && nPendencias > 0 && (
            <a className="campo-elo" href="#pendencias-do-canvas">
              Pendências no Canvas
              <span className="campo-elo__contagem">{nPendencias}</span>
            </a>
          )}
          <button type="button" className="ciclo-ate-a-tabela" onClick={rolarAteATabela}>
            Rolar até a tabela
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M12 5v14M7 14l5 5 5-5" />
            </svg>
          </button>
        </div>
      </div>

      {/* ─── A VARREDURA ─────────────────────────────────────────────────
          Daqui para baixo é a tabela e o que pertence a ela. Os filtros são
          DELA — peneiram estas linhas — e por isso ficam colados nela, e não
          na linha da identidade onde mora a régua. */}
      <BarraFiltros
        tela="ciclo"
        algumAtivo={algumFiltroAtivo}
        onLimpar={() => {
          setSedeIds(new Set());
          setTurmaIds(new Set());
          setBusca('');
        }}
        grupos={[
          {
            chave: 'busca', rotulo: 'Aluno',
            resumo: resumirTexto(busca),
            corpo: (
              <Busca
                valor={busca}
                onChange={setBusca}
                placeholder={`Peneirar estes ${alunos.length} alunos…`}
                rotulo="Buscar aluno na tabela"
              />
            ),
          },
          dados.fasesDisponiveis.length >= 2 && {
            chave: 'fase', rotulo: 'Fase',
            resumo: dados.faseSelecionada === '1' ? '1ª Fase' : '2ª Fase',
            corpo: (
              <Segmento
                opcoes={dados.fasesDisponiveis.map((f) => ({
                  label: f === '1' ? '1ª Fase' : '2ª Fase',
                  value: f,
                }))}
                valor={dados.faseSelecionada}
                onEscolher={setFase}
              />
            ),
          },
          {
            chave: 'sede', rotulo: 'Sede',
            resumo: resumirSelecao(
              sedeIds,
              sedes.map((sd) => ({ valor: sd.id, label: nomeSede(sd.nome) })),
              'sede', 'sedes',
            ),
            corpo: (
              <Pills
                // Sedes com prefixo de ano são resíduo de importações antigas.
                opcoes={sedes
                  .filter((sd) => !sd.nome.startsWith('2025_'))
                  .map((sd) => ({ valor: sd.id, label: nomeSede(sd.nome) }))}
                selecionados={sedeIds}
                onToggle={(idSede) => setSedeIds((s) => alternarConjunto(s, idSede))}
              />
            ),
          },
          {
            chave: 'turma', rotulo: 'Turmas',
            resumo: resumirSelecao(
              turmaIds,
              turmas.map((t) => ({ valor: t.id, label: t.nome })),
              'turma', 'turmas',
            ),
            corpo: (
              <Pills
                opcoes={turmas.map((t) => ({ valor: t.id, label: t.nome }))}
                selecionados={turmaIds}
                onToggle={(idTurma) => setTurmaIds((s) => alternarConjunto(s, idTurma))}
              />
            ),
          },
          {
            chave: 'ordem', rotulo: 'Ordem',
            resumo: ROTULO_ORDEM_CURTO[ordenacao],
            corpo: (
              <Segmento
                opcoes={[
                  { label: 'Pior primeiro', value: 'distancia' as const },
                  { label: 'Ranking', value: 'ranking' as const },
                  { label: 'A–Z', value: 'alfabetica' as const },
                ]}
                valor={ordenacao}
                onEscolher={setOrdenacao}
              />
            ),
          },
        ]}
      />

      {erroSalvar && <div className="agendar__erro">{erroSalvar}</div>}

      {/* A tabela não desenha o cartão em volta de si: quem monta é a tela,
          como o Painel fazia. `scroll-margin-top` é o que impede o "rolar até
          a tabela" de parar embaixo da topbar e da tira. */}
      <section className="card ciclo-tabela" ref={refTabela}>
        {carregandoNotas ? (
          <div className="empty-state">Carregando notas…</div>
        ) : dados.erro ? (
          <div className="empty-state">{dados.erro}</div>
        ) : (
          <TabelaDoCiclo
            alunos={dados.alunosOrdenados}
            colunas={dados.colunas}
            notasAluno={dados.notasAluno}
            notasIgnoradas={dados.notasIgnoradas}
            mediasVirtuais={dados.mediasVirtuais}
            mediasPorColuna={dados.mediasPorColuna}
            classificacao={classificacao}
            criterio={classificacaoResp?.criterio ?? null}
            ordenacao={ordenacao}
            nomeDaTurma={nomeDaTurma}
            recolhidos={recolhidos}
            onToggleLimite={
              ordenacao === 'ranking'
                ? (pos) => setRecolhidos((r) => alternarConjunto(r, pos))
                : null
            }
            onEditarNota={(alunoId, simuladoId) => setEmEdicao({ alunoId, simuladoId })}
          />
        )}
      </section>

      {/* A TAREFA das pendências, no destino do elo da chegada. O bloco some
          sozinho quando não há nada pendente — ele consulta e decide. */}
      <div id="pendencias-do-canvas" className="ciclo-ancora">
        <BlocoPendenciasCanvas cicloId={id} canvasEstado={ciclo.canvasEstado ?? null} />
      </div>

      {emEdicao && (
        <DialogoNota
          alunoId={emEdicao.alunoId}
          simuladoId={emEdicao.simuladoId}
          notasPorSim={notasPorSim}
          criterioAtual={classificacaoResp?.criterio ?? null}
          onFechar={salvarNota}
        />
      )}

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

/** Um campo na medida da tira: glifo de 15px, a pergunta e o número vivo. */
function CampoCompacto({
  para, glifo, titulo, resumo,
}: {
  para: string;
  glifo: string;
  titulo: string;
  /** `null` enquanto não há número — o botão continua levando à tela. */
  resumo: string | null;
}) {
  return (
    <Link className="ciclo-tira__campo" to={para}>
      <svg width="15" height="15" viewBox="0 0 70 70" fill="none" stroke="currentColor"
        strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">
        <path d={glifo} />
      </svg>
      {titulo}
      {resumo && <span className="ciclo-tira__resumo">{resumo}</span>}
    </Link>
  );
}

/**
 * O CICLO SEM NENHUMA PROVA APLICADA.
 *
 * Existe de verdade no banco — "Ciclo 1 · IME · 2022" foi criado e ficou sem
 * uso. A tela mostrava quatro travessões, três cards dizendo "ainda não" e uma
 * tabela vazia: quatro buracos, não informação. Um ciclo sem prova tem de
 * dizer O QUE É (não uma consulta que falhou) e O QUE FAZER.
 *
 * QUAIS saídas oferecer é regra, não desenho: mora em
 * `dominio/cicloVazio.ts`, com teste ao lado e o porquê de cada condição. Aqui
 * fica só o que é tela — a explicação do que aconteceu e o desenho do
 * calendário vazio.
 */
function CicloSemProva({ ciclo, ciclos }: { ciclo: Ciclo; ciclos: readonly Ciclo[] }) {
  const { podeAgendar, vizinho } = saidasDoCicloVazio(ciclo, ciclos);

  return (
    <div className="tela">
      <div className="ciclo-vazio">
        <div className="ciclo-vazio__texto">
          <div className="ciclo-identidade__linha">
            <h1 className="ciclo-identidade__nome">{ciclo.nome}</h1>
            {ciclo.vestibularAlvo && (
              <span className="ciclo-identidade__vestibular">{ciclo.vestibularAlvo}</span>
            )}
          </div>
          <p className="ciclo-vazio__olho">Nenhuma prova aplicada</p>
          <h2 className="ciclo-vazio__titulo">Este ciclo existe, mas ninguém fez prova nele</h2>
          <p className="ciclo-vazio__corpo">
            Sem simulado aplicado não há nota, não há média e não há corte a desenhar. Não é uma
            consulta que falhou: o ciclo foi criado e ficou sem uso.
          </p>
          <div className="ciclo-vazio__acoes">
            {podeAgendar && (
              <Link className="btn btn--primary" to="/provas/simulados">
                Agendar a primeira prova
              </Link>
            )}
            {vizinho && (
              <Link className="btn" to={`/ciclos/${vizinho.id}`}>{`Ver ${vizinho.nome}`}</Link>
            )}
          </div>
          <p className="ciclo-vazio__nota">
            Os KPIs, os campos e a tabela não aparecem: quatro travessões e três cards dizendo
            “ainda não” eram quatro buracos, não informação.
          </p>
        </div>

        {/* O calendário sem nenhuma marca — a mesma ideia das três portas
            fechadas do primeiro dia do Painel, no tracejado de `--sas-fio-forte`
            que este sistema usa para "lugar reservado, ainda vazio". */}
        <svg
          className="ciclo-vazio__desenho"
          width="300"
          height="230"
          viewBox="0 0 300 230"
          fill="none"
          role="img"
          aria-label="Calendário de ciclo sem nenhuma prova marcada"
        >
          <rect x="20" y="24" width="260" height="184" rx="14" stroke="var(--sas-borda)" strokeWidth="1.5" />
          <path d="M20 66h260" stroke="var(--sas-borda)" strokeWidth="1.5" />
          <path d="M74 24V10M226 24V10" stroke="var(--sas-borda)" strokeWidth="1.5" strokeLinecap="round" />
          {CASAS_DO_CALENDARIO.map(({ x, y }) => (
            <rect
              key={`${x}-${y}`}
              x={x}
              y={y}
              width="36"
              height="26"
              rx="5"
              stroke="var(--sas-fio-forte)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
          ))}
        </svg>
      </div>
    </div>
  );
}

/**
 * Ficha de nota aberta a partir de uma célula. Fica em componente separado
 * porque precisa cruzar aluno, simulado e as notas da turma para montar a
 * comparação — e o CORTE da matéria, que é o que faz a régua da tela alcançar
 * o diálogo. Sem ele a escala do diálogo desenharia a nota sem a única linha
 * contra a qual ela se lê.
 */
function DialogoNota({
  alunoId, simuladoId, notasPorSim, criterioAtual, onFechar,
}: {
  alunoId: string;
  simuladoId: string;
  notasPorSim: Record<string, Array<{ alunoId: string; nota: number | null; presente?: boolean; acertos?: number | null; total?: number | null }>>;
  criterioAtual: Parameters<typeof corteDaMateria>[0];
  onFechar: (valores: ValoresNota | null) => void;
}) {
  const { data: alunos = [] } = useAlunos();
  const { data: simulados = [] } = useSimulados();

  const aluno = alunos.find((a) => a.id === alunoId);
  const simulado = simulados.find((s) => s.id === simuladoId);
  if (!aluno || !simulado) return null;

  const notas = notasPorSim[simuladoId] ?? [];
  const atual = notas.find((n) => n.alunoId === alunoId);
  const materia = simulado.materia?.codigo ?? null;

  return (
    <FichaNota
      nomeAluno={aluno.nome}
      nomeSimulado={simulado.rotuloCurto || simulado.nome}
      pontuacaoAtual={atual?.acertos ?? null}
      presenteAtual={atual?.presente ?? true}
      notaMaxima={atual?.total ?? simulado.notaMaxima ?? null}
      stats={estatisticasDoSimulado(notas, alunoId)}
      corte={corteDaMateria(criterioAtual, materia)}
      elimina={eliminaSozinho(criterioAtual, materia)}
      onFechar={onFechar}
    />
  );
}

/** Seletor de valor único em pílulas — fase e ordenação. */
function Segmento<V extends string>({
  opcoes, valor, onEscolher,
}: {
  opcoes: Array<{ label: string; value: V }>;
  valor: V;
  onEscolher: (v: V) => void;
}) {
  return (
    <div className="painel-topn">
      {opcoes.map((o) => (
        <button
          key={o.value}
          className={`pill${valor === o.value ? ' is-active' : ''}`}
          aria-pressed={valor === o.value}
          onClick={() => onEscolher(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
