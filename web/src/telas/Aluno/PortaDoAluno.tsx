import { useState } from 'react';

import * as api from '../../servicos/api';
import { ErroApi } from '../../servicos/http';
import { Icone } from './pecas/Icone';

// A PORTA DO ALUNO — a tela de login inteira, não só uma ilustração.
//
// É a ÚNICA tela do produto que pode ser ilustrada, e o motivo da ilustração é
// um só: **a linha dourada no horizonte É a linha de corte de todas as outras
// telas**, na maior escala em que ela aparece. O planador sobe acima dela
// deixando um rastro pontilhado que é uma curva de nota, e cruza a linha no
// meio do caminho. Quem entra vê, antes de qualquer número, a metáfora que
// organiza o produto inteiro.
//
// A grade quadrada do céu é o MESMO motivo do cobogó da fachada, em outra
// escala — não são duas decisões (brief §Restrições).
//
// ⚠️ ESTA TELA SUBSTITUI O LOGIN INTEIRO quando o modo é 'aluno'. O modo
// 'coordenador' segue renderizando o `.lp` institucional de `Login.tsx`, sem
// uma linha alterada — são ~900 alunos contra uma dúzia de coordenadores, e por
// isso o padrão é esta porta, com a passagem para o outro lado num link
// discreto no rodapé.
//
// ⚠️ NÃO existe gancho de retorno personalizado ("sua sequência de 12 está
// esperando"), embora ele apareça na imagem de referência. A ausência é
// deliberada: antes do login o servidor não sabe quem está do outro lado, e
// mostrar a sequência de alguém a quem quer que abra a página é vazamento, não
// retenção. O gancho de verdade é notificação, e notificação não existe
// (docs/29 §C). Registrado como `ganchoDeRetorno` em `dados/aluno/registro.ts`.
//
// ⚠️ Também não entram os números institucionais da imagem ("900 alunos",
// "2.693 questões"): não vêm de dado nenhum, e a régua do brief é explícita —
// nenhum número institucional inventado.

/** O mesmo shape que `/auth/login` e `/auth/primeiro-acesso` devolvem. */
export interface DadosDeSessao {
  access_token: string;
  tipo: string;
  nome: string;
  aluno_id?: string;
  temFoto: boolean;
}

interface Props {
  onEntrar: (dados: DadosDeSessao) => void;
  /** O botão do Canvas só existe se o servidor tiver a Developer Key. */
  ssoCanvas: boolean;
  /** Aviso de volta do SSO ("o Canvas recusou o login…"), quando houver. */
  avisoCanvas: string | null;
  onIrParaCoordenacao: () => void;
}

/**
 * Os dois links do rodapé caem no MESMO formulário, e isso não é atalho: a
 * rota `/auth/primeiro-acesso` serve os dois casos, porque a validação é a
 * mesma — matrícula mais o e-mail do Canvas (`api/app/routes/auth.py`). O que
 * muda é só o que o aluno acha que está fazendo, e é por isso que o título e o
 * botão mudam junto.
 */
type Formulario = 'login' | 'primeiro-acesso' | 'esqueci';

export function PortaDoAluno({ onEntrar, ssoCanvas, avisoCanvas, onIrParaCoordenacao }: Props) {
  const [formulario, setFormulario] = useState<Formulario>('login');

  return (
    <div className="porta">
      <div className="porta__cena-caixa">
        <Amanhecer />

        <div className="porta__marca">
          {/* A marca do colégio, não um selo inventado. A versão branca é a
              que o repositório já tem e é exatamente a que este fundo pede. */}
          <span className="alu-marca alu-marca--grande" role="img" aria-label="Colégio Ari de Sá" />
          <span className="porta__marca-sub">Turma ITM</span>
        </div>

        <h1 className="porta__manchete">
          Todo dia
          <br />
          acima da linha
        </h1>
      </div>

      <div className="porta__painel">
        <div className="porta__painel-interno">
          {avisoCanvas && <p className="porta__erro">{avisoCanvas}</p>}

          {formulario === 'login' ? (
            <FormularioDeEntrada
              ssoCanvas={ssoCanvas}
              onEntrar={onEntrar}
              onPrimeiroAcesso={() => setFormulario('primeiro-acesso')}
              onEsqueci={() => setFormulario('esqueci')}
            />
          ) : (
            <FormularioDeSenha
              esqueci={formulario === 'esqueci'}
              onEntrar={onEntrar}
              onVoltar={() => setFormulario('login')}
            />
          )}

          <button type="button" className="porta__coordenacao" onClick={onIrParaCoordenacao}>
            Sou da coordenação
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Formulários ─────────────────────────────────────────────────────────

/** Um 401 sem `detail` viraria "POST /auth/login → 401" — texto de log, não de tela. */
function mensagemDeErro(erro: unknown, padrao: string): string {
  if (erro instanceof ErroApi && erro.message && !erro.message.includes('→')) return erro.message;
  return padrao;
}

function FormularioDeEntrada({
  ssoCanvas,
  onEntrar,
  onPrimeiroAcesso,
  onEsqueci,
}: {
  ssoCanvas: boolean;
  onEntrar: (dados: DadosDeSessao) => void;
  onPrimeiroAcesso: () => void;
  onEsqueci: () => void;
}) {
  const [matricula, setMatricula] = useState('');
  const [senha, setSenha] = useState('');
  const [verSenha, setVerSenha] = useState(false);
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function enviar(ev: React.FormEvent) {
    ev.preventDefault();
    setErro('');
    setEnviando(true);
    try {
      onEntrar(await api.login({ tipo: 'aluno', usuario: matricula.trim(), senha }));
    } catch (e) {
      setErro(mensagemDeErro(e, 'Matrícula ou senha incorreta. Confira e tente de novo.'));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="porta__form" noValidate onSubmit={enviar}>
      <Campo
        rotulo="Matrícula"
        tipo="text"
        placeholder="sua matrícula"
        autoComplete="username"
        valor={matricula}
        onChange={setMatricula}
      />

      <label className="porta__campo">
        <span className="porta__rotulo">Senha</span>
        <span className="porta__campo-caixa">
          <input
            className="porta__input"
            type={verSenha ? 'text' : 'password'}
            placeholder="sua senha"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
          <button
            type="button"
            className="porta__olho"
            onClick={() => setVerSenha((v) => !v)}
            aria-label={verSenha ? 'Ocultar a senha' : 'Mostrar a senha'}
          >
            <Icone nome={verSenha ? 'olho_fechado' : 'olho'} tamanho={20} />
          </button>
        </span>
      </label>

      {erro && (
        <p className="porta__erro" role="alert">
          {erro}
        </p>
      )}

      <button className="alu-tecla alu-tecla--larga" type="submit" disabled={enviando}>
        {enviando ? 'Entrando…' : 'Entrar'}
      </button>

      {/* Link, e não `fetch`: o browser precisa NAVEGAR até o Canvas e voltar.
          É o que faz "quem já está logado no Canvas entra direto" funcionar. */}
      {ssoCanvas && (
        <a className="alu-tecla alu-tecla--fantasma alu-tecla--larga" href="/api/auth/canvas/iniciar?proximo=/">
          Entrar com o Canvas
        </a>
      )}

      <p className="porta__links">
        <button type="button" className="porta__link" onClick={onPrimeiroAcesso}>
          Primeiro acesso
        </button>
        <span aria-hidden="true">·</span>
        <button type="button" className="porta__link" onClick={onEsqueci}>
          Esqueci a senha
        </button>
      </p>
    </form>
  );
}

/**
 * Criar a primeira senha, ou redefinir a esquecida — o mesmo formulário e a
 * mesma rota (ver o comentário do tipo `Formulario`).
 *
 * ⚠️ Todas as falhas do servidor devolvem a MESMA mensagem, de propósito: é o
 * que impede a tela de dizer se uma matrícula existe ou se o e-mail está certo
 * (`auth.py`). Não "melhore" o erro aqui distinguindo os casos.
 */
function FormularioDeSenha({
  esqueci,
  onEntrar,
  onVoltar,
}: {
  esqueci: boolean;
  onEntrar: (dados: DadosDeSessao) => void;
  onVoltar: () => void;
}) {
  const [matricula, setMatricula] = useState('');
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function enviar(ev: React.FormEvent) {
    ev.preventDefault();
    setErro('');
    if (!matricula.trim() || !email.trim()) return setErro('Preencha a matrícula e o e-mail.');
    if (senha.length < 8) return setErro('A senha precisa ter pelo menos 8 caracteres.');
    if (senha !== confirmar) return setErro('As senhas não conferem.');

    setEnviando(true);
    try {
      onEntrar(
        await api.primeiroAcesso({
          matricula: matricula.trim(),
          email: email.trim(),
          senha_nova: senha,
        }),
      );
    } catch (e) {
      setErro(mensagemDeErro(e, 'Não foi possível validar seus dados.'));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="porta__form" noValidate onSubmit={enviar}>
      <div className="porta__cabecalho">
        <h2 className="porta__titulo">{esqueci ? 'Redefinir a senha' : 'Primeiro acesso'}</h2>
        <p className="porta__ajuda">
          Confirme sua matrícula e o e-mail que está no Canvas, e escolha uma senha nova.
        </p>
      </div>

      <Campo
        rotulo="Matrícula"
        tipo="text"
        placeholder="sua matrícula"
        autoComplete="username"
        valor={matricula}
        onChange={setMatricula}
      />
      <Campo
        rotulo="E-mail cadastrado no Canvas"
        tipo="email"
        placeholder="seu e-mail institucional"
        autoComplete="email"
        valor={email}
        onChange={setEmail}
      />
      <Campo
        rotulo="Nova senha"
        tipo="password"
        placeholder="mínimo 8 caracteres"
        autoComplete="new-password"
        valor={senha}
        onChange={setSenha}
      />
      <Campo
        rotulo="Confirmar a nova senha"
        tipo="password"
        placeholder="repita a senha"
        autoComplete="new-password"
        valor={confirmar}
        onChange={setConfirmar}
      />

      {erro && (
        <p className="porta__erro" role="alert">
          {erro}
        </p>
      )}

      <button className="alu-tecla alu-tecla--larga" type="submit" disabled={enviando}>
        {enviando ? 'Validando…' : 'Criar senha e entrar'}
      </button>

      <p className="porta__links">
        <button type="button" className="porta__link" onClick={onVoltar}>
          Voltar para o login
        </button>
      </p>
    </form>
  );
}

function Campo({
  rotulo,
  tipo,
  placeholder,
  autoComplete,
  valor,
  onChange,
}: {
  rotulo: string;
  tipo: string;
  placeholder: string;
  autoComplete: string;
  valor: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="porta__campo">
      <span className="porta__rotulo">{rotulo}</span>
      <span className="porta__campo-caixa">
        <input
          className="porta__input"
          type={tipo}
          placeholder={placeholder}
          autoComplete={autoComplete}
          value={valor}
          onChange={(e) => onChange(e.target.value)}
        />
      </span>
    </label>
  );
}

// ─── A ilustração ────────────────────────────────────────────────────────

/**
 * A cena, em SVG escrito à mão. Nenhum asset de terceiro e nenhuma foto de
 * pessoa (regra 6 do CLAUDE.md — os dados são de menores de idade).
 *
 * `preserveAspectRatio="xMidYMid slice"` deixa a cena COBRIR alturas diferentes
 * sem esticar o planador: no celular ela é uma faixa larga e baixa, no desktop
 * uma coluna alta, e é o mesmo desenho nas duas.
 */
function Amanhecer() {
  return (
    <svg
      className="porta__cena"
      viewBox="0 0 400 560"
      preserveAspectRatio="xMidYMid slice"
      role="img"
      aria-label="Uma pista ao amanhecer, uma linha dourada de corte no horizonte, e um planador subindo acima dela"
    >
      <title>Todo dia acima da linha</title>

      <defs>
        <linearGradient id="porta-ceu" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--porta-ceu-alto)" />
          <stop offset="58%" stopColor="var(--porta-ceu-baixo)" />
          <stop offset="100%" stopColor="var(--porta-alvorada)" />
        </linearGradient>
        <linearGradient id="porta-chao" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--porta-chao-alto)" />
          <stop offset="100%" stopColor="var(--porta-chao-baixo)" />
        </linearGradient>
        {/* O brilho do sol nascendo, no ponto de fuga da pista. */}
        <radialGradient id="porta-sol" cx="0.5" cy="1" r="0.6">
          <stop offset="0%" stopColor="var(--porta-alvorada)" stopOpacity="0.95" />
          <stop offset="100%" stopColor="var(--porta-alvorada)" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="porta-veu" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--porta-chao-baixo)" stopOpacity="0" />
          <stop offset="100%" stopColor="var(--porta-chao-baixo)" stopOpacity="0.94" />
        </linearGradient>
        {/* A grade do cobogó, no mesmo ritmo de 24px do fundo das outras telas. */}
        <pattern id="porta-cobogo" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0v24" fill="none" stroke="var(--porta-grade)" strokeWidth="1" />
        </pattern>
      </defs>

      {/* A GEOMETRIA DA CENA, e a ordem dela importa:

            y=232  a linha de corte, cruzando o CÉU
            y=372  o horizonte, onde os morros terminam e o chão começa
            y=372  o ponto de fuga da pista, sobre o brilho do amanhecer

          ⚠️ A linha de corte fica ACIMA dos morros, e não na base deles. Foi o
          erro da primeira versão: com a linha no horizonte ela virava só o
          horizonte, e a leitura "o planador sobe ACIMA da linha" desaparecia —
          era a metáfora inteira indo embora por 140px de diferença. */}
      <rect width="400" height="372" fill="url(#porta-ceu)" />
      <rect width="400" height="372" fill="url(#porta-cobogo)" opacity="0.7" />

      {/* Estrelas com posições fixas, escritas à mão: aleatoriedade aqui só
          faria a cena mudar a cada render sem ninguém pedir. Todas acima da
          linha de corte, que é onde ainda é noite. */}
      <g fill="var(--porta-estrela)">
        {[
          [38, 44, 1.4], [92, 28, 1], [150, 62, 1.2], [214, 36, 1], [268, 70, 1.5],
          [318, 30, 1.1], [360, 86, 1.3], [66, 104, 1], [124, 132, 1.2], [286, 128, 1],
          [340, 158, 1.2], [22, 168, 1], [186, 96, 1.6], [246, 176, 1.1], [104, 196, 1],
          [58, 212, 0.9], [352, 204, 1], [148, 222, 0.9],
        ].map(([cx, cy, r]) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} />
        ))}
      </g>

      <g stroke="var(--porta-estrela)" strokeWidth="0.8" opacity="0.55" fill="none">
        <path d="M118 96 L154 60 L186 78 L214 46" />
      </g>

      {/* O brilho do amanhecer, no ponto de fuga. Vem ANTES dos morros para as
          silhuetas se recortarem contra ele — é o que dá o contraluz. */}
      <ellipse cx="200" cy="372" rx="180" ry="92" fill="url(#porta-sol)" />

      {/* Morros — três camadas, da mais clara à mais escura, todas abaixo da
          linha de corte. */}
      <path
        d="M0 372 L0 300 Q64 258 128 294 Q182 324 236 288 Q308 242 400 296 L400 372 Z"
        fill="var(--porta-morro-3)"
      />
      <path
        d="M0 372 L0 326 Q78 288 146 322 Q214 354 282 318 Q344 286 400 328 L400 372 Z"
        fill="var(--porta-morro-2)"
      />
      <path d="M0 372 L0 348 Q96 324 168 346 Q248 370 400 340 L400 372 Z" fill="var(--porta-morro-1)" />

      {/* O chão e a pista, convergindo no ponto de fuga sobre o brilho. */}
      <rect y="372" width="400" height="188" fill="url(#porta-chao)" />
      <path d="M194 372 L206 372 L400 560 L0 560 Z" fill="var(--porta-pista)" />
      <path d="M194 372 L0 560" stroke="var(--porta-pista-fio)" strokeWidth="2" fill="none" />
      <path d="M206 372 L400 560" stroke="var(--porta-pista-fio)" strokeWidth="2" fill="none" />

      {/* O eixo tracejado: os traços crescem com a perspectiva.

          ⚠️ Ele PARA na metade da pista, e isso é composição, não descuido: os
          traços de baixo são os maiores e mais claros, e caem exatamente atrás
          da manchete — no celular, onde a cena é estreita, o tracejado saía
          entre "Todo dia" e "acima da linha". A perspectiva continua legível
          pelas duas bordas convergentes, que é de onde ela vem de fato. */}
      <g stroke="var(--porta-pista-eixo)" strokeLinecap="round">
        {[
          [378, 6, 2], [392, 9, 2.6], [410, 13, 3.2], [434, 18, 4],
        ].map(([y, h, w]) => (
          <line key={y} x1="200" x2="200" y1={y} y2={y + h} strokeWidth={w} />
        ))}
      </g>

      {/* O véu da base: dá contraste à manchete sem apagar a pista, que
          continua aparecendo pelas bordas. */}
      <rect y="392" width="400" height="168" fill="url(#porta-veu)" />

      {/* ── A LINHA DE CORTE ─────────────────────────────────────────────
          A mesma linha de todas as outras telas, aqui na maior escala em que
          ela aparece. VALOR, contínua, atravessando a cena inteira — e SEM
          rótulo: escrever "CORTE" sobre ela era legendar a metáfora. */}
      <line x1="0" x2="400" y1="232" y2="232" stroke="var(--alu-valor)" strokeWidth="2.5" />

      {/* O rastro É uma curva de nota: sai baixo à esquerda, cruza o corte e
          sobe. É a trajetória que a Jornada desenha com dado de verdade. */}
      <path
        d="M6 372 C 76 350 122 300 166 264 C 216 224 268 176 330 118"
        fill="none"
        stroke="var(--porta-rastro)"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeDasharray="1 9"
      />
      {/* O cruzamento, marcado — é o momento que o produto inteiro persegue. */}
      <circle cx="192" cy="232" r="5" fill="var(--porta-ceu-alto)" stroke="var(--alu-valor)" strokeWidth="2" />

      <g transform="translate(330 118) rotate(-32)">
        <path d="M-30 0 L20 -2 L30 1 L20 4 L-30 3 Z" fill="var(--porta-planador)" />
        <path d="M-6 1 L-26 -22 L-14 -22 L2 0 Z" fill="var(--porta-planador)" />
        <path d="M-6 2 L-26 24 L-14 24 L2 2 Z" fill="var(--porta-planador)" opacity="0.72" />
      </g>
    </svg>
  );
}
