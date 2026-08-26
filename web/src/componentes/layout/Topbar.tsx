import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAlunos, useTurmas } from '../../hooks/consultas';
import { Avatar } from '../ui/Avatar';
import * as sessao from '../../servicos/sessao';
import { normalizar } from '../../util/formato';
import { useMigalhas } from './migalhas';

const MAX_RESULTADOS = 8;

function IconeBusca() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <circle cx="9" cy="9" r="6" />
      <path d="M13.5 13.5L17.5 17.5" />
    </svg>
  );
}

function IconeSino() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M5 8.4a5 5 0 0 1 10 0c0 3.6 1.2 4.6 1.2 4.6H3.8S5 12 5 8.4Z" />
      <path d="M8.3 16a2 2 0 0 0 3.4 0" />
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
  const [ligada, setLigada] = useState(false);
  const { data: alunos = [] } = useAlunos({ habilitada: ligada });
  const { data: turmas = [] } = useTurmas({ habilitada: ligada });

  const turmaPorId = useMemo(() => new Map(turmas.map((t) => [t.id, t])), [turmas]);

  const resultados = useMemo(() => {
    const q = termo.trim();
    if (!q) return [];
    const nq = normalizar(q);
    return alunos.filter((a) => normalizar(a.nome).includes(nq)).slice(0, MAX_RESULTADOS);
  }, [termo, alunos]);

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
    <div className="busca">
      <IconeBusca />
      <input
        ref={inputRef}
        className="busca__input"
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
      <span className="busca__atalho">/</span>

      <div className={`busca__resultados${mostrarResultados ? ' is-aberto' : ''}`}>
        {mostrarResultados && resultados.length === 0 && (
          <div className="busca__vazio">Nenhum aluno encontrado.</div>
        )}
        {mostrarResultados &&
          resultados.map((a, i) => {
            const turma = turmaPorId.get(a.turmaId);
            return (
              <a
                key={a.id}
                className={`busca__item${i === ativo ? ' is-ativo' : ''}`}
                href={`/alunos/${a.id}`}
                // Evita o blur fechar a lista antes do clique registrar.
                onMouseDown={(ev) => ev.preventDefault()}
                onClick={(ev) => {
                  ev.preventDefault();
                  irPara(a.id);
                }}
              >
                <span className="busca__item-nome">{a.nome}</span>
                {turma && <span className="busca__item-sub">{turma.nome}</span>}
              </a>
            );
          })}
      </div>
    </div>
  );
}

export function Topbar() {
  const navegar = useNavigate();
  const migalhas = useMigalhas();
  const nome = sessao.nome();

  // Mesmo `encerrar()` que o aluno já usa; o coordenador não tinha o botão
  // ("tem um botão de sair? como faz para deslogar?" — 21/08, 18h54).
  function sair() {
    sessao.encerrar();
    navegar('/login', { replace: true });
  }

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
              <span className="topbar__migalha" aria-current="page">
                {m.texto}
              </span>
            )}
          </Fragment>
        ))}
      </nav>

      <div className="topbar__acoes">
        <BuscaAlunos />
        <Link className="topbar__icone-btn" to="/painel#alertas" title="Alertas" aria-label="Alertas">
          <IconeSino />
        </Link>
        <button
          onClick={sair}
          title={nome ? `Sair (${nome})` : 'Sair'}
          aria-label={nome ? `Sair da conta de ${nome}` : 'Sair'}
        >
          <Avatar tipo="coordenador" proprio nome={nome} className="topbar__avatar" />
        </button>
      </div>
    </header>
  );
}
