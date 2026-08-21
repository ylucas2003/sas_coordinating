# 15 · Plano de hospedagem — VPS Hostinger

Plano de implementação da hospedagem do SAS, do VPS provisionado até o go-live.
Complementa [`14-plano-producao.md`](14-plano-producao.md), que continua sendo a
referência do *porquê* de cada item — aqui é a ordem de execução.

---

## 1. Estado de partida (21/08/2026)

| Peça | Estado |
|---|---|
| VPS | Hostinger KVM 2 — 2 vCPU, 8 GB, 100 GB NVMe |
| Região | **Brasil · São Paulo** (9 ms) |
| Host | `srv1920219.hstgr.cloud` · `46.202.150.165` |
| SO | Ubuntu 24.04 LTS + Gerenciador Docker |
| Domínio | **`portalsas.online`** — apex e `www` já apontam para o IP, zona na própria Hostinger |
| Portas | 22/80/443 ainda fechadas (provisionamento em curso) |

DNS não exige nenhuma ação. Subdomínio do colégio (`sas.aridesa.com.br`) fica como
opção futura — sem e-mail em produção, trocar de domínio depois é barato.

## 2. Decisões travadas

| Decisão | Escolha | Consequência |
|---|---|---|
| Quem entra no dia 1 | **Coordenação + alunos** | Endurecer primeiro acesso e pôr teto no chat entram no caminho crítico (~1 semana a mais) |
| Domínio | **`portalsas.online`**, próprio | Sem dependência externa; DNS pronto |
| Login da coordenação | **Tabela de usuários** antes do go-live | ~1 dia; reusa o PBKDF2 de `auth.py:32-59` |
| E-mail | **Adiado** | Lembretes desligados. SES, sandbox e conta AWS saem do caminho crítico |

### O que essas decisões eliminaram

Adiar o e-mail derrubou três itens da Fase 0 e um risco inteiro:

- O **SSRF do webhook do SNS** ([14 §4.2](14-plano-producao.md)) deixa de ser
  exposição: sem SES, a rota não deve nem ser registrada. Vira `if` no `create_app()`,
  não conserto de segurança.
- O **teto de e-mail menor que a audiência** ([14 §4.4](14-plano-producao.md)) deixa de
  ser urgente — nada é enviado com `LEMBRETE_ALUNO_ATIVO=false`.
- **Sair do sandbox do SES** some do caminho crítico.
- Trocar de domínio depois deixa de quebrar link de descadastro, porque não há e-mail
  enviado com link dentro.

### O que essas decisões acrescentaram

Incluir alunos no dia 1 traz para o caminho crítico:

- **Teto de custo no chat do aluno** — 873 contas, hoje sem rate limit e sem `max_tokens`
- **Corrigir o fallback de modelo** — o chat da coordenação roda em `gpt-4o` por um
  fallback invertido em `perfis.py:31-39`, 16× mais caro que o mini
- **Primeiro acesso sem autosserviço** (ver §4.2)

---

## 3. Os dois portões

A sequência tem dois pontos de não-retorno. Tudo se organiza em torno deles.

```
Etapas 1-2 ──► PORTÃO 1 ──► Etapas 3-6 ──► PORTÃO 2 ──► go-live
              expor 443                    distribuir
              na internet                    acesso
```

**Portão 1 — antes de a porta 443 abrir para a internet.** O que impede um estranho
de virar coordenador.

**Portão 2 — antes de qualquer pessoa receber login.** O que impede um aluno de
virar outro aluno, e a fatura de virar surpresa.

---

## 4. Etapas

### Etapa 1 — Preparar o servidor (~meio dia)

```sh
# acesso
ssh root@46.202.150.165
adduser sas && usermod -aG sudo,docker sas
# chave pública para o novo usuário, depois:
#   PasswordAuthentication no  +  PermitRootLogin no  em /etc/ssh/sshd_config

# firewall — só o que precisa
ufw default deny incoming && ufw allow 22,80,443/tcp && ufw enable

# fuso: o código usa date.today() em 7 pontos das estatísticas (14 §3.2)
timedatectl set-timezone America/Fortaleza

apt update && apt upgrade -y && apt install -y fail2ban
docker --version && docker compose version    # v2.x
```

> **`TZ` também precisa entrar nos containers.** O host em Fortaleza não basta: os
> containers herdam UTC. Sem isso, das 21h à meia-noite as estatísticas incluem a prova
> do dia seguinte.

### Etapa 2 — Correções do Portão 1 (~1 dia)

Nenhuma depende do servidor; podem ser feitas em paralelo com a Etapa 1.

| # | Correção | Onde |
|---|---|---|
| 2.1 | **Guard de boot fail-safe** — tirar os defaults de `jwt_secret_key` e `coordenador_senha`, validar sempre, não só quando `APP_ENV != dev` | [config.py:11,35,39](../api/app/config.py), [main.py:33](../api/app/main.py#L33) |
| 2.2 | Remover `env` do `/health` — hoje qualquer um sonda se o guard está ativo | [main.py:77](../api/app/main.py#L77) |
| 2.3 | `/docs`, `/redoc`, `/openapi.json` desligados fora de dev | [main.py:44-48](../api/app/main.py#L44-L48) |
| 2.4 | **Não registrar o router de e-mail** enquanto SES estiver desligado — mata o SSRF sem consertá-lo | [main.py:74](../api/app/main.py#L74) |
| 2.5 | `python-multipart` → 0.0.18, `python-jose` → 3.5.0, declarar `postgrest==0.16.11`, gerar `requirements.lock` | [requirements.txt](../api/requirements.txt) |
| 2.6 | `ROOT_PATH` em Settings + `--proxy-headers --forwarded-allow-ips` no CMD | [main.py:44](../api/app/main.py#L44), [Dockerfile:62](../api/Dockerfile#L62) |

> **Pendência do 2.5:** `starlette` fica em 0.38.6 (CVE-2024-47874, mesma superfície
> de upload). Não dá para subir isolado — `fastapi==0.115.0` fixa `starlette<0.39.0`,
> então exige bumpar o próprio FastAPI. Fora do escopo do Portão 1; entra junto com
> a próxima atualização de dependências.
>
> **`ROOT_PATH` (2.6)** foi resolvido sem mudar código: `--root-path /api` no comando
> do uvicorn, em `infra/vps/docker-compose.yml`.
>
> **`/docs` (2.3)** está bloqueado em duas camadas de propósito — no nginx (protege
> mesmo com a API exposta por engano) e no FastAPI (protege mesmo sem o nginx).

### Etapa 3 — Stack de produção (~1 dia)

Um `docker-compose.prod.yml` de verdade. Só o nginx publica porta.

```
nginx        :80 :443   →  /      web/ estático
                        →  /api   proxy_pass api:8000
api                     (sem ports:)
postgrest               (sem ports:)   ← é isto que resolve o maior risco da auditoria
db + volume             (sem ports:)
```

Junto:

- `BASE_URL = ''` em [http-client.js:10](../web/js/services/http-client.js#L10) — some o hardcode do Render e some o CORS
- `proxy_buffering off` e `proxy_read_timeout 300s` na rota do chat (SSE)
- `client_max_body_size 25m` (upload de planilha)
- Headers: CSP, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors`
- Plus Jakarta Sans local em `web/assets/fonts/` — hoje é a única saída externa do front e vaza IP de aluno para o Google
- Base do web para `nginxinc/nginx-unprivileged`
- `/health` (liveness) separado de `/health/ready` (checa PostgREST)

### Etapa 4 — Banco (~1 dia)

| # | Item |
|---|---|
| 4.1 | Papéis viram `0000_papeis.sql` idempotente — `docker-entrypoint-initdb.d` só roda na criação do volume |
| 4.2 | Runner emite `GRANT ALL ON ALL TABLES ... TO sas_service` ao fim de todo `up` |
| 4.3 | Collation explícita no cluster (`--locale-provider=icu --icu-locale=pt-BR`) — a imagem alpine ordena por byte |
| 4.4 | `pg_advisory_lock` no `cmd_up`/`cmd_down` |
| 4.5 | `wipe-dados` exige `--confirmo=<banco>` e recusa fora de dev |
| 4.6 | `migrate up` → **`docker compose restart postgrest`** (o `NOTIFY` sozinho não basta) |
| 4.7 | `canvas_backfill` → `canvas_backfill_arquivos` → `recalcular_metricas` |

> O backfill leva horas (~3.300 chamadas em série, e medimos round-trips de 0,17 s a 15 s
> no Canvas). Rode em `tmux`, não numa sessão SSH que pode cair.

**Executado em 21/08.** Resultado e três aprendizados:

| | |
|---|---|
| Duração | histórico 100 min · PDFs 5 min · métricas 1 min |
| Volume | 1.521 alunos · 251 simulados · 101.058 notas · 361.403 respostas de questão |
| Arquivos | 105 PDFs, 128 MB — 198 dos 251 simulados com prova anexada |
| Derivados | 2.727 métricas · 946 classificações · 490 alertas |

1. **2021 e 2022 não entraram.** Os assignments daqueles anos usam outra convenção
   (`1_01 - P1 - Matemática - 20/02/2022`) e o parser os ignora, junto com sections
   como `'aprovados'` e `'Coordenação'`. Não é falha de infraestrutura — é a gramática
   de nomes do Canvas tendo mudado ao longo dos anos. Como o valor do SAS é análise
   longitudinal, decidir se vale recuperá-los é trabalho de `canvas_sync/mapeador.py`.
2. **O volume real é o dobro do que a auditoria mediu**, porque o banco local do
   desenvolvedor estava incompleto. Isso agrava a dívida de paginação: a auditoria
   citava `questao_resposta_aluno` como risco hipotético, e ela tem 361 mil linhas.
3. **Não confie em vigia que trate falha de SSH como fim de tarefa.** Um
   `Network is unreachable` fez o monitor anunciar conclusão com o backfill ainda a
   meia hora do fim. Distinga os dois casos e só desista após N falhas seguidas.

### Etapa 5 — TLS (~1 hora) — ✅ 21/08

Certificado Let's Encrypt para `portalsas.online` e `www`, válido até 19/11/2026.
Renovação pelo timer do systemd, **testada com `certbot renew --dry-run`**.

Duas decisões que o arranjo exigiu:

- **O certificado é copiado, não lido de `/etc/letsencrypt`.** Lá a chave privada é
  legível só por root, e o nginx roda como uid 101 (imagem unprivileged). O hook
  `infra/vps/renovar-tls.sh`, instalado em `/etc/letsencrypt/renewal-hooks/deploy/`,
  copia com o dono certo e recarrega o `web` a cada renovação.
- **HSTS começa curto (`max-age=86400`), não em um ano.** HSTS é difícil de desfazer:
  com um ano, qualquer falha de certificado tranca os usuários fora do sistema pelo
  resto do prazo, porque o browser recusa o fallback para HTTP. Subir para 31536000
  depois de uma ou duas renovações bem-sucedidas.

### Etapa 6 — Cron (~1 hora)

Quatro jobs, no fuso do host, com timeout — o reconcile leva 60-100 min:

```cron
*/5 * * * * curl -fsS --max-time 280 -X POST -H "X-Scheduler-Secret: $S" http://127.0.0.1:8000/canvas-sync/run
0   * * * * curl -fsS --max-time 280 -X POST -H "X-Scheduler-Secret: $S" http://127.0.0.1:8000/alertas/verificar
5   * * * * curl -fsS --max-time 280 -X POST -H "X-Scheduler-Secret: $S" http://127.0.0.1:8000/disparos/processar
0   3 * * * curl -fsS --max-time 7200 -X POST -H "X-Scheduler-Secret: $S" http://127.0.0.1:8000/canvas-sync/reconciliar
```

Use `/disparos/processar` — `/cobranca/verificar` é delegate deprecado.
Depois: `cdk destroy SasSchedulerStack` e apagar o parâmetro SSM (mas **guarde o valor**:
sem `SCHEDULER_SECRET` as quatro rotas devolvem 503).

### Etapa 7 — Correções do Portão 2 (~1 semana)

| # | Correção | Por quê |
|---|---|---|
| 7.1 | **Tabela de usuários da coordenação** com PBKDF2 e um login por pessoa | Hoje é senha única em env, texto puro, sem rate limit no `/auth/login`, sem rastro de autoria |
| 7.2 | **Primeiro acesso sem autosserviço** — coordenação provisiona via `criar_acesso.py`, aluno troca no primeiro login | Hoje matrícula + e-mail reseta a senha sem prova de posse, e matrícula circula em lista de chamada |
| 7.3 | `criar_acesso.py` para de imprimir senha e PII no stdout | Num servidor, stdout vira log retido |
| 7.4 | **Teto de custo no chat**: N mensagens/hora por usuário + `max_tokens` | 873 contas sem freio nenhum; pior caso medido, US$ 379 numa hora |
| 7.5 | **Fallback de modelo**: `_modelo_coordenador()` cai em `gpt-4o` quando lê "mini" | 16× mais caro; um coordenador custa mais que 175 alunos |
| 7.6 | **Race no cache de alertas** — tirar o estado de módulo de `stats/alertas.py` | Upload concorrente com o sync grava alerta sobre histórico pela metade |

> **Executado em 21/08.** Verificado em produção: login pela tabela devolve `sub`
> com UUID (autoria deixou de ser a string fixa `"coordenador"`), senha errada dá 401,
> a 6ª tentativa dá 429, o autosserviço de primeiro acesso responde 403, e o motor de
> alertas rodou pelo caminho novo emitindo 446 alertas.
>
> **Três coisas que a execução ensinou:**
>
> 1. **As migrations vivem DENTRO da imagem, não no disco do host.** `rsync` no host
>    não as atualiza, e `docker compose build api` não reconstrói o `migrate` — são
>    imagens separadas do mesmo contexto. A 0021 ficou invisível para o runner até um
>    `docker compose build migrate`. Em todo deploy com migration nova: **buildar os
>    dois**.
> 2. **`/app` é read-only para o uid 10001 da imagem de produção.** Os scripts de
>    provisionamento gravavam a senha no diretório de trabalho e quebravam com
>    `PermissionError` — *depois* de escrever o hash no banco. Com senha sorteada, isso
>    perderia a senha para sempre. Agora o destino é resolvido e testado ANTES de
>    qualquer escrita no banco (`_destino_da_senha`, com `SAS_SAIDA_SENHA` para apontar
>    para um volume).
> 3. **O `POSTGREST_TOKEN` do plano original não foi exigido**, e não deve ser: nesta
>    topologia o PostgREST não tem porta publicada e quem contém o acesso é a rede.
>
> **Lacuna operacional que isto abriu, e que é decisão sua:** com o autosserviço
> desligado, `criar_acesso.py` provisiona **um aluno por vez**. Para os ~900 alunos da
> decisão "coordenação + alunos no dia 1", falta um modo em lote — ou religar o
> autosserviço com prova de posse de verdade (código de uso único por e-mail), que
> depende do envio de e-mail, hoje adiado.

### Etapa 8 — Observabilidade mínima (~2 dias)

- Log JSON com nível por env, em `create_app()`
- Exception handler global com request id
- Log de autenticação e de edição de nota em tabela (`evento_auditoria`)
- **`/health/ready` degrada sem sync bem-sucedido em 30 min** — é o modo de falha mais
  provável da migração: cron parado, API respondendo 200, dados congelando em silêncio

> **Executado em 21/08.** O que entrou:
>
> | | |
> |---|---|
> | Log | JSON estruturado em `app/observabilidade.py`, nível por `LOG_NIVEL`, `LOG_FORMATO=texto` volta ao legível em dev |
> | Correlação | `X-Request-Id` gerado ou herdado, na resposta e em toda linha de log da requisição |
> | Erro | handler global: traceback com rota e método no log, corpo só com `request_id` — mensagem de exceção pode carregar URL do PostgREST ou trecho de token |
> | Readiness | `/health/ready` checa PostgREST **e** idade do último sync (503 se > 30 min) |
> | Vigia | `cron-saude.sh` a cada 10 min — é o que transforma o endpoint em alerta |
> | Auditoria | tabela `evento_auditoria` (0022) + `login_ok`, `login_falhou`, `primeiro_acesso_bloqueado` |
>
> **`/health` continua liveness e NÃO checa banco de propósito.** É o que o healthcheck
> do Docker consulta: se ele dependesse do agendador, um cron parado colocaria o
> container em loop de restart — que não conserta nada e ainda derruba o que funcionava.
>
> **Dois defeitos que a execução expôs:**
>
> 1. **`request.url.path` inclui o `root_path`.** O filtro que excluía `/health` do log
>    comparava com igualdade e nunca casava, porque com `--root-path /api` o caminho que
>    chega ao middleware é `/api/health`. Eram ~3 mil linhas/dia de ruído do healthcheck,
>    com o filtro parecendo correto. Agora é `endswith`.
> 2. **A auditoria confirmou que o `X-Forwarded-For` está certo.** Os eventos gravam o IP
>    real do cliente, não o do container nginx — se a configuração de proxy da Etapa 3
>    estivesse errada, todo evento teria o mesmo IP e a trilha não serviria para nada.
>
> **Limite honesto:** sem canal de notificação (e-mail adiado), o "alerta" é um log e um
> arquivo de estado em `/var/log/sas/saude-estado.txt`. O ramo DEGRADADO do
> `cron-saude.sh` é onde um canal real entra, quando existir.

### Etapa 9 — Corte para o React, ensaio e abertura

O frontend está sendo migrado para React + TypeScript + Vite em paralelo
([16-plano-migracao-react.md](16-plano-migracao-react.md)). Aquele plano cobre o lado
de `web/` (Dockerfile, Vite, `web/nginx.conf`). **Esta etapa cobre o lado da borda —
`infra/vps/` — que nenhum dos dois planos toca até aqui.**

> ⚠️ **Até o corte, não rode `sync.sh` cegamente.** Hoje o serviço `web` monta `web/`
> **cru** no nginx. Um `index.html` que referencia `/src/main.tsx` chega ao browser
> sem passar pelo Vite e o site quebra. Enquanto a migração estiver no meio, envie
> arquivos pontuais por `scp`, como foi feito na Etapa 6.

#### 9.1 · O `web` deixa de ser mount e vira build

Em `infra/vps/docker-compose.yml`:

```yaml
  web:
-   image: nginxinc/nginx-unprivileged:1.27-alpine
+   build:
+     context: ../../web          # multi-stage: node build → nginx unprivileged
    volumes:
-     - ../../web:/usr/share/nginx/html:ro     ← sai
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro   ← FICA
```

O mount do `nginx.conf` **continua**, e de propósito: o `web/Dockerfile` copia o
`web/nginx.conf`, que serve a imagem isolada e não sabe de TLS nem do proxy `/api`.
Em produção quem manda é `infra/vps/nginx.conf`, montado por cima.

Efeito no deploy: `docker compose restart web` deixa de bastar — passa a ser
`up -d --build web`. O `02-deploy.sh` já faz `build`, então o fluxo do operador não
muda; o que muda é o tempo (segundos → alguns minutos, por causa do `npm ci`).

#### 9.2 · O fallback de SPA passa a ser obrigatório — a regra inverte

Hoje `infra/vps/nginx.conf` tem `try_files $uri $uri/ =404` **com um comentário
dizendo que a ausência de fallback é proposital**, porque o roteamento era por hash.
Com React Router e caminhos reais, isso inverte:

```nginx
    location ^~ /assets/ {          # PRIMEIRO, e com ^~ para vencer as regex
        try_files $uri =404;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
```

A ordem importa mais que o fallback. Sem a regra `^~ /assets/`, um módulo ausente
recebe o `index.html` com **status 200**, e o erro no browser vira
`Unexpected token '<'` — indecifrável. Com ela, asset que não existe dá 404 honesto.

#### 9.3 · O cache inverte também — e tem uma armadilha já paga

Assets ganham hash no nome, então passam de `no-cache` para cacheáveis de verdade;
o HTML continua `no-cache`, porque é o único sem hash.

> **Não use `add_header Cache-Control "public, immutable"` no bloco de assets.**
> Um `add_header` dentro de um `location` **anula todos os herdados do `server`** —
> foi exatamente assim que CSP, `nosniff` e `frame-ancestors` sumiram em silêncio na
> Etapa 3, com a configuração passando no `nginx -t`. Use `expires 1y;`, que define
> `Cache-Control` por outro mecanismo e preserva a herança. Se `immutable` for mesmo
> necessário, repita os quatro headers de segurança dentro do bloco.

#### 9.4 · `login.html` continua sendo segunda entrada

O Vite builda duas entradas (`index.html` e `login.html`). O fallback do 9.2 não a
engole, porque o arquivo existe e o `try_files` acha antes. Quando a Etapa 9 do
plano do React transformar o login em rota do SPA, esta regra some sozinha.

#### 9.5 · A CSP pode apertar depois do build

Com bundle, deixa de haver `<script>` inline no `index.html` — dá para tirar
`'unsafe-inline'` de `script-src`. Conferir depois do primeiro build se o Vite não
injetou preload inline; e CSS Modules viram arquivo, o que pode liberar
`style-src` também. Apertar **depois** de o corte estar estável, não junto.

#### 9.6 · Ordem do corte

1. `npm run build` local passa sem erro de TypeScript
2. `sync.sh` (aí sim), com `web/dist` no exclude — quem builda é o container
3. `docker compose up -d --build web`
4. Verificação do 9.7 antes de avisar qualquer usuário

#### 9.7 · Verificação pós-corte

| Teste | Esperado |
|---|---|
| `GET /` | 200 |
| `GET /alunos/A023` (rota profunda) | 200 **com o index**, não 404 |
| `GET /assets/nao-existe.js` | **404**, não 200 com HTML |
| `GET /login.html` | 200 |
| Headers de segurança em `/` | CSP, `nosniff`, `Referrer-Policy`, `X-Frame-Options` **ainda presentes** |
| `GET /api/health` | 200 |
| Fonte local | 200, sem saída para `fonts.gstatic.com` |

> **Corte executado em 21/08.** Build do Vite em 20 s no VPS; os sete testes do
> 9.7 passaram, incluindo o crítico (asset inexistente → 404, não 200 com HTML).
>
> **Um bug real que só o smoke test pegou — e é o modo de falha que esta etapa
> descrevia.** O download de PDF passou a devolver `index.html` com status 200 em vez
> do arquivo, e um token adulterado também devolvia 200.
>
> Causa: `API_BASE_URL` não incluía o prefixo `/api`, então a URL gerada era
> `https://portalsas.online/arquivos/download?token=…` — que **não** é a rota da API.
> Antes do corte isso dava 404 (não havia fallback); depois, o fallback de SPA passou
> a servir o index. A falha ficou mais silenciosa justamente por causa da mudança
> correta.
>
> Correção: `API_BASE_URL=https://portalsas.online/api`. Verificado — PDF de 1,6 MB
> com `content-type: application/pdf`, e token adulterado devolvendo 403.
>
> **A lição generaliza:** toda URL que a API gera para si mesma precisa do prefixo
> `/api`. `API_BASE_URL` é a única hoje; qualquer outra que apareça tem o mesmo risco,
> e o sintoma será sempre "HTML com 200 no lugar do recurso".

#### 9.8 · Ensaio e abertura

1. Smoke test com a imagem `prod`: login, upload de planilha, download de PDF em browser real, chat com streaming atravessando o nginx (`curl -N`)
2. Abrir para a **coordenação** primeiro
3. Alunos depois de alguns dias de operação estável — e só depois do Portão 2 (Etapa 7)

---

## 5. Segredos a gerar (nenhum reaproveitado do `.env` de dev)

- [ ] `JWT_SECRET_KEY` — 32+ bytes aleatórios
- [ ] `SCHEDULER_SECRET`
- [ ] `POSTGREST_TOKEN` + `PGRST_JWT_SECRET`
- [ ] `POSTGRES_PASSWORD` / `POSTGREST_PASSWORD`
- [ ] `CANVAS_API_TOKEN` — pedir conta de serviço ao colégio (o atual é pessoal e tem poder de escrita e de nota)
- [ ] `OPENAI_API_KEY` — chave separada da usada em dev, para o gasto ficar isolado
- [ ] `APP_ENV=production` · `API_BASE_URL=https://portalsas.online` · `CORS_ALLOW_ORIGINS` vazio (mesma origem)
- [ ] `EMAIL_DESTINATARIO_TESTE` **vazia** · `LEMBRETE_ALUNO_ATIVO=false`

## 6. Cronograma

| Etapa | Esforço | Portão | Estado |
|---|---|---|---|
| 1 · Servidor | meio dia | — | ✅ 21/08 |
| 2 · Correções | 1 dia | **Portão 1** | ✅ 21/08 |
| 3 · Stack | 1 dia | — | ✅ 21/08 |
| 4 · Banco | 1 dia | — | ✅ 21/08 |
| 5 · TLS | 1 h | — | ✅ 21/08 |
| 6 · Cron | 1 h | — | ✅ 21/08 |
| 7 · Auth e custo | 1 semana | **Portão 2** | ✅ 21/08 |
| 8 · Observabilidade | 2 dias | — | ✅ 21/08 |
| 9 · Corte React, ensaio e go-live | 1 dia | go-live | ✅ 21/08 (corte) |

**~2,5 semanas.** As etapas 3-6 podem correr em paralelo com a 7, porque o que trava a
abertura para alunos é o Portão 2, não a stack.

## 6b. Scripts (infra/vps/)

| Script | Onde roda | Papel |
|---|---|---|
| `01-preparar-servidor.sh` | servidor, root | Etapa 1. `--ssh-hardening` é passo separado, ainda **não aplicado** |
| `00-prep-root.sh` | servidor, root, uma vez | Cria `/opt/sas` e o storage com o dono certo, para o deploy não precisar de sudo |
| `sync.sh` | máquina de dev | Envia a árvore por rsync (o repo ainda tem trabalho não commitado) |
| `02-deploy.sh` | servidor, usuário `sas` | Etapa 3. Idempotente; nas próximas vezes é o comando de deploy |

## 7. O que fica de fora deste plano

Registrado para não virar surpresa: backup contínuo (decisão de 21/08 — o Canvas é o
arquivo), e-mail e lembretes, conta de serviço do Canvas, ambiente de homologação,
subdomínio do colégio, e a dívida listada em [14 §10](14-plano-producao.md).
