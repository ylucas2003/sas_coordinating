import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import * as sessao from '../../servicos/sessao';
import { useTema } from '../../servicos/tema';
import { Avatar } from '../ui/Avatar';
import { useMigalhas } from './migalhas';

/**
 * Topbar da coordenação: migalhas, tema, identidade. Nada mais.
 *
 * ⚠️ A BUSCA GLOBAL E O SINO SAÍRAM (docs/39 §1, decisão 5). O sino apontava
 * para a âncora `#alertas` do Painel, que no desenho novo é praticamente a
 * tela inteira — um botão que leva para onde a pessoa já está. A busca de
 * navegação (com o atalho `/`) foi junto: ela era o segundo campo de busca do
 * produto e competia com a `<Busca>` da BarraFiltros, que é a que recorta a
 * tela em que se está. O caminho para a ficha de um aluno passa a ser a lista,
 * que é onde ele já estava documentado.
 */

function IconeSol() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.6v2.4M12 19v2.4M2.6 12h2.4M19 12h2.4M5.3 5.3l1.7 1.7M17 17l1.7 1.7M18.7 5.3L17 7M7 17l-1.7 1.7" />
    </svg>
  );
}

function IconeLua() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 14.2A8.4 8.4 0 0 1 9.8 4a8.4 8.4 0 1 0 10.2 10.2Z" />
    </svg>
  );
}

/**
 * Troca de tema da coordenação.
 *
 * Compartilha o estado com a área do aluno (`servicos/tema.ts`): o tema é um
 * atributo só na raiz, então não havia como serem dois. O botão diz para onde
 * VAI, não onde está — é o que se aperta.
 */
function BotaoTema() {
  const { tema, alternar } = useTema();
  const destino = tema === 'dia' ? 'escuro' : 'claro';
  return (
    <button
      className="topbar__tema"
      onClick={alternar}
      title={`Mudar para o tema ${destino}`}
      aria-label={`Mudar para o tema ${destino}`}
    >
      {tema === 'dia' ? <IconeLua /> : <IconeSol />}
    </button>
  );
}

/**
 * A identidade: quem está logado, e em que papel.
 *
 * É PLACA, não botão. O sair morava aqui, no avatar, e desceu para o rodapé do
 * rail, onde a conta agora está desenhada por inteiro — deixar os dois seria
 * duas portas para a mesma saída.
 *
 * O papel sai de `servicos/sessao`, que é quem sabe distinguir os dois da
 * coordenação. ⚠️ Sem flexão de gênero: a prancheta escreve "coordenadora"
 * porque a pessoa do mock é uma mulher, e o login não diz o gênero de quem
 * entrou — o papel aparece na forma em que a sessão o nomeia.
 */
function Identidade() {
  const nome = sessao.nome();
  const papel = sessao.ehAdministrador() ? 'administrador' : 'coordenador';
  return (
    <div className="topbar__identidade">
      <Avatar tipo="coordenador" proprio nome={nome} className="topbar__identidade-avatar" />
      <span className="topbar__identidade-papel">{nome ? `${nome} · ${papel}` : papel}</span>
    </div>
  );
}

export function Topbar() {
  const migalhas = useMigalhas();

  return (
    <header className="topbar">
      <nav className="topbar__migalhas" aria-label="Trilha de navegação">
        {migalhas.map((m, i) => (
          <Fragment key={`${m.texto}-${i}`}>
            {i > 0 && <span className="topbar__separador" aria-hidden="true">›</span>}
            {m.para ? (
              <Link className="topbar__migalha topbar__migalha--link" to={m.para}>
                {m.texto}
              </Link>
            ) : (
              // O último degrau é o TÍTULO da tela, e por isso pesa o triplo
              // dos outros. `useMigalhas` garante que só ele vem sem `para`.
              <span className="topbar__migalha topbar__migalha--atual" aria-current="page">
                {m.texto}
              </span>
            )}
          </Fragment>
        ))}
      </nav>

      <div className="topbar__acoes">
        <BotaoTema />
        <Identidade />
      </div>
    </header>
  );
}
