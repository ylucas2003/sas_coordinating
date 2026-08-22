// Mapa de rotas do app da coordenação.
//
// Equivalente ao antigo `js/router.js`, com duas diferenças: os caminhos são
// reais (`/alunos/A023`, não `#/alunos/A023`) e quem casa o padrão é o React
// Router. O que sobrou aqui é o que o roteador não sabe: qual sidebar cada
// rota mostra.

/** Que sidebar a rota mostra. */
export type TipoSidebar = 'nenhuma' | 'ciclos' | 'filtros';

/**
 * Sidebar de cada rota — espelha os conjuntos `ROTAS_SEM_SIDEBAR` e
 * `ROTAS_COM_FILTROS` que viviam em `js/main.js`.
 *
 * - `ciclos`: só o painel, que lista os ciclos na lateral.
 * - `filtros`: as três listagens, que filtram na lateral.
 * - `nenhuma`: fichas (layout próprio) e a importação (tela cheia).
 */
export function sidebarPara(caminho: string): TipoSidebar {
  const partes = caminho.split('/').filter(Boolean);
  const raiz = partes[0] ?? '';
  const temId = partes.length > 1;

  if (raiz === '' || raiz === 'painel') return 'ciclos';
  if (temId) return 'nenhuma';
  if (raiz === 'alunos' || raiz === 'simulados' || raiz === 'ciclos' || raiz === 'auditoria') return 'filtros';
  return 'nenhuma';
}
