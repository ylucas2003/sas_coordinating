import type { ReactNode } from 'react';

interface Props {
  rotulo: string;
  children: ReactNode;
}

/** Sidebar das telas em React: o card lateral com rótulo e conteúdo livre. */
export function Sidebar({ rotulo, children }: Props) {
  return (
    <aside className="card sidebar">
      <div className="sidebar__label">{rotulo}</div>
      {children}
    </aside>
  );
}
