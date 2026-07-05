"""Rota do sync incremental — POST /canvas-sync/run.

Chamada pelo EventBridge (infra/) a cada 5 min com o header X-Scheduler-Secret.
Executa de forma síncrona (sem BackgroundTasks): uma falha vira resposta 500,
que fica visível na entrega do EventBridge — um cron não precisa de resposta
imediata, precisa de erro observável.

O handler é `def` (síncrono) de propósito: o FastAPI o executa no threadpool,
e o `asyncio.run` interno roda o cliente async do Canvas num loop próprio —
o loop principal fica livre pra servir /health e o resto da API enquanto o
sync roda.
"""

from __future__ import annotations

import asyncio
import threading

from fastapi import APIRouter, Depends, HTTPException

from ..auth import exigir_scheduler_secret
from ..config import get_settings
from ..ingest.upsert import criar_execucao_sync, finalizar_execucao_sync
from ..supabase_client import criar_cliente_supabase
from .cliente import ClienteCanvas
from .sincronizar import ResumoSincronizacao, sincronizar_ano_atual

router = APIRouter(prefix="/canvas-sync", tags=["canvas-sync"])

# Evita rodadas sobrepostas se uma execução passar dos 5 min do intervalo.
_trava_execucao = threading.Lock()


async def _executar() -> ResumoSincronizacao:
    settings = get_settings()
    # Cliente novo (não cacheado): conexão TCP isolada do resto da API —
    # mesma razão documentada em routes/uploads.py.
    cliente = criar_cliente_supabase()
    async with ClienteCanvas(
        base_url=settings.canvas_base_url, token=settings.canvas_api_token
    ) as canvas:
        return await sincronizar_ano_atual(
            cliente=cliente,
            canvas=canvas,
            account_id=settings.canvas_account_id,
            override_ano=settings.canvas_ano_vigente or None,
            lookback_minutos=int(settings.canvas_sync_lookback_minutos),
        )


@router.post("/run")
def executar_sync(_: None = Depends(exigir_scheduler_secret)) -> dict:
    if not _trava_execucao.acquire(blocking=False):
        return {"status": "ignorado", "motivo": "sync anterior ainda em andamento"}

    # TUDO depois do acquire fica dentro do try — se qualquer passo (inclusive
    # criar a linha de auditoria) falhar, a trava é liberada mesmo assim.
    # Sem isso, uma falha aqui deixaria todos os syncs futuros em "ignorado".
    execucao_id: str | None = None
    try:
        cliente = criar_cliente_supabase()
        execucao_id = criar_execucao_sync(cliente, tipo="incremental")
        resumo = asyncio.run(_executar())
        finalizar_execucao_sync(
            cliente, execucao_id=execucao_id, status="sucesso", resumo=resumo.como_dict()
        )
        return {"status": "ok", "execucao_id": execucao_id, **resumo.como_dict()}
    except Exception as exc:
        if execucao_id is not None:
            try:
                finalizar_execucao_sync(
                    cliente, execucao_id=execucao_id, status="erro", erro_mensagem=str(exc)
                )
            except Exception:
                pass  # auditoria não pode mascarar o erro original
        raise HTTPException(status_code=500, detail=f"sync falhou: {exc}")
    finally:
        _trava_execucao.release()
