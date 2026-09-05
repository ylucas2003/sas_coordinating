import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './componentes/layout/AppShell';
import { Alunos } from './telas/Alunos/Alunos';
import { Provas } from './telas/Provas/Provas';
import { SimuladoFicha } from './telas/SimuladoFicha/SimuladoFicha';
import { CicloFicha } from './telas/CicloFicha/CicloFicha';
import { CicloCalibracao } from './telas/CicloFicha/CicloCalibracao';
import { CicloRegua } from './telas/CicloFicha/CicloRegua';
import { CicloComparacao } from './telas/CicloFicha/CicloComparacao';
import { AlunoFicha } from './telas/AlunoFicha/AlunoFicha';
import { CascoAluno } from './telas/Aluno/CascoAluno';
import { PortaoDoOnboarding } from './telas/Aluno/Onboarding';
import { QuestaoTelaCheia } from './telas/Aluno/QuestaoTelaCheia';
import { Treino } from './telas/Aluno/Treino';
import { TreinoResumo } from './telas/Aluno/TreinoResumo';
import { Painel } from './telas/Painel/Painel';
import { Importar } from './telas/Importar/Importar';
import { Auditoria } from './telas/Auditoria/Auditoria';
import { Calibracao } from './telas/Calibracao/Calibracao';
import { Banco } from './telas/Banco/Banco';
import { HubAdministracao } from './telas/Administracao/HubAdministracao';
import { Contas } from './telas/Administracao/Contas';
import { Integracoes } from './telas/Integracoes/Integracoes';
import { SincronizacaoAulas } from './telas/Integracoes/SincronizacaoAulas';
import { Login } from './telas/Login/Login';
import { LoginCantina } from './telas/Login/LoginCantina';
import { CallbackCanvas } from './telas/Login/CallbackCanvas';
import { CascoCantina } from './telas/Cantina/CascoCantina';
import { CantinaCoordenacao, CardapioNaCoordenacao } from './telas/Cantina/NaCoordenacao';
import { AdministracaoCantina } from './telas/Administracao/Cantina';
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
        {/* A ficha de ciclo virou entrada + três campos (C3: cada destino é
            tela inteira, com URL própria). `/ciclos/:id` continua sendo a
            entrada, então nenhum link salvo quebra. */}
        <Route path="/ciclos/:id" element={<CicloFicha />} />
        <Route path="/ciclos/:id/calibracao" element={<CicloCalibracao />} />
        <Route path="/ciclos/:id/regua" element={<CicloRegua />} />
        <Route path="/ciclos/:id/comparacao" element={<CicloComparacao />} />
        <Route path="/importar" element={<Importar />} />
        <Route path="/banco/*" element={<Banco perfil="coordenacao" />} />
        <Route path="/auditoria" element={<Auditoria />} />
        <Route path="/calibracao" element={<Calibracao />} />
        {/* `/administracao` era a tela de Contas e passa a ser o HUB de quatro
            campos; Contas ganhou rota própria. Quem tiver o link antigo salvo
            cai no hub, a um clique de distância, e não num 404. */}
        <Route path="/administracao" element={<HubAdministracao />} />
        <Route path="/administracao/contas" element={<Contas />} />
        <Route path="/integracoes" element={<Integracoes />} />
        <Route path="/integracoes/aulas" element={<SincronizacaoAulas />} />
        {/* A cantina em modo LEITURA. A coordenação vê o cardápio e os
            pedidos; publicar é da cantina, que tem casco próprio (docs/38 §6). */}
        <Route path="/cantina" element={<CantinaCoordenacao />} />
        <Route path="/cantina/:data/:refeicao" element={<CardapioNaCoordenacao />} />
        <Route path="/administracao/cantina" element={<AdministracaoCantina />} />
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
      {/* URL própria, e não um terceiro modo de `/login`: quem trabalha na
          cantina recebe UM endereço e o salva (docs/38 §5). */}
      <Route path="/login-cantina" element={<LoginCantina />} />
      <Route path="/login/canvas" element={<CallbackCanvas />} />
      <Route path="*" element={<RotaProtegida />} />
    </Routes>
  );
}

/**
 * Sem sessão, qualquer rota leva ao login.
 *
 * ⚠️ **Três cascos, e o desconhecido volta para o login — não para a
 * coordenação.** Até 05/09 isto era `tipo === 'aluno' ? aluno : coordenação`,
 * e o `else` era seguro só porque existiam exatamente dois tipos. Com a
 * cantina, aquele `else` montaria o casco da COORDENAÇÃO para ela: as rotas
 * dariam 403 e a tela apareceria mesmo assim — e tela que monta para dar erro
 * ensina a pessoa a desconfiar do produto (docs/38 §1.1).
 *
 * O default do `switch` é fail-closed pela mesma razão: um `sas_tipo` que esta
 * versão não conhece (token velho, storage adulterado) não pode cair no casco
 * mais poderoso.
 */
function RotaProtegida() {
  if (!sessao.autenticado()) return <Navigate to="/login" replace />;
  switch (sessao.tipo()) {
    case 'aluno':
      return <AppAluno />;
    case 'coordenador':
    case 'administrador':
      return <AppCoordenacao />;
    case 'cantina':
      return <CascoCantina />;
    default:
      return <Navigate to="/login" replace />;
  }
}
