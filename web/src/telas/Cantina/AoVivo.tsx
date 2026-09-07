import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import jsQR from 'jsqr';

import {
  horaLegivel, lerRespostaDoQr, refeicaoPorHorario, ROTULO_DA_REFEICAO, rotuloDoDia,
} from '../../dominio/cantina';
import type { LeituraDoQr } from '../../dominio/cantina';
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
/** Teto do quadro analisado. Um vídeo 1080p custaria 6× mais por leitura sem
    achar um QR a mais: o código ocupa metade da tela do aluno. */
const LARGURA_MAXIMA = 640;

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
  const telaRef = useRef<HTMLCanvasElement | null>(null);
  // Enquanto uma confirmação está no ar — ou a ficha está na tela —, a varredura
  // continua rodando mas não envia nada: sem esta trava, os oito quadros
  // seguintes ao primeiro mandariam oito confirmações do mesmo código, e sete
  // voltariam 409 "já retirado" sobre uma retirada que acabou de dar certo.
  const ocupadoRef = useRef(false);
  const ultimoRef = useRef<{ token: string; quando: number } | null>(null);

  const confirmarToken = confirmar.mutateAsync;

  const aoLer = useCallback(async (token: string) => {
    const agora = Date.now();
    const ultimo = ultimoRef.current;
    if (ultimo && ultimo.token === token && agora - ultimo.quando < MESMO_CODIGO_MS) return;

    ocupadoRef.current = true;
    ultimoRef.current = { token, quando: agora };
    try {
      const ficha = await confirmarToken(token);
      const resultado = lerRespostaDoQr(ficha, refeicaoDoServico);
      setLeitura(resultado);
      contadorRef.current += 1;
      const n = contadorRef.current;
      setHistorico((atual) => [{ n, leitura: resultado }, ...atual].slice(0, 12));
    } catch (erro) {
      // O status é o que separa "segunda passagem" de "peça para atualizar" de
      // "cardápio de outra cantina" — três desfechos com ações diferentes
      // (docs/40 §7). A tradução é função pura, com teste ao lado.
      const status = erro instanceof ErroApi ? erro.status : 0;
      const mensagem = erro instanceof Error ? erro.message : '';
      setLeitura(lerRespostaDoQr({ status, mensagem }, refeicaoDoServico));
    } finally {
      // Volta a escanear SOZINHA, sem exigir toque: quem está no balcão está
      // com as duas mãos ocupadas (docs/40 §7).
      window.setTimeout(() => {
        ocupadoRef.current = false;
        setLeitura(null);
      }, FICHA_NA_TELA_MS);
    }
  }, [confirmarToken, refeicaoDoServico]);

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
    const avisoDeDemora = window.setTimeout(() => setDemorando(true), 6_000);

    const desligar = () => {
      for (const trilha of stream?.getTracks() ?? []) trilha.stop();
      stream = null;
    };

    const varrer = (agora: number) => {
      quadro = requestAnimationFrame(varrer);
      if (agora - ultimoQuadro < INTERVALO_DE_QUADRO_MS) return;
      ultimoQuadro = agora;
      if (ocupadoRef.current) return;

      const video = videoRef.current;
      if (!video || video.readyState < video.HAVE_CURRENT_DATA) return;

      const escala = Math.min(1, LARGURA_MAXIMA / (video.videoWidth || LARGURA_MAXIMA));
      const largura = Math.round(video.videoWidth * escala);
      const altura = Math.round(video.videoHeight * escala);
      if (!largura || !altura) return;

      // Um canvas só, reaproveitado: alocar um por quadro seria 8 canvas por
      // segundo para o coletor de lixo, durante duas horas de serviço.
      if (!telaRef.current) telaRef.current = document.createElement('canvas');
      const tela = telaRef.current;
      if (tela.width !== largura || tela.height !== altura) {
        tela.width = largura;
        tela.height = altura;
      }
      const pincel = tela.getContext('2d', { willReadFrequently: true });
      if (!pincel) return;
      pincel.drawImage(video, 0, 0, largura, altura);

      const codigo = jsQR(pincel.getImageData(0, 0, largura, altura).data, largura, altura, {
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
          // A traseira no tablet do balcão; num notebook só existe uma e o
          // navegador ignora a preferência em vez de falhar.
          video: { facingMode: 'environment' },
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
      video.srcObject = stream;
      // `play()` rejeita quando a aba perde o foco no meio; não é falha de
      // câmera, e derrubar a tela por isso seria pior que continuar.
      await video.play().catch(() => undefined);
      if (cancelado) {
        desligar();
        return;
      }
      setCamera('ligada');
      quadro = requestAnimationFrame(varrer);
    };

    void ligar();

    return () => {
      cancelado = true;
      window.clearTimeout(avisoDeDemora);
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
          <p className="cant-sub">
            Aponte a câmera para o código do aluno. A leitura é automática e volta a escanear
            sozinha.
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
          {camera === 'ligada' && <div className="cant-aovivo__mira" aria-hidden="true" />}
          {camera !== 'ligada' && (
            <div className="cant-aovivo__semcamera">
              <ProblemaDeCamera estado={camera} demorando={demorando} />
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
      <div className={`cant-ficha-leitura cant-ficha-leitura--${leitura.tipo}`} role="status">
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
};

function ProblemaDeCamera({
  estado, demorando,
}: { estado: EstadoDaCamera; demorando: boolean }) {
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
        câmera para este site e recarregue a página.
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

  return (
    <div className="cant-aviso" role="alert">
      <b>Não consegui abrir a câmera.</b> Verifique se outro programa está usando ela e recarregue
      a página.
    </div>
  );
}
