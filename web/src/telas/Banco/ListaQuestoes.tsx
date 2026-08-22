import { useQuestoes } from '../../hooks/banco';
import type { FiltrosBanco as Filtros } from '../../tipos/banco';
import type { PerfilBanco } from './Banco';
import { CartaoQuestao } from './CartaoQuestao';

// A listagem paginada (docs/22 §P3).
//
// Paginar aqui é o certo e NÃO contradiz a armadilha 2 do CLAUDE.md: lá o teto
// é proibido porque truncar leitura estatística devolve número errado sem
// parecer errado; aqui a resposta é navegação, e a página seguinte está a um
// clique. Quem agrega — `/banco/estatisticas` — nunca pagina (docs/22 §2.2).

interface Props {
  filtros: Filtros;
  perfil: PerfilBanco;
  onPagina: (pagina: number) => void;
  idsNaLista: ReadonlySet<string>;
  onAlternarNaLista: (questaoId: string) => void;
  tituloListaAtiva: string | null;
}

export function ListaQuestoes({
  filtros,
  perfil,
  onPagina,
  idsNaLista,
  onAlternarNaLista,
  tituloListaAtiva,
}: Props) {
  const { data, isPending, isError, error, isPlaceholderData } = useQuestoes(filtros);

  const questoes = data?.questoes ?? [];
  const total = data?.total ?? 0;
  const pagina = data?.pagina ?? filtros.pagina ?? 1;
  const porPagina = data?.porPagina ?? filtros.porPagina ?? 20;
  const totalPaginas = Math.max(1, Math.ceil(total / porPagina));

  return (
    <>
      <div className="banco-cabecalho">
        <h1 className="banco-cabecalho__titulo">Banco de questões</h1>
        <span className="banco-cabecalho__meta">
          {isPending
            ? 'Carregando…'
            : `${total} ${total === 1 ? 'questão' : 'questões'} · página ${pagina} de ${totalPaginas}`}
          {/* `keepPreviousData` segura a página atual enquanto a próxima carrega
              (hooks/banco.ts): sem dizer que está atualizando, o clique em
              "próxima" parece não ter feito nada. */}
          {isPlaceholderData && ' · atualizando…'}
        </span>
      </div>

      {isError && (
        <p className="banco-vazio">
          {(error as Error)?.message || 'Não foi possível carregar as questões.'}
        </p>
      )}

      {!isError && isPending && <p className="banco-vazio">Carregando questões…</p>}

      {!isError && !isPending && questoes.length === 0 && (
        <p className="banco-vazio">
          Nenhuma questão com esses filtros. Tire um filtro ou limpe a busca.
        </p>
      )}

      {questoes.length > 0 && (
        <ul className="banco-questoes">
          {questoes.map((questao) => (
            <li key={questao.id}>
              <CartaoQuestao
                questao={questao}
                perfil={perfil}
                naLista={idsNaLista.has(questao.id)}
                onAlternarNaLista={onAlternarNaLista}
                tituloListaAtiva={tituloListaAtiva}
              />
            </li>
          ))}
        </ul>
      )}

      {totalPaginas > 1 && (
        <nav className="banco-paginacao" aria-label="Paginação das questões">
          <button
            type="button"
            className="banco-paginacao__botao"
            disabled={pagina <= 1}
            onClick={() => onPagina(pagina - 1)}
          >
            ← Anterior
          </button>
          <span className="banco-paginacao__posicao">{`${pagina} / ${totalPaginas}`}</span>
          <button
            type="button"
            className="banco-paginacao__botao"
            disabled={pagina >= totalPaginas}
            onClick={() => onPagina(pagina + 1)}
          >
            Próxima →
          </button>
        </nav>
      )}
    </>
  );
}
