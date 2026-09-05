import { useEffect, useMemo, useRef, useState } from 'react';

import { Kpi } from '../../componentes/ui/Kpi';
import { EdicaoCriterio } from '../../componentes/dialogos/EdicaoCriterio';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { BarraFiltros, Busca, Pills, PillsUnica } from '../../componentes/ui/filtros/BarraFiltros';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import {
  RECORTE_VAZIO, cicloPadrao, ciclosNoRecorte, contagensDoRecorte, recorteCompleto, rotuloDoCiclo,
} from '../../dominio/painelFiltros';
import type { RecortePainel } from '../../dominio/painelFiltros';
import { FichaNota } from '../../componentes/dialogos/FichaNota';
import type { ValoresNota } from '../../componentes/dialogos/formularioNota';
import { FaixaDecisao } from './FaixaDecisao';
import { TabelaPainel } from './TabelaPainel';
import {
  estatisticasDoSimulado, montarPainel, nomeSede, normMateria,
} from '../../dominio/painel';
import {
  useAlunos, useCiclos, useClassificacaoCiclo, useCriteriosDisponiveis, useNotasDoCiclo,
  useSedes, useSimulados, useTurmas,
} from '../../hooks/consultas';
import { useEditarNota } from '../../hooks/mutacoes';
import { useRecorteDaTela } from '../../componentes/layout/migalhas';
import { fmtNota } from '../../util/formato';
import type { OrdenacaoPainel } from '../../dominio/painel';
import type { AlunoClassificado, CriterioClassificacao } from '../../tipos/dominio';

// Painel — a tabela alunos × matérias/fases de um ciclo.
//
// A lógica de colunas, médias e ranking vive em `dominio/painel.ts`; aqui fica
// só o estado da tela (ciclo, filtros, busca, ordenação) e o desenho.

export function Painel() {
  const { data: ciclos = [] } = useCiclos();
  const { data: alunos = [] } = useAlunos();
  const { data: simulados = [] } = useSimulados();
  const { data: sedes = [] } = useSedes();
  const { data: turmas = [] } = useTurmas();

  const [cicloId, setCicloId] = useState<string | null>(null);
  // Ano e vestibular estreitam a fileira de ciclos, e nascem com TUDO marcado
  // (decisão do Yan, 03/09) — o recorte inteiro é o estado neutro.
  const [recorte, setRecorte] = useState<RecortePainel>(RECORTE_VAZIO);
  const [sedeIds, setSedeIds] = useState<ReadonlySet<string>>(new Set());
  const [turmaIds, setTurmaIds] = useState<ReadonlySet<string>>(new Set());
  const [busca, setBusca] = useState('');
  // R6 · a tabela ABRE pela distância do corte, ascendente — o pior primeiro.
  // É o que substitui a cor como mecanismo de varredura, e é por isso que ele
  // é o padrão e não mais uma opção na lista.
  const [ordenacao, setOrdenacao] = useState<OrdenacaoPainel>('distancia');
  const [fase, setFase] = useState<'1' | '2'>('1');
  // A régua do corte. 'tio-leo' é a pedagógica do colégio; ITA/IME seguem o edital.
  const [criterio, setCriterio] = useState('tio-leo');
  const [recolhidos, setRecolhidos] = useState<ReadonlySet<number>>(new Set());
  const [emEdicao, setEmEdicao] = useState<{ alunoId: string; simuladoId: string } | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');
  const [criandoRegua, setCriandoRegua] = useState(false);

  const editarNota = useEditarNota();

  // Semeia UMA vez, quando os ciclos chegam. Semear a cada render desfaria o
  // que o coordenador acabou de desmarcar.
  const jaSemeou = useRef(false);
  useEffect(() => {
    if (jaSemeou.current || ciclos.length === 0) return;
    jaSemeou.current = true;
    setRecorte(recorteCompleto(ciclos));
  }, [ciclos]);

  const todasAsOpcoes = useMemo(() => recorteCompleto(ciclos), [ciclos]);
  const anosOrdenados = useMemo(
    () => [...todasAsOpcoes.anos].sort((a, b) => b - a),
    [todasAsOpcoes],
  );
  const vestibularesOrdenados = useMemo(
    () => [...todasAsOpcoes.vestibulares].sort(),
    [todasAsOpcoes],
  );
  const ciclosVisiveis = useMemo(() => ciclosNoRecorte(ciclos, recorte), [ciclos, recorte]);
  const contagens = useMemo(() => contagensDoRecorte(ciclos, recorte), [ciclos, recorte]);

  // O ciclo escolhido pode ter saído da fileira quando o recorte mudou; aí a
  // tela cai no default do recorte novo em vez de apontar para um ciclo que
  // não está mais visível. Antes disto o Painel abria em `ciclos[0]`, que é o
  // primeiro dos TRÊS ciclos com `ordem = 1` — e qual dos três não estava
  // definido (docs/32 §3.1).
  const cicloAtivo = useMemo(
    () => ciclosVisiveis.find((c) => c.id === cicloId) ?? cicloPadrao(ciclosVisiveis, simulados),
    [ciclosVisiveis, cicloId, simulados],
  );
  const { data: notasPorSim = {}, isPending: carregandoNotas } = useNotasDoCiclo(cicloAtivo, simulados);
  const { data: criterios = [] } = useCriteriosDisponiveis();
  // Veredito, motivo, cor e posição vêm do servidor (docs/18 §1.2). A fase
  // exibida manda: a régua do colégio vale para qualquer fase; as do edital
  // já sabem a sua.
  const { data: classificacaoResp } = useClassificacaoCiclo(
    cicloAtivo?.id ?? null, criterio, fase === '1' ? 1 : 2,
  );
  const classificacao = useMemo(() => {
    const porAluno: Record<string, AlunoClassificado> = {};
    for (const a of classificacaoResp?.alunos ?? []) porAluno[a.alunoId] = a;
    return porAluno;
  }, [classificacaoResp]);

  // O que o assistente precisa saber para "e a Física?" ter referente. É o
  // Painel que declara porque estes filtros vivem em `useState` e não na URL.
  useRecorteDaTela(useMemo(() => ({
    cicloId: cicloAtivo?.id,
    fase: fase === '1' ? (1 as const) : (2 as const),
    criterio,
    sedeIds: [...sedeIds],
    turmaIds: [...turmaIds],
    anos: [...recorte.anos],
    vestibulares: [...recorte.vestibulares],
  }), [cicloAtivo?.id, fase, criterio, sedeIds, turmaIds, recorte]));

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
      ciclo: cicloAtivo,
      simulados,
      alunos: alunosFiltrados,
      notasPorSim,
      fase,
      ordenacao,
      classificacao,
      criterio: classificacaoResp?.criterio ?? null,
    }),
    [
      cicloAtivo, simulados, alunosFiltrados, notasPorSim, fase, ordenacao, classificacao,
      classificacaoResp?.criterio,
    ],
  );

  // A fase escolhida pode não existir no ciclo novo — segue a que sobrou.
  useEffect(() => {
    if (dados.faseSelecionada !== fase) setFase(dados.faseSelecionada);
  }, [dados.faseSelecionada, fase]);

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

  function alternarConjunto<V>(set: ReadonlySet<V>, valor: V): ReadonlySet<V> {
    const novo = new Set(set);
    if (novo.has(valor)) novo.delete(valor);
    else novo.add(valor);
    return novo;
  }

  const resumo = dados.resumo;

  return (
    <div className="tela">
      <BarraFiltros
        tela="painel"
        algumAtivo={
          sedeIds.size > 0 ||
          turmaIds.size > 0 ||
          recorte.anos.size !== todasAsOpcoes.anos.size ||
          recorte.vestibulares.size !== todasAsOpcoes.vestibulares.size
        }
        // Nesta faixa "limpar" é voltar para TUDO marcado, não para vazio:
        // com os dois eixos nascendo cheios, o vazio não é o estado neutro —
        // é a fileira de ciclos sem nenhum ciclo.
        onLimpar={() => {
          setSedeIds(new Set());
          setTurmaIds(new Set());
          setRecorte(recorteCompleto(ciclos));
        }}
        grupos={[
          {
            chave: 'ano', rotulo: 'Ano letivo',
            resumo: resumirSelecao(
              recorte.anos,
              anosOrdenados.map((a) => ({ valor: a, label: String(a) })),
              'ano', 'anos',
            ),
            corpo: (
              <Pills
                opcoes={anosOrdenados.map((ano) => ({
                  valor: ano,
                  label: String(ano),
                  contagem: contagens.porAno.get(ano) ?? 0,
                }))}
                selecionados={recorte.anos}
                onToggle={(ano) =>
                  setRecorte((r) => ({ ...r, anos: alternarConjunto(r.anos, ano) }))}
              />
            ),
          },
          {
            chave: 'vestibular', rotulo: 'Vestibular',
            resumo: resumirSelecao(
              recorte.vestibulares,
              vestibularesOrdenados.map((v) => ({ valor: v, label: v })),
              'vestibular', 'vestibulares',
            ),
            corpo: (
              <Pills
                opcoes={vestibularesOrdenados.map((v) => ({
                  valor: v,
                  label: v,
                  contagem: contagens.porVestibular.get(v) ?? 0,
                }))}
                selecionados={recorte.vestibulares}
                onToggle={(v) =>
                  setRecorte((r) => ({ ...r, vestibulares: alternarConjunto(r.vestibulares, v) }))}
              />
            ),
          },
          {
            chave: 'ciclo', rotulo: 'Ciclo',
            // O nome inteiro, e não o rótulo curto da pílula: colapsada, a faixa
            // perde o contexto que o recorte dava, e "4" sozinho não diz de
            // que ano nem de que vestibular.
            resumo: cicloAtivo?.nome ?? null,
            corpo: (
              <PillsUnica
                opcoes={ciclosVisiveis.map((c) => ({
                  valor: c.id,
                  label: rotuloDoCiclo(c, recorte),
                }))}
                selecionado={cicloAtivo?.id ?? null}
                onSelecionar={(id) => {
                  setCicloId(id);
                  setBusca('');
                }}
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
                onToggle={(id) => setSedeIds((s) => alternarConjunto(s, id))}
              />
            ),
          },
          {
            chave: 'busca', rotulo: 'Aluno',
            resumo: resumirTexto(busca),
            corpo: (
              <Busca
                valor={busca}
                onChange={setBusca}
                placeholder="Buscar aluno…"
                rotulo="Buscar aluno na tabela"
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
                onToggle={(id) => setTurmaIds((s) => alternarConjunto(s, id))}
              />
            ),
          },
        ]}
      />

      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">Panorama geral</h1>
          <p className="tela-subtitulo">
            {cicloAtivo ? cicloAtivo.nome : 'Escolha um ciclo na faixa de filtros.'}
          </p>
        </div>

        <div className="painel-header__controles">
          <BotaoAjuda criterio={classificacaoResp?.criterio ?? null} />
          <Segmento
            opcoes={[
              { label: 'Pior primeiro', value: 'distancia' as const },
              { label: 'Ranking', value: 'ranking' as const },
              { label: 'A–Z', value: 'alfabetica' as const },
            ]}
            valor={ordenacao}
            onEscolher={setOrdenacao}
          />
          {dados.fasesDisponiveis.length >= 2 && (
            <Segmento
              opcoes={dados.fasesDisponiveis.map((f) => ({
                label: f === '1' ? '1ª Fase' : '2ª Fase',
                value: f,
              }))}
              valor={dados.faseSelecionada}
              onEscolher={setFase}
            />
          )}
          <SeletorCriterio
            criterios={criterios}
            valor={criterio}
            onEscolher={setCriterio}
            onCriar={() => setCriandoRegua(true)}
          />
        </div>
      </div>

      {erroSalvar && <div className="agendar__erro">{erroSalvar}</div>}

      {cicloAtivo && (
        <FaixaDecisao
          alunosNoRecorte={dados.alunosOrdenados}
          classificacao={classificacao}
          recorteAtivo={sedeIds.size > 0 || turmaIds.size > 0 || busca.trim() !== ''}
          nomeCriterio={classificacaoResp?.criterio.nome ?? null}
        />
      )}

      {resumo && (
        <div className="kpi-grid kpi-grid--cartoes">
          <Kpi rotulo="Alunos no ciclo" valor={resumo.totalAlunos} />
          <Kpi rotulo="Simulados aplicados" valor={resumo.totalSimulados} />
          {/* Sem tom, e é decisão (R7): a TABELA abaixo é que carrega a
              leitura da tela, e duas escalas semânticas ao mesmo tempo é o
              mesmo que nenhuma.

              A "Média geral" tinha um ternário fixo — verde ≥7, âmbar ≥5 —
              sem relação nenhuma com o corte em uso, enquanto a célula logo
              abaixo usava o corte de verdade: o MESMO número podia estar
              verde em cima e vermelho embaixo. Não foi substituído por outra
              função de cor porque não sobra cor para ele. */}
          <Kpi rotulo="Média geral" valor={fmtNota(resumo.mediaGeral)} />
          <Kpi
            rotulo={`Cortados · ${classificacaoResp?.criterio.nome ?? '…'}`}
            valor={resumo.cortados ?? '…'}
            sufixo={` de ${resumo.totalAlunos}`}
          />
        </div>
      )}

      <section className="card">
        {carregandoNotas ? (
          <div className="empty-state">Carregando notas…</div>
        ) : dados.erro ? (
          <div className="empty-state">{dados.erro}</div>
        ) : (
          <TabelaPainel
            alunos={dados.alunosOrdenados}
            colunas={dados.colunas}
            notasAluno={dados.notasAluno}
            notasIgnoradas={dados.notasIgnoradas}
            mediasVirtuais={dados.mediasVirtuais}
            mediasPorColuna={dados.mediasPorColuna}
            classificacao={classificacao}
            criterio={classificacaoResp?.criterio ?? null}
            ordenacao={ordenacao}
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

      {emEdicao && (
        <DialogoNota
          alunoId={emEdicao.alunoId}
          simuladoId={emEdicao.simuladoId}
          notasPorSim={notasPorSim}
          onFechar={salvarNota}
        />
      )}

      {criandoRegua && (
        <EdicaoCriterio
          cicloId={cicloAtivo?.id ?? null}
          fase={fase === '1' ? 1 : 2}
          onFechar={() => setCriandoRegua(false)}
          onSalvo={(slug) => {
            setCriandoRegua(false);
            // Já entra em uso: quem acabou de descrever a régua quer vê-la
            // aplicada, não procurá-la no seletor.
            setCriterio(slug);
          }}
        />
      )}
    </div>
  );
}

/**
 * Ficha de nota aberta a partir de uma célula. Fica em componente separado
 * porque precisa cruzar aluno, simulado e as notas da turma para montar a
 * comparação.
 */
function DialogoNota({
  alunoId, simuladoId, notasPorSim, onFechar,
}: {
  alunoId: string;
  simuladoId: string;
  notasPorSim: Record<string, Array<{ alunoId: string; nota: number | null; presente?: boolean; acertos?: number | null; total?: number | null }>>;
  onFechar: (valores: ValoresNota | null) => void;
}) {
  const { data: alunos = [] } = useAlunos();
  const { data: simulados = [] } = useSimulados();

  const aluno = alunos.find((a) => a.id === alunoId);
  const simulado = simulados.find((s) => s.id === simuladoId);
  if (!aluno || !simulado) return null;

  const notas = notasPorSim[simuladoId] ?? [];
  const atual = notas.find((n) => n.alunoId === alunoId);

  return (
    <FichaNota
      nomeAluno={aluno.nome}
      nomeSimulado={simulado.rotuloCurto || simulado.nome}
      pontuacaoAtual={atual?.acertos ?? null}
      presenteAtual={atual?.presente ?? true}
      notaMaxima={atual?.total ?? simulado.notaMaxima ?? null}
      stats={estatisticasDoSimulado(notas, alunoId)}
      onFechar={onFechar}
    />
  );
}

/** Seletor de valor único em pílulas — ordenação e fase. */
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

function descreverMinimo(p: CriterioClassificacao['predicados'][number]): string {
  if (typeof p.minimo === 'number') return fmtNota(p.minimo);
  return `${p.minimo.acertos} de ${p.minimo.de} acertos`;
}

/**
 * Legenda gerada a partir do critério — nunca de um número fixo. Foi um "4,0
 * em vermelho" com legenda dizendo "< 5,0" que expôs a régua duplicada.
 */
function LegendaCriterio({ criterio }: { criterio: CriterioClassificacao | null }) {
  if (!criterio) return null;
  const regra = criterio.combinador === 'todos'
    ? 'cortado quando TODOS os requisitos falham'
    : 'cortado quando QUALQUER requisito falha';
  return (
    <>
      <p className="painel-help-titulo">{criterio.nome} — {regra}</p>
      <ul className="painel-help-lista">
        {criterio.predicados.map((p, i) => (
          <li key={i}>
            {p.materia === null ? 'Média geral' : p.materia === '*' ? 'Qualquer disciplina' : p.materia === 'fase_1' ? '1ª fase (componente da média)' : p.materia}
            {` ${p.operador} ${descreverMinimo(p)}`}
            {p.eliminatorio ? ' · eliminatório' : ''}
            {!p.entraNaMedia ? ' · fora da média' : ''}
            {p.peso !== 1 ? ` · peso ${p.peso}` : ''}
            {p.fonte ? ` (${p.fonte})` : ''}
          </li>
        ))}
      </ul>
      <div className="painel-help-sep" />
      {/* A legenda explicava o semáforo. Agora explica a FORMA, que é o que a
          célula passou a dizer: preenchido acima do corte, vazado abaixo, e a
          distância no próprio traço. Uma legenda desatualizada é pior que
          nenhuma — ela ensina a ler errado. */}
      <div className="painel-help-legenda">
        <span className="painel-help-amostra painel-help-amostra--acima" />
        Preenchido — acima do corte; quanto mais forte, mais folga
      </div>
      <div className="painel-help-legenda">
        <span className="painel-help-amostra painel-help-amostra--margem" />
        Preenchido fraco — passou, mas perto do corte
      </div>
      <div className="painel-help-legenda">
        <span className="painel-help-amostra painel-help-amostra--abaixo" />
        Vazado — abaixo do corte; o traço engrossa com a distância, e o número
        vermelho ao lado diz quanto
      </div>
      <div className="painel-help-legenda">
        <span className="painel-help-amostra painel-help-amostra--sem-nota" />
        Hachurado — sem nota lançada. Não é zero
      </div>
    </>
  );
}

const AJUDA_ITENS = [
  'Escolha um ciclo na faixa de filtros para carregar os dados.',
  'Estreite a fileira de ciclos por Ano letivo e Vestibular — os dois nascem com tudo marcado.',
  'Filtre por Sede e Turmas na mesma faixa (múltipla seleção).',
  'Use a busca da faixa para encontrar um aluno na tabela.',
  'A faixa colapsa sozinha quando não cabe numa linha; o resumo do que está ativo fica no lugar.',
  'Ranking: não-cortados primeiro, depois os cortados; desempate pela ordem do critério.',
  'Troque o critério (Tio Leo, ITA, IME) para ver a mesma turma sob outra régua.',
  'Clique nos separadores Top 10 / 50 / 100 para ocultar ou exibir os alunos abaixo.',
];

function BotaoAjuda({ criterio }: { criterio: CriterioClassificacao | null }) {
  const [aberto, setAberto] = useState(false);
  const refRaiz = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!aberto) return;
    function aoClicarFora(ev: MouseEvent) {
      if (!refRaiz.current?.contains(ev.target as Node)) setAberto(false);
    }
    document.addEventListener('click', aoClicarFora);
    return () => document.removeEventListener('click', aoClicarFora);
  }, [aberto]);

  return (
    <div className="painel-help-wrap" ref={refRaiz}>
      <button
        className="painel-help-btn"
        onClick={(ev) => {
          ev.stopPropagation();
          setAberto((a) => !a);
        }}
      >
        ?
      </button>

      <div className="painel-help-tooltip" style={{ display: aberto ? '' : 'none' }}>
        <p className="painel-help-titulo">Legenda &amp; funcionalidades</p>
        <ul className="painel-help-lista">
          {AJUDA_ITENS.map((t) => <li key={t}>{t}</li>)}
        </ul>
        <div className="painel-help-sep" />
        <LegendaCriterio criterio={criterio} />
      </div>
    </div>
  );
}
