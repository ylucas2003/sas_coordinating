#!/usr/bin/env bash
#
# Disparo de um job agendado do SAS (docs/15 §Etapa 6). Chamado pelo crontab
# do usuário `sas`:
#
#   cron-sas.sh /canvas-sync/run 280
#
# TRÊS coisas que o comando do plano original não previa, todas específicas
# desta topologia:
#
# 1. A API NÃO tem porta publicada no host — só o nginx tem. Um curl em
#    127.0.0.1:8000 não conecta. É de propósito: é o que mantém a API e o
#    PostgREST fora da internet (docs/14 §5).
# 2. A porta 80 redireciona para HTTPS desde a Etapa 5, então um curl em
#    http://127.0.0.1/api/... recebe 301 e nunca chega no endpoint.
# 3. Por isso o `--resolve`: fala HTTPS com o próprio host, sem sair para a
#    internet e sem depender de DNS externo, mas com o Host e o SNI corretos
#    para o certificado bater.
set -uo pipefail

ROTA="${1:?uso: cron-sas.sh /rota [max-time]}"
MAXTIME="${2:-280}"

ENV_FILE="/opt/sas/infra/vps/.env"
LOG="/var/log/sas/cron.log"
DOMINIO="portalsas.online"

registrar() { echo "$(date -Is) $ROTA $*" >> "$LOG"; }

# O backfill roda num container `sas-api-run-*` separado, e a trava do
# canvas_sync é um threading.Lock DE PROCESSO (docs/14 §7) — ela não coordena
# entre containers. Enquanto houver backfill em andamento, o sync incremental
# escreveria por cima dele.
if [[ "$ROTA" == /canvas-sync/* ]] && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^sas-api-run-'; then
    registrar "pulado (backfill em andamento)"
    exit 0
fi

SEGREDO="$(grep -E '^SCHEDULER_SECRET=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | xargs)"
if [[ -z "$SEGREDO" ]]; then
    registrar "ERRO segredo-vazio (as rotas devolveriam 503)"
    exit 1
fi

SAIDA="$(mktemp)"
INICIO="$(date +%s)"
CODIGO="$(curl -s -o "$SAIDA" -w '%{http_code}' \
    --max-time "$MAXTIME" \
    --resolve "$DOMINIO:443:127.0.0.1" \
    -X POST -H "X-Scheduler-Secret: $SEGREDO" \
    "https://$DOMINIO/api$ROTA" 2>/dev/null)"
DURACAO=$(( $(date +%s) - INICIO ))
CORPO="$(head -c 220 "$SAIDA" | tr -d '\n')"
rm -f "$SAIDA"

registrar "http=$CODIGO ${DURACAO}s $CORPO"
[[ "$CODIGO" == 2* ]] || exit 1
