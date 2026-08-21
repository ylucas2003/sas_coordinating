"""DEPRECATED — use POST /disparos/processar.

Este path continua existindo por um motivo só: é o endpoint que o schedule
CobrancaProfessor do EventBridge conhece (infra/sas_scheduler/), e renomear
lá exige `cdk deploy`. O rename pega carona no próximo deploy de infra que
existir por outro motivo; até lá, este delegate mantém o tick horário
alimentando o despachante do motor de lembretes (P2).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import exigir_scheduler_secret
from .disparos import despachar_se_livre

router = APIRouter(prefix="/cobranca", tags=["cobranca"])


@router.post("/verificar")
async def verificar_cobranca(_: None = Depends(exigir_scheduler_secret)) -> dict:
    return await despachar_se_livre()
