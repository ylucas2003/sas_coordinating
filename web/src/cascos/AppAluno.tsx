// O casco do ALUNO, em módulo próprio para virar um PEDAÇO próprio do bundle.
//
// ⚠️ A extração não é organização: é o que permite o `lazy()` do `App.tsx`
// funcionar. Enquanto estas telas eram importadas de lá, o bundler as juntava
// ao arquivo de entrada — e o tablet do balcão da cantina baixava a Jornada, o
// Treino e o Tio Léo para mostrar uma tela de login (docs/40 §12.1.4).
//
// Por isso o import do casco tem de continuar sendo DINÂMICO. Um `import`
// estático de qualquer um destes módulos a partir do `App.tsx` desfaz a divisão
// em silêncio: o build não reclama, o pedaço volta para a entrada, e só se
// descobre medindo.

import { Route, Routes } from 'react-router-dom';

import { CascoAluno } from '../telas/Aluno/CascoAluno';
import { PortaoDoOnboarding } from '../telas/Aluno/Onboarding';
import { QuestaoTelaCheia } from '../telas/Aluno/QuestaoTelaCheia';
import { Treino } from '../telas/Aluno/Treino';
import { TreinoResumo } from '../telas/Aluno/TreinoResumo';

/**
 * Área do aluno: casco e rotas próprios, sem a topbar da coordenação.
 *
 * TRÊS rotas ficam FORA do casco, e a exclusão é de desenho, não de conveniência
 * (docs/28 §3 e o brief): treino, resumo do treino e a questão em tela cheia são
 * tela inteira, sem barra inferior e sem o botão do Tio Léo. Uma fila de
 * questões com navegação por baixo convida a sair no meio, que é o oposto do que
 * a sessão precisa.
 *
 * `origem` viaja na URL (`/treino/prioridade`, `/treino/lista/:id`) porque a
 * tela tem de saber dizer POR QUE são aquelas questões e não outras — "por que
 * estou vendo isto" é o que mata a confiança numa recomendação quando não tem
 * resposta.
 *
 * O chat do aluno NÃO é o `ChatLauncher`: é a folha do Tio Léo, montada dentro
 * do casco (docs/27 §8). O `ChatLauncher` segue intocado servindo a
 * coordenação, que precisa dele não-modal.
 */
export default function AppAluno() {
  return (
    // O portão envolve TUDO, inclusive treino e questão em tela cheia: elas
    // ficam fora do casco mas não fora do produto, e um link direto para
    // `/treino/prioridade` não pode ser a porta dos fundos de um onboarding
    // obrigatório (docs/36 §1.4).
    <PortaoDoOnboarding>
      <Routes>
        <Route path="/treino/:origem/resumo" element={<TreinoResumo />} />
        <Route path="/treino/:origem/*" element={<Treino />} />
        <Route path="/questao/:id" element={<QuestaoTelaCheia />} />
        <Route path="*" element={<CascoAluno />} />
      </Routes>
    </PortaoDoOnboarding>
  );
}
