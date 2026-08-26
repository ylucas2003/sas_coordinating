import { useState } from 'react';
import { NavLink, Route, Routes, Navigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';

import { Icone } from '../../componentes/aluno/graficos';
import { Avatar } from '../../componentes/ui/Avatar';
import { PainelAluno } from './PainelAluno';
import { DetalheSimuladoAlunoTela, ListaSimuladosAluno } from './SimuladosAluno';
import { Banco } from '../Banco/Banco';
import * as api from '../../servicos/api';
import * as sessao from '../../servicos/sessao';

// Shell da área do aluno: header (desktop e mobile), tabs e bottom nav.
//
// Diferença consciente em relação à versão anterior: a navegação entre tabs
// agora usa rotas reais (`/simulados/S12`), em vez de estado interno. O aluno
// pode recarregar a página ou salvar o link sem voltar para o painel.

const D_HOME = 'M3 11.5l9-7.5 9 7.5M5 10v9a1 1 0 0 0 1 1h3v-6h6v6h3a1 1 0 0 0 1-1v-9';
const D_DOC = 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M9 13h6 M9 17h4';
const D_GRAD = 'M22 10L12 5 2 10l10 5 10-5z M6 12v5c0 1 2.7 2.5 6 2.5s6-1.5 6-2.5v-5';
const D_BANCO = 'M4 5a2 2 0 0 1 2-2h11a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H6a2 2 0 0 1-2-2z M4 17.5A2 2 0 0 1 6 16h12 M8 7h6';

const TABS = [
  { caminho: '/', label: 'Painel', d: D_HOME, exata: true },
  { caminho: '/simulados', label: 'Simulados', d: D_DOC, exata: false },
  { caminho: '/banco', label: 'Banco', d: D_BANCO, exata: false },
];

function sair() {
  sessao.encerrar();
  window.location.replace('/login.html');
}

function Logo({ tamanho = 34 }: { tamanho?: number }) {
  return (
    <div className="alu-header__logo" style={{ width: tamanho, height: tamanho }}>
      <Icone d={D_GRAD} tamanho={tamanho * 0.5} cor="#fff" />
      <span className="alu-header__logo-bar" />
    </div>
  );
}

export function ShellAluno() {
  const nome = sessao.nome();
  const primeiro = nome.split(' ')[0] || nome;

  const [modal, setModal] = useState<'nenhum' | 'senha' | 'conta'>('nenhum');

  return (
    <div className="alu-shell">
      <header className="alu-header">
        <div className="alu-header__brand">
          <Logo />
          <div className="alu-header__brand-text">
            <span className="alu-header__brand-name">SAS</span>
            <span className="alu-header__brand-sub">Área do estudante</span>
          </div>
        </div>

        <div className="alu-header__tabs">
          {TABS.map((t) => (
            <NavLink
              key={t.caminho}
              to={t.caminho}
              end={t.exata}
              className={({ isActive }) => `alu-tab${isActive ? ' is-active' : ''}`}
            >
              {({ isActive }) => (
                <>
                  <Icone d={t.d} tamanho={16} cor={isActive ? 'var(--color-navy)' : 'var(--color-text-secondary)'} />
                  {t.label}
                </>
              )}
            </NavLink>
          ))}
        </div>

        <div className="alu-header__user">
          <div className="alu-header__user-info">
            <div className="alu-header__user-name">{nome}</div>
          </div>
          <Avatar tipo="aluno" proprio nome={nome} className="alu-avatar" />
          <button className="alu-header__sair" onClick={() => setModal('senha')}>Trocar senha</button>
          <button className="alu-header__sair" onClick={sair}>Sair</button>
        </div>
      </header>

      <header className="alu-header alu-header--mobile">
        <div className="alu-header__brand">
          <Logo tamanho={30} />
          <div className="alu-header__brand-text">
            <span className="alu-header__brand-name" style={{ fontSize: 15 }}>SAS</span>
          </div>
        </div>
        <div className="alu-header__user" style={{ marginLeft: 'auto' }}>
          {/* No mobile o avatar abre o menu de conta (trocar senha / sair). */}
          <Avatar
            tipo="aluno"
            proprio
            nome={nome}
            className="alu-avatar"
            style={{ width: 30, height: 30, fontSize: 13, cursor: 'pointer' }}
            onClick={() => setModal('conta')}
          />
        </div>
      </header>

      <div className="alu-body">
        <div className="alu-body__inner">
          <Routes>
            <Route path="/" element={<PainelAluno nome={primeiro} />} />
            <Route path="/simulados" element={<ListaSimuladosAluno />} />
            <Route path="/simulados/:id" element={<DetalheSimuladoAlunoTela />} />
            <Route path="/banco/*" element={<Banco perfil="aluno" />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>

      <nav className="alu-bottom-nav">
        {TABS.map((t) => (
          <NavLink
            key={t.caminho}
            to={t.caminho}
            end={t.exata}
            className={({ isActive }) => `alu-nav-item${isActive ? ' is-active' : ''}`}
          >
            {({ isActive }) => (
              <>
                <Icone d={t.d} tamanho={22} cor={isActive ? 'var(--color-navy)' : 'var(--color-text-tertiary)'} />
                {t.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {modal === 'conta' && (
        <Modal titulo="Minha conta" onFechar={() => setModal('nenhum')}>
          <div className="alu-modal__form">
            <button className="alu-modal__btn" onClick={() => setModal('senha')}>Trocar senha</button>
            <button className="alu-modal__btn" onClick={sair}>Sair da conta</button>
          </div>
        </Modal>
      )}

      {modal === 'senha' && <ModalTrocarSenha onFechar={() => setModal('nenhum')} />}
    </div>
  );
}

function Modal({
  titulo, onFechar, children,
}: {
  titulo: string;
  onFechar: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="alu-modal-overlay"
      onClick={(ev) => {
        if (ev.target === ev.currentTarget) onFechar();
      }}
    >
      <div className="alu-modal">
        <div className="alu-modal__header">
          <span className="alu-modal__titulo">{titulo}</span>
          <button className="alu-modal__fechar" onClick={onFechar}>×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ModalTrocarSenha({ onFechar }: { onFechar: () => void }) {
  const [atual, setAtual] = useState('');
  const [nova, setNova] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [erro, setErro] = useState('');
  const [ok, setOk] = useState(false);

  const trocar = useMutation({
    mutationFn: (corpo: { senha_atual: string; senha_nova: string }) => api.trocarSenhaMe(corpo),
  });

  async function enviar(ev: React.FormEvent) {
    ev.preventDefault();
    setErro('');
    setOk(false);

    if (nova.length < 8) return setErro('A nova senha precisa ter pelo menos 8 caracteres.');
    if (nova !== confirmar) return setErro('As senhas não conferem.');

    try {
      await trocar.mutateAsync({ senha_atual: atual, senha_nova: nova });
      setOk(true);
      // Deixa a confirmação visível por um instante antes de fechar.
      window.setTimeout(onFechar, 900);
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível trocar a senha.');
    }
  }

  const campo = (label: string, valor: string, set: (v: string) => void) => (
    <label className="alu-modal__campo">
      <span className="alu-modal__label">{label}</span>
      <input
        className="alu-modal__input"
        type="password"
        autoComplete="new-password"
        value={valor}
        onChange={(e) => set(e.target.value)}
      />
    </label>
  );

  return (
    <Modal titulo="Trocar senha" onFechar={onFechar}>
      <form className="alu-modal__form" onSubmit={enviar}>
        {campo('Senha atual', atual, setAtual)}
        {campo('Nova senha (mínimo 8 caracteres)', nova, setNova)}
        {campo('Confirmar nova senha', confirmar, setConfirmar)}

        {erro && <div className="alu-modal__erro">{erro}</div>}
        {ok && <div className="alu-modal__ok">Senha alterada com sucesso.</div>}

        <button
          className="alu-modal__btn alu-modal__btn--primario"
          type="submit"
          disabled={trocar.isPending}
        >
          Salvar nova senha
        </button>
      </form>
    </Modal>
  );
}
