# 45 — Notificação push: a capacidade

> **Estado: IMPLEMENTADO, na `main` desde o PR #128, fora de produção**
> *(18/11/2026)*. Escrito contra a `main` em `ca5e120` (migrations até a 0080);
> a implementação traz a **0081**. O que foi feito, o que foi verificado e o que
> falta está no **§14**: leia esse antes do resto. Para ligar em produção: **§15**.
>
> **Atualização (19/11/2026): o primeiro evento existe — a missão do dia, no
> §16.** Todo dia às 15h, o aluno com aparelho ativo recebe o assunto de hoje.
> Branch `feat/push-missao-do-dia`, migration **0082**, fora de produção. A
> capacidade (o PR #128, já na `main`) também **ainda não foi para produção**:
> ligar as duas é o §15.
>
> **Escopo do §1 ao §15: só a capacidade.** Inscrever um aparelho, guardar a
> inscrição, mandar, receber com a tela bloqueada, tocar e cair na tela certa.
> O §9 é o contrato que cada evento preenche, e o §16 é o primeiro a preenchê-lo.
>
> ⚠️ Três pontos do primeiro desenho mudaram na implementação, e o texto abaixo
> já está corrigido:
> - a reconciliação de cada abertura **só confirma, nunca cria** (§6.1);
> - a tabela `envio_push` ficou fora da capacidade (§5.2) e **entrou com o
>   primeiro evento** (§16.3), como a trava de "uma vez por dia";
> - a cifra é **nossa**, sobre o `cryptography`, sem dependência nova (§5.4).

---

## 0 · O que existia antes

| Peça | Estado em 18/11 | Onde |
|---|---|---|
| `manifest.webmanifest`, ícone, `theme-color` | **não existia**. A P4 do plano mobile nunca começou, e não havia nem `web/public/` | [21 §P4](21-plano-mobile.md), [19 bloco C](19-roadmap.md) |
| Service worker | **não existia**, nem para cache. O cache offline ficou fora de propósito ("dado velho que parece novo") | [21 §P4](21-plano-mobile.md) |
| Sessão | JWT Bearer no `sessionStorage`, **por aba**. Aba nova chega deslogada, e o login devolve a pessoa para onde ela ia (`?proximo=`) | [App.tsx](../web/src/App.tsx) `RotaProtegida`, [sessao.ts](../web/src/servicos/sessao.ts) |
| Login do aluno | **só pelo Canvas (SSO)**. Não existe senha de aluno | [Porta.tsx](../web/src/telas/Login/Porta.tsx) |
| Canal de aviso | e-mail pelo SES, no motor de lembretes. `regra_lembrete.canal` e `disparo.canal` têm `CHECK (canal IN ('email'))` desde a 0019, que já previa alargar | [app/lembretes/](../api/app/lembretes/) |
| Tipos de sessão | `aluno`, `coordenador`, `cantina`. `administrador` é papel **dentro** de `coordenador` | [auth.py](../api/app/auth.py) `TIPOS_DE_SESSAO` |
| CSP de produção | `default-src 'self'`. `worker-src` e `manifest-src` herdam `'self'`, então **a CSP não muda**. O POST para o serviço de push sai do servidor e não do browser, então `connect-src` também fica como está | [infra/vps/nginx.conf](../infra/vps/nginx.conf) |

---

## 1 · A decisão que este plano reabre

O [docs/20 §1](20-mobile.md) escolheu a rota A (web responsiva + PWA) e disse
que push "é o único motivo real" para a rota B (Capacitor). Também disse que,
se push virasse requisito, a rota seria B.

**Essa premissa não vale mais.** Web Push é padrão (RFC 8030, 8291 e 8292) e
funciona no próprio `portalsas.online`:

| Plataforma | Recebe push web? | Condição |
|---|---|---|
| Android: Chrome, Samsung Internet, Firefox, Edge | sim | numa aba mesmo, sem instalar |
| Desktop: Chrome, Edge, Firefox | sim | com o navegador aberto, mesmo em segundo plano |
| macOS: Safari 16 ou mais novo | sim | numa aba, sem instalar |
| iPhone/iPad: iOS 16.4 ou mais novo | sim | **só com o site instalado na Tela de Início**, e a permissão é pedida de dentro do app instalado |
| iOS anterior a 16.4 | não | — |

**Decidido (18/11): rota A**, com Web Push padrão e VAPID. Firebase no site,
OneSignal e afins foram descartados. Por baixo eles usam o mesmo Web Push,
então não acrescentam capacidade nenhuma, e põem um terceiro na página. O preço
da rota A está no iPhone: o aluno precisa instalar o site antes de receber
qualquer aviso, e esse funil existe só lá. Nenhuma ferramenta contorna isso: no
iPhone, só app instalado notifica.

**O que reabre a rota B:** a medição do §8 mostrar uma adesão de iPhone menor
do que os eventos escolhidos precisam. Nada desta rota se perde se isso
acontecer: o backend da §5 serve também a um app nativo, como um segundo meio
de entrega.

---

## 2 · LGPD: o que sai do servidor e para onde

Web Push sempre passa pelo serviço de push do fabricante do navegador: FCM
(Google) no Chrome e no Android, APNs (Apple) no Safari, *autopush* (Mozilla)
no Firefox e WNS (Microsoft) no Edge. Não há como evitar. Também **não é
terceiro na página**, no sentido da armadilha 7 do [CLAUDE.md](../CLAUDE.md):
nenhum script, SDK ou asset de fora é carregado, porque quem fala com o serviço
é o próprio navegador.

| O fabricante **vê** | O fabricante **não vê** |
|---|---|
| o endpoint (id opaco daquela inscrição naquele aparelho), o tamanho do payload, os headers `TTL`, `Urgency` e `Topic`, o horário e o IP do nosso servidor | o conteúdo. O payload é cifrado de ponta a ponta (RFC 8291, `aes128gcm`) com uma chave que só o aparelho e nós temos |

Regras que passam a valer:

1. **Só a API padrão.** Firebase JS SDK, OneSignal e afins são exatamente o
   "SDK de push de fornecedor" que o [docs/20 §6](20-mobile.md) proíbe.
2. **Header vai em claro.** `Topic` e qualquer outro header nunca levam dado de
   aluno, só slug genérico (`resultado-simulado`).
3. **O `sub` do VAPID é `https://portalsas.online`**, não o e-mail de alguém.
   É o contato que o fabricante usa se o nosso servidor se comportar mal, e
   ele chega à Google e à Apple.
4. **A tela bloqueada é pública.** O texto da notificação não leva nota,
   posição, desempenho nem nome de outro aluno. Ele diz que há algo, não o quê:
   "Saiu o resultado do P3. Toque para ver." *(Regra padrão. Cada evento a
   confirma no §9.)*
5. **A inscrição é dado pessoal.** Ela é apagada em cascata com o dono (§5.2),
   o que já resolve a parte de push do caminho de eliminação ([19 bloco G](19-roadmap.md)).
6. **Toda inscrição nasce de um clique** (§6.1). Nenhum código reinscreve
   ninguém sozinho, e o clique em "Ativar" é também o registro do
   consentimento, na trilha de auditoria (`push_aparelho_ativado`).

---

## 3 · Como as peças se encaixam

```
 APARELHO                          portalsas.online                     FABRICANTE
 ────────                          ────────────────                     ──────────
 clique em "Ativar"
   ├─ pushManager.subscribe(chave pública VAPID) ──────────────────────►  cria endpoint
   └─ POST /api/push/inscricoes {endpoint, p256dh, auth} ──► inscricao_push

 cada abertura do casco
   └─ POST /api/push/inscricoes/confirmar ──► só atualiza o que já é da pessoa

                         (mais tarde, quando um evento quiser)
                                   envio.enviar_para_dono(dono, notificação)
                                     └─ cifra + assina ── POST endpoint ──►  FCM / APNs / …
 sw.js  ◄────────────────────────────────────────────────────────────────  entrega
   └─ showNotification ─► toque ─► foca a aba aberta e navega
                                   ou abre aba nova ─► /login?proximo=… ─► tela
```

O service worker não lê o `sessionStorage` e não precisa de sessão. Ele só
mostra o que chegou. A sessão só é exigida ao **inscrever** e ao **abrir** o
destino, e o segundo caso já está coberto pelo `?proximo=`.

---

## 4 · Fase 0: PWA instalável

É a P4 do [docs/21](21-plano-mobile.md), que nunca tinha sido feita. No iPhone é
pré-requisito do push. No Android não é, mas são os mesmos arquivos, e ela tem
valor sozinha: o aluno abre o SAS pelo ícone, sem barra de navegador.

| O quê | Como ficou |
|---|---|
| [`web/public/manifest.webmanifest`](../web/public/manifest.webmanifest) | `id`, `start_url` e `scope` em `/`, `display: standalone`, `name: "Portal SAS"`, `short_name: "SAS"` (§12, decisão 3), fundo e tema `#ffffff` |
| [Ícones](../web/public/icones/) | 192, 512, maskable 512 (o logotipo dentro da zona segura de 80%), `apple-touch-icon` 180 e o **selo** monocromático de 96 px da barra de status do Android. Gerados a partir de `web/assets/ari-logo-branca.png` sobre o azul da marca (`#1b3f8b`). O `ari-logo.png` não serve: ele traz junto o selo do centenário com o retrato, que vira borrão em ícone pequeno |
| [`index.html`](../web/index.html) | `<link rel="manifest">`, ícone, `apple-touch-icon`, `apple-mobile-web-app-title`, dois `theme-color` (claro e escuro) e o título **"SAS · Colégio Ari de Sá"**: o antigo, "SAS · coordenação ITA/IME", ia para a tela inicial do aluno (docs/21 §P4) |
| [`web/public/sw.js`](../web/public/sw.js) | **escrito à mão, sem `vite-plugin-pwa`.** O plugin traz o precache do Workbox por padrão, que é justamente o cache que o docs/21 deixou fora. Este arquivo tem só `push` e `notificationclick` e **nenhum handler de `fetch`**: nada é cacheado e nenhum dado velho aparece como novo |
| Registro | `registrarServiceWorker()` em [main.tsx](../web/src/main.tsx), depois do `load`, em toda rota, inclusive no login |
| nginx (`web/nginx.conf` **e** `infra/vps/nginx.conf`) | `location = /sw.js` e `location = /manifest.webmanifest` com `try_files $uri =404`, `expires -1` e o `types` do manifest. **Nenhum `add_header`**: ele anularia a CSP e o HSTS herdados do `server`. Verificado (§14) |

### 4.1 · ⚠️ O portão: login do aluno no app instalado do iPhone

**Ainda não verificado, e é o maior risco do plano.** O aluno entra só pelo
Canvas. No iPhone, um app da Tela de Início abre navegação para fora do próprio
escopo (o domínio do Canvas) numa camada de navegador por cima do app. Não
sabemos se, na volta do OAuth, o token cai no `sessionStorage` **do app
instalado** ou fica preso nessa camada.

- **Se cair no app:** segue como está.
- **Se não cair:** o iPhone fica sem push até o login no app instalado ser
  resolvido. Esse é um problema próprio, com plano próprio (por exemplo:
  parear o app instalado com um código mostrado numa sessão já logada no
  Safari). Android e desktop seguem sem esperar.

Junto vem uma consequência que já existia, mas que o push deixa visível: como a
sessão mora no `sessionStorage`, **cada abertura a frio do app instalado pede
login de novo**. Tocar numa notificação com o app fechado passa pelo Canvas
sempre. Com a sessão do Canvas viva, são dois redirecionamentos.

**Custo do portão:** uns 15 minutos com um iPhone real, contra um ambiente com
este branch no ar. O MCP `mobile` não enxerga aparelho nenhum (falta o Xcode,
ver [20 §2](20-mobile.md)), então o teste é manual.

---

## 5 · Fase 1: backend

### 5.1 · Chaves VAPID

- **Um par P-256, gerado uma vez** por
  [`api/scripts/gerar_chave_vapid.py`](../api/scripts/gerar_chave_vapid.py). O
  script grava a privada num arquivo 0600 (O_EXCL, como o `criar_token_mcp`) e
  imprime só a pública. A privada vai para o `.env` como
  `PUSH_VAPID_CHAVE_PRIVADA`. A pública é **derivada da privada na subida da
  API**: uma variável só, então não existe par descasado.
- ⚠️ **Trocar a chave mata todas as inscrições.** Cada inscrição fica amarrada
  à chave pública com que nasceu, e todo aparelho teria que reativar. A chave é
  tratada como permanente, com backup junto dos outros segredos, e **não** é
  `[gerado]` no `.env.example`.
- `PUSH_VAPID_CONTATO`, com default `https://portalsas.online` (§2, regra 3).
- **Sem a variável, o push fica desligado e a API sobe**, como o SES faz hoje.
  O `deploy.sh` avisa. **Com a variável preenchida mas ilegível,
  `_validar_configuracao` recusa subir**, e também com contato que não seja
  `https://`/`mailto:` ou que aponte para localhost (armadilha 3: o guard falha
  fechado).

### 5.2 · Schema: migration [`0081_inscricao_push`](../api/migrations/0081_inscricao_push.sql) (+ `.down.sql`)

```sql
CREATE TABLE inscricao_push (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id                uuid REFERENCES aluno(id) ON DELETE CASCADE,
    usuario_coordenacao_id  uuid REFERENCES usuario_coordenacao(id) ON DELETE CASCADE,
    CONSTRAINT inscricao_push_um_dono
        CHECK (num_nonnulls(aluno_id, usuario_coordenacao_id) = 1),
    endpoint                text NOT NULL UNIQUE,
    chave_p256dh            text NOT NULL,
    chave_auth              text NOT NULL,
    plataforma              text NOT NULL CHECK (plataforma IN ('ios', 'android', 'desktop', 'outra')),
    descricao_aparelho      text,
    criada_em               timestamptz NOT NULL DEFAULT now(),
    vista_em                timestamptz NOT NULL DEFAULT now(),
    ultimo_envio_ok_em      timestamptz,
    falhas_seguidas         int NOT NULL DEFAULT 0,
    ultimo_status_http      int,
    ultimo_erro             text
);
```

- **Duas FKs de verdade, e não (tipo, id) solto:** o `ON DELETE CASCADE` dá a
  eliminação da LGPD de graça, e um id de coordenação nunca é lido como de aluno.
- **`endpoint UNIQUE`:** o mesmo navegador gera o mesmo endpoint para quem se
  inscrever nele, e com isso a inscrição muda de dono num computador
  compartilhado, em vez de existirem duas.
- **Sem tabela `envio_push`.** O primeiro desenho previa um log por envio. Para
  a capacidade, que só manda teste, ele seria uma tabela crescendo sem leitor
  (armadilha 2). O "o aviso chegou?" fica em `ultimo_status_http`,
  `ultimo_erro` e `ultimo_envio_ok_em`. O log por evento entra junto do
  primeiro evento, se ele precisar. *(Precisou: a 0082 trouxe a `envio_push`
  com a missão do dia, mais pela idempotência que pelo log. Ver §16.3.)*
- O MCP não lê esta tabela, e não deve: tabela nova nasce invisível ao
  `sas_leitura`.
- **Depois do `migrate up`, `docker compose restart postgrest`** (armadilha 1).

### 5.3 · Rotas: [`api/app/routes/push.py`](../api/app/routes/push.py)

| Rota | Quem | O quê |
|---|---|---|
| `GET /push/configuracao` | qualquer sessão | `{ativo, chavePublica}`. A cantina recebe `ativo: false`, e a seção não aparece |
| `POST /push/inscricoes` | aluno, coordenação | **só o clique em "Ativar".** Upsert por `endpoint`: se o endpoint já é de outro dono, **ele muda de dono** |
| `POST /push/inscricoes/confirmar` | idem | a reconciliação de cada abertura: atualiza `vista_em` e as chaves **do que já é da pessoa**, e devolve `registrada: false` para o resto. **Nunca cria, nunca transfere** (§6.1) |
| `GET /push/inscricoes` | idem | "seus aparelhos", sem endpoint e sem chaves na resposta |
| `DELETE /push/inscricoes/{id}` | o dono | revoga um aparelho da lista, inclusive outro que não este. Id que não é uuid dá 404, não 500 |
| `POST /push/inscricoes/remover` | o dono | "Desativar neste aparelho" e o Sair. POST com o endpoint **no corpo**, porque na query ele iria para o log do nginx |
| `POST /push/teste` | o dono | manda o aviso de teste para **os aparelhos do próprio dono** e para mais ninguém. Teto de 5 por hora, na memória do processo (exato com `UVICORN_WORKERS=1`) |

- **Fail-closed por tipo de sessão.** `_dono_da_sessao(user)`, no molde de
  `_entidade_do_usuario` da foto: `aluno` resolve para `aluno_id`,
  `coordenador` para `usuario_coordenacao_id`, e **qualquer outro tipo recebe
  403**, inclusive a cantina e o aluno sem `aluno_id` no token. É a lição do
  [docs/38 §1.1](38-plano-cantina.md) e do PR #7.
- **O dono vem só do JWT.** Id de dono no corpo da requisição não é aceito.
- **Os handlers são `def`**, não `async def` (api/CLAUDE.md, "Convenções").
- **Auditoria:** `push_aparelho_ativado` (inscrição nova ou troca de dono) e
  `push_aparelho_removido`, no canal `acesso`. Nunca o endpoint nem as chaves.
- ⚠️ **SSRF: o endpoint é uma URL que o cliente manda e que o servidor chama com
  POST.** Sem filtro, uma sessão autenticada registraria
  `http://postgrest:3000/...` e o servidor faria POST na rede interna, onde o
  papel anônimo do PostgREST tem acesso total ao schema (armadilha 4).
  [`app/push/endpoints.py`](../api/app/push/endpoints.py) aceita só `https`,
  porta 443, sem credencial na URL, e uma lista fechada de hosts:
  `fcm.googleapis.com`, `web.push.apple.com`,
  `updates.push.services.mozilla.com` e `*.notify.windows.com`. A conferência
  roda na rota **e de novo antes de cada POST**, e o envio não segue
  redirecionamento.

### 5.4 · Envio: [`api/app/push/`](../api/app/push/)

| Módulo | O quê |
|---|---|
| `chaves.py` | lê a chave, deriva a pública, base64url |
| `cifra.py` | o corpo `aes128gcm` (RFC 8188 + RFC 8291) |
| `vapid.py` | o cabeçalho `Authorization: vapid t=…, k=…` (RFC 8292), JWT ES256 com `aud` = origem do endpoint, validade de 12 h |
| `endpoints.py` | a lista fechada do §5.3 |
| `envio.py` | `Notificacao`, `Dono`, `enviar_para_dono`, `enviar_para_inscricoes` e a leitura das respostas |

- **Sem dependência nova.** O protocolo cabe em três primitivas que o
  `cryptography` (já no projeto, via `python-jose`) tem prontas: ECDH P-256,
  HKDF-SHA256 e AES-128-GCM. A composição é conferida **byte a byte** contra o
  vetor do Apêndice A da RFC 8291, e o próprio Chrome a decifrou na
  verificação (§14). `pywebpush` traria `requests` e mais três pacotes para
  fazer o mesmo.
- **Síncrono de propósito**, com os POSTs em paralelo num pool de threads
  (concorrência 10) e as escritas no banco **depois**, na thread de quem chamou:
  o cliente PostgREST divide uma conexão HTTP/2, e um GOAWAY numa stream derruba
  as outras. Quem chamar de um `async def` usa `asyncio.to_thread`.
- **O que cada resposta do fabricante significa:**

  | Status | Leitura | Ação |
  |---|---|---|
  | 2xx | entregue ao fabricante | zera `falhas_seguidas`, grava `ultimo_envio_ok_em` |
  | 404, 410 | a inscrição morreu (permissão revogada ou app desinstalado) | **apaga** a inscrição |
  | 429, 5xx, rede | transitório | conta falha. Com 10 seguidas e nada entregue em 7 dias, apaga. **Não re-tenta aqui**: quem re-tenta é o chamador |
  | outro 4xx (400, 403, 413) | **erro nosso**: chave, assinatura ou tamanho. Na Apple, 403 `BadJwtToken` aponta para `sub` ou chave errados | registra e loga alto, **e nunca conta contra o aparelho**. Com a chave errada, TODO envio dá 403, e contar isso apagaria a inscrição de todo mundo em dez envios |

- **`Notificacao` valida o que dá para validar:** `tipo` e `tag` são slugs,
  título de até 80 caracteres, corpo de até 200, `url` **só interna** (mesma
  regra de `voltaDoLogin.ts`, conferida de novo no service worker), TTL até 28
  dias, `Topic` até 32 caracteres base64url. A regra 4 do §2 (nada de nota na
  tela bloqueada) não se valida por código: é contrato de quem chama.

### 5.5 · Testes: [`api/tests/test_push.py`](../api/tests/test_push.py), 88 casos

Cobrem a cifra contra o vetor da RFC 8291 e a ida e volta, o JWT VAPID
conferido com a chave pública, a lista de hosts (incluindo `postgrest:3000`,
`169.254.169.254`, sufixo sem ponto e porta trocada), a leitura de cada status,
o envio com fabricante falso (decifrado do lado do "aparelho"), as sete rotas
(dono só do JWT, cantina barrada, troca de dono, confirmar que não cria nem
transfere, revogar só o que é seu, teto do teste) e a guarda de subida.

---

## 6 · Fase 2: front

### 6.1 · [`web/src/servicos/avisosNoAparelho.ts`](../web/src/servicos/avisosNoAparelho.ts)

- **`lerAparelho(config)`** decide o estado. Com permissão concedida e
  inscrição local feita com a chave atual, chama `/push/inscricoes/confirmar`.
  ⚠️ **Essa é a reconciliação de cada abertura, e ela nunca cria.** No primeiro
  desenho, ela fazia upsert, e isso desfaria três decisões da pessoa sem ela
  saber:
  - o aparelho revogado na lista de outro aparelho voltaria sozinho;
  - quem entrasse depois num computador compartilhado herdaria os avisos de
    quem saiu, sem ter pedido;
  - um "Desativar" mal sincronizado voltaria na abertura seguinte.

  Por isso o `pushsubscriptionchange` também não é usado: além de só o Firefox
  dispará-lo com confiança, ele reinscreveria sem ninguém pedir. Uma inscrição
  que o navegador trocou sozinho aparece como "Ativar" de novo, que é a verdade.
- **`pedirPermissao()` roda dentro do clique, antes de qualquer `await`**, e a
  promessa vai pronta para a mutação. O Safari só mostra o pedido com o gesto
  do usuário em andamento, e a mutação do React Query roda depois de um `await`
  interno.
- **`ativar()`** espera o service worker ativo (prazo de 15 s), troca uma
  inscrição feita com chave antiga e chama o `subscribe`, com **prazo de 30 s**.
  Na primeira vez de um perfil, o Chrome abre a conexão com o FCM e isso já
  passou de 15 s na verificação. Estourar o prazo não perde nada: o segundo
  clique reaproveita a inscrição que tiver chegado.
- **`desativar()`** cancela no navegador primeiro e depois no servidor. Se o
  servidor falhar, a linha que sobrar leva 410 no próximo envio e se apaga.
- **`desativarAoSair()`**: o **Sair** dos dois cascos desativa neste aparelho
  antes de encerrar, com prazo de 2,5 s e erro engolido. Fechar a aba não é
  sair, e o 401 de sessão vencida também não.
- A reconciliação roda ao montar o casco: `CascoAluno` e o `Conta` do rail
  chamam `useEsteAparelho`.

### 6.2 · [`web/public/sw.js`](../web/public/sw.js)

- **`push`** lê o JSON e mostra a notificação com ícone, selo, `tag` (com
  `renotify`) e `data.url`. **Sempre mostra alguma coisa**: push silencioso é
  proibido pelo `userVisibleOnly`, e o Safari revoga a inscrição de quem recebe
  sem mostrar.
- **`notificationclick`** procura uma aba do SAS aberta: se acha, faz `focus()`
  e `navigate(url)`, e a pessoa cai direto na tela (aquela aba ainda tem o
  `sessionStorage`). Se não acha, abre uma aba nova, que cai no
  `/login?proximo=url` e volta.
- `skipWaiting` + `clients.claim`: sem cache para migrar, a versão nova assume
  na hora.

### 6.3 · Telas

- **A peça é uma só**,
  [`componentes/perfil/AvisosNoAparelho.tsx`](../web/src/componentes/perfil/AvisosNoAparelho.tsx),
  com o CSS em [`styles/avisos.css`](../web/styles/avisos.css), lendo os papéis
  `--sas-*`. O que muda por casco é a classe do botão.
- **Aluno:** seção "Avisos neste aparelho" na folha "Minha conta". A folha
  passou de `espiada` (34dvh) para `meio` (62dvh): com a seção, o "Sair da
  conta" ficava abaixo da dobra a 390px.
- **Coordenação:** um sino no rodapé do rail, ao lado do Sair, abre um
  `Dialogo` com a mesma peça. ⚠️ **No celular o sino some**: abaixo de 760px o
  rail vira barra inferior de seis alvos e a conta encolhe para o Sair, então
  um sétimo alvo ali arriscaria a barra. A coordenação usa o notebook.
- **Estados:** `inativo` (botão "Ativar avisos"), `ativo` (selo, "Mandar um
  teste" e "Desativar"), `precisa-instalar` (iPhone numa aba: os três passos
  da Tela de Início, sem botão), `bloqueado` (onde religar, por plataforma),
  `sem-suporte`. Com o servidor sem chave, a seção **não existe**.
- **"Seus aparelhos"** lista o nome montado do user agent ("Mac · Chrome",
  "iPhone · app instalado"), marca "este aparelho" e oferece "Remover" nos
  outros.
- **Nenhum pedido de permissão fora desta seção.** O convite no contexto ("quer
  ser avisado quando sair a nota?") é decisão de evento (§9).
- Domínio puro com teste:
  [`dominio/avisosNoAparelho.ts`](../web/src/dominio/avisosNoAparelho.ts)
  (plataforma, com o iPad que se diz Mac; descrição; máquina de estados; chave
  para bytes).

---

## 7 · Fase 3: verificação em aparelho

| Onde | Como | Estado |
|---|---|---|
| Chrome no Mac | puppeteer-core contra um stack isolado | ✅ **feito** (§14) |
| Build de produção atrás do `infra/vps/nginx.conf` | nginx real, certificado autoassinado | ✅ **feito** (§14) |
| Android real | Chrome numa aba e depois instalado | ⬜ falta |
| iPhone real, iOS 16.4 ou mais novo | instalado | ⬜ **falta, e é o portão do §4.1** |
| Safari no macOS | numa aba | ⬜ falta |
| Revogação pelo sistema | bloquear nas configurações do aparelho e mandar um teste | ⬜ falta (o 410 → apaga está coberto em teste) |

Nunca use aparelho em nuvem nem conta de aluno real: só a conta de aluno de
teste do Canvas (regra do MCP `mobile` no [CLAUDE.md](../CLAUDE.md)).

**Pronto quando:** em cada linha acima, a pessoa ativa, aperta "Mandar um
teste", recebe com a tela bloqueada, toca e cai na tela certa (passando pelo
login se a sessão morreu). Revogada a permissão, o próximo envio apaga a
inscrição.

---

## 8 · O que medir depois que entrar

- inscrições ativas por plataforma;
- alunos com pelo menos um aparelho ativo, sobre os alunos com acesso;
- dos iPhones, quantos instalaram (`descricao_aparelho` termina em "app
  instalado").

É esse número que diz se a rota A basta (§1). Uma tool do MCP da coordenação,
ou uma linha no painel de administração, resolve. Não precisa de tela nova.

---

## 9 · O contrato dos eventos (o que vem depois)

Quando um evento for escolhido, ele responde a estas oito perguntas antes de
virar código. A porta de entrada é `envio.enviar_para_dono(cliente, dono,
Notificacao(...))`, ou, para evento de turma, `registro.reservar` +
`registro.disparar` (§16.3). **O primeiro evento a responder, e o modelo para os
próximos, é a missão do dia: §16.1.**

1. **Quem recebe?** Aluno, coordenação, e quais deles.
2. **Quando sai?** Na hora, por chamada direta (por exemplo, no fim do sync do
   Canvas, via `asyncio.to_thread`), ou agendado, pelo motor de lembretes. No
   segundo caso, `canal` ganha `'push'` numa migration que alarga o `CHECK` da
   0019, e `disparo.destinatario`, que hoje é um e-mail, passa a precisar do
   dono.
3. **Qual o texto?** Dentro da regra 4 do §2.
4. **Vale até quando?** O TTL: "o simulado é amanhã" não serve depois do
   simulado. E qual a urgência.
5. **Agrupa?** A `tag`: o aviso novo do mesmo tipo substitui o anterior?
6. **Tem horário de silêncio?** Proposta: nada entre 22h e 7h (BRT), salvo
   urgente. É decisão de produto.
7. **O aluno pode desligar só este tipo?** Preferência por tipo pede tabela
   nova, que só se justifica quando existir o segundo tipo.
8. **Substitui o e-mail ou soma?**

E, se o evento for para muita gente: registrar o envio por evento (a tabela
que saiu do §5.2) e **nunca** rodar o fan-out dentro da requisição de quem
disparou.

---

## 10 · Fora do escopo

- **Qualquer evento** além da missão do dia (§16).
- **Mensagem livre da coordenação para os alunos.** É um vetor de abuso contra
  menores. Se vier, vem com auditoria e aprovação, num plano próprio.
- Cache offline, que continua fora pelo mesmo motivo do docs/21 §P4.
- Badge no ícone (Badging API), botões de ação na notificação, imagem.
- *Declarative Web Push* do Safari 18.4: dispensável enquanto houver service worker.
- Capacitor (§1).

---

## 11 · Ordem e tamanho

O plano previa a Fase 0 num PR próprio, antes do backend. Na implementação,
as Fases 0 a 2 entraram juntas no branch `feat/notificacao-push`, porque a
verificação de ponta a ponta precisava de tudo. A Fase 3 em aparelho real
(§7) e o portão do iPhone (§4.1) continuam pendentes.

---

## 12 · Decisões

| # | Pergunta | Como ficou |
|---|---|---|
| 1 | Web Push no PWA (rota A) em vez de Capacitor | **A**, decidido pelo dono em 18/11. Reabrir com a medição do §8 |
| 2 | Quem pode receber já na capacidade | **aluno e coordenação**; a cantina recebe 403 até haver evento para ela *(padrão adotado, a confirmar)* |
| 3 | Nome na tela inicial | **`name: "Portal SAS"`, `short_name: "SAS"`**, título da aba "SAS · Colégio Ari de Sá" *(padrão adotado, a confirmar)* |
| 4 | A regra de conteúdo da tela bloqueada (§2, regra 4) | adotada como padrão; cada evento a confirma |
| 5 | Sair desativa o push neste aparelho | **sim** (computador da escola é compartilhado) *(padrão adotado, a confirmar)* |
| 6 | Logo em vetor | dispensado: os ícones saíram de `ari-logo-branca.png` (312×157), que cabe sem ampliar no 512. Com o vetor, dá para refazê-los mais nítidos |
| 7 | Primeiro evento | **a missão do dia**, pedido do dono em 19/11 ("todos os dias"). §16 |
| 8 | Horário da missão | **15h** de Fortaleza, decidido pelo dono em 19/11 (a primeira proposta era 18h). Muda numa linha do `crontab-sas` |
| 9 | Quem já mexeu no assunto de hoje recebe? | **não**: cobrar a missão de quem já está nela ensina a ignorar os avisos *(padrão adotado, a confirmar)* |
| 10 | Desligar só a missão | **ainda não**: com um tipo só, "Desativar" é o desligar dela. A preferência por tipo entra com o segundo evento (§9, item 7) |

---

## 13 · Documentos que mudaram junto

- [docs/20 §1](20-mobile.md): push não exige mais Capacitor.
- [docs/21 §P4](21-plano-mobile.md): feita aqui, com o SW à mão no lugar do
  `vite-plugin-pwa`.
- [docs/19, bloco C](19-roadmap.md): aponta para cá.
- [CLAUDE.md](../CLAUDE.md) e [api/CLAUDE.md](../api/CLAUDE.md): o 45 no mapa,
  o `app/push/` nos módulos e a armadilha da chave VAPID.

---

## 14 · O que foi feito e verificado *(18/11/2026)*

**Portões locais:**

| Portão | Resultado |
|---|---|
| `pytest tests/` | 3408 passaram, 34 pulados; `test_push.py` traz 88 |
| `ruff check .` | limpo |
| `npm test` | 1084 passaram (o `avisosNoAparelho.test.ts` é novo) |
| `npm run typecheck` | limpo |
| `npm run lint` | nenhum aviso nos arquivos tocados. Os 29 avisos do projeto já estavam na `main` |
| `npm run build` | ok; `dist/` traz `sw.js`, `manifest.webmanifest` e `icones/` na raiz |
| Migration 0081 | aplicou num Postgres 16 limpo, depois das 80 anteriores. `down` apaga e `up` recria |

**No navegador:** um stack isolado, sem tocar no de desenvolvimento: Postgres e
PostgREST próprios em outras portas, a API e o Vite rodando da worktree, uma
chave VAPID só de teste, e o Chrome do Mac por puppeteer-core com perfil
descartável. Passos e resultados:

| Passo | Resultado |
|---|---|
| Service worker | registrado e ativo no escopo `/`; manifest no `<head>` |
| Coordenação: sino → "Ativar avisos" | inscrição em `fcm.googleapis.com`, linha no banco, "Mac · Chrome · este aparelho" na lista, `push_aparelho_ativado` na auditoria |
| "Mandar um teste" | FCM respondeu **201**. O `chrome://gcm-internals` registrou `Data msg received` (572 bytes, da nossa chave VAPID) e **nenhuma falha de decifração**, ou seja, o Chrome decifrou o nosso `aes128gcm` |
| Notificação | `getNotifications()` devolveu o aviso com título, texto, `tag`, `url: "/"`, ícone e selo |
| "Desativar" e Sair | os dois apagam a inscrição do navegador e a do servidor |
| Aluno a 390px, Android | "Ativar avisos" com 50 px de altura, sem transbordo, "Sair da conta" à vista |
| Aluno a 390px, iPhone numa aba (sem `PushManager`) | os três passos da Tela de Início, sem botão |
| Coordenação a 390px | sino escondido, sem transbordo |
| Build atrás do `infra/vps/nginx.conf` real (TLS autoassinado) | `/sw.js` (`application/javascript`) e `/manifest.webmanifest` (`application/manifest+json`) com `no-cache` **e** com CSP, HSTS e `X-Frame-Options`; service worker ativo e **zero** violação de CSP no console |

**Achados da verificação:**

- **Um flag padrão do puppeteer desliga o serviço de push**: o `subscribe`
  nunca responde. Sem os flags padrão, responde em ~1,5 s. Quem for repetir a
  verificação usa `ignoreDefaultArgs: true`. No `headless` o push chega, mas a
  notificação não é exibida: para ver a notificação, o Chrome precisa de janela.
- **O prazo do `subscribe` subiu para 30 s**: num perfil novo, a primeira
  conexão com o FCM passou de 15 s.

**O que NÃO foi verificado:**

- **Nenhum aparelho real**: Android, iPhone e Safari estão no §7.
- **O toque na notificação** (`notificationclick`): o puppeteer não clica em
  notificação do sistema. A lógica (focar a aba aberta, senão abrir pelo
  `/login?proximo=`) foi lida, não exercitada.
- **O portão do iPhone** (§4.1).

---

## 15 · Como ligar em produção

1. **Gerar a chave uma vez**, na sua máquina ou no servidor:
   `cd api && ./.venv/bin/python -m scripts.gerar_chave_vapid`. Copiar a linha
   `PUSH_VAPID_CHAVE_PRIVADA=…` do arquivo que ele grava para o `.env` **do
   VPS** (o `deploy.sh` preserva o `.env` existente e não acrescenta chave
   nova), guardar no cofre junto dos outros segredos e apagar o arquivo.
2. **Deploy com migration:** `./infra/vps/deploy.sh --migrar` (aplica a 0081
   e, com a missão do dia, a 0082).
3. **Conferir:** entrar como coordenação no notebook, sino → "Ativar avisos" →
   "Mandar um teste". Sem a chave, o sino não aparece, e o `deploy.sh` avisa.
4. **Reinstalar o crontab.** O `deploy.sh` leva o arquivo para o VPS (o rsync
   manda a árvore inteira), mas **não o instala**: no VPS, como o usuário
   `sas`, `crontab /opt/sas/infra/vps/crontab-sas` e `crontab -l | grep missao`
   para conferir. Sem isto, a missão do dia nunca sai, e nada avisa.
5. **Ver a missão sair** sem esperar as 15h (precisa ser entre 7h e 22h):
   `/opt/sas/infra/vps/cron-sas.sh /push/eventos/missao-do-dia 120` no VPS e
   `tail -1 /var/log/sas/cron.log`. Isso gasta a vaga do dia: o disparo das 15h
   vai responder `ja_enviado`, e é o certo.
6. **Depois:** o portão do iPhone (§4.1) e as linhas do §7.

---

## 16 · O primeiro evento: a missão do dia *(19/11/2026)*

O pedido do dono: avisar a missão de hoje aos alunos, todos os dias. É o
mesmo cartão do topo da aba Hoje
([`Hoje.tsx`](../web/src/telas/Aluno/Hoje.tsx) `MissaoDeHoje`), dito na tela
bloqueada:

```
Missão de hoje: Polinômios
10 questões de Matemática. O desafio é o mesmo para toda a turma.
```

A missão já era a mesma para todos e determinística pela data de Fortaleza
([`banco/missao.py`](../api/app/banco/missao.py), docs/35 §9.3). Por isso o
aviso também é um só, para a turma, e não um por aluno.

### 16.1 · As oito perguntas do §9

| # | Pergunta | Resposta |
|---|---|---|
| 1 | Quem recebe | aluno com `aluno.ativo` (a régua do login, `auth_canvas.py::_sessao_para`) e aparelho ativado, **menos quem já mexeu numa questão do assunto de hoje, hoje** (§16.2). A coordenação não recebe |
| 2 | Quando sai | **agendado pelo cron, 15h** (§12, decisão 8). Não passa pelo motor de lembretes: lá o destinatário é um e-mail e o disparo é por pessoa, aqui é um envio só para a turma |
| 3 | O texto | o assunto no título, que é o que se lê de relance, e a matéria no corpo. Os dois são iguais para todos, e nada é pessoal (regra 4 do §2). Nome de tópico com mais de 64 caracteres sai do título e vai para o corpo |
| 4 | Validade | **TTL até a meia-noite de Fortaleza**, quando a missão vira. Depois disso o aviso falaria de um assunto que já não é o da tela. Urgência `normal` |
| 5 | Agrupa | `tag` e `Topic` fixos em `missao-do-dia`: o aviso de hoje substitui o de ontem na central de notificações, e um aparelho que ficou desligado recebe só o mais novo quando volta, nunca a fila da semana |
| 6 | Silêncio | **a rota recusa fora das 7h–22h de Fortaleza**, seja qual for o horário do crontab. Um cron mal escrito ou um disparo à mão de madrugada não acorda ninguém |
| 7 | Desligar só este tipo | ainda não (§12, decisão 10) |
| 8 | E-mail | não existe e-mail da missão: é só push |

- **Destino do toque:** `/`, a aba Hoje, e não `/treino/prioridade`. Um toque
  depois da meia-noite abriria o treino do assunto novo debaixo de um aviso que
  fala do antigo; na Hoje, o nome do assunto aparece antes do "Começar".
- **O texto da seção** "Avisos neste aparelho" do aluno passou a dizer o que
  chega ("Receba aqui a missão de hoje, todo dia…"): quem ativa precisa saber o
  que vai receber. Sem a hora, que mora no crontab e mentiria no dia em que a
  linha mudasse. A coordenação manteve o texto genérico.

### 16.2 · "Já mexeu no assunto de hoje"

O treino deixa uma pegada só: `questao_estudo_aluno.atualizado_em`, que muda em
toda escrita (`banco/listas.py::atualizar_estudo`), seja resposta, pulo,
anotação ou marca de resolvida. Quem tem uma linha com `atualizado_em` desde a
meia-noite de Fortaleza numa questão do assunto de hoje não recebe.

- **Os ids vêm do mesmo sorteio** (`missao_e_questoes_do_dia`), e não de uma
  segunda leitura do acervo: duas leituras seriam duas chances de o aviso falar
  de um assunto e conferir outro (o bug de docs/35 §9.1).
- **O banco filtra só pela data; o recorte pelo assunto é em Python.** Mandar os
  ids num `in_` poria na URL uma lista do tamanho do assunto (Polinômios tem
  102), enquanto o que mudou no dia é pouco.
- **`filtro_ts`** (`lembretes/despachante.py`): o `+` do fuso viraria espaço na
  query string, a armadilha que o motor de lembretes já pagou.
- **"Hoje" é Fortaleza:** quem treinou às 22h da véspera (01h UTC do dia) recebe.

### 16.3 · Uma vez por dia: [`envio_push`](../api/migrations/0082_envio_push.sql) e [`push/registro.py`](../api/app/push/registro.py)

Uma linha por envio, com `UNIQUE (tipo, referencia)`, e a referência da
missão é a data. A rota segue três passos, nesta ordem:

1. **`preparar` só lê:** sorteio, aparelhos e cortes. Se o banco cair aqui, a
   vaga do dia continua livre.
2. **`reservar` ocupa a vaga** com `upsert(..., ignore_duplicates=True)`, o
   `ON CONFLICT DO NOTHING` do PostgREST: a resposta traz só o que foi inserido,
   e lista vazia quer dizer "já enviado hoje". A atomicidade é do Postgres, não
   do processo, então vale também para um segundo container ou para depois de um
   restart. Conferido no PostgREST real (§16.5).
3. **`disparar` vai para o BackgroundTasks**, depois da resposta ao cron (§9). Ao
   terminar, ou ao cair, fecha a linha com as contagens ou com
   `interrompido: <Erro>`.

**Se o processo morrer no meio, o envio não se refaz naquele dia.** Perder um
aviso custa um dia. Mandar o mesmo aviso duas vezes para a turma inteira é o
que faz o aluno desligar os avisos, e desligar vale para todo tipo de aviso.
A tabela cresce uma linha por dia (365 por ano) e não precisa de limpeza.

### 16.4 · A rota: [`POST /push/eventos/missao-do-dia`](../api/app/routes/push_eventos.py)

Fica num router **separado** de `routes/push.py`, como `gravacoes_aula/rotas.py`
fica separado de `consulta.py`: lá tudo é JWT, aqui tudo é `X-Scheduler-Secret`.
Todas as respostas são 200, porque nenhuma delas é falha do agendador:

| `status` | Quando |
|---|---|
| `desligado` | sem chave VAPID. O cron pode rodar antes de o push ser ligado |
| `fora_do_horario` | fora das 7h–22h de Fortaleza |
| `ja_enviado` | a vaga do dia já foi usada |
| `sem_missao` | o acervo não tem tópico elegível hoje |
| `ninguem_com_aparelho`, `todos_ja_mexeram` | não há a quem mandar. A linha do dia é gravada |
| `aceito` | o envio começou em segundo plano, com `destinatarios`, `pulados` e `aparelhos` |

O cron é [`infra/vps/crontab-sas`](../infra/vps/crontab-sas),
`0 15 * * *`, com `--max-time 120`: a resposta sai antes do fan-out.

### 16.5 · O que foi verificado

| Portão | Resultado |
|---|---|
| `pytest tests/` | 3437 passaram, 34 pulados; `test_push_missao_do_dia.py` é novo |
| `ruff`, `npm test` (1084), `typecheck`, `lint`, `build` | limpos; os 29 avisos do lint já estavam na `main` |
| Migration 0082 | aplicou num Postgres 16 limpo depois das 81 anteriores; `down` + `up` ok |
| `reservar` no PostgREST real | a 1ª reserva devolve o id, a 2ª do mesmo dia devolve `None`, a do dia seguinte passa |

**De ponta a ponta**, no stack isolado (Postgres, PostgREST, API e Vite
próprios, chave VAPID de teste, acervo semeado só com Polinômios elegível) e no
Chrome do Mac, com janela:

| Passo | Resultado |
|---|---|
| Rota sem segredo, com segredo errado e com JWT de aluno | **401** nos três |
| Antes de qualquer aparelho | `ninguem_com_aparelho`, e a linha do dia gravada |
| Aluno a 390px, Minha conta → "Ativar avisos" | o texto novo nos dois estados; inscrição no FCM |
| Disparo do "cron" | `aceito`, 1 destinatário. O Chrome mostrou **"Missão de hoje: Polinômios / 10 questões de Matemática. O desafio é o mesmo para toda a turma."**, `tag` `missao-do-dia`, `url` `/`. O `gcm-internals` registrou o recebimento, sem falha de decifração |
| `envio_push` e `inscricao_push` | linha fechada (1 destinatário, 1 entregue); inscrição com 201 e `ultimo_envio_ok_em` |
| Segundo disparo do dia | `ja_enviado` |
| O aluno responde uma questão de Polinômios pelo treino (`PUT /banco/estudo/…`) e o dia é liberado | `todos_ja_mexeram`, 1 pulado: o filtro por `atualizado_em` funciona no PostgREST real |
| O aluno treinou Física hoje | recebe (`aceito`) |

**O que NÃO foi verificado:**

- **O cron do VPS de verdade** chamando a rota às 15h. Isso só se prova em
  produção, pelo `cron.log`, no primeiro dia (§15, passo 5).
- **O volume**: 900 alunos é um `select` de `inscricao_push` inteira e de
  `questao_estudo_aluno` do dia, sem paginação (armadilha 2). Os dois são
  pequenos, mas não foram medidos com dado real.
- Tudo o que o §14 já não verificou continua não verificado: aparelho real, o
  toque na notificação, o portão do iPhone.
