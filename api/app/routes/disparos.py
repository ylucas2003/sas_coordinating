"""Despachante do motor de lembretes — o tick.

O cron do VPS chama /disparos/processar de hora em hora;
esta rota é o nome verdadeiro da operação e o alvo dos curls manuais. O sync
de 5 min também chama o despachante no fim da sua rodada (canvas_sync/rotas.py)
— com o tick horário sozinho, um lembrete das 18:00 materializado às 18:05
esperaria uma hora.

Ver docs/12-plano-p2-motor-lembretes.md §4.5 e docs/13-plano-p3-lembrete-aluno.md §4.4.
"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends

from ..auth import exigir_scheduler_secret
from ..lembretes.despachante import processar_disparos_vencidos
from ..supabase_client import get_supabase

router = APIRouter(prefix="/disparos", tags=["disparos"])

# Evita rodadas sobrepostas — uma rodada de P3 leva minutos, e o EventBridge
# re-entrega chamada que demora a responder. O claim por disparo já torna o
# atropelo inofensivo; a trava evita o desperdício e o log sujo. Mesmo padrão
# de canvas_sync/rotas.py.
_trava_despacho = threading.Lock()


async def despachar_se_livre() -> dict[str, Any]:
    """Uma rodada, se ninguém estiver rodando. Ponto único de entrada — usado
    pela rota e pelo fim do sync do Canvas."""
    if not _trava_despacho.acquire(blocking=False):
        return {"status": "ignorado", "motivo": "despacho anterior ainda em andamento"}
    try:
        return await processar_disparos_vencidos(get_supabase())
    finally:
        _trava_despacho.release()


@router.post("/processar")
async def processar_disparos(_: None = Depends(exigir_scheduler_secret)) -> dict:
    return await despachar_se_livre()
