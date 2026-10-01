#!/usr/bin/env bash
#
# Reabre as aulas que o pipeline de vídeo largou por falha do S3. Roda da
# máquina de desenvolvimento, e o trabalho acontece no container da API.
#
#   ./infra/vps/reabrir-aulas.sh                        # ensaio: só mostra
#   ./infra/vps/reabrir-aulas.sh --aplicar              # reabre
#   ./infra/vps/reabrir-aulas.sh --aplicar --disparar   # reabre e já começa uma rodada
#   ./infra/vps/reabrir-aulas.sh --todas                # qualquer erro, não só S3
#
# O porquê de cada decisão está em api/scripts/reabrir_aulas_com_erro.py.
#
# Variáveis de ambiente:
#   SAS_VPS   destino ssh (default sas@46.202.150.165)

set -euo pipefail

DESTINO="${SAS_VPS:-sas@46.202.150.165}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$RAIZ/api/scripts/reabrir_aulas_com_erro.py"

# O script viaja por stdin, como a parte remota do deploy.sh: roda a versão
# DESTE checkout dentro do container, sem depender de deploy. É o que permite
# usá-lo na hora em que o S3 volta, com as gravações correndo para sair do
# Canvas. Os imports `app.*` resolvem porque o WORKDIR do container é /app.
#
# As opções só entram se existirem. `printf '%q '` sem argumento nenhum
# devolve `''`, e o argparse recusaria o ensaio por um argumento vazio.
ARGS=""
if [[ $# -gt 0 ]]; then
    ARGS="$(printf '%q ' "$@")"
fi

ssh -o BatchMode=yes "$DESTINO" \
    "cd /opt/sas/infra/vps && docker compose exec -T api python - $ARGS" <"$SCRIPT"
