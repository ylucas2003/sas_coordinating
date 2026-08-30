import { Link, useParams } from 'react-router-dom';

import { useAtualizarLista, useLista, useRemoverQuestaoDaLista } from '../../dados/aluno';
import { reordenar } from '../../dominio/banco';
import { CartaoQuestaoAluno } from './pecas/CartaoQuestaoAluno';
import { Icone } from './pecas/Icone';
import { fmtDataCurta } from './pecas/formato';

// UMA LISTA ABERTA — a fila que o aluno montou, na ordem que ele escolheu.
//
// A ordem é dado, não enfeite: `lista_questoes_item.posicao` existe justamente
// para o aluno colocar primeiro o que quer refazer primeiro.
//
// ⚠️ REORDENAR MANDA A ORDEM COMPLETA num PATCH só (`AtualizarLista.questaoIds`,
// docs/22 §P6). É assim que a rota funciona, e é assim que dois toques rápidos
// em "subir" não viram duas requisições que chegam fora de ordem e deixam a
// lista embaralhada — o servidor recebe o estado final, não um movimento.

export function EstudarLista() {
  const { id = '' } = useParams();
  const lista = useLista(id || null);
  const atualizar = useAtualizarLista();
  const remover = useRemoverQuestaoDaLista();

  function mover(de: number, para: number) {
    if (!lista.data) return;
    const ordem = reordenar(
      lista.data.questoes.map((q) => q.id),
      de,
      para,
    );
    atualizar.mutate({ id, remendo: { questaoIds: ordem } });
  }

  if (lista.isPending) {
    return <p className="alu-carregando">Abrindo a lista…</p>;
  }

  if (lista.isError || !lista.data) {
    return (
      <>
        <Link className="alu-est-voltar" to="/estudar/listas">
          <Icone nome="voltar" tamanho={16} />
          Minhas listas
        </Link>
        <div className="alu-bloco">
          <p className="alu-erro">Esta lista não abriu.</p>
          <p className="alu-vazio">
            Ou ela foi apagada, ou a conexão caiu no meio. Suas outras listas continuam lá.
          </p>
          <Link className="alu-tecla" to="/estudar/listas">
            Ver minhas listas
          </Link>
        </div>
      </>
    );
  }

  const { questoes, titulo, atualizadaEm } = lista.data;

  return (
    <>
      <Link className="alu-est-voltar" to="/estudar/listas">
        <Icone nome="voltar" tamanho={16} />
        Minhas listas
      </Link>

      <h1 className="alu-titulo-tela alu-lista__titulo-tela">{titulo}</h1>

      <p className="alu-lista__meta">
        {questoes.length === 1 ? '1 questão' : `${questoes.length} questões`}
        {' · atualizada em '}
        {fmtDataCurta(atualizadaEm.slice(0, 10))}
      </p>

      {questoes.length === 0 ? (
        <div className="alu-bloco">
          <p className="alu-vazio">
            Esta lista ainda está vazia. Toque em "Lista" no rodapé de qualquer questão para
            trazê-la para cá.
          </p>
          <Link className="alu-tecla" to="/estudar">
            Escolher questões
          </Link>
        </div>
      ) : (
        <>
          <Link className="alu-tecla alu-tecla--larga" to={`/treino/lista/${id}`}>
            Treinar esta lista
          </Link>

          <ul className="alu-lista-questoes">
            {questoes.map((questao, i) => (
              <li key={questao.id} className="alu-lista-questao">
                <div className="alu-lista-questao__ordem">
                  <span className="alu-olho alu-olho--quieto">{i + 1}</span>
                  <button
                    type="button"
                    className="alu-lista-questao__mover"
                    disabled={i === 0 || atualizar.isPending}
                    onClick={() => mover(i, i - 1)}
                    aria-label={`Mover a questão ${i + 1} para cima`}
                  >
                    <Icone nome="seta_cima" tamanho={16} />
                  </button>
                  <button
                    type="button"
                    className="alu-lista-questao__mover"
                    disabled={i === questoes.length - 1 || atualizar.isPending}
                    onClick={() => mover(i, i + 1)}
                    aria-label={`Mover a questão ${i + 1} para baixo`}
                  >
                    <Icone nome="seta_baixo" tamanho={16} />
                  </button>
                </div>

                {/* `naLista` já ligado: aqui o botão da lista é o de TIRAR
                    daqui, e reusar a mesma ação do cartão evita um segundo
                    botão de remover competindo com ele no mesmo rodapé. */}
                <CartaoQuestaoAluno
                  questao={questao}
                  naLista
                  onAlternarNaLista={(questaoId) =>
                    remover.mutate({ listaId: id, questaoId })
                  }
                />
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
