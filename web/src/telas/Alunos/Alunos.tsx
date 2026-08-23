import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Sparkline } from '../../componentes/ui/Sparkline';
import { TheadOrdenavel } from '../../componentes/ui/TabelaOrdenavel';
import { ordenarLinhas, proximaOrdenacao } from '../../componentes/ui/ordenacao';
import type { ColunaTabela, Ordenacao } from '../../componentes/ui/ordenacao';
import { BarraFiltros, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { useAlunos, useSedes, useTurmas } from '../../hooks/consultas';
import type { Aluno } from '../../tipos/dominio';
import { fmtNota, iniciais } from '../../util/formato';

const PERFIL_LABEL = { ancora: 'Âncora', misterio: 'Mistério', regular: 'Regular' } as const;
const TENDENCIA_LABEL = { subindo: '↑ Subindo', estavel: '→ Estável', caindo: '↓ Caindo' } as const;
const ZONA_LABEL = { top: 'Top', cinzenta: 'Cinzenta', risco: 'Risco' } as const;

const ZONA_TONE = { top: 'tone-verde', cinzenta: 'tone-ambar', risco: 'tone-vermelho' } as const;
const TENDENCIA_TONE = { subindo: 'tone-verde', estavel: 'tone-navy', caindo: 'tone-vermelho' } as const;

// Ordem semântica das colunas categóricas — do pior para o melhor. Ordenar
// alfabeticamente ("Cinzenta, Risco, Top") não diria nada.
const ORDEM_ZONA = ['risco', 'cinzenta', 'top'] as const;
const ORDEM_TENDENCIA = ['caindo', 'estavel', 'subindo'] as const;
const ORDEM_PERFIL = ['regular', 'misterio', 'ancora'] as const;

/** Lista de alunos com filtros laterais (turma, sede) e tabela ordenável. */
export function Alunos() {
  const navegar = useNavigate();

  const { data: alunos = [], isPending, isError, error } = useAlunos();
  const { data: turmas = [] } = useTurmas();
  const { data: sedes = [] } = useSedes();

  const [turmasSel, setTurmasSel] = useState<ReadonlySet<string>>(new Set());
  const [sedesSel, setSedesSel] = useState<ReadonlySet<string>>(new Set());
  const [ordenacao, setOrdenacao] = useState<Ordenacao | null>(null);

  const turmaPorId = useMemo(() => new Map(turmas.map((t) => [t.id, t])), [turmas]);
  const sedePorId = useMemo(() => new Map(sedes.map((s) => [s.id, s])), [sedes]);

  const colunas: Array<ColunaTabela<Aluno>> = useMemo(
    () => [
      { chave: 'nome', label: 'Aluno', valor: (a) => a.nome },
      { chave: 'turma', label: 'Turma', valor: (a) => turmaPorId.get(a.turmaId)?.nome },
      { chave: 'sede', label: 'Sede', valor: (a) => sedePorId.get(a.sedeId)?.nome },
      { chave: 'media', label: 'Média', valor: (a) => a.media, tipo: 'numero' },
      { chave: 'tendencia', label: 'Tendência', valor: (a) => a.tendencia, tipo: 'ordinal', ordem: ORDEM_TENDENCIA },
      { chave: 'perfil', label: 'Perfil', valor: (a) => a.perfil, tipo: 'ordinal', ordem: ORDEM_PERFIL },
      { chave: 'zona', label: 'Zona', valor: (a) => a.zona, tipo: 'ordinal', ordem: ORDEM_ZONA },
      { chave: 'trajetoria', label: 'Trajetória', ordenavel: false },
      { chave: 'acao', label: '', ordenavel: false },
    ],
    [turmaPorId, sedePorId],
  );

  const filtrados = useMemo(
    () =>
      alunos.filter((a) => {
        if (turmasSel.size && !turmasSel.has(a.turmaId)) return false;
        if (sedesSel.size && !sedesSel.has(a.sedeId)) return false;
        return true;
      }),
    [alunos, turmasSel, sedesSel],
  );

  // Cross-filtering: cada dimensão conta ignorando o próprio filtro, senão as
  // contagens virariam sempre o total selecionado.
  const contagens = useMemo(() => {
    const porTurma = new Map<string, number>();
    const porSede = new Map<string, number>();
    for (const a of alunos) {
      if (sedesSel.size === 0 || sedesSel.has(a.sedeId)) {
        porTurma.set(a.turmaId, (porTurma.get(a.turmaId) ?? 0) + 1);
      }
      if (turmasSel.size === 0 || turmasSel.has(a.turmaId)) {
        porSede.set(a.sedeId, (porSede.get(a.sedeId) ?? 0) + 1);
      }
    }
    return { porTurma, porSede };
  }, [alunos, turmasSel, sedesSel]);

  const linhas = useMemo(
    () => ordenarLinhas(filtrados, colunas, ordenacao),
    [filtrados, colunas, ordenacao],
  );

  const algumAtivo = turmasSel.size + sedesSel.size > 0;

  function alternar<V>(conjunto: ReadonlySet<V>, valor: V): ReadonlySet<V> {
    const novo = new Set(conjunto);
    if (novo.has(valor)) novo.delete(valor);
    else novo.add(valor);
    return novo;
  }

  return (
    <div className="tela">
      <BarraFiltros
        algumAtivo={algumAtivo}
        onLimpar={() => {
          setTurmasSel(new Set());
          setSedesSel(new Set());
        }}
        grupos={[
          {
            chave: 'turma',
            rotulo: 'Turma',
            corpo: (
              <Pills
                opcoes={turmas.map((t) => ({
                  valor: t.id,
                  label: t.nome,
                  contagem: contagens.porTurma.get(t.id) ?? 0,
                }))}
                selecionados={turmasSel}
                onToggle={(id) => setTurmasSel((s) => alternar(s, id))}
              />
            ),
          },
          {
            chave: 'sede',
            rotulo: 'Sede',
            corpo: (
              <Pills
                opcoes={sedes.map((sd) => ({
                  valor: sd.id,
                  label: sd.nome,
                  contagem: contagens.porSede.get(sd.id) ?? 0,
                }))}
                selecionados={sedesSel}
                onToggle={(id) => setSedesSel((s) => alternar(s, id))}
              />
            ),
          },
        ]}
      />

      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">Alunos da turma ITM</h1>
          <p className="tela-subtitulo">
            {isPending
              ? 'Carregando…'
              : `${filtrados.length} alunos${algumAtivo ? ` de ${alunos.length}` : ''}`}
          </p>
        </div>
      </div>

      <section className="card">
        {isError ? (
          <div className="empty-state">
            Não foi possível carregar os alunos.
            <div className="empty-state__hint">{(error as Error)?.message}</div>
          </div>
        ) : isPending ? (
          <div className="empty-state">Carregando…</div>
        ) : linhas.length === 0 ? (
          <div className="empty-state">
            Nenhum aluno atende a esses critérios.
            <div className="empty-state__hint">Tente remover algum filtro.</div>
          </div>
        ) : (
          <table className="data-table">
            <TheadOrdenavel
              colunas={colunas}
              ordenacao={ordenacao}
              onOrdenar={(chave) => setOrdenacao((o) => proximaOrdenacao(o, chave))}
            />
            <tbody>
              {linhas.map((a) => (
                <tr key={a.id} onClick={() => navegar(`/alunos/${a.id}`)}>
                  <td>
                    <span className="celula-pessoa">
                      <span className="avatar" aria-hidden="true">{iniciais(a.nome)}</span>
                      <span className="celula-pessoa__nome">{a.nome}</span>
                    </span>
                  </td>
                  <td>{turmaPorId.get(a.turmaId)?.nome ?? '—'}</td>
                  <td>{sedePorId.get(a.sedeId)?.nome ?? '—'}</td>
                  <td>{fmtNota(a.media)}</td>
                  <td>
                    <span className={`tag ${TENDENCIA_TONE[a.tendencia]}`}>
                      {TENDENCIA_LABEL[a.tendencia]}
                    </span>
                  </td>
                  <td>{PERFIL_LABEL[a.perfil]}</td>
                  <td>
                    <span className={`tag ${ZONA_TONE[a.zona]}`}>{ZONA_LABEL[a.zona]}</span>
                  </td>
                  <td>
                    <Sparkline valores={a.sparkline ?? []} cor="var(--color-navy)" />
                  </td>
                  <td>
                    <Link to={`/alunos/${a.id}`} onClick={(ev) => ev.stopPropagation()}>
                      Ver →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
