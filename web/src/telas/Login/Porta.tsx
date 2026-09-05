import type { ReactNode } from 'react';

// A PORTA — a tela de login inteira, das DUAS entradas, não só uma ilustração.
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
// ⚠️ ESTA TELA É O LOGIN INTEIRO, nos DOIS modos, e só o PAINEL da direita
// troca de conteúdo. Até 05/09/2026 "Sou da coordenação" trocava a página
// inteira por outro desenho — o `.lp` institucional, com coluna dupla, logos e
// selo —, e o resultado era que a coordenação parecia outro produto a um
// clique de distância. Aquele front foi apagado: `PainelDireito.tsx`,
// `modos.ts` e as 625 linhas de `login.css`.
//
// A cena, a marca e a manchete são as mesmas nas duas portas. A ilustração já
// carrega o cobogó e a linha de corte, então a coordenação passou a herdar de
// graça a fachada que o brief pedia que ela tivesse.
//
// São ~900 alunos contra uma dúzia de coordenadores: o padrão é a porta do
// aluno, e a travessia é um link discreto no rodapé do painel, nos dois
// sentidos — nunca uma aba, que sugeriria duas coisas de peso igual.
//
// ⚠️ NÃO HÁ FORMULÁRIO DE ALUNO (docs/35 §11.5). Saíram os dois: o de
// matrícula + senha e o de "primeiro acesso / esqueci a senha". O aluno entra
// só pelo Canvas, com a conta que ele já usa nas aulas — não existe mais senha
// de aluno no SAS para digitar, criar ou redefinir. O formulário que existe
// aqui é o da COORDENAÇÃO, e entra como slot: a porta é só o casco e não
// conhece a sessão nem a API.
//
// O painel do aluno tem de PARECER UMA PORTA, e não o resto de uma tela que
// tinha mais coisa. É por isso que ele não é só um botão solto: diz de qual
// conta se trata, o que fazer quando o Canvas recusa, e quem procurar. O texto
// ocupa o lugar que os campos ocupavam — de propósito.
//
// ⚠️ Consequência que veio junto e não tem contorno: Canvas fora do ar =
// ninguém entra. É o que o `else` do botão precisa dizer com todas as letras,
// em vez de sumir e deixar a porta vazia.
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

/**
 * Qual porta está aberta. NÃO diz quem a pessoa é — diz o que a tela mostra.
 *
 * São TRÊS desde 05/09, e a terceira não é irmã das outras duas: 'aluno' e
 * 'coordenador' convivem na MESMA URL (`/login`) e trocam por um link no
 * rodapé; 'cantina' mora em `/login-cantina` e não tem travessia nenhuma
 * (docs/38 §5). Quem trabalha na cantina não erra de porta por engano — chega
 * lá pelo endereço que a coordenação entregou —, e um "Sou aluno" ali seria
 * ruído numa porta de trabalho.
 */
export type Modo = 'aluno' | 'coordenador' | 'cantina';

interface Props {
  modo: Modo;
  /** O botão do Canvas só existe se o servidor tiver a Developer Key. */
  ssoCanvas: boolean;
  /** Aviso de volta do SSO ("o Canvas recusou o login…"), quando houver. */
  avisoCanvas: string | null;
  /** Ausente no modo 'cantina': não há para onde atravessar. */
  onTrocarModo?: (modo: Modo) => void;
  /** O formulário de e-mail e senha. Entra como slot para a porta não precisar
      conhecer a sessão nem a API — ela é só o casco. */
  formulario: ReactNode;
}

/** O que o painel da direita diz, por porta. */
const TEXTO_DO_PAINEL: Record<Modo, { titulo: string; ajuda: ReactNode }> = {
  aluno: {
    titulo: 'Entrar',
    ajuda: (
      <>
        Você entra com a <b>mesma conta do Canvas</b> que usa nas aulas. Não há senha
        separada aqui — se já estiver logado no Canvas, a porta abre direto.
      </>
    ),
  },
  coordenador: {
    titulo: 'Entrar na coordenação',
    ajuda: (
      <>
        A coordenação entra com <b>e-mail e senha</b>. O botão do Canvas é a porta do
        aluno — esta conta existe só aqui.
      </>
    ),
  },
  cantina: {
    titulo: 'Entrar na cantina',
    ajuda: (
      <>
        A conta da cantina é criada pelo <b>administrador do SAS</b> e serve só para lançar
        cardápio e ver os pedidos do dia.
      </>
    ),
  },
};

export function Porta({
  modo, ssoCanvas, avisoCanvas, onTrocarModo, formulario,
}: Props) {
  // As duas portas com senha se comportam igual daqui para baixo: mostram o
  // formulário e escondem o botão do Canvas. O que as separa é só o texto do
  // cabeçalho e a existência da travessia.
  const comSenha = modo !== 'aluno';
  const texto = TEXTO_DO_PAINEL[modo];
  return (
    <div className="porta">
      <div className="porta__cena-caixa">
        <Amanhecer />

        <div className="porta__marca">
          {/* A marca do colégio, não um selo inventado. A versão branca é a
              que o repositório já tem e é exatamente a que este fundo pede. */}
          <span className="alu-marca alu-marca--grande" role="img" aria-label="Colégio Ari de Sá" />
          {/* "ITM" não existe em lugar nenhum do dado: a `trilha` das turmas
              reais é ITA e o `section_original` vem do Canvas como "3o ITA AD"
              / "3o ITA MF" (docs/35 §7). */}
          <span className="porta__marca-sub">Turma ITA/IME</span>
        </div>

        <h1 className="porta__manchete">
          Todo dia
          <br />
          acima da linha
        </h1>
      </div>

      {/* ⚠️ Só o PAINEL troca. A cena, a marca e a manchete são as mesmas nas
          duas portas — é isso que faz a coordenação parar de parecer outro
          produto ao clicar em "Sou da coordenação". */}
      <div className="porta__painel">
        <div className="porta__painel-interno">
          {avisoCanvas && !comSenha && (
            <p className="porta__erro" role="alert">
              {avisoCanvas}
            </p>
          )}

          <div className="porta__cabecalho">
            <h2 className="porta__titulo">{texto.titulo}</h2>
            <p className="porta__ajuda">{texto.ajuda}</p>
          </div>

          {comSenha ? (
            formulario
          ) : (
            <>
              {ssoCanvas ? (
                /* Link, e não `fetch`: o browser precisa NAVEGAR até o Canvas e
                   voltar. É o que faz "quem já está logado no Canvas entra
                   direto" funcionar. */
                <a className="alu-tecla alu-tecla--larga" href="/api/auth/canvas/iniciar?proximo=/">
                  Entrar com o Canvas
                </a>
              ) : (
                <p className="porta__erro" role="alert">
                  O login pelo Canvas está fora do ar no momento, e ele é o único caminho de
                  entrada do aluno. Tente de novo em alguns minutos.
                </p>
              )}

              {/* O acesso do aluno não é "liberado" por ninguém aqui dentro nem
                  casado por e-mail — ele nasce da matrícula no curso de
                  simulados, que o sync lê do Canvas a cada 5 min. */}
              <p className="porta__ajuda">
                Se o Canvas disser que você não tem acesso ao SAS, confira com a coordenação a
                sua matrícula no curso de simulados do ITA/IME — é dela que sai a lista de
                alunos daqui.
              </p>
            </>
          )}

          {/* A travessia para a outra porta, discreta, no rodapé do painel.
              São ~900 alunos contra uma dúzia de coordenadores: o padrão é a
              porta do aluno, e a volta é um link, não uma aba.

              A cantina NÃO participa: ela mora noutra URL e não tem para onde
              atravessar — ver o comentário do tipo `Modo`. */}
          {onTrocarModo && modo !== 'cantina' && (
            <button
              type="button"
              className="porta__coordenacao"
              onClick={() => onTrocarModo(modo === 'coordenador' ? 'aluno' : 'coordenador')}
            >
              {modo === 'coordenador' ? 'Sou aluno' : 'Sou da coordenação'}
            </button>
          )}
        </div>
      </div>
    </div>
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
