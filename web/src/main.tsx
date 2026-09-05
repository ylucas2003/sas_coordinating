import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { App } from './App';

// CSS global, na mesma ordem em que o `index.html` os carregava. Os arquivos
// por tela vão virando CSS Modules conforme cada tela migra; o que fica aqui
// para sempre são tokens, base e fontes.
import '../styles/fontes.css';
// A pilha de cor, e a ordem dela é obrigatória: os hexadecimais crus
// (`paleta.css`), depois os seis papéis com os três blocos de tema
// (`papeis.css`), e só então os aliases — `tokens.css` para a coordenação e
// `aluno-tokens.css` lá embaixo para o aluno. Alias antes de papel resolveria
// para vazio. Ver o cabeçalho de cada um.
import '../styles/paleta.css';
import '../styles/papeis.css';
import '../styles/tokens.css';
import '../styles/base.css';
// KaTeX vem antes do nosso `markdown.css`, que ajusta corpo e margem do que ele
// desenha. As fontes vêm no próprio pacote npm e o Vite as emite como asset do
// nosso domínio — nenhuma requisição sai para CDN (CLAUDE.md, armadilha 6).
import 'katex/dist/katex.min.css';
import '../styles/markdown.css';
import '../styles/casco.css';
import '../styles/layout.css';
import '../styles/simulados.css';
import '../styles/auditoria.css';
import '../styles/painel.css';
import '../styles/aluno-ficha.css';
import '../styles/filtros.css';
import '../styles/chat.css';
import '../styles/edicao.css';
// Área do aluno: tokens primeiro (os `--alu-*` dos dois temas), depois o casco,
// as peças compartilhadas, e uma folha por tela.
//
// O antigo `aluno.css` foi removido junto com `PainelAluno`, `SimuladosAluno` e
// `ShellAluno`: ele redefinia `.alu-shell` com `height: 100dvh; overflow:
// hidden`, e como era importado ANTES daqui, o casco novo herdava altura fixa e
// deixava de rolar. Colisão de prefixo entre duas gerações da mesma área.
import '../styles/aluno-tokens.css';
import '../styles/aluno-casco.css';
import '../styles/aluno-questao.css';
import '../styles/aluno-hoje.css';
import '../styles/aluno-estudar.css';
import '../styles/aluno-treino.css';
import '../styles/aluno-provas.css';
import '../styles/aluno-jornada.css';
import '../styles/aluno-tioleo.css';
import '../styles/aluno-login.css';
import '../styles/banco.css';
import '../styles/login.css';
import '../styles/foto-perfil.css';
import '../styles/integracoes.css';
// Por ÚLTIMO, e é obrigatório: o `@media print` de `documento.css` remapeia a
// paleta inteira para `--doc-*`, e blocos `:root` têm a mesma especificidade —
// quem vem depois vence. Importado antes daqui, o documento voltaria a herdar
// o tema da tela, e o coordenador que trabalha à noite imprimiria um dossiê
// preto. Documento impresso não tem tema.
import '../styles/documento.css';

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
