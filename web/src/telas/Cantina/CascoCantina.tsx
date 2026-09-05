import { NavLink, Navigate, Route, Routes } from 'react-router-dom';

import * as sessao from '../../servicos/sessao';
import { Calendario } from './Calendario';
import { CardapioDoDia } from './CardapioDoDia';
import { PedidosDoDia } from './PedidosDoDia';

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

const DESTINOS = [
  { para: '/cardapios', rotulo: 'Cardápios' },
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
          <Route path="*" element={<Navigate to="/cardapios" replace />} />
        </Routes>
      </main>
    </div>
  );
}
