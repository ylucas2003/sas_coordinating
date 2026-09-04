import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import * as api from '../../servicos/api';
import { ErroApi } from '../../servicos/http';
import * as sessao from '../../servicos/sessao';
import { PainelDireito } from './PainelDireito';
import { PortaDoAluno } from '../Aluno/PortaDoAluno';
import { ROTULOS_COORDENACAO } from './modos';
import type { Modo } from './modos';

// Tela de login: duas portas, uma delas com formulário.
//
// 'aluno' devolve a `PortaDoAluno` inteira — hoje só o botão do Canvas.
// 'coordenador' desenha o `.lp` institucional com e-mail + senha, e é por onde
// entram coordenador E administrador: a porta é a mesma, o que muda é o
// `papel` que volta do servidor (docs/35 §11).
//
// ⚠️ O formulário de "primeiro acesso" saiu daqui em 04/09, junto com o do
// aluno na porta: ele criava/redefinia a senha do aluno, e a senha do aluno
// deixou de existir (docs/35 §11.5).
//
// ⚠️ O botão "Entrar com o Canvas" também saiu DESTE lado. Ele continua na
// porta do aluno, mas a coordenação não entra mais por lá — clicar levaria ao
// `?canvas=sem-conta`, que é uma recusa correta explicada de um jeito que não
// serviria para quem tem conta (docs/35 §11.6).

export function Login() {
  const navegar = useNavigate();
  const [params] = useSearchParams();
  // Canvas como identidade (docs/18 §4.2). O botão da porta do aluno só existe
  // se o servidor tiver a Developer Key; sem ela, ninguém entra por lá — e a
  // porta diz isso, em vez de ficar sem nada.
  const [ssoCanvas, setSsoCanvas] = useState(false);
  useEffect(() => {
    api.ssoCanvasDisponivel().then((r) => setSsoCanvas(r.disponivel)).catch(() => setSsoCanvas(false));
  }, []);
  // Motivos que o Canvas devolve quando a CHAVE está errada — não o usuário.
  // Aparecem porque o conserto é de quem administra, não de quem clicou.
  const MOTIVO_CANVAS: Record<string, string> = {
    unauthorized_client: 'a Developer Key do SAS está desligada no Canvas (Admin → Developer Keys → ON).',
    invalid_scope: 'a Developer Key não permite o escopo que o SAS pede.',
    invalid_request: 'a redirect URI configurada no Canvas não bate com a do servidor.',
  };
  const motivo = params.get('motivo') ?? '';
  const avisoCanvas = {
    cancelado: null,
    recusado: `O Canvas recusou o login: ${MOTIVO_CANVAS[motivo] ?? motivo}`,
    // Sem "ou entre com matrícula e senha": essa saída não existe mais.
    falhou: 'O Canvas não confirmou o login. Tente de novo em alguns instantes.',
    // A recusa certa (o SAS decide quem entra), dita de um jeito que ensina o
    // que fazer. A versão anterior — "Procure a coordenação" — mandava a
    // pessoa embora sem dizer o que pedir (docs/33 §6).
    //
    // ⚠️ Sem ecoar o e-mail na mensagem, embora ele fosse o texto mais útil
    // possível: ele viajaria na query string, e query string entra em
    // histórico de navegador e em log de acesso do nginx.
    'sem-conta':
      'Sua conta do Canvas ainda não tem acesso ao SAS. Peça a um coordenador para criar seu '
      + 'acesso usando o mesmo e-mail da sua conta do Canvas — o Canvas diz quem você é, mas o '
      + 'acesso ao SAS é criado aqui dentro.',
  }[params.get('canvas') ?? ''] ?? null;
  const [modo, setModo] = useState<Modo>('aluno');
  // Chave de animação: mudar de modo reinicia a transição de entrada do texto.
  const [geracao, setGeracao] = useState(0);

  const m = ROTULOS_COORDENACAO;

  function trocarModo(novo: Modo) {
    if (novo === modo) return;
    setModo(novo);
    setGeracao((g) => g + 1);
  }

  function entrar(dados: {
    access_token: string; tipo: string; papel?: string; nome: string; aluno_id?: string; temFoto: boolean;
  }) {
    sessao.iniciar(dados);
    navegar('/', { replace: true });
  }

  // ⚠️ A PORTA DO ALUNO SUBSTITUI O LOGIN INTEIRO, não só a coluna da direita.
  // São ~900 alunos contra uma dúzia de coordenadores: o padrão é a porta, e a
  // travessia para o outro lado é um link discreto no rodapé dela.
  if (modo === 'aluno') {
    return (
      <PortaDoAluno
        ssoCanvas={ssoCanvas}
        avisoCanvas={avisoCanvas}
        onIrParaCoordenacao={() => trocarModo('coordenador')}
      />
    );
  }

  return (
    <div className="lp-page">
    <div className="lp">
      <div className="lp-left">
        <div className="lp-left__inner">
          <div className="lp-label" key={`label-${geracao}`}>
            <span className="lp-label__bar" />
            <span className="lp-label__text">{m.label}</span>
          </div>

          <div className="lp-headline-wrap" key={`hl-${geracao}`}>
            <h1 className="lp-headline">
              {m.hl1}
              <br />
              <em>{m.hlEm}</em>
              <span>{m.hl2}</span>
            </h1>
          </div>

          <p className="lp-subtitle" key={`sub-${geracao}`}>{m.subtitle}</p>

          <div className="lp-toggle">
            <button
              className="lp-toggle__btn"
              onClick={() => trocarModo('aluno')}
            >
              <IconePessoa />
              Sou aluno
            </button>
            <button className="lp-toggle__btn is-active">
              <IconeEscudo />
              Sou coordenador
            </button>
          </div>

          <FormularioLogin rotulos={m} onEntrar={entrar} />
        </div>
      </div>

      <PainelDireito geracao={geracao} />
    </div>
    </div>
  );
}

function FormularioLogin({
  rotulos, onEntrar,
}: {
  rotulos: typeof ROTULOS_COORDENACAO;
  onEntrar: (dados: { access_token: string; tipo: string; papel?: string; nome: string; aluno_id?: string; temFoto: boolean }) => void;
}) {
  const [usuario, setUsuario] = useState('');
  const [senha, setSenha] = useState('');
  const [verSenha, setVerSenha] = useState(false);
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);
  // Incrementa a cada erro para re-disparar a animação de shake.
  const [tremor, setTremor] = useState(0);

  async function enviar(ev: React.FormEvent) {
    ev.preventDefault();
    setEnviando(true);
    setErro('');
    try {
      // `tipo` fixo: é o único que `/auth/login` ainda aceita.
      onEntrar(await api.login({ tipo: 'coordenador', usuario: usuario.trim(), senha }));
    } catch (e) {
      setErro(mensagemDeErro(e, 'Credenciais inválidas. Verifique seus dados e tente novamente.'));
      setTremor((t) => t + 1);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="lp-form" key={tremor} style={tremor ? { animation: 'lp-shake 0.4s ease' } : undefined} noValidate onSubmit={enviar}>
      <Campo
        rotulo={rotulos.fieldLabel}
        icone={<IconePessoa pequeno />}
        tipo="text"
        placeholder={rotulos.placeholder}
        autoComplete="username"
        valor={usuario}
        onChange={setUsuario}
      />

      <div className="lp-field">
        <label className="lp-field__label">Senha</label>
        <div className="lp-field__wrap">
          <IconeCadeado />
          <input
            className="lp-field__input"
            type={verSenha ? 'text' : 'password'}
            placeholder="••••••••"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
          <button
            type="button"
            className="lp-field__eye"
            tabIndex={-1}
            aria-label={verSenha ? 'Ocultar senha' : 'Mostrar senha'}
            onClick={() => setVerSenha((v) => !v)}
          >
            <IconeOlho aberto={verSenha} />
          </button>
        </div>
      </div>

      <div className="lp-extras">
        <label className="lp-check">
          <input type="checkbox" className="lp-check__input" defaultChecked />
          <span className="lp-check__box" />
          Manter conectado
        </label>
      </div>

      {erro && <div className="lp-error">{erro}</div>}

      <button type="submit" className="lp-submit" disabled={enviando}>
        <span>{rotulos.submitText}</span>
        <IconeSeta />
      </button>

      {/* Não há "primeiro acesso" nem "esqueci a senha" aqui: a senha da
          coordenação é redefinida pelo administrador, no painel
          /administracao, e entregue pelo canal do colégio (docs/35 §11.7). */}
      <p className="lp-first-access">
        Esqueceu a senha? Peça ao administrador do SAS para redefinir.
      </p>
    </form>
  );
}

function Campo({
  rotulo, icone, tipo, placeholder, autoComplete, valor, onChange,
}: {
  rotulo: string;
  icone: React.ReactNode;
  tipo: string;
  placeholder: string;
  autoComplete: string;
  valor: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="lp-field">
      <label className="lp-field__label">{rotulo}</label>
      <div className="lp-field__wrap">
        {icone}
        <input
          className="lp-field__input"
          type={tipo}
          placeholder={placeholder}
          autoComplete={autoComplete}
          value={valor}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    </div>
  );
}

/**
 * Mensagem para o usuário. Um 401 sem `detail` do backend viraria
 * "POST /auth/login → 401" — texto de log, não de tela.
 */
function mensagemDeErro(e: unknown, padrao: string): string {
  if (e instanceof ErroApi && (e.status === 401 || /→ \d{3}$/.test(e.message))) return padrao;
  return (e as Error)?.message || padrao;
}

// ─── Ícones ──────────────────────────────────────────────────────────────

const traco = {
  fill: 'none', stroke: 'currentColor', strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

function IconePessoa({ pequeno = false }: { pequeno?: boolean }) {
  const t = pequeno ? 15 : 14;
  return (
    <svg
      className={pequeno ? 'lp-field__icon' : undefined}
      width={t} height={t} viewBox="0 0 24 24" strokeWidth={pequeno ? 2 : 2.2} {...traco}
    >
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function IconeEscudo() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" strokeWidth="2.2" {...traco}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function IconeCadeado() {
  return (
    <svg className="lp-field__icon" width="15" height="15" viewBox="0 0 24 24" strokeWidth="2" {...traco}>
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function IconeOlho({ aberto }: { aberto: boolean }) {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" strokeWidth="2" {...traco}>
      {aberto ? (
        <>
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </>
      ) : (
        <>
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
          <line x1="1" y1="1" x2="23" y2="23" />
        </>
      )}
    </svg>
  );
}

function IconeSeta() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" strokeWidth="2.2" {...traco}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}
