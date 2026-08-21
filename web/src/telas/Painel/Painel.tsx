import { useEffect, useMemo, useRef, useState } from 'react';

import { Sidebar } from '../../componentes/layout/Sidebar';
import { Kpi } from '../../componentes/ui/Kpi';
import { CorpoChips, CorpoLista, PainelFiltros } from '../../componentes/ui/filtros/PainelFiltros';
import { FichaNota } from '../../componentes/dialogos/FichaNota';
import { TabelaPainel } from './TabelaPainel';
import {
  estatisticasDoSimulado, montarPainel, nomeSede, normMateria,
} from '../../dominio/painel';
import { useAlunos, useCiclos, useNotasDoCiclo, useSedes, useSimulados, useTurmas } from '../../hooks/consultas';
import { useEditarNota } from '../../hooks/mutacoes';
import { fmtNota } from '../../util/formato';

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
  const [recolhidos, setRecolhidos] = useState<ReadonlySet<number>>(new Set());
  const [abertas, setAbertas] = useState<ReadonlySet<string>>(new Set(['ciclo']));
  const [emEdicao, setEmEdicao] = useState<{ alunoId: string; simuladoId: string } | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');

  const editarNota = useEditarNota();

  // Primeiro ciclo da lista assim que ela chega.
  const cicloAtivo = ciclos.find((c) => c.id === cicloId) ?? ciclos[0] ?? null;
  const { data: notasPorSim = {}, isPending: carregandoNotas } = useNotasDoCiclo(cicloAtivo, simulados);

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
    }),
    [cicloAtivo, simulados, alunosFiltrados, notasPorSim, fase, ordenacao],
  );

  // A fase escolhida pode não existir no ciclo novo — segue a que sobrou.
  useEffect(() => {
    if (dados.faseSelecionada !== fase) setFase(dados.faseSelecionada);
  }, [dados.faseSelecionada, fase]);

  async function salvarNota(valores: { pontuacao: number | null; presente: boolean } | null) {
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
    <>
      <Sidebar rotulo="Ciclos">
        <PainelFiltros
          abertas={abertas}
          onToggleSecao={(chave) => setAbertas((a) => alternarConjunto(a, chave))}
          algumAtivo={sedeIds.size > 0 || turmaIds.size > 0}
          onLimpar={() => {
            setSedeIds(new Set());
            setTurmaIds(new Set());
          }}
          secoes={[
            {
              chave: 'ciclo', rotulo: 'Ciclos', icone: 'ciclos',
              corpo: (
                <CorpoLista
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
              chave: 'sede', rotulo: 'Sede', icone: 'sede',
              corpo: (
                <CorpoChips
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
              chave: 'turma', rotulo: 'Turmas', icone: 'turmas',
              corpo: (
                <CorpoChips
                  opcoes={turmas.map((t) => ({ valor: t.id, label: t.nome }))}
                  selecionados={turmaIds}
                  onToggle={(id) => setTurmaIds((s) => alternarConjunto(s, id))}
                />
              ),
            },
          ]}
        />
      </Sidebar>

      <main className="app-main">
        <section className="card">
          <div className="painel-header">
            <div className="painel-header__esq">
              <div className="screen-breadcrumb">Painel</div>
              <h1 className="screen-title">Panorama geral</h1>
              <p className="screen-subtitle">
                {cicloAtivo ? cicloAtivo.nome : 'Selecione um ciclo na barra lateral.'}
              </p>
            </div>

            <div className="painel-header__dir">
              <div className="painel-header__controles">
                <BotaoAjuda />
                <BuscaAluno valor={busca} onChange={setBusca} />
                <Pills
                  opcoes={[
                    { label: 'Ranking', value: 'ranking' as const },
                    { label: 'A–Z', value: 'alfabetica' as const },
                  ]}
                  valor={ordenacao}
                  onEscolher={setOrdenacao}
                />
              </div>

              {dados.fasesDisponiveis.length >= 2 && (
                <div className="painel-fase-filtro">
                  <Pills
                    opcoes={dados.fasesDisponiveis.map((f) => ({
                      label: f === '1' ? '1ª Fase' : '2ª Fase',
                      value: f,
                    }))}
                    valor={dados.faseSelecionada}
                    onEscolher={setFase}
                    semWrapper
                  />
                </div>
              )}
            </div>
          </div>

          {erroSalvar && <div className="agendar__erro">{erroSalvar}</div>}

          {resumo && (
            <div className="painel-kpis">
              <Kpi rotulo="Alunos no ciclo" valor={resumo.totalAlunos} />
              <Kpi rotulo="Simulados aplicados" valor={resumo.totalSimulados} />
              <Kpi rotulo="Média geral" valor={fmtNota(resumo.mediaGeral)} tone={toneMedia(resumo.mediaGeral)} />
              <Kpi
                rotulo="Em zona de corte"
                valor={resumo.cortados}
                sufixo={` de ${resumo.totalAlunos}`}
                tone={resumo.cortados > 0 ? 'tone-vermelho' : 'tone-verde'}
              />
            </div>
          )}

          {carregandoNotas ? (
            <div className="section">
              <p className="section__subtitle">Carregando notas…</p>
            </div>
          ) : dados.erro ? (
            <div className="empty-state">{dados.erro}</div>
          ) : (
            <TabelaPainel
              alunos={dados.alunosOrdenados}
              colunas={dados.colunas}
              notasAluno={dados.notasAluno}
              mediasVirtuais={dados.mediasVirtuais}
              mediasPorColuna={dados.mediasPorColuna}
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
      </main>

      {emEdicao && (
        <DialogoNota
          alunoId={emEdicao.alunoId}
          simuladoId={emEdicao.simuladoId}
          notasPorSim={notasPorSim}
          onFechar={salvarNota}
        />
      )}
    </>
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
  onFechar: (valores: { pontuacao: number | null; presente: boolean } | null) => void;
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

function Pills<V extends string>({
  opcoes, valor, onEscolher, semWrapper = false,
}: {
  opcoes: Array<{ label: string; value: V }>;
  valor: V;
  onEscolher: (v: V) => void;
  semWrapper?: boolean;
}) {
  const botoes = opcoes.map((o) => (
    <button
      key={o.value}
      className={`painel-topn__btn${valor === o.value ? ' is-active' : ''}`}
      onClick={() => onEscolher(o.value)}
    >
      {o.label}
    </button>
  ));
  return semWrapper ? <>{botoes}</> : <div className="painel-topn">{botoes}</div>;
}

const AJUDA_ITENS = [
  'Selecione um ciclo na barra lateral para carregar os dados.',
  'Filtre por Sede e Turmas na barra lateral (múltipla seleção).',
  'Use a busca para encontrar um aluno específico.',
  'Ordene por Geral (média final ponderada) ou 1ª Fase.',
  'Clique nos separadores Top 10 / 50 / 100 para ocultar ou exibir os alunos abaixo.',
];

function BotaoAjuda() {
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
        <div className="painel-help-legenda">
          <span className="painel-help-dot painel-help-dot--verde" />
          Verde — sem cortes (todas as notas ≥ 5,0)
        </div>
        <div className="painel-help-legenda">
          <span className="painel-help-dot painel-help-dot--vermelho" />
          Vermelho — cortado em alguma matéria (nota &lt; 5,0)
        </div>
      </div>
    </div>
  );
}
