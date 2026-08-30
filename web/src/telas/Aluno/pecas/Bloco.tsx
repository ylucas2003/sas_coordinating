import type { ReactNode } from 'react';
import { TarjaFonte } from './TarjaFonte';

// A superfície padrão da área do aluno: borda, raio de 18px, rótulo de olho no
// topo e a tarja da fonte no canto.
//
// Existe como componente, e não como classe CSS solta, por um motivo só: a
// tarja. Um bloco alimentado por mock sem marca é exatamente o que o inventário
// deveria impedir, e a única forma de garantir isso é a marca vir junto do
// contêiner. Passar `fonte` é a regra; não passar é dizer "este bloco não lê
// dado de servidor", que também é uma afirmação.
//
// ⚠️ Nunca sombra flutuante — é o que faz qualquer tela parecer template
// (docs/24 §7.2). A superfície se separa do fundo pela borda.

interface Props {
  /** A chave no `registro.ts`. Omitida, o bloco não tem fonte de dado. */
  fonte?: string;
  /** O rótulo de olho, em maiúscula pequena. */
  olho?: ReactNode;
  /** Aparece à direita do olho — contagem, link, ação curta. */
  acao?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Sem moldura: o bloco vira só agrupamento, mantendo o olho e a tarja. */
  nu?: boolean;
}

export function Bloco({ fonte, olho, acao, children, className = '', nu = false }: Props) {
  return (
    <section className={`alu-bloco${nu ? ' alu-bloco--nu' : ''} ${className}`.trim()}>
      {fonte && <TarjaFonte chave={fonte} />}
      {(olho || acao) && (
        <header className="alu-bloco__topo">
          {olho && <span className="alu-olho">{olho}</span>}
          {acao && <span className="alu-bloco__acao">{acao}</span>}
        </header>
      )}
      {children}
    </section>
  );
}
