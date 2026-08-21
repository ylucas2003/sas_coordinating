import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** O que mostrar no lugar. Recebe a mensagem do erro. */
  fallback: (mensagem: string) => ReactNode;
}

interface State {
  mensagem: string | null;
}

/**
 * Isola uma parte da árvore: um erro de render aqui dentro não derruba o
 * resto do app.
 *
 * Existe por causa do chat. Antes ele era montado fora da árvore de telas, e
 * uma exceção nele não podia afetar o painel; em React, sem isto, qualquer
 * erro no chat deixaria a página inteira em branco.
 */
export class LimiteDeErro extends Component<Props, State> {
  state: State = { mensagem: null };

  static getDerivedStateFromError(erro: unknown): State {
    return { mensagem: (erro as Error)?.message || 'erro desconhecido' };
  }

  componentDidCatch(erro: Error, info: ErrorInfo) {
    console.error('[limite-de-erro]', erro, info.componentStack);
  }

  render() {
    if (this.state.mensagem != null) return this.props.fallback(this.state.mensagem);
    return this.props.children;
  }
}
