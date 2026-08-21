#!/usr/bin/env bash
#
# Etapa 1 do plano de hospedagem (docs/15-plano-hospedagem-vps.md): prepara o
# VPS Ubuntu 24.04 da Hostinger para receber a stack do SAS.
#
# Roda como root, no servidor:
#
#   scp infra/vps/01-preparar-servidor.sh root@46.202.150.165:/root/
#   ssh root@46.202.150.165 'bash /root/01-preparar-servidor.sh'
#
# É IDEMPOTENTE: pode rodar de novo sem estragar nada.
#
# O endurecimento do SSH (desligar senha e login de root) NÃO roda por default,
# porque é o passo que tranca você do lado de fora se algo estiver errado. Só
# depois de confirmar que `ssh sas@<ip>` funciona por chave:
#
#   ssh root@46.202.150.165 'bash /root/01-preparar-servidor.sh --ssh-hardening'

set -euo pipefail

USUARIO="sas"
FUSO="America/Fortaleza"

log()  { printf '\n\033[1;34m▸ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
aviso(){ printf '  \033[0;33m!\033[0m %s\n' "$*"; }
erro() { printf '  \033[0;31m✗\033[0m %s\n' "$*" >&2; }

[[ $EUID -eq 0 ]] || { erro "rode como root"; exit 1; }


# ─── modo hardening (separado, por ser o passo que tranca) ────────────────
if [[ "${1:-}" == "--ssh-hardening" ]]; then
    log "Endurecendo o SSH"

    if ! id "$USUARIO" &>/dev/null; then
        erro "usuário $USUARIO não existe — rode o script sem flag primeiro"; exit 1
    fi
    if [[ ! -s "/home/$USUARIO/.ssh/authorized_keys" ]]; then
        erro "/home/$USUARIO/.ssh/authorized_keys vazio — você perderia o acesso"; exit 1
    fi
    ok "$USUARIO tem chave autorizada"

    cat > /etc/ssh/sshd_config.d/99-sas.conf <<'EOF'
# Endurecimento do SAS (infra/vps/01-preparar-servidor.sh --ssh-hardening).
# Só chave, e nunca como root: quem administra entra como `sas` e usa sudo.
PasswordAuthentication no
PermitRootLogin no
KbdInteractiveAuthentication no
EOF

    # sshd -t recusa config inválida ANTES do reload — sem isso, um erro de
    # sintaxe derruba o daemon e o acesso vai junto.
    if sshd -t; then
        systemctl reload ssh 2>/dev/null || systemctl reload sshd
        ok "senha e login de root desligados"
        aviso "NÃO FECHE ESTA SESSÃO até confirmar, de outro terminal: ssh $USUARIO@\$IP"
    else
        rm -f /etc/ssh/sshd_config.d/99-sas.conf
        erro "config de sshd inválida — revertida, nada mudou"; exit 1
    fi
    exit 0
fi


# ─── 1. identificação ─────────────────────────────────────────────────────
log "Servidor"
. /etc/os-release
ok "$PRETTY_NAME ($(uname -m))"
[[ "${VERSION_ID:-}" == "24.04" ]] || aviso "esperado Ubuntu 24.04, achei ${VERSION_ID:-?}"
ok "$(nproc) vCPU · $(free -g | awk '/^Mem:/{print $2}') GB RAM · $(df -h / | awk 'NR==2{print $4}') livres em /"


# ─── 2. fuso horário ──────────────────────────────────────────────────────
# O código usa date.today() em 7 pontos das estatísticas. Em UTC, das 21h à
# meia-noite BRT o "hoje" já é amanhã e a prova do dia seguinte entra nas
# médias (docs/14 §3.2).
log "Fuso horário"
if [[ "$(timedatectl show -p Timezone --value)" != "$FUSO" ]]; then
    timedatectl set-timezone "$FUSO"
fi
ok "$(timedatectl show -p Timezone --value) — $(date '+%d/%m/%Y %H:%M')"
aviso "o container herda UTC mesmo assim: TZ=$FUSO precisa entrar no compose"


# ─── 3. pacotes ───────────────────────────────────────────────────────────
log "Pacotes"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
# tmux entra porque o backfill do Canvas leva horas e não pode morrer com a
# sessão SSH (docs/15 §4).
apt-get install -y -qq ufw fail2ban unattended-upgrades curl git tmux ca-certificates
ok "atualizado; ufw, fail2ban, unattended-upgrades, git, tmux instalados"

dpkg-reconfigure -f noninteractive unattended-upgrades >/dev/null 2>&1 || true
ok "patches de segurança automáticos ligados"


# ─── 4. usuário de operação ───────────────────────────────────────────────
log "Usuário $USUARIO"
if id "$USUARIO" &>/dev/null; then
    ok "já existe"
else
    adduser --disabled-password --gecos "" "$USUARIO"
    ok "criado (sem senha — só chave)"
fi
usermod -aG sudo "$USUARIO"

# Herda as chaves que já funcionam para o root, senão o hardening tranca todo
# mundo do lado de fora.
if [[ -s /root/.ssh/authorized_keys ]]; then
    install -d -m 700 -o "$USUARIO" -g "$USUARIO" "/home/$USUARIO/.ssh"
    install -m 600 -o "$USUARIO" -g "$USUARIO" \
        /root/.ssh/authorized_keys "/home/$USUARIO/.ssh/authorized_keys"
    ok "chave(s) do root copiada(s): $(wc -l < /home/$USUARIO/.ssh/authorized_keys) autorizada(s)"
else
    aviso "/root/.ssh/authorized_keys vazio — autorize sua chave ANTES do --ssh-hardening"
fi


# ─── 5. docker ────────────────────────────────────────────────────────────
log "Docker"
if command -v docker &>/dev/null; then
    ok "$(docker --version)"
else
    aviso "não encontrado — instalando do repositório oficial"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
    ok "$(docker --version)"
fi

if docker compose version &>/dev/null; then
    ok "$(docker compose version)"
else
    erro "docker compose v2 ausente"; exit 1
fi

# `docker` é equivalente a root — quem está no grupo pode montar / no container.
# Aceitável aqui porque $USUARIO já tem sudo, mas é bom saber.
usermod -aG docker "$USUARIO"
ok "$USUARIO no grupo docker"

# Sem isto o json-file cresce sem limite. Com 288 sincronizações por dia, é o
# que enche o disco primeiro — antes de qualquer PDF.
log "Rotação de log do Docker"
if [[ ! -f /etc/docker/daemon.json ]]; then
    install -d -m 755 /etc/docker
    cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
    systemctl restart docker
    ok "10 MB × 3 por container"
else
    aviso "/etc/docker/daemon.json já existe — não mexi"
fi


# ─── 6. firewall ──────────────────────────────────────────────────────────
# Regras ANTES do enable. Na ordem inversa, o default deny derruba o SSH.
log "Firewall"
ufw allow 22/tcp  >/dev/null
ufw allow 80/tcp  >/dev/null
ufw allow 443/tcp >/dev/null
ufw default deny incoming  >/dev/null
ufw default allow outgoing >/dev/null
if ufw status | grep -q "^Status: active"; then
    ok "já ativo"
else
    ufw --force enable >/dev/null
    ok "ativado com 22, 80 e 443 liberadas"
fi
ufw status numbered | sed 's/^/    /'

# Armadilha conhecida: o Docker escreve no iptables direto e PASSA POR CIMA do
# ufw para portas publicadas. Por isso a stack de produção publica apenas o
# nginx — se `db` ou `postgrest` publicassem porta, o ufw não os protegeria.
aviso "Docker ignora o ufw em portas publicadas — só o nginx pode ter 'ports:'"


# ─── 7. fail2ban ──────────────────────────────────────────────────────────
log "fail2ban"
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
findtime = 10m
EOF
systemctl enable --now fail2ban >/dev/null 2>&1
systemctl restart fail2ban
ok "jail sshd ativa (5 tentativas / 10 min → 1 h de banimento)"


# ─── resumo ───────────────────────────────────────────────────────────────
log "Etapa 1 concluída"
cat <<EOF

  Próximos passos, nesta ordem:

  1. De OUTRO terminal, confirme que a chave funciona:
         ssh $USUARIO@$(hostname -I | awk '{print $1}')

  2. Só depois disso, endureça o SSH:
         ssh root@$(hostname -I | awk '{print $1}') 'bash /root/01-preparar-servidor.sh --ssh-hardening'

  3. Confira no painel da Hostinger que o firewall DELES não bloqueia 80/443 —
     é uma camada separada do ufw e não dá para ver daqui de dentro.

  Depois disso, Etapa 3: clonar o repo e subir a stack.

EOF
