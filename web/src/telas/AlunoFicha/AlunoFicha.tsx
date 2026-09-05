import { useEffect, useMemo, useRef, useState } from 'react';
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
import { descreverSemelhanca } from '../../dominio/alunosParecidos';
import type { TracoDoAluno } from '../../dominio/alunosParecidos';
import {
  lerRecorteDeRevisao, marcarUltimoVisto, montarRevisao,
} from '../../dominio/revisaoEmSequencia';
import type { RevisaoEmSequencia } from '../../dominio/revisaoEmSequencia';
import { decidirCorte, montarEixoCiclos, montarSeries } from '../../dominio/evolucaoAluno';
import { lerSeries } from '../../dominio/leituraDeGrafico';
import {
  useAluno, useAlunosSimilares, useCriteriosDisponiveis, useHeatmapAluno, useMaterias, useSedes,
  useSimulados, useTrajetoriaAluno, useTurmas,
} from '../../hooks/consultas';
import { useEditarNota } from '../../hooks/mutacoes';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import type { AlunoSimilar, Simulado } from '../../tipos/dominio';
import { fmtNota, iniciais } from '../../util/formato';

import {
  exportarCSVHistorico, exportarPDFFicha, exportarPNGGrafico,
  exportarPanoramaPDF, exportarPanoramaPNG,
} from '../../exportacao/exportar-aluno.js';

const PERFIL_LABEL: Record<string, string> = { ancora: 'Âncora', misterio: 'Mistério', regular: 'Regular' };
const TENDENCIA_LABEL: Record<string, string> = { subindo: 'Subindo', estavel: 'Estável', caindo: 'Caindo' };
const ZONA_LABEL: Record<string, string> = { top: 'Zona top', cinzenta: 'Zona cinzenta', risco: 'Zona de risco' };

// O que cada palavra QUER DIZER. As três classificações apareciam como tags
// soltas — "Regular", "Estável", "Zona de Risco" — e nenhuma delas se explica
// sozinha: perfil é a mais sutil e a que menos gente entende.
//
// As frases são a tradução do que o servidor de fato calcula, em
// `api/app/stats/classificacao.py`; mudar a regra lá e não mudar aqui deixa a
// tela explicando uma conta que não é mais feita.
const ZONA_EXPLICA: Record<string, string> = {
  risco: 'a régua da casa corta este aluno',
  cinzenta: 'passa na régua, não passaria numa régua mais dura',
  top: 'passaria mesmo com a régua mais dura',
};
const TENDENCIA_EXPLICA: Record<string, string> = {
  subindo: 'a inclinação das últimas notas sobe, e sobe o bastante para não ser ruído',
  caindo: 'a inclinação das últimas notas cai, e cai o bastante para não ser ruído',
  estavel: 'nenhuma inclinação clara nas últimas notas — o que varia é ruído',
};
const PERFIL_EXPLICA: Record<string, string> = {
  ancora: 'está no topo da turma e varia pouco entre provas',
  misterio: 'varia muito mais que a turma entre provas: a média esconde o que acontece',
  regular: 'varia como a turma varia',
};

/** Ficha individual do aluno: classificações, evolução, histórico, heatmap e similares. */
export function AlunoFicha() {
  const { id = '' } = useParams();
  const navegar = useNavigate();

  const { data: aluno, isPending, isError } = useAluno(id);
  const { data: turmas = [] } = useTurmas();
  const { data: sedes = [] } = useSedes();
  const { data: materias = [] } = useMaterias();
  const { data: trajetoria = [], isPending: trajetoriaPendente } = useTrajetoriaAluno(id);
  const { data: heat } = useHeatmapAluno(id);
  const { data: similares = [] } = useAlunosSimilares(id);
  const { data: todosSimulados = [], isPending: simuladosPendentes } = useSimulados();

  const editarNota = useEditarNota();

  const [filtro, setFiltro] = useState<FiltroSimulados>(FILTRO_VAZIO);
  const [emEdicao, setEmEdicao] = useState<{ simulado: Simulado; nota: number | null } | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');

  // O exportador de PNG precisa do SVG vivo do gráfico, não de uma re-render.
  const refGrafico = useRef<HTMLDivElement>(null);

  // A REVISÃO EM SEQUÊNCIA. Lido UMA vez, na montagem: dentro da ficha o
  // recorte não muda — quem o troca é a lista, e voltar para ela desmonta esta
  // tela. Reler a cada aluno da sequência só gastaria acesso ao storage.
  const [recorte] = useState(lerRecorteDeRevisao);
  const revisao = useMemo(() => montarRevisao(recorte, id), [recorte, id]);

  // Onde a lista deve cair na volta: a linha de onde se saiu, não só a URL.
  useEffect(() => marcarUltimoVisto(id), [id]);

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
  // desenhar o corte errado em metade dos pontos. O motivo está ESCRITO na
  // tela, ao lado do nome da régua: ausência de controle sem explicação lê
  // como funcionalidade esquecida.
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

  // Vinte alunos, vinte teclas. O atalho existe porque a tarefa é repetir a
  // MESMA leitura vinte vezes — obrigar o mouse a achar a seta a cada volta é
  // metade do custo que a sequência veio resolver.
  useEffect(() => {
    if (!revisao) return;
    function aoTeclar(ev: KeyboardEvent) {
      if (ev.defaultPrevented || ev.altKey || ev.ctrlKey || ev.metaKey) return;
      // O gráfico em camadas usa ←/→ dentro do próprio `tablist`, e campo de
      // texto usa para mover o cursor: quem está lá dentro manda.
      const alvo = ev.target as HTMLElement | null;
      if (alvo?.closest?.('input, textarea, select, [contenteditable="true"], [role="tablist"]')) return;
      // ⚠️ Diálogo aberto trava a sequência. Os diálogos deste produto são
      // portais no `<body>` — `closest` no alvo não os alcança —, e sem este
      // guarda uma seta trocaria de aluno por baixo da edição de nota (a nota
      // digitada some) ou da confirmação de remover a foto (o diálogo some com
      // a tela que o abriu, e o clique seguinte cai em outro aluno).
      if (document.querySelector('.dialog-overlay')) return;
      const destino = ev.key === 'ArrowLeft' ? revisao?.anterior
        : ev.key === 'ArrowRight' ? revisao?.proximo
        : null;
      if (!destino) return;
      ev.preventDefault();
      navegar(`/alunos/${destino}`);
    }
    window.addEventListener('keydown', aoTeclar);
    return () => window.removeEventListener('keydown', aoTeclar);
  }, [revisao, navegar]);

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

  // "Sem simulado nenhum" é a chegada de todo aluno novo, e não é o mesmo que
  // "ainda não carregou": enquanto a trajetória vem, a tela não pode afirmar
  // ausência (regra 5 — nunca "0" no lugar de "não sei").
  const historicoCarregando = trajetoriaPendente || simuladosPendentes;
  const semHistorico = !historicoCarregando && simuladosDoAluno.length === 0;

  const ciclosAcompanhados = new Set(simuladosDoAluno.map((s) => s.cicloId)).size;
  const ultimoCiclo = aluno.medias?.ultimoCiclo;
  const voltaPara = revisao?.volta ?? '/alunos';

  return (
    // A ficha é TELA DE LEITURA, e por isso ganha a coluna lateral de 320px
    // com o contexto que vivia espalhado pelo cabeçalho: a régua em vigor,
    // onde o aluno está contra ela, as classificações e as ações. As telas de
    // VARREDURA — painel, alunos, banco — não têm: lá a tabela tem 14 colunas,
    // e 320px do lado direito saem direto da tarefa mais frequente do dia
    // (docs/brief-claude-design-coordenacao.md §A arquitetura).
    //
    // ⚠️ As duas colunas ficam de pé TAMBÉM no estado sem histórico. Numa
    // revisão em sequência, um aluno sem prova no meio da fila mudaria a
    // largura do texto e o lugar de cada peça — a tela inteira dançaria a cada
    // seta, e o olho recomeçaria a leitura do zero no aluno seguinte.
    <div className="tela ficha-duas-colunas">
      <div className="ficha-coluna">
        <header className="ficha-cabeca">
          <Link
            className="ficha-cabeca__voltar aluno-ficha__nao-imprimir"
            to={voltaPara}
            aria-label={revisao ? 'Voltar para o recorte em Alunos' : 'Voltar para Alunos'}
          >
            {/* Chevron, não seta: seta promete desfazer, chevron diz subir um
                nível — e é isto que ele faz (padrão de campo, C4). */}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M14 6l-6 6 6 6" />
            </svg>
          </Link>

          <Avatar tipo="aluno" id={aluno.id} nome={aluno.nome} temFoto={aluno.temFoto}
            className="avatar avatar--grande" />

          <div className="ficha-cabeca__quem">
            <div className="ficha-cabeca__id">{aluno.id}</div>
            <h1 className="ficha-cabeca__nome">{aluno.nome}</h1>
            <p className="ficha-cabeca__onde">
              {`${turma?.nome ?? '—'} · ${sede?.nome ?? '—'} · alvos: ${alvos}`}
            </p>
          </div>

          {revisao && <BarraDeRevisao revisao={revisao} />}

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
        </header>

        {erroSalvar && <div className="agendar__erro">{erroSalvar}</div>}

        {semHistorico ? (
          <SemSimuladoNenhum nome={aluno.nome} voltaPara={voltaPara} temRecorte={!!revisao} />
        ) : (
          <>
            {/* A faixa de filtros não é peça: é o recorte das duas peças
                abaixo. Card próprio a punha no mesmo peso do gráfico. */}
            <div className="ficha-recorte aluno-ficha__nao-imprimir">
              <SimFiltros
                opcoes={opcoes}
                filtro={filtro}
                contagens={contagens}
                onToggle={alternar}
                onLimpar={() => setFiltro(FILTRO_VAZIO)}
              />
            </div>

            {/* A PEÇA PRIMÁRIA da coluna. Onze superfícies com a mesma borda,
                o mesmo raio e o mesmo peso viravam listra numa tela de leitura
                longa: a hierarquia agora está na SUPERFÍCIE — preenchida e com
                borda de tema para o que domina, contorno fino e fundo do papel
                para o que apoia (a prancheta "Alunos", tela `ficha`). */}
            <section className="ficha-peca ficha-peca--primaria">
              {/* O título é o OLHO da peça, e não o `titulo` do gráfico em
                  camadas: dois blocos vizinhos com dois desenhos de título
                  diferentes é o mesmo defeito de hierarquia, um degrau abaixo. */}
              <h2 className="ficha-olho">Evolução do aluno</h2>
              <GraficoEmCamadas
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
            </section>

            <section className="ficha-peca ficha-peca--tabela">
              <div className="ficha-peca__cabeca ficha-peca__cabeca--faixa">
                <h2 className="ficha-olho">Histórico de simulados</h2>
                <span className="ficha-peca__nota">
                  {`${filtrados.length} de ${simuladosDoAluno.length} · a nota abre a edição`}
                </span>
              </div>
              {/* A rolagem horizontal é da TABELA, nunca do corpo da página:
                  a 390px as colunas não cabem, e o corpo rolando de lado leva
                  junto o cabeçalho e a coluna lateral. */}
              <div className="ficha-tabela">
                <TabelaSimulados
                  simulados={filtrados}
                  notasAluno={notasPorSimulado}
                  compacto
                  onEditarNota={(simulado, nota) => setEmEdicao({ simulado, nota })}
                />
              </div>
            </section>

            <section className="ficha-peca aluno-ficha__nao-imprimir">
              <h2 className="ficha-olho">Matérias × simulados</h2>
              <GraficoEmCamadas
                legenda="Célula cheia = acima do corte, e quanto mais forte, mais folga; célula vazada = abaixo. Cobre todo o histórico do aluno (independente dos filtros acima)."
                // O heatmap não tem insight de LLM por trás — não existe recorte
                // em `insight_ciclo` que corresponda a "este aluno, todas as
                // matérias". A camada aparece vazia, com a mensagem que o
                // `InsightsPainel` já dá nesse caso, em vez de sumir: o degrau
                // sumindo em um gráfico e não em outro é pior que o degrau vazio.
                frase={null}
                grafico={() => <Heatmap payload={heat} notaMaxima={10} corte={corte?.valor ?? null} />}
              />
            </section>
          </>
        )}
      </div>

      {/* A COLUNA LATERAL, 320px. O contexto que estava espalhado pelo
          cabeçalho e pelo fim da rolagem: onde o aluno está contra a régua,
          as classificações como PALAVRA, e o acesso. */}
      <aside className="ficha-lateral aluno-ficha__nao-imprimir">
        {!semHistorico && (
          <section className="ficha-peca ficha-peca--primaria">
            <div className="ficha-peca__cabeca">
              <h2 className="ficha-olho">Onde ele está</h2>
              <span className="ficha-peca__nota">
                {reguaAtiva ? `régua ${reguaAtiva.nome}` : 'régua indisponível'}
              </span>
            </div>
            {/* A MESMA peça que o aluno vê de si mesmo, e é de propósito: é
                aqui que a coerência entre os dois produtos fica evidente. */}
            <BarraCorte materias={materiasContraCorte} />
            {/* O motivo VISÍVEL de não haver seletor de régua aqui. A ficha
                imprimia só o nome da régua, e controle ausente sem explicação
                lê como funcionalidade esquecida — ou pior, como se a escolha
                não importasse, quando ela muda toda a leitura da tela. */}
            <p className="ficha-porque">
              Esta tela não escolhe a régua, e é de propósito: a evolução mistura
              ciclos de ITA e de IME, e fixar um edital desenharia o corte errado
              em metade dos pontos. O corte em ouro é o da régua da casa
              {reguaAtiva ? `, ${reguaAtiva.nome}` : ''} — a mesma contra a qual o
              aluno se vê na área dele.
            </p>
          </section>
        )}

        {/* ⚠️ Sem prova, as três viram travessão — e NÃO a palavra que o
            servidor devolveu. O classificador tem fallback ("cinzenta",
            "estável", "regular") para quem ainda não tem nota, e imprimir
            "Zona cinzenta" ao lado de "sem nota, sem zona" seria a tela
            afirmando um comportamento que ninguém observou. */}
        <section className="ficha-peca">
          <h2 className="ficha-olho">Como ele se comporta</h2>
          <dl className="ficha-classificacoes">
            <Classificacao
              rotulo="Zona"
              valor={semHistorico ? '—' : ZONA_LABEL[aluno.zona] || aluno.zona}
              explica={semHistorico ? 'sem nota, sem zona' : ZONA_EXPLICA[aluno.zona]}
            />
            <Classificacao
              rotulo="Tendência"
              valor={semHistorico ? '—' : TENDENCIA_LABEL[aluno.tendencia] || aluno.tendencia}
              explica={semHistorico
                ? 'precisa de mais de um ciclo para existir'
                : TENDENCIA_EXPLICA[aluno.tendencia]}
            />
            <Classificacao
              rotulo="Perfil"
              valor={semHistorico ? '—' : PERFIL_LABEL[aluno.perfil] || aluno.perfil}
              explica={semHistorico
                ? 'precisa de provas para existir'
                : PERFIL_EXPLICA[aluno.perfil]}
            />
          </dl>
        </section>

        {!semHistorico && (
          <AlunosParecidos
            similares={similares}
            alvo={{
              perfil: aluno.perfil, tendencia: aluno.tendencia,
              zona: aluno.zona, media: aluno.media,
            }}
          />
        )}

        {/* Era "Métricas internas" — e o nome era a confissão. Os três números
            eram "Média recente", "Notas no histórico" e "Janela: 9", que é o
            tamanho do vetor da sparkline: detalhe de implementação exposto
            como informação. O que sobrou diz o que os números desta tela
            COBREM, que é a pergunta que alguém de fato tem ao ler uma ficha. */}
        <section className="ficha-peca">
          <h2 className="ficha-olho">O que estes números cobrem</h2>
          <p className="ficha-peca__nota ficha-peca__nota--bloco">
            Todo o histórico do aluno, independente dos filtros da coluna ao lado.
          </p>
          <div className="kpi-grid">
            <Kpi
              rotulo="Simulados no histórico"
              valor={historicoCarregando ? null : simuladosDoAluno.length}
            />
            <Kpi
              rotulo="Ciclos acompanhados"
              valor={historicoCarregando ? null : ciclosAcompanhados}
            />
            <Kpi
              // O rótulo do último ciclo vem do servidor (`referencia`), que é
              // quem escolheu o ciclo. Sem ele, o número que sobra é a média
              // recente — e a etiqueta diz isso, em vez de emprestar o nome do
              // ciclo a um número que não é dele.
              rotulo={ultimoCiclo?.referencia ? `Média · ${ultimoCiclo.referencia}` : 'Média recente'}
              valor={fmtNota(ultimoCiclo?.referencia ? ultimoCiclo.geral : aluno.media)}
            />
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

/**
 * A barra de revisão: onde este aluno está dentro do recorte que a pessoa
 * montou na lista, e as duas teclas para andar nele.
 *
 * Não aparece para quem chegou pela busca ou por link salvo (`montarRevisao`
 * devolve `null`): anunciar "aluno 1 de 1" prometeria uma sequência que não
 * existe.
 */
function BarraDeRevisao({ revisao }: { revisao: RevisaoEmSequencia }) {
  const seta = (dir: 'anterior' | 'proximo') => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={dir === 'anterior' ? 'M14 6l-6 6 6 6' : 'M10 6l6 6-6 6'} />
    </svg>
  );

  // Fim de fila é BOTÃO desabilitado, não `<Link>` desligado: link que não
  // navega é a promessa quebrada mais barata de escrever e a mais cara de
  // descobrir. A seta continua no lugar — some-la faria a barra encolher
  // justamente no aluno em que a pessoa precisa perceber que terminou —, e o
  // rótulo diz por que ela não anda.
  const passo = (dir: 'anterior' | 'proximo', destino: string | null, rotulo: string) =>
    destino ? (
      <Link className="ficha-revisao__passo" to={`/alunos/${destino}`} aria-label={rotulo}>
        {seta(dir)}
      </Link>
    ) : (
      <button type="button" className="ficha-revisao__passo" disabled
        aria-label={`${rotulo} — não há: este é o ${dir === 'anterior' ? 'primeiro' : 'último'} do recorte`}>
        {seta(dir)}
      </button>
    );

  return (
    <div className="ficha-revisao aluno-ficha__nao-imprimir">
      <div className="ficha-revisao__texto">
        <span className="ficha-olho">Revisando o recorte</span>
        <span className="ficha-revisao__posicao">{`${revisao.posicao} · ${revisao.rotulo}`}</span>
      </div>
      {passo('anterior', revisao.anterior, 'Aluno anterior do recorte')}
      {passo('proximo', revisao.proximo, 'Próximo aluno do recorte')}
    </div>
  );
}

/** Uma classificação: a palavra, e o que ela quer dizer. */
function Classificacao({ rotulo, valor, explica }: { rotulo: string; valor: string; explica?: string }) {
  return (
    <div className="ficha-classificacao">
      <dt className="ficha-classificacao__rotulo">{rotulo}</dt>
      <dd className="ficha-classificacao__valor">
        {valor}
        {explica && <span className="ficha-classificacao__explica">{explica}</span>}
      </dd>
    </div>
  );
}

/**
 * O estado de chegada de todo aluno novo — e ele é ESTADO, não uma sequência
 * de peças vazias.
 *
 * Antes, o gráfico, o heatmap e a barra de corte apareciam os três sem nada
 * dentro, e três vazios seguidos leem como falha do sistema. Aqui a tela diz o
 * que houve: não é desempenho ruim, é ausência de dado.
 *
 * ⚠️ Nada de data de matrícula nem de "o primeiro simulado é dia 12/09": a
 * ficha não recebe nem uma coisa nem outra do servidor, e a prancheta as tem
 * porque mock inventa. O convite é a agenda de provas, que existe.
 */
function SemSimuladoNenhum(
  { nome, voltaPara, temRecorte }: { nome: string; voltaPara: string; temRecorte: boolean },
) {
  // 24 células tracejadas: a grade de matérias por ciclo, sem uma preenchida.
  // Desenha a ausência com a MESMA forma que o heatmap usa para o vazado (R1),
  // então quem já leu a tela cheia entende esta sem legenda.
  const celulas = Array.from({ length: 24 }, (_, k) => ({
    x: 10 + (k % 6) * 38, y: 14 + Math.floor(k / 6) * 34,
  }));

  return (
    <section className="ficha-peca ficha-peca--primaria ficha-vazia">
      <div className="ficha-vazia__texto">
        <h2 className="ficha-olho">Sem simulado nenhum</h2>
        <p className="ficha-vazia__titulo">{`${nome} ainda não fez prova`}</p>
        <p className="ficha-vazia__corpo">
          Sem nota não há média, trajetória, corte nem zona — não é desempenho
          ruim, é ausência de dado. As classificações ao lado ficam vazias pelo
          mesmo motivo, e passam a existir sozinhas quando a primeira prova for
          lançada.
        </p>
        <div className="ficha-vazia__acoes">
          <Link className="btn btn--primary" to="/provas/simulados">Ver a agenda de provas</Link>
          <Link className="btn btn--ghost" to={voltaPara}>
            {temRecorte ? 'Voltar ao recorte' : 'Voltar para Alunos'}
          </Link>
        </div>
      </div>
      <svg className="ficha-vazia__grade" width="240" height="150" viewBox="0 0 240 150" fill="none"
        role="img" aria-label="Grade de matérias por ciclo, sem nenhuma célula preenchida">
        {celulas.map((c) => (
          <rect key={`${c.x}-${c.y}`} x={c.x} y={c.y} width="34" height="22" rx="4"
            stroke="var(--sas-fio-forte)" strokeWidth="1" strokeDasharray="3 3" />
        ))}
      </svg>
    </section>
  );
}

/**
 * "Alunos com desempenho parecido" — a antiga "Perfis semelhantes".
 *
 * O que mudou é a LÍNGUA, não o dado: o subtítulo dizia "kNN por vetor de
 * features (média por matéria + desvio + tendência)" e a primeira coluna era
 * "Distância: 0,42". A distância continua mandando — ela é a ORDEM da lista
 * (R6) —, mas sai da tela: quem está mais acima é mais parecido, e o número
 * cru não ajuda ninguém a decidir chamar um aluno para conversar.
 *
 * ⚠️ Não vira card de recomendação. "Estes se parecem com ele" é uma
 * afirmação sobre os números; "faça o que funcionou com eles" seria
 * causalidade que este produto não mede.
 */
function AlunosParecidos({ similares, alvo }: { similares: AlunoSimilar[]; alvo: TracoDoAluno }) {
  return (
    <section className="ficha-peca aluno-ficha__nao-imprimir">
      <h2 className="ficha-olho">Alunos com desempenho parecido</h2>

      {similares.length === 0 ? (
        <p className="ficha-peca__nota ficha-peca__nota--bloco">
          Ainda não há histórico suficiente para comparar: com pouquíssimas provas,
          qualquer semelhança é coincidência.
        </p>
      ) : (
        <>
          <p className="ficha-peca__nota ficha-peca__nota--bloco">
            Notas por matéria e oscilação parecidas com as dele nos últimos ciclos, o
            mais parecido primeiro. Serve para ver o que aconteceu com quem estava no
            mesmo lugar — não é receita: o que funcionou com eles pode não valer aqui.
          </p>
          {/* O número da direita PRECISA de nome. Cada linha já diz "média 0,3
              acima" — que é relativo a este aluno —, e um segundo número, em
              negrito, sem etiqueta, na mesma linha, é convite a ler um como o
              outro. Pior: era exatamente aqui que ficava a "Distância: 0,42".
              O rótulo aparece uma vez para o olho e uma vez por linha para o
              leitor de tela, que não associa cabeçalho a item de lista. */}
          <p className="ficha-parecidos__legenda ficha-olho">Média geral</p>
          <ul className="ficha-parecidos">
            {similares.map((s) => {
              const semelhanca = descreverSemelhanca(alvo, s);
              return (
                <li key={s.alunoId}>
                  <Link className="ficha-parecido" to={`/alunos/${s.alunoId}`}>
                    {/* Duas letras, nunca foto: a ficha imprime e exporta, e o
                        que sai daqui pode virar papel na mesa de alguém. */}
                    <span className="ficha-parecido__iniciais" aria-hidden="true">{iniciais(s.nome)}</span>
                    <span className="ficha-parecido__quem">
                      <span className="ficha-parecido__nome">{s.nome}</span>
                      {semelhanca && <span className="ficha-parecido__semelhanca">{semelhanca}</span>}
                    </span>
                    <span className="ficha-parecido__media">
                      <span className="ficha-so-leitor">média geral </span>
                      {fmtNota(s.media)}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
