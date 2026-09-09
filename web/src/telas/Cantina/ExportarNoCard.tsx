import { useEffect, useId, useRef, useState } from 'react';

/**
 * O gesto de exportar no canto de um card de hub (docs/40 §12.3).
 *
 * ⚠️ **Não vai DENTRO do card.** O `CartaoDeCampo` inteiro é um `<Link>`, e um
 * `<button>` dentro de uma âncora é HTML inválido e armadilha de teclado. Este
 * componente é passado como `acao` e renderizado como irmão do link — dois
 * alvos honestos, dois pontos de tabulação, 44 px cada.
 *
 * O menu é `<details>`, e a escolha é deliberada: ele abre e fecha sem estado
 * nosso, fecha no Esc de graça, e é acessível por teclado sem nenhuma linha de
 * ARIA escrita à mão. Um popover próprio custaria trinta linhas para reproduzir
 * o que o navegador já faz — e reproduziria pior.
 */

export interface SaidaExportavel {
  rotulo: string;
  /** Um `href` para baixar do servidor, ou uma função que gera no cliente. */
  href?: string;
  onEscolher?: () => void;
  /** Desabilitada com o motivo à mostra — botão cinza sem explicação ensina a
      desconfiar da tela. */
  indisponivel?: string;
}

export function ExportarNoCard({ saidas, oQue }: { saidas: SaidaExportavel[]; oQue: string }) {
  const id = useId();
  const caixa = useRef<HTMLDetailsElement>(null);
  const [aberto, setAberto] = useState(false);

  // Fecha ao clicar fora. Sem isto, o menu fica aberto atrás da próxima tela —
  // e o `<details>` não faz isso sozinho.
  useEffect(() => {
    if (!aberto) return;
    function fora(evento: MouseEvent) {
      if (!caixa.current?.contains(evento.target as Node)) setAberto(false);
    }
    document.addEventListener('mousedown', fora);
    return () => document.removeEventListener('mousedown', fora);
  }, [aberto]);

  return (
    <details
      ref={caixa}
      className="campo-exportar"
      open={aberto}
      onToggle={(e) => setAberto((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="campo-exportar__gatilho" aria-label={`Exportar ${oQue}`} title={`Exportar ${oQue}`}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 4v11" />
          <path d="M7.5 10.5 12 15l4.5-4.5" />
          <path d="M5 19h14" />
        </svg>
      </summary>

      <ul className="campo-exportar__menu" id={id}>
        {saidas.map((saida) => (
          <li key={saida.rotulo}>
            {saida.indisponivel ? (
              <span className="campo-exportar__item campo-exportar__item--inerte">
                {saida.rotulo}
                <small>{saida.indisponivel}</small>
              </span>
            ) : saida.href ? (
              <a className="campo-exportar__item" href={saida.href} download onClick={() => setAberto(false)}>
                {saida.rotulo}
              </a>
            ) : (
              <button
                type="button"
                className="campo-exportar__item"
                onClick={() => { saida.onEscolher?.(); setAberto(false); }}
              >
                {saida.rotulo}
              </button>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
