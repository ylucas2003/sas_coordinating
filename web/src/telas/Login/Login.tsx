import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import * as api from '../../servicos/api';
import { ErroApi } from '../../servicos/http';
import * as sessao from '../../servicos/sessao';
import { Porta } from './Porta';
import type { Modo } from './Porta';

// Tela de login: duas portas, UM casco.
//
// ⚠️ O `.lp` institucional MORREU em 05/09/2026. Até então, clicar em "Sou da
// coordenação" trocava a PÁGINA INTEIRA por outro desenho — coluna dupla,
// logos, selo de 108 anos, manchete própria — e a coordenação parecia outro
// produto a um clique de distância. Foram apagados `PainelDireito.tsx`,
// `modos.ts` e as 625 linhas de `login.css`.
//
// Agora as duas portas são a mesma `Porta`, e só o painel da direita troca de
// conteúdo. A coordenação herda a cena, a marca e o cobogó — que é exatamente
// o que o brief pedia ao dizer que o login da coordenação é "a mesma fachada,
// outro ângulo". Antes isso era uma treliça desenhada à parte no painel velho;
// agora não precisa existir, porque a fachada já está lá.
//
// A porta é o CASCO e não conhece sessão nem API: o formulário entra como slot.
//
// ⚠️ O botão "Entrar com o Canvas" é só da porta do ALUNO. A coordenação não
// entra por lá — clicar levaria ao `?canvas=sem-conta`, que é uma recusa
// correta explicada de um jeito que não serviria para quem tem conta
// (docs/35 §11.6).

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
    // que fazer. Quem cria aluno é o sync do Canvas, a partir da matrícula no
    // curso de simulados — e é isso que a mensagem manda conferir.
    //
    // ⚠️ Sem ecoar o e-mail na mensagem, embora ele fosse o texto mais útil
    // possível: ele viajaria na query string, e query string entra em
    // histórico de navegador e em log de acesso do nginx.
    'sem-conta':
      'Sua conta do Canvas não está na lista de alunos do SAS. A lista vem da sua matrícula no '
      + 'curso de simulados do ITA/IME no Canvas: matrícula nova leva alguns minutos para chegar '
      + 'aqui. Se a sua já está lá, fale com a coordenação.',
  }[params.get('canvas') ?? ''] ?? null;

  const [modo, setModo] = useState<Modo>('aluno');

  function entrar(dados: {
    access_token: string; tipo: string; papel?: string; nome: string; aluno_id?: string; temFoto: boolean;
  }) {
    sessao.iniciar(dados);
    navegar('/', { replace: true });
  }

  return (
    <Porta
      modo={modo}
      ssoCanvas={ssoCanvas}
      avisoCanvas={avisoCanvas}
      onTrocarModo={setModo}
      formularioCoordenacao={<FormularioCoordenacao onEntrar={entrar} onTrocarModo={setModo} />}
    />
  );
}

/**
 * E-mail e senha — a única porta da coordenação, e a mesma do administrador.
 * Quem distingue os dois é o `papel` que volta do servidor (docs/35 §11).
 *
 * Usa as classes `.porta__*`, que já existiam e estavam órfãs: são as do
 * formulário que o ALUNO teve até 04/09, quando a senha de aluno acabou. O
 * desenho do campo, do rótulo e do olho de senha é o mesmo — o que mudou é
 * quem digita nele.
 */
function FormularioCoordenacao({
  onEntrar, onTrocarModo,
}: {
  onEntrar: (dados: { access_token: string; tipo: string; papel?: string; nome: string; aluno_id?: string; temFoto: boolean }) => void;
  /** Para mandar quem errou de porta para a certa. */
  onTrocarModo: (modo: Modo) => void;
}) {
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
      // `tipo` fixo: é o único que `/auth/login` ainda aceita.
      onEntrar(await api.login({ tipo: 'coordenador', usuario: usuario.trim(), senha }));
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
            placeholder="nome@aridesa.com.br"
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
          {/* DUAS PORTAS, e elas são diferentes: a coordenação entra por e-mail
              e senha; o aluno entra SÓ pelo Canvas. Quem errar de porta precisa
              saber para onde ir — senão tenta a mesma senha três vezes e
              conclui que a conta foi bloqueada. Só aparece DEPOIS de uma
              falha: antes dela seria ruído na porta certa. */}
          <button type="button" className="porta__link" onClick={() => onTrocarModo('aluno')}>
            É aluno? A entrada de aluno é pelo Canvas.
          </button>
        </div>
      )}

      <button type="submit" className="alu-tecla alu-tecla--larga" disabled={enviando}>
        {enviando ? 'Entrando…' : 'Entrar'}
      </button>

      {/* Não há "primeiro acesso" nem "esqueci a senha": a senha da coordenação
          é redefinida pelo administrador, em /administracao/contas, e entregue
          pelo canal do colégio (docs/35 §11.7). */}
      <p className="porta__ajuda">
        Esqueceu a senha? Peça ao administrador do SAS para redefinir.
      </p>
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
