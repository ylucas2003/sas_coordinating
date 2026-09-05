import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useParams } from 'react-router-dom';

import { AppShell } from './componentes/layout/AppShell';
import { Alunos } from './telas/Alunos/Alunos';
import { Provas } from './telas/Provas/Provas';
import { Ciclos } from './telas/Ciclos/Ciclos';
import { Simulados } from './telas/Simulados/Simulados';
import { SimuladoFicha } from './telas/SimuladoFicha/SimuladoFicha';
import { CicloFicha } from './telas/CicloFicha/CicloFicha';
import { CicloCalibracao } from './telas/CicloFicha/CicloCalibracao';
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
import {
  CalendarioNaCoordenacao, CardapioNaCoordenacao, DiaNaCoordenacao, HubDaCantina,
} from './telas/Cantina/NaCoordenacao';
import { AcessoDaCantina, DireitosDaCantina } from './telas/Administracao/Cantina';
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
        {/* PROVAS — hub e as duas listas.

            As abas (`?aba=simulados`) viraram três endereços: cada lista é
            tela inteira com URL própria (C3, docs/39 fase 3). O hub em si
            traduz o `?aba=` antigo, porque o roteador não casa query string.

            Os caminhos antigos seguem valendo — estão em link salvo e em
            e-mail de lembrete, e removê-los é proibição registrada no
            `web/CLAUDE.md`. */}
        <Route path="/provas" element={<Provas />} />
        <Route path="/provas/ciclos" element={<Ciclos />} />
        <Route path="/provas/simulados" element={<Simulados />} />
        <Route path="/simulados" element={<Navigate to="/provas/simulados" replace />} />
        <Route path="/simulados/:id" element={<SimuladoFicha />} />
        <Route path="/ciclos" element={<Navigate to="/provas/ciclos" replace />} />
        {/* A ficha de ciclo virou entrada + campos (C3: cada destino é tela
            inteira, com URL própria). `/ciclos/:id` continua sendo a entrada,
            então nenhum link salvo quebra. */}
        <Route path="/ciclos/:id" element={<CicloFicha />} />
        <Route path="/ciclos/:id/calibracao" element={<CicloCalibracao />} />
        <Route path="/ciclos/:id/regua" element={<ReguaAbsorvidaPelaFicha />} />
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
        {/* CANTINA — o hub e as quatro portas (docs/39 fase 5).

            A coordenação LÊ o cardápio e ESCREVE só duas coisas: quem tem
            direito e quem lança. Publicar é da cantina, que tem casco próprio
            (docs/38 §6) — não há rota de edição de cardápio aqui, e é por isso
            que nenhuma destas telas oferece uma.

            ⚠️ `/cantina/cardapios`, `/cantina/direitos` e `/cantina/acesso`
            convivem com `/cantina/:data` sem ambiguidade porque o roteador
            ranqueia segmento ESTÁTICO acima de dinâmico, independentemente da
            ordem em que as rotas aparecem aqui. A ordem abaixo é para quem lê,
            não para o casamento — mas não invente um `:data` que colida com
            uma das três palavras, porque aí a palavra ganha em silêncio. */}
        <Route path="/cantina" element={<HubDaCantina />} />
        <Route path="/cantina/cardapios" element={<CalendarioNaCoordenacao />} />
        <Route path="/cantina/direitos" element={<DireitosDaCantina />} />
        <Route
          path="/cantina/acesso"
          element={<SoAdministrador><AcessoDaCantina /></SoAdministrador>}
        />
        {/* O dia inteiro, com as duas refeições — é o destino do card do
            Painel, que pula o hub para o caminho diário caber em um clique. */}
        <Route path="/cantina/:data" element={<DiaNaCoordenacao />} />
        <Route path="/cantina/:data/:refeicao" element={<CardapioNaCoordenacao />} />
        {/* A tela antiga se dividiu em duas. O link salvo cai no hub, que é o
            único destino válido para os DOIS papéis: quem não é administrador
            não tem `/cantina/acesso`, e mandá-lo para lá seria trocar um link
            velho por um beco. */}
        <Route path="/administracao/cantina" element={<Navigate to="/cantina" replace />} />
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
 * `/ciclos/:id/regua` SOME — a tabela dela foi absorvida pela ficha do ciclo
 * (docs/39 fase 3), com as colunas Situação e Distância junto, que são a única
 * explicação de corte do produto.
 *
 * Redireciona em vez de dar 404 porque quem tem o link salvo quer a resposta,
 * não a tela: ele cai onde a pergunta passou a ser respondida. `<Navigate>`
 * puro não serve — ele não interpola `:id`, e o parâmetro é justamente o que
 * não se pode perder no caminho.
 */
function ReguaAbsorvidaPelaFicha() {
  const { id } = useParams();
  return <Navigate to={`/ciclos/${id}`} replace />;
}

/**
 * `/cantina/acesso` é escrita exclusiva do administrador, e o portão é aqui.
 *
 * O hub já não desenha o card para quem não pode — o card SOME, não fica cinza.
 * Este é o outro lado da mesma decisão: quem chega pela URL (link colado,
 * histórico, um papel que mudou desde ontem) é levado ao hub, e não a uma tela
 * que monta para depois dar 403. Tela que monta para dar erro ensina a pessoa a
 * desconfiar do produto (docs/38 §1.1).
 */
function SoAdministrador({ children }: { children: ReactNode }) {
  if (!sessao.ehAdministrador()) return <Navigate to="/cantina" replace />;
  return <>{children}</>;
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
