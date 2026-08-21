import { Link } from 'react-router-dom';
import { LIMITES_RANKING, linhaVisivel, statusAluno } from '../../dominio/painel';
import type { ColunaPainel, NotasPorAluno } from '../../dominio/painel';
import type { Aluno } from '../../tipos/dominio';
import { fmtNota } from '../../util/formato';

interface Props {
  alunos: readonly Aluno[];
  colunas: readonly ColunaPainel[];
  notasAluno: NotasPorAluno;
  mediasVirtuais: Record<string, Record<string, number | null>>;
  mediasPorColuna: Record<string, number | null>;
  recolhidos: ReadonlySet<number>;
  /** `null` fora do modo ranking — os separadores só fazem sentido ordenado. */
  onToggleLimite: ((posicao: number) => void) | null;
  onEditarNota: (alunoId: string, simuladoId: string) => void;
}

function classeColuna(col: ColunaPainel, base: string): string {
  return [base, col.novaFase && 'borda-nova-fase', col.destaque && 'col-destaque']
    .filter(Boolean)
    .join(' ');
}

function NotaBadge({ nota, daTurma = false }: { nota: number | null; daTurma?: boolean }) {
  if (nota == null) return <span className="nota-badge nota-badge--vazia">—</span>;
  const tom = nota >= 7 ? 'verde' : nota >= 5 ? 'ambar' : 'vermelho';
  return (
    <span className={`nota-badge nota-badge--${tom}${daTurma ? ' nota-badge--media' : ''}`}>
      {fmtNota(nota)}
    </span>
  );
}

export function TabelaPainel({
  alunos, colunas, notasAluno, mediasVirtuais, mediasPorColuna,
  recolhidos, onToggleLimite, onEditarNota,
}: Props) {
  return (
    <div className="painel-tabela-wrap">
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
          </tr>

          {alunos.flatMap((aluno, i) => {
            const pos = i + 1;
            if (!linhaVisivel(pos, recolhidos)) return [];

            const status = statusAluno(aluno.id, colunas, notasAluno);
            const extra = status === 'cortado' ? ' is-cortado' : status === 'aprovado' ? ' is-aprovado' : '';

            const linha = (
              <tr key={aluno.id}>
                <td className="painel-tabela__td-pos">
                  <span className="pos-badge">{pos}</span>
                </td>
                <td className="painel-tabela__td-aluno">
                  <Link
                    className={`painel-tabela__aluno-link${extra}`}
                    to={`/alunos/${aluno.id}`}
                    title={aluno.nome}
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
                      <NotaBadge nota={nota} />
                    </td>
                  );
                })}
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
