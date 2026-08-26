import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

// Selo de informação — quadradinho dourado com "i" azul que revela um texto
// explicativo ao tocar/clicar. Nasceu do aviso da página original da prova
// (telas/Banco/CartaoQuestao.tsx), que ocupava uma linha inteira do cartão
// mesmo sendo lido uma vez só.
//
// Portal pro <body>, como o Dialogo (componentes/dialogos/Dialogo.tsx): o
// cartão de questão tem `overflow: hidden` (styles/banco.css), então um
// balão posicionado dentro dele cortaria pela borda do card.

interface Props {
  texto: string;
  /** Nome acessível do botão — o texto do balão já é lido via aria-describedby. */
  rotulo?: string;
}

const MARGEM_VIEWPORT = 8;
const LARGURA_BALAO = 260;

export function BotaoInfo({ texto, rotulo = 'Mais informações' }: Props) {
  const [aberto, setAberto] = useState(false);
  const [posicao, setPosicao] = useState<{ top: number; left: number } | null>(null);
  const botaoRef = useRef<HTMLButtonElement>(null);
  const idBalao = useId();

  function abrir() {
    const rect = botaoRef.current?.getBoundingClientRect();
    if (!rect) return;
    const left = Math.min(
      Math.max(rect.left, MARGEM_VIEWPORT),
      window.innerWidth - LARGURA_BALAO - MARGEM_VIEWPORT,
    );
    setPosicao({ top: rect.bottom + 6, left });
    setAberto(true);
  }

  function fechar() {
    setAberto(false);
  }

  // Fecha em clique fora, Esc ou rolagem — o balão é `position: fixed` num
  // ponto calculado na abertura; rolar a lista o deixaria flutuando no lugar
  // errado, então some em vez de seguir o card.
  useEffect(() => {
    if (!aberto) return;
    // `setAberto(false)` direto, e não `fechar()`: setters de estado são
    // estáveis entre renders, mas `fechar` é recriada a cada um — colocá-la
    // como dependência faria o efeito reanexar os listeners toda hora.
    function aoClicarFora(ev: MouseEvent) {
      if (!botaoRef.current?.contains(ev.target as Node)) setAberto(false);
    }
    function aoTeclar(ev: KeyboardEvent) {
      if (ev.key === 'Escape') setAberto(false);
    }
    function aoRolar() {
      setAberto(false);
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
        onClick={() => (aberto ? fechar() : abrir())}
      >
        i
      </button>
      {aberto && posicao &&
        createPortal(
          <div
            id={idBalao}
            role="tooltip"
            className="botao-info__balao"
            style={{ top: posicao.top, left: posicao.left, width: LARGURA_BALAO }}
          >
            {texto}
          </div>,
          document.body,
        )}
    </>
  );
}
