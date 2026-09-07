import { useState } from 'react';

import { exportarPedidosCSV, exportarPedidosPDF } from './exportar';
import type { DiaExportavel } from './exportar';

// Os dois botões de exportar, iguais para a cantina e para a coordenação.
//
// Duas saídas porque são dois usos: o CSV vai para a planilha de quem fecha a
// conta do mês; o PDF é a folha que desce impressa para o balcão. Um menu
// "Exportar" com submenu esconderia dois cliques atrás de três.
//
// O erro do PDF aparece na tela, e não no console: a causa quase sempre é
// pop-up bloqueado, que é coisa que só quem está na frente do navegador
// resolve — e um clique que não faz nada, sem explicação, parece bug do
// produto.

export function BotoesDeExportar({ dia }: { dia: DiaExportavel }) {
  const [erro, setErro] = useState('');
  const vazio = dia.pedidos.length === 0;

  function proteger(acao: () => void) {
    setErro('');
    try {
      acao();
    } catch (e) {
      setErro((e as Error).message || 'Não consegui gerar o arquivo.');
    }
  }

  return (
    <span className="cant-exportar">
      <button
        type="button"
        className="cant-tecla cant-tecla--fina"
        disabled={vazio}
        title={vazio ? 'Nenhum pedido para exportar' : 'Planilha com pedidos e contagem'}
        onClick={() => proteger(() => exportarPedidosCSV(dia))}
      >
        CSV
      </button>
      <button
        type="button"
        className="cant-tecla cant-tecla--fina"
        disabled={vazio}
        title={vazio ? 'Nenhum pedido para exportar' : 'Folha para imprimir'}
        onClick={() => proteger(() => exportarPedidosPDF(dia))}
      >
        PDF
      </button>
      {erro && <span className="cant-exportar__erro" role="alert">{erro}</span>}
    </span>
  );
}
