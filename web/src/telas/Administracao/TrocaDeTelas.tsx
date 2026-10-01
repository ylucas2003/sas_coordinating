import { Navigate } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import * as sessao from '../../servicos/sessao';
import '../../../styles/troca-de-telas.css';

import imgMenuDoObs from '../../../assets/troca-de-telas/obs-menu.webp';
import imgWebsocket from '../../../assets/troca-de-telas/obs-websocket.webp';
import imgConexao from '../../../assets/troca-de-telas/s3-conn.webp';
import imgConectado from '../../../assets/troca-de-telas/s3-bar.webp';
import imgIniciar from '../../../assets/troca-de-telas/s3-btns.webp';
import imgCenas from '../../../assets/troca-de-telas/s4-scenes.webp';
import imgSeletor from '../../../assets/troca-de-telas/s5-selector.webp';
import imgPresets from '../../../assets/troca-de-telas/s5-preset.webp';

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
// A forma segue o guia rápido em slides (quatro passos, cada um com o recorte
// fiel da tela do programa ao lado do texto): quem nunca abriu o OBS acha o
// lugar pela imagem, não pela descrição. As imagens são recortes do próprio
// guia, em `assets/troca-de-telas/`.
//
// ⚠️ `obs-websocket.webp` NÃO é o print original. O original mostra a senha
// real do WebSocket, o IP da máquina e um QR code que codifica os dois — e o
// asset vai no bundle, que o nginx serve SEM login. A cópia foi cortada antes
// do QR code e teve a senha e o IP cobertos. Ao trocar essa imagem, refaça o
// mesmo: nada de credencial num arquivo público.
//
// ⚠️ O arquivo mora FORA da imagem, em `/opt/sas/dados/downloads/` no servidor
// (bind mount em `/srv/downloads`, servido pelo nginx em `/downloads/`). O
// nginx o serve por URL, SEM login: a guarda de administrador é desta tela e
// do card, não do arquivo. O zip não pode conter segredo. Trocar o arquivo
// não passa pelo deploy nem pelo git: o procedimento está no volume
// `/srv/downloads` de `infra/vps/docker-compose.yml`.

const ARQUIVO = '/downloads/AutoSwift-OBS-Windows.zip';

const FASES = ['Preparar o OBS', 'Instalar e conectar', 'Configurar a troca', 'Operar'];

interface PropsFigura {
  letra: string;
  legenda: string;
  src: string;
  alt: string;
}

/** O recorte da tela, com a letra que o texto usa para apontá-lo. */
function Figura({ letra, legenda, src, alt }: PropsFigura) {
  return (
    <figure className="troca-figura">
      <figcaption className="troca-figura__legenda">
        <span className="troca-figura__letra">{letra}</span>
        {legenda}
      </figcaption>
      {/* Os recortes têm fundo escuro próprio: o quadro fixa o contraste nos dois temas. */}
      <div className="troca-figura__quadro">
        <img className="troca-figura__img" src={src} alt={alt} loading="lazy" decoding="async" />
      </div>
    </figure>
  );
}

function Fase({
  numero,
  titulo,
  olho,
  children,
}: {
  numero: number | string;
  titulo: string;
  olho?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="troca-fase">
      <header className="troca-fase__topo">
        <span className="troca-fase__numero">{numero}</span>
        <div>
          <span className="troca-fase__olho">
            {olho ?? (typeof numero === 'number' ? `Passo ${numero}` : 'Ajuda')}
          </span>
          <h2 className="troca-fase__titulo">{titulo}</h2>
        </div>
      </header>
      <div className="troca-fase__corpo">{children}</div>
    </section>
  );
}

/** Um item do passo: a marca (letra ou número), o título e, se houver, o texto. */
function Item({ marca, titulo, children }: { marca: string; titulo?: string; children: React.ReactNode }) {
  return (
    <li className="troca-item">
      <span className="troca-item__marca">{marca}</span>
      <div className="troca-item__texto">
        {titulo && <strong className="troca-item__titulo">{titulo}</strong>}
        <span className="troca-item__corpo">{children}</span>
      </div>
    </li>
  );
}

/** O aviso em caixa: `alerta` é o que quebra se ignorado; `dica` é o que ajuda. */
function Destaque({ tom, children }: { tom: 'alerta' | 'dica'; children: React.ReactNode }) {
  return (
    <p className={`troca-destaque troca-destaque--${tom}`}>
      <svg
        className="troca-destaque__icone"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {tom === 'alerta' ? (
          <>
            <path d="M12 4 3 20h18z" />
            <path d="M12 10v5M12 17.6v.4" />
          </>
        ) : (
          <>
            <path d="M9 18h6M10 21h4" />
            <path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z" />
          </>
        )}
      </svg>
      <span>{children}</span>
    </p>
  );
}

const EXTRAS: { titulo: string; corpo: string }[] = [
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
    sintoma: '"Senha ou porta incorretos"',
    solucao: 'Confira o WebSocket e a senha do Passo 1, e deixe o OBS aberto antes de clicar em ▶ Iniciar.',
  },
  {
    sintoma: '"A cena fica preta / só detecta uma"',
    solucao:
      'Desmarque "Desativar quando não estiver em exibição" nas Propriedades da fonte de câmera.',
  },
  {
    sintoma: '"Criei cenas novas e não aparecem"',
    solucao: 'Clique em "Atualizar do OBS" para recarregar a lista.',
  },
  {
    sintoma: '"Failed to load Python DLL python311.dll"',
    solucao:
      'Você rodou de dentro do zip ou separou o .exe da pasta "_internal". Extraia o zip inteiro e rode de dentro da pasta.',
  },
  {
    sintoma: 'O programa abre e fecha sozinho',
    solucao: 'Abra %APPDATA%\\AutoSwiftOBS\\crash.log — o erro do início está lá.',
  },
  {
    sintoma: 'Fica piscando entre as cenas',
    solucao:
      'Aumente "frames_confirmacao" e/ou "carencia_segundos", e afaste "confianca_entrar" de "confianca_permanecer".',
  },
  {
    sintoma: 'Não detecta bem o professor',
    solucao: 'A confiança está alta demais. Baixe "confianca_entrar" (por exemplo, 0,35).',
  },
];

export function TrocaDeTelas() {
  useTituloDaTela('Troca de Telas Automática');

  // Quem chega pela URL sem ser administrador volta ao hub, e não vê uma tela
  // que o card não ofereceu (mesma regra do `SoAdministrador` da cantina).
  if (!sessao.ehAdministrador()) return <Navigate to="/administracao" replace />;

  return (
    <div className="tela troca">
      <CabecaDeCampo titulo="Troca de Telas Automática" para="/administracao" destino="Administração" />

      <div className="troca-capa">
        <span className="troca-capa__olho">Guia rápido</span>
        <h2 className="troca-capa__titulo">AutoSwift OBS</h2>
        <p className="troca-capa__texto">
          Detecta a pessoa nas câmeras e troca a cena do OBS sozinho — com quantas câmeras você
          quiser, modo manual quando precisar e presets por cenário. Ele lê a imagem do próprio OBS:
          não abre as câmeras.
        </p>
        <ol className="troca-capa__indice">
          {FASES.map((f, i) => (
            <li key={f} className="troca-capa__fase">
              <span className="troca-capa__n">{i + 1}</span>
              {f}
            </li>
          ))}
        </ol>
        <p className="troca-capa__nota">Leia os quatro passos e, no fim da página, baixe o programa.</p>
      </div>

      <Fase numero={1} titulo="Preparar o OBS">
        <ul className="troca-itens">
          <Item marca="a" titulo="Crie uma cena por câmera">
            Quantas você precisar — não há limite de quantidade. Pode ser cada metade da lousa, por
            exemplo.
          </Item>
          <Item marca="b" titulo="Mantenha a câmera ativa">
            Nas <strong>Propriedades</strong> da fonte de câmera, desmarque{' '}
            <strong>"Desativar quando não estiver em exibição"</strong>. Senão a detecção vê tela preta.
          </Item>
          <Item marca="c" titulo="Ative o WebSocket">
            <strong>Ferramentas → Configurações do servidor WebSocket → Ativar.</strong> Copie a{' '}
            <strong>Porta</strong> (quase sempre 4455) e a <strong>Senha</strong>.
          </Item>
        </ul>
        <div className="troca-figuras">
          <Figura
            letra="A"
            legenda="Onde clicar no OBS"
            src={imgMenuDoObs}
            alt='Menu Ferramentas do OBS aberto, com "Configurações do servidor WebSocket" destacado'
          />
          <Figura
            letra="B"
            legenda="Porta e Senha"
            src={imgWebsocket}
            alt="Janela de configurações do servidor WebSocket, com o servidor ativado e os campos de porta e senha"
          />
        </div>
      </Fase>

      <Fase numero={2} titulo="Instalar e conectar">
        <ul className="troca-itens">
          <Item marca="1">
            Descompacte o <strong>.zip inteiro</strong> e abra o <strong>AutoSwift OBS.exe</strong> de
            dentro da pasta extraída — não rode de dentro do zip. O programa está no fim desta página.
          </Item>
          <Item marca="2">
            Preencha só o grupo <strong>Conexão com o OBS</strong>: Host <code>localhost</code>, Porta{' '}
            <code>4455</code> e a <strong>Senha</strong>.
          </Item>
          <Item marca="3">
            Clique <strong>▶ Iniciar</strong>. O selo passa de <strong>Conectando…</strong> para{' '}
            <strong>Rodando</strong> e o app importa as cenas do OBS sozinho.
          </Item>
          <Destaque tom="dica">Não precisa digitar nomes de cena nem índices de câmera.</Destaque>
          <Destaque tom="alerta">
            Na primeira vez o Windows pode mostrar "O Windows protegeu o computador". Clique em{' '}
            <strong>Mais informações → Executar mesmo assim</strong>: o programa não é assinado, e o
            aviso é esperado.
          </Destaque>
        </ul>
        <div className="troca-figuras">
          <Figura
            letra="A"
            legenda="Preencha a conexão"
            src={imgConexao}
            alt="Grupo Conexão com o OBS, com os campos Host (localhost), Porta (4455) e Senha"
          />
          <ol className="troca-selos" aria-label="O selo do programa: Parado, Conectando, Rodando">
            <li className="troca-selo">Parado</li>
            <li className="troca-selos__seta" aria-hidden="true">→</li>
            <li className="troca-selo troca-selo--meio">Conectando…</li>
            <li className="troca-selos__seta" aria-hidden="true">→</li>
            <li className="troca-selo troca-selo--fim">Rodando</li>
          </ol>
          <Figura
            letra="B"
            legenda="Conectado!"
            src={imgConectado}
            alt="Faixa 'Conectado ao OBS', com localhost:4455 e o botão editar"
          />
          <Figura
            letra="C"
            legenda="Iniciar"
            src={imgIniciar}
            alt="Botões Parar e Iniciar do programa"
          />
        </div>
      </Fase>

      <Fase numero={3} titulo="Configurar a troca">
        <ul className="troca-itens">
          <Item marca="1">
            A lista mostra <strong>todas as cenas do OBS</strong>. Ligue o <strong>auto</strong> nas
            cenas que devem entrar na troca automática (no mínimo duas).
          </Item>
          <Item marca="2">
            Deixe o <strong>auto desligado</strong> nas cenas de slide ou abertura — elas ficam de fora
            do rodízio.
          </Item>
          <Item marca="3">
            Clique na setinha <strong>▼</strong> de uma cena para ver <strong>ao vivo</strong> o que
            está passando nela.
          </Item>
          <Item marca="4">
            <strong>Opcional:</strong> defina uma <strong>cena de fallback</strong> (entra quando
            ninguém aparece) e a <strong>transição</strong> (tipo + duração).
          </Item>
          <Destaque tom="dica">
            Criou cena nova no OBS? Clique em <strong>Atualizar do OBS</strong> para recarregar a lista.
          </Destaque>
        </ul>
        <div className="troca-figuras">
          <Figura
            letra="A"
            legenda='Interruptor "auto" por cena · cena no ar em vermelho'
            src={imgCenas}
            alt='Lista de cenas com o interruptor "auto" ligado; a cena no ar aparece em vermelho com o selo NO AR'
          />
        </div>
      </Fase>

      <Fase numero={4} titulo="Operar no dia a dia">
        <ul className="troca-itens">
          <Item marca="1">
            Em <strong>Automático</strong>, o app troca a cena sozinho pela detecção.
          </Item>
          <Item marca="2">
            Em <strong>Manual</strong>, você comanda: clique numa cena (ou <code>Ctrl+1…9</code>) para
            colocá-la no ar — útil para forçar uma cena e depois voltar ao automático.{' '}
            <code>Ctrl+M</code> alterna entre os dois modos.
          </Item>
          <Item marca="3">
            Salve <strong>presets</strong> por cenário (Salvar · Salvar como… · Excluir), como "Sala
            204" e "Auditório", e acompanhe a <strong>cena no ar</strong> pela setinha ▼.
          </Item>
          <Destaque tom="dica">
            No <strong>Avançado</strong>, ative <strong>Reconexão automática</strong> e{' '}
            <strong>Iniciar ao abrir</strong>: se a conexão cair o programa volta sozinho, e ele começa a
            trocar assim que abre.
          </Destaque>
        </ul>
        <div className="troca-figuras">
          <Figura
            letra="A"
            legenda="Seletor Automático ⇄ Manual"
            src={imgSeletor}
            alt="Seletor com as opções Automático e Manual, e a explicação do modo Manual"
          />
          <Figura
            letra="B"
            legenda="Presets por cenário"
            src={imgPresets}
            alt="Campo de preset com os botões Salvar, Salvar como e Excluir"
          />
        </div>
      </Fase>

      <section className="troca-extras">
        <h2 className="troca-extras__titulo">Recursos da aula</h2>
        <div className="troca-extras__grade">
          {EXTRAS.map((e) => (
            <div key={e.titulo} className="troca-extra">
              <strong className="troca-extra__titulo">{e.titulo}</strong>
              <span className="troca-extra__corpo">{e.corpo}</span>
            </div>
          ))}
        </div>
      </section>

      {/* EQ dinâmico por plugin VST no OBS. O programa não instala nem cria este
          filtro: é feito à mão, uma vez por máquina. Só cortes, porque a cada
          reaplicação o programa põe os filtros "AutoSwift · " no topo da lista e
          o VST acaba no fim, depois do limitador — ali um reforço estouraria. */}
      <Fase numero="+" olho="Opcional" titulo="Equalizador dinâmico no microfone">
        <ul className="troca-itens">
          <Destaque tom="dica">
            O tratamento de áudio do programa usa equalização fixa. Para cortar o grave embolado e o
            chiado do "s" só quando eles acontecem, instale no OBS o <strong>TDR Nova</strong>, um
            plugin gratuito. É feito uma vez por máquina.
          </Destaque>
          <Item marca="1">
            Baixe o TDR Nova em{' '}
            <a href="https://www.tokyodawn.net/tdr-nova/" target="_blank" rel="noreferrer">
              tokyodawn.net/tdr-nova
            </a>{' '}
            e rode o instalador marcando a versão <strong>VST2 de 64 bits</strong>. Se ele perguntar a
            pasta do VST2, use <code>{'C:\\Program Files\\VSTPlugins'}</code>.
          </Item>
          <Item marca="2">
            Confira se o arquivo do TDR Nova (<code>.dll</code>) ficou nessa pasta e{' '}
            <strong>reinicie o OBS</strong>.
          </Item>
          <Item marca="3">
            No <strong>Mixer de áudio</strong>, clique na engrenagem do microfone →{' '}
            <strong>Filtros</strong> → <strong>+</strong> → <strong>VST 2.x</strong>. Dê o nome{' '}
            <strong>EQ dinâmico</strong>.
          </Item>
          <Item marca="4">
            Escolha <strong>TDR Nova</strong> na lista, abra a interface do plug-in, configure com o
            ponto de partida desta seção e feche a janela. O OBS guarda a configuração.
          </Item>
          <Destaque tom="alerta">
            Não comece o nome do filtro com <strong>"AutoSwift · "</strong>: o programa apaga os filtros
            com esse prefixo que não fazem parte do preset.
          </Destaque>
        </ul>
        <ul className="troca-itens">
          <Destaque tom="dica">
            Ponto de partida para a voz do professor. Ajuste o limiar de cada banda ouvindo a fala: o
            corte deve acontecer só nos picos, não o tempo todo.
          </Destaque>
          <Item marca="a" titulo="Passa-alta em ~80 Hz">
            Tira ronco, batida na mesa e barulho de ar-condicionado.
          </Item>
          <Item marca="b" titulo="Banda em ~250 Hz, dinâmica">
            Corta de 2 a 4 dB só quando o grave embola, por exemplo quando o professor chega perto do
            microfone.
          </Item>
          <Item marca="c" titulo="Banda em ~6–7 kHz, estreita, dinâmica">
            Corta de 3 a 6 dB só nos "s" e "ch".
          </Item>
          <Destaque tom="alerta">
            Use <strong>só cortes</strong>, nunca reforços. O programa reorganiza os filtros dele no topo
            da lista, então o EQ dinâmico sempre fica no fim, depois do limitador — ali um reforço pode
            estourar o áudio.
          </Destaque>
        </ul>
      </Fase>

      <Fase numero="?" titulo="Ajuda & Dicas">
        <div className="troca-problemas">
          {PROBLEMAS.map((p) => (
            <div key={p.sintoma} className="troca-problema">
              <strong className="troca-problema__sintoma">{p.sintoma}</strong>
              <span className="troca-problema__seta" aria-hidden="true">→</span>
              <span className="troca-problema__solucao">{p.solucao}</span>
            </div>
          ))}
          <Destaque tom="alerta">
            O OBS precisa estar <strong>aberto</strong> antes de clicar em Iniciar.
          </Destaque>
          <p className="troca-rodape">
            A configuração e os registros ficam em {'%APPDATA%\\AutoSwiftOBS\\'} (gui_config.json,
            autoswift.log). A caixa "Log" do programa mostra o mesmo em tempo real.
          </p>
        </div>
      </Fase>

      <div className="card troca-baixar">
        <div className="troca-baixar__texto">
          <h2 className="troca-baixar__titulo">Baixar o programa</h2>
          <p className="troca-baixar__nota">
            Windows · arquivo .zip · extraia a pasta inteira antes de abrir (Passo 2)
          </p>
        </div>
        <a className="btn btn-primary troca-baixar__botao" href={ARQUIVO} download>
          Baixar para Windows
        </a>
      </div>
    </div>
  );
}
