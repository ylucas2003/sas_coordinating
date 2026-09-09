import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { App } from './App';
// ⚠️ **Import por EFEITO, e ele é obrigatório aqui.** `servicos/tema.ts` estampa
// `data-tema` no `<html>` no escopo do módulo, antes do primeiro render — é o
// que evita o piscão de tema.
//
// Ele não era importado daqui porque a topbar da coordenação o puxava, e a
// topbar vinha no bundle de entrada. **A divisão do bundle (docs/40 §12.1.4)
// quebrou isso em silêncio:** com os cascos em `lazy()`, ninguém carrega o
// módulo na tela de login, `data-tema` fica ausente, e o CSS cai no
// `@media (prefers-color-scheme: dark)` — a porta voltava a nascer escura num
// aparelho escuro, exatamente o que a §12.10 tinha acabado de corrigir.
//
// Achado no browser, não no build: nenhum portão pega isto. Se algum dia o
// tema parecer "ignorar a escolha" numa tela nova, esta linha é o primeiro
// lugar a olhar.
import './servicos/tema';

// CSS global, na mesma ordem em que o `index.html` os carregava. Os arquivos
// por tela vão virando CSS Modules conforme cada tela migra; o que fica aqui
// para sempre são tokens, base e fontes.
import '../styles/fontes.css';
// A pilha de cor, e a ordem dela é obrigatória: os hexadecimais crus
// (`paleta.css`), depois os seis papéis com os três blocos de tema
// (`papeis.css`), e só então o alias que sobrou — `aluno-tokens.css`, lá
// embaixo. Alias antes de papel resolveria para vazio. Ver o cabeçalho de cada
// um. O alias da coordenação (`tokens.css`) morreu na fase 0 do docs/39: a
// coordenação lê o papel direto.
//
// `forma.css` é o que restou de `tokens.css` e não era cor — raio, casco e
// família tipográfica. Fora da pilha porque não responde a tema.
import '../styles/paleta.css';
import '../styles/papeis.css';
import '../styles/forma.css';
import '../styles/base.css';
// ⚠️ `katex.min.css` e `markdown.css` SAÍRAM daqui, e foram JUNTOS para
// `componentes/ui/Markdown.tsx` — na mesma ordem, que é obrigatória (o nosso
// ajusta corpo e margem do que o KaTeX desenha).
//
// O motivo é a divisão do bundle (docs/40 §12.1.4): enquanto o CSS do KaTeX era
// importado daqui, o Vite o tratava como dependência da ENTRADA e punha um
// `modulepreload` do KaTeX no `index.html` — 75 KB comprimidos baixados em toda
// rota, inclusive no login da cantina, que nunca desenha uma fórmula.
//
// Foram os dois porque separá-los quebraria a ordem: o nosso ficaria aqui, o
// deles chegaria depois no pedaço, e o ajuste de margem perderia para o
// original sem erro nenhum. As classes `.md*` só existem em `Markdown.tsx`,
// então a folha inteira pertence a ele.
import '../styles/casco.css';
import '../styles/layout.css';
import '../styles/simulados.css';
import '../styles/auditoria.css';
import '../styles/painel.css';
// A varredura de um ciclo. Saiu de `painel.css` junto com o componente
// (docs/39 §PRECEDÊNCIA): a tabela sempre foi de um ciclo só, e o Painel
// gastava uma faixa de filtros para pedir o contexto que a URL já dá.
import '../styles/ciclo.css';
import '../styles/aluno-ficha.css';
import '../styles/filtros.css';
import '../styles/campo.css';
// A tarja de procedência, que substitui os quatro dialetos de "de onde veio
// este número?" (docs/39, fase 1). Global como `campo.css`: ela é peça de
// vocabulário e aparece em tela de qualquer casco.
import '../styles/procedencia.css';
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
import '../styles/aluno-cantina.css';
// A PORTA — o login das duas entradas. O `.lp` institucional foi apagado em
// 05/09: eram dois desenhos de login, e clicar em "Sou da coordenação" trocava
// a página inteira em vez de revelar o formulário.
import '../styles/porta.css';
import '../styles/banco.css';
import '../styles/foto-perfil.css';
import '../styles/integracoes.css';
// A cantina tem casco próprio (o terceiro do produto) e usa os tokens da
// coordenação — a folha do lado do ALUNO é `aluno-cantina.css`, lá em cima.
import '../styles/cantina.css';
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
