import { NavLink } from 'react-router-dom';
// Asset local — nada de CDN (CLAUDE.md, regra 6: dados de menores).
import ariLogo from '../../../assets/ari-logo.png';

/**
 * Rail de navegação: cinco destinos, ícone sempre, rótulo quando aberto.
 *
 * Quem abre o rail é o CSS (`.rail:hover`, `.rail:focus-within`) e não o
 * React: um `useState` aqui remontaria a árvore inteira a cada passada de
 * mouse, e o estado não sobrevive à navegação de todo jeito.
 */

const DESTINOS = [
  { caminho: '/painel', label: 'Painel', icone: IconePainel },
  { caminho: '/alunos', label: 'Alunos', icone: IconeAlunos },
  { caminho: '/provas', label: 'Provas', icone: IconeProvas },
  { caminho: '/banco', label: 'Banco', icone: IconeBanco },
  { caminho: '/administracao', label: 'Administração', icone: IconeAdmin },
];

export function Rail() {
  return (
    <nav className="rail" aria-label="Navegação principal">
      <NavLink className="rail__marca" to="/painel">
        <span className="rail__logo">
          <IconeAsterisco />
        </span>
        <span className="rail__marca-texto">
          <span className="rail__marca-nome">SAS</span>
          <span className="rail__marca-sub">coordenação ITM</span>
        </span>
      </NavLink>

      {DESTINOS.map(({ caminho, label, icone: Icone }) => (
        <NavLink
          key={caminho}
          to={caminho}
          title={label}
          className={({ isActive }) => `rail__item${isActive ? ' is-active' : ''}`}
        >
          <span className="rail__icone">
            <Icone />
          </span>
          {/* O rótulo fica sempre na árvore, só transparente quando fechado —
              é ele que o leitor de tela anuncia. */}
          <span className="rail__label">{label}</span>
        </NavLink>
      ))}

      <span className="rail__espaco" />

      {/* "seria bom colocar o LOGO do Ari tb" — 21/08, 18h54. */}
      <img className="rail__ari" src={ariLogo} alt="Colégio Ari de Sá Cavalcante" />
    </nav>
  );
}

// ─── Ícones ────────────────────────────────────────────────────────────────
// Todos no mesmo grid de 20×20 com traço 1.6: é o que faz cinco desenhos de
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

function IconeAsterisco() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
      <line x1="12" y1="2" x2="12" y2="22" />
      <line x1="3" y1="7" x2="21" y2="17" />
      <line x1="21" y1="7" x2="3" y2="17" />
    </svg>
  );
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
