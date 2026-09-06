import { useEffect, useRef, useState } from 'react';

interface Props {
  onPanoramaPDF: () => void;
  onPanoramaPNG: () => void;
  onPNG: () => void;
  onCSV: () => void;
  onPDF: () => void;
}

/**
 * Menu suspenso de exportação. Fecha ao clicar fora, ao escolher um item e no
 * Esc — as três saídas, porque o que ele abre é uma lista de ações que saem do
 * produto (PDF, PNG, CSV) e ficar preso nela é o pior estado possível.
 *
 * ⚠️ O que sai daqui vira PAPEL na mesa de alguém, com nome de menor de idade
 * impresso. Os geradores estão em `src/exportacao/` e o LEIA-ME de lá explica
 * por que são `.js` montando DOM à mão: não "modernize" a pasta.
 */
export function MenuExportar({ onPanoramaPDF, onPanoramaPNG, onPNG, onCSV, onPDF }: Props) {
  const [aberto, setAberto] = useState(false);
  const refRaiz = useRef<HTMLDivElement>(null);
  const refBotao = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!aberto) return;
    function aoClicarFora(ev: MouseEvent) {
      if (!refRaiz.current?.contains(ev.target as Node)) setAberto(false);
    }
    // Esc devolve o foco ao botão: sem isso o foco cai no `<body>` e quem
    // navega por teclado recomeça a tabulação do topo da página.
    function aoTeclar(ev: KeyboardEvent) {
      if (ev.key !== 'Escape') return;
      ev.stopPropagation();
      setAberto(false);
      refBotao.current?.focus();
    }
    document.addEventListener('click', aoClicarFora);
    document.addEventListener('keydown', aoTeclar);
    return () => {
      document.removeEventListener('click', aoClicarFora);
      document.removeEventListener('keydown', aoTeclar);
    };
  }, [aberto]);

  const item = (rotulo: string, dica: string, acao: () => void) => (
    <button
      type="button"
      className="export-menu__item"
      onClick={() => {
        acao();
        setAberto(false);
      }}
    >
      <span>{rotulo}</span>
      <span className="export-menu__item-dica">{dica}</span>
    </button>
  );

  return (
    <div className="export-menu aluno-ficha__nao-imprimir" ref={refRaiz}>
      <button
        type="button"
        ref={refBotao}
        className="export-menu__botao"
        aria-expanded={aberto}
        aria-haspopup="true"
        onClick={(ev) => {
          ev.stopPropagation();
          setAberto((a) => !a);
        }}
      >
        Exportar
        <span className="export-menu__seta" aria-hidden="true">▾</span>
      </button>

      {aberto && (
        <div className="export-menu__lista">
          <div className="export-menu__secao">Panorama do aluno</div>
          {item('PDF — completo', 'Identificação + classificações + heatmap + tabelas', onPanoramaPDF)}
          {item('PNG — imagem do panorama', 'Snapshot único — bom pra compartilhar', onPanoramaPNG)}

          <div className="export-menu__secao">Componentes específicos</div>
          {item('PDF da ficha atual', 'Imprime a página inteira com os filtros aplicados', onPDF)}
          {item('CSV do histórico', 'Tabela filtrada pra Excel', onCSV)}
          {item('PNG do gráfico', 'Só o gráfico de evolução', onPNG)}
        </div>
      )}
    </div>
  );
}
