import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import * as sessao from '../../servicos/sessao';

/**
 * Destino do redirect do Canvas. O backend põe o JWT do SAS no fragmento
 * (#token=…) — que não vai ao servidor nem fica em log de acesso — e esta
 * página grava a sessão, limpa a URL e segue. Quem já estava logado no
 * Canvas passa por aqui sem ver nada.
 */
export function CallbackCanvas() {
  const navegar = useNavigate();

  useEffect(() => {
    const frag = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const token = frag.get('token');
    const tipo = frag.get('tipo');
    const proximo = frag.get('proximo') || '/';
    if (!token || !tipo) {
      navegar('/login?canvas=falhou', { replace: true });
      return;
    }
    // O nome vem do próprio JWT — o callback não tem como passá-lo sem
    // expor mais na URL.
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    sessao.iniciar({ access_token: token, tipo, nome: payload.nome ?? '', aluno_id: payload.aluno_id });
    window.history.replaceState(null, '', '/login/canvas');
    navegar(proximo.startsWith('/') ? proximo : '/', { replace: true });
  }, [navegar]);

  return <div className="empty-state">Entrando…</div>;
}
