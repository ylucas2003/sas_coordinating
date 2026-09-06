import { NavLink, useNavigate } from 'react-router-dom';
import * as sessao from '../../servicos/sessao';
import { Avatar } from '../ui/Avatar';

/**
 * Rail de navegação: cinco destinos, ícone e rótulo, SEMPRE.
 *
 * ⚠️ Ele não abre mais. Era 88px que viravam 228px no `:hover` do CSS, e a
 * decisão 7 do docs/39 o fixou em 252px. O custo está registrado e é aceito —
 * 164px a menos de largura em toda tela, o tempo todo, inclusive na tabela de
 * 900 linhas. O que se compra é o rótulo legível sem depender de hover, que em
 * toque não existe: no celular o rail vira barra inferior e ali nunca houve
 * como consultar o nome do destino.
 *
 * Com a largura fixa, o `useState` que esta nota antes proibia deixou de ser
 * tentação: não há mais estado nenhum aqui além da sessão.
 */

const DESTINOS = [
  { caminho: '/painel', label: 'Painel', icone: IconePainel },
  { caminho: '/alunos', label: 'Alunos', icone: IconeAlunos },
  { caminho: '/provas', label: 'Provas', icone: IconeProvas },
  { caminho: '/banco', label: 'Banco', icone: IconeBanco },
  { caminho: '/administracao', label: 'Administração', icone: IconeAdmin },
];

export function Rail() {
  const navegar = useNavigate();
  const nome = sessao.nome();

  // Mesmo `encerrar()` que o aluno já usa; o coordenador não tinha o botão
  // ("tem um botão de sair? como faz para deslogar?" — 21/08, 18h54). Ele
  // morava no avatar da topbar e desceu para cá junto com a conta: a pílula
  // de identidade lá em cima virou placa, não botão.
  function sair() {
    sessao.encerrar();
    navegar('/login', { replace: true });
  }

  return (
    <nav className="rail" aria-label="Navegação principal">
      {/* A marca do colégio, e o olho que diz de que produto esta janela é.
          O asterisco do SAS saiu: era um símbolo inventado ao lado de uma
          marca de verdade, e a prancheta desenha só a do Ari. Não é link —
          "Painel" está logo abaixo e um segundo caminho para o mesmo lugar
          não é atalho, é ruído. */}
      <div className="rail__marca">
        <span className="rail__logo" role="img" aria-label="Colégio Ari de Sá Cavalcante" />
        <span className="rail__olho">Coordenação</span>
      </div>

      {/* `NavLink` já estampa `aria-current="page"` no item ativo — é o que
          diz ao leitor de tela o que o preenchimento da pílula diz aos olhos. */}
      {DESTINOS.map(({ caminho, label, icone: Icone }) => (
        <NavLink
          key={caminho}
          to={caminho}
          className={({ isActive }) => `rail__item${isActive ? ' is-active' : ''}`}
        >
          <span className="rail__icone">
            <Icone />
          </span>
          <span className="rail__label">{label}</span>
        </NavLink>
      ))}

      <span className="rail__espaco" />

      <div className="rail__usuario">
        <Avatar tipo="coordenador" proprio nome={nome} className="rail__avatar" />
        <span className="rail__usuario-nome">{nome}</span>
        <button
          className="rail__sair"
          onClick={sair}
          title={nome ? `Sair (${nome})` : 'Sair'}
          aria-label={nome ? `Sair da conta de ${nome}` : 'Sair'}
        >
          <IconeSair />
        </button>
      </div>
    </nav>
  );
}

// ─── Ícones ────────────────────────────────────────────────────────────────
// Todos no mesmo grid de 20×20 com traço 1.6: é o que faz seis desenhos de
// origens diferentes lerem como um conjunto.

function svgProps() {
  return {
    width: 20,
    height: 20,
    viewBox: '0 0 20 20',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    'aria-hidden': true,
  } as const;
}

function IconePainel() {
  return (
    <svg {...svgProps()}>
      <rect x="2.5" y="2.5" width="6" height="6" rx="1.6" />
      <rect x="11.5" y="2.5" width="6" height="6" rx="1.6" />
      <rect x="2.5" y="11.5" width="6" height="6" rx="1.6" />
      <rect x="11.5" y="11.5" width="6" height="6" rx="1.6" />
    </svg>
  );
}

function IconeAlunos() {
  return (
    <svg {...svgProps()}>
      <circle cx="8" cy="6.5" r="3" />
      <path d="M2.5 16.5c0-3 2.5-4.6 5.5-4.6s5.5 1.6 5.5 4.6" />
      <path d="M14 4.4a3 3 0 0 1 0 5.6" />
      <path d="M15.4 12.3c1.4.6 2.3 1.9 2.3 4.2" />
    </svg>
  );
}

function IconeProvas() {
  return (
    <svg {...svgProps()}>
      <rect x="4" y="3.5" width="12" height="14" rx="2.2" />
      <rect x="7.2" y="1.8" width="5.6" height="3.2" rx="1.4" />
      <path d="M7.4 9.5h5.2M7.4 13h3.4" />
    </svg>
  );
}

function IconeBanco() {
  return (
    <svg {...svgProps()}>
      <ellipse cx="10" cy="5" rx="6.2" ry="2.6" />
      <path d="M3.8 5v5c0 1.4 2.8 2.6 6.2 2.6s6.2-1.2 6.2-2.6V5" />
      <path d="M3.8 10v5c0 1.4 2.8 2.6 6.2 2.6s6.2-1.2 6.2-2.6v-5" />
    </svg>
  );
}

function IconeAdmin() {
  return (
    <svg {...svgProps()}>
      <circle cx="10" cy="10" r="2.6" />
      <path d="M10 2.2v2M10 15.8v2M17.8 10h-2M4.2 10h-2M15.5 4.5l-1.4 1.4M5.9 14.1l-1.4 1.4M15.5 15.5l-1.4-1.4M5.9 5.9L4.5 4.5" />
    </svg>
  );
}

function IconeSair() {
  return (
    <svg {...svgProps()} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.4 5.8V4.2a1.6 1.6 0 0 0-1.6-1.6H4.2a1.6 1.6 0 0 0-1.6 1.6v11.6a1.6 1.6 0 0 0 1.6 1.6h6.6a1.6 1.6 0 0 0 1.6-1.6v-1.6" />
      <path d="M7.6 10h9.8M14.6 7.2 17.4 10l-2.8 2.8" />
    </svg>
  );
}
