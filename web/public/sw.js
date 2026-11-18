// Service worker do SAS — só os avisos no aparelho (docs/45 §4 e §6.2).
//
// ⚠️ **Não tem handler de `fetch`, e isso é decisão.** Nada passa por aqui no
// carregamento de tela nenhuma: sem cache, não existe "dado velho que parece
// novo" — o motivo de o docs/21 §P4 ter deixado o cache offline de fora. Este
// arquivo recebe o push, mostra a notificação e abre o SAS no toque. Mais nada.
//
// Escrito à mão, sem `vite-plugin-pwa`: o plugin traz o precache do Workbox por
// padrão, que é justamente o cache que não queremos. Fica em `web/public/`, e o
// Vite o copia para a raiz do `dist` sem hash; o nginx o serve com `expires -1`
// para a versão nova valer no próximo carregamento.
//
// O service worker não lê o `sessionStorage` e não precisa de sessão: o
// conteúdo chega cifrado de ponta a ponta (RFC 8291) e o navegador o decifra
// antes de entregar aqui.

const ICONE = '/icones/icone-192.png';
// O ícone pequeno da barra de status do Android: o navegador usa só o canal alfa.
const SELO = '/icones/selo-96.png';

self.addEventListener('install', () => {
  // Sem cache para migrar, a versão nova pode assumir na hora.
  self.skipWaiting();
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(self.clients.claim());
});

/** Mesma regra de `dominio/voltaDoLogin.ts` e de `app/push/envio.py`: só caminho interno. */
function urlInterna(url) {
  if (typeof url !== 'string' || url.length > 512) return false;
  if (!url.startsWith('/') || url.startsWith('//') || url.includes('\\')) return false;
  for (let i = 0; i < url.length; i++) {
    const c = url.charCodeAt(i);
    if (c < 0x20 || c === 0x7f) return false;
  }
  return true;
}

self.addEventListener('push', (evento) => {
  let dados = {};
  try {
    dados = evento.data ? evento.data.json() : {};
  } catch {
    dados = {};
  }
  const titulo = typeof dados.titulo === 'string' && dados.titulo ? dados.titulo : 'SAS';
  const opcoes = {
    body: typeof dados.corpo === 'string' ? dados.corpo : '',
    icon: ICONE,
    badge: SELO,
    lang: 'pt-BR',
    data: { url: urlInterna(dados.url) ? dados.url : '/' },
  };
  if (typeof dados.tag === 'string' && dados.tag) {
    // Mesma tag substitui a anterior em vez de empilhar; `renotify` faz a
    // substituta tocar de novo.
    opcoes.tag = dados.tag;
    opcoes.renotify = true;
  }
  // SEMPRE mostra alguma coisa. Push sem notificação visível é proibido pelo
  // `userVisibleOnly`, e o Safari revoga a inscrição de quem recebe sem mostrar.
  evento.waitUntil(self.registration.showNotification(titulo, opcoes));
});

self.addEventListener('notificationclick', (evento) => {
  evento.notification.close();
  const pedido = evento.notification.data && evento.notification.data.url;
  const url = urlInterna(pedido) ? pedido : '/';

  evento.waitUntil(
    (async () => {
      const janelas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      for (const janela of janelas) {
        if (new URL(janela.url).origin !== self.location.origin) continue;
        // Uma aba do SAS já aberta ainda tem o `sessionStorage`: a pessoa cai
        // direto na tela, sem login.
        await janela.focus();
        try {
          await janela.navigate(url);
        } catch {
          // Aba que este worker ainda não controla não aceita `navigate`; o
          // foco já a trouxe para a frente.
        }
        return;
      }
      // Sem aba aberta, a nova chega SEM sessão (ela é por aba): a
      // `RotaProtegida` manda para `/login?proximo=<url>` e o login devolve a
      // pessoa para cá (`App.tsx`).
      await self.clients.openWindow(url);
    })(),
  );
});
