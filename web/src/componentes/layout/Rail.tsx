import { useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { caminhoNoBloco, destinoDoCaminho, rotuloDoBloco, serieDoCaminho } from '../../dominio/blocos';
import type { SerieDoBloco } from '../../dominio/blocos';
import { useBlocos } from '../../hooks/consultas';
import * as sessao from '../../servicos/sessao';
import type { BlocoDaCoordenacao } from '../../tipos/dominio';
import { Avatar } from '../ui/Avatar';
import { useSerieDaTela } from './migalhas';

/**
 * Rail de navegação: ícone e rótulo, SEMPRE.
 *
 * ⚠️ Ele não abre mais. Era 88px que viravam 228px no `:hover` do CSS, e a
 * decisão 7 do docs/39 o fixou em 252px. O custo está registrado e é aceito —
 * 164px a menos de largura em toda tela, o tempo todo, inclusive na tabela de
 * 900 linhas. O que se compra é o rótulo legível sem depender de hover, que em
 * toque não existe: no celular o rail vira barra inferior e ali nunca houve
 * como consultar o nome do destino.
 *
 * Tem duas formas (docs/44 §1). Com um bloco só, são os cinco destinos de sempre.
 * Com 1º ou 2º ano na plataforma, cada série vira um bloco à vista, com o próprio
 * Painel, Alunos e Provas: não existe modo escondido, então ninguém olha a turma
 * errada sem perceber. Banco e Administração valem para todas e ficam fora.
 */

const DESTINOS = [
  { caminho: '/painel', label: 'Painel', icone: IconePainel },
  { caminho: '/alunos', label: 'Alunos', icone: IconeAlunos },
  { caminho: '/provas', label: 'Provas', icone: IconeProvas },
  { caminho: '/banco', label: 'Banco', icone: IconeBanco },
  { caminho: '/administracao', label: 'Administração', icone: IconeAdmin },
];
const DESTINOS_DO_BLOCO = DESTINOS.slice(0, 3);
const DESTINOS_COMUNS = DESTINOS.slice(3);

/** Preferência de quem usa, e só dela: guardada no navegador, e pode faltar. */
const CHAVE_DOS_FECHADOS = 'sas_rail_blocos_fechados';

function lerFechados(): SerieDoBloco[] {
  try {
    const salvo: unknown = JSON.parse(localStorage.getItem(CHAVE_DOS_FECHADOS) ?? '[]');
    return Array.isArray(salvo) ? (salvo as SerieDoBloco[]) : [];
  } catch {
    return [];
  }
}

function gravarFechados(fechados: SerieDoBloco[]) {
  try {
    localStorage.setItem(CHAVE_DOS_FECHADOS, JSON.stringify(fechados));
  } catch {
    // Sem armazenamento, o bloco só não lembra: nada para quem usa consertar.
  }
}

export function Rail() {
  const { data: blocos = [] } = useBlocos();
  return blocos.length > 1 ? <RailEmBlocos blocos={blocos} /> : <RailDeUmBloco />;
}

/** A marca do colégio, e o olho que diz de que produto esta janela é. */
function Marca() {
  return (
    <div className="rail__marca">
      {/* O asterisco do SAS saiu: era um símbolo inventado ao lado de uma marca de
          verdade, e a prancheta desenha só a do Ari. Não é link — "Painel" está
          logo abaixo e um segundo caminho para o mesmo lugar não é atalho, é ruído. */}
      <span className="rail__logo" role="img" aria-label="Colégio Ari de Sá Cavalcante" />
      <span className="rail__olho">Coordenação</span>
    </div>
  );
}

function Conta() {
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
  );
}

function RailDeUmBloco() {
  return (
    <nav className="rail" aria-label="Navegação principal">
      <Marca />
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
      <Conta />
    </nav>
  );
}

function RailEmBlocos({ blocos }: { blocos: readonly BlocoDaCoordenacao[] }) {
  const { pathname } = useLocation();
  const serieAtual = useSerieDaTela();
  const destinoAtual = destinoDoCaminho(pathname);
  const [fechados, setFechados] = useState<SerieDoBloco[]>(lerFechados);

  function alternar(serie: SerieDoBloco) {
    const proximos = fechados.includes(serie)
      ? fechados.filter((s) => s !== serie)
      : [...fechados, serie];
    setFechados(proximos);
    gravarFechados(proximos);
  }

  return (
    <nav className="rail rail--em-blocos" aria-label="Navegação principal">
      <Marca />

      {/* A lista rola, e a conta fica: com tudo aberto o rail passa da altura de um
          notebook, e o Sair não pode sair da tela (docs/44 §4). */}
      <div className="rail__lista">
        {blocos.map(({ serie, alunos, alertas }) => {
          const aberto = !fechados.includes(serie);
          const noBloco = serieAtual === serie;
          const corpoId = `rail-bloco-${serie}`;
          return (
            <section
              key={serie}
              // `is-no-celular` não depende do destino: em Banco, a barra inferior do
              // celular continua mostrando o bloco de onde se veio.
              className={`rail__bloco${noBloco && destinoAtual ? ' is-atual' : ''}${
                serie === serieDoCaminho(pathname) ? ' is-no-celular' : ''
              }`}
              aria-label={rotuloDoBloco(serie)}
            >
              <button
                type="button"
                className="rail__bloco-cabeca"
                aria-expanded={aberto}
                aria-controls={corpoId}
                onClick={() => alternar(serie)}
              >
                <span className="rail__bloco-texto">
                  <span className="rail__bloco-nome">{rotuloDoBloco(serie)}</span>
                  <span className="rail__bloco-contagem">
                    {`${alunos.toLocaleString('pt-BR')} ${alunos === 1 ? 'aluno' : 'alunos'}`}
                  </span>
                </span>
                {/* Recolhido, o bloco ainda avisa: é o que torna seguro recolher. */}
                {!aberto && alertas > 0 && <SeloDeAlertas alertas={alertas} />}
                <IconeSeta />
              </button>

              <div className="rail__bloco-corpo" id={corpoId} hidden={!aberto}>
                {DESTINOS_DO_BLOCO.map(({ caminho, label, icone: Icone }) => {
                  const ativo = noBloco && destinoAtual === caminho.slice(1);
                  return (
                    <Link
                      key={caminho}
                      to={caminhoNoBloco(serie, caminho)}
                      className={`rail__item${ativo ? ' is-active' : ''}`}
                      aria-current={ativo ? 'page' : undefined}
                    >
                      <span className="rail__icone">
                        <Icone />
                      </span>
                      <span className="rail__label">{label}</span>
                      {caminho === '/painel' && alertas > 0 && <SeloDeAlertas alertas={alertas} />}
                    </Link>
                  );
                })}
              </div>
            </section>
          );
        })}

        {DESTINOS_COMUNS.map(({ caminho, label, icone: Icone }) => (
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
      </div>

      <Conta />
    </nav>
  );
}

function SeloDeAlertas({ alertas }: { alertas: number }) {
  return (
    // O número sozinho não diz nada ao leitor de tela, e `aria-label` não vale em
    // `<span>`: a frase vai escrita, escondida da vista.
    <span className="rail__selo">
      <span aria-hidden="true">{alertas}</span>
      <span className="rail__selo-leitura">
        {`${alertas} ${alertas === 1 ? 'alerta aberto' : 'alertas abertos'}`}
      </span>
    </span>
  );
}

function IconeSeta() {
  return (
    <svg
      className="rail__bloco-seta"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
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
