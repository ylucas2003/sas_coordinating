"""O sync do Canvas está fazendo o trabalho dele? — a regra do "atrasado".

Nasceu dentro do `/health/ready` (main.py), que existe por causa do modo de
falha mais provável da migração para a VPS: o agendador parar de disparar. Aí a
API responde 200 em tudo e os dados simplesmente congelam — o coordenador só
percebe dias depois (docs/14 §5, ops).

Desceu para cá porque deixou de ter um leitor só: a tool do assistente que
responde "o Canvas está sincronizando?" (docs/43 §4.3) precisa da mesma
resposta, e copiar os 30 minutos para dentro dela seria a segunda definição de
"sync atrasado".
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from supabase import Client


def limite_em_minutos() -> int:
    """`SYNC_ALERTA_MINUTOS`, relido a cada chamada, como o /health/ready sempre leu.

    30 min = 6x o intervalo do sync incremental (5 min). Tolera uma rodada
    longa ou uma indisponibilidade curta do Canvas sem alarme falso, e ainda
    detecta cron parado no mesmo turno de trabalho.

    Valor que não é inteiro levanta `ValueError`: é erro de configuração, e o
    /health/ready o deixa subir em vez de reportá-lo como sync atrasado.
    """
    return int(os.environ.get("SYNC_ALERTA_MINUTOS", "30"))


def ultimo_sync(
    cliente: Client,
    agora: datetime | None = None,
    *,
    limite_minutos: int | None = None,
) -> dict[str, Any]:
    """O último sync bem-sucedido e se ele está atrasado.

    Devolve `{ultimoSync, haMinutos, limiteMinutos, atrasado}`:

      * `ultimoSync` — ISO 8601 do `finalizado_em` da última rodada com
        `status='sucesso'`, de qualquer tipo; `None` se nunca houve uma.
      * `haMinutos` — minutos inteiros desde então, arredondados para baixo;
        `None` junto com `ultimoSync`.
      * `atrasado` — a idade passou do limite. Compara a idade EXATA, não
        `haMinutos`: 30 min e 30 s com limite 30 já é atraso, embora
        `haMinutos` diga 30. Nunca ter sincronizado também é atraso: o sync
        não está fazendo o trabalho dele.

    Não engole erro: banco fora do ar ou `finalizado_em` ilegível levantam, e
    quem chama decide o que dizer — o /health/ready transforma em 503.

    `agora` existe para teste; `limite_minutos`, para o /health/ready ler a
    variável uma vez só, no mesmo ponto em que sempre leu.
    """
    limite = limite_em_minutos() if limite_minutos is None else limite_minutos
    linhas = (
        cliente.table("canvas_sync_execucao")
        .select("finalizado_em, status")
        .eq("status", "sucesso")
        .order("finalizado_em", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not linhas:
        return {"ultimoSync": None, "haMinutos": None, "limiteMinutos": limite, "atrasado": True}

    quando = datetime.fromisoformat(str(linhas[0]["finalizado_em"]).replace("Z", "+00:00"))
    idade = (agora or datetime.now(UTC)) - quando
    return {
        "ultimoSync": quando.isoformat(),
        "haMinutos": int(idade.total_seconds() // 60),
        "limiteMinutos": limite,
        "atrasado": idade > timedelta(minutes=limite),
    }
