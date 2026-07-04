"""Cobrança de professores (WhatsApp/Z-API) — placeholder.

O schedule CobrancaProfessor do EventBridge (infra/) já chama esta rota a
cada 1h. A lógica real (fila de cobrança, envio via Z-API, botões) fica pra
quando as decisões em aberto forem tomadas: conta Z-API, fonte do telefone
do professor (não vem do Canvas — ver docs/08-integracao-canvas.md §4.2),
cadência dos lembretes e fluxo de botões.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import exigir_scheduler_secret

router = APIRouter(prefix="/cobranca", tags=["cobranca"])


@router.post("/verificar")
async def verificar_cobranca(_: None = Depends(exigir_scheduler_secret)) -> dict:
    return {"status": "not_implemented"}
