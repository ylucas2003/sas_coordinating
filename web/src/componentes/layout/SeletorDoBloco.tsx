import { Link, useLocation } from 'react-router-dom';

import { caminhoAoTrocarDeBloco, ehListaDoBloco, rotuloDoBloco } from '../../dominio/blocos';
import { useBlocos } from '../../hooks/consultas';
import { useSerieDaTela } from './migalhas';

/**
 * A troca de bloco no celular, no topo da tela (docs/44 §4).
 *
 * A barra inferior não comporta os blocos, então lá ela mostra só o bloco em que
 * se está, e é aqui que se troca. Só aparece nas listas: uma ficha pertence a uma
 * coisa só, e o `@media` de `casco.css` a esconde no desktop, onde o rail mostra
 * tudo.
 */
export function SeletorDoBloco() {
  const { pathname } = useLocation();
  const { data: blocos = [] } = useBlocos();
  const atual = useSerieDaTela();

  if (blocos.length < 2 || !ehListaDoBloco(pathname)) return null;

  return (
    <nav className="seletor-bloco" aria-label="Turmas">
      {blocos.map(({ serie, alunos, alertas }) => (
        <Link
          key={serie}
          className={`seletor-bloco__item${serie === atual ? ' is-active' : ''}`}
          aria-current={serie === atual ? 'page' : undefined}
          to={caminhoAoTrocarDeBloco(pathname, serie)}
        >
          <span className="seletor-bloco__nome">{rotuloDoBloco(serie)}</span>
          <span className="seletor-bloco__detalhe">
            {alunos.toLocaleString('pt-BR')}
            {alertas > 0 ? ` · ${alertas} ${alertas === 1 ? 'alerta' : 'alertas'}` : ''}
          </span>
        </Link>
      ))}
    </nav>
  );
}
