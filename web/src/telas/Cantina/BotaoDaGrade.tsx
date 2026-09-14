import { useState } from 'react';

import { exportarGradeDaSemanaPDF } from './exportar';
import { obterCardapio } from '../../servicos/api';
import type { DiaDoCalendario } from '../../tipos/cantina';

/**
 * "Imprimir a grade" — o cardápio do período para o MURAL (docs/40 §12.5.3).
 *
 * ⚠️ **Busca os cardápios na hora do clique, e não antes.** O calendário traz
 * só o estado e a contagem de cada dia; os blocos e as opções ficam de fora de
 * propósito, porque a tela do mês não os mostra. Carregá-los adiantado seria
 * baixar o cardápio inteiro de trinta dias toda vez que alguém abre o
 * calendário, para servir um clique que quase nunca acontece — o oposto do que
 * a §12.1 acabou de consertar no resto do produto.
 *
 * ⚠️ **Uma requisição por dia publicado, e aqui isso é aceitável.** São no
 * máximo ~40 no mês, disparadas juntas, uma única vez, por ação explícita de
 * quem está esperando o papel sair. É diferente do N+1 da §12.1.3, que
 * acontecia a cada 60 segundos, para todo aluno, sem ninguém pedir.
 */
export function BotaoDaGrade({
  dias, cantina,
}: {
  dias: DiaDoCalendario[];
  cantina: string | null;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function imprimir() {
    setOcupado(true);
    setErro(null);
    try {
      const cardapios = await Promise.all(dias.map((d) => obterCardapio(d.id)));
      exportarGradeDaSemanaPDF(
        cardapios.map((c) => ({ data: c.data, refeicao: c.refeicao, blocos: c.blocos })),
        cantina,
      );
    } catch (e) {
      setErro((e as Error).message || 'Não deu para montar a grade.');
    } finally {
      setOcupado(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="cant-tecla cant-tecla--fina"
        // Desabilitado com o motivo à mostra no `title`: um botão cinza sem
        // explicação ensina a desconfiar da tela.
        disabled={!dias.length || ocupado}
        title={dias.length ? 'Cardápio do mês em uma folha, para imprimir' : 'Nenhum cardápio publicado neste mês'}
        onClick={imprimir}
      >
        {ocupado ? 'Montando…' : 'Imprimir a grade'}
      </button>
      {erro && <span className="cant-erro" role="alert">{erro}</span>}
    </>
  );
}
