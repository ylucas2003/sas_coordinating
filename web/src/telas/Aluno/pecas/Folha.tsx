import { useCallback, useEffect, useId, useRef } from 'react';
import type { ReactNode } from 'react';
import { Icone } from './Icone';

// A folha: bottom sheet no celular, painel lateral no desktop.
//
// Serve a folha de filtros do Estudar e a do Tio Léo — as duas têm a mesma
// mecânica e alturas diferentes, então a altura é prop.
//
// ⚠️ A TENSÃO COM A D.1, e ela é deliberada (docs/27 §8). O docs/10 pede o chat
// NÃO-MODAL porque o modal bloqueia a navegação — é a reclamação do coordenador.
// Para o aluno no celular o cálculo é outro: sheet é o único padrão sensato num
// aparelho de 390px, e ele não precisa navegar enquanto conversa. Por isso o
// aluno tem folha modal e o coordenador segue com o painel lateral do
// `ChatLauncher`, que este arquivo não toca.
//
// No desktop a folha vira painel à direita e deixa de ser modal — a página
// continua utilizável, e aí a regra do docs/10 volta a valer.
//
// ⚠️ A DO TIO LÉO É A EXCEÇÃO NA FORMA, não na mecânica: no desktop ela é um
// cartão flutuante de 400×620 no canto, e não a faixa de altura total. Quem faz
// isso é `.alu-tioleo.alu-folha` em aluno-tioleo.css, escopado para não
// arrastar as outras quatro folhas junto. Continua não-modal.

export type AlturaDaFolha = 'espiada' | 'meio' | 'cheio';

interface Props {
  aberta: boolean;
  titulo: ReactNode;
  /** Segunda linha do cabeçalho, em minúsculo. */
  subtitulo?: ReactNode;
  /** Ícone circular à esquerda do título. */
  marca?: ReactNode;
  /** Ações à direita do X — histórico, limpar, etc. */
  acoes?: ReactNode;
  altura?: AlturaDaFolha;
  onFechar: () => void;
  /** Fixo na base, fora da área que rola: o "VER N QUESTÕES" do filtro. */
  rodape?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Folha({
  aberta,
  titulo,
  subtitulo,
  marca,
  acoes,
  altura = 'meio',
  onFechar,
  rodape,
  children,
  className = '',
}: Props) {
  const idTitulo = useId();
  const painel = useRef<HTMLDivElement>(null);
  const focoAnterior = useRef<HTMLElement | null>(null);

  // Esc fecha, e o foco volta para quem abriu. Sem a volta do foco, quem usa
  // teclado é devolvido ao topo do documento a cada fechamento.
  useEffect(() => {
    if (!aberta) return;
    focoAnterior.current = document.activeElement as HTMLElement | null;

    function aoTeclar(ev: KeyboardEvent) {
      if (ev.key === 'Escape') {
        ev.stopPropagation();
        onFechar();
      }
    }
    document.addEventListener('keydown', aoTeclar);

    // O scroll do fundo trava só no celular, onde a folha é modal. No desktop
    // ela é painel lateral e a página tem de continuar rolando.
    const modal = window.matchMedia('(max-width: 899px)').matches;
    const overflowAnterior = document.body.style.overflow;
    if (modal) document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', aoTeclar);
      document.body.style.overflow = overflowAnterior;
      focoAnterior.current?.focus?.();
    };
  }, [aberta, onFechar]);

  // O primeiro foco vai para o painel, não para o botão de fechar: quem abre
  // uma folha quer ler o conteúdo, e anunciar "Fechar" como primeira coisa
  // inverte a ordem da leitura.
  useEffect(() => {
    if (aberta) painel.current?.focus();
  }, [aberta]);

  const cliqueNoFundo = useCallback(
    (ev: React.MouseEvent) => {
      if (ev.target === ev.currentTarget) onFechar();
    },
    [onFechar],
  );

  if (!aberta) return null;

  return (
    <div className="alu-folha-fundo" onClick={cliqueNoFundo}>
      <div
        ref={painel}
        className={`alu-folha alu-folha--${altura} ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        tabIndex={-1}
      >
        {/* A alça é decorativa: quem arrasta no celular arrasta a folha
            inteira, e no teclado o Esc já fecha. `aria-hidden` para o leitor
            de tela não anunciar um elemento sem função. */}
        <span className="alu-folha__alca" aria-hidden="true" />

        <header className="alu-folha__topo">
          {marca && <span className="alu-folha__marca">{marca}</span>}
          <span className="alu-folha__titulos">
            <span className="alu-folha__titulo" id={idTitulo}>
              {titulo}
            </span>
            {subtitulo && <span className="alu-folha__subtitulo">{subtitulo}</span>}
          </span>
          <span className="alu-folha__acoes">
            {acoes}
            <button
              type="button"
              className="alu-folha__botao-icone"
              onClick={onFechar}
              aria-label="Fechar"
            >
              <Icone nome="fechar" tamanho={20} />
            </button>
          </span>
        </header>

        <div className="alu-folha__corpo">{children}</div>

        {rodape && <footer className="alu-folha__rodape">{rodape}</footer>}
      </div>
    </div>
  );
}
