import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './componentes/layout/AppShell';
import { Alunos } from './telas/Alunos/Alunos';
import { Ciclos } from './telas/Ciclos/Ciclos';
import { Simulados } from './telas/Simulados/Simulados';
import { SimuladoFicha } from './telas/SimuladoFicha/SimuladoFicha';
import { CicloFicha } from './telas/CicloFicha/CicloFicha';
import { AlunoFicha } from './telas/AlunoFicha/AlunoFicha';
import { ShellAluno } from './telas/Aluno/ShellAluno';
import { Painel } from './telas/Painel/Painel';
import { Importar } from './telas/Importar/Importar';
import { Auditoria } from './telas/Auditoria/Auditoria';
import { Administracao } from './telas/Administracao/Administracao';
import { Login } from './telas/Login/Login';
import { ChatLauncher } from './componentes/chat/ChatLauncher';
import { LimiteDeErro } from './componentes/LimiteDeErro';
import {
  CAPACIDADES_ALUNO, CAPACIDADES_COORDENADOR, SUGESTOES_ALUNO, SUGESTOES_COORDENADOR,
} from './dados/perfisSugestoes';
import * as sessao from './servicos/sessao';

// Telas ainda não migradas. Cada uma sai desta lista quando virar componente.

/**
 * Área do aluno: casco e rotas próprios, sem a topbar da coordenação.
 *
 * O aluno conversa com o "Mentor" (tools restritas aos próprios dados); a
 * coordenação, com o "Assistente" (tools staff). Quem escolhe o perfil é o
 * backend, pelo tipo do JWT — o que vai daqui é o rótulo e as sugestões de
 * abertura, que precisam bater com as tools que cada perfil realmente tem.
 */
function AppAluno() {
  return (
    <>
      <ShellAluno />
      <ChatComLimite
        rotuloFab="Mentor"
        tituloDrawer="Mentor de estudos"
        sugestoes={SUGESTOES_ALUNO}
        capacidades={CAPACIDADES_ALUNO}
      />
    </>
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
        <Route path="/simulados" element={<Simulados />} />
        <Route path="/simulados/:id" element={<SimuladoFicha />} />
        <Route path="/ciclos" element={<Ciclos />} />
        <Route path="/ciclos/:id" element={<CicloFicha />} />
        <Route path="/importar" element={<Importar />} />
        <Route path="/auditoria" element={<Auditoria />} />
        <Route path="/administracao" element={<Administracao />} />
        {/* Rota desconhecida cai no painel, como o roteador antigo fazia. */}
        <Route path="*" element={<Navigate to="/painel" replace />} />
      </Routes>

      <ChatComLimite sugestoes={SUGESTOES_COORDENADOR} capacidades={CAPACIDADES_COORDENADOR} />
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
      <Route path="*" element={<RotaProtegida />} />
    </Routes>
  );
}

/** Sem sessão, qualquer rota leva ao login. */
function RotaProtegida() {
  if (!sessao.autenticado()) return <Navigate to="/login" replace />;
  return sessao.tipo() === 'aluno' ? <AppAluno /> : <AppCoordenacao />;
}
