import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';

import { QUADRO, RAIL } from '../../dominio/tour';
import type { PassoMontado } from '../../dominio/tour';
// ⚠️ Como `provas.css`, esta folha é importada AQUI e não em `main.tsx`, onde
// moram todas as outras: `main.tsx` não estava no escopo desta rodada. Nada em
// `onboarding.css` redefine classe de outra folha, então a posição dela no
// bundle não muda desenho nenhum — mas o lugar certo dela é junto das irmãs, e
// isso fica registrado como pendência.
import '../../../styles/onboarding.css';

/**
 * O TOUR — "como se lê um ciclo e uma prova", em seis passos.
 *
 * ┌── A DECISÃO DE ESCOPO, que era a que sobrava ────────────────────────┐
 * │ Os seis passos da prancheta são todos do ramo de PROVAS. Como        │
 * │ onboarding, ou ele ganhava os outros quatro ramos ou ficava órfão    │
 * │ numa aba só. Ele NÃO ganhou os outros ramos, e a escolha é esta:     │
 * │                                                                      │
 * │ ele não é "conheça o SAS", é "como se lê um ciclo e uma prova" —     │
 * │ a parte mais densa do produto e a única que ninguém acerta sozinha.  │
 * │                                                                      │
 * │ Alunos, Banco e Administração são telas que se explicam ao abrir:    │
 * │ uma lista com filtros, um acervo com busca, quatro campos com o      │
 * │ nome do que fazem. O ciclo não: ali há uma RÉGUA que muda quem está  │
 * │ cortado, uma tabela que ordena por distância porque a cor deixou de  │
 * │ significar, e uma calibração que só faz sentido com os doze          │
 * │ histogramas dividindo o mesmo pico. Nada disso se deduz olhando.     │
 * │                                                                      │
 * │ Um tour que fingisse cobrir o produto inteiro cobraria seis passos   │
 * │ de quem já sabe abrir uma lista, e ainda assim não explicaria a      │
 * │ régua. Este é honesto sobre o que cobre: o rótulo do gatilho diz     │
 * │ "como se lê um ciclo e uma prova", não "conheça o SAS".              │
 * │                                                                      │
 * │ Por isso ele abre em DOIS lugares e não num só: o Painel, que é a    │
 * │ home onde o coordenador novo chega toda manhã, e o hub de Provas,    │
 * │ que é o assunto. Ficar só em Provas seria escondê-lo de quem ainda   │
 * │ não sabe que Provas é onde a resposta está.                          │
 * └──────────────────────────────────────────────────────────────────────┘
 *
 * O que mudou da prancheta para cá, e por quê:
 *
 *   ABRIR E FECHAR   lá era um estado do mock. Aqui é diálogo de verdade:
 *                    Esc fecha, o foco fica preso enquanto aberto e volta
 *                    para quem abriu (a mecânica é a de `Aluno/pecas/Folha`).
 *   O "JÁ VI"        `memoria.ts`. Um coordenador não quer o tour toda manhã.
 *   O DESTINO        lá o passo trocava a tela do mock junto. Aqui não há
 *                    como iluminar uma região de uma tela em que a pessoa não
 *                    está, então cada passo mostra o ESQUEMA da região e
 *                    oferece a porta — que `dominio/tour.ts` mantém apontando
 *                    para o endereço de hoje.
 */

interface Props {
  passos: readonly PassoMontado[];
  /** Fechar por Esc, pelo X, pelo "Pular" ou pelo "Entendi" — é tudo fechar. */
  aoFechar: () => void;
  /** Para onde devolver o foco quando não havia foco na abertura (auto-abertura). */
  focoDeVolta?: RefObject<HTMLElement | null>;
}

/** O que o Tab e o Shift+Tab podem alcançar dentro do painel. */
const FOCAVEIS = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Tour({ passos, aoFechar, focoDeVolta }: Props) {
  const [indice, setIndice] = useState(0);
  const painel = useRef<HTMLDivElement>(null);
  const focoAnterior = useRef<HTMLElement | null>(null);
  const idTitulo = useId();

  const passo = passos[indice];
  const ultimo = indice === passos.length - 1;

  const avancar = useCallback(() => {
    setIndice((i) => (i < passos.length - 1 ? i + 1 : i));
  }, [passos.length]);
  const voltar = useCallback(() => setIndice((i) => Math.max(0, i - 1)), []);

  // Quem abriu, e para onde o foco volta.
  //
  // Efeito PRÓPRIO, com dependências estáveis: junto com os atalhos de teclado
  // ele reexecutaria a cada render em que `aoFechar` mudasse de identidade —
  // e cada reexecução devolveria o foco no cleanup, arrancando-o do botão que
  // a pessoa estava usando.
  useEffect(() => {
    focoAnterior.current = document.activeElement as HTMLElement | null;
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = overflowAnterior;
      // Auto-abertura não tem "quem abriu": o foco estava no `<body>`, e
      // devolvê-lo para lá é o mesmo que perdê-lo. Nesse caso a volta é para o
      // gatilho, que é onde a pessoa reabre o tour se quiser rever.
      const anterior = focoAnterior.current;
      const volta = anterior && anterior !== document.body ? anterior : focoDeVolta?.current;
      volta?.focus?.();
    };
  }, [focoDeVolta]);

  // Esc fecha, Tab circula dentro, ← e → andam nos passos.
  //
  // O foco PRESO é o que separa um diálogo de uma sobreposição decorativa: sem
  // ele o Tab passa por baixo do véu e quem usa teclado começa a operar uma
  // tela que não pode ver.
  useEffect(() => {
    function aoTeclar(ev: KeyboardEvent) {
      if (ev.key === 'Escape') {
        ev.stopPropagation();
        aoFechar();
        return;
      }
      if (ev.key === 'ArrowRight') return avancar();
      if (ev.key === 'ArrowLeft') return voltar();
      if (ev.key !== 'Tab') return;

      const alvos = painel.current?.querySelectorAll<HTMLElement>(FOCAVEIS);
      if (!alvos || alvos.length === 0) return;
      const primeiro = alvos[0];
      const derradeiro = alvos[alvos.length - 1];
      const atual = document.activeElement;
      // Fora do painel (o foco escapou de alguma forma) o Tab volta para dentro.
      if (!painel.current?.contains(atual)) {
        ev.preventDefault();
        primeiro.focus();
      } else if (ev.shiftKey && atual === primeiro) {
        ev.preventDefault();
        derradeiro.focus();
      } else if (!ev.shiftKey && atual === derradeiro) {
        ev.preventDefault();
        primeiro.focus();
      }
    }

    document.addEventListener('keydown', aoTeclar);
    return () => document.removeEventListener('keydown', aoTeclar);
  }, [aoFechar, avancar, voltar]);

  // O primeiro foco vai para o painel, e não para "Próximo": quem abre um tour
  // quer LER o passo, e anunciar o botão antes do texto inverte a ordem.
  useEffect(() => {
    painel.current?.focus();
  }, []);

  if (!passo) return null;

  return createPortal(
    <div className="tour-veu">
      <div
        ref={painel}
        className="tour"
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        tabIndex={-1}
      >
        <div className="tour__topo">
          <span className="tour__olho">{passo.olho}</span>
          <span className="tour__contador">{passo.contador}</span>
        </div>

        <EsquemaDaRegiao regiao={passo.regiao} />

        <h2 className="tour__titulo" id={idTitulo}>{passo.titulo}</h2>
        <p className="tour__texto">{passo.texto}</p>
        {/* A regra citada, na moldura de ouro: é o VALOR — a régua de desenho
            do produto —, e não mais um parágrafo do texto. */}
        <p className="tour__regra">{passo.regra}</p>

        {passo.destino && (
          <Link className="tour__destino" to={passo.destino.para} onClick={aoFechar}>
            {passo.destino.rotulo}
            <svg width="18" height="12" viewBox="0 0 20 14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
              <path d="M2 7h15M13 3l4 4-4 4" />
            </svg>
          </Link>
        )}

        {/* Decorativo: quem diz em que passo a pessoa está é o contador, que é
            texto. Seis traços sem rótulo não acrescentam nada ao leitor de tela. */}
        <div className="tour__trilha" aria-hidden="true">
          {passos.map((p, i) => (
            <span
              key={p.chave}
              className={i === indice ? 'tour__traco tour__traco--atual' : 'tour__traco'}
            />
          ))}
        </div>

        <div className="tour__acoes">
          <button type="button" className="tour__pular" onClick={aoFechar}>
            {ultimo ? 'Fechar' : 'Pular o tour'}
          </button>
          <button
            type="button"
            className="btn btn--ghost tour__botao"
            onClick={voltar}
            disabled={indice === 0}
          >
            Voltar
          </button>
          <button
            type="button"
            className="btn btn-primary tour__botao"
            onClick={ultimo ? aoFechar : avancar}
          >
            {ultimo ? 'Entendi' : 'Próximo'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/**
 * ONDE a região fica na tela — o esquema, não a tela.
 *
 * Na prancheta o passo abria um buraco no véu por cima do mock: dava para
 * apontar porque a tela estava ali atrás. No produto o tour abre a partir do
 * Painel e do hub, e iluminar uma região da ficha de ciclo por cima do Painel
 * apontaria para o lugar errado — que é exatamente o defeito que este trabalho
 * tinha de evitar.
 *
 * A saída é o esquema: um quadro de 1440×900 com o rail e a topbar em fio, e a
 * região acesa em `--sas-superficie` contra o `--sas-superficie-2` do resto. A
 * pessoa aprende ONDE olhar antes de chegar lá, e nada mente sobre a tela em
 * que ela está agora.
 */
function EsquemaDaRegiao({ regiao }: { regiao: PassoMontado['regiao'] }) {
  return (
    <svg
      className="tour__esquema"
      viewBox={`0 0 ${QUADRO.largura} ${QUADRO.altura}`}
      aria-hidden="true"
    >
      <rect
        x="2" y="2" width={QUADRO.largura - 4} height={QUADRO.altura - 4} rx="20"
        fill="var(--sas-superficie-2)" stroke="var(--sas-borda)" strokeWidth="4"
      />
      {/* O rail e a topbar, em fio: dois traços bastam para o quadro ler como
          uma tela do produto e não como um retângulo qualquer. */}
      <path
        d={`M${RAIL} 12V${QUADRO.altura - 12}M${RAIL} 72H${QUADRO.largura - 12}`}
        stroke="var(--sas-fio-forte)" strokeWidth="3" fill="none"
      />
      <rect
        x={regiao.x} y={regiao.y} width={regiao.largura} height={regiao.altura} rx="18"
        fill="var(--sas-superficie)" stroke="var(--sas-dado)" strokeWidth="6"
      />
    </svg>
  );
}
