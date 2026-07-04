"""Sincronização direta com o Canvas LMS — substitui o import manual de planilha.

Contexto e mapeamento completo em docs/08-integracao-canvas.md. Submódulos:

    cliente.py      — wrapper async (httpx) sobre a REST API do Canvas
    mapeador.py     — funções puras: JSON do Canvas → dicts pro ingest/upsert.py
    sincronizar.py  — orquestração (incremental do ano vigente + backfill histórico)
    rotas.py        — POST /canvas-sync/run (chamado pelo EventBridge a cada 5 min)
"""
