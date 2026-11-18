// Avisos neste aparelho — a parte que fala com o NAVEGADOR (docs/45 §6.1).
//
// Web Push padrão: `serviceWorker` + `PushManager` + `Notification`, e nenhum
// SDK de fornecedor (docs/20 §6). O que decidir sem navegador mora em
// `dominio/avisosNoAparelho.ts`; o HTTP, em `servicos/api.ts`.
//
// ⚠️ **Toda inscrição nasce de um clique.** `ativar` é o único caminho que cria
// (ou toma para si) uma inscrição no servidor. A leitura de cada abertura
// (`lerAparelho`) só CONFIRMA o que já é desta pessoa e nunca cria: senão o
// aparelho revogado na lista de outro voltaria sozinho, e quem entra depois
// num computador compartilhado herdaria os avisos de quem saiu sem ter pedido.
// O mesmo vale para o `pushsubscriptionchange`, que não é usado: além de só o
// Firefox dispará-lo com confiança, ele reinscreveria sem ninguém pedir.

import * as api from './api';
import type { ConfiguracaoDosAvisos } from './api';
import {
  chaveParaBytes,
  descricaoDoAparelho,
  estadoDoAparelho,
  mesmosBytes,
  plataformaDoAparelho,
} from '../dominio/avisosNoAparelho';
import type { EstadoDoAparelho, PermissaoDoNavegador, Plataforma } from '../dominio/avisosNoAparelho';

const CAMINHO_DO_SERVICE_WORKER = '/sw.js';

/**
 * Teto para o que depende do navegador. `navigator.serviceWorker.ready` NUNCA
 * assenta se o registro falhou (sw.js fora do ar, bloqueado por extensão) — e
 * promessa que nunca assenta deixa o botão em "Ativando…" para sempre, o mesmo
 * defeito que o teto de `servicos/http.ts` existe para impedir.
 */
const PRAZO_DO_NAVEGADOR_MS = 15_000;

/**
 * O `subscribe` tem prazo próprio, maior: na PRIMEIRA vez de um navegador, ele
 * espera o Chrome abrir a conexão com o FCM, e isso já passou de 15 s num
 * perfil novo (verificação de 18/11). Estourar não perde nada: a inscrição que
 * chegar depois fica no navegador, a tela mostra "Ativar" de novo (o servidor
 * não a tem), e o segundo clique a reaproveita em vez de criar outra.
 */
const PRAZO_DA_INSCRICAO_MS = 30_000;

/** Tempo que o Sair espera pela limpeza antes de sair mesmo assim. */
const PRAZO_DO_SAIR_MS = 2_500;

export class PermissaoNegada extends Error {
  constructor(readonly permissao: NotificationPermission) {
    super(
      permissao === 'denied'
        ? 'O navegador bloqueou os avisos para o SAS.'
        : 'Os avisos não foram permitidos. Toque em Ativar de novo para responder ao navegador.',
    );
    this.name = 'PermissaoNegada';
  }
}

function comPrazo<T>(promessa: Promise<T>, ms: number, mensagem: string): Promise<T> {
  let relogio: ReturnType<typeof setTimeout> | undefined;
  const estouro = new Promise<never>((_, rejeitar) => {
    relogio = setTimeout(() => rejeitar(new Error(mensagem)), ms);
  });
  return Promise.race([promessa, estouro]).finally(() => clearTimeout(relogio));
}

export function temPush(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

/** Aberto como app — Tela de Início do iPhone, app instalado no Android ou no desktop. */
export function estaInstalado(): boolean {
  const iosStandalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return iosStandalone || window.matchMedia?.('(display-mode: standalone)').matches === true;
}

function plataformaAtual(): Plataforma {
  return plataformaDoAparelho(navigator.userAgent, navigator.maxTouchPoints ?? 0);
}

/**
 * Registra o service worker. Chamado uma vez, em `main.tsx`, em toda rota.
 *
 * O `sw.js` não tem handler de `fetch` (docs/45 §4): nada é cacheado, então
 * registrá-lo não muda o carregamento de nenhuma tela. É o que faz o Chrome
 * oferecer "Instalar" e o que recebe o push com o SAS fechado.
 */
export function registrarServiceWorker(): void {
  if (!('serviceWorker' in navigator)) return;
  const registrar = () => {
    navigator.serviceWorker.register(CAMINHO_DO_SERVICE_WORKER, { scope: '/' }).catch(() => {
      // Sem service worker o SAS funciona igual; só não recebe aviso.
    });
  };
  // Depois do `load`, para não disputar banda com a primeira tela no 3G da escola.
  if (document.readyState === 'complete') registrar();
  else window.addEventListener('load', registrar, { once: true });
}

async function registroAtivo(): Promise<ServiceWorkerRegistration> {
  const existente = await navigator.serviceWorker.getRegistration('/');
  if (!existente) await navigator.serviceWorker.register(CAMINHO_DO_SERVICE_WORKER, { scope: '/' });
  // `subscribe` exige um worker ATIVO; `ready` espera ele terminar de instalar.
  return comPrazo(navigator.serviceWorker.ready, PRAZO_DO_NAVEGADOR_MS, 'O navegador não terminou de preparar os avisos.');
}

async function inscricaoLocal(): Promise<PushSubscription | null> {
  const registro = await navigator.serviceWorker.getRegistration('/');
  return registro ? registro.pushManager.getSubscription() : null;
}

function corpoDaInscricao(inscricao: PushSubscription): api.CorpoDaInscricao {
  const json = inscricao.toJSON();
  const p256dh = json.keys?.p256dh;
  const auth = json.keys?.auth;
  if (!json.endpoint || !p256dh || !auth) throw new Error('O navegador devolveu uma inscrição incompleta.');
  const plataforma = plataformaAtual();
  return {
    endpoint: json.endpoint,
    chaves: { p256dh, auth },
    plataforma,
    descricao_aparelho: descricaoDoAparelho(navigator.userAgent, plataforma, estaInstalado()),
  };
}

export interface LeituraDesteAparelho {
  estado: EstadoDoAparelho;
  plataforma: Plataforma;
  instalado: boolean;
  /** O id da inscrição deste aparelho no servidor — para marcar "este aparelho" na lista. */
  idNoServidor: string | null;
}

/**
 * O estado da seção. Com inscrição local e permissão concedida, confirma no
 * servidor (`/push/inscricoes/confirmar`) — que é também a reconciliação de
 * cada abertura (atualiza `vista_em`), e que nunca cria.
 */
export async function lerAparelho(config: ConfiguracaoDosAvisos): Promise<LeituraDesteAparelho> {
  const plataforma = plataformaAtual();
  const instalado = estaInstalado();
  const push = temPush();
  const permissao: PermissaoDoNavegador = push ? Notification.permission : 'default';

  let registradaAqui = false;
  let idNoServidor: string | null = null;
  if (push && config.ativo && config.chavePublica && permissao === 'granted') {
    const inscricao = await inscricaoLocal();
    // Inscrição feita com OUTRA chave VAPID (a do servidor mudou) não recebe
    // mais nada: o fabricante recusa o envio. Conta como inativa, e o Ativar
    // refaz com a chave certa.
    if (inscricao && mesmosBytes(inscricao.options.applicationServerKey, chaveParaBytes(config.chavePublica))) {
      const resposta = await api.confirmarAparelho(corpoDaInscricao(inscricao));
      registradaAqui = resposta.registrada;
      idNoServidor = resposta.id;
    }
  }

  return {
    estado: estadoDoAparelho({ servidorAtivo: config.ativo, temPush: push, plataforma, instalado, permissao, inscrito: registradaAqui }),
    plataforma,
    instalado,
    idNoServidor,
  };
}

/**
 * Pede a permissão. ⚠️ **Chame DENTRO do clique, antes de qualquer `await`.**
 *
 * O Safari só mostra o pedido com gesto do usuário em andamento, e um `await`
 * antes dele — de uma consulta, de uma mutação — pode consumir o gesto: o
 * pedido não aparece e a promessa volta "default" sem a pessoa ver nada. Por
 * isso a promessa nasce no `onClick` e só DEPOIS vai para a mutação.
 */
export function pedirPermissao(): Promise<NotificationPermission> {
  return Notification.requestPermission();
}

/** O caminho do clique em "Ativar". Devolve o id da inscrição no servidor. */
export async function ativar(permissao: Promise<NotificationPermission>, chavePublica: string): Promise<string> {
  const resposta = await permissao;
  if (resposta !== 'granted') throw new PermissaoNegada(resposta);

  const registro = await registroAtivo();
  const chave = chaveParaBytes(chavePublica);
  let inscricao = await registro.pushManager.getSubscription();
  if (inscricao && !mesmosBytes(inscricao.options.applicationServerKey, chave)) {
    // O navegador recusa inscrever por cima de uma inscrição com outra chave.
    await inscricao.unsubscribe();
    inscricao = null;
  }
  inscricao ??= await comPrazo(
    registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chave }),
    PRAZO_DA_INSCRICAO_MS,
    'O serviço de avisos do navegador não respondeu. Tente de novo.',
  );
  const { id } = await api.inscreverAparelho(corpoDaInscricao(inscricao));
  return id;
}

/** "Desativar neste aparelho": cancela no navegador e no servidor. */
export async function desativar(): Promise<void> {
  if (!temPush()) return;
  const inscricao = await inscricaoLocal();
  if (!inscricao) return;
  const { endpoint } = inscricao;
  // O navegador primeiro. Se o servidor falhar, a linha que sobrar lá leva 410
  // no próximo envio e se apaga sozinha (app/push/envio.py).
  await inscricao.unsubscribe();
  await api.removerInscricaoDoAparelho(endpoint);
}

/**
 * O Sair da conta desativa os avisos NESTE aparelho (docs/45 §12, decisão 5:
 * computador da escola é compartilhado).
 *
 * Fechar a aba NÃO é sair, e não passa por aqui: o aviso existe justamente para
 * quem está com o SAS fechado. O 401 de sessão vencida (`servicos/http.ts`)
 * também não — sessão vencida não é escolha de ninguém.
 *
 * Nunca segura o Sair: com prazo curto, e qualquer erro é engolido.
 */
export async function desativarAoSair(): Promise<void> {
  try {
    await comPrazo(desativar(), PRAZO_DO_SAIR_MS, 'prazo');
  } catch {
    // Sair sempre vence.
  }
}
