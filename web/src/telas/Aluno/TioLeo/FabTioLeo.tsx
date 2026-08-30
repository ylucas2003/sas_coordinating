import { useState } from 'react';

import { Icone } from '../pecas/Icone';
import { FolhaTioLeo } from './FolhaTioLeo';

// O botão flutuante do Tio Léo, presente em todas as abas do casco do aluno.
//
// Não é rota (docs/24 §7.1): a conversa abre por cima da tela onde o aluno já
// está, e fechá-la devolve exatamente o contexto de onde ele veio. Uma rota
// perderia isso e ainda poria o chat no histórico do navegador.
//
// ⚠️ A FOLHA FICA MONTADA MESMO FECHADA, e é de propósito. `Folha` devolve
// `null` quando `aberta` é falsa, então nada é desenhado — mas as threads já
// carregadas, a conversa escolhida e o estado de erro sobrevivem ao fecha-abre,
// que num celular acontece o tempo todo. Desmontar `FolhaTioLeo` faria o aluno
// pagar uma busca de conversas a cada toque no botão.
//
// ⚠️ E o botão continua montado com a folha aberta: `Folha` devolve o foco a
// quem a abriu quando fecha, e se o botão tivesse sumido quem usa teclado
// seria devolvido ao topo do documento.

export function FabTioLeo() {
  const [aberta, setAberta] = useState(false);

  return (
    <>
      <button
        type="button"
        className="alu-fab"
        aria-expanded={aberta}
        onClick={() => setAberta((v) => !v)}
      >
        <Icone nome="faisca" tamanho={26} />
        <span className="alu-so-leitor">Falar com o Tio Léo</span>
      </button>

      <FolhaTioLeo aberta={aberta} onFechar={() => setAberta(false)} />
    </>
  );
}
