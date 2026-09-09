import { lazy, Suspense } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';

import { useEventosDaCantina } from '../../hooks/eventosCantina';
import { Esqueleto } from '../../componentes/ui/Esqueleto';
import * as sessao from '../../servicos/sessao';
import { Calendario } from './Calendario';
import { CardapioDoDia } from './CardapioDoDia';
import { PedidosDoDia } from './PedidosDoDia';
import { PedidosPorData } from './PedidosPorData';

/**
 * A leitura de QR num pedaço próprio, porque ela arrasta o `jsqr` junto.
 *
 * A cantina passa a manhã em "Cardápios" e só liga a câmera na hora de servir.
 * Carregar o decodificador junto do calendário é pagar por ele todo dia de
 * manhã, quando ele só é usado ao meio-dia (docs/40 §12.1.4).
 */
const AoVivo = lazy(() => import('./AoVivo').then((m) => ({ default: m.AoVivo })));

// O casco da cantina — o TERCEIRO do produto, e deliberadamente o mais pobre.
//
// Marca, quem entrou, sair. Sem rail de cinco destinos, sem topbar com busca de
// aluno, sem sino, sem chat. Não é falta de acabamento: a cantina tem UM
// trabalho — lançar o cardápio e ler os pedidos do dia —, e todo elemento a
// mais aqui seria uma porta para uma tela que ela não pode abrir.
//
// ⚠️ Ele não conhece nenhuma rota da coordenação nem do aluno, e isso é a
// segunda camada da separação. A primeira é o servidor: `get_current_cantina`
// recusa qualquer outro tipo de sessão, e `get_current_coordenador` recusa a
// cantina (docs/38 §1). Se um dia alguém montar este casco por engano para
// outro tipo de conta, ele não terá o que mostrar — em vez de mostrar demais.

// ⚠️ TRÊS destinos são o teto desta barra. Em 390px, três rótulos com alvo de
// 44px cabem; o quarto obrigaria a virar só-ícone, e ícone sem rótulo em casco
// que se usa uma vez por dia é adivinhação. Se houver um quarto, a barra muda
// de desenho — não se aperta (docs/40 §12.8.2).
//
// Os trabalhos da cantina: LANÇAR o cardápio (de
// manhã, sentada) e SERVIR (ao meio-dia, de pé, com a câmera ligada). "Pedidos
// ao vivo" é destino de topo e não uma aba dentro do dia porque fica aberto o
// serviço inteiro — enterrá-lo em `/cardapios/:data/:refeicao` obrigaria a
// reencontrá-lo a cada recarregamento, com a fila esperando (docs/40 §7).
const DESTINOS = [
  { para: '/cardapios', rotulo: 'Cardápios' },
  // A terceira porta (docs/40 §12.8.2): a lista de quem vai comer, pela DATA
  // em vez de pelo calendário. As duas portas para a mesma lista são de
  // propósito — quem monta a semana chega pelo calendário, quem serve hoje
  // chega por aqui.
  { para: '/pedidos', rotulo: 'Visualizar pedidos' },
  // ⚠️ "Validar ENTREGA", e o substantivo custou uma conversa (docs/40 §12.8.1).
  //
  // "Ler" descreve o gesto; "validar" descreve o que acontece, e é o verbo de
  // quem está servindo. O substantivo é que exigiu cuidado: "pedido" seria
  // falso exatamente sobre as pessoas a quem o QR serve — quem chegou SEM ter
  // pedido. "Entrega" é verdade para os dois públicos.
  //
  // O comentário abaixo é o original, e continua explicando por que não é
  // "Pedidos ao vivo": aqui ninguém pediu nada — o
  // contador da própria tela conta RETIRADAS. E este é o destino mais visível
  // do casco, então o nome antigo levava quem queria conferir a lista de
  // pedidos a abrir a câmera, com pedido de permissão e tudo. O verbo diz o que
  // acontece ao clicar, que era justamente a surpresa.
  { para: '/ao-vivo', rotulo: 'Validar entrega' },
];

function sair() {
  sessao.encerrar();
  // `/login-cantina` e não `/login`: a cantina volta para a porta dela. Cair na
  // porta do aluno depois de sair seria pedir para ela tentar o Canvas.
  window.location.replace('/login-cantina');
}

export function CascoCantina() {
  const nome = sessao.nome();
  const cantina = sessao.nomeDaCantina();
  // No CASCO e não em cada tela: a assinatura precisa sobreviver à navegação
  // entre calendário, editor e pedidos. Montada por tela, ela cairia e
  // reconectaria a cada clique, e o servidor veria uma sessão nova por
  // navegação.
  useEventosDaCantina('/cantina/eventos');

  return (
    <div className="cant-shell">
      <header className="cant-topo">
        <span className="cant-marca">
          <span className="alu-marca" role="img" aria-label="Colégio Ari de Sá" />
          <span className="cant-marca__texto">
            <b>Cantina</b>
            {/* O nome do estabelecimento vem do login e fica no `sessionStorage`.
                Aparece porque no dia em que houver duas cantinas, saber em qual
                se está é a diferença entre lançar o cardápio certo e o errado. */}
            {cantina && <span className="cant-marca__sub">{cantina}</span>}
          </span>
        </span>

        <nav className="cant-nav" aria-label="Navegação da cantina">
          {DESTINOS.map((d) => (
            <NavLink key={d.para} to={d.para} className="cant-nav__link">
              {d.rotulo}
            </NavLink>
          ))}
        </nav>

        <div className="cant-topo__conta">
          <span className="cant-topo__nome">{nome}</span>
          <button type="button" className="cant-sair" onClick={sair}>Sair</button>
        </div>
      </header>

      <main className="cant-main">
        <Routes>
          <Route path="/" element={<Navigate to="/cardapios" replace />} />
          <Route path="/cardapios" element={<Calendario />} />
          {/* A URL é DATA + REFEIÇÃO, e não o id do cardápio, porque um dia
              ainda sem cardápio também precisa de endereço: é clicando nele que
              a cantina cria o primeiro. Com id na URL, o dia vazio não teria
              para onde apontar. */}
          <Route path="/cardapios/:data/:refeicao" element={<CardapioDoDia />} />
          <Route path="/cardapios/:data/:refeicao/pedidos" element={<PedidosDoDia />} />
          {/* A MESMA tela, por outra porta. Sem `:data/:refeicao` na URL: aqui
              a escolha é por campo, com hoje já preenchido, e a lista aparece
              sem clique (docs/40 §12.8.2). */}
          <Route path="/pedidos" element={<PedidosPorData />} />
          {/* `Suspense` local: o casco com a barra de destinos continua de pé
              enquanto o decodificador chega. No balcão, a tela sumir inteira
              por meio segundo pareceria queda. */}
          <Route
            path="/ao-vivo"
            element={<Suspense fallback={<Esqueleto />}><AoVivo /></Suspense>}
          />
          <Route path="*" element={<Navigate to="/cardapios" replace />} />
        </Routes>
      </main>
    </div>
  );
}
