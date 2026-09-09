// O casco da COORDENAÇÃO, em módulo próprio para virar um PEDAÇO próprio do
// bundle — a mesma razão de `AppAluno.tsx`, e aqui o peso é maior: são 24
// rotas, o chat e o banco de questões.
//
// ⚠️ O import a partir do `App.tsx` tem de continuar DINÂMICO. Um `import`
// estático desfaz a divisão sem erro nenhum (docs/40 §12.1.4).

import { lazy, Suspense, type ReactNode } from 'react';
import { Navigate, Route, Routes, useParams } from 'react-router-dom';

import { AppShell } from '../componentes/layout/AppShell';
import { Alunos } from '../telas/Alunos/Alunos';
import { Provas } from '../telas/Provas/Provas';
import { Ciclos } from '../telas/Ciclos/Ciclos';
import { Simulados } from '../telas/Simulados/Simulados';
import { SimuladoFicha } from '../telas/SimuladoFicha/SimuladoFicha';
import { CicloFicha } from '../telas/CicloFicha/CicloFicha';
import { CicloCalibracao } from '../telas/CicloFicha/CicloCalibracao';
import { CicloComparacao } from '../telas/CicloFicha/CicloComparacao';
import { AlunoFicha } from '../telas/AlunoFicha/AlunoFicha';
import { Painel } from '../telas/Painel/Painel';
import { Importar } from '../telas/Importar/Importar';
import { Auditoria } from '../telas/Auditoria/Auditoria';
import { Calibracao } from '../telas/Calibracao/Calibracao';
import { HubAdministracao } from '../telas/Administracao/HubAdministracao';
import { Contas } from '../telas/Administracao/Contas';
import { Integracoes } from '../telas/Integracoes/Integracoes';
import { SincronizacaoAulas } from '../telas/Integracoes/SincronizacaoAulas';
import {
  CalendarioNaCoordenacao, CardapioNaCoordenacao, DiaNaCoordenacao, HubDaCantina,
} from '../telas/Cantina/NaCoordenacao';
import { CustosDaCantina } from '../telas/Cantina/CustosDaCantina';
import { AcessoDaCantina, DireitosDaCantina } from '../telas/Administracao/Cantina';
import { LimiteDeErro } from '../componentes/LimiteDeErro';
import { LembreteFotoPerfil } from '../componentes/perfil/LembreteFotoPerfil';
import { Esqueleto } from '../componentes/ui/Esqueleto';
import {
  CAPACIDADES_COORDENADOR, SUGESTOES_COORDENADOR, sugestoesDoCoordenador,
} from '../dados/perfisSugestoes';
import * as sessao from '../servicos/sessao';

/**
 * As duas peças CARAS da coordenação, cada uma num pedaço próprio.
 *
 *   Banco  — arrasta o KaTeX junto (256 KB, 75 KB comprimido, mais 19 fontes),
 *            porque é ele que desenha fórmula. Antes disto o KaTeX vinha com
 *            `modulepreload` em TODA rota, inclusive no login da cantina.
 *   Chat   — o launcher fica montado no casco inteiro, mas ninguém o abre ao
 *            entrar. Carregar o reducer de streaming e o Markdown junto do
 *            Painel é pagar adiantado por algo que talvez não aconteça.
 */
const Banco = lazy(() =>
  import('../telas/Banco/Banco').then((m) => ({ default: m.Banco })));
const ChatLauncher = lazy(() =>
  import('../componentes/chat/ChatLauncher').then((m) => ({ default: m.ChatLauncher })));

export default function AppCoordenacao() {
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
        {/* `Suspense` local, e não no topo: quem já está na coordenação vê o
            casco inteiro de pé com só o miolo em esqueleto. Um fallback lá em
            cima piscaria a tela toda para trocar de aba. */}
        <Route
          path="/banco/*"
          element={
            <Suspense fallback={<Esqueleto />}>
              <Banco perfil="coordenacao" />
            </Suspense>
          }
        />
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
        {/* Custos é LEITURA de qualquer coordenador — sem `SoAdministrador`.
            Ver quanto custou não é o mesmo que decidir quanto custa, e
            cadastrar o valor continua em `/cantina/acesso` (docs/40 §12.11.4). */}
        <Route path="/cantina/custos" element={<CustosDaCantina />} />
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

      {/* Sem fallback visível: o chat é um botão flutuante, e um esqueleto de
          botão aparecendo sozinho na tela seria mais estranho que a ausência
          de meio segundo. */}
      <Suspense fallback={null}>
        <ChatComLimite
        sugestoes={SUGESTOES_COORDENADOR}
        capacidades={CAPACIDADES_COORDENADOR}
          derivarSugestoes={sugestoesDoCoordenador}
        />
      </Suspense>
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
