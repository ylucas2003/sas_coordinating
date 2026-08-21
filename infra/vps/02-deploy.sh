#!/usr/bin/env bash
#
# Etapa 3 do plano de hospedagem (docs/15-plano-hospedagem-vps.md): coloca o
# código no servidor e sobe a stack de produção.
#
# Roda como o usuário `sas` (que está no grupo docker), NÃO como root:
#
#   ssh sas@46.202.150.165 'bash -s' < infra/vps/02-deploy.sh
#
# IDEMPOTENTE: da segunda vez em diante vira o comando de deploy — puxa o
# código novo, reconstrói e reinicia sem tocar no .env nem no banco.

set -euo pipefail

RAIZ="/opt/sas"
REPO="https://github.com/ylucas2003/sas_coordinating.git"
BRANCH="main"
STORAGE="/opt/sas/dados/storage"
UID_APP=10001          # usuário `sas` de dentro da imagem (api/Dockerfile)

log()  { printf '\n\033[1;34m▸ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
aviso(){ printf '  \033[0;33m!\033[0m %s\n' "$*"; }
erro() { printf '  \033[0;31m✗\033[0m %s\n' "$*" >&2; }

command -v docker >/dev/null || { erro "docker ausente — rode a Etapa 1 antes"; exit 1; }


# ─── 1. código ────────────────────────────────────────────────────────────
# O código chega por `rsync` da máquina de desenvolvimento (infra/vps/sync.sh),
# não por `git clone`: a árvore de trabalho local ainda tem mudanças não
# commitadas, e um clone do GitHub subiria uma versão diferente da testada.
# Quando o repositório estiver em dia, trocar por git pull aqui é trivial.
log "Código"
if [[ -d "$RAIZ/infra/vps" ]]; then
    if [[ -d "$RAIZ/.git" ]]; then
        ok "presente em $RAIZ ($(git -C "$RAIZ" rev-parse --short HEAD 2>/dev/null || echo 'sem git'))"
    else
        ok "presente em $RAIZ (enviado por rsync)"
    fi
else
    erro "código ausente em $RAIZ — rode infra/vps/sync.sh da sua máquina primeiro"
    exit 1
fi

cd "$RAIZ/infra/vps"


# ─── 2. storage ───────────────────────────────────────────────────────────
# A imagem prod roda como uid 10001 e NÃO é root. Um volume nomeado nasceria
# root e o upload falharia com PermissionError; por isso é bind mount com dono
# explícito (docs/14 §5).
#
# Este script NÃO usa sudo de propósito: dar sudo sem senha ao usuário de
# operação é privilégio permanente para conveniência de uma vez. O diretório é
# criado uma única vez pelo root, em 00-prep-root.sh.
log "Storage dos PDFs"
if [[ ! -d "$STORAGE" ]]; then
    erro "$STORAGE não existe"
    erro "rode uma vez, como root: bash /opt/sas/infra/vps/00-prep-root.sh"
    exit 1
fi
dono="$(stat -c '%u' "$STORAGE")"
if [[ "$dono" != "$UID_APP" ]]; then
    erro "$STORAGE pertence ao uid $dono, deveria ser $UID_APP"
    erro "rode como root: chown -R $UID_APP:$UID_APP $(dirname "$STORAGE")"
    exit 1
fi
ok "$STORAGE (dono uid $UID_APP)"


# ─── 3. segredos ──────────────────────────────────────────────────────────
log "Configuração"
if [[ -f .env ]]; then
    ok ".env já existe — preservado (segredos não são regerados)"
else
    cp .env.example .env
    # Sorteados aqui, no servidor: nunca trafegam por chat, e-mail ou git.
    for chave in POSTGRES_PASSWORD POSTGREST_PASSWORD JWT_SECRET_KEY SCHEDULER_SECRET; do
        valor="$(openssl rand -hex 32)"
        sed -i "s|^${chave}=.*|${chave}=${valor}|" .env
    done
    # Senha da coordenação: legível, para alguém conseguir digitar.
    senha="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
    sed -i "s|^COORDENADOR_SENHA=.*|COORDENADOR_SENHA=${senha}|" .env
    chmod 600 .env
    ok "gerado com segredos aleatórios (chmod 600)"
    printf '\n  \033[1;33mSENHA DA COORDENAÇÃO: %s\033[0m\n' "$senha"
    printf '  Anote agora — ela não será mostrada de novo.\n\n'
fi

# O guard de boot recusa subir sem estes dois.
for obrigatoria in JWT_SECRET_KEY COORDENADOR_SENHA; do
    if ! grep -qE "^${obrigatoria}=.+" .env; then
        erro "$obrigatoria vazia no .env — a API não vai subir"; exit 1
    fi
done
ok "segredos obrigatórios presentes"

grep -qE '^CANVAS_API_TOKEN=.+' .env \
    && ok "token do Canvas configurado" \
    || aviso "CANVAS_API_TOKEN vazia — o sync não roda (necessária na Etapa 4)"
grep -qE '^OPENAI_API_KEY=.+' .env \
    && ok "chave da OpenAI configurada" \
    || aviso "OPENAI_API_KEY vazia — insights e chat ficam desligados (degrada limpo)"


# ─── 4. subir ─────────────────────────────────────────────────────────────
log "Build e subida"
docker compose build --quiet
docker compose up -d
ok "containers no ar"

echo
docker compose ps --format "  {{.Service}}\t{{.Status}}\t{{.Ports}}"


# ─── 5. verificar ─────────────────────────────────────────────────────────
log "Verificação"

# A API leva alguns segundos até o uvicorn atender.
for i in $(seq 1 30); do
    if curl -fsS --max-time 3 http://127.0.0.1/api/health >/dev/null 2>&1; then break; fi
    sleep 2
done

resp="$(curl -fsS --max-time 5 http://127.0.0.1/api/health 2>/dev/null || echo FALHOU)"
[[ "$resp" != "FALHOU" ]] && ok "API responde através do nginx: $resp" \
                          || { erro "API não respondeu em /api/health"; docker compose logs --tail=40 api; exit 1; }

curl -fsS --max-time 5 http://127.0.0.1/health >/dev/null 2>&1 \
    && ok "nginx responde" || aviso "nginx não respondeu em /health"

curl -fsS --max-time 5 -o /dev/null http://127.0.0.1/ 2>/dev/null \
    && ok "front estático servido" || aviso "front não respondeu em /"

# A regra que sustenta a segurança da stack: só o web publica porta.
log "Portas publicadas (só o web pode aparecer)"
docker compose ps --format "{{.Service}} {{.Ports}}" | grep -E "0\.0\.0\.0|:::" | sed 's/^/  /' || echo "  (nenhuma)"

log "Etapa 3 concluída"
cat <<'EOF'

  Próximo: Etapa 4 (banco).

      cd /opt/sas/infra/vps
      docker compose run --rm migrate status
      docker compose run --rm migrate up
      docker compose restart postgrest     # o PostgREST cacheia o schema no boot

  O banco ainda está vazio: a API sobe, mas qualquer tela com dado volta erro.

EOF
