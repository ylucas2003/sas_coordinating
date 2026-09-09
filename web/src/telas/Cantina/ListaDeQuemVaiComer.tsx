import { useMemo, useState } from 'react';

import { BarraFiltros, Busca, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { Dialogo } from '../../componentes/dialogos/Dialogo';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import {
  escolhasDaLinha, type FiltroDaLista, horaDaLinha, marcaDoModo, type OrdemDaLista,
  recortarPedidos, ROTULO_DA_REFEICAO, rotuloDaContagem, contagemPorModo, rotuloDoDia,
} from '../../dominio/cantina';
import type { PedidoDeAluno, Refeicao } from '../../tipos/cantina';

/**
 * A lista de quem vai comer — a MESMA nos dois cascos (docs/40 §12.4).
 *
 * Ela já existia nas duas telas, escrita duas vezes, mostrando o mesmo. O que
 * faltava era poder TRABALHAR nela: achar um nome na fila, separar quem pediu
 * de quem vai pegar na hora, saber quem deixou para a última hora, e abrir uma
 * pessoa para conferir o que ela marcou.
 *
 * ⚠️ **Uma diferença entre os dois públicos sobrevive, e é de propósito:** a
 * cantina vê o TEXTO da restrição alimentar (ela cozinha); a coordenação vê só
 * a marca de que existe, com a revelação deliberada em `/cantina/direitos`. É
 * dado de saúde de menor (docs/38 §2.6), e é o único motivo de este componente
 * ter um `comTextoDaRestricao` em vez de mostrar sempre.
 *
 * ⚠️ **O filtro recorta o que o botão de exportar leva.** Quem chama recebe a
 * lista recortada de volta por `onRecorte` — um export de 47 linhas embaixo de
 * uma tela que mostra 44 é um botão que mente, e a descoberta acontece na
 * cozinha.
 */

const PILULAS: Array<{ valor: FiltroDaLista; label: string }> = [
  { valor: 'pediu', label: 'pediu' },
  { valor: 'presencial', label: 'retirada na hora' },
  { valor: 'retirado', label: 'já retirado' },
  { valor: 'restricao', label: 'com restrição' },
];

const ORDENS: Array<{ valor: OrdemDaLista; label: string }> = [
  { valor: 'nome', label: 'nome' },
  { valor: 'turma', label: 'turma' },
  { valor: 'hora', label: 'hora' },
];

export function ListaDeQuemVaiComer({
  pedidos, superficie, comTextoDaRestricao = false, refeicao, data, onRecorte,
}: {
  pedidos: PedidoDeAluno[];
  /** A superfície da `BarraFiltros` — é ela que lembra o recorte por tela. */
  superficie: string;
  comTextoDaRestricao?: boolean;
  refeicao: Refeicao;
  data: string;
  /** A lista como está na tela, para o export não divergir dela. */
  onRecorte?: (lista: PedidoDeAluno[]) => void;
}) {
  const [filtros, setFiltros] = useState<ReadonlySet<FiltroDaLista>>(new Set());
  const [busca, setBusca] = useState('');
  const [ordem, setOrdem] = useState<OrdemDaLista>('nome');
  const [aberto, setAberto] = useState<PedidoDeAluno | null>(null);

  const lista = useMemo(
    () => recortarPedidos(pedidos, { filtros, busca, ordem }),
    [pedidos, filtros, busca, ordem],
  );

  // `useMemo` e não `useEffect` para avisar quem chama: o efeito criaria um
  // segundo render a cada digitação, e o botão de exportar ficaria um quadro
  // atrás do que a tela mostra.
  useMemo(() => onRecorte?.(lista), [lista, onRecorte]);

  const contagem = contagemPorModo(lista);
  const filtrando = filtros.size > 0 || !!busca.trim();

  function alternar(valor: FiltroDaLista) {
    setFiltros((atual) => {
      const novo = new Set(atual);
      const v = valor;
      if (novo.has(v)) novo.delete(v);
      else {
        // "pediu" e "retirada na hora" são os dois lados de `modo`: marcar os
        // dois devolveria lista vazia, o que parece defeito. Um substitui o
        // outro, como em qualquer par excludente.
        if (v === 'pediu') novo.delete('presencial');
        if (v === 'presencial') novo.delete('pediu');
        novo.add(v);
      }
      return novo;
    });
  }

  return (
    <div className="cant-lista-trabalho">
      <BarraFiltros
        tela={superficie}
        algumAtivo={filtrando}
        onLimpar={() => { setFiltros(new Set()); setBusca(''); }}
        grupos={[
          {
            chave: 'busca',
            rotulo: 'Aluno',
            corpo: (
              <Busca valor={busca} onChange={setBusca} placeholder="Buscar aluno" />
            ),
            resumo: resumirTexto(busca),
          },
          {
            chave: 'mostrar',
            rotulo: 'Mostrar',
            corpo: (
              <Pills opcoes={PILULAS} selecionados={filtros} onToggle={alternar} />
            ),
            // ⚠️ O resumo é obrigatório: sem ele, a faixa colapsada esconderia
            // um recorte em vigor, e a lista abaixo mentiria em silêncio.
            resumo: resumirSelecao(filtros, PILULAS, 'filtro', 'filtros'),
          },
          {
            chave: 'ordem',
            rotulo: 'Ordenar por',
            corpo: (
              <Pills
                opcoes={ORDENS}
                selecionados={new Set([ordem])}
                onToggle={(v) => setOrdem(v)}
              />
            ),
            resumo: ordem === 'nome' ? null : `por ${ordem}`,
          },
        ]}
      />

      <h2 className="cant-refeicao__olho">
        {lista.length} {rotuloDaContagem(contagem)}
        {/* Quando há filtro, o total também aparece: "44 de 47" é o que impede
            alguém de levar o número recortado como se fosse o do dia. */}
        {filtrando && <span className="cant-lista__de"> de {pedidos.length}</span>}
      </h2>

      <ul className="cant-lista">
        {lista.map((pedido) => (
          <li key={pedido.alunoId} className="cant-lista__linha">
            {/* A linha inteira abre o detalhe. É `button` e não `div` com
                onClick: quem navega por teclado tem de chegar aqui, e quem usa
                leitor de tela precisa ouvir que é acionável. */}
            <button
              type="button"
              className="cant-lista__abrir"
              onClick={() => setAberto(pedido)}
            >
              <span className="cant-lista__aluno">
                {pedido.nome ?? 'sem nome'}
                {pedido.turma && <span className="cant-lista__turma">{pedido.turma}</span>}
                {pedido.modo === 'presencial' && (
                  <span className="cant-tarja">{marcaDoModo(pedido)}</span>
                )}
              </span>
              <span className="cant-lista__escolhas">{escolhasDaLinha(pedido)}</span>
              {/* O dado já viajava na resposta e só aparecia no export. Na
                  véspera do prazo, "quem deixou para as 19h50" é pergunta
                  real. */}
              {horaDaLinha(pedido) && (
                <span className="cant-lista__hora">{horaDaLinha(pedido)}</span>
              )}
              {pedido.restricaoAlimentar && (
                <span className="cant-lista__marca">
                  {comTextoDaRestricao ? pedido.restricaoAlimentar : 'tem restrição alimentar'}
                </span>
              )}
            </button>
          </li>
        ))}
        {!lista.length && (
          <li className="cant-vazio">
            {filtrando ? 'Nenhum aluno com esse recorte.' : 'Ninguém pediu ainda.'}
          </li>
        )}
      </ul>

      {aberto && (
        <DetalheDoAluno
          pedido={aberto}
          refeicao={refeicao}
          data={data}
          comTextoDaRestricao={comTextoDaRestricao}
          onFechar={() => setAberto(null)}
        />
      )}
    </div>
  );
}

/**
 * O pedido de UMA pessoa, sobre a lista.
 *
 * Diálogo e não rota própria: a tarefa é conferir vários em sequência, e perder
 * o lugar na lista a cada um trocaria um problema por outro (docs/40 §12.4).
 */
function DetalheDoAluno({
  pedido, refeicao, data, comTextoDaRestricao, onFechar,
}: {
  pedido: PedidoDeAluno;
  refeicao: Refeicao;
  data: string;
  comTextoDaRestricao: boolean;
  onFechar: () => void;
}) {
  return (
    <Dialogo
      titulo={pedido.nome ?? 'Sem nome'}
      subtitulo={`${ROTULO_DA_REFEICAO[refeicao]} · ${rotuloDoDia(data)}`}
      onFechar={onFechar}
      rodape={<button type="button" className="btn" onClick={onFechar}>Fechar</button>}
    >
      <dl className="cant-detalhe">
        <dt>Turma</dt>
        <dd>{pedido.turma ?? '—'}</dd>

        <dt>Como vai comer</dt>
        <dd>{marcaDoModo(pedido)}</dd>

        <dt>O que escolheu</dt>
        <dd>{escolhasDaLinha(pedido)}</dd>

        {pedido.pedidoEm && (
          <>
            <dt>Marcou às</dt>
            <dd>{new Date(pedido.pedidoEm).toLocaleString('pt-BR')}</dd>
          </>
        )}

        {pedido.retiradoEm && (
          <>
            <dt>Retirou às</dt>
            <dd>{new Date(pedido.retiradoEm).toLocaleString('pt-BR')}</dd>
          </>
        )}

        {pedido.restricaoAlimentar && (
          <>
            <dt>Restrição alimentar</dt>
            <dd>
              {comTextoDaRestricao ? (
                pedido.restricaoAlimentar
              ) : (
                // ⚠️ A coordenação vê que existe, não o quê. A revelação é
                // deliberada em `/cantina/direitos`, e um diálogo de conferência
                // não pode ser o caminho mais curto para contorná-la
                // (docs/38 §2.6).
                <>
                  Tem restrição registrada. O texto aparece em{' '}
                  <b>Alunos com direito</b>, onde revelá-lo é uma escolha.
                </>
              )}
            </dd>
          </>
        )}
      </dl>
    </Dialogo>
  );
}
