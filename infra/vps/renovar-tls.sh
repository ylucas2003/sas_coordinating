#!/usr/bin/env bash
#
# Deploy hook do certbot: instalado em
# /etc/letsencrypt/renewal-hooks/deploy/ e executado como root a cada
# emissão ou renovação de certificado.
#
# Existe porque /etc/letsencrypt/live guarda a chave privada com permissão
# só para root, e o nginx desta stack roda como uid 101 (imagem
# unprivileged). Copia os dois arquivos com o dono certo e recarrega o web.
set -euo pipefail

DOMINIO="portalsas.online"
DESTINO="/opt/sas/dados/tls"
ORIGEM="/etc/letsencrypt/live/$DOMINIO"

[[ -f "$ORIGEM/fullchain.pem" ]] || { echo "sem certificado em $ORIGEM"; exit 0; }

install -o 101 -g 101 -m 644 "$ORIGEM/fullchain.pem" "$DESTINO/fullchain.pem"
install -o 101 -g 101 -m 640 "$ORIGEM/privkey.pem"   "$DESTINO/privkey.pem"
echo "certificado copiado para $DESTINO"

if [[ -d /opt/sas/infra/vps ]]; then
    cd /opt/sas/infra/vps && docker compose restart web >/dev/null 2>&1 \
        && echo "nginx recarregado"
fi
