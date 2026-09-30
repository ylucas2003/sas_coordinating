import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

// Selo de informação — quadradinho dourado com "i" azul que revela um texto
// explicativo ao passar o mouse, ao focar pelo teclado ou ao tocar/clicar.
// Nasceu do aviso da página original da prova (telas/Banco/CartaoQuestao.tsx),
// que ocupava uma linha inteira do cartão mesmo sendo lido uma vez só.
//
// Portal pro <body>, como o Dialogo (componentes/dialogos/Dialogo.tsx): o
// cartão de questão tem `overflow: hidden` (styles/banco.css), então um
// balão posicionado dentro dele cortaria pela borda do card.

interface Props {
  /** O que o balão diz. `ReactNode` para aceitar uma explicação com estrutura. */
  texto: ReactNode;
  /** Nome acessível do botão — o texto do balão já é lido via aria-describedby. */
  rotulo?: string;
  /** Largura do balão em px. Explicação com lista pede mais que uma frase. */
  largura?: number;
}

/**
 * Como o balão foi aberto — e é isso que decide como ele fecha.
 *
 *  - `'passagem'`: mouse em cima ou foco de teclado. Some quando o mouse sai ou
 *    o foco vai embora; quem só passou por ali não precisa fechar nada.
 *  - `'fixo'`: a pessoa clicou/tocou. Fica até um segundo clique, Esc, clique
 *    fora ou rolagem — é o único modo que existe no celular, onde não há hover,
 *    e o que permite ler com calma sem manter o mouse parado em 18px.
 */
type Modo = 'passagem' | 'fixo';

const MARGEM_VIEWPORT = 8;
const LARGURA_PADRAO = 260;

export function BotaoInfo({ texto, rotulo = 'Mais informações', largura = LARGURA_PADRAO }: Props) {
  const [modo, setModo] = useState<Modo | null>(null);
  const [posicao, setPosicao] = useState<{ top: number; left: number } | null>(null);
  const botaoRef = useRef<HTMLButtonElement>(null);
  const idBalao = useId();
  const aberto = modo !== null;

  // Mede a posição a cada abertura: o botão pode ter se movido desde a última
  // (a lista de réguas, por exemplo, abre e fecha debaixo dele).
  function abrir(como: Modo) {
    const rect = botaoRef.current?.getBoundingClientRect();
    if (!rect) return;
    const left = Math.min(
      Math.max(rect.left, MARGEM_VIEWPORT),
      window.innerWidth - largura - MARGEM_VIEWPORT,
    );
    setPosicao({ top: rect.bottom + 6, left });
    setModo(como);
  }

  // Fecha em clique fora, Esc ou rolagem — o balão é `position: fixed` num
  // ponto calculado na abertura; rolar a lista o deixaria flutuando no lugar
  // errado, então some em vez de seguir o card.
  useEffect(() => {
    if (!aberto) return;
    // `setModo(null)` direto, e não uma função local: setters de estado são
    // estáveis entre renders, mas uma função declarada no corpo é recriada a
    // cada um — colocá-la como dependência faria o efeito reanexar os
    // listeners toda hora.
    function aoClicarFora(ev: MouseEvent) {
      if (!botaoRef.current?.contains(ev.target as Node)) setModo(null);
    }
    function aoTeclar(ev: KeyboardEvent) {
      if (ev.key === 'Escape') setModo(null);
    }
    function aoRolar() {
      setModo(null);
    }
    document.addEventListener('mousedown', aoClicarFora);
    document.addEventListener('keydown', aoTeclar);
    window.addEventListener('scroll', aoRolar, true);
    return () => {
      document.removeEventListener('mousedown', aoClicarFora);
      document.removeEventListener('keydown', aoTeclar);
      window.removeEventListener('scroll', aoRolar, true);
    };
  }, [aberto]);

  return (
    <>
      <button
        ref={botaoRef}
        type="button"
        className="botao-info"
        aria-label={rotulo}
        aria-expanded={aberto}
        aria-describedby={aberto ? idBalao : undefined}
        // Clicar num balão aberto por passagem o FIXA, em vez de fechá-lo: no
        // mouse o `mouseenter` já o abriu um instante antes, e no toque o
        // navegador emula `mouseenter` antes do `click`. Se o clique fechasse, o
        // toque abriria e fecharia na mesma ação e o "i" nunca apareceria.
        onClick={() => (modo === 'fixo' ? setModo(null) : abrir('fixo'))}
        onMouseEnter={() => modo === null && abrir('passagem')}
        onMouseLeave={() => modo === 'passagem' && setModo(null)}
        onFocus={() => modo === null && abrir('passagem')}
        onBlur={() => modo === 'passagem' && setModo(null)}
      >
        i
      </button>
      {aberto && posicao &&
        createPortal(
          <div
            id={idBalao}
            role="tooltip"
            className="botao-info__balao"
            style={{ top: posicao.top, left: posicao.left, width: largura }}
          >
            {texto}
          </div>,
          document.body,
        )}
    </>
  );
}
