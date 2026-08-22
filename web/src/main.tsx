import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { App } from './App';

// CSS global, na mesma ordem em que o `index.html` os carregava. Os arquivos
// por tela vão virando CSS Modules conforme cada tela migra; o que fica aqui
// para sempre são tokens, base e fontes.
import '../styles/fontes.css';
import '../styles/tokens.css';
import '../styles/base.css';
import '../styles/layout.css';
import '../styles/simulados.css';
import '../styles/auditoria.css';
import '../styles/painel.css';
import '../styles/aluno-ficha.css';
import '../styles/filtros.css';
import '../styles/chat.css';
import '../styles/edicao.css';
import '../styles/aluno.css';
import '../styles/login.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Os dados do SAS só mudam quando entra planilha nova ou alguém edita
      // algo — não vale revalidar a cada foco de janela. É o mesmo raciocínio
      // do `cacheGet` antigo, com um teto de frescor em vez de cache eterno.
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const raiz = document.getElementById('root');
if (!raiz) throw new Error('Elemento #root não encontrado no index.html');

createRoot(raiz).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
