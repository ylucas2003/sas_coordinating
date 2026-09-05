#!/usr/bin/env bash
#
# Deploy de produção do SAS, em UM comando e UM arquivo.
#
#   ./infra/vps/deploy.sh                # portões locais → rsync → build → up → smoke
#   ./infra/vps/deploy.sh --migrar       # idem, autorizando as migrations pendentes
#   ./infra/vps/deploy.sh --rapido       # pula os portões locais (lint, teste, typecheck)
#   ./infra/vps/deploy.sh --estrito      # lint deixa de ser aviso e passa a bloquear
#   ./infra/vps/deploy.sh --verificar    # só o smoke test; não toca no servidor
#
# Roda da máquina de desenvolvimento. A parte que executa no servidor viaja por
# stdin (`ssh bash -s`), não de uma cópia em /opt/sas: o passo de deploy é
# sempre o deste arquivo, nunca o que sobrou de um deploy anterior.
#
# Pré-requisitos, cada um de uma vez só e fora daqui:
#   01-preparar-servidor.sh   usuário, firewall, docker, fuso     (servidor, root)
#   00-prep-root.sh           diretórios com o dono certo         (servidor, root)
#   03-tls.sh                 certificado e renovação             (servidor, root)
#
# Variáveis de ambiente:
#   SAS_VPS       destino ssh       (default sas@46.202.150.165)
#   SAS_DOMINIO   domínio público   (default portalsas.online)

set -euo pipefail

DESTINO="${SAS_VPS:-sas@46.202.150.165}"
DOMINIO="${SAS_DOMINIO:-portalsas.online}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

MIGRAR=0
RAPIDO=0
ESTRITO=0
SO_VERIFICAR=0
CONFIRMAR=1

log()   { printf '\n\033[1;34m▸ %s\033[0m\n' "$*"; }
ok()    { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
aviso() { printf '  \033[0;33m!\033[0m %s\n' "$*"; }
erro()  { printf '  \033[0;31m✗\033[0m %s\n' "$*" >&2; }

ajuda() {
    # Imprime o cabeçalho até a primeira linha que não é comentário — assim a
    # ajuda não descola do arquivo quando o cabeçalho muda de tamanho.
    awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "${BASH_SOURCE[0]}"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --migrar)          MIGRAR=1 ;;
        --rapido)          RAPIDO=1 ;;
        --estrito)         ESTRITO=1 ;;
        --verificar)       SO_VERIFICAR=1 ;;
        --sem-confirmar)   CONFIRMAR=0 ;;
        --host)            DESTINO="$2"; shift ;;
        -h|--ajuda|--help) ajuda ;;
        *) erro "opção desconhecida: $1"; exit 1 ;;
    esac
    shift
done


# ─── 1. Portões locais ────────────────────────────────────────────────────
# Duas categorias, de propósito:
#
#   BLOQUEIA  teste e typecheck — dizem se o código está QUEBRADO.
#   AVISA     ruff e biome — dizem se o código está FEIO.
#
# Lint não bloqueia porque a árvore de hoje já tem achado herdado (120 no ruff,
# 8 no biome, a maioria de regra nova que entrou com a atualização do linter).
# Um portão que reprova sempre não protege nada: ensina o operador a passar
# `--rapido`, que desliga junto os testes, que são os que importam. Quem quiser
# o bloqueio tem `--estrito`.
#
# O build do Vite fica de fora: quem builda o front é o container, e o
# typecheck já pega quase tudo que quebraria lá.
portoes_locais() {
    log "Portões locais"

    reprovou_lint() {   # $1 = ferramenta, $2 = como rodar à mão
        if [[ $ESTRITO == 1 ]]; then
            erro "$1 reprovou — rode '$2'"; exit 1
        else
            aviso "$1 com achados (não bloqueia; use --estrito para bloquear) — '$2'"
        fi
    }

    if [[ -x "$RAIZ/api/.venv/bin/ruff" ]]; then
        (cd "$RAIZ/api" && ./.venv/bin/ruff check . >/dev/null 2>&1) \
            && ok "ruff" || reprovou_lint ruff "cd api && ./.venv/bin/ruff check ."
        (cd "$RAIZ/api" && ./.venv/bin/python -m pytest tests/ -q >/tmp/sas-pytest.log 2>&1) \
            && ok "pytest" || { erro "pytest reprovou:"; tail -25 /tmp/sas-pytest.log >&2; exit 1; }
    else
        aviso "api/.venv ausente — lint e teste da API pulados"
    fi

    if [[ -d "$RAIZ/web/node_modules" ]]; then
        (cd "$RAIZ/web" && npm run typecheck >/dev/null 2>&1) \
            && ok "typecheck" || { erro "typecheck reprovou — rode 'cd web && npm run typecheck'"; exit 1; }
        (cd "$RAIZ/web" && npm run lint >/dev/null 2>&1) \
            && ok "biome" || reprovou_lint biome "cd web && npm run lint"
        (cd "$RAIZ/web" && npm test >/tmp/sas-vitest.log 2>&1) \
            && ok "vitest" || { erro "testes do front reprovaram:"; tail -25 /tmp/sas-vitest.log >&2; exit 1; }
    else
        aviso "web/node_modules ausente — checagens do front puladas (rode 'cd web && npm install')"
    fi
}


# ─── 2. O que exatamente vai subir ────────────────────────────────────────
# O rsync envia a ÁRVORE DE TRABALHO, não o HEAD. Então o que está sujo no git
# é o que vai para produção, e isso precisa aparecer ANTES, não depois.
resumo_e_confirmacao() {
    local commit sujos
    if git -C "$RAIZ" rev-parse --git-dir >/dev/null 2>&1; then
        commit="$(git -C "$RAIZ" log -1 --format='%h %s')"
        sujos="$(git -C "$RAIZ" status --porcelain | wc -l | tr -d ' ')"
    else
        commit="sem git"; sujos=0
    fi

    log "Vai subir para PRODUÇÃO"
    printf '  destino     %s\n' "$DESTINO"
    printf '  domínio     https://%s\n' "$DOMINIO"
    printf '  commit      %s\n' "$commit"
    if [[ "$sujos" != "0" ]]; then
        printf '  \033[0;33mnão commitado  %s arquivo(s) — o rsync envia a árvore de trabalho\033[0m\n' "$sujos"
        git -C "$RAIZ" status --porcelain | head -10 | sed 's/^/      /' || true
        [[ "$sujos" -gt 10 ]] && printf '      … e mais %s\n' "$((sujos - 10))"
    fi
    printf '  migrations  %s\n' \
        "$([[ $MIGRAR == 1 ]] && echo 'AUTORIZADAS (--migrar)' || echo 'bloqueadas (use --migrar)')"

    if [[ $CONFIRMAR == 1 ]]; then
        printf '\n  Continuar? [s/N] '
        read -r resposta || resposta=""
        [[ "$resposta" =~ ^[sSyY]$ ]] || { echo "  abortado."; exit 130; }
    fi
}


# ─── 3. Enviar o código ───────────────────────────────────────────────────
# Por que rsync da árvore e não `git pull` no servidor: o repositório costuma
# ter trabalho não commitado, e um clone do GitHub subiria uma versão diferente
# da que foi testada acima. Quando o repo estiver sempre em dia, trocar por
# git pull no bloco remoto é trivial.
#
# NUNCA envia .env: os segredos de produção são gerados no servidor e ficam só
# lá. Como está em --exclude, o --delete também não o toca.
#
# ⚠️ A LISTA DE EXCLUDES ERA ESCRITA À MÃO, E NÃO CONHECIA O .gitignore.
#
# O efeito não era desperdício: era vazamento. `.auditoria-mobile/` está no
# .gitignore desde sempre e continha capturas do painel de um ALUNO REAL — nome,
# nota, "37º de 179", percentil por matéria. Como não estava em nenhum
# --exclude, ia para o VPS a cada deploy. E como `git status --porcelain` não
# lista arquivo ignorado, a tela de confirmação (`resumo_e_confirmacao`) nunca
# mencionou isso: o operador confirmava sem ter como saber.
#
# `--filter=':- .gitignore'` faz o rsync herdar a régua que o repositório já
# mantém, e fecha a classe inteira do problema em vez de tapar um buraco por
# vez. De quebra, o envio caiu de 4.870 arquivos / 1,63 GB para 842 / 36,7 MB —
# eram 929 MB de PDF original e 570 MB de provas resolvidas, todos gitignorados
# e nenhum deles usado em produção.
#
# Os quatro --exclude que SOBRAM não são redundância: nenhum deles está no
# .gitignore, e cada um tem um motivo próprio:
#   .git/              versionado por definição; o servidor não precisa do histórico
#   /dados/            é o storage de produção, que mora NO servidor — mandar o
#                      local por cima apagaria upload de verdade
#   .env               segredo gerado no servidor; em --exclude também para o
#                      --delete não o remover
#   .DS_Store          lixo do Finder; aparece em qualquer pasta aberta no Mac
CAMINHOS_QUE_O_GITIGNORE_NAO_COBRE=(
    --exclude '.git/'
    --exclude '/dados/'
    --exclude '.env'
    --exclude '.DS_Store'
)

enviar_codigo() {
    log "Enviando código (rsync)"
    rsync -az --delete --stats \
        --filter=':- .gitignore' \
        "${CAMINHOS_QUE_O_GITIGNORE_NAO_COBRE[@]}" \
        "$RAIZ/" "$DESTINO:/opt/sas/" | tail -4
}


# ─── 4. Build, migrations e subida — no servidor ──────────────────────────
# O bloco abaixo roda como o usuário `sas` (que está no grupo docker), NÃO como
# root, e viaja por stdin. É idempotente: não toca no .env nem no banco além
# das migrations autorizadas.
subir_no_servidor() {
    log "Build e subida no servidor"
    ssh -o BatchMode=yes "$DESTINO" "bash -s -- $MIGRAR $DOMINIO" <<'REMOTO'
set -euo pipefail

MIGRAR="${1:-0}"
DOMINIO="${2:-portalsas.online}"
RAIZ="/opt/sas"
STORAGE="/opt/sas/dados/storage"
UID_APP=10001          # usuário `sas` de DENTRO da imagem (api/Dockerfile)

ok()   { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
aviso(){ printf '  \033[0;33m!\033[0m %s\n' "$*"; }
erro() { printf '  \033[0;31m✗\033[0m %s\n' "$*" >&2; }

command -v docker >/dev/null || { erro "docker ausente — rode 01-preparar-servidor.sh"; exit 1; }
[[ -d "$RAIZ/infra/vps" ]] || { erro "código ausente em $RAIZ"; exit 1; }
cd "$RAIZ/infra/vps"

# ── Storage ──────────────────────────────────────────────────────────────
# A imagem prod roda como uid 10001 e NÃO é root. Um volume nomeado nasceria
# root e o upload falharia com PermissionError; por isso é bind mount com dono
# explícito (docs/14 §5). Este bloco NÃO usa sudo de propósito: dar sudo sem
# senha ao usuário de operação é privilégio permanente em troca da conveniência
# de uma execução. Quem cria o diretório, uma vez, é o 00-prep-root.sh.
[[ -d "$STORAGE" ]] || { erro "$STORAGE não existe — rode como root: bash $RAIZ/infra/vps/00-prep-root.sh"; exit 1; }
dono="$(stat -c '%u' "$STORAGE")"
[[ "$dono" == "$UID_APP" ]] || { erro "$STORAGE pertence ao uid $dono, deveria ser $UID_APP"; exit 1; }
ok "storage ok (uid $UID_APP)"

# ── Segredos ─────────────────────────────────────────────────────────────
if [[ -f .env ]]; then
    ok ".env preservado (segredos não são regerados)"
else
    cp .env.example .env
    # Sorteados aqui, no servidor: nunca trafegam por chat, e-mail ou git.
    for chave in POSTGRES_PASSWORD POSTGREST_PASSWORD JWT_SECRET_KEY SCHEDULER_SECRET; do
        sed -i "s|^${chave}=.*|${chave}=$(openssl rand -hex 32)|" .env
    done
    # Senha da coordenação: legível, para alguém conseguir digitar.
    senha="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
    sed -i "s|^COORDENADOR_SENHA=.*|COORDENADOR_SENHA=${senha}|" .env
    chmod 600 .env
    ok ".env gerado com segredos aleatórios (chmod 600)"
    printf '\n  \033[1;33mSENHA DA COORDENAÇÃO: %s\033[0m\n  Anote agora — não será mostrada de novo.\n\n' "$senha"
fi

# O guard de boot recusa subir sem estas duas.
for obrigatoria in JWT_SECRET_KEY COORDENADOR_SENHA; do
    grep -qE "^${obrigatoria}=.+" .env || { erro "$obrigatoria vazia no .env — a API não sobe"; exit 1; }
done
grep -qE '^CANVAS_API_TOKEN=.+' .env || aviso "CANVAS_API_TOKEN vazia — o sync do Canvas não roda"
grep -qE '^OPENAI_API_KEY=.+'   .env || aviso "OPENAI_API_KEY vazia — insights e chat desligados (degrada limpo)"

# ── Imagens ──────────────────────────────────────────────────────────────
# `--profile tools` existe para incluir o `migrate`, que fica FORA do build
# default por estar num profile. As migrations viajam DENTRO da imagem: o rsync
# atualiza o disco do host, não a imagem, e `build api` não reconstrói o
# `migrate` — são imagens separadas do mesmo contexto. Foi assim que a 0021
# ficou invisível para o runner (docs/15 §Etapa 7, aprendizado 1).
echo "  … build (api, web, migrate)"
docker compose --profile tools build --quiet
ok "imagens construídas"

# ── Migrations ───────────────────────────────────────────────────────────
# ANTES do `up -d`, não depois: código novo contra schema velho devolve 500 na
# primeira tela que dependa da coluna nova.
#
# Falha FECHADO. Migration pendente sem autorização explícita interrompe o
# deploy aqui — a stack continua no ar com a versão anterior, que é o estado
# seguro.
# `</dev/null` e `-T` NÃO são opcionais: este trecho roda via `ssh bash -s`,
# com o script inteiro chegando por stdin. `docker compose run` lê stdin por
# padrão — e lia o RESTO DESTE SCRIPT: tudo daqui para baixo (migrations,
# up -d, restart do postgrest) era engolido em silêncio, o bash remoto
# terminava "com sucesso" e o smoke test batia no container antigo, que
# continuava no ar. Aconteceu no deploy da Sprint 2 (22/08/2026).
saida_status="$(docker compose run --rm -T migrate status </dev/null 2>&1)" || {
    erro "não consegui ler o status das migrations:"; echo "$saida_status" | tail -20 >&2; exit 1; }
echo "$saida_status" | tail -3 | sed 's/^/  /'

if grep -q 'pendente(s)' <<<"$saida_status"; then
    if [[ "$MIGRAR" == "1" ]]; then
        docker compose run --rm -T migrate up </dev/null || { erro "migration falhou — nada foi trocado"; exit 1; }
        ok "migrations aplicadas"
    else
        erro "há migration pendente e o deploy não foi autorizado a aplicá-la"
        erro "revise o SQL e rode de novo:  ./infra/vps/deploy.sh --migrar"
        erro "a stack segue no ar com a versão anterior — nada foi trocado"
        exit 2
    fi
else
    ok "schema em dia"
fi

# ── Subida ───────────────────────────────────────────────────────────────
docker compose up -d </dev/null
ok "containers no ar"

# O PostgREST lê o schema UMA vez, no boot, e o cacheia. Sem este restart as
# tabelas e colunas novas voltam 404 — e o 404 parece bug de código
# (docs/14 §6.6).
#
# ⚠️ INCONDICIONAL, e isso é decisão, não descuido. Até 04/09 o restart só
# acontecia quando ESTA execução aplicava migration (`MIGROU == 1`), e a
# pergunta certa é outra: "o schema mudou desde que o postgrest bootou?".
# Um deploy que morresse entre o `up -d` acima e este restart — ssh caindo,
# Ctrl-C, `up -d` demorando — deixava o operador reexecutando o script, e aí
# o `migrate status` dizia "schema em dia", `MIGROU` ficava 0 e o restart
# NUNCA acontecia. O cache seguia sem conhecer a coluna nova indefinidamente,
# com o deploy declarando sucesso.
#
# O preço de rodar sempre são ~2 s. O preço de pular é a armadilha 1 do
# CLAUDE.md num sistema que parece no ar (docs/35 §13).
docker compose restart postgrest </dev/null
ok "postgrest reiniciado (cache de schema)"

# ── Esperar o uvicorn atender ────────────────────────────────────────────
# Por que --resolve em vez de http://127.0.0.1: desde a Etapa 5 a porta 80
# redireciona para HTTPS, e 3xx NÃO é erro para o `curl -f` — uma checagem em
# http receberia o 301 com corpo vazio e comemoraria sem ter falado com a API.
# O --resolve fala HTTPS com o próprio host, sem sair para a internet e sem
# depender de DNS, mas com Host e SNI corretos para o certificado bater (mesma
# técnica do cron-sas.sh).
for _ in $(seq 1 30); do
    resp="$(curl -fsS --max-time 3 --resolve "$DOMINIO:443:127.0.0.1" "https://$DOMINIO/api/health" 2>/dev/null || true)"
    [[ "$resp" == *'"status":"ok"'* ]] && break
    sleep 2
done
[[ "$resp" == *'"status":"ok"'* ]] \
    && ok "API responde através do nginx" \
    || { erro "API não respondeu em /api/health"; docker compose logs --tail=40 api; exit 1; }

docker compose ps --format "  {{.Service}}\t{{.Status}}"
REMOTO
}


# ─── 5. Smoke test, pelo HTTPS público ────────────────────────────────────
# De fora, pelo domínio real: é o caminho que o coordenador e o aluno fazem.
# Cada caso aqui é uma falha que JÁ aconteceu neste projeto (docs/15 §9.7).
FALHAS=0
codigo()  { curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMINIO$1" 2>/dev/null || echo 000; }
esperar() {
    local caminho="$1" esperado="$2" rotulo="$3" obtido
    obtido="$(codigo "$caminho")"
    if [[ "$obtido" == "$esperado" ]]; then
        ok "$rotulo ($caminho → $obtido)"
    else
        erro "$rotulo ($caminho → $obtido, esperado $esperado)"
        FALHAS=$((FALHAS + 1))
    fi
}

verificar() {
    log "Verificação em https://$DOMINIO"

    esperar "/api/health"            200 "API viva"
    esperar "/"                      200 "front servido"
    # Rota profunda tem que cair no index (React Router), não dar 404.
    esperar "/alunos/A023"           200 "rota profunda no SPA"
    # E asset inexistente tem que dar 404 HONESTO. Se devolver 200, o fallback
    # de SPA está engolindo /assets/ e todo erro de módulo vira
    # "Unexpected token '<'" no browser (docs/15 §9.2).
    esperar "/assets/nao-existe.js"  404 "asset inexistente dá 404"
    esperar "/api/docs"              404 "superfície da API fechada"

    # Readiness pode legitimamente estar 503 (sync do Canvas atrasado) sem que
    # o deploy tenha falhado — por isso é aviso, não falha.
    local pronto
    pronto="$(codigo /api/health/ready)"
    if [[ "$pronto" == "200" ]]; then
        ok "readiness ok (banco + sync recentes)"
    else
        aviso "readiness devolveu $pronto — $(curl -sS --max-time 10 "https://$DOMINIO/api/health/ready" | head -c 200)"
    fi

    # O index recém-publicado precisa apontar para assets que existem: é o modo
    # de falha clássico de deploy com hash no nome (HTML novo, bundle velho —
    # ou o contrário).
    local asset
    asset="$(curl -sS --max-time 20 "https://$DOMINIO/" 2>/dev/null | grep -o '/assets/[A-Za-z0-9._-]*\.js' | head -1 || true)"
    if [[ -n "$asset" ]]; then
        esperar "$asset" 200 "bundle referenciado pelo index existe"
    else
        aviso "não achei referência a /assets/*.js no index — build do front?"
    fi

    # Headers de segurança: um add_header dentro de location apaga todos os
    # herdados do server, em silêncio e passando no `nginx -t` (docs/15 §9.3).
    local cabecalhos ausentes=""
    cabecalhos="$(curl -sSI --max-time 20 "https://$DOMINIO/" 2>/dev/null | tr 'A-Z' 'a-z')"
    for h in content-security-policy x-content-type-options referrer-policy x-frame-options strict-transport-security; do
        grep -q "^$h:" <<<"$cabecalhos" || ausentes+=" $h"
    done
    [[ -z "$ausentes" ]] && ok "headers de segurança presentes" \
                         || { erro "headers ausentes:$ausentes"; FALHAS=$((FALHAS + 1)); }

    # HTTP tem que redirecionar, não servir.
    local http
    http="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "http://$DOMINIO/" 2>/dev/null || echo 000)"
    [[ "$http" == "301" ]] && ok "http → https (301)" \
                           || { erro "http devolveu $http, esperado 301"; FALHAS=$((FALHAS + 1)); }

    # A regra que sustenta a segurança da stack: só o `web` publica porta. Se o
    # db ou o postgrest aparecerem aqui, estão na internet — o Docker escreve
    # no iptables por cima do ufw (docs/14 §5).
    local publicadas
    publicadas="$(ssh -o BatchMode=yes "$DESTINO" \
        'cd /opt/sas/infra/vps && docker compose ps --format "{{.Service}} {{.Ports}}"' 2>/dev/null \
        | grep -E '0\.0\.0\.0|:::' | awk '{print $1}' | sort -u | tr '\n' ' ' | xargs || true)"
    if [[ "$publicadas" == "web" ]]; then
        ok "só o web publica porta"
    else
        erro "portas publicadas por: ${publicadas:-nenhum} — esperado só 'web'"
        FALHAS=$((FALHAS + 1))
    fi

    echo
    if [[ $FALHAS -eq 0 ]]; then
        printf '  \033[0;32m● produção respondendo em https://%s\033[0m\n\n' "$DOMINIO"
    else
        printf '  \033[0;31m● %s verificação(ões) falharam\033[0m\n' "$FALHAS"
        printf '    logs:  ssh %s '"'"'cd /opt/sas/infra/vps && docker compose logs --tail=60 api web'"'"'\n\n' "$DESTINO"
        return 3
    fi
}


# ─── Fluxo ────────────────────────────────────────────────────────────────
if [[ $SO_VERIFICAR == 1 ]]; then
    verificar
    exit $?
fi

ssh -o BatchMode=yes -o ConnectTimeout=10 "$DESTINO" true 2>/dev/null \
    || { erro "sem acesso ssh a $DESTINO (chave? VPN? host certo?)"; exit 1; }

[[ $RAPIDO == 1 ]] && aviso "portões locais pulados (--rapido)" || portoes_locais
resumo_e_confirmacao
enviar_codigo
subir_no_servidor \
    || { saida=$?; erro "o deploy no servidor falhou (exit $saida)"; exit $saida; }
verificar
