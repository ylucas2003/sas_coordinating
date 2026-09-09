import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import jsQR from 'jsqr';

import {
  horaLegivel, lerRespostaDoQr, refeicaoPorHorario, ROTULO_DA_REFEICAO, rotuloDoDia,
} from '../../dominio/cantina';
import type { LeituraDoQr } from '../../dominio/cantina';
import { recorteDaMira } from '../../dominio/mira';
import type { Recorte } from '../../dominio/mira';
import { useConfirmarRetirada } from '../../hooks/cantina';
import { ErroApi } from '../../servicos/http';
import type { Refeicao } from '../../tipos/cantina';

// PEDIDOS AO VIVO — a câmera ligada o serviço inteiro (docs/40 §7).
//
// Está no nav do casco, e não dentro do fluxo por dia, porque é tela que fica
// ABERTA: a cantina entra aqui às 11h30 e sai às 13h. Um destino escondido
// dentro de `/cardapios/:data/:refeicao` obrigaria a reencontrá-la a cada
// recarregamento de página, com a fila esperando.
//
// ⚠️ **A câmera exige contexto seguro.** HTTPS ou `localhost`; um IP na rede
// local (`http://192.168.0.10:8080`) NÃO serve, e o navegador nem pergunta —
// `navigator.mediaDevices` simplesmente não existe. Por isso a falha vira
// texto na tela com o endereço em que se está, e não um `console.error` que
// ninguém no balcão vai abrir.
//
// ⚠️ A decodificação roda no cliente e o token vai inteiro para o servidor, que
// é quem verifica assinatura, validade e cantina (docs/40 §4). A tela não
// interpreta o conteúdo do QR — se interpretasse, um QR forjado passaria a
// depender da nossa leitura em vez da assinatura.

/** Quanto tempo a ficha fica na tela antes de voltar a escanear sozinha. */
const FICHA_NA_TELA_MS = 5_000;
/**
 * Não relê o MESMO código enquanto ele estiver na frente da câmera.
 *
 * Maior que o tempo da ficha na tela de propósito: sem essa distância, o
 * celular ainda parado no balcão seria lido de novo assim que a ficha saísse, e
 * o aluno veria "já retirado" sobre a retirada que acabou de dar certo. Uma
 * segunda passagem DE VERDADE acontece minutos depois — e aí o token já é
 * outro, porque a tela do aluno o renova a cada dois minutos.
 */
const MESMO_CODIGO_MS = 45_000;
/** Um quadro a cada ~130 ms: acima disso a CPU de um tablet de balcão sofre e
    a leitura não fica mais rápida — o gargalo é a mão que aproxima o celular. */
const INTERVALO_DE_QUADRO_MS = 130;
/**
 * Quanto o recorte se estende ALÉM da mira, em fração do lado dela, de cada
 * lado.
 *
 * A mira é um contorno de 2 px: um código encostado na borda dela ficaria com
 * metade de fora se o recorte parasse exatamente ali. 6% de ~557 px são ~33 px
 * de cada lado, contra um código que ocupa ~141 px — folga de sobra, e custa
 * ~1,5 ms por quadro no aparelho de referência.
 */
const FOLGA_DA_MIRA = 0.06;
/**
 * Teto do lado do recorte analisado — e é aqui que mora a conta da leitura.
 *
 * ⚠️ **O que se analisa é o RECORTE DA MIRA em resolução nativa, não o quadro
 * inteiro.** A régua da legibilidade não mudou: quem decide é a fração do
 * QUADRO DA CÂMERA que o código ocupa. O QR do token tem 69 módulos, o celular é
 * apresentado a 30-60 cm do tablet, e a essa distância ele ocupa ~11% da
 * LARGURA do quadro — em 640 px isso dá ~1 px por módulo, e nada abaixo de 2
 * px/módulo é lido. Por isso o `getUserMedia` continua pedindo 1280: em 640 a
 * tela não lia mal, não tinha chance nenhuma. **Voltar a reduzir o quadro
 * inteiro é o conserto errado.**
 *
 * O que estava errado era o CUSTO. A medição que sustentava "1280 cabe com
 * folga de 5×" foi feita num quadro LISO, e a cena de um balcão não é lisa:
 * azulejo quadriculado, bandejas e cardápio impresso na parede são textura
 * repetida, e é procurando padrão de localização nela que o jsQR gasta o tempo
 * dele. Medido no browser (Chrome, câmera falsa alimentada por uma cena de
 * balcão sintética com borrão de foco e ruído de sensor; custo = `drawImage` +
 * `getImageData` + `jsQR`, mediana de 40 quadros; o freio de CPU de 6× é o
 * tablet de balcão, a coluna solta é um Apple Silicon):
 *
 *     SEM código no quadro — o estado NORMAL entre um aluno e outro
 *       quadro inteiro 1280×720 ........  19 ms  ·  107 ms com freio de 6×
 *       recorte da mira ~630×630 ........  8 ms  ·   45 ms
 *     COM código, a 2,75 px/módulo
 *       quadro inteiro 1280×720 ........  19 ms  ·  114 ms   · lê
 *       recorte da mira ~630×630 ........ 10 ms  ·   55 ms   · lê
 *       quadro inteiro reduzido a 640 ... 10 ms  ·   58 ms   · NÃO lê
 *
 * Contra os 130 ms de `INTERVALO_DE_QUADRO_MS`, o quadro inteiro come 82% do
 * orçamento de um tablet **na linha em que o balcão passa a maior parte do
 * serviço** — sem ninguém na frente. O recorte come 35%. E a cena sintética é
 * mais boazinha que a real: a lente que abriu este achado mediu ~400 ms num
 * tablet de verdade, onde o quadro inteiro simplesmente não cabe.
 *
 * (O lado do recorte é derivado da mira, não escolhido: 58% da caixa × 75% da
 * largura do quadro que a caixa 4/3 mostra de um vídeo 16/9 = ~557 px, mais a
 * `FOLGA_DA_MIRA` e o arredondamento da origem — 624 a 632 px na prática.)
 *
 * O recorte não custa leitura: em 140 combinações de óptica × px/módulo ×
 * tamanho de recorte, a taxa do recorte foi IDÊNTICA à do quadro inteiro. O
 * único jeito de ele ler pior é desalinhar a fase de 8 px do binarizador do
 * jsQR, e disso cuida `dominio/mira.ts` (com a medição no comentário de lá).
 *
 * ⚠️ O teto só age quando o aparelho entrega MAIS do que o `getUserMedia`
 * pediu. Em 1280×720 a mira dá 624 px e é analisada em 1:1, que é o ponto; numa
 * câmera de 1920 ela daria 935 px e o teto reduz para 768 — ainda ~2,5
 * px/módulo. Sem teto, em 4K a mira sozinha valeria 2,8 megapixels.
 *
 * ⚠️ O preço aceito: um código apontado FORA da mira deixa de ser lido, onde o
 * quadro inteiro leria. É por isso que a mira é desenhada na tela e o subtítulo
 * manda apontar para ela — e é por isso que ela tem 4× a largura do código.
 */
const LADO_MAXIMO_DO_RECORTE = 768;
/**
 * O quanto o balcão espera pela confirmação antes de voltar a ler.
 *
 * ⚠️ Esta é a rede de segurança do `ocupadoRef`, e ela existe MESMO com o teto
 * de `servicos/http.ts`: o de lá é o do gateway (5 min), calibrado para não
 * cortar rota lenta nenhuma, e cinco minutos de câmera cega com fila na frente é
 * o mesmo defeito de antes, só que com hora marcada. O prazo de um balcão é
 * este — e ele vale mesmo que o transporte mude de ideia um dia.
 *
 * 12 s é ~100× o que a rota leva de verdade (um JWT lido e um UPDATE
 * condicional, docs/40 §4): quando ele estoura, alguma coisa está mesmo errada.
 */
const RESPOSTA_NO_BALCAO_MS = 12_000;
/**
 * Quanto tempo o vídeo pode ficar parado antes de a tela concluir que a câmera
 * morreu.
 *
 * Um `<video>` de câmera avança `currentTime` continuamente; se ele para com a
 * página visível, não há mais imagem chegando — não importa se por pausa, por
 * trilha mutada ou por trilha encerrada. Medir o congelamento cobre as três de
 * uma vez, sem depender de qual evento cada sistema resolve disparar.
 */
const CONGELADO_MS = 2_500;
/** Quantas ressurreições automáticas antes de a tela desistir e pedir ajuda. */
const RESSURREICOES_SEGUIDAS = 3;
/**
 * Quanto «Ligando a câmera…» pode ficar mudo antes de a tela dizer que está
 * esperando a PERMISSÃO. Curto de propósito: passado isso, ou o navegador está
 * perguntando, ou alguma coisa não está andando — e nos dois casos a pessoa no
 * balcão precisa de uma frase, não de uma reticência.
 */
const ESPERANDO_PERMISSAO_MS = 6_000;

type EstadoDaCamera = 'iniciando' | 'ligada' | 'negada' | 'indisponivel' | 'falhou';

export function AoVivo() {
  const [refeicaoDoServico, setRefeicaoDoServico] = useState<Refeicao>(() => refeicaoPorHorario());
  const [camera, setCamera] = useState<EstadoDaCamera>('iniciando');
  // `getUserMedia` fica PENDENTE enquanto o aviso de permissão do navegador
  // estiver aberto — pode ser meio segundo ou um minuto, e "Ligando a câmera…"
  // parado é indistinguível de travamento. Passados alguns segundos a tela diz
  // onde procurar, em vez de deixar a pessoa recarregar a página (o que fecha o
  // aviso e recomeça tudo).
  const [demorando, setDemorando] = useState(false);
  const [leitura, setLeitura] = useState<LeituraDoQr | null>(null);
  // Cada linha do histórico carrega um número de ordem próprio: o mesmo aluno
  // pode aparecer duas vezes (a segunda passagem por engano é um dos casos do
  // docs/40 §7), e o índice do array como chave faria o React reaproveitar a
  // linha errada quando a lista anda.
  const [historico, setHistorico] = useState<Array<{ n: number; leitura: LeituraDoQr }>>([]);
  const contadorRef = useRef(0);
  const confirmar = useConfirmarRetirada();

  const videoRef = useRef<HTMLVideoElement>(null);
  // A mira é lida do DOM, não repetida em número mágico: é ela que diz ao aluno
  // onde encostar o celular, e é ela que o laço recorta (`dominio/mira.ts`).
  // Mexer no CSS move os dois juntos.
  const miraRef = useRef<HTMLDivElement>(null);
  const telaRef = useRef<HTMLCanvasElement | null>(null);
  // O religar mora num ref porque a maquinaria da câmera vive dentro do efeito,
  // e é lá que ela tem de ficar: é toda ela ligar/desligar com limpeza no
  // desmonte. O botão da tela só precisa de um gatilho.
  const religarRef = useRef<() => void>(() => undefined);
  // Enquanto uma confirmação está no ar — ou a ficha está na tela —, a varredura
  // continua rodando mas não envia nada: sem esta trava, os oito quadros
  // seguintes ao primeiro mandariam oito confirmações do mesmo código, e sete
  // voltariam 409 "já retirado" sobre uma retirada que acabou de dar certo.
  const ocupadoRef = useRef(false);
  const ultimoRef = useRef<{ token: string; quando: number } | null>(null);
  // Cada leitura recebe um número, e só a MAIS NOVA tem direito à tela. Sem
  // isso, duas coisas se atropelam: uma confirmação lenta que assenta depois de
  // a seguinte já ter pintado a ficha apagaria a ficha certa, e o relógio de 5 s
  // de uma leitura tiraria da tela a ficha da leitura seguinte.
  const vezRef = useRef(0);
  // O relógio que tira a ficha da tela vive num ref para poder ser CANCELADO:
  // dois relógios soltos ao mesmo tempo é justamente o atropelo acima.
  const fichaRef = useRef(0);

  const confirmarToken = confirmar.mutateAsync;

  const aoLer = useCallback(async (token: string) => {
    const agora = Date.now();
    const ultimo = ultimoRef.current;
    if (ultimo && ultimo.token === token && agora - ultimo.quando < MESMO_CODIGO_MS) return;

    vezRef.current += 1;
    const vez = vezRef.current;
    ocupadoRef.current = true;
    ultimoRef.current = { token, quando: agora };

    /** Põe o desfecho na tela — se esta ainda for a leitura da vez. */
    const mostrar = (resultado: LeituraDoQr) => {
      if (vezRef.current !== vez) return;
      setLeitura(resultado);
      window.clearTimeout(fichaRef.current);
      // Volta a escanear SOZINHA, sem exigir toque: quem está no balcão está
      // com as duas mãos ocupadas (docs/40 §7).
      fichaRef.current = window.setTimeout(() => {
        if (vezRef.current !== vez) return;
        ocupadoRef.current = false;
        setLeitura(null);
      }, FICHA_NA_TELA_MS);
    };

    // ⚠️ **A rede de segurança, e é o conserto mais importante desta tela.**
    // `ocupadoRef` só era solto quando a promessa assentava; uma requisição
    // pendurada (wi-fi oscilando no meio do POST) a deixava presa em `true` e a
    // varredura passava a descartar TODO quadro — câmera ligada, mira na tela,
    // painel dizendo "Esperando um código…", e nenhum aluno mais sendo lido.
    // Cego, sem erro, com fila esperando.
    //
    // `ultimoRef` é limpo junto: a trava de "não releia o mesmo código" existe
    // para não confirmar duas vezes o que JÁ DEU CERTO, e aqui não deu certo
    // nada. Sem limpá-la, o aluno na frente ficaria 45 s sem poder ser lido de
    // novo. Se a primeira tentativa tiver chegado ao servidor apesar de tudo, a
    // segunda volta 409 "já retirado às 12h14" — que é verdade, e é servível.
    //
    // `ocupadoRef` continua garantindo UMA tentativa por vez: mesmo com a rede
    // toda fora, isto é uma requisição a cada 12 s, não uma por quadro.
    const semResposta = window.setTimeout(() => {
      if (vezRef.current !== vez) return;
      ultimoRef.current = null;
      ocupadoRef.current = false;
      mostrar(lerRespostaDoQr({ status: 0, mensagem: '' }, refeicaoDoServico));
    }, RESPOSTA_NO_BALCAO_MS);

    try {
      const ficha = await confirmarToken(token);
      const resultado = lerRespostaDoQr(ficha, refeicaoDoServico);
      // O histórico registra FATO, não a tela do momento: uma confirmação que
      // chegou tarde continua sendo uma retirada que o servidor gravou, e
      // escondê-la faria o placar da tela contar menos do que aconteceu.
      contadorRef.current += 1;
      const n = contadorRef.current;
      setHistorico((atual) => [{ n, leitura: resultado }, ...atual].slice(0, 12));
      mostrar(resultado);
    } catch (erro) {
      // O status é o que separa "segunda passagem" de "peça para atualizar" de
      // "cardápio de outra cantina" — três desfechos com ações diferentes
      // (docs/40 §7). A tradução é função pura, com teste ao lado.
      const status = erro instanceof ErroApi ? erro.status : 0;
      // Só a frase de um `ErroApi` chega ao balcão: ela vem do servidor, ou do
      // transporte, que escrevem para gente. Qualquer outro erro (um corpo com
      // JSON quebrado, por exemplo) traria a mensagem do motor de JS para a tela
      // — e a frase padrão do domínio diz mais.
      const mensagem = erro instanceof ErroApi ? erro.message : '';
      mostrar(lerRespostaDoQr({ status, mensagem }, refeicaoDoServico));
    } finally {
      window.clearTimeout(semResposta);
    }
  }, [confirmarToken, refeicaoDoServico]);

  // Os relógios não podem sobreviver à tela: `setLeitura` depois do desmonte é
  // trabalho jogado fora, e a cantina fecha esta aba todo dia.
  useEffect(() => () => window.clearTimeout(fichaRef.current), []);

  /**
   * O aviso de demora, rearmado a CADA entrada em «iniciando».
   *
   * ⚠️ Era um `setTimeout` criado uma vez só, no efeito da câmera, e isso
   * fechava um beco sem saída **pelo caminho que a própria mensagem de permissão
   * negada manda seguir**: abrir o cadeado, redefinir a permissão e apertar
   * «Ligar a câmera de novo». Aí o navegador volta a PERGUNTAR e o
   * `getUserMedia` fica pendente; como o relógio já tinha disparado lá atrás,
   * `demorando` não voltava a `true` e a tela ficava em «Ligando a câmera…» —
   * sem botão, sem explicação e sem nada acontecendo.
   *
   * O comentário antigo dizia que repetir o aviso "mandaria procurar um aviso
   * que não vai aparecer". É o contrário: quando a permissão foi redefinida, o
   * aviso do navegador aparece de novo, e é exatamente essa a hora de apontar
   * para ele.
   */
  useEffect(() => {
    if (camera !== 'iniciando') {
      setDemorando(false);
      return;
    }
    const aviso = window.setTimeout(() => setDemorando(true), ESPERANDO_PERMISSAO_MS);
    return () => window.clearTimeout(aviso);
  }, [camera]);

  /** O botão de "tentar de novo" da mensagem de câmera parada. */
  const religar = useCallback(() => {
    setCamera('iniciando');
    religarRef.current();
  }, []);

  // O callback vive num ref para o laço da câmera não ser remontado a cada
  // troca de refeição do serviço: religar a câmera pisca a imagem e perde
  // meio segundo de leitura, e nada disso tem a ver com a decodificação.
  const aoLerRef = useRef(aoLer);
  useEffect(() => { aoLerRef.current = aoLer; }, [aoLer]);

  useEffect(() => {
    let cancelado = false;
    let stream: MediaStream | null = null;
    let quadro = 0;
    let ultimoQuadro = 0;
    // O último instante em que o vídeo REALMENTE andou (ver `CONGELADO_MS`).
    let andou = { tempo: -1, quando: 0 };
    // `play()` é a tentativa barata, e serve uma vez por congelamento: se o
    // vídeo continua parado depois dela, o problema não era pausa.
    let tentouPlay = false;
    let religando = false;
    // Quantas ressurreições seguidas SEM o vídeo voltar a andar. Existe porque a
    // recuperação automática, sozinha, é um laço: uma câmera que abre e não
    // entrega quadro nenhum seria pedida de novo a cada 2,5 s para sempre. Ao
    // fim das tentativas a tela DIZ que parou e oferece o botão — que é melhor
    // que uma tela calma tentando em silêncio atrás de uma fila.
    let ressurreicoes = 0;
    // O recorte da mira, guardado entre quadros — ver `medirRecorte`.
    let recorte: Recorte | null = null;
    let quadroMedido = '';
    let remedir = true;

    const desligar = () => {
      for (const trilha of stream?.getTracks() ?? []) {
        // Antes do `stop()`: `stop()` não dispara `ended`, mas deixar o
        // manipulador pendurado numa trilha morta é convite a religar a câmera
        // depois do desmonte.
        trilha.onended = null;
        trilha.stop();
      }
      stream = null;
    };

    /**
     * O vídeo andou desde o último quadro?
     *
     * É a checagem que faltava, e a falta era muda: no iOS, quando o tablet
     * bloqueia ou troca de app, o vídeo pausa e a trilha é mutada — sem erro,
     * sem evento tratado. Ao voltar, o estado do componente continuava `'ligada'`
     * e o `jsQR` analisava **o mesmo quadro congelado, para sempre**, com a mira
     * na tela e o painel dizendo "Esperando um código…".
     */
    const andando = (video: HTMLVideoElement, agora: number): boolean => {
      if (!stream) return false;
      if (video.currentTime !== andou.tempo) {
        andou = { tempo: video.currentTime, quando: agora };
        tentouPlay = false;
        ressurreicoes = 0;
        return true;
      }
      if (agora - andou.quando < CONGELADO_MS) return true;
      void reanimar();
      return false;
    };

    /** Recupera a câmera parada — do jeito barato, e depois do jeito caro. */
    const reanimar = async () => {
      if (cancelado || religando) return;
      religando = true;
      try {
        const video = videoRef.current;
        const trilha = stream?.getVideoTracks()[0];
        const viva = !!trilha && trilha.readyState === 'live' && !trilha.muted;
        if (video && viva && !tentouPlay) {
          tentouPlay = true;
          // ⚠️ Renova só o PRAZO, nunca o tempo marcado. Zerar `andou.tempo`
          // aqui faria o quadro seguinte ler o vídeo parado como "andou" — e
          // com isso `tentouPlay` voltava a `false` e a tela ficava dando
          // `play()` num vídeo morto para sempre, sem nunca chegar ao caminho
          // caro. Foi assim no browser, e só apareceu lá.
          andou = { tempo: andou.tempo, quando: performance.now() };
          await video.play().catch(() => undefined);
          return;
        }
        if (ressurreicoes >= RESSURREICOES_SEGUIDAS) {
          desligar();
          setCamera('falhou');
          return;
        }
        // Trilha mutada ou encerrada não volta com `play()`: o stream acabou, e
        // o que existe é pedir outro.
        ressurreicoes += 1;
        desligar();
        await ligar();
      } finally {
        religando = false;
      }
    };

    /**
     * Onde recortar, em pixels do quadro.
     *
     * `getBoundingClientRect` força layout, então o resultado fica guardado e
     * só é refeito quando a geometria muda de verdade: o observador cuida do
     * redimensionamento e da rotação do tablet, e a comparação de
     * `videoWidth/videoHeight` cuida da câmera que troca de resolução no meio
     * (acontece ao religar depois de outro app ter tomado o aparelho).
     */
    const medirRecorte = (video: HTMLVideoElement): Recorte | null => {
      const caixa = video.getBoundingClientRect();
      const mira = miraRef.current?.getBoundingClientRect() ?? null;
      // Enquanto a mira não estiver montada vale o recorte de segurança, mas a
      // medida NÃO é guardada: o contorno aparece no commit seguinte ao
      // `setCamera('ligada')`, e congelar o palpite aqui deixaria a tela lendo
      // um quadrado grande demais pelo resto do serviço.
      if (!mira) remedir = true;
      return recorteDaMira(
        {
          quadro: { largura: video.videoWidth, altura: video.videoHeight },
          video: { largura: caixa.width, altura: caixa.height },
          mira: mira && {
            x: mira.left - caixa.left, y: mira.top - caixa.top,
            largura: mira.width, altura: mira.height,
          },
        },
        { folga: FOLGA_DA_MIRA, ladoMaximo: LADO_MAXIMO_DO_RECORTE },
      );
    };

    const varrer = (agora: number) => {
      quadro = requestAnimationFrame(varrer);
      if (agora - ultimoQuadro < INTERVALO_DE_QUADRO_MS) return;
      ultimoQuadro = agora;

      const video = videoRef.current;
      if (!video || video.readyState < video.HAVE_CURRENT_DATA) return;
      // A vigília vem ANTES da trava de ocupado: uma câmera que morreu enquanto
      // uma confirmação estava no ar tem de ser percebida do mesmo jeito.
      if (!andando(video, agora)) return;
      if (ocupadoRef.current) return;

      const assinatura = `${video.videoWidth}×${video.videoHeight}`;
      if (remedir || !recorte || assinatura !== quadroMedido) {
        remedir = false;
        quadroMedido = assinatura;
        recorte = medirRecorte(video);
      }
      if (!recorte) return;
      const { origem, destino } = recorte;

      // Um canvas só, reaproveitado: alocar um por quadro seria 8 canvas por
      // segundo para o coletor de lixo, durante duas horas de serviço.
      if (!telaRef.current) telaRef.current = document.createElement('canvas');
      const tela = telaRef.current;
      if (tela.width !== destino.largura || tela.height !== destino.altura) {
        tela.width = destino.largura;
        tela.height = destino.altura;
      }
      const pincel = tela.getContext('2d', { willReadFrequently: true });
      if (!pincel) return;
      // A forma de nove argumentos: recorta do quadro e desenha 1:1 no destino.
      // É ela que dá mais pixel por módulo POR MENOS custo do que reduzir o
      // quadro inteiro (ver `LADO_MAXIMO_DO_RECORTE`).
      pincel.drawImage(
        video, origem.x, origem.y, origem.largura, origem.altura,
        0, 0, destino.largura, destino.altura,
      );

      const dados = pincel.getImageData(0, 0, destino.largura, destino.altura).data;
      const codigo = jsQR(dados, destino.largura, destino.altura, {
        // Só o QR normal: tentar a versão invertida dobra o custo por quadro, e
        // a tela do aluno é sempre escura sobre branco por decisão da tela do
        // código (`CantinaRetirada.tsx`).
        inversionAttempts: 'dontInvert',
      });
      if (codigo?.data) void aoLerRef.current(codigo.data);
    };

    const ligar = async () => {
      // Sem `mediaDevices` não houve recusa nenhuma: o navegador não oferece a
      // API fora de contexto seguro, e o usuário nunca viu um pedido.
      if (!navigator.mediaDevices?.getUserMedia) {
        setCamera('indisponivel');
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            // A traseira no tablet do balcão; num notebook só existe uma e o
            // navegador ignora a preferência em vez de falhar.
            facingMode: 'environment',
            // ⚠️ Sem pedir resolução, o navegador escolhe — e "escolhe" costuma
            // ser 640×480, em que o QR do aluno não é legível a distância de
            // balcão nenhuma (a conta está em `LADO_MAXIMO_DO_RECORTE`).
            // Recortar a mira não substitui isto: recorte não inventa pixel, só
            // deixa de gastar com o que não interessa. `ideal`, nunca `exact`:
            // `exact` levanta `OverconstrainedError` numa webcam que só faz
            // 640×480, e a tela cairia em "não consegui abrir a câmera" onde
            // hoje ela pelo menos tenta.
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: false,
        });
      } catch (erro) {
        if (cancelado) return;
        const nome = erro instanceof Error ? erro.name : '';
        setCamera(nome === 'NotAllowedError' || nome === 'SecurityError' ? 'negada' : 'falhou');
        return;
      }
      const video = videoRef.current;
      if (cancelado || !video) {
        desligar();
        return;
      }

      // A trilha ACABOU: outro app tomou a câmera, o cabo saiu, o sistema
      // revogou a permissão. Não há `play()` que resolva — e sem tratar isso a
      // tela ficaria com a mira desenhada sobre um quadro parado dizendo
      // "Esperando um código…". O pior desfecho desta tela é o mudo.
      for (const trilha of stream.getVideoTracks()) {
        trilha.onended = () => { if (!cancelado) void reanimar(); };
      }

      video.srcObject = stream;
      // `play()` rejeita quando a aba perde o foco no meio; não é falha de
      // câmera, e derrubar a tela por isso seria pior que continuar.
      await video.play().catch(() => undefined);
      if (cancelado) {
        desligar();
        return;
      }
      setCamera('ligada');
      andou = { tempo: -1, quando: 0 };
      tentouPlay = false;
      // Um laço só. `ligar()` também é o caminho da ressurreição, e sem cancelar
      // o anterior cada recuperação deixaria mais um `requestAnimationFrame`
      // rodando por cima — numa tela que fica aberta o serviço inteiro.
      cancelAnimationFrame(quadro);
      quadro = requestAnimationFrame(varrer);
    };

    // Voltar do bloqueio ou de outro app: o iOS deixa o vídeo pausado e não o
    // retoma sozinho. O `play()` cobre o caso comum; a vigília de congelamento
    // cobre o resto.
    const aoVoltar = () => {
      if (cancelado || document.visibilityState !== 'visible') return;
      // `requestAnimationFrame` não roda com a aba escondida, então o marcador
      // de "andou" parou no tempo junto com o vídeo: sem zerá-lo, o primeiro
      // quadro da volta seria lido como um congelamento de dez minutos.
      andou = { tempo: -1, quando: 0 };
      tentouPlay = false;
      void videoRef.current?.play().catch(() => undefined);
    };
    document.addEventListener('visibilitychange', aoVoltar);

    // Redimensionar a janela ou girar o tablet muda onde a mira cai dentro do
    // quadro. Um observador em vez de `window.onresize` porque a caixa da
    // câmera também muda de tamanho sem a janela mudar — o histórico embaixo
    // dela cresce à medida que a fila anda.
    const observador = new ResizeObserver(() => { remedir = true; });
    if (videoRef.current) observador.observe(videoRef.current);

    // A saída manual, para quando a automática não deu conta (a câmera segue
    // tomada por outro app, a permissão foi revogada). Quem está no balcão não
    // deveria ter de recarregar a página com a fila esperando.
    religarRef.current = () => {
      // O toque zera a conta: quem apertou sabe de algo que a tela não sabe —
      // que o outro app foi fechado, que a permissão foi dada agora.
      ressurreicoes = 0;
      tentouPlay = false;
      void reanimar();
    };

    void ligar();

    return () => {
      cancelado = true;
      religarRef.current = () => undefined;
      document.removeEventListener('visibilitychange', aoVoltar);
      observador.disconnect();
      cancelAnimationFrame(quadro);
      desligar();
    };
  }, []);

  const contagemDoDia = useMemo(
    () => historico.filter((l) => l.leitura.tipo === 'sucesso').length,
    [historico],
  );

  return (
    <div className="cant-tela cant-aovivo">
      <header className="cant-cabeca">
        <div>
          <h1 className="cant-titulo">Ler código</h1>
          {/* «dentro do quadrado» não é capricho de redação: desde que a
              leitura passou a analisar o recorte da mira
              (`LADO_MAXIMO_DO_RECORTE`), o que está fora dele não é lido. A
              tela tem de dizer isso, e a mira desenhada sozinha não diz. */}
          <p className="cant-sub">
            Aponte a câmera para o código do aluno, dentro do quadrado. A leitura é automática e
            volta a escanear sozinha.
          </p>
        </div>

        <div className="cant-cabeca__acoes">
          {/* Qual serviço está em curso. Não bloqueia nada: só decide quando a
              ficha destaca "refeição trocada" (docs/40 §7) — o token de janta
              lido no almoço é VÁLIDO, e quem decide é quem está no balcão. */}
          <div className="cant-abas" role="tablist" aria-label="Refeição em serviço">
            {(['almoco', 'janta'] as Refeicao[]).map((r) => (
              <button
                key={r}
                type="button"
                role="tab"
                aria-selected={refeicaoDoServico === r}
                className={`cant-aba${refeicaoDoServico === r ? ' cant-aba--ativa' : ''}`}
                onClick={() => setRefeicaoDoServico(r)}
              >
                {ROTULO_DA_REFEICAO[r]}
              </button>
            ))}
          </div>

          <span className="cant-magnitude">
            <span className="cant-magnitude__numero">{contagemDoDia}</span>
            <span className="cant-magnitude__legenda">
              retirada{contagemDoDia === 1 ? '' : 's'} nesta tela
            </span>
          </span>
        </div>
      </header>

      <div className="cant-aovivo__palco">
        <div className="cant-aovivo__camera">
          {/* `muted` e `playsInline` não são enfeite: sem os dois, o iOS recusa
              o autoplay e o vídeo fica preto sem erro nenhum. */}
          <video
            ref={videoRef}
            className="cant-aovivo__video"
            muted
            playsInline
            // Não há áudio nem legenda a oferecer: é o quadro da câmera,
            // consumido por `jsQR` e descartado. Nada aqui é gravado nem sai
            // do aparelho.
          />
          {/* A mira é desenho E contrato: é o retângulo que o laço recorta para
              ler (`dominio/mira.ts`). Mudar o tamanho dela em `cantina.css`
              muda o que é lido — e é para ser assim. */}
          {camera === 'ligada' && (
            <div ref={miraRef} className="cant-aovivo__mira" aria-hidden="true" />
          )}
          {camera !== 'ligada' && (
            <div className="cant-aovivo__semcamera">
              <ProblemaDeCamera estado={camera} demorando={demorando} onReligar={religar} />
            </div>
          )}
        </div>

        <div className="cant-aovivo__resultado" aria-live="polite">
          {leitura ? <Ficha leitura={leitura} /> : (
            <p className="cant-vazio">
              {camera === 'ligada' ? 'Esperando um código…' : 'Câmera parada.'}
            </p>
          )}
        </div>
      </div>

      {historico.length > 0 && (
        <section>
          <h2 className="cant-refeicao__olho">Últimas leituras</h2>
          <ul className="cant-aovivo__historico">
            {historico.map(({ n, leitura: l }) => (
              <li key={n} className="cant-aovivo__linha">
                {l.tipo === 'sucesso' ? (
                  <>
                    <b>{l.ficha.nome ?? 'sem nome'}</b>
                    {l.ficha.turma && <span className="cant-lista__turma">{l.ficha.turma}</span>}
                    <span className="cant-lista__escolhas">
                      {ROTULO_DA_REFEICAO[l.ficha.refeicao]} · {horaLegivel(l.ficha.retiradoEm)}
                    </span>
                  </>
                ) : (
                  <span className="cant-lista__escolhas">{l.mensagem}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/**
 * A ficha da leitura — e os quatro desfechos NÃO são "sucesso e erro".
 *
 * Só um deles é problema de verdade. A segunda passagem por engano é o caso
 * comum e não pode parecer falha; o token vencido tem uma ação do lado do
 * ALUNO; o cardápio de outra cantina tem uma ação de ninguém ali.
 */
function Ficha({ leitura }: { leitura: LeituraDoQr }) {
  if (leitura.tipo !== 'sucesso') {
    return (
      <div
        className={`cant-ficha-leitura cant-ficha-leitura--${ESTILO_DA_LEITURA[leitura.tipo]}`}
        role="status"
      >
        <span className="cant-ficha-leitura__olho">{TITULO_DA_LEITURA[leitura.tipo]}</span>
        <p className="cant-ficha-leitura__frase">{leitura.mensagem}</p>
      </div>
    );
  }

  const { ficha, refeicaoTrocada } = leitura;
  return (
    <div className="cant-ficha-leitura cant-ficha-leitura--sucesso" role="status">
      <span className="cant-ficha-leitura__olho">Pode servir</span>
      <p className="cant-ficha-leitura__nome">{ficha.nome ?? 'sem nome'}</p>
      <p className="cant-ficha-leitura__sub">
        {ficha.turma ?? 'sem turma'} · {ROTULO_DA_REFEICAO[ficha.refeicao]}
        {ficha.data && ` de ${rotuloDoDia(ficha.data)}`} · {horaLegivel(ficha.retiradoEm)}
      </p>

      {/* ⚠️ A restrição em DESTAQUE, e não numa linha qualquer: este é o único
          instante em que dá para agir sobre ela — o prato ainda não foi
          montado (docs/40 §7, docs/38 §2.6). */}
      {ficha.restricaoAlimentar && (
        <p className="cant-ficha-leitura__restricao">⚠ {ficha.restricaoAlimentar}</p>
      )}

      {refeicaoTrocada && (
        <p className="cant-ficha-leitura__trocada">
          Este código é do <b>{ROTULO_DA_REFEICAO[ficha.refeicao].toLowerCase()}</b>, não da
          refeição em serviço. Não é erro do aluno — decida no balcão.
        </p>
      )}
    </div>
  );
}

const TITULO_DA_LEITURA: Record<Exclude<LeituraDoQr['tipo'], 'sucesso'>, string> = {
  'ja-retirado': 'Já retirado',
  atualizar: 'Peça para o aluno atualizar a tela',
  recusado: 'Não dá para servir por aqui',
  'sem-resposta': 'O servidor não respondeu',
};

/**
 * A moldura de cada desfecho — e `sem-resposta` toma emprestada a de `recusado`.
 *
 * O CSS tem três skins (`--ja-retirado`, `--atualizar`, `--recusado`), e a falta
 * de resposta é falha operacional como a recusa: mesma moldura de alerta. O que
 * NÃO pode ser emprestado é o título — "Não dá para servir por aqui" mandaria
 * embora um aluno que só precisa que se leia o código de novo.
 */
const ESTILO_DA_LEITURA: Record<Exclude<LeituraDoQr['tipo'], 'sucesso'>, string> = {
  'ja-retirado': 'ja-retirado',
  atualizar: 'atualizar',
  recusado: 'recusado',
  'sem-resposta': 'recusado',
};

function ProblemaDeCamera({
  estado, demorando, onReligar,
}: { estado: EstadoDaCamera; demorando: boolean; onReligar: () => void }) {
  if (estado === 'iniciando') {
    return demorando ? (
      <div className="cant-aviso">
        <b>Esperando a permissão.</b> O navegador pede autorização para usar a câmera — o aviso
        aparece no alto da janela. Responda «Permitir» e a leitura começa sozinha.
      </div>
    ) : (
      <p className="cant-vazio">Ligando a câmera…</p>
    );
  }

  if (estado === 'negada') {
    return (
      <div className="cant-aviso" role="alert">
        <b>O navegador bloqueou a câmera.</b> Clique no cadeado ao lado do endereço, autorize a
        câmera para este site e tente de novo.
        <div className="cant-acoes">
          <button type="button" className="cant-tecla" onClick={onReligar}>
            Ligar a câmera de novo
          </button>
        </div>
      </div>
    );
  }

  if (estado === 'indisponivel') {
    return (
      <div className="cant-aviso" role="alert">
        <b>Este endereço não permite câmera.</b> O navegador só a oferece em <code>https://</code>
        {' '}ou em <code>localhost</code> — e você está em <code>{window.location.origin}</code>.
        Abra o sistema pelo endereço oficial da escola.
      </div>
    );
  }

  // Também é o desfecho de uma câmera que PAROU no meio do serviço — a trilha
  // encerrada, o tablet que dormiu, o app de vídeo que tomou a câmera. Por isso
  // a saída aqui é um botão, e não "recarregue a página": recarregar com a fila
  // parada custa o dobro, e a maior parte das vezes um pedido novo resolve.
  return (
    <div className="cant-aviso" role="alert">
      <b>A câmera parou.</b> Verifique se outro programa está usando ela e ligue de novo.
      <div className="cant-acoes">
        <button type="button" className="cant-tecla" onClick={onReligar}>
          Ligar a câmera de novo
        </button>
      </div>
    </div>
  );
}
