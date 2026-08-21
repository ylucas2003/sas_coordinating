import { useEffect, useRef, useState } from 'react';

interface Props {
  onPanoramaPDF: () => void;
  onPanoramaPNG: () => void;
  onPNG: () => void;
  onCSV: () => void;
  onPDF: () => void;
}

/** Menu suspenso de exportação. Fecha ao clicar fora ou ao escolher um item. */
export function MenuExportar({ onPanoramaPDF, onPanoramaPNG, onPNG, onCSV, onPDF }: Props) {
  const [aberto, setAberto] = useState(false);
  const refRaiz = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!aberto) return;
    function aoClicarFora(ev: MouseEvent) {
      if (!refRaiz.current?.contains(ev.target as Node)) setAberto(false);
    }
    document.addEventListener('click', aoClicarFora);
    return () => document.removeEventListener('click', aoClicarFora);
  }, [aberto]);

  const item = (rotulo: string, dica: string, acao: () => void) => (
    <button
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
        className="export-menu__botao"
        onClick={(ev) => {
          ev.stopPropagation();
          setAberto((a) => !a);
        }}
      >
        Exportar
        <span className="export-menu__seta">▾</span>
      </button>

      <div className="export-menu__lista" style={{ display: aberto ? 'flex' : 'none' }}>
        <div className="export-menu__secao">Panorama do aluno</div>
        {item('PDF — completo', 'Identificação + classificações + heatmap + tabelas', onPanoramaPDF)}
        {item('PNG — imagem do panorama', 'Snapshot único — bom pra compartilhar', onPanoramaPNG)}

        <div className="export-menu__secao">Componentes específicos</div>
        {item('PDF da ficha atual', 'Imprime a página inteira com os filtros aplicados', onPDF)}
        {item('CSV do histórico', 'Tabela filtrada pra Excel', onCSV)}
        {item('PNG do gráfico', 'Só o gráfico de evolução', onPNG)}
      </div>
    </div>
  );
}
