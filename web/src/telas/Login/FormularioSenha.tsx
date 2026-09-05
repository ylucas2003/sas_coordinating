import { useState } from 'react';
import type { ReactNode } from 'react';

import * as api from '../../servicos/api';
import { ErroApi } from '../../servicos/http';

// O formulário de e-mail e senha — usado pelas DUAS portas que têm senha:
// a da coordenação (`/login`, modo coordenador) e a da cantina
// (`/login-cantina`).
//
// Ele nasceu dentro de `Login.tsx` como `FormularioCoordenacao` e saiu de lá
// quando a cantina apareceu (docs/38 §5). O motivo de extrair em vez de copiar
// é o mesmo que o projeto já paga caro em outro lugar: o Banco está construído
// duas vezes e as duas metades divergiram. Um formulário de senha duplicado
// divergiria no dia em que alguém consertasse o `autoComplete` de um só.
//
// Usa as classes `.porta__*`, que são as do formulário que o ALUNO teve até
// 04/09, quando a senha de aluno acabou. O desenho do campo, do rótulo e do
// olho de senha é o mesmo — o que mudou é quem digita nele.

interface Props {
  /** O que vai no corpo do `/auth/login`. Decide contra qual tabela o servidor
      autentica — `usuario_coordenacao` (0021) ou `usuario_cantina` (0047). */
  tipo: 'coordenador' | 'cantina';
  onEntrar: (dados: api.RespostaAutenticacao) => void;
  /** Sai DENTRO da caixa de erro, e só depois de uma falha. É onde a porta da
      coordenação manda quem errou de porta para a certa; a da cantina não tem
      para onde mandar ninguém, e por isso o campo é opcional. */
  aposErro?: ReactNode;
  /** A linha quieta abaixo do botão: quem procurar quando a senha se perde. */
  ajuda: string;
  /** Preenche o `placeholder` do e-mail com um exemplo do domínio certo. */
  exemploEmail: string;
}

export function FormularioSenha({ tipo, onEntrar, aposErro, ajuda, exemploEmail }: Props) {
  const [usuario, setUsuario] = useState('');
  const [senha, setSenha] = useState('');
  const [verSenha, setVerSenha] = useState(false);
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function enviar(ev: React.FormEvent) {
    ev.preventDefault();
    setEnviando(true);
    setErro('');
    try {
      onEntrar(await api.login({ tipo, usuario: usuario.trim(), senha }));
    } catch (e) {
      setErro(mensagemDeErro(e, 'Credenciais inválidas. Verifique seus dados e tente novamente.'));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="porta__form" noValidate onSubmit={enviar}>
      <div className="porta__campo">
        <label className="porta__rotulo" htmlFor="login-usuario">E-mail</label>
        <div className="porta__campo-caixa">
          <input
            id="login-usuario"
            className="porta__input"
            type="email"
            placeholder={exemploEmail}
            autoComplete="username"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
          />
        </div>
      </div>

      <div className="porta__campo">
        <label className="porta__rotulo" htmlFor="login-senha">Senha</label>
        <div className="porta__campo-caixa">
          <input
            id="login-senha"
            className="porta__input"
            type={verSenha ? 'text' : 'password'}
            placeholder="••••••••"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
          <button
            type="button"
            className="porta__olho"
            tabIndex={-1}
            aria-label={verSenha ? 'Ocultar senha' : 'Mostrar senha'}
            onClick={() => setVerSenha((v) => !v)}
          >
            {verSenha ? 'Ocultar' : 'Mostrar'}
          </button>
        </div>
      </div>

      {/* O "Manter conectado" NÃO voltou. Era `defaultChecked` sem estado e sem
          chegar ao `api.login` — um controle que fingia fazer alguma coisa, o
          que é pior que controle nenhum. Se sessão longa virar produto, o lugar
          dela é no servidor, na validade do token. */}

      {erro && (
        <div className="porta__erro" role="alert">
          {erro}
          {aposErro}
        </div>
      )}

      <button type="submit" className="alu-tecla alu-tecla--larga" disabled={enviando}>
        {enviando ? 'Entrando…' : 'Entrar'}
      </button>

      <p className="porta__ajuda">{ajuda}</p>
    </form>
  );
}

/**
 * A mensagem que o usuário vê.
 *
 * 401 e as mensagens que terminam em "→ 4xx" viram o texto padrão: são o
 * "credenciais inválidas" cru da API, que não ajuda ninguém. O resto passa,
 * porque aí o servidor disse algo específico e útil.
 */
function mensagemDeErro(e: unknown, padrao: string): string {
  if (e instanceof ErroApi && (e.status === 401 || /→ \d{3}$/.test(e.message))) return padrao;
  return (e as Error)?.message || padrao;
}
