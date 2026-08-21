#!/usr/bin/env bash
#
# Etapa 5 do plano (docs/15): emite e instala o certificado TLS.
#
#   ssh root@<ip> 'bash -s' < infra/vps/03-tls.sh
#
# Existe porque, na primeira montagem, todo o TLS foi feito por comandos
# avulsos e nada disso ficou no repositório — um servidor reconstruído pelos
# scripts subiria SEM HTTPS, e o sintoma só apareceria no navegador do usuário.
#
# IDEMPOTENTE: o certbot não reemite certificado válido, e o resto é mkdir e
# cópia. Pode rodar de novo sem risco.
#
# PRÉ-REQUISITOS: 00-prep-root.sh (cria os diretórios) e a stack no ar com a
# porta 80 aberta — o desafio HTTP-01 precisa chegar no nginx.

set -euo pipefail

DOMINIO="${SAS_DOMINIO:-portalsas.online}"
EMAIL="${SAS_EMAIL_ACME:-ylucas2003@gmail.com}"
WEBROOT="/opt/sas/dados/acme"
HOOK="/etc/letsencrypt/renewal-hooks/deploy/sas-renovar-tls.sh"

log()  { printf '\n\033[1;34m▸ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
erro() { printf '  \033[0;31m✗\033[0m %s\n' "$*" >&2; }

[[ $EUID -eq 0 ]] || { erro "rode como root"; exit 1; }
[[ -d "$WEBROOT" ]] || { erro "$WEBROOT não existe — rode 00-prep-root.sh antes"; exit 1; }


log "certbot"
if command -v certbot >/dev/null; then
    ok "$(certbot --version 2>&1)"
else
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot >/dev/null
    ok "$(certbot --version 2>&1) instalado"
fi
systemctl enable --now certbot.timer >/dev/null 2>&1 || true
ok "timer de renovação: $(systemctl is-enabled certbot.timer 2>/dev/null || echo '?')"


# O hook roda como root a cada renovação e copia o certificado para um lugar
# que o nginx (uid 101) consiga ler. Sem ele, a renovação acontece e o nginx
# continua servindo o certificado velho até alguém notar.
log "Hook de renovação"
install -D -m 755 /opt/sas/infra/vps/renovar-tls.sh "$HOOK"
ok "$HOOK"


log "Certificado para $DOMINIO"
if certbot certificates 2>/dev/null | grep -q "Domains:.*\b$DOMINIO\b"; then
    ok "já existe — certbot renova sozinho pelo timer"
else
    certbot certonly --webroot -w "$WEBROOT" \
        -d "$DOMINIO" -d "www.$DOMINIO" \
        --agree-tos -m "$EMAIL" --non-interactive --no-eff-email
    ok "emitido"
fi

# Hooks de deploy não rodam na emissão inicial, só na renovação — por isso a
# chamada explícita.
log "Instalando o certificado para o nginx"
bash "$HOOK"


log "Verificação"
if certbot renew --dry-run >/dev/null 2>&1; then
    ok "ensaio de renovação passou"
else
    erro "ensaio de renovação FALHOU — em ~60 dias o site cai sozinho"
    erro "investigue com: certbot renew --dry-run"
    exit 1
fi

echo
echo "  Depois disto, ajuste no .env e reinicie a api:"
echo "      API_BASE_URL=https://$DOMINIO/api"
echo "  (sem o sufixo /api, o link de download cai no fallback do SPA e"
echo "   devolve HTML com status 200 — ver docs/15 §Etapa 9)"
