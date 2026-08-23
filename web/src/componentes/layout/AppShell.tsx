import type { ReactNode } from 'react';
import { Rail } from './Rail';
import { Topbar } from './Topbar';
import { ProvedorMigalhas } from './migalhas';

/**
 * Casco da coordenação: rail de ícones à esquerda, topbar com migalhas em
 * cima, tela no resto.
 *
 * Diferente do casco anterior, este NÃO abre espaço para uma sidebar de
 * filtros: os filtros viraram faixa de pílulas dentro da própria tela, o que
 * devolve a largura inteira para as tabelas.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ProvedorMigalhas>
      <div className="casco">
        <Rail />
        <div className="casco__coluna">
          <Topbar />
          <main className="casco__main">{children}</main>
        </div>
      </div>
    </ProvedorMigalhas>
  );
}
