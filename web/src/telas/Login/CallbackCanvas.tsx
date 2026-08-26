import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import * as sessao from '../../servicos/sessao';

/**
 * Destino do redirect do Canvas. O backend põe o JWT do SAS no fragmento
 * (#token=…) — que não vai ao servidor nem fica em log de acesso — e esta
 * página grava a sessão, limpa a URL e segue. Quem já estava logado no
 * Canvas passa por aqui sem ver nada.
 *
 * O efeito precisa ser IDEMPOTENTE: em dev o StrictMode o executa duas
 * vezes, e a primeira execução limpa o fragmento — a segunda via "sem token"
 * e mandava para "falhou" um login que tinha dado certo. Por isso o
 * fragmento é lido UMA vez, fora do efeito, e a ausência dele só é falha se
 * também não houver sessão gravada.
 */
function lerFragmento(): { token: string; tipo: string; proximo: string } | null {
  const frag = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const token = frag.get('token');
  const tipo = frag.get('tipo');
  if (!token || !tipo) return null;
  const proximo = frag.get('proximo') || '/';
  return { token, tipo, proximo: proximo.startsWith('/') && !proximo.startsWith('//') ? proximo : '/' };
}

function nomeDoToken(token: string): { nome: string; aluno_id?: string; temFoto: boolean } {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return { nome: payload.nome ?? '', aluno_id: payload.aluno_id, temFoto: Boolean(payload.temFoto) };
  } catch {
    return { nome: '', temFoto: false };
  }
}

export function CallbackCanvas() {
  const navegar = useNavigate();

  useEffect(() => {
    const dados = lerFragmento();
    if (dados) {
      const { nome, aluno_id, temFoto } = nomeDoToken(dados.token);
      sessao.iniciar({ access_token: dados.token, tipo: dados.tipo, nome, aluno_id, temFoto });
      window.history.replaceState(null, '', '/login/canvas');
      navegar(dados.proximo, { replace: true });
      return;
    }
    // Sem fragmento: ou é a segunda execução do StrictMode (sessão já
    // gravada → segue), ou alguém abriu /login/canvas à mão (→ login).
    navegar(sessao.autenticado() ? '/' : '/login?canvas=falhou', { replace: true });
  }, [navegar]);

  return <div className="empty-state">Entrando…</div>;
}
