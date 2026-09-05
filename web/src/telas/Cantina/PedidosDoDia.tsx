import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { ROTULO_DA_REFEICAO, ROTULO_DO_ESTADO, rotuloDoDia } from '../../dominio/cantina';
import { useCalendarioDaCantina, useContagem, usePedidosDoCardapio } from '../../hooks/cantina';
import type { ContagemDeOpcao, Refeicao } from '../../tipos/cantina';

// OS PEDIDOS DE UM DIA — e são DUAS leituras, porque são dois momentos.
//
//   · a CONTAGEM ("47 arroz, 31 feijão, 12 proteína de soja") é o que se lê de
//     manhã, para cozinhar;
//   · a LISTA POR ALUNO é o que se lê no balcão, ao meio-dia.
//
// Uma tela só com a lista obrigaria a cantina a contar no papel — que é
// exatamente o trabalho que este produto existe para tirar dela (docs/38 §5).
//
// ⚠️ **É tudo o que a cantina vê do aluno**: nome, turma e restrição alimentar.
// Nenhuma consulta desta tela toca nota, simulado ou ficha. São dados de
// menores, e a própria lista de pedidos já é informação sensível por tabela
// interposta — a escolha vegetariana insinua religião ou saúde (docs/38 §8.2.2).

type Aba = 'contagem' | 'lista';

export function PedidosDoDia() {
  const { data = '', refeicao = 'almoco' } = useParams<{ data: string; refeicao: Refeicao }>();
  const [aba, setAba] = useState<Aba>('contagem');

  const { data: doDia = [] } = useCalendarioDaCantina(data, data);
  const cardapio = doDia.find((d) => d.refeicao === refeicao);

  const { data: contagem = [] } = useContagem(cardapio?.id);
  const { data: pedidos = [], isLoading } = usePedidosDoCardapio(cardapio?.id);

  const porBloco = useMemo(() => agruparPorBloco(contagem), [contagem]);
  const comRestricao = pedidos.filter((p) => p.restricaoAlimentar).length;

  if (!cardapio) {
    return <p className="cant-vazio">Não há cardápio para este dia.</p>;
  }

  const final = cardapio.estado === 'fechado';

  return (
    <div className="cant-tela">
      <header className="cant-cabeca">
        <div>
          <Link className="cant-voltar" to={`/cardapios/${data}/${refeicao}`} aria-label="Voltar ao cardápio">‹</Link>
          <h1 className="cant-titulo">
            Pedidos · {ROTULO_DA_REFEICAO[refeicao]} de {rotuloDoDia(data)}
          </h1>
          <p className="cant-sub">
            {pedidos.length} pedido{pedidos.length === 1 ? '' : 's'}
            {' · '}
            {/* A frase muda com o estado porque a pergunta muda: antes do prazo
                o número ainda anda, depois dele é o que vai para o fogão. */}
            {final ? 'contagem final' : `ainda ${ROTULO_DO_ESTADO[cardapio.estado].toLowerCase()}`}
            {comRestricao > 0 && ` · ${comRestricao} com restrição alimentar`}
          </p>
        </div>

        <div className="cant-abas" role="tablist">
          <button
            type="button" role="tab" aria-selected={aba === 'contagem'}
            className={`cant-aba${aba === 'contagem' ? ' cant-aba--ativa' : ''}`}
            onClick={() => setAba('contagem')}
          >
            O que cozinhar
          </button>
          <button
            type="button" role="tab" aria-selected={aba === 'lista'}
            className={`cant-aba${aba === 'lista' ? ' cant-aba--ativa' : ''}`}
            onClick={() => setAba('lista')}
          >
            O que servir
          </button>
        </div>
      </header>

      {isLoading && <p className="cant-vazio">Carregando…</p>}

      {!isLoading && aba === 'contagem' && (
        <div className="cant-contagem">
          {porBloco.map(([bloco, linhas]) => (
            <section key={bloco} className="cant-bloco cant-bloco--leitura">
              <h2 className="cant-bloco__titulo">{bloco}</h2>
              <ul className="cant-contagem__lista">
                {linhas.map((linha) => (
                  <li
                    key={linha.opcao_id}
                    className={`cant-contagem__linha${linha.disponivel ? '' : ' cant-contagem__linha--fora'}`}
                  >
                    <span className="cant-contagem__nome">
                      {linha.opcao}
                      {!linha.disponivel && <span className="cant-tarja">acabou</span>}
                    </span>
                    {/* O número em magnitude: é o que se lê de longe, com a
                        mão na panela. */}
                    <span className="cant-contagem__numero">{linha.quantos}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {!porBloco.length && <p className="cant-vazio">Nenhum pedido ainda.</p>}
        </div>
      )}

      {!isLoading && aba === 'lista' && (
        <ul className="cant-lista">
          {pedidos.map((pedido) => (
            <li key={pedido.alunoId} className="cant-lista__linha">
              <div className="cant-lista__aluno">
                <b>{pedido.nome ?? '—'}</b>
                {pedido.turma && <span className="cant-lista__turma">{pedido.turma}</span>}
              </div>
              <div className="cant-lista__escolhas">{pedido.escolhas.join(' · ') || '—'}</div>
              {/* A restrição fica em destaque, e não numa coluna qualquer: é a
                  informação que muda o que sai do balcão. */}
              {pedido.restricaoAlimentar && (
                <div className="cant-lista__restricao">⚠ {pedido.restricaoAlimentar}</div>
              )}
            </li>
          ))}
          {!pedidos.length && <p className="cant-vazio">Nenhum pedido ainda.</p>}
        </ul>
      )}
    </div>
  );
}

/** Agrupa preservando a ordem do cardápio — que já vem ordenada do servidor. */
function agruparPorBloco(contagem: ContagemDeOpcao[]): Array<[string, ContagemDeOpcao[]]> {
  const mapa = new Map<string, ContagemDeOpcao[]>();
  for (const linha of contagem) {
    const atual = mapa.get(linha.bloco);
    if (atual) atual.push(linha);
    else mapa.set(linha.bloco, [linha]);
  }
  return [...mapa.entries()];
}
