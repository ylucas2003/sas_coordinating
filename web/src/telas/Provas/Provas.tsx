import { useSearchParams } from 'react-router-dom';

import { Ciclos } from '../Ciclos/Ciclos';
import { Simulados } from '../Simulados/Simulados';

/**
 * "Provas" — ciclos e simulados sob a mesma porta.
 *
 * Eram dois destinos do menu, e a distinção nunca foi de navegação: um ciclo
 * é um agrupamento de simulados, e o coordenador alterna entre as duas
 * leituras da mesma prova o tempo todo. Como aba, alternar custa um clique e
 * não perde o contexto.
 *
 * A aba vive na query (`?aba=simulados`) e não no estado: é o que faz o link
 * copiado abrir na aba certa, e o botão voltar do navegador funcionar.
 */
export function Provas() {
  const [params, setParams] = useSearchParams();
  const aba = params.get('aba') === 'simulados' ? 'simulados' : 'ciclos';

  function trocar(nova: 'ciclos' | 'simulados') {
    // `replace`: alternar aba não merece um degrau no histórico — voltar deve
    // sair de Provas, não desfazer cliques de aba.
    setParams(nova === 'ciclos' ? {} : { aba: nova }, { replace: true });
  }

  return (
    <div className="tela">
      <div className="abas" role="tablist" aria-label="Provas">
        <button
          role="tab"
          aria-selected={aba === 'ciclos'}
          className={`aba${aba === 'ciclos' ? ' is-active' : ''}`}
          onClick={() => trocar('ciclos')}
        >
          Ciclos
        </button>
        <button
          role="tab"
          aria-selected={aba === 'simulados'}
          className={`aba${aba === 'simulados' ? ' is-active' : ''}`}
          onClick={() => trocar('simulados')}
        >
          Simulados
        </button>
      </div>

      {aba === 'ciclos' ? <Ciclos /> : <Simulados />}
    </div>
  );
}
