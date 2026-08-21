#!/usr/bin/env bash
#
# Envia a árvore de trabalho local para /opt/sas no VPS.
#
#   ./infra/vps/sync.sh
#
# Por que rsync e não `git clone` no servidor: a árvore local ainda tem
# mudanças não commitadas (o P3 inteiro, entre outras), então um clone do
# GitHub subiria uma versão diferente da que você está testando. Quando o
# repositório estiver em dia, trocar por git pull no 02-deploy.sh é trivial.
#
# NUNCA envia .env: os segredos de produção são gerados no servidor e ficam
# só lá (02-deploy.sh). Como estão em --exclude, o --delete também não os toca.

set -euo pipefail

DESTINO="${1:-sas@46.202.150.165}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "▸ Enviando $RAIZ → $DESTINO:/opt/sas"

rsync -az --delete --stats \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache/' \
    --exclude '.mypy_cache/' \
    --exclude '.dados/' \
    --exclude '/dados/' \
    --exclude '*.log' \
    --exclude '/web/dist/' \
    --exclude 'cdk.out/' \
    --exclude 'node_modules/' \
    --exclude 'dist/' \
    --exclude '.DS_Store' \
    --exclude '.env' \
    --exclude 'grading_prototype/dados_exemplo/' \
    --exclude 'grading_prototype/resultados/' \
    "$RAIZ/" "$DESTINO:/opt/sas/"

echo "▸ Pronto. Para subir:"
echo "    ssh $DESTINO 'bash /opt/sas/infra/vps/02-deploy.sh'"
