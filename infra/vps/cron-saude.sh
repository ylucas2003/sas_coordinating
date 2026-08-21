#!/usr/bin/env bash
#
# Vigia do /health/ready (docs/15 §Etapa 8). Roda de 10 em 10 min pelo cron.
#
# O endpoint sozinho não alerta ninguém — o que fecha o ciclo é alguém
# consultá-lo. Enquanto o envio de e-mail está adiado, o "alerta" possível é
# um log e um arquivo de estado; quando houver canal de notificação, é aqui
# que ele entra (uma linha no ramo DEGRADADO).
#
# O modo de falha que isto existe para pegar: o cron do sync parar. Nesse
# cenário a API responde 200 em tudo, o /health diz ok, e os dados congelam
# em silêncio (docs/14 §5, ops).
set -uo pipefail

LOG="/var/log/sas/saude.log"
ESTADO="/var/log/sas/saude-estado.txt"
DOMINIO="portalsas.online"

CORPO="$(curl -s --max-time 25 --resolve "$DOMINIO:443:127.0.0.1" \
    -w '\n%{http_code}' "https://$DOMINIO/api/health/ready" 2>/dev/null)"
CODIGO="$(tail -n1 <<<"$CORPO")"
CORPO="$(head -n-1 <<<"$CORPO" | tr -d '\n')"
AGORA="$(date -Is)"

if [[ "$CODIGO" == "200" ]]; then
    echo "$AGORA OK $CORPO" >> "$LOG"
    echo "$AGORA OK" > "$ESTADO"
    exit 0
fi

# Repetido no log e no arquivo de estado: o log dá a série histórica, o estado
# responde "e agora?" sem precisar ler o log inteiro.
echo "$AGORA DEGRADADO http=$CODIGO $CORPO" >> "$LOG"
echo "$AGORA DEGRADADO http=$CODIGO $CORPO" > "$ESTADO"

# Também no syslog, que é onde um coletor futuro vai procurar primeiro.
logger -t sas-saude -p daemon.err "SAS degradado: http=$CODIGO $CORPO"
exit 1
