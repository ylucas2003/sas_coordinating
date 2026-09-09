import { useMemo, useState } from 'react';

import { BotoesDeExportar } from './BotoesDeExportar';
import { ListaDeQuemVaiComer } from './ListaDeQuemVaiComer';
import {
  contagemPorModo, fraseDaQuebra, isoDoDia, quebraDaContagem,
  refeicaoPorHorario, ROTULO_DA_REFEICAO, rotuloDaContagem, rotuloDoDia,
} from '../../dominio/cantina';
import {
  useCalendarioDaCantina, useContagem, useMinhaCantina, usePedidosDoCardapio,
} from '../../hooks/cantina';
import type { PedidoDeAluno, Refeicao } from '../../tipos/cantina';

/**
 * "Visualizar pedidos" — a lista de quem vai comer, pela DATA (docs/40 §12.8.2).
 *
 * ⚠️ **É a mesma tela que `/cardapios/:data/:refeicao/pedidos`, por outra
 * porta, e as duas continuam existindo de propósito.** O calendário é o caminho
 * de quem está montando a semana; a data é o caminho de quem está servindo
 * hoje. Mesma pergunta, momentos diferentes — e enterrar a segunda dentro da
 * primeira obriga a atravessar um mês para chegar ao almoço de agora.
 *
 * Os dois campos nascem preenchidos — hoje, e a refeição do horário — para a
 * lista aparecer **sem nenhum clique**. É o que se olha 90% das vezes; pedir
 * dois cliques por isso seria cobrar pelo caso comum para servir o raro.
 */
const REFEICOES: Refeicao[] = ['almoco', 'janta'];

export function PedidosPorData() {
  const hoje = useMemo(() => isoDoDia(new Date()), []);
  const [data, setData] = useState(hoje);
  // A refeição do horário: antes das 15h, almoço. É PALPITE, e a tela deixa
  // trocar num toque — o mesmo raciocínio de `AoVivo`.
  const [refeicao, setRefeicao] = useState<Refeicao>(() => refeicaoPorHorario(new Date()));
  const [pedidosNaTela, setPedidosNaTela] = useState<PedidoDeAluno[]>([]);

  // O calendário do DIA, só para descobrir o id do cardápio: a URL aqui é a
  // data, e o id é detalhe de banco que a cantina não digita.
  const { data: dias = [], isLoading: carregandoDia } = useCalendarioDaCantina(data, data);
  const doDia = dias.find((d) => d.refeicao === refeicao);

  const { data: pedidos = [], isLoading } = usePedidosDoCardapio(doDia?.id);
  const { data: contagem } = useContagem(doDia?.id);
  const { data: minha } = useMinhaCantina();

  const valor = refeicao === 'almoco' ? minha?.valor_almoco : minha?.valor_janta;
  const total = contagemPorModo(pedidos);
  const quebra = quebraDaContagem(total);

  return (
    <div className="tela">
      <header className="cant-cabeca">
        <div>
          <h1 className="cant-titulo">Visualizar pedidos</h1>
          <p className="cant-sub">
            {rotuloDoDia(data)} · {ROTULO_DA_REFEICAO[refeicao]}
            {!carregandoDia && !doDia && ' · sem cardápio lançado'}
          </p>
        </div>

        <div className="cant-cabeca__acoes">
          {/* O botão fica no TOPO, como você pediu, e leva o recorte da tela —
              não a lista inteira (docs/40 §12.4). */}
          <BotoesDeExportar
            dia={{
              data, refeicao,
              pedidos: pedidosNaTela,
              contagem: contagem?.opcoes ?? [],
              cantina: minha?.nome ?? null,
              valor: valor ?? null,
              // O balcão leva o texto da restrição: é o que muda o prato.
              incluirRestricao: true,
            }}
          />
        </div>
      </header>

      <div className="cant-escolha-do-dia">
        <label className="cant-campo">
          <span className="cant-campo__rotulo">Dia</span>
          <input
            className="cant-input"
            type="date"
            value={data}
            onChange={(e) => setData(e.target.value || hoje)}
          />
        </label>

        <div className="cant-campo">
          <span className="cant-campo__rotulo">Refeição</span>
          <div className="cant-abas">
            {REFEICOES.map((r) => (
              <button
                key={r}
                type="button"
                className={`cant-aba${r === refeicao ? ' cant-aba--ativa' : ''}`}
                onClick={() => setRefeicao(r)}
              >
                {ROTULO_DA_REFEICAO[r]}
              </button>
            ))}
          </div>
        </div>

        {/* "Hoje" só aparece quando não é hoje: um botão que não faz nada
            ensina a desconfiar do resto da tela. */}
        {data !== hoje && (
          <button type="button" className="cant-tecla cant-tecla--fina" onClick={() => setData(hoje)}>
            Voltar para hoje
          </button>
        )}
      </div>

      {carregandoDia && <p className="cant-vazio">Carregando…</p>}

      {!carregandoDia && !doDia && (
        <p className="cant-vazio">
          Nenhum cardápio lançado para {rotuloDoDia(data)} · {ROTULO_DA_REFEICAO[refeicao]}.
        </p>
      )}

      {doDia && !isLoading && (
        <>
          <p className="cant-intro">
            {pedidos.length} {rotuloDaContagem(total)}
            {quebra && ` · ${fraseDaQuebra(quebra)}`}
          </p>

          <ListaDeQuemVaiComer
            pedidos={pedidos}
            superficie="cantina.pedidos.balcao"
            comTextoDaRestricao
            refeicao={refeicao}
            data={data}
            onRecorte={setPedidosNaTela}
          />
        </>
      )}
    </div>
  );
}
