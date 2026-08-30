import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './componentes/layout/AppShell';
import { Alunos } from './telas/Alunos/Alunos';
import { Provas } from './telas/Provas/Provas';
import { SimuladoFicha } from './telas/SimuladoFicha/SimuladoFicha';
import { CicloFicha } from './telas/CicloFicha/CicloFicha';
import { AlunoFicha } from './telas/AlunoFicha/AlunoFicha';
import { CascoAluno } from './telas/Aluno/CascoAluno';
import { QuestaoTelaCheia } from './telas/Aluno/QuestaoTelaCheia';
import { Treino } from './telas/Aluno/Treino';
import { TreinoResumo } from './telas/Aluno/TreinoResumo';
import { Painel } from './telas/Painel/Painel';
import { Importar } from './telas/Importar/Importar';
import { Auditoria } from './telas/Auditoria/Auditoria';
import { Banco } from './telas/Banco/Banco';
import { Administracao } from './telas/Administracao/Administracao';
import { Integracoes } from './telas/Integracoes/Integracoes';
import { SincronizacaoAulas } from './telas/Integracoes/SincronizacaoAulas';
import { Login } from './telas/Login/Login';
import { CallbackCanvas } from './telas/Login/CallbackCanvas';
import { ChatLauncher } from './componentes/chat/ChatLauncher';
import { LimiteDeErro } from './componentes/LimiteDeErro';
import { LembreteFotoPerfil } from './componentes/perfil/LembreteFotoPerfil';
// As do aluno (`SUGESTOES_ALUNO`, `CAPACIDADES_ALUNO`) saíram daqui: quem as
// consome agora é a folha do Tio Léo, dentro do casco do aluno.
import {
  CAPACIDADES_COORDENADOR, SUGESTOES_COORDENADOR, sugestoesDoCoordenador,
} from './dados/perfisSugestoes';
import * as sessao from './servicos/sessao';


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
function AppAluno() {
  return (
    <Routes>
      <Route path="/treino/:origem/resumo" element={<TreinoResumo />} />
      <Route path="/treino/:origem/*" element={<Treino />} />
      <Route path="/questao/:id" element={<QuestaoTelaCheia />} />
      <Route path="*" element={<CascoAluno />} />
    </Routes>
  );
}

function AppCoordenacao() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/painel" replace />} />
        <Route path="/painel" element={<Painel />} />
        <Route path="/alunos" element={<Alunos />} />
        <Route path="/alunos/:id" element={<AlunoFicha />} />
        <Route path="/provas" element={<Provas />} />
        {/* As listagens viraram abas de /provas. Os caminhos antigos seguem
            valendo porque estão em link salvo e em e-mail de lembrete. */}
        <Route path="/simulados" element={<Navigate to="/provas?aba=simulados" replace />} />
        <Route path="/simulados/:id" element={<SimuladoFicha />} />
        <Route path="/ciclos" element={<Navigate to="/provas" replace />} />
        <Route path="/ciclos/:id" element={<CicloFicha />} />
        <Route path="/importar" element={<Importar />} />
        <Route path="/banco/*" element={<Banco perfil="coordenacao" />} />
        <Route path="/auditoria" element={<Auditoria />} />
        <Route path="/administracao" element={<Administracao />} />
        <Route path="/integracoes" element={<Integracoes />} />
        <Route path="/integracoes/aulas" element={<SincronizacaoAulas />} />
        {/* Rota desconhecida cai no painel, como o roteador antigo fazia. */}
        <Route path="*" element={<Navigate to="/painel" replace />} />
      </Routes>

      <ChatComLimite
        sugestoes={SUGESTOES_COORDENADOR}
        capacidades={CAPACIDADES_COORDENADOR}
        derivarSugestoes={sugestoesDoCoordenador}
      />
      <LembreteFotoPerfil />
    </AppShell>
  );
}

/**
 * O chat isolado: se ele quebrar, quem some é o painel do chat, não a tela
 * que o usuário está usando.
 */
function ChatComLimite(props: React.ComponentProps<typeof ChatLauncher>) {
  return (
    <LimiteDeErro
      fallback={(mensagem) => (
        <div className="chat-fab" title={mensagem}>
          <span className="chat-fab__icone">⚠️</span>
          <span className="chat-fab__label">Chat indisponível</span>
        </div>
      )}
    >
      <ChatLauncher {...props} />
    </LimiteDeErro>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/login/canvas" element={<CallbackCanvas />} />
      <Route path="*" element={<RotaProtegida />} />
    </Routes>
  );
}

/** Sem sessão, qualquer rota leva ao login. */
function RotaProtegida() {
  if (!sessao.autenticado()) return <Navigate to="/login" replace />;
  return sessao.tipo() === 'aluno' ? <AppAluno /> : <AppCoordenacao />;
}
