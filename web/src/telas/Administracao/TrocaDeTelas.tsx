import { Navigate } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import * as sessao from '../../servicos/sessao';
import '../../../styles/troca-de-telas.css';

// TROCA DE TELAS AUTOMÁTICA — o download do AutoSwift OBS e o passo a passo
// para pôr o programa a trabalhar numa sala.
//
// O card do hub leva para CÁ, e não direto ao arquivo: quem baixa um programa
// de Windows sem instrução abre o .zip, roda o .exe de dentro dele e recebe
// "Failed to load Python DLL" — o erro mais comum do programa, e a primeira
// coisa que o tutorial previne. O texto abaixo vem do readme do repositório
// `obs` (seções "Uso passo a passo" e "Solução de problemas"); se o programa
// mudar, o readme de lá é a fonte e este arquivo é a cópia.
//
// ⚠️ O arquivo mora FORA da imagem, em `/opt/sas/dados/downloads/` no servidor
// (bind mount em `/srv/downloads`, servido pelo nginx em `/downloads/`). O
// nginx o serve por URL, SEM login: a guarda de administrador é desta tela e
// do card, não do arquivo. O zip não pode conter segredo.

const ARQUIVO = '/downloads/AutoSwift-OBS-Windows.zip';

interface Passo {
  titulo: string;
  corpo: string;
}

const ANTES: Passo[] = [
  {
    titulo: 'Computador com Windows e o OBS Studio instalado',
    corpo: 'O programa é só para Windows e conversa com o OBS do mesmo computador (ou da mesma rede).',
  },
  {
    titulo: 'WebSocket do OBS ligado',
    corpo:
      'No OBS: Ferramentas → Configurações do servidor WebSocket → marque "Ativar servidor WebSocket". Copie a porta (quase sempre 4455) e a senha — o programa vai pedir as duas.',
  },
];

const PASSOS: Passo[] = [
  {
    titulo: 'Baixe e extraia o zip inteiro',
    corpo:
      'Baixe o programa no fim desta página, clique com o botão direito no arquivo → "Extrair tudo" e abra a pasta criada. O "AutoSwift OBS.exe" e a pasta "_internal" precisam ficar juntos: não rode o programa de dentro do zip e não mova só o .exe.',
  },
  {
    titulo: 'Abra o programa',
    corpo:
      'Dê dois cliques em "AutoSwift OBS.exe". Se o Windows mostrar "O Windows protegeu o computador", clique em "Mais informações" → "Executar mesmo assim": o programa não é assinado, e o aviso é esperado.',
  },
  {
    titulo: 'Prepare as cenas no OBS',
    corpo:
      'Crie uma cena por câmera (por exemplo, cada metade da lousa) — não há limite de quantidade. Em cada cena, clique com o botão direito na fonte de câmera → Propriedades → e DESMARQUE "Desativar quando não estiver em exibição". Sem isso a detecção vê tela preta e o programa só enxerga um dos lados.',
  },
  {
    titulo: 'Conecte ao OBS',
    corpo:
      'Com o OBS já aberto, preencha o grupo "Conexão com o OBS": host localhost, porta 4455 e a senha do WebSocket. Clique em ▶ Iniciar: o selo passa de Parado para Conectando… e depois Rodando, e o programa importa as cenas do OBS sozinho. Não é preciso digitar nome de cena nem número de câmera.',
  },
  {
    titulo: 'Escolha as cenas do rodízio',
    corpo:
      'Na lista de cenas, ligue o interruptor "auto" das cenas que entram na troca automática (no mínimo duas) e deixe desligado nas de abertura, slide e "voltamos já". A setinha ▼ de cada cena mostra ao vivo o que está passando nela. Criou cena nova no OBS? Clique em "Atualizar do OBS".',
  },
  {
    titulo: 'Ajuste o que precisar (opcional)',
    corpo:
      'Cena de espera para quando ninguém for detectado, tipo e duração da transição, e presets por cenário (Salvar · Salvar como… · Excluir — por exemplo "Sala 204" e "Auditório"). Cada campo tem um "?" que explica em linguagem simples. A configuração é salva sozinha.',
  },
  {
    titulo: 'Escolha Automático ou Manual',
    corpo:
      'Automático: o programa coloca no ar a cena onde o professor está (Ctrl+M alterna entre os dois modos). Manual: ele não troca sozinho — clique numa cena, ou use Ctrl+1…9, para colocá-la no ar. Trocar pelo OBS também vale, e a cena no ar aparece em vermelho ("NO AR").',
  },
  {
    titulo: 'Deixe no piloto automático (opcional)',
    corpo:
      'No Avançado, ative "Reconexão automática" e "Iniciar ao abrir o app": se a conexão cair, o programa volta sozinho, e ele começa a trocar assim que abre.',
  },
];

const EXTRAS: Passo[] = [
  {
    titulo: 'Controle de 2 botões',
    corpo:
      'Um apresentador de slides Bluetooth/RF funciona como controle: o Botão 1 pula para uma cena especial (slide, documento) e volta ao automático; o Botão 2 conduz a aula — inicia a transmissão, entra no automático e encerra com contagem regressiva. Na aba "Controle" do programa você vincula cada botão físico.',
  },
  {
    titulo: 'Início automático por áudio',
    corpo:
      'A aula entra no automático sozinha quando o microfone capta som e o professor é detectado em uma das cenas. Exige as cenas de início e de fim do ciclo definidas.',
  },
  {
    titulo: 'Tratamento de áudio',
    corpo:
      'Aplica no microfone uma cadeia de filtros (supressão de ruído, compressor, limitador) por preset Leve, Médio ou Forte, sem ninguém precisar entender de dB.',
  },
];

const PROBLEMAS: { sintoma: string; solucao: string }[] = [
  {
    sintoma: '"Failed to load Python DLL python311.dll"',
    solucao: 'Você rodou de dentro do zip ou separou o .exe da pasta "_internal". Extraia o zip inteiro e rode de dentro da pasta.',
  },
  {
    sintoma: 'O programa abre e fecha sozinho',
    solucao: 'Abra %APPDATA%\\AutoSwiftOBS\\crash.log — o erro do início está lá.',
  },
  {
    sintoma: '"Senha ou porta incorretos" · não conecta',
    solucao: 'O WebSocket está desligado ou a senha está errada. Ative-o no OBS e confira porta e senha — e deixe o OBS aberto antes de clicar em ▶ Iniciar.',
  },
  {
    sintoma: 'A lista de cenas está vazia, ou cena nova não aparece',
    solucao: 'Clique em "Atualizar do OBS" para recarregar a lista.',
  },
  {
    sintoma: '"Nome de cena não confere"',
    solucao: 'O nome mudou no OBS. Use "Atualizar do OBS" para importar os nomes exatos.',
  },
  {
    sintoma: 'A cena fica preta · só troca para um lado',
    solucao: 'A câmera da cena escondida desliga. Na fonte de câmera: Propriedades → desmarque "Desativar quando não estiver em exibição".',
  },
  {
    sintoma: 'Fica piscando entre as cenas',
    solucao: 'Aumente "frames_confirmacao" e/ou "carencia_segundos", e afaste "confianca_entrar" de "confianca_permanecer".',
  },
  {
    sintoma: 'Não detecta bem o professor',
    solucao: 'A confiança está alta demais. Baixe "confianca_entrar" (por exemplo, 0,35).',
  },
];

function Lista({ itens, numerada = false }: { itens: Passo[]; numerada?: boolean }) {
  const Tag = numerada ? 'ol' : 'ul';
  return (
    <Tag className={`troca-lista${numerada ? ' troca-lista--numerada' : ''}`}>
      {itens.map((p) => (
        <li key={p.titulo} className="troca-lista__item">
          <strong className="troca-lista__titulo">{p.titulo}</strong>
          <span className="troca-lista__corpo">{p.corpo}</span>
        </li>
      ))}
    </Tag>
  );
}

export function TrocaDeTelas() {
  useTituloDaTela('Troca de Telas Automática');

  // Quem chega pela URL sem ser administrador volta ao hub, e não vê uma tela
  // que o card não ofereceu (mesma regra do `SoAdministrador` da cantina).
  if (!sessao.ehAdministrador()) return <Navigate to="/administracao" replace />;

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Troca de Telas Automática" para="/administracao" destino="Administração" />

      <p className="troca-intro">
        O AutoSwift OBS troca a cena do OBS sozinho: quando o professor se move, o programa coloca
        no ar a câmera onde ele está. Ele detecta a pessoa na imagem do próprio OBS — não abre as
        câmeras. Leia o passo a passo e, no fim da página, baixe o programa.
      </p>

      <section className="troca-secao">
        <h2 className="troca-secao__titulo">Antes de começar</h2>
        <Lista itens={ANTES} />
      </section>

      <section className="troca-secao">
        <h2 className="troca-secao__titulo">Passo a passo</h2>
        <Lista itens={PASSOS} numerada />
      </section>

      <section className="troca-secao">
        <h2 className="troca-secao__titulo">Recursos da aula</h2>
        <Lista itens={EXTRAS} />
      </section>

      <section className="troca-secao">
        <h2 className="troca-secao__titulo">Se algo der errado</h2>
        <div className="card troca-problemas">
          {PROBLEMAS.map((p) => (
            <div key={p.sintoma} className="troca-problema">
              <strong className="troca-problema__sintoma">{p.sintoma}</strong>
              <span className="troca-problema__solucao">{p.solucao}</span>
            </div>
          ))}
        </div>
        <p className="troca-rodape">
          A configuração e os registros ficam em %APPDATA%\AutoSwiftOBS\ (gui_config.json,
          autoswift.log). A caixa "Log" do programa mostra o mesmo em tempo real.
        </p>
      </section>

      <div className="card troca-baixar">
        <div className="troca-baixar__texto">
          <h2 className="troca-secao__titulo">Baixar o programa</h2>
          <p className="troca-baixar__nota">
            Windows · arquivo .zip · extraia a pasta inteira antes de abrir (passo 1)
          </p>
        </div>
        <a className="btn btn-primary troca-baixar__botao" href={ARQUIVO} download>
          Baixar para Windows
        </a>
      </div>
    </div>
  );
}
