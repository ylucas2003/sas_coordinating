import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import {
  instrucaoDoBloco, prazoLegivel, ROTULO_DA_REFEICAO, ROTULO_DO_ESTADO, rotuloDoDia,
} from '../../dominio/cantina';
import { useCalendarioNaCoordenacao, useCardapioNaCoordenacao } from '../../hooks/cantina';
import type { Refeicao } from '../../tipos/cantina';
import { GradeDeCardapios, janelaDoMes, NavegadorDeMes } from './GradeDeCardapios';

// A CANTINA VISTA PELA COORDENAÇÃO — leitura, e só.
//
// Nenhum botão de publicar, criar ou editar: publicar é da cantina, e um
// coordenador publicando em nome dela apagaria a autoria de
// `cardapio.criado_por`. O servidor recusa de qualquer jeito
// (`get_current_cantina` não aceita sessão de coordenação); a tela não oferece,
// que é a metade que evita a pessoa descobrir o limite por 403.
//
// A grade é a MESMA da cantina (`GradeDeCardapios`) — o que muda é o destino do
// clique e o fato de o dia sem cardápio ficar inerte, porque a coordenação não
// cria cardápio nenhum.

export function CantinaCoordenacao() {
  const hoje = new Date();
  const [ano, setAno] = useState(hoje.getFullYear());
  const [mes, setMes] = useState(hoje.getMonth());

  const [de, ate] = useMemo(() => janelaDoMes(ano, mes), [ano, mes]);
  const { data: dias = [], isLoading, isError } = useCalendarioNaCoordenacao(de, ate);

  function andar(passo: number) {
    const d = new Date(ano, mes + passo, 1);
    setAno(d.getFullYear());
    setMes(d.getMonth());
  }

  const pedidos = dias.reduce((soma, d) => soma + d.pedidos, 0);
  const rascunhos = dias.filter((d) => d.estado === 'rascunho').length;

  return (
    <div className="tela">
      <header className="cant-cabeca">
        <div>
          <h1 className="cant-titulo">Cantina</h1>
          <p className="cant-sub">
            {isError
              ? 'Não consegui carregar o mês.'
              : isLoading
                ? 'Carregando…'
                : `${pedidos} pedido${pedidos === 1 ? '' : 's'} no mês`
                  + (rascunhos ? ` · ${rascunhos} dia(s) em rascunho` : '')}
          </p>
        </div>
        <NavegadorDeMes ano={ano} mes={mes} onAndar={andar} />
      </header>

      <GradeDeCardapios
        ano={ano}
        mes={mes}
        dias={dias}
        // Dia sem cardápio fica inerte: a coordenação lê, não lança.
        href={(data, refeicao, dia) => (dia ? `/cantina/${data}/${refeicao}` : null)}
      />
    </div>
  );
}

/** Um dia inteiro: o cardápio, o que foi pedido de cada coisa, e por quem. */
export function CardapioNaCoordenacao() {
  const { data = '', refeicao = 'almoco' } = useParams<{ data: string; refeicao: Refeicao }>();
  const { data: dias = [] } = useCalendarioNaCoordenacao(data, data);
  const doDia = dias.find((d) => d.refeicao === refeicao);
  const { data: cardapio, isLoading } = useCardapioNaCoordenacao(doDia?.id);

  if (isLoading) return <div className="tela"><p className="cant-vazio">Carregando…</p></div>;
  if (!cardapio) {
    return (
      <div className="tela">
        <p className="cant-vazio">A cantina ainda não lançou este dia.</p>
      </div>
    );
  }

  return (
    <div className="tela">
      <header className="cant-cabeca">
        <div>
          <Link className="cant-voltar" to="/cantina" aria-label="Voltar à cantina">‹</Link>
          <h1 className="cant-titulo">
            {ROTULO_DA_REFEICAO[refeicao]} · {rotuloDoDia(data)}
          </h1>
          <p className="cant-sub">
            {ROTULO_DO_ESTADO[cardapio.estado]}
            {cardapio.pedidos_ate && ` · ${prazoLegivel(cardapio.pedidos_ate)}`}
            {` · ${cardapio.pedidos.length} pedido${cardapio.pedidos.length === 1 ? '' : 's'}`}
          </p>
        </div>
      </header>

      <section className="cant-colunas">
        <div>
          <h2 className="cant-secao__titulo">O cardápio</h2>
          {cardapio.blocos.map((bloco) => (
            <section key={bloco.id} className="cant-bloco cant-bloco--leitura">
              <h3 className="cant-bloco__titulo">
                {bloco.nome}
                <span className="cant-bloco__instrucao">{instrucaoDoBloco(bloco)}</span>
              </h3>
              <ul className="cant-opcoes cant-opcoes--leitura">
                {bloco.opcoes.map((opcao) => (
                  <li key={opcao.id} className={opcao.disponivel ? '' : 'cant-contagem__linha--fora'}>
                    {opcao.nome}
                    {!opcao.disponivel && <span className="cant-tarja">acabou</span>}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <div>
          <h2 className="cant-secao__titulo">O que foi pedido</h2>
          <ul className="cant-contagem__lista">
            {cardapio.contagem.map((linha) => (
              <li key={linha.opcao_id} className="cant-contagem__linha">
                <span className="cant-contagem__nome">
                  <span className="cant-contagem__bloco">{linha.bloco}</span>
                  {linha.opcao}
                </span>
                <span className="cant-contagem__numero">{linha.quantos}</span>
              </li>
            ))}
            {!cardapio.contagem.length && <li className="cant-vazio">Nenhum pedido ainda.</li>}
          </ul>
        </div>
      </section>
    </div>
  );
}
