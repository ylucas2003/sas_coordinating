import type { ReactNode } from 'react';
import { Topbar } from './Topbar';

/**
 * Casco do app da coordenação: topbar + a faixa onde a tela se desenha.
 *
 * O casco NÃO decide sobre sidebar: quem monta `<aside>` e `<main>` é a
 * própria rota, porque cada tela sabe que filtros tem.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      <Topbar />
      <div className="app-shell">
        <div className="app-body">{children}</div>
      </div>
    </>
  );
}
