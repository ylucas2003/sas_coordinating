// AVISOS NESTE APARELHO — o que a seção mostra, decidido sem tocar no navegador.
//
// Push no aparelho é Web Push padrão (docs/45): sem SDK de fornecedor, o
// navegador fala com o serviço de push do próprio fabricante. Este módulo é a
// parte PURA — a plataforma a partir do user agent, o texto do aparelho e a
// máquina de estados da seção. Quem lê `navigator`, `Notification` e o
// `PushManager` é `servicos/avisosNoAparelho.ts`.
//
// ⚠️ O estado que mais pesa é `precisa-instalar`. No iPhone, a notificação do
// site só existe com o SAS instalado na Tela de Início (iOS 16.4+): numa aba do
// Safari não há `PushManager`, e nenhuma biblioteca contorna isso — é regra da
// Apple (docs/45 §1). A seção ali não oferece botão que não funciona; ensina a
// instalar.

export type Plataforma = 'ios' | 'android' | 'desktop' | 'outra';

export type PermissaoDoNavegador = 'default' | 'granted' | 'denied';

export type EstadoDoAparelho =
  /** O servidor não tem chave VAPID, ou a sessão é de um tipo que não recebe. A seção some. */
  | 'desligado'
  /** Navegador sem Web Push (iOS antigo, navegador embutido de app). */
  | 'sem-suporte'
  /** iPhone/iPad numa aba: só instalado na Tela de Início recebe. */
  | 'precisa-instalar'
  /** A pessoa (ou o navegador) disse "não". O site não pode perguntar de novo. */
  | 'bloqueado'
  /** Pode ativar. */
  | 'inativo'
  /** Inscrito e registrado no servidor. */
  | 'ativo';

/**
 * A plataforma, pelo user agent.
 *
 * O iPad com iPadOS 13+ se apresenta como Mac ("Macintosh") por padrão; o que o
 * entrega é a tela de toque. Sem esta conferência ele cairia em `desktop` e a
 * seção ofereceria um botão que, numa aba do Safari dele, não funciona.
 */
export function plataformaDoAparelho(userAgent: string, pontosDeToque = 0): Plataforma {
  if (/iPhone|iPad|iPod/i.test(userAgent)) return 'ios';
  if (/Macintosh/i.test(userAgent) && pontosDeToque > 1) return 'ios';
  if (/Android/i.test(userAgent)) return 'android';
  if (/Windows|Macintosh|Linux|CrOS/i.test(userAgent)) return 'desktop';
  return 'outra';
}

function navegadorDoAparelho(userAgent: string): string | null {
  // A ordem importa: o Edge e o Samsung Internet também dizem "Chrome", e todo
  // navegador do iPhone diz "Safari".
  if (/Edg(e|A|iOS)?\//.test(userAgent)) return 'Edge';
  if (/SamsungBrowser\//.test(userAgent)) return 'Samsung Internet';
  if (/Firefox\/|FxiOS\//.test(userAgent)) return 'Firefox';
  if (/OPR\//.test(userAgent)) return 'Opera';
  if (/Chrome\/|CriOS\//.test(userAgent)) return 'Chrome';
  if (/Safari\//.test(userAgent)) return 'Safari';
  return null;
}

function aparelhoDoUserAgent(userAgent: string, plataforma: Plataforma): string {
  if (/iPad/i.test(userAgent) || (plataforma === 'ios' && /Macintosh/i.test(userAgent))) return 'iPad';
  if (plataforma === 'ios') return 'iPhone';
  if (plataforma === 'android') return 'Android';
  if (/Windows/i.test(userAgent)) return 'Windows';
  if (/Macintosh/i.test(userAgent)) return 'Mac';
  if (/CrOS/i.test(userAgent)) return 'Chromebook';
  if (/Linux/i.test(userAgent)) return 'Linux';
  return 'Aparelho';
}

/**
 * O nome que aparece em "seus aparelhos": "iPhone · app instalado",
 * "Windows · Edge". É só exibição — o servidor guarda até 80 caracteres e
 * nunca decide nada por ele.
 */
export function descricaoDoAparelho(userAgent: string, plataforma: Plataforma, instalado: boolean): string {
  const aparelho = aparelhoDoUserAgent(userAgent, plataforma);
  if (instalado) return `${aparelho} · app instalado`;
  const navegador = navegadorDoAparelho(userAgent);
  return navegador ? `${aparelho} · ${navegador}` : aparelho;
}

export interface LeituraDoAparelho {
  /** `GET /push/configuracao` respondeu `ativo: true`. */
  servidorAtivo: boolean;
  /** `serviceWorker`, `PushManager` e `Notification` existem neste navegador. */
  temPush: boolean;
  plataforma: Plataforma;
  /** Aberto como app (Tela de Início / instalado), não numa aba. */
  instalado: boolean;
  permissao: PermissaoDoNavegador;
  /** Existe `PushSubscription` neste navegador. */
  inscrito: boolean;
}

export function estadoDoAparelho(leitura: LeituraDoAparelho): EstadoDoAparelho {
  if (!leitura.servidorAtivo) return 'desligado';
  if (!leitura.temPush) {
    // No iPhone, faltar `PushManager` numa aba quer dizer "instale"; instalado e
    // ainda sem ele, é iOS anterior a 16.4.
    return leitura.plataforma === 'ios' && !leitura.instalado ? 'precisa-instalar' : 'sem-suporte';
  }
  if (leitura.permissao === 'denied') return 'bloqueado';
  if (leitura.permissao === 'granted' && leitura.inscrito) return 'ativo';
  return 'inativo';
}

/** Onde religar, quando a permissão foi negada. O site não pode perguntar de novo. */
export function comoReligar(plataforma: Plataforma, instalado: boolean): string {
  if (plataforma === 'ios') {
    return 'Abra os Ajustes do iPhone, toque em Notificações, procure o SAS e ligue "Permitir Notificações".';
  }
  if (plataforma === 'android') {
    return instalado
      ? 'Toque e segure o ícone do SAS, abra "Informações do app" e ligue as notificações.'
      : 'Toque no cadeado ao lado do endereço, abra "Permissões" e permita as notificações.';
  }
  return 'Clique no cadeado ao lado do endereço do site e permita as notificações. Depois recarregue a página.';
}

/**
 * A chave pública VAPID (base64url) no formato que `pushManager.subscribe` pede.
 *
 * Devolve `Uint8Array` sobre um `ArrayBuffer` próprio: o `BufferSource` do
 * TypeScript recente recusa a visão de um `SharedArrayBuffer`.
 */
export function chaveParaBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const preenchido = base64url.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (base64url.length % 4)) % 4);
  const binario = atob(preenchido);
  const bytes = new Uint8Array(new ArrayBuffer(binario.length));
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
  return bytes;
}

/** As duas chaves são a mesma? Usado para descobrir inscrição feita com chave VAPID antiga. */
export function mesmosBytes(a: ArrayBuffer | ArrayBufferView | null | undefined, b: Uint8Array): boolean {
  if (!a) return false;
  const vista = a instanceof ArrayBuffer ? new Uint8Array(a) : new Uint8Array(a.buffer, a.byteOffset, a.byteLength);
  if (vista.length !== b.length) return false;
  for (let i = 0; i < b.length; i++) if (vista[i] !== b[i]) return false;
  return true;
}
