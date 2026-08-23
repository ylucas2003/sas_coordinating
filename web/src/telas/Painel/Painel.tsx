import { useEffect, useMemo, useRef, useState } from 'react';

import { Kpi } from '../../componentes/ui/Kpi';
import { BarraFiltros, Pills, PillsUnica } from '../../componentes/ui/filtros/BarraFiltros';
import { FichaNota } from '../../componentes/dialogos/FichaNota';
import type { ValoresNota } from '../../componentes/dialogos/formularioNota';
import { TabelaPainel } from './TabelaPainel';
import {
  estatisticasDoSimulado, montarPainel, nomeSede, normMateria,
} from '../../dominio/painel';
import {
  useAlunos, useCiclos, useClassificacaoCiclo, useCriteriosDisponiveis, useNotasDoCiclo,
  useSedes, useSimulados, useTurmas,
} from '../../hooks/consultas';
import { useEditarNota } from '../../hooks/mutacoes';
import { fmtNota } from '../../util/formato';
import type { AlunoClassificado, CriterioClassificacao } from '../../tipos/dominio';

// Painel — a tabela alunos × matérias/fases de um ciclo.
//
// A lógica de colunas, médias e ranking vive em `dominio/painel.ts`; aqui fica
// só o estado da tela (ciclo, filtros, busca, ordenação) e o desenho.

function toneMedia(media: number | null): string {
  if (media == null) return '';
  return media >= 7 ? 'tone-verde' : media >= 5 ? 'tone-ambar' : 'tone-vermelho';
}

export function Painel() {
  const { data: ciclos = [] } = useCiclos();
  const { data: alunos = [] } = useAlunos();
  const { data: simulados = [] } = useSimulados();
  const { data: sedes = [] } = useSedes();
  const { data: turmas = [] } = useTurmas();

  const [cicloId, setCicloId] = useState<string | null>(null);
  const [sedeIds, setSedeIds] = useState<ReadonlySet<string>>(new Set());
  const [turmaIds, setTurmaIds] = useState<ReadonlySet<string>>(new Set());
  const [busca, setBusca] = useState('');
  const [ordenacao, setOrdenacao] = useState<'ranking' | 'alfabetica'>('ranking');
  const [fase, setFase] = useState<'1' | '2'>('1');
  // A régua do corte. 'tio-leo' é a pedagógica do colégio; ITA/IME seguem o edital.
  const [criterio, setCriterio] = useState('tio-leo');
  const [recolhidos, setRecolhidos] = useState<ReadonlySet<number>>(new Set());
  const [emEdicao, setEmEdicao] = useState<{ alunoId: string; simuladoId: string } | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');

  const editarNota = useEditarNota();

  // Primeiro ciclo da lista assim que ela chega.
  const cicloAtivo = ciclos.find((c) => c.id === cicloId) ?? ciclos[0] ?? null;
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
    }),
    [cicloAtivo, simulados, alunosFiltrados, notasPorSim, fase, ordenacao, classificacao],
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
        algumAtivo={sedeIds.size > 0 || turmaIds.size > 0}
        onLimpar={() => {
          setSedeIds(new Set());
          setTurmaIds(new Set());
        }}
        grupos={[
          {
            chave: 'ciclo', rotulo: 'Ciclo',
            corpo: (
              <PillsUnica
                opcoes={ciclos.map((c) => ({ valor: c.id, label: c.nome }))}
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
            chave: 'turma', rotulo: 'Turmas',
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
          <BuscaAluno valor={busca} onChange={setBusca} />
          <Segmento
            opcoes={[
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
          <SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />
        </div>
      </div>

      {erroSalvar && <div className="agendar__erro">{erroSalvar}</div>}

      {resumo && (
        <div className="kpi-grid kpi-grid--cartoes">
          <Kpi rotulo="Alunos no ciclo" valor={resumo.totalAlunos} />
          <Kpi rotulo="Simulados aplicados" valor={resumo.totalSimulados} />
          <Kpi rotulo="Média geral" valor={fmtNota(resumo.mediaGeral)} tone={toneMedia(resumo.mediaGeral)} />
          <Kpi
            rotulo={`Cortados · ${classificacaoResp?.criterio.nome ?? '…'}`}
            valor={resumo.cortados ?? '…'}
            sufixo={` de ${resumo.totalAlunos}`}
            tone={resumo.cortados == null ? '' : resumo.cortados > 0 ? 'tone-vermelho' : 'tone-verde'}
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
            mediasVirtuais={dados.mediasVirtuais}
            mediasPorColuna={dados.mediasPorColuna}
            classificacao={classificacao}
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

function BuscaAluno({ valor, onChange }: { valor: string; onChange: (v: string) => void }) {
  return (
    <div className="painel-busca-wrap">
      <svg
        xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      >
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        className="painel-busca"
        type="text"
        placeholder="Buscar aluno…"
        value={valor}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
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

/** Qual régua de corte está em uso — a do colégio ou a de um edital. */
function SeletorCriterio({
  criterios, valor, onEscolher,
}: {
  criterios: CriterioClassificacao[];
  valor: string;
  onEscolher: (slug: string) => void;
}) {
  if (!criterios.length) return null;
  return (
    <select
      className="painel-criterio"
      aria-label="Critério de classificação"
      value={valor}
      onChange={(ev) => onEscolher(ev.target.value)}
    >
      {criterios.map((c) => (
        <option key={c.slug} value={c.slug}>{c.nome}</option>
      ))}
    </select>
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
      <div className="painel-help-legenda">
        <span className="painel-help-dot painel-help-dot--verde" />
        Verde — confortável acima do corte
      </div>
      <div className="painel-help-legenda">
        <span className="painel-help-dot painel-help-dot--ambar" />
        Âmbar — passou, mas perto do corte
      </div>
      <div className="painel-help-legenda">
        <span className="painel-help-dot painel-help-dot--vermelho" />
        Vermelho — abaixo do corte
      </div>
    </>
  );
}

const AJUDA_ITENS = [
  'Escolha um ciclo na faixa de filtros para carregar os dados.',
  'Filtre por Sede e Turmas na mesma faixa (múltipla seleção).',
  'Use a busca para encontrar um aluno específico.',
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
