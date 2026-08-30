import { Link } from 'react-router-dom';

import { useAssuntos } from '../../dados/aluno';
import type { AssuntoPrioritario } from '../../dados/aluno';
import { Bloco } from './pecas/Bloco';
import { Icone } from './pecas/Icone';
import { AVISO_DE_COBERTURA, fmtDelta, fmtPercentual } from './pecas/formato';

// "O QUE MAIS CAI" — a tela que deixa de responder "o que já caiu".
//
// A diferença entre as duas perguntas é o documento inteiro de docs/24 §4:
// incidência bruta diz o passado; importância é a fatia da prova ponderada por
// recência (meia-vida de 5 anos), e é isso que se lê como "vale 7% da prova".
//
// ⚠️ O ÍNDICE DIZ O QUANTO ESTUDAR; A TENDÊNCIA DIZ POR QUÊ (docs/24 §4.2,
// passo 4). Por isso os DOIS números da tendência aparecem — a fatia dos cinco
// anos recentes e a dos cinco anteriores. Um índice sozinho esconde o que
// ponderou, e uma seta sozinha esconde a escala: "▼" sobre 6% e sobre 0,4% são
// a mesma seta e conselhos opostos.
//
// ⚠️ E o `n` aparece SEMPRE (docs/24 §4.4). Tópico com n < 3 ranqueia por
// ruído e fica fora de "priorize isto" — mas NUNCA some: "não caiu em oito
// anos" é informação de estudo, e sumir com ele daria ao aluno um recorte
// incompleto sem aviso.

/** Abaixo disto a base amostral é ruído, não sinal (docs/24 §4.4). */
const N_MINIMO = 3;

export function EstudarAssuntos() {
  const assuntos = useAssuntos();

  // A ORDEM VEM DA FONTE e não é reordenada aqui: ela é
  // `importância × (1 − meu acerto)` (docs/24 §4.5). Reordenar na tela trocaria
  // a régua que a coordenação discute pela ordenação de um componente, e os
  // dois passariam a mostrar rankings diferentes do mesmo assunto.
  const todos = assuntos.data ?? [];
  const priorizar = todos.filter((a) => a.nQuestoes >= N_MINIMO);
  const raros = todos.filter((a) => a.nQuestoes < N_MINIMO);

  return (
    <>
      <Link className="alu-est-voltar" to="/estudar">
        <Icone nome="voltar" tamanho={16} />
        Estudar
      </Link>

      <h1 className="alu-titulo-tela">O que mais cai</h1>

      <p className="alu-est-cobertura">
        <span className="alu-olho alu-olho--quieto">Cobertura</span>
        {AVISO_DE_COBERTURA}
      </p>

      {assuntos.isPending && <p className="alu-carregando">Pesando as provas…</p>}

      {assuntos.isError && (
        <div className="alu-bloco">
          <p className="alu-erro">Não deu para carregar os assuntos.</p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma"
            onClick={() => {
              assuntos.refetch();
            }}
          >
            Tentar de novo
          </button>
        </div>
      )}

      {assuntos.isSuccess && todos.length === 0 && (
        <Bloco fonte="importanciaDoAssunto">
          <p className="alu-vazio">
            Ainda não há assunto medido para você. Enquanto isso, o acervo inteiro está aberto
            em Estudar.
          </p>
          <Link className="alu-tecla" to="/estudar">
            Ver as questões
          </Link>
        </Bloco>
      )}

      {priorizar.length > 0 && (
        <Bloco
          fonte="importanciaDoAssunto"
          olho="Priorize isto"
          acao={`${priorizar.length} assuntos`}
        >
          <p className="alu-assunto__explicacao">
            Ordenados pelo que mais cai <em>e</em> você mais erra. A fatia é quanto o assunto
            vale da prova hoje; a tendência mostra para onde a banca está indo.
          </p>
          <ul className="alu-assunto-lista">
            {priorizar.map((a) => (
              <LinhaDoAssunto key={`${a.materia}-${a.topicoCodigo}`} assunto={a} />
            ))}
          </ul>
        </Bloco>
      )}

      {raros.length > 0 && (
        <Bloco fonte="importanciaDoAssunto" olho="Base pequena demais para ranquear">
          <p className="alu-assunto__explicacao">
            Estes caíram menos de {N_MINIMO} vezes em todo o acervo. Com tão poucas questões o
            índice mede ruído, então eles ficam fora da lista de prioridade — mas continuam
            aqui, porque "quase não cai" também é informação de estudo.
          </p>
          <ul className="alu-assunto-lista">
            {raros.map((a) => (
              <LinhaDoAssunto key={`${a.materia}-${a.topicoCodigo}`} assunto={a} />
            ))}
          </ul>
        </Bloco>
      )}
    </>
  );
}

function LinhaDoAssunto({ assunto }: { assunto: AssuntoPrioritario }) {
  const sobe = assunto.tendencia > 0;
  const parado = assunto.tendencia === 0;

  return (
    <li className="alu-assunto">
      <div className="alu-assunto__cabeca">
        <span className="alu-assunto__nome">
          <strong>{assunto.nome}</strong>
          <span className="alu-olho alu-olho--quieto">
            {assunto.materia} · {assunto.topicoCodigo}
          </span>
        </span>
        {/* A matéria viaja junto do código porque o código não identifica o
            assunto sozinho: '1.1' existe nas três e significa coisa diferente
            em cada uma (docs/28 §6). Quem monta a fila do treino precisa das
            duas coisas para não pedir um recorte errado. */}
        <Link
          className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
          to={`/treino/assunto/${assunto.topicoCodigo}?materia=${encodeURIComponent(assunto.materia)}`}
        >
          Treinar
        </Link>
      </div>

      <dl className="alu-assunto__numeros">
        <div className="alu-assunto__numero">
          <dt className="alu-olho alu-olho--quieto">Fatia da prova</dt>
          <dd className="alu-magnitude alu-assunto__valor">
            {fmtPercentual(assunto.importancia)}
          </dd>
        </div>

        <div className="alu-assunto__numero">
          <dt className="alu-olho alu-olho--quieto">Tendência</dt>
          <dd className="alu-assunto__tendencia">
            <span className="alu-assunto__antes">{fmtPercentual(assunto.fatiaAntiga)}</span>
            {parado ? (
              <Icone nome="avancar" tamanho={14} />
            ) : (
              <Icone nome={sobe ? 'seta_cima' : 'seta_baixo'} tamanho={14} />
            )}
            <span className="alu-assunto__agora">{fmtPercentual(assunto.fatiaRecente)}</span>
            <em className="alu-assunto__delta">{fmtDelta(assunto.tendencia * 100)} p.p.</em>
          </dd>
        </div>

        <div className="alu-assunto__numero">
          <dt className="alu-olho alu-olho--quieto">Você acerta</dt>
          <dd className="alu-magnitude alu-assunto__valor">
            {fmtPercentual(assunto.meuAcerto)}
          </dd>
        </div>
      </dl>

      <p className="alu-assunto__n">
        {assunto.nQuestoes === 1
          ? '1 questão no acervo'
          : `${assunto.nQuestoes} questões no acervo`}
        {assunto.nQuestoes < N_MINIMO && ' · base pequena'}
      </p>
    </li>
  );
}
