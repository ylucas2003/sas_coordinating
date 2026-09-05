import { Link } from 'react-router-dom';
import { corteDaMateria } from '../../dominio/criterios';
import { LIMITES_RANKING, linhaVisivel } from '../../dominio/painel';
import type { ClassificacaoPorAluno, OrdenacaoPainel } from '../../dominio/painel';
import { seloDaNota } from '../../dominio/selo';
import { Sparkline } from '../../componentes/ui/Sparkline';
import type { TomNota } from '../../tipos/dominio';
import type { ColunaPainel, IgnoradasPorAluno, NotasPorAluno } from '../../dominio/painel';
import type { Aluno, CriterioClassificacao } from '../../tipos/dominio';
import { fmtNota } from '../../util/formato';

interface Props {
  alunos: readonly Aluno[];
  colunas: readonly ColunaPainel[];
  notasAluno: NotasPorAluno;
  /** O que a média deixou de fora — a célula mostra, marcado. */
  notasIgnoradas: IgnoradasPorAluno;
  mediasVirtuais: Record<string, Record<string, number | null>>;
  mediasPorColuna: Record<string, number | null>;
  /** Veredito, motivo e cor por aluno — vem do servidor. */
  classificacao: ClassificacaoPorAluno;
  /** A régua em vigor. É dela que sai o corte de cada matéria, e sem ela o
      selo não tem como desenhar distância — só lado. */
  criterio: CriterioClassificacao | null;
  /** Qual ordenação está em vigor — R6 exige que ela seja VISÍVEL e NOMEADA. */
  ordenacao: OrdenacaoPainel;
  recolhidos: ReadonlySet<number>;
  /** `null` fora do modo ranking — os separadores só fazem sentido ordenado. */
  onToggleLimite: ((posicao: number) => void) | null;
  onEditarNota: (alunoId: string, simuladoId: string) => void;
}

/** O nome do ordenador, como ele aparece no cabeçalho da tabela (R6). */
const ROTULO_ORDEM: Record<OrdenacaoPainel, string> = {
  distancia: 'distância do corte, pior primeiro',
  ranking: 'classificação do critério',
  alfabetica: 'nome, A–Z',
};

function classeColuna(col: ColunaPainel, base: string): string {
  return [base, col.novaFase && 'borda-nova-fase', col.destaque && 'col-destaque']
    .filter(Boolean)
    .join(' ');
}

/**
 * O selo de uma nota — PREENCHIDO acima do corte, VAZADO abaixo (R1), com a
 * intensidade carregando a distância (R3) e a etiqueta em vermelho como único
 * alerta (R4). Ver `dominio/selo.ts`.
 *
 * A régua NÃO é decidida aqui. O corte vem resolvido do servidor e é lido por
 * `corteDaMateria` — reimplementar o encadeamento em TypeScript foi o que a
 * Sprint 2 proibiu (docs/18 §1.2).
 *
 * Quando não há corte aplicável — coluna virtual de média, ou classificação
 * ainda carregando —, cai no `tom` que o servidor mandou. Ele diz o lado mas
 * não diz a distância, então o desenho fica sem etiqueta e com intensidade
 * fixa: é menos informação, e é honesto que pareça menos.
 */
const INTENSIDADE_SEM_CORTE: Record<TomNota, { classe: string; intensidade: number }> = {
  verde: { classe: 'nota-badge--acima', intensidade: 0.7 },
  ambar: { classe: 'nota-badge--acima', intensidade: 0.15 },
  vermelho: { classe: 'nota-badge--abaixo', intensidade: 0.5 },
};

function NotaBadge({
  nota, tom, corte, daTurma = false, titulo,
}: {
  nota: number | null;
  tom?: TomNota;
  corte?: number | null;
  daTurma?: boolean;
  titulo?: string;
}) {
  if (nota == null) {
    return <span className="nota-badge nota-badge--vazia" title="sem nota lançada">—</span>;
  }

  // A média da turma é REFERÊNCIA, não desempenho de ninguém (R5): fica
  // neutra, atrás do dado, em vez de disputar a leitura com as linhas.
  if (daTurma) {
    return (
      <span className="nota-badge nota-badge--media" title={titulo}>
        {fmtNota(nota)}
      </span>
    );
  }

  const selo = seloDaNota(nota, corte);
  const semRegua = selo.estado === 'sem-dado';
  const alternativa = semRegua && tom ? INTENSIDADE_SEM_CORTE[tom] : null;

  const classe = alternativa
    ? alternativa.classe
    : semRegua
      ? ''
      : `nota-badge--${selo.estado}${selo.estado === 'acima' && selo.intensidade > 0.5 ? ' nota-badge--acima-forte' : ''}`;
  const intensidade = alternativa ? alternativa.intensidade : selo.intensidade;

  return (
    <>
      <span
        className={`nota-badge ${classe}`.trimEnd()}
        style={{ '--nota-intensidade': intensidade } as React.CSSProperties}
        title={titulo}
      >
        {fmtNota(nota)}
      </span>
      {selo.etiqueta && (
        // `title` e não `aria-label`: um `<span>` sem role não suporta
        // `aria-label`, e o texto visível já é a informação — a etiqueta É o
        // número. O `title` só acrescenta contra o quê ele é medido.
        <span className="nota-etiqueta" title={`${selo.etiqueta} em relação ao corte da matéria`}>
          {selo.etiqueta}
        </span>
      )}
    </>
  );
}

/** Motivo técnico → frase. `motivo` novo cai no texto genérico, sem quebrar. */
const TEXTO_IGNORADA: Record<string, string> = {
  todas_em_branco: 'nenhuma alternativa marcada',
};

/**
 * A nota que a média não somou — visível, riscada, e dizendo por quê.
 *
 * Regra da casa: um número que o produto decidiu ignorar precisa DIZER que
 * ignorou. Some-lo da tela esconderia a decisão; deixá-lo igual aos outros
 * faria o coordenador somar de cabeça um valor que o sistema não somou
 * (docs/32 §1.5, item 7).
 */
function NotaIgnoradaBadge({ nota, motivo }: { nota: number | null; motivo: string | null }) {
  const explicacao = (motivo && TEXTO_IGNORADA[motivo]) || 'não entra na média';
  return (
    <span
      className="nota-badge nota-badge--ignorada"
      title={`${fmtNota(nota)} — ${explicacao}; não entra na média`}
    >
      {fmtNota(nota)}
    </span>
  );
}

export function TabelaPainel({
  alunos, colunas, notasAluno, notasIgnoradas, mediasVirtuais, mediasPorColuna, classificacao,
  criterio, ordenacao,
  recolhidos, onToggleLimite, onEditarNota,
}: Props) {
  return (
    <div className="painel-tabela-wrap">
      {/* R6 · o ordenador em vigor é visível e NOMEADO. Sem a cor, é a ordem
          que entrega o aluno em risco — e uma ordem que o coordenador não sabe
          qual é não entrega nada. */}
      <div className="painel-tabela-ordem">
        <span className="painel-tabela-ordem__total">
          {alunos.length} {alunos.length === 1 ? 'aluno' : 'alunos'}
        </span>
        <span className="painel-tabela-ordem__pilula">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M12 5v14M7 14l5 5 5-5" />
          </svg>
          {ROTULO_ORDEM[ordenacao]}
        </span>
      </div>
      <table className="painel-tabela">
        <thead>
          <tr>
            <th className="painel-tabela__th-pos" rowSpan={2}>#</th>
            <th className="painel-tabela__th-aluno" rowSpan={2}>Aluno</th>
            {colunas.map((col) => (
              <th key={col.id} className={classeColuna(col, 'painel-tabela__th-col')}>
                {col.label}
              </th>
            ))}
            {/* A TRAJETÓRIA no lugar da distância. O número da distância já
                aparece na etiqueta de cada célula abaixo do corte, e a coluna
                repetia a pior delas; a trajetória diz outra coisa — para onde
                o aluno está indo —, que a tabela não respondia. */}
            <th className="painel-tabela__th-traj" rowSpan={2}>Trajetória</th>
          </tr>
          <tr>
            {colunas.map((col) => (
              <th key={col.id} className={classeColuna(col, 'painel-tabela__th-fase')}>
                {col.fase}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          <tr className="painel-tabela__tr-media">
            <td className="painel-tabela__td-pos" />
            <td className="painel-tabela__td-aluno">Média da turma</td>
            {colunas.map((col) => (
              <td key={col.id} className={classeColuna(col, 'painel-tabela__td-nota')}>
                <NotaBadge nota={mediasPorColuna[col.id] ?? null} daTurma />
              </td>
            ))}
            <td className="painel-tabela__td-traj" />
          </tr>

          {alunos.flatMap((aluno, i) => {
            const pos = i + 1;
            if (!linhaVisivel(pos, recolhidos)) return [];

            const veredito = classificacao[aluno.id];
            const extra = !veredito ? '' : veredito.aprovado ? ' is-aprovado' : ' is-cortado';

            const linha = (
              <tr key={aluno.id}>
                <td className="painel-tabela__td-pos">
                  <span className="pos-badge">{pos}</span>
                </td>
                <td className="painel-tabela__td-aluno">
                  <Link
                    className={`painel-tabela__aluno-link${extra}`}
                    to={`/alunos/${aluno.id}`}
                    title={veredito?.motivo ? `${aluno.nome} — cortado: ${veredito.motivo}` : aluno.nome}
                  >
                    {aluno.nome}
                  </Link>
                </td>
                {colunas.map((col) => {
                  const nota = col.virtual
                    ? mediasVirtuais[aluno.id]?.[col.id] ?? null
                    : col.sim
                      ? notasAluno[aluno.id]?.[col.sim.id] ?? null
                      : null;
                  const editavel = !col.virtual && !!col.sim;
                  const ignorada = col.sim ? notasIgnoradas[aluno.id]?.[col.sim.id] : undefined;

                  return (
                    <td
                      key={col.id}
                      className={classeColuna(col, 'painel-tabela__td-nota') + (editavel ? ' is-editavel' : '')}
                      onClick={
                        editavel
                          ? (ev) => {
                              ev.stopPropagation();
                              onEditarNota(aluno.id, col.sim!.id);
                            }
                          : undefined
                      }
                    >
                      {ignorada ? (
                        <NotaIgnoradaBadge nota={ignorada.nota} motivo={ignorada.motivo} />
                      ) : (
                        <NotaBadge
                          nota={nota}
                          tom={col.sim?.materia?.codigo ? veredito?.notas[col.sim.materia.codigo]?.tom : undefined}
                          corte={
                            col.virtual ? null : corteDaMateria(criterio, col.sim?.materia?.codigo)
                          }
                        />
                      )}
                    </td>
                  );
                })}
                <td className="painel-tabela__td-traj">
                  {aluno.sparkline?.length ? (
                    <Sparkline valores={aluno.sparkline} cor="var(--color-dado)" />
                  ) : (
                    <span className="painel-tabela__traj-vazia" title="sem histórico suficiente">—</span>
                  )}
                </td>
              </tr>
            );

            // Separador de ranking depois da posição N (só no modo ranking).
            if (onToggleLimite && LIMITES_RANKING.includes(pos) && i < alunos.length - 1) {
              return [
                linha,
                <SeparadorRanking
                  key={`sep-${pos}`}
                  posicao={pos}
                  colunas={colunas.length}
                  recolhido={recolhidos.has(pos)}
                  onToggle={onToggleLimite}
                />,
              ];
            }
            return [linha];
          })}
        </tbody>
      </table>
    </div>
  );
}

function SeparadorRanking({
  posicao, colunas, recolhido, onToggle,
}: {
  posicao: number;
  colunas: number;
  recolhido: boolean;
  onToggle: (p: number) => void;
}) {
  return (
    <tr className="painel-corte-row">
      <td className="painel-corte__label" colSpan={colunas + 2}>
        <span className="painel-corte__tag">{`Top ${posicao}`}</span>
        <button className="painel-corte__btn" onClick={() => onToggle(posicao)}>
          {recolhido ? `▼ exibir abaixo do ${posicao}°` : `▲ ocultar abaixo do ${posicao}°`}
        </button>
      </td>
    </tr>
  );
}
