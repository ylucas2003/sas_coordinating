#!/usr/bin/env bash
#
# Único passo da Etapa 3 que exige root. Roda UMA vez:
#
#   ssh root@46.202.150.165 'bash -s' < infra/vps/00-prep-root.sh
#
# Cria os dois diretórios com o dono certo, para que o deploy (02-deploy.sh)
# possa rodar inteiro como o usuário `sas`, sem sudo. Dar sudo sem senha ao
# usuário de operação seria privilégio permanente em troca da conveniência de
# uma única execução — não compensa.

set -euo pipefail

USUARIO="sas"
RAIZ="/opt/sas"
STORAGE="/opt/sas/dados/storage"
UID_APP=10001     # usuário `sas` de DENTRO da imagem (api/Dockerfile), não o do host

ok() { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "rode como root" >&2; exit 1; }
id "$USUARIO" &>/dev/null || { echo "usuário $USUARIO não existe — rode a Etapa 1" >&2; exit 1; }

# Onde o código vive. Dono é o usuário do host, que é quem recebe o rsync.
mkdir -p "$RAIZ"
chown "$USUARIO:$USUARIO" "$RAIZ"
ok "$RAIZ (dono $USUARIO)"

# Onde os PDFs vivem. Dono é o uid de DENTRO do container, que é diferente —
# o processo da API não é root e precisa escrever aqui.
mkdir -p "$STORAGE"
chown -R "$UID_APP:$UID_APP" "$(dirname "$STORAGE")"
ok "$STORAGE (dono uid $UID_APP, o da imagem)"

# Onde os scripts de cron escrevem. FORA de /opt/sas de propósito: aquele
# diretório é alvo de `rsync --delete`, e um log ali seria apagado a cada
# deploy — foi o que aconteceu com o log do primeiro backfill.
mkdir -p /var/log/sas
chown "$USUARIO:$USUARIO" /var/log/sas
ok "/var/log/sas (dono $USUARIO)"

# Sem rotação, cron.log e saude.log crescem para sempre. São ~340 linhas/dia
# hoje, mas o disco é finito e ninguém olha log que não incomoda.
cat > /etc/logrotate.d/sas <<'ROTACAO'
/var/log/sas/*.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 0644 sas sas
}
ROTACAO
ok "rotação de log configurada (8 semanas)"

# Diretórios do TLS. O ACME é o webroot do desafio do Let's Encrypt e o TLS
# guarda a CÓPIA do certificado — ambos lidos pelo nginx, que roda como uid
# 101 e não consegue ler /etc/letsencrypt, onde a chave privada é só de root.
mkdir -p /opt/sas/dados/acme /opt/sas/dados/tls
chown -R 101:101 /opt/sas/dados/acme /opt/sas/dados/tls
chmod 750 /opt/sas/dados/tls
ok "/opt/sas/dados/{acme,tls} (dono uid 101, o do nginx)"

echo
echo "  Pronto. Agora, da sua máquina:"
echo "      ./infra/vps/sync.sh"
echo "      ssh $USUARIO@\$IP 'bash /opt/sas/infra/vps/02-deploy.sh'"
