import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

// O PADRÃO DE CAMPO — como uma tela pesada vira várias leves.
//
// Nasceu na aba Estudar da área do aluno (`telas/Aluno/Estudar.tsx`) e é a
// coisa que mais reduziu poluição visual na história do projeto. As cinco
// regras abaixo são a razão de ele funcionar: copiar a aparência sem elas dá
// um menu bonito e inútil
// (docs/brief-claude-design-coordenacao.md §O padrão de campo).
//
//   C1 · A DIVISÃO É POR PERGUNTA, nunca por tipo de objeto nem por recência.
//        "A prova estava boa?", não "Último simulado". Ninguém abre a
//        ferramenta querendo o último simulado; abre querendo saber se a prova
//        estava boa. É a regra inteira — as outras quatro são consequência.
//
//   C2 · O SUBTÍTULO É DADO VIVO, não descrição. "34 eventos hoje · 2
//        alterações de nota", nunca "veja o histórico". É o que separa um hub
//        de um menu: cada card relata o próprio estado, e a tela de entrada já
//        informa antes de qualquer clique.
//
//   C3 · O DESTINO É TELA INTEIRA, com URL própria. Não acordeão, não modal,
//        não aba. É a separação de ROLAGENS que faz o padrão funcionar.
//
//   C4 · A VOLTA É UM CHEVRON DE 44px NA MESMA LINHA DO TÍTULO.
//
//   C5 · O ELO QUIETO, para o que não merece um card — e ele SOME quando está
//        vazio ou quando a consulta falha.
//
// ── O que a prancheta acrescentou (docs/39 fase 1) ────────────────────────
//
// O Painel deixou de ser tabela com KPIs em cima e virou uma grade de campos,
// e isso cobrou do card quatro capacidades que o hub de Administração nunca
// precisou. Estão em `cardCiclo`, `cardSimulado` e `cardCantina` da prancheta
// "Painel e cantina", e cada uma resolve um problema declarado lá:
//
//   `magnitude`  o numeral grande. NÃO é um KPI: os quatro KPIs do Painel
//                antigo eram todos sobre o ciclo, e o card do ciclo já os
//                carregava. Sobrou UM número, e ele responde "preciso abrir
//                isto hoje?". Por isso só um card por tela o tem — é ele que
//                domina os outros, e a hierarquia sobrevive ao crescimento da
//                grade porque não vem do tamanho, vem do número.
//   `aviso`      a linha de baixo, para quando o atalho ENVELHECEU: "nenhum
//                ciclo em andamento — este encerrou há 7 semanas" (a frase é
//                montada em `Painel.tsx`). Sem ela o card mostra o dado de
//                julho como se fosse o de hoje.
//   `marca`      o selo curto ("Pendente", "Sem destino"), na linha do olho.
//   `inerte`     o card da cantina num sábado — ver a prop, que é onde mora a
//                distinção que importa.
//
// A outra mudança da prancheta é silenciosa e vale para os dois cards: o olho
// deixou de ser DADO e virou texto secundário. Azul é o valor MEDIDO (R3/R7,
// uma escala semântica por tela) e um rótulo de seção não é medida nenhuma —
// gastar o azul nele tirava do dado a única cor que o distingue.

interface PropsCartao {
  /** O olho, em sentence case: o CSS o põe em caixa alta. */
  olho: string;
  /** A PERGUNTA que este campo responde (C1), não o nome do objeto. */
  titulo: string;
  /**
   * O destino, tela inteira e com URL própria (C3). Opcional porque um card
   * pode não ter para onde ir — e um card sem destino é inerte por
   * construção, sem que ninguém precise declarar.
   */
  para?: string;
  /** O `<path>` do glifo de 70×70, em traço fino. Decorativo: quem nomeia o destino é o texto. */
  glifo?: ReactNode;
  /**
   * O dado vivo (C2). Os três estados são explícitos de propósito, porque é
   * neles que o padrão costuma ser implementado errado:
   *   `carregando`  → esqueleto, sem número
   *   `subtitulo` nulo com `carregando` falso → a frase de `vazio`, que convida
   *   `subtitulo` com texto → o par, com o número real
   *
   * Número fixo escrito no componente envelhece calado. Se o dado ainda não
   * existe no servidor, não escreva um: deixe o estado vazio aparecer.
   */
  carregando?: boolean;
  subtitulo?: string | null;
  vazio: string;
  /**
   * O numeral que decide se vale abrir o card hoje. Só um card por tela.
   *
   * `null` e ausente NÃO são a mesma coisa, pelo mesmo motivo da `contagem` do
   * elo quieto: `null` diz "este card TEM lugar de magnitude e ainda não sei o
   * número" — o esqueleto reserva o vão do numeral e a grade não pula quando o
   * dado chega. Ausente diz "este card não tem magnitude".
   */
  magnitude?: string | null;
  /** O que o numeral conta, em palavras: "cortados de 407 alunos". */
  magnitudeLegenda?: string;
  /** A linha que confessa que o atalho envelheceu. */
  aviso?: string | null;
  /** O selo curto, em sentence case: o CSS o põe em caixa alta. */
  marca?: string | null;
  /**
   * ⚠️ INERTE NÃO É DESABILITADO.
   *
   * Um card desabilitado diz "você não pode"; o inerte diz "não há". Ele é
   * superfície de contorno TRACEJADO, sem preenchimento, que não afunda ao ser
   * pressionada, não é link, não recebe foco — e o subtítulo passa a carregar
   * o MOTIVO ("sem refeição hoje · sábado"), porque um card que não leva a
   * lugar nenhum sem dizer por quê parece defeito.
   *
   * Existe como prop, e não só como "card sem `para`", para o caso em que o
   * destino existe mas não se aplica hoje.
   */
  inerte?: boolean;
  /**
   * O card pequeno da grade do Painel (`cardSimulado` e `cardCantina` da
   * prancheta): 148px, título de 20px, glifo de 44. É a metade que empilha ao
   * lado do card com magnitude, e as duas somadas fecham a borda inferior com
   * a dele.
   */
  compacto?: boolean;
}

export function CartaoDeCampo({
  olho, titulo, para, glifo, carregando = false, subtitulo = null, vazio,
  magnitude, magnitudeLegenda, aviso = null, marca = null, inerte = false,
  compacto = false,
}: PropsCartao) {
  const semDestino = inerte || !para;
  const classe = [
    'campo-cartao',
    compacto ? 'campo-cartao--compacto' : '',
    magnitude !== undefined ? 'campo-cartao--magnitude' : '',
    semDestino ? 'campo-cartao--inerte' : '',
  ].filter(Boolean).join(' ');

  const conteudo = (
    <>
      <span className="campo-cartao__texto">
        <span className="campo-cartao__topo">
          <span className="campo-cartao__olho">{olho}</span>
          {marca && <span className="campo-cartao__marca">{marca}</span>}
        </span>
        <span className="campo-cartao__titulo">{titulo}</span>
        {carregando ? (
          <span className="campo-cartao__esqueleto" aria-hidden="true">
            <span className="campo-cartao__esqueleto-bloco" />
            <span className="campo-cartao__esqueleto-linha" />
          </span>
        ) : (
          <>
            {magnitude != null && (
              <span className="campo-cartao__magnitude">
                <span className="campo-cartao__magnitude-numero">{magnitude}</span>
                {magnitudeLegenda && (
                  <span className="campo-cartao__magnitude-legenda">{magnitudeLegenda}</span>
                )}
              </span>
            )}
            <span className="campo-cartao__sub">{subtitulo ?? vazio}</span>
            {aviso && (
              <span className="campo-cartao__aviso">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="8.6" />
                  <path d="M12 7.6V12l3 2" />
                </svg>
                {aviso}
              </span>
            )}
          </>
        )}
      </span>
      {glifo && (
        <svg
          className="campo-cartao__glifo"
          width="70"
          height="70"
          viewBox="0 0 70 70"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
          strokeLinecap="round"
          aria-hidden="true"
        >
          {glifo}
        </svg>
      )}
    </>
  );

  // Sem destino não é `<Link>` desligado nem `<button disabled>`: é uma
  // superfície de leitura. Um link que não navega é a promessa quebrada mais
  // barata de escrever e a mais cara de descobrir.
  if (semDestino) return <div className={classe}>{conteudo}</div>;

  return <Link className={classe} to={para!}>{conteudo}</Link>;
}

interface PropsCabeca {
  titulo: string;
  /** Para onde o `‹` sobe. */
  para: string;
  /** Como o destino se chama, para o leitor de tela. */
  destino: string;
  /** Ações à direita do título, quando a tela tiver. */
  acoes?: ReactNode;
}

/**
 * C4 · O chevron de 44px NA MESMA LINHA do título.
 *
 * Nunca um "← Voltar" em linha própria acima: a 390px isso empurra o título
 * para fora da dobra, e o título é o que diz onde a pessoa está. É chevron
 * `‹`, não seta — a seta promete "desfazer", o chevron diz "subir um nível",
 * que é o que ele de fato faz.
 *
 * O nome acessível diz o DESTINO, não "voltar": quem navega por leitor de tela
 * ouve para onde vai, não que está recuando.
 */
export function CabecaDeCampo({ titulo, para, destino, acoes }: PropsCabeca) {
  return (
    <header className="campo-cabeca">
      <Link className="campo-cabeca__voltar" to={para} aria-label={`Voltar para ${destino}`}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 6l-6 6 6 6" />
        </svg>
      </Link>
      <h1 className="campo-cabeca__titulo">{titulo}</h1>
      {acoes && <div className="campo-cabeca__acoes">{acoes}</div>}
    </header>
  );
}

interface PropsElo {
  para: string;
  texto: string;
  /**
   * A contagem. `null` faz o elo SUMIR — e isso vale para os dois casos em que
   * ele deve sumir (C5):
   *
   *   vazio     atalho para uma lista vazia é convite para uma tela vazia;
   *   FALHOU    "0 pendências" para quem tem 34 é a mentira mais cara da tela.
   *
   * Por isso a contagem é `number | null` e não `number` com default zero: o
   * componente não tem como distinguir os dois, e quem chama tem.
   */
  contagem: number | null;
  /** Quando o elo deve aparecer mesmo sem contagem (um caminho, não uma lista). */
  semContagem?: boolean;
}

export function EloQuieto({ para, texto, contagem, semContagem = false }: PropsElo) {
  if (!semContagem && (contagem == null || contagem === 0)) return null;
  return (
    <Link className="campo-elo" to={para}>
      {texto}
      {contagem != null && <span className="campo-elo__contagem">{contagem}</span>}
    </Link>
  );
}

interface PropsEntrada {
  olho: string;
  /** A pergunta, numa linha só. */
  titulo: string;
  /** Uma linha de números vivos. `null` enquanto carrega ou quando não há. */
  numeros: string | null;
  para: string;
}

/**
 * O CARD DE ENTRADA — a versão baixa do card de campo, de 110px.
 *
 * Existe para a faixa de entrada do Painel, e a diferença de altura é a
 * decisão: o Painel NÃO vira um hub de campos. Na aba do aluno nenhum dos três
 * campos domina; aqui um domina esmagadoramente — a varredura. Virar hub
 * cobraria um clique a mais na tarefa mais frequente do dia, todo dia
 * (docs/brief-claude-design-coordenacao.md §Onde ele entra).
 *
 * ⚠️ A faixa ROLA PARA FORA — não é sticky. Você a vê ao chegar e ela some
 * assim que o trabalho começa. É assim que o Painel ganha os cards sem cobrar
 * espaço permanente da tarefa dominante.
 */
export function CartaoDeEntrada({ olho, titulo, numeros, para }: PropsEntrada) {
  return (
    <Link className="campo-entrada" to={para}>
      <span className="campo-entrada__olho">{olho}</span>
      <span className="campo-entrada__titulo">{titulo}</span>
      {numeros ? (
        <span className="campo-entrada__numeros">{numeros}</span>
      ) : (
        <span className="campo-entrada__esqueleto" aria-hidden="true" />
      )}
    </Link>
  );
}
