import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAlunos, useTurmas } from '../../hooks/consultas';

const ABAS = [
  { caminho: '/painel', label: 'Painel' },
  { caminho: '/alunos', label: 'Alunos' },
  { caminho: '/simulados', label: 'Simulados' },
  { caminho: '/ciclos', label: 'Ciclos' },
  { caminho: '/auditoria', label: 'Auditoria' },
];

const MAX_RESULTADOS = 8;

function normalizar(s: string): string {
  return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

function IconeAsterisco() {
  return (
    <svg
      width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"
    >
      <line x1="12" y1="2" x2="12" y2="22" />
      <line x1="3" y1="7" x2="21" y2="17" />
      <line x1="21" y1="7" x2="3" y2="17" />
    </svg>
  );
}

function IconeBusca() {
  return (
    <svg
      width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

/** Busca global de alunos, com navegação por teclado e atalho "/". */
function BuscaAlunos() {
  const navegar = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [termo, setTermo] = useState('');
  const [aberta, setAberta] = useState(false);
  const [ativo, setAtivo] = useState(-1);

  // Só busca dados depois que o usuário mexe na busca — a topbar aparece em
  // toda tela, e carregar a lista inteira de alunos no boot seria desperdício.
  // (A topbar antiga fazia o mesmo, com um cache manual em `carregarDadosBusca`.)
  const [ligada, setLigada] = useState(false);
  const { data: alunos = [] } = useAlunos({ habilitada: ligada });
  const { data: turmas = [] } = useTurmas({ habilitada: ligada });

  const turmaPorId = useMemo(() => new Map(turmas.map((t) => [t.id, t])), [turmas]);

  const resultados = useMemo(() => {
    const q = termo.trim();
    if (!q) return [];
    const nq = normalizar(q);
    return alunos.filter((a) => normalizar(a.nome).includes(nq)).slice(0, MAX_RESULTADOS);
  }, [termo, alunos, ligada]);

  // Atalho global: "/" foca a busca de qualquer tela.
  useEffect(() => {
    function aoTeclar(ev: KeyboardEvent) {
      if (ev.key !== '/' || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const alvo = ev.target as HTMLElement | null;
      if (alvo && (alvo.tagName === 'INPUT' || alvo.tagName === 'TEXTAREA' || alvo.isContentEditable)) {
        return;
      }
      ev.preventDefault();
      inputRef.current?.focus();
    }
    document.addEventListener('keydown', aoTeclar);
    return () => document.removeEventListener('keydown', aoTeclar);
  }, []);

  function abrir() {
    setLigada(true);
    setAberta(true);
  }

  function fechar() {
    setAberta(false);
    setAtivo(-1);
  }

  function irPara(id: string) {
    navegar(`/alunos/${id}`);
    fechar();
    setTermo('');
    inputRef.current?.blur();
  }

  function aoTeclarNaBusca(ev: React.KeyboardEvent<HTMLInputElement>) {
    if (ev.key === 'Escape') {
      fechar();
      inputRef.current?.blur();
    } else if (ev.key === 'ArrowDown' && resultados.length) {
      ev.preventDefault();
      setAtivo((i) => Math.min(i + 1, resultados.length - 1));
    } else if (ev.key === 'ArrowUp' && resultados.length) {
      ev.preventDefault();
      setAtivo((i) => Math.max(i - 1, 0));
    } else if (ev.key === 'Enter') {
      const alvo = resultados[ativo >= 0 ? ativo : 0];
      if (alvo) irPara(alvo.id);
    }
  }

  const mostrarResultados = aberta && termo.trim().length > 0;

  return (
    <div className="topbar__busca">
      <IconeBusca />
      <input
        ref={inputRef}
        className="topbar__busca-input"
        type="text"
        placeholder="Buscar aluno…"
        aria-label="Buscar aluno"
        value={termo}
        onChange={(ev) => {
          setTermo(ev.target.value);
          setAtivo(-1);
          abrir();
        }}
        onFocus={abrir}
        // Atraso para o clique num resultado acontecer antes do fechamento.
        onBlur={() => window.setTimeout(fechar, 120)}
        onKeyDown={aoTeclarNaBusca}
      />
      <span className="topbar__busca-atalho">/</span>

      <div className={`topbar__busca-resultados${mostrarResultados ? ' is-aberto' : ''}`}>
        {mostrarResultados && resultados.length === 0 && (
          <div className="topbar__busca-vazio">Nenhum aluno encontrado.</div>
        )}
        {mostrarResultados &&
          resultados.map((a, i) => {
            const turma = turmaPorId.get(a.turmaId);
            return (
              <a
                key={a.id}
                className={`topbar__busca-item${i === ativo ? ' is-ativo' : ''}`}
                href={`/alunos/${a.id}`}
                // Evita o blur fechar a lista antes do clique registrar.
                onMouseDown={(ev) => ev.preventDefault()}
                onClick={(ev) => {
                  ev.preventDefault();
                  irPara(a.id);
                }}
              >
                <span className="topbar__busca-item-nome">{a.nome}</span>
                {turma && <span className="topbar__busca-item-sub">{turma.nome}</span>}
              </a>
            );
          })}
      </div>
    </div>
  );
}

export function Topbar() {
  return (
    <header className="topbar">
      <div className="topbar__brand">
        <div className="topbar__logo">
          <IconeAsterisco />
        </div>
        <div className="topbar__brand-text">
          <span className="topbar__brand-name">SAS</span>
          <span className="topbar__brand-sub">coordenação ITM</span>
        </div>
      </div>

      <nav className="topbar__nav">
        {ABAS.map((aba) => (
          <NavLink
            key={aba.caminho}
            to={aba.caminho}
            className={({ isActive }) => `topbar__tab${isActive ? ' is-active' : ''}`}
          >
            {aba.label}
          </NavLink>
        ))}
      </nav>

      <div className="topbar__actions">
        <BuscaAlunos />
        <NavLink
          className="topbar__action topbar__action--primary"
          to="/importar"
          title="Importar planilha do Canvas"
        >
          Importar planilha
        </NavLink>
      </div>
    </header>
  );
}
