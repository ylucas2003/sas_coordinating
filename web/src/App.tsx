import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { enderecoDoLogin } from './dominio/voltaDoLogin';
import { Login } from './telas/Login/Login';
import { LoginCantina } from './telas/Login/LoginCantina';
import { CallbackCanvas } from './telas/Login/CallbackCanvas';
import { Esqueleto } from './componentes/ui/Esqueleto';
import * as sessao from './servicos/sessao';

// ⚠️ **Os três cascos entram por `lazy()`, e isso é desempenho, não estilo.**
//
// Até 09/09 este arquivo importava as 29 telas estaticamente, e o resultado
// medido era um bundle único de 1,0 MB (306 KB comprimido) que descia igual em
// toda rota: o tablet do balcão da cantina baixava o banco de questões, a
// Jornada do aluno e as 24 telas da coordenação para mostrar um formulário de
// login (docs/40 §12.1.4).
//
// Com a divisão, cada casco baixa o seu — e quem está no login não baixa
// nenhum.
//
// ⚠️ **Um `import` estático de qualquer um destes módulos, em qualquer lugar
// alcançável a partir daqui, desfaz a divisão em silêncio.** O bundler junta o
// pedaço de volta à entrada, o build não reclama, os testes passam, e só se
// descobre olhando `dist/assets` ou a aba de rede. É a razão de os cascos
// terem virado módulos próprios em `src/cascos/`.
//
// O LOGIN fica estático de propósito: é a primeira tela de todo mundo, e
// buscá-la num segundo passo trocaria o ganho por uma espera no pior momento.
const AppAluno = lazy(() => import('./cascos/AppAluno'));
const AppCoordenacao = lazy(() => import('./cascos/AppCoordenacao'));
const CascoCantina = lazy(() =>
  import('./telas/Cantina/CascoCantina').then((m) => ({ default: m.CascoCantina })));
// O consentimento do OAuth entra por `lazy()` pelo mesmo motivo dos cascos: ele
// lê `hooks/consultas` e `hooks/mutacoes`, que puxariam meia coordenação para o
// pedaço de ENTRADA — o que o celular do aluno e o tablet do balcão baixam.
const ConectarIa = lazy(() =>
  import('./telas/ConectarIa/ConectarIa').then((m) => ({ default: m.ConectarIa })));

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* URL própria, e não um terceiro modo de `/login`: quem trabalha na
          cantina recebe UM endereço e o salva (docs/38 §5). */}
      <Route path="/login-cantina" element={<LoginCantina />} />
      <Route path="/login/canvas" element={<CallbackCanvas />} />
      {/* O CONSENTIMENTO do OAuth (docs/43 §5.3) é PÚBLICO desde 26/10, e por
          isso mora aqui, fora da `RotaProtegida`. O authorization server da
          API manda o browser para `/conectar-ia?pedido=<id>` numa aba que o
          claude.ai ou o ChatGPT abriram — sem sessão do SAS, porque ela mora
          no `sessionStorage`, que é por aba. Quem aprova prova a posse do
          e-mail da IA com um código (decisão do dono de 26/10), e não um
          login. Com ou sem sessão na aba, é a mesma página: ela não lê nada
          da sessão e não chama nenhuma rota que exija uma. */}
      <Route
        path="/conectar-ia"
        element={(
          <Suspense fallback={<Esqueleto />}>
            <ConectarIa />
          </Suspense>
        )}
      />
      <Route path="*" element={<RotaProtegida />} />
    </Routes>
  );
}

/**
 * Sem sessão, qualquer rota leva ao login — e o login guarda o caminho de
 * volta (`?proximo=`).
 *
 * A volta existe porque a sessão mora no `sessionStorage`, que é por aba: todo
 * link aberto numa aba nova chega deslogado, e mandar a pessoa para `/` depois
 * de entrar perderia o link. Ela nasceu pelo consentimento do OAuth, que desde
 * 26/10 é rota pública (acima) e não passa mais por aqui. Quem valida o
 * caminho — só interno, nunca `//` nem URL absoluta — é
 * `dominio/voltaDoLogin.ts`, dos dois lados: aqui ao guardar, e no `Login` ao
 * ler.
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
 *
 * O `Suspense` é aqui e não dentro de cada casco porque é aqui que a troca
 * acontece — uma vez por sessão, logo depois do login. Os `Suspense` de dentro
 * (banco, chat, leitura de QR) são outros, e existem para a navegação do dia a
 * dia não piscar.
 */
function RotaProtegida() {
  if (!sessao.autenticado()) return <IrParaOLogin />;
  return (
    <Suspense fallback={<Esqueleto />}>
      <CascoDaSessao />
    </Suspense>
  );
}

/**
 * O login, levando junto o caminho de onde a pessoa veio.
 *
 * Componente próprio, e não `useLocation` dentro de `RotaProtegida`: quem lê a
 * localização renderiza de novo a CADA navegação, e lá em cima isso arrastaria
 * o casco inteiro — rail, topbar, chat — a cada troca de tela. Aqui ele só
 * existe no ramo sem sessão, que vive o tempo de um redirecionamento.
 */
function IrParaOLogin() {
  const { pathname, search, hash } = useLocation();
  return <Navigate to={enderecoDoLogin(`${pathname}${search}${hash}`)} replace />;
}

function CascoDaSessao() {
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
